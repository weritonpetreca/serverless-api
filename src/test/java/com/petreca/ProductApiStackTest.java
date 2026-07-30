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
    // 1. Seus Testes Originais (Preservados Intactos)
    // =========================================================================

    @Test
    @DisplayName("Deve sintetizar o template contendo as funções Lambda corretamente")
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

    @Test
    @DisplayName("Deve criar tabela no DynamoDB com um GSI")
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

    // =========================================================================
    // 2. Testes de Cobertura Corrigidos para S3, Valkey, VPC e Lambdas de Negócio
    // =========================================================================

    @Test
    @DisplayName("Deve criar o Bucket S3 com Criptografia SSE-S3, Bloqueio Público e Ciclo de Vida FinOps")
    void shouldCreateS3BucketWithSecurityAndLifecycle() {
        final App app = new App();
        final ProductApiStack stack = new ProductApiStack(app, "TestStack", null);
        final Template template = Template.fromStack(stack);

        // Valida Bloqueio de Acesso Público e Criptografia
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

        // Valida Regras de Ciclo de Vida (Standard-IA em 30 dias e Glacier em 90 dias)
        assertDoesNotThrow(() ->
                template.hasResourceProperties("AWS::S3::Bucket", Map.of(
                        "LifecycleConfiguration", Map.of(
                                "Rules", List.of(
                                        Map.of(
                                                "Id", "ProductImageLifecycle",
                                                "Status", "Enabled",
                                                "Prefix", "products/",
                                                "Transitions", List.of(
                                                        Map.of("StorageClass", "STANDARD_IA", "TransitionInDays", 30),
                                                        Map.of("StorageClass", "GLACIER", "TransitionInDays", 90)
                                                ),
                                                "ExpirationInDays", 2555
                                        )
                                )
                        )
                ))
        );
    }

    @Test
    @DisplayName("Deve criar a VPC e o Security Group autorizando a porta 6379 do Cache")
    void shouldCreateVpcAndSecurityGroupForCache() {
        final App app = new App();
        final ProductApiStack stack = new ProductApiStack(app, "TestStack", null);
        final Template template = Template.fromStack(stack);

        // 1. Valida a criação da VPC
        assertDoesNotThrow(() ->
                template.resourceCountIs("AWS::EC2::VPC", 1)
        );

        // 2. Valida o Security Group e a regra de Ingress embutida na porta 6379/tcp
        assertDoesNotThrow(() ->
                template.hasResourceProperties("AWS::EC2::SecurityGroup", Map.of(
                        "GroupDescription", "Permite acesso ao ElastiCache Valkey na porta 6379 a partir da VPC",
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
    @DisplayName("Deve criar o Cluster ElastiCache com o engine Valkey na porta 6379")
    void shouldCreateElastiCacheValkeyCluster() {
        final App app = new App();
        final ProductApiStack stack = new ProductApiStack(app, "TestStack", null);
        final Template template = Template.fromStack(stack);

        assertDoesNotThrow(() ->
                template.hasResourceProperties("AWS::ElastiCache::CacheCluster", Map.of(
                        "Engine", "valkey",
                        "CacheNodeType", "cache.t3.micro",
                        "NumCacheNodes", 1
                ))
        );
    }

    @Test
    @DisplayName("Deve conter as funções Lambda de negócio configuradas com seus respectivos handlers")
    void shouldHaveBusinessLambdaFunctionsConfigured() {
        final App app = new App();
        final ProductApiStack stack = new ProductApiStack(app, "TestStack", null);
        final Template template = Template.fromStack(stack);

        // Valida a presença do handler de geração de URL pré-assinada
        assertDoesNotThrow(() ->
                template.hasResourceProperties("AWS::Lambda::Function", Map.of(
                        "Handler", "handlers.generate_upload_url.handler"
                ))
        );

        // Valida a presença do handler de processamento reativo de imagens do S3
        assertDoesNotThrow(() ->
                template.hasResourceProperties("AWS::Lambda::Function", Map.of(
                        "Handler", "handlers.process_image_metadata.handler"
                ))
        );
    }
}