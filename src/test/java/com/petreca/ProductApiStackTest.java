package com.petreca;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import software.amazon.awscdk.App;
import software.amazon.awscdk.assertions.Match;
import software.amazon.awscdk.assertions.Template;

import java.util.List;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertDoesNotThrow;
import static org.junit.jupiter.api.Assertions.assertNotNull;

@DisplayName("Suíte de Testes de Infraestrutura IaC - ProductApiStack")
class ProductApiStackTest {

    private Template template;

    @BeforeEach
    void setUp() {
        final App app = new App();
        final ProductApiStack stack = new ProductApiStack(app, "TestProductApiStack", null);
        this.template = Template.fromStack(stack);
    }

    @Test
    @DisplayName("Deverá sintetizar o template sem exceções")
    void shouldSynthesizeStackSuccessfully() {
        assertNotNull(template, "O Template sintetizado do CloudFormation não deve ser nulo.");
    }

    // =========================================================================
    // 1. Testes de Borda, Runtimes e API Gateway (Módulos 03-05 e 10)
    // =========================================================================

    @Test
    @DisplayName("Deve sintetizar o template contendo as funções Lambda em Python 3.12")
    void shouldCreateLambdaFunctionsWithCorrectRuntime() {
        assertDoesNotThrow(() ->
                template.hasResourceProperties("AWS::Lambda::Function", Map.of(
                        "Runtime", "python3.12"
                ))
        );
    }

    @Test
    @DisplayName("Deve conter uma instância do API Gateway REST e o recurso /orders")
    void shouldHaveApiGatewayRestApiAndOrdersResource() {
        assertDoesNotThrow(() ->
                template.resourceCountIs("AWS::ApiGateway::RestApi", 1)
        );

        assertDoesNotThrow(() ->
                template.hasResourceProperties("AWS::ApiGateway::Resource", Map.of(
                        "PathPart", "orders"
                ))
        );
    }

    @Test
    @DisplayName("Deve conter as funções Lambda de negócio configuradas com seus respectivos handlers")
    void shouldHaveBusinessLambdaFunctionsConfigured() {
        assertDoesNotThrow(() ->
                template.hasResourceProperties("AWS::Lambda::Function", Map.of(
                        "Handler", "handlers.generate_upload_url.handler"
                ))
        );

        assertDoesNotThrow(() ->
                template.hasResourceProperties("AWS::Lambda::Function", Map.of(
                        "Handler", "handlers.process_image_metadata.handler"
                ))
        );

        assertDoesNotThrow(() ->
                template.hasResourceProperties("AWS::Lambda::Function", Map.of(
                        "Handler", "handlers.order_processor.handler"
                ))
        );

        assertDoesNotThrow(() ->
                template.hasResourceProperties("AWS::Lambda::Function", Map.of(
                        "Handler", "handlers.stream_transformer.handler"
                ))
        );

        assertDoesNotThrow(() ->
                template.hasResourceProperties("AWS::Lambda::Function", Map.of(
                        "Handler", "handlers.create_order.handler"
                ))
        );
    }

    // =========================================================================
    // 2. Testes de Persistência NoSQL e Armazenamento em S3 (Módulos 04, 06 e 09)
    // =========================================================================

    @Test
    @DisplayName("Deve criar tabela no DynamoDB com chave id e GSI category-index em ALL")
    void shouldCreateDynamoDbTableWithGsi() {
        assertDoesNotThrow(() ->
                template.hasResourceProperties("AWS::DynamoDB::Table", Map.of(
                        "TableName", "Products",
                        "BillingMode", "PAY_PER_REQUEST",
                        "KeySchema", List.of(
                                Map.of("AttributeName", "id", "KeyType", "HASH")
                        )
                ))
        );

        assertDoesNotThrow(() ->
                template.hasResourceProperties("AWS::DynamoDB::Table", Map.of(
                        "GlobalSecondaryIndexes", List.of(
                                Map.of(
                                        "IndexName", "category-index",
                                        "KeySchema", List.of(
                                                Map.of("AttributeName", "category", "KeyType", "HASH")
                                        ),
                                        "Projection", Map.of("ProjectionType", "ALL")
                                )
                        )
                ))
        );
    }

    @Test
    @DisplayName("Deve criar Buckets S3 para Mídias e para o Data Lake Analítico com Bloqueio Público")
    void shouldCreateS3BucketsWithSecurity() {
        assertDoesNotThrow(() ->
                template.hasResourceProperties("AWS::S3::Bucket", Map.of(
                        "PublicAccessBlockConfiguration", Map.of(
                                "BlockPublicAcls", true,
                                "BlockPublicPolicy", true,
                                "IgnorePublicAcls", true,
                                "RestrictPublicBuckets", true
                        )
                ))
        );

        assertDoesNotThrow(() ->
                template.hasResourceProperties("AWS::S3::Bucket", Map.of(
                        "LifecycleConfiguration", Map.of(
                                "Rules", Match.arrayWith(List.of(
                                        Match.objectLike(Map.of(
                                                "Id", "AnalyticsDataLakeLifecycle",
                                                "Status", "Enabled",
                                                "Prefix", "analytics/"
                                        ))
                                ))
                        )
                ))
        );
    }

    // =========================================================================
    // 3. Testes de Rede e Caching em Memória (ElastiCache Redis) (Módulo 06)
    // =========================================================================

