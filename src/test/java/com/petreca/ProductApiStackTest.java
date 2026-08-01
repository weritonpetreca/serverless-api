package com.petreca;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import software.amazon.awscdk.App;
import software.amazon.awscdk.assertions.Match;
import software.amazon.awscdk.assertions.Template;

import java.util.List;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertDoesNotThrow;

class ProductApiStackTest {

    // =========================================================================
    // 1. Testes de Borda e Runtimes
    // =========================================================================

    @Test
    @DisplayName("Deve sintetizar o template contendo as funções Lambda em Python 3.12")
    void shouldCreateLambdaFunctionsWithCorrectRuntime() {
        final App app = new App();
        final ProductApiStack stack = new ProductApiStack(app, "TestStack", null);
        final Template template = Template.fromStack(stack);

        assertDoesNotThrow(() ->
                template.hasResourceProperties("AWS::Lambda::Function", Map.of(
                        "Runtime", "python3.12"
                ))
        );
    }

    @Test
    @DisplayName("Deve conter uma instância do API Gateway REST")
    void shouldHaveApiGatewayRestApi() {
        final App app = new App();
        final ProductApiStack stack = new ProductApiStack(app, "TestStack", null);
        final Template template = Template.fromStack(stack);

        assertDoesNotThrow(() ->
                template.resourceCountIs("AWS::ApiGateway::RestApi", 1)
        );
    }

    // =========================================================================
    // 2. Testes de Persistência NoSQL e Armazenamento em S3
    // =========================================================================

    @Test
    @DisplayName("Deve criar tabela no DynamoDB com chave id e GSI category-index em ALL")
    void shouldCreateDynamoDbTableWithGsi() {
        final App app = new App();
        final ProductApiStack stack = new ProductApiStack(app, "TestStack", null);
        final Template template = Template.fromStack(stack);

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
    @DisplayName("Deve criar o Bucket S3 com Criptografia SSE-S3 e Bloqueio Público")
    void shouldCreateS3BucketWithSecurityAndLifecycle() {
        final App app = new App();
        final ProductApiStack stack = new ProductApiStack(app, "TestStack", null);
        final Template template = Template.fromStack(stack);

        assertDoesNotThrow(() ->
                template.hasResourceProperties("AWS::S3::Bucket", Map.of(
                        "PublicAccessBlockConfiguration", Map.of(
                                "BlockPublicAcls", true,
                                "BlockPublicPolicy", true,
                                "IgnorePublicAcls", true,
                                "RestrictPublicBuckets", true
                        ),
                        "BucketEncryption", Map.of(
                                "ServerSideEncryptionConfiguration", List.of(
                                        Map.of("ServerSideEncryptionByDefault", Map.of("SSEAlgorithm", "AES256"))
                                )
                        )
                ))
        );
    }

    // =========================================================================
    // 3. Testes de Rede e Caching em Memória (ElastiCache Redis)
    // =========================================================================

    @Test
    @DisplayName("Deve criar a VPC e o Security Group autorizando a porta 6379 do Cache")
    void shouldCreateVpcAndSecurityGroupForCache() {
        final App app = new App();
        final ProductApiStack stack = new ProductApiStack(app, "TestStack", null);
        final Template template = Template.fromStack(stack);

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
        final App app = new App();
        final ProductApiStack stack = new ProductApiStack(app, "TestStack", null);
        final Template template = Template.fromStack(stack);

        assertDoesNotThrow(() ->
                template.hasResourceProperties("AWS::ElastiCache::CacheCluster", Map.of(
                        "Engine", "redis",
                        "CacheNodeType", "cache.t3.micro",
                        "NumCacheNodes", 1
                ))
        );
    }

    // =========================================================================
    // 4. Testes Módulo 07: AWS SSM Parameter Store & Handlers
    // =========================================================================

    @Test
    @DisplayName("Deve sintetizar os parâmetros de configuração no AWS SSM Parameter Store")
    void shouldCreateSsmParametersWithCorrectConfig() {
        final App app = new App();
        final ProductApiStack stack = new ProductApiStack(app, "TestStack", null);
        final Template template = Template.fromStack(stack);

        assertDoesNotThrow(() ->
                template.hasResourceProperties("AWS::SSM::Parameter", Map.of(
                        "Name", "/store/dev/config/api_timeout",
                        "Type", "String",
                        "Value", "5"
                ))
        );

        assertDoesNotThrow(() ->
                template.hasResourceProperties("AWS::SSM::Parameter", Map.of(
                        "Name", "/store/dev/config/circuit_breaker_threshold",
                        "Type", "String",
                        "Value", "5"
                ))
        );

        assertDoesNotThrow(() ->
                template.hasResourceProperties("AWS::SSM::Parameter", Map.of(
                        "Name", "/store/dev/config/feature_flag_image_processing",
                        "Type", "String",
                        "Value", "true"
                ))
        );
    }

    @Test
    @DisplayName("Deve conter as funções Lambda de negócio configuradas com seus respectivos handlers")
    void shouldHaveBusinessLambdaFunctionsConfigured() {
        final App app = new App();
        final ProductApiStack stack = new ProductApiStack(app, "TestStack", null);
        final Template template = Template.fromStack(stack);

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
    }
}