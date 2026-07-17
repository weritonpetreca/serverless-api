package com.petreca;

import software.amazon.awscdk.RemovalPolicy;
import software.amazon.awscdk.Stack;
import software.amazon.awscdk.StackProps;
import software.amazon.awscdk.services.apigateway.CorsOptions;
import software.amazon.awscdk.services.apigateway.IResource;
import software.amazon.awscdk.services.apigateway.LambdaIntegration;
import software.amazon.awscdk.services.apigateway.RestApi;
import software.amazon.awscdk.services.dynamodb.*;
import software.amazon.awscdk.services.lambda.*;
import software.amazon.awscdk.services.lambda.Runtime;
import software.constructs.Construct;

import java.util.List;

public class ProductApiStack extends Stack {

    private static final String TABLE_NAME_ENV = "PRODUCTS_TABLE_NAME";

    public ProductApiStack(final Construct scope, final String constructId, final StackProps props) {
        super(scope, constructId, props);

        final Table productsTable = Table.Builder.create(this, "ProductsTable")
                .tableName("Products")
                .partitionKey(Attribute.builder()
                        .name("id")
                        .type(AttributeType.STRING)
                        .build())
                .billingMode(BillingMode.PAY_PER_REQUEST)
                .build();

        productsTable.addGlobalSecondaryIndex(GlobalSecondaryIndexProps.builder()
                        .indexName("category-index")
                        .partitionKey(Attribute.builder()
                                .name("category")
                                .type(AttributeType.STRING)
                                .build())
                        .projectionType(ProjectionType.ALL)
                        .build());

        final ILayerVersion dependencyLayer = LayerVersion.Builder.create(this, "AppDependencyLayer")
                .layerVersionName("ProductApiDeps")
                .removalPolicy(RemovalPolicy.RETAIN)
                .code(Code.fromAsset("lambda_layer"))
                .compatibleRuntimes(List.of(Runtime.PYTHON_3_12))
                .description("Camada contendo Pydantic v2 e utilitário compartilhados.")
                .build();

        final Function queryProducts = createPythonLambda(
                "QueryProducts",
                "query_products.handler",
                productsTable,
                dependencyLayer,
                false
        );
        queryProducts.addEnvironment("CATEGORY_GSI_NAME", "category-index");

        final Function getProduct = createPythonLambda(
                "GetProduct",
                "get_product.handler",
                productsTable,
                dependencyLayer,
                false
        );

        final Function insertProduct = createPythonLambda(
                "InsertProduct",
                "insert_product.handler",
                productsTable,
                dependencyLayer,
                true
        );

        final Function updateProduct = createPythonLambda(
                "UpdateProduct",
                "update_product.handler",
                productsTable,
                dependencyLayer,
                true
        );

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
    }

    private Function createPythonLambda(
            final String id,
            final String handler,
            final Table table,
            final ILayerVersion layer,
            final boolean isWritable
    ) {
        final Function function = Function.Builder.create(this, id)
                .runtime(Runtime.PYTHON_3_12)
                .handler(handler)
                .code(Code.fromAsset("lambda_code"))
                .layers(List.of(layer))
                .build();

        function.addEnvironment(TABLE_NAME_ENV, table.getTableName());

        function.addEnvironment("PYTHONPATH", "/var/task:/var/task/vendor");

        if (isWritable) {
            table.grantReadWriteData(function);
        } else {
            table.grantReadData(function);
        }

        return function;
    }
}
