package com.petreca;

import software.amazon.awscdk.*;
import software.amazon.awscdk.services.apigateway.CorsOptions;
import software.amazon.awscdk.services.apigateway.IResource;
import software.amazon.awscdk.services.apigateway.LambdaIntegration;
import software.amazon.awscdk.services.apigateway.RestApi;
import software.amazon.awscdk.services.dynamodb.*;
import software.amazon.awscdk.services.ec2.*;
import software.amazon.awscdk.services.elasticache.CfnCacheCluster;
import software.amazon.awscdk.services.elasticache.CfnSubnetGroup;
import software.amazon.awscdk.services.events.EventBus;
import software.amazon.awscdk.services.events.EventPattern;
import software.amazon.awscdk.services.events.Rule;
import software.amazon.awscdk.services.events.targets.SqsQueue;
import software.amazon.awscdk.services.iam.PolicyStatement;
import software.amazon.awscdk.services.iam.Role;
import software.amazon.awscdk.services.iam.ServicePrincipal;
import software.amazon.awscdk.services.kinesisfirehose.CfnDeliveryStream;
import software.amazon.awscdk.services.lambda.*;
import software.amazon.awscdk.services.lambda.Runtime;
import software.amazon.awscdk.services.lambda.eventsources.S3EventSource;
import software.amazon.awscdk.services.lambda.eventsources.SqsEventSource;
import software.amazon.awscdk.services.logs.LogGroup;
import software.amazon.awscdk.services.logs.LogStream;
import software.amazon.awscdk.services.logs.RetentionDays;
import software.amazon.awscdk.services.s3.*;
import software.amazon.awscdk.services.sns.Topic;
import software.amazon.awscdk.services.sqs.DeadLetterQueue;
import software.amazon.awscdk.services.sqs.Queue;
import software.amazon.awscdk.services.ssm.StringParameter;
import software.constructs.Construct;

import java.util.List;
import java.util.Map;

public class ProductApiStack extends Stack {

    private static final String TABLE_NAME_ENV = "PRODUCTS_TABLE_NAME";
    private static final String CATEGORY_GSI_NAME = "category-index";
    private static final String BUCKET_NAME_ENV = "PRODUCT_IMAGE_BUCKET";
    private static final String REDIS_HOST_ENV = "REDIS_HOST";
    private static final String REDIS_PORT_ENV = "REDIS_PORT";
    private static final String SSM_CONFIG_PREFIX_ENV = "SSM_CONFIG_PREFIX";
    private static final String FIREHOSE_STREAM_NAME = "customer-activity-stream";

    // Records Java 21 para encapsulamento (SonarQube java:S107 Fix)
    public record LambdaNetworkConfig(Vpc vpc, SecurityGroup securityGroup) {}

    public record LambdaConfig(
            boolean isWritable,
            LambdaNetworkConfig networkConfig,
            Map<String, String> extraEnvVars,
            Duration timeout
    ) {
        public static LambdaConfig of(boolean isWritable, LambdaNetworkConfig networkConfig, Map<String, String> extraEnvVars) {
            return new LambdaConfig(isWritable, networkConfig, extraEnvVars, Duration.seconds(5));
        }

        public static LambdaConfig of(boolean isWritable, LambdaNetworkConfig networkConfig, Map<String, String> extraEnvVars, Duration timeout) {
            return new LambdaConfig(isWritable, networkConfig, extraEnvVars, timeout);
        }
    }

