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
import software.amazon.awscdk.services.lambda.*;
import software.amazon.awscdk.services.lambda.Runtime;
import software.amazon.awscdk.services.lambda.eventsources.S3EventSource;
import software.amazon.awscdk.services.lambda.eventsources.SqsEventSource;
import software.amazon.awscdk.services.s3.*;
import software.amazon.awscdk.services.sns.Topic;
import software.amazon.awscdk.services.sqs.DeadLetterQueue;
import software.amazon.awscdk.services.sqs.Queue;
import software.amazon.awscdk.services.ssm.StringParameter;
import software.constructs.Construct;

import java.util.List;
import java.util.Map;

public class ProductApiStack extends Stack {

    // Constantes originais preservadas
    private static final String TABLE_NAME_ENV = "PRODUCTS_TABLE_NAME";
    private static final String CATEGORY_GSI_NAME = "category-index";

    // Constantes para S3, ElastiCache Redis e SSM
    private static final String BUCKET_NAME_ENV = "PRODUCT_IMAGE_BUCKET";
    private static final String REDIS_HOST_ENV = "REDIS_HOST";
    private static final String REDIS_PORT_ENV = "REDIS_PORT";
    private static final String SSM_CONFIG_PREFIX_ENV = "SSM_CONFIG_PREFIX";

    // Record Java 21 para encapsular a rede da Lambda (SonarQube S107 Fix - Max 7 Params)
    public record LambdaNetworkConfig(Vpc vpc, SecurityGroup securityGroup) {}

