package com.petreca;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import software.amazon.awscdk.App;
import software.amazon.awscdk.assertions.Template;

import java.util.List;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertDoesNotThrow;

class ProductApiStackTest {

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
}