    public ProductApiStack(final Construct scope, final String constructId, final StackProps props) {
        super(scope, constructId, props);

        Tags.of(this).add("Project", "ServerlessApi");
        Tags.of(this).add("Environment", "Development");
        Tags.of(this).add("ManagedBy", "AWS-CDK");

        final Object envObj = this.getNode().tryGetContext("environment");
        final String envScope = (envObj instanceof String envStr && !envStr.isBlank()) ? envStr : "dev";
        final String ssmPrefixPath = "/store/" + envScope + "/config";

        // 1. Tabela DynamoDB
        final Table productsTable = Table.Builder.create(this, "ProductsTable")
                .tableName("Products")
                .partitionKey(Attribute.builder().name("id").type(AttributeType.STRING).build())
                .billingMode(BillingMode.PAY_PER_REQUEST)
                .removalPolicy(RemovalPolicy.DESTROY)
                .build();

        productsTable.addGlobalSecondaryIndex(GlobalSecondaryIndexProps.builder()
                .indexName(CATEGORY_GSI_NAME)
                .partitionKey(Attribute.builder().name("category").type(AttributeType.STRING).build())
                .projectionType(ProjectionType.ALL)
                .build());

        // 2. Bucket S3 de Mídias
        final Bucket assetsBucket = Bucket.Builder.create(this, "ProductAssetsBucket")
                .versioned(true)
                .encryption(BucketEncryption.S3_MANAGED)
                .blockPublicAccess(BlockPublicAccess.BLOCK_ALL)
                .removalPolicy(RemovalPolicy.DESTROY)
                .autoDeleteObjects(true)
                .build();

        assetsBucket.addLifecycleRule(LifecycleRule.builder()
                .id("ProductImageLifecycle")
                .enabled(true)
                .prefix("products/")
                .transitions(List.of(
                        Transition.builder().transitionAfter(Duration.days(30)).storageClass(StorageClass.INFREQUENT_ACCESS).build(),
                        Transition.builder().transitionAfter(Duration.days(90)).storageClass(StorageClass.GLACIER).build()
                ))
                .expiration(Duration.days(2555))
                .build());

        // 2.1. Bucket S3 Data Lake
        final Bucket analyticsBucket = Bucket.Builder.create(this, "AnalyticsDataLakeBucket")
                .encryption(BucketEncryption.S3_MANAGED)
                .blockPublicAccess(BlockPublicAccess.BLOCK_ALL)
                .removalPolicy(RemovalPolicy.DESTROY)
                .autoDeleteObjects(true)
                .build();

        analyticsBucket.addLifecycleRule(LifecycleRule.builder()
                .id("AnalyticsDataLakeLifecycle")
                .enabled(true)
                .prefix("analytics/")
                .transitions(List.of(
                        Transition.builder().transitionAfter(Duration.days(90)).storageClass(StorageClass.INFREQUENT_ACCESS).build(),
                        Transition.builder().transitionAfter(Duration.days(180)).storageClass(StorageClass.GLACIER).build()
                ))
                .expiration(Duration.days(365))
                .build());

        analyticsBucket.addLifecycleRule(LifecycleRule.builder()
                .id("AnalyticsErrorsLifecycle")
                .enabled(true)
                .prefix("errors/")
                .expiration(Duration.days(90))
                .build());

        // 3. VPC & ElastiCache Redis
        final Vpc vpc = Vpc.Builder.create(this, "ProductApiVpc").maxAzs(2).build();

        final SecurityGroup cacheSecurityGroup = SecurityGroup.Builder.create(this, "CacheSecurityGroup")
                .vpc(vpc)
                .description("Permite acesso ao ElastiCache Redis na porta 6379 a partir da VPC")
                .allowAllOutbound(true)
                .build();

        cacheSecurityGroup.addIngressRule(Peer.ipv4(vpc.getVpcCidrBlock()), Port.tcp(6379), "Acesso ao Redis Cache");

        final List<String> isolatedSubnetIds = vpc.getIsolatedSubnets().stream().map(ISubnet::getSubnetId).toList();
        final List<String> privateSubnetIds = vpc.getPrivateSubnets().stream().map(ISubnet::getSubnetId).toList();
        final List<String> cacheSubnetIds = isolatedSubnetIds.isEmpty() ? privateSubnetIds : isolatedSubnetIds;

        final CfnSubnetGroup cacheSubnetGroup = CfnSubnetGroup.Builder.create(this, "CacheSubnetGroup")
                .description("Subnets privadas para o ElastiCache Redis")
                .subnetIds(cacheSubnetIds)
                .build();

        final CfnCacheCluster redisCache = CfnCacheCluster.Builder.create(this, "ProductValkeyCache")
                .clusterName("product-catalog-cache")
                .engine("redis")
                .cacheNodeType("cache.t3.micro")
                .numCacheNodes(1)
                .vpcSecurityGroupIds(List.of(cacheSecurityGroup.getSecurityGroupId()))
                .cacheSubnetGroupName(cacheSubnetGroup.getRef())
                .build();

        final LambdaNetworkConfig networkConfig = new LambdaNetworkConfig(vpc, cacheSecurityGroup);

        // 4. Mensageria & Eventos
        final EventBus storeEventBus = EventBus.Builder.create(this, "StoreEventBus")
                .eventBusName("online-store-events")
                .build();

        final Queue orderDlq = Queue.Builder.create(this, "OrderProcessingDlq")
                .queueName("order-processing-dlq")
                .retentionPeriod(Duration.days(14))
                .visibilityTimeout(Duration.seconds(60))
                .build();

        final Queue orderQueue = Queue.Builder.create(this, "OrderProcessingQueue")
                .queueName("order-processing-queue")
                .visibilityTimeout(Duration.seconds(300))
                .retentionPeriod(Duration.days(14))
                .receiveMessageWaitTime(Duration.seconds(20))
                .deadLetterQueue(DeadLetterQueue.builder().queue(orderDlq).maxReceiveCount(3).build())
                .build();

        final Topic customerNotificationTopic = Topic.Builder.create(this, "CustomerNotificationTopic")
                .topicName("customer-notifications-topic")
                .displayName("Notificações de Clientes do E-commerce")
                .build();

        final Rule orderProcessingRule = Rule.Builder.create(this, "OrderProcessingRule")
                .ruleName("order-processing-rule")
                .eventBus(storeEventBus)
                .description("Roteia eventos de pedidos criados para a fila SQS de processamento")
                .eventPattern(EventPattern.builder().source(List.of("store.orders")).detailType(List.of("Order Placed")).build())
                .build();

        orderProcessingRule.addTarget(new SqsQueue(orderQueue));

        // 5. Firehose & Layer
        final ILayerVersion dependencyLayer = LayerVersion.Builder.create(this, "AppDependencyLayer")
                .layerVersionName("ProductApiDeps")
                .removalPolicy(RemovalPolicy.RETAIN)
                .code(Code.fromAsset("lambda_layer"))
                .compatibleRuntimes(List.of(Runtime.PYTHON_3_12))
                .description("Camada contendo Pydantic v2 e utilitários compartilhados.")
                .build();

        final Map<String, String> commonEnvVars = Map.of(
                BUCKET_NAME_ENV, assetsBucket.getBucketName(),
                REDIS_HOST_ENV, redisCache.getAttrRedisEndpointAddress(),
                REDIS_PORT_ENV, redisCache.getAttrRedisEndpointPort(),
                SSM_CONFIG_PREFIX_ENV, ssmPrefixPath,
                "EVENT_BUS_NAME", storeEventBus.getEventBusName(),
                "CUSTOMER_NOTIFICATION_TOPIC", customerNotificationTopic.getTopicArn(),
                "FIREHOSE_STREAM_NAME", FIREHOSE_STREAM_NAME
        );

        // 5.1. Stream Transformer Lambda (Timeout de 30s)
        final Function streamTransformerFn = createPythonLambda(
                "StreamTransformer",
                "handlers.stream_transformer.handler",
                productsTable,
                dependencyLayer,
                LambdaConfig.of(false, null, commonEnvVars, Duration.seconds(30))
        );

        // 5.2. Log Group no CloudWatch para Erros Nativa do Firehose
        final LogGroup firehoseLogGroup = LogGroup.Builder.create(this, "FirehoseLogGroup")
                .logGroupName("/aws/kinesisfirehose/" + FIREHOSE_STREAM_NAME)
                .retention(RetentionDays.ONE_MONTH)
                .removalPolicy(RemovalPolicy.DESTROY)
                .build();

        final LogStream firehoseLogStream = LogStream.Builder.create(this, "FirehoseLogStream")
                .logGroup(firehoseLogGroup)
                .logStreamName("S3Delivery")
                .removalPolicy(RemovalPolicy.DESTROY)
                .build();

        final Role firehoseRole = Role.Builder.create(this, "FirehoseDeliveryRole")
                .assumedBy(new ServicePrincipal("firehose.amazonaws.com"))
                .build();

        analyticsBucket.grantReadWrite(firehoseRole);
        streamTransformerFn.grantInvoke(firehoseRole);
        firehoseLogGroup.grantWrite(firehoseRole);

        final CfnDeliveryStream customerActivityStream = CfnDeliveryStream.Builder.create(this, "CustomerActivityStream")
                .deliveryStreamName(FIREHOSE_STREAM_NAME)
                .deliveryStreamType("DirectPut")
                .extendedS3DestinationConfiguration(CfnDeliveryStream.ExtendedS3DestinationConfigurationProperty.builder()
                        .bucketArn(analyticsBucket.getBucketArn())
                        .roleArn(firehoseRole.getRoleArn())
                        .prefix("analytics/customer-activity/year=!{timestamp:yyyy}/month=!{timestamp:MM}/")
                        .errorOutputPrefix("errors/firehose/")
                        .bufferingHints(CfnDeliveryStream.BufferingHintsProperty.builder().sizeInMBs(1).intervalInSeconds(60).build())
                        .compressionFormat("GZIP")
                        .cloudWatchLoggingOptions(CfnDeliveryStream.CloudWatchLoggingOptionsProperty.builder()
                                .enabled(true)
                                .logGroupName(firehoseLogGroup.getLogGroupName())
                                .logStreamName(firehoseLogStream.getLogStreamName())
                                .build())
                        .processingConfiguration(CfnDeliveryStream.ProcessingConfigurationProperty.builder()
                                .enabled(true)
                                .processors(List.of(
                                        CfnDeliveryStream.ProcessorProperty.builder()
                                                .type("Lambda")
                                                .parameters(List.of(
                                                        CfnDeliveryStream.ProcessorParameterProperty.builder()
                                                                .parameterName("LambdaArn")
                                                                .parameterValue(streamTransformerFn.getFunctionArn())
                                                                .build()
                                                ))
                                                .build()
                                ))
                                .build())
                        .build())
                .build();

        // 6. Instanciação das Lambdas Principais com LambdaConfig
        final Function queryProducts = createPythonLambda("QueryProducts", "handlers.query_products.handler", productsTable, dependencyLayer, LambdaConfig.of(false, networkConfig, commonEnvVars));
        queryProducts.addEnvironment("CATEGORY_GSI_NAME", CATEGORY_GSI_NAME);

        final Function getProduct = createPythonLambda("GetProduct", "handlers.get_product.handler", productsTable, dependencyLayer, LambdaConfig.of(false, networkConfig, commonEnvVars));
        final Function insertProduct = createPythonLambda("InsertProduct", "handlers.insert_product.handler", productsTable, dependencyLayer, LambdaConfig.of(true, networkConfig, commonEnvVars));
        final Function updateProduct = createPythonLambda("UpdateProduct", "handlers.update_product.handler", productsTable, dependencyLayer, LambdaConfig.of(true, networkConfig, commonEnvVars));

        final Function generateUploadUrl = createPythonLambda("GenerateUploadUrl", "handlers.generate_upload_url.handler", productsTable, dependencyLayer, LambdaConfig.of(false, null, commonEnvVars));
        assetsBucket.grantReadWrite(generateUploadUrl);

        final Function processImageMetadata = createPythonLambda("ProcessImageMetadata", "handlers.process_image_metadata.handler", productsTable, dependencyLayer, LambdaConfig.of(true, null, commonEnvVars, Duration.seconds(30)));
        assetsBucket.grantRead(processImageMetadata);

        processImageMetadata.addEventSource(S3EventSource.Builder.create(assetsBucket)
                .events(List.of(EventType.OBJECT_CREATED))
                .filters(List.of(NotificationKeyFilter.builder().prefix("products/").build()))
                .build());

        final Function orderProcessorWorker = createPythonLambda("OrderProcessorWorker", "handlers.order_processor.handler", productsTable, dependencyLayer, LambdaConfig.of(true, networkConfig, commonEnvVars, Duration.seconds(300)));
        orderProcessorWorker.addEventSource(SqsEventSource.Builder.create(orderQueue).batchSize(10).maxBatchingWindow(Duration.seconds(5)).build());

        // 7. Permissões IAM
        storeEventBus.grantPutEventsTo(insertProduct);
        storeEventBus.grantPutEventsTo(updateProduct);
        customerNotificationTopic.grantPublish(orderProcessorWorker);

        final PolicyStatement firehosePutPolicy = PolicyStatement.Builder.create()
                .actions(List.of("firehose:PutRecord", "firehose:PutRecordBatch"))
                .resources(List.of(customerActivityStream.getAttrArn()))
                .build();

        insertProduct.addToRolePolicy(firehosePutPolicy);
        updateProduct.addToRolePolicy(firehosePutPolicy);
        getProduct.addToRolePolicy(firehosePutPolicy);
        orderProcessorWorker.addToRolePolicy(firehosePutPolicy);

        // 8. SSM Parameter Store
        final StringParameter apiTimeoutParam = StringParameter.Builder.create(this, "ApiTimeoutParam").parameterName(ssmPrefixPath + "/api_timeout").stringValue("5").build();
        final StringParameter circuitThresholdParam = StringParameter.Builder.create(this, "CircuitThresholdParam").parameterName(ssmPrefixPath + "/circuit_breaker_threshold").stringValue("5").build();
        final StringParameter featureFlagImageParam = StringParameter.Builder.create(this, "FeatureFlagImageParam").parameterName(ssmPrefixPath + "/feature_flag_image_processing").stringValue("true").build();
        final StringParameter s3UploadExpirationParam = StringParameter.Builder.create(this, "S3UploadExpirationParam").parameterName(ssmPrefixPath + "/s3_presigned_url_expiration").stringValue("3600").build();
        final StringParameter featureFlagOrderParam = StringParameter.Builder.create(this, "FeatureFlagOrderParam").parameterName(ssmPrefixPath + "/feature_flag_order_processing").stringValue("true").build();
        final StringParameter cacheTtlProductParam = StringParameter.Builder.create(this, "CacheTtlProductParam").parameterName(ssmPrefixPath + "/cache_ttl_product").stringValue("3600").build();
        final StringParameter cacheTtlCategoryParam = StringParameter.Builder.create(this, "CacheTtlCategoryParam").parameterName(ssmPrefixPath + "/cache_ttl_category").stringValue("1800").build();

        final List<Function> allFunctions = List.of(queryProducts, getProduct, insertProduct, updateProduct, generateUploadUrl, processImageMetadata, orderProcessorWorker, streamTransformerFn);

        for (Function fn : allFunctions) {
            apiTimeoutParam.grantRead(fn);
            circuitThresholdParam.grantRead(fn);
            featureFlagImageParam.grantRead(fn);
            s3UploadExpirationParam.grantRead(fn);
            featureFlagOrderParam.grantRead(fn);
            cacheTtlProductParam.grantRead(fn);
            cacheTtlCategoryParam.grantRead(fn);
        }

        // 9. API Gateway
        final CorsOptions globalCorsOptions = CorsOptions.builder()
                .allowOrigins(List.of("*"))
                .allowMethods(List.of("GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"))
                .allowHeaders(List.of("Content-Type", "X-Amz-Date", "Authorization", "X-Api-Key"))
                .build();

        final RestApi api = RestApi.Builder.create(this, "ProductsAPI")
                .restApiName("Products Service")
                .description("API Serverless para gerenciamento do catálogo de produtos.")
                .defaultCorsPreflightOptions(globalCorsOptions)
                .build();

        final IResource productsResource = api.getRoot().addResource("products");
        productsResource.addMethod("GET", new LambdaIntegration(queryProducts));
        productsResource.addMethod("POST", new LambdaIntegration(insertProduct));

        final IResource productByIdResource = productsResource.addResource("{id}");
        productByIdResource.addMethod("GET", new LambdaIntegration(getProduct));
        productByIdResource.addMethod("PATCH", new LambdaIntegration(updateProduct));

        final IResource uploadUrlResource = productByIdResource.addResource("upload-url");
        uploadUrlResource.addMethod("POST", new LambdaIntegration(generateUploadUrl));
    }

