plugins {
    id("application")
}

group = "org.example"
version = "1.0-SNAPSHOT"

repositories {
    mavenCentral()
}

dependencies {
    implementation(libs.aws.cdk.lib)
    implementation(libs.constructs)
    testImplementation(platform(libs.junit.bom))
    testImplementation(libs.junit.jupiter)
    testRuntimeOnly(libs.junit.platform.launcher)
}

application {
    mainClass.set("com.petreca.MyCdkApp")
}

java {
    toolchain {
        languageVersion.set(JavaLanguageVersion.of(21))
    }
}

tasks.test {
    useJUnitPlatform()
}

// Task para instalar dependências Python no vendor automaticamente antes da compilação do CDK
tasks.register<Exec>("installPythonVendorDeps") {
    group = "build"
    description = "Instala dependências do requirements.txt na pasta lambda_code/vendor"
    commandLine("pip", "install", "-r", "lambda_code/requirements.txt", "-t", "lambda_code/vendor", "--upgrade", "--quiet")
}

// Garante que o ./gradlew build execute o installPythonVendorDeps automaticamente
tasks.named("build") {
    dependsOn("installPythonVendorDeps")
}