    public ProductApiStack(final Construct scope, final String constructId, final StackProps props) {
        super(scope, constructId, props);

        Tags.of(this).add("Project", "ServerlessApi");
        Tags.of(this).add("Environment", "Development");
        Tags.of(this).add("ManagedBy", "AWS-CDK");

        // Resolução dinâmica do caminho SSM via CDK Context
        final Object envObj = this.getNode().tryGetContext("environment");
        final String envScope = (envObj instanceof String envStr && !envStr.isBlank()) ? envStr : "dev";
        final String ssmPrefixPath = "/store/" + envScope + "/config";

        // =========================================================================
        // 1. Tabela DynamoDB Original (Chave "id" e GSI "category-index" com ALL)
        // =========================================================================
        final Table productsTable = Table.Builder.create(this, "ProductsTable")
                .tableName("Products")
                .partitionKey(Attribute.builder()
                        .name("id")
                        .type(AttributeType.STRING)
                        .build())
                .billingMode(BillingMode.PAY_PER_REQUEST)
                .removalPolicy(RemovalPolicy.DESTROY)
                .build();

        productsTable.addGlobalSecondaryIndex(GlobalSecondaryIndexProps.builder()
                .indexName(CATEGORY_GSI_NAME)
                .partitionKey(Attribute.builder()
                        .name("category")
                        .type(AttributeType.STRING)
                        .build())
                .projectionType(ProjectionType.ALL)
                .build());

        // =========================================================================
        // 2. Bucket S3 de Mídias (Criptografia SSE-S3, Block Public e Lifecycle)
        // =========================================================================
        final Bucket assetsBucket = Bucket.Builder.create(this, "ProductAssetsBucket")
                .versioned(true)
                .encryption(BucketEncryption.S3_MANAGED)
                .blockPublicAccess(BlockPublicAccess.BLOCK_ALL)
                .removalPolicy(RemovalPolicy.DESTROY)
                .autoDeleteObjects(true)
                .build();

        // FinOps: Regras de ciclo de vida do S3
        assetsBucket.addLifecycleRule(LifecycleRule.builder()
                .id("ProductImageLifecycle")
                .enabled(true)
                .prefix("products/")
                .transitions(List.of(
                        Transition.builder()
                                .transitionAfter(Duration.days(30))
                                .storageClass(StorageClass.INFREQUENT_ACCESS)
                                .build(),
                        Transition.builder()
                                .transitionAfter(Duration.days(90))
                                .storageClass(StorageClass.GLACIER)
                                .build()
                ))
                .expiration(Duration.days(2555)) // Retenção de 7 anos
                .build());

        // =========================================================================
        // 3. Camada de Rede (VPC) e ElastiCache Redis
        // =========================================================================
        final Vpc vpc = Vpc.Builder.create(this, "ProductApiVpc")
                .maxAzs(2)
                .build();

        final SecurityGroup cacheSecurityGroup = SecurityGroup.Builder.create(this, "CacheSecurityGroup")
                .vpc(vpc)
                .description("Permite acesso ao ElastiCache Redis na porta 6379 a partir da VPC")
                .allowAllOutbound(true)
                .build();

        cacheSecurityGroup.addIngressRule(Peer.ipv4(vpc.getVpcCidrBlock()), Port.tcp(6379), "Acesso ao Redis Cache");

        final List<String> isolatedSubnetIds = vpc.getIsolatedSubnets().stream()
                .map(ISubnet::getSubnetId)
                .toList();
        final List<String> privateSubnetIds = vpc.getPrivateSubnets().stream()
                .map(ISubnet::getSubnetId)
                .toList();
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

        // Objeto de configuração de rede para encapsulamento
        final LambdaNetworkConfig networkConfig = new LambdaNetworkConfig(vpc, cacheSecurityGroup);

        // =========================================================================
        // 4. MENSAGERIA & EVENTOS (EVENTBRIDGE, SQS, DLQ & SNS)
        // =========================================================================

        // 4.1. Amazon EventBridge - Barramento Customizado de Eventos
        final EventBus storeEventBus = EventBus.Builder.create(this, "StoreEventBus")
                .eventBusName("online-store-events")
                .build();

        // 4.2. Amazon SQS - Fila de Mensagens Mortas (Dead Letter Queue - DLQ)
        final Queue orderDlq = Queue.Builder.create(this, "OrderProcessingDlq")
                .queueName("order-processing-dlq")
                .retentionPeriod(Duration.days(14))
                .visibilityTimeout(Duration.seconds(60))
                .build();

        // 4.3. Amazon SQS - Fila Principal de Processamento de Pedidos (Com Long Polling e DLQ)
        final Queue orderQueue = Queue.Builder.create(this, "OrderProcessingQueue")
                .queueName("order-processing-queue")
                .visibilityTimeout(Duration.seconds(300)) // 5 minutos para workers
                .retentionPeriod(Duration.days(14))
                .receiveMessageWaitTime(Duration.seconds(20)) // FinOps: Long Polling Ativado
                .deadLetterQueue(DeadLetterQueue.builder()
                        .queue(orderDlq)
                        .maxReceiveCount(3) // Redrive para DLQ após 3 falhas
                        .build())
                .build();

        // 4.4. Amazon SNS - Tópico de Notificações Multicanal
        final Topic customerNotificationTopic = Topic.Builder.create(this, "CustomerNotificationTopic")
                .topicName("customer-notifications-topic")
                .displayName("Notificações de Clientes do E-commerce")
                .build();

        // 4.5. Amazon EventBridge Rule - Roteamento para a Fila SQS
        final Rule orderProcessingRule = Rule.Builder.create(this, "OrderProcessingRule")
                .ruleName("order-processing-rule")
                .eventBus(storeEventBus)
                .description("Roteia eventos de pedidos criados para a fila SQS de processamento")
                .eventPattern(EventPattern.builder()
                        .source(List.of("store.orders"))
                        .detailType(List.of("Order Placed"))
                        .build())
                .build();

        // Associa a Fila SQS como Alvo (Target) da Regra do EventBridge via SqsQueue
        orderProcessingRule.addTarget(new SqsQueue(orderQueue));

        // =========================================================================
        // 5. Layer de Dependências e Variáveis de Ambiente
        // =========================================================================
        final ILayerVersion dependencyLayer = LayerVersion.Builder.create(this, "AppDependencyLayer")
                .layerVersionName("ProductApiDeps")
                .removalPolicy(RemovalPolicy.RETAIN)
                .code(Code.fromAsset("lambda_layer"))
                .compatibleRuntimes(List.of(Runtime.PYTHON_3_12))
                .description("Camada contendo Pydantic v2 e utilitários compartilhados.")
                .build();

        // Mapa estendido de variáveis de ambiente
        final Map<String, String> commonEnvVars = Map.of(
                BUCKET_NAME_ENV, assetsBucket.getBucketName(),
                REDIS_HOST_ENV, redisCache.getAttrRedisEndpointAddress(),
                REDIS_PORT_ENV, redisCache.getAttrRedisEndpointPort(),
                SSM_CONFIG_PREFIX_ENV, ssmPrefixPath,
                "EVENT_BUS_NAME", storeEventBus.getEventBusName(),
                "CUSTOMER_NOTIFICATION_TOPIC", customerNotificationTopic.getTopicArn()
        );

        // =========================================================================
        // 6. Instanciação das Lambdas Principais
        // =========================================================================
        final Function queryProducts = createPythonLambda(
                "QueryProducts",
                "handlers.query_products.handler",
                productsTable,
                dependencyLayer,
                false,
                networkConfig,
                commonEnvVars
        );
        queryProducts.addEnvironment("CATEGORY_GSI_NAME", CATEGORY_GSI_NAME);

        final Function getProduct = createPythonLambda(
                "GetProduct",
                "handlers.get_product.handler",
                productsTable,
                dependencyLayer,
                false,
                networkConfig,
                commonEnvVars
        );

        final Function insertProduct = createPythonLambda(
                "InsertProduct",
                "handlers.insert_product.handler",
                productsTable,
                dependencyLayer,
                true,
                networkConfig,
                commonEnvVars
        );

        final Function updateProduct = createPythonLambda(
                "UpdateProduct",
                "handlers.update_product.handler",
                productsTable,
                dependencyLayer,
                true,
                networkConfig,
                commonEnvVars
        );

        // Lambdas para S3
        final Function generateUploadUrl = createPythonLambda(
                "GenerateUploadUrl",
                "handlers.generate_upload_url.handler",
                productsTable,
                dependencyLayer,
                false,
                null,
                commonEnvVars
        );
        assetsBucket.grantReadWrite(generateUploadUrl);

        final Function processImageMetadata = createPythonLambda(
                "ProcessImageMetadata",
                "handlers.process_image_metadata.handler",
                productsTable,
                dependencyLayer,
                true,
                null,
                commonEnvVars
        );
        assetsBucket.grantRead(processImageMetadata);

        processImageMetadata.addEventSource(S3EventSource.Builder.create(assetsBucket)
                .events(List.of(EventType.OBJECT_CREATED))
                .filters(List.of(NotificationKeyFilter.builder().prefix("products/").build()))
                .build());

        // =========================================================================
        // 7. NOVA LAMBDA WORKER: Processamento de Pedidos acionada por SQS
        // =========================================================================
        final Function orderProcessorWorker = createPythonLambda(
                "OrderProcessorWorker",
                "handlers.order_processor.handler",
                productsTable,
                dependencyLayer,
                true,
                networkConfig,
                commonEnvVars
        );

        // Associa o Gatilho de Origem de Eventos do SQS à Lambda Worker
        orderProcessorWorker.addEventSource(SqsEventSource.Builder.create(orderQueue)
                .batchSize(10)
                .maxBatchingWindow(Duration.seconds(5))
                .build());

        // =========================================================================
        // 8. PERMISSÕES IAM MENOR PRIVILÉGIO (EVENTBRIDGE, SNS E SSM)
        // =========================================================================
        storeEventBus.grantPutEventsTo(insertProduct);
        storeEventBus.grantPutEventsTo(updateProduct);
        customerNotificationTopic.grantPublish(orderProcessorWorker);

        // =========================================================================
        // 9. AWS SYSTEMS MANAGER (SSM) PARAMETER STORE - PARÂMETROS DE CONFIGURAÇÃO
        // =========================================================================
        final StringParameter apiTimeoutParam = StringParameter.Builder.create(this, "ApiTimeoutParam")
                .parameterName(ssmPrefixPath + "/api_timeout")
                .stringValue("5")
                .description("Timeout padrão em segundos para integrações de serviços externos")
                .build();

        final StringParameter circuitThresholdParam = StringParameter.Builder.create(this, "CircuitThresholdParam")
                .parameterName(ssmPrefixPath + "/circuit_breaker_threshold")
                .stringValue("5")
                .description("Limiar de falhas consecutivas para abertura do Circuit Breaker")
                .build();

        final StringParameter featureFlagImageParam = StringParameter.Builder.create(this, "FeatureFlagImageParam")
                .parameterName(ssmPrefixPath + "/feature_flag_image_processing")
                .stringValue("true")
                .description("Feature Flag para ativacao do processamento de imagem")
                .build();

        final StringParameter s3UploadExpirationParam = StringParameter.Builder.create(this, "S3UploadExpirationParam")
                .parameterName(ssmPrefixPath + "/s3_presigned_url_expiration")
                .stringValue("3600")
                .description("Tempo de expiração em segundos para URLs pré-assinadas de upload no S3")
                .build();

        final StringParameter featureFlagOrderParam = StringParameter.Builder.create(this, "FeatureFlagOrderParam")
                .parameterName(ssmPrefixPath + "/feature_flag_order_processing")
                .stringValue("true")
                .description("Feature Flag para controle do processamento assíncrono de pedidos")
                .build();

        final StringParameter cacheTtlProductParam = StringParameter.Builder.create(this, "CacheTtlProductParam")
                .parameterName(ssmPrefixPath + "/cache_ttl_product")
                .stringValue("3600")
                .description("TTL de cache para detalhes de produto no ElastiCache")
                .build();

        final StringParameter cacheTtlCategoryParam = StringParameter.Builder.create(this, "CacheTtlCategoryParam")
                .parameterName(ssmPrefixPath + "/cache_ttl_category")
                .stringValue("1800")
                .description("TTL de cache para listas de categoria no ElastiCache")
                .build();

        final List<Function> allFunctions = List.of(
                queryProducts, getProduct, insertProduct, updateProduct,
                generateUploadUrl, processImageMetadata, orderProcessorWorker
        );

        for (Function fn : allFunctions) {
            apiTimeoutParam.grantRead(fn);
            circuitThresholdParam.grantRead(fn);
            featureFlagImageParam.grantRead(fn);
            s3UploadExpirationParam.grantRead(fn);
            featureFlagOrderParam.grantRead(fn);
            cacheTtlProductParam.grantRead(fn);
            cacheTtlCategoryParam.grantRead(fn);
        }

        // =========================================================================
        // 10. API Gateway RestApi Original Preservada
        // =========================================================================
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
    // Método Auxiliar createPythonLambda (Máximo de 7 parâmetros - SonarQube S107 OK)
    // =========================================================================
    private Function createPythonLambda(
            final String id,
            final String handler,
            final Table table,
            final ILayerVersion layer,
            final boolean isWritable,
            final LambdaNetworkConfig networkConfig,
            final Map<String, String> extraEnvVars
    ) {
        final Function.Builder builder = Function.Builder.create(this, id)
                .runtime(Runtime.PYTHON_3_12)
                .handler(handler)
                .code(Code.fromAsset("lambda_code"))
                .layers(List.of(layer));

        if (networkConfig != null && networkConfig.vpc() != null && networkConfig.securityGroup() != null) {
            builder.vpc(networkConfig.vpc())
                    .vpcSubnets(SubnetSelection.builder().subnetType(SubnetType.PRIVATE_WITH_EGRESS).build())
                    .securityGroups(List.of(networkConfig.securityGroup()));
        }

        final Function function = builder.build();

        function.addEnvironment(TABLE_NAME_ENV, table.getTableName());
        function.addEnvironment("PYTHONPATH", "/var/task:/var/task/vendor");

        if (extraEnvVars != null) {
            extraEnvVars.forEach(function::addEnvironment);
        }

        if (isWritable) {
            table.grantReadWriteData(function);
        } else {
            table.grantReadData(function);
        }

        return function;
    }
}