    // =========================================================================
    // Método Auxiliar createPythonLambda (Máximo de 5 parâmetros - SonarQube OK)
    // =========================================================================
    private Function createPythonLambda(
            final String id,
            final String handler,
            final Table table,
            final ILayerVersion layer,
            final LambdaConfig config
    ) {
        final Function.Builder builder = Function.Builder.create(this, id)
                .runtime(Runtime.PYTHON_3_12)
                .handler(handler)
                .code(Code.fromAsset("lambda_code"))
                .layers(List.of(layer))
                .timeout(config != null && config.timeout() != null ? config.timeout() : Duration.seconds(5));

        if (config != null && config.networkConfig() != null && config.networkConfig().vpc() != null && config.networkConfig().securityGroup() != null) {
            builder.vpc(config.networkConfig().vpc())
                    .vpcSubnets(SubnetSelection.builder().subnetType(SubnetType.PRIVATE_WITH_EGRESS).build())
                    .securityGroups(List.of(config.networkConfig().securityGroup()));
        }

        final Function function = builder.build();

        function.addEnvironment(TABLE_NAME_ENV, table.getTableName());
        function.addEnvironment("PYTHONPATH", "/var/task:/var/task/vendor");

        if (config != null && config.extraEnvVars() != null) {
            config.extraEnvVars().forEach(function::addEnvironment);
        }

        if (config != null && config.isWritable()) {
            table.grantReadWriteData(function);
        } else {
            table.grantReadData(function);
        }

        return function;
    }
}