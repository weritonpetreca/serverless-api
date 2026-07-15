# ADR 0001: Uso de Java 21 e Gradle Kotlin DSL para a Infraestrutura (AWS CDK)

## Contexto
O *AWS Developer Learning Plan* sugere o uso de Python para codificar a infraestrutura como código (IaC) com o AWS CDK. No entanto, em ecossistemas de software corporativos de alta escala, o uso de linguagens dinâmicas e sem tipagem estática para IaC aumenta o risco de desvios de configuração (*configuration drift*) e erros de digitação simples que só são detectados após o deploy na nuvem.

Além disso, a consistência em ambientes de desenvolvimento que já utilizam a JVM se beneficia de ferramentas unificadas de compilação, suítes de testes estruturadas (como JUnit 5) e controle centralizado de dependências de segurança.

## Decisão
Decidi adotar **Java 21**, **Gradle com Kotlin DSL (`build.gradle.kts`)** e **Gradle Version Catalogs (`gradle/libs.versions.toml`)** para o desenvolvimento das Stacks do AWS CDK.

A validação de integridade da infraestrutura será realizada via testes de asserção lógica locais utilizando o framework **JUnit 5**, aplicando o conceito de *Shift-Left Testing*.

## Consequências

### Positivas ✅
*   **Segurança de Tipos (Type Safety):** O compilador do Java impede a definição de propriedades inválidas, tipos incorretos ou nulos nas Stacks do CDK antes mesmo da síntese (`cdk synth`), diminuindo o tempo de feedback de erros.
*   **Gestão Centralizada de Dependências (SCA):** Centralização de todas as versões de bibliotecas e plugins de testes de segurança no arquivo `libs.versions.toml`, facilitando auditorias automatizadas e atualizações de segurança em lote.
*   **Shift-Left Testing Confiável:** Capacidade de rodar testes de unidade e asserções de infraestrutura localmente em milissegundos, sem necessidade de realizar chamadas de rede ou deploys reais para validar a estrutura do template do CloudFormation.
*   **Produtividade na IDE:** Autocomplete inteligente e forte indexação no IntelliJ IDEA para classes e propriedades de infraestrutura da AWS.

### Negativas / Compensações (Trade-offs) ⚠️
*   **Verbosidade de Código:** O Java exige maior verbosidade e cerimônia (como o uso de builders complexos do CDK) em relação à flexibilidade sintática do Python.
*   **Gerenciamento do Gradle:** Necessidade de gerenciar e sincronizar os wrappers locais do Gradle e arquivos de compilação, o que adiciona overhead de inicialização ao projeto.