    @Test
    @DisplayName("Deve criar a VPC e o Security Group autorizando a porta 6379 do Cache")
    void shouldCreateVpcAndSecurityGroupForCache() {
        assertDoesNotThrow(() ->
                template.resourceCountIs("AWS::EC2::VPC", 1)
        );

        assertDoesNotThrow(() ->
                template.hasResourceProperties("AWS::EC2::SecurityGroup", Map.of(
                        "GroupDescription", "Permite acesso ao ElastiCache Redis na porta 6379 a partir da VPC",
                        "SecurityGroupIngress", Match.arrayWith(List.of(
                                Match.objectLike(Map.of(
                                        "FromPort", 6379,
                                        "ToPort", 6379,
                                        "IpProtocol", "tcp"
                                ))
                        ))
                ))
        );
    }

    @Test
    @DisplayName("Deve criar o Cluster ElastiCache com o engine redis na porta 6379")
    void shouldCreateElastiCacheRedisCluster() {
        assertDoesNotThrow(() ->
                template.hasResourceProperties("AWS::ElastiCache::CacheCluster", Map.of(
                        "Engine", "redis",
                        "CacheNodeType", "cache.t3.micro",
                        "NumCacheNodes", 1
                ))
        );
    }

    // =========================================================================
    // 4. Testes Módulo 07 & 08: SSM Parameter Store, EventBridge, SQS, SNS
    // =========================================================================

    @Test
    @DisplayName("Deve sintetizar os parâmetros de configuração no AWS SSM Parameter Store")
    void shouldCreateSsmParametersWithCorrectConfig() {
        assertDoesNotThrow(() ->
                template.hasResourceProperties("AWS::SSM::Parameter", Map.of(
                        "Name", "/store/dev/config/api_timeout",
                        "Type", "String",
                        "Value", "5"
                ))
        );
    }

    @Test
    @DisplayName("Deverá criar o Barramento Customizado no EventBridge e as Filas SQS")
    void shouldCreateMessagingResources() {
        assertDoesNotThrow(() ->
                template.hasResourceProperties("AWS::Events::EventBus", Map.of(
                        "Name", "online-store-events"
                ))
        );

        assertDoesNotThrow(() ->
                template.hasResourceProperties("AWS::SQS::Queue", Map.of(
                        "QueueName", "order-processing-queue",
                        "VisibilityTimeout", 300,
                        "ReceiveMessageWaitTimeSeconds", 20
                ))
        );

        assertDoesNotThrow(() ->
                template.hasResourceProperties("AWS::SNS::Topic", Map.of(
                        "TopicName", "customer-notifications-topic"
                ))
        );
    }

    // =========================================================================
    // 5. Testes Módulo 09: Amazon Data Firehose
    // =========================================================================

    @Test
    @DisplayName("Deverá criar o Delivery Stream do Firehose com Buffering de 1MB/60s e compressão GZIP")
    void shouldCreateFirehoseDeliveryStreamWithBufferingAndCompression() {
        assertDoesNotThrow(() ->
                template.hasResourceProperties("AWS::KinesisFirehose::DeliveryStream", Map.of(
                        "DeliveryStreamName", "customer-activity-stream",
                        "DeliveryStreamType", "DirectPut"
                ))
        );
    }

    // =========================================================================
    // 6. MÓDULO 10: TESTES DO AMAZON ECR, AMAZON ECS CLUSTER, FARGATE E ALB
    // =========================================================================

    @Test
    @DisplayName("Deverá criar o Repositório ECR Privado com Varredura de Imagens Ativada")
    void shouldCreateEcrRepositoryWithImageScanning() {
        assertDoesNotThrow(() ->
                template.hasResourceProperties("AWS::ECR::Repository", Map.of(
                        "RepositoryName", "store-recommendations",
                        "ImageScanningConfiguration", Map.of(
                                "ScanOnPush", true
                        )
                ))
        );
    }

    @Test
    @DisplayName("Deverá criar o Cluster Amazon ECS")
    void shouldCreateEcsCluster() {
        assertDoesNotThrow(() ->
                template.hasResourceProperties("AWS::ECS::Cluster", Map.of(
                        "ClusterName", "recommendations-cluster"
                ))
        );
    }

    @Test
    @DisplayName("Deverá criar a Task Definition do Fargate com 0.25 vCPU e 512 MB de RAM")
    void shouldCreateFargateTaskDefinition() {
        assertDoesNotThrow(() ->
                template.hasResourceProperties("AWS::ECS::TaskDefinition", Map.of(
                        "RequiresCompatibilities", List.of("FARGATE"),
                        "Cpu", "256",
                        "Memory", "512",
                        "NetworkMode", "awsvpc"
                ))
        );
    }

    @Test
    @DisplayName("Deverá criar o Serviço ECS Fargate com DesiredCount = 2")
    void shouldCreateEcsFargateService() {
        assertDoesNotThrow(() ->
                template.hasResourceProperties("AWS::ECS::Service", Map.of(
                        "LaunchType", "FARGATE",
                        "DesiredCount", 2
                ))
        );
    }

    @Test
    @DisplayName("Deverá criar o Application Load Balancer (ALB) com Target Group e Health Check em /health")
    void shouldCreateApplicationLoadBalancerWithHealthCheck() {
        assertDoesNotThrow(() ->
                template.hasResourceProperties("AWS::ElasticLoadBalancingV2::LoadBalancer", Map.of(
                        "Scheme", "internet-facing"
                ))
        );

        assertDoesNotThrow(() ->
                template.hasResourceProperties("AWS::ElasticLoadBalancingV2::TargetGroup", Map.of(
                        "HealthCheckPath", "/health"
                ))
        );
    }
}