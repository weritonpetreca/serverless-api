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
import software.amazon.awscdk.services.lambda.*;
import software.amazon.awscdk.services.lambda.Runtime;
import software.amazon.awscdk.services.lambda.eventsources.S3EventSource;
import software.amazon.awscdk.services.s3.*;
import software.amazon.awscdk.services.ssm.StringParameter;
import software.constructs.Construct;

import java.util.List;
import java.util.Map;

public class ProductApiStack extends Stack {

    // Constantes originais preservadas
    private static final String TABLE_NAME_ENV = "PRODUCTS_TABLE_NAME";
    private static final String CATEGORY_GSI_NAME = "category-index";

    // Constantes para S3 e ElastiCache Redis
    private static final String BUCKET_NAME_ENV = "PRODUCT_IMAGE_BUCKET";
    private static final String REDIS_HOST_ENV = "REDIS_HOST";
    private static final String REDIS_PORT_ENV = "REDIS_PORT";

    // Constante para a variável de ambiente do prefixo SSM
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
        // 4. Layer de Dependências Original Preservada
        // =========================================================================
        final ILayerVersion dependencyLayer = LayerVersion.Builder.create(this, "AppDependencyLayer")
                .layerVersionName("ProductApiDeps")
                .removalPolicy(RemovalPolicy.RETAIN)
                .code(Code.fromAsset("lambda_layer"))
                .compatibleRuntimes(List.of(Runtime.PYTHON_3_12))
                .description("Camada contendo Pydantic v2 e utilitários compartilhados.")
                .build();

        // Mapa de variáveis de ambiente para S3, Cache Redis e SSM
        final Map<String, String> cacheAndS3Env = Map.of(
                BUCKET_NAME_ENV, assetsBucket.getBucketName(),
                REDIS_HOST_ENV, redisCache.getAttrRedisEndpointAddress(),
                REDIS_PORT_ENV, redisCache.getAttrRedisEndpointPort(),
                SSM_CONFIG_PREFIX_ENV, ssmPrefixPath
        );

        // =========================================================================
        // 5. Instanciação das Lambdas Principais usando createPythonLambda
        // =========================================================================
        final Function queryProducts = createPythonLambda(
                "QueryProducts",
                "handlers.query_products.handler",
                productsTable,
                dependencyLayer,
                false,
                networkConfig,
                cacheAndS3Env
        );
        queryProducts.addEnvironment("CATEGORY_GSI_NAME", CATEGORY_GSI_NAME);

        final Function getProduct = createPythonLambda(
                "GetProduct",
                "handlers.get_product.handler",
                productsTable,
                dependencyLayer,
                false,
                networkConfig,
                cacheAndS3Env
        );

        final Function insertProduct = createPythonLambda(
                "InsertProduct",
                "handlers.insert_product.handler",
                productsTable,
                dependencyLayer,
                true,
                networkConfig,
                cacheAndS3Env
        );

        final Function updateProduct = createPythonLambda(
                "UpdateProduct",
                "handlers.update_product.handler",
                productsTable,
                dependencyLayer,
                true,
                networkConfig,
                cacheAndS3Env
        );

        // =========================================================================
        // 6. Novas Lambdas para o S3 (Upload Pré-assinado e Processamento Reativo)
        // =========================================================================
        final Function generateUploadUrl = createPythonLambda(
                "GenerateUploadUrl",
                "handlers.generate_upload_url.handler",
                productsTable,
                dependencyLayer,
                false,
                null,
                cacheAndS3Env
        );
        assetsBucket.grantReadWrite(generateUploadUrl);

        final Function processImageMetadata = createPythonLambda(
                "ProcessImageMetadata",
                "handlers.process_image_metadata.handler",
                productsTable,
                dependencyLayer,
                true,
                null,
                cacheAndS3Env
        );
        assetsBucket.grantRead(processImageMetadata);

        processImageMetadata.addEventSource(S3EventSource.Builder.create(assetsBucket)
                .events(List.of(EventType.OBJECT_CREATED))
                .filters(List.of(NotificationKeyFilter.builder().prefix("products/").build()))
                .build());

        // =========================================================================
        // 7. AWS SYSTEMS MANAGER (SSM) PARAMETER STORE - PARÂMETROS DE CONFIGURAÇÃO
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

        final List<Function> allFunctions = List.of(
                queryProducts, getProduct, insertProduct, updateProduct,
                generateUploadUrl, processImageMetadata
        );

        for (Function fn : allFunctions) {
            apiTimeoutParam.grantRead(fn);
            circuitThresholdParam.grantRead(fn);
            featureFlagImageParam.grantRead(fn);
        }

        // =========================================================================
        // 8. API Gateway RestApi Original Preservada
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
    // Metodo Auxiliar createPythonLambda (Máximo de 7 parâmetros - SonarQube S107 OK)
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