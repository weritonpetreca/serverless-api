package com.petreca;

import software.amazon.awscdk.Duration;
import software.amazon.awscdk.RemovalPolicy;
import software.amazon.awscdk.Stack;
import software.amazon.awscdk.StackProps;
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
import software.constructs.Construct;

import java.util.List;
import java.util.Map;

public class ProductApiStack extends Stack {

    // Constantes originais preservadas
    private static final String TABLE_NAME_ENV = "PRODUCTS_TABLE_NAME";
    private static final String CATEGORY_GSI_NAME = "category-index";

    // Novas constantes para S3 e ElastiCache Valkey
    private static final String BUCKET_NAME_ENV = "PRODUCT_IMAGE_BUCKET";
    private static final String VALKEY_HOST_ENV = "VALKEY_HOST";
    private static final String VALKEY_PORT_ENV = "VALKEY_PORT";

    public ProductApiStack(final Construct scope, final String constructId, final StackProps props) {
        super(scope, constructId, props);

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
                .blockPublicAccess(BlockPublicAccess.BLOCK_ALL) // Cibersegurança Hardening
                .removalPolicy(RemovalPolicy.DESTROY)
                .autoDeleteObjects(true)
                .build();

        // FinOps: Regras de ciclo de vida para otimização de custos de armazenamento
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
        // 3. Camada de Rede (VPC) e ElastiCache Valkey
        // =========================================================================
        final Vpc vpc = Vpc.Builder.create(this, "ProductApiVpc")
                .maxAzs(2)
                .build();

        final SecurityGroup cacheSecurityGroup = SecurityGroup.Builder.create(this, "CacheSecurityGroup")
                .vpc(vpc)
                .description("Permite acesso ao ElastiCache Valkey na porta 6379 a partir da VPC")
                .allowAllOutbound(true)
                .build();

        cacheSecurityGroup.addIngressRule(Peer.ipv4(vpc.getVpcCidrBlock()), Port.tcp(6379), "Acesso ao Valkey Redis");

        final List<String> isolatedSubnetIds = vpc.getIsolatedSubnets().stream()
                .map(ISubnet::getSubnetId)
                .toList();
        final List<String> privateSubnetIds = vpc.getPrivateSubnets().stream()
                .map(ISubnet::getSubnetId)
                .toList();
        final List<String> cacheSubnetIds = isolatedSubnetIds.isEmpty() ? privateSubnetIds : isolatedSubnetIds;

        final CfnSubnetGroup cacheSubnetGroup = CfnSubnetGroup.Builder.create(this, "CacheSubnetGroup")
                .description("Subnets privadas para o ElastiCache Valkey")
                .subnetIds(cacheSubnetIds)
                .build();

        final CfnCacheCluster valkeyCache = CfnCacheCluster.Builder.create(this, "ProductValkeyCache")
                .clusterName("product-catalog-cache")
                .engine("valkey")
                .cacheNodeType("cache.t3.micro") // Nó otimizado para testes e baixo custo
                .numCacheNodes(1)
                .vpcSecurityGroupIds(List.of(cacheSecurityGroup.getSecurityGroupId()))
                .cacheSubnetGroupName(cacheSubnetGroup.getRef())
                .build();

        // =========================================================================
        // 4. Layer de Dependências Original Preservada
        // =========================================================================
        final ILayerVersion dependencyLayer = LayerVersion.Builder.create(this, "AppDependencyLayer")
                .layerVersionName("ProductApiDeps")
                .removalPolicy(RemovalPolicy.RETAIN)
                .code(Code.fromAsset("lambda_layer"))
                .compatibleRuntimes(List.of(Runtime.PYTHON_3_12))
                .description("Camada contendo Pydantic v2 e utilitário compartilhados.")
                .build();

        // Mapa de variáveis de ambiente adicionais para S3 e Cache Valkey
        final Map<String, String> cacheAndS3Env = Map.of(
                BUCKET_NAME_ENV, assetsBucket.getBucketName(),
                VALKEY_HOST_ENV, valkeyCache.getAttrRedisEndpointAddress(),
                VALKEY_PORT_ENV, valkeyCache.getAttrRedisEndpointPort()
        );

        // =========================================================================
        // 5. Instanciação das Lambdas Principais usando o seu padrão createPythonLambda
        // =========================================================================
        final Function queryProducts = createPythonLambda(
                "QueryProducts",
                "handlers.query_products.handler",
                productsTable,
                dependencyLayer,
                false,
                vpc,
                cacheSecurityGroup,
                cacheAndS3Env
        );
        queryProducts.addEnvironment("CATEGORY_GSI_NAME", CATEGORY_GSI_NAME);

        final Function getProduct = createPythonLambda(
                "GetProduct",
                "handlers.get_product.handler",
                productsTable,
                dependencyLayer,
                false,
                vpc,
                cacheSecurityGroup,
                cacheAndS3Env
        );

        final Function insertProduct = createPythonLambda(
                "InsertProduct",
                "handlers.insert_product.handler",
                productsTable,
                dependencyLayer,
                true,
                vpc,
                cacheSecurityGroup,
                cacheAndS3Env
        );

        final Function updateProduct = createPythonLambda(
                "UpdateProduct",
                "handlers.update_product.handler",
                productsTable,
                dependencyLayer,
                true,
                vpc,
                cacheSecurityGroup,
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
                null, // Não exige VPC pois apenas assina a URL do S3
                null,
                cacheAndS3Env
        );
        assetsBucket.grantReadWrite(generateUploadUrl);

        final Function processImageMetadata = createPythonLambda(
                "ProcessImageMetadata",
                "handlers.process_image_metadata.handler",
                productsTable,
                dependencyLayer,
                true, // Writable para atualizar o DynamoDB com os metadados da imagem
                null,
                null,
                cacheAndS3Env
        );
        assetsBucket.grantRead(processImageMetadata);

        // Gatilho do S3 para invocar a Lambda reativa no evento de upload
        processImageMetadata.addEventSource(S3EventSource.Builder.create(assetsBucket)
                .events(List.of(EventType.OBJECT_CREATED))
                .filters(List.of(NotificationKeyFilter.builder().prefix("products/").build()))
                .build());

        // =========================================================================
        // 7. API Gateway RestApi Original Preservada
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

        // Nova Rota para obtenção da URL Pré-assinada de Upload de Foto
        final IResource uploadUrlResource = productByIdResource.addResource("upload-url");
        uploadUrlResource.addMethod("POST", new LambdaIntegration(generateUploadUrl));
    }

    // =========================================================================
    // Metodo Auxiliar createPythonLambda Expandido sem quebrar a assinatura
    // =========================================================================
    private Function createPythonLambda(
            final String id,
            final String handler,
            final Table table,
            final ILayerVersion layer,
            final boolean isWritable,
            final Vpc vpc,
            final SecurityGroup securityGroup,
            final Map<String, String> extraEnvVars
    ) {
        final Function.Builder builder = Function.Builder.create(this, id)
                .runtime(Runtime.PYTHON_3_12)
                .handler(handler)
                .code(Code.fromAsset("lambda_code"))
                .layers(List.of(layer));

        // Se a Lambda precisar acessar o Valkey/ElastiCache, associa à VPC e Security Group
        if (vpc != null && securityGroup != null) {
            builder.vpc(vpc)
                    .vpcSubnets(SubnetSelection.builder().subnetType(SubnetType.PRIVATE_WITH_EGRESS).build())
                    .securityGroups(List.of(securityGroup));
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