package com.petreca;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import software.amazon.awscdk.App;
import software.amazon.awscdk.assertions.Template;

import java.util.Map;

class ProductApiStackTest {

    @Test
    @DisplayName("Deve sintetizar o template contendo as funções Lambda corretamente")
    void shouldCreateLambdaFunctionsWithCorrectRuntime() {

        final App app = new App();
        final ProductApiStack stack = new ProductApiStack(app, "TestStack", null);

        final Template template = Template.fromStack(stack);

        template.hasResourceProperties("AWS::Lambda::Function", Map.of(
                "Runtime", "python3.12"
        ));
    }

    @Test
    @DisplayName("Deve conter uma instância do APU Gateway REST")
    void shouldHaveApiGatewayRestApi() {

        final App app = new App();
        final ProductApiStack stack = new ProductApiStack(app, "TestStack", null);

        final Template template = Template.fromStack(stack);

        template.resourceCountIs("AWS::ApiGateway::RestApi", 1);
    }
}
