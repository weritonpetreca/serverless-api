package com.petreca;

import software.amazon.awscdk.App;
import software.amazon.awscdk.StackProps;

public class MyCdkApp {

    public static void main(String[] args) {
        final App app = new App();

        new ProductApiStack(app, "ProductApiStack", StackProps.builder().build());

        app.synth();
    }
}
