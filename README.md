# AWS Developer Learning Plan — Enterprise Serverless API

[![AWS Certified](https://img.shields.io/badge/AWS-Certified_Cloud_Practitioner-FF9900?logo=amazon-aws&logoColor=white)](https://aws.amazon.com/certification/certified-cloud-practitioner/)
[![Java Version](https://img.shields.io/badge/Java-21-red?logo=openjdk&logoColor=white)](https://openjdk.org/projects/jdk/21/)
[![Python Version](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Gradle](https://img.shields.io/badge/Gradle-9.3.0-blue?logo=gradle&logoColor=white)](https://gradle.org/)
[![AWS CDK](https://img.shields.io/badge/AWS_CDK-v2-FF9900?logo=amazon-aws&logoColor=white)](https://aws.amazon.com/cdk/v2/)
[![JUnit 5](https://img.shields.io/badge/JUnit-5-green?logo=junit5&logoColor=white)](https://junit.org/junit5/)
[![License](https://img.shields.io/badge/License-MIT-purple.svg)](LICENSE)

Este repositório registra a evolução prática do meu progresso ao longo do **AWS Developer Learning Plan** (uma trilha oficial de 22h15m do AWS Skill Builder voltada ao desenvolvimento, segurança e operações de APIs em escala).

O projeto simula um cenário corporativo real: a construção de uma API para um catálogo de e-commerce que evolui de simples buscas locais até uma infraestrutura de vendas resiliente, segura e de alta performance.

### 🌟 O Diferencial de Engenharia ("Senior Mindset")
Em vez de simplesmente replicar as implementações básicas em Python propostas pelo curso, decidi elevar a maturidade técnica do projeto aplicando conceitos de **Enterprise Software Engineering**:
*   **IaC Estático e Robusto:** Migração de toda a camada de Infraestrutura como Código (IaC) para **Java 21** utilizando **Gradle Kotlin DSL** e **Gradle Version Catalogs**, mitigando desvios de configuração antes mesmo da síntese.
*   **Abordagem Híbrida Inteligente:** CDK em Java 21 para garantir máxima consistência em tempo de compilação combinado com funções de computação (Lambdas) em Python 3.12 para garantir um tempo de inicialização ultrarrápido (*ultra-low cold start*) e economia de recursos.
*   **Testes Shift-Left:** Cobertura de testes de asserção lógica da infraestrutura com JUnit 5 antes de qualquer deploy em nuvem.

---

## 🗺️ Painel de Evolução do Projeto (18 Módulos)

A tabela abaixo mapeia a jornada completa de evolução do e-commerce. O repositório evolui de forma incremental e *in-place*. Para consultar o estado exato do código em marcos anteriores, utilize as **Git Tags** correspondentes.

| Fase | Módulo Técnico | Status | Tecnologias Chave | Versão do Código | Documentação Conceitual |
| :---: | :--- | :---: | :--- | :---: | :---: |
| **0** | **1. Introduction to AWS Developer Learning Plan** |  Concluído | AWS CLI, SDK, AWS SSO | `v1.0.0-phase1.3` | [Acessar Docs](./docs/00-setup/README.md) |
| **0** | **2. Introduction to Being an AWS Developer** |  Concluído | Compute Options (Lambda/ECS/EC2) | `v1.0.0-phase1.3` | [Acessar Docs](./docs/00-evaluation/README.md) |
| **1** | **3. Building Your First Serverless API** |  Concluído | AWS CDK v2, Java 21, API Gateway, Lambda (Python) | `v1.0.0-phase1.3` | [Acessar Detalhamento](./docs/01-serverless-api-cdk/README.md) |
| **1** | **4. Adding Data to Your API** | ⏳ Próximo | Amazon DynamoDB, Data Persistence | - | *A fazer* |
| **1** | **5. Testing and Error Handling** | 📅 Planejado | DLQ, Amazon CloudWatch Alarms, Mocking | - | *A fazer* |
| **2** | **6. Scaling with Data Storage** | 📅 Planejado | Amazon S3, Amazon ElastiCache, CDN | - | *A fazer* |
| **2** | **7. Advanced Lambda Patterns** | 📅 Planejado | Lambda Layers, Config Management | - | *A fazer* |
| **2** | **8. Adding Asynchronous Processing** | 📅 Planejado | Amazon SQS, Amazon SNS, EventBridge | - | *A fazer* |
| **2** | **9. Real-time Data Streaming** | 📅 Planejado | Amazon Data Firehose, Continuous Streams | - | *A fazer* |
| **3** | **10. Containerized Applications** | 📅 Planejado | Docker, Amazon ECS, AWS Fargate | - | *A fazer* |
| **3** | **11. Building APIs on Amazon EC2** | 📅 Planejado | Amazon EC2, ALB, Auto Scaling | - | *A fazer* |
| **3** | **12. Integration and Advanced Testing** | 📅 Planejado | Integration Tests, Mocking Payment APIs | - | *A fazer* |
| **4** | **13. User Authentication & Authorization** | 📅 Planejado | Amazon Cognito, OAuth2, JWT Roles | - | *A fazer* |
| **4** | **14. Securing Data and Secrets** | 📅 Planejado | AWS Secrets Manager, KMS Encryption | - | *A fazer* |
| **5** | **15. Infrastructure as Code** | 📅 Planejado | Environment deploys, AWS AppConfig | - | *A fazer* |
| **5** | **16. CI/CD Automation** | 📅 Planejado | AWS CodePipeline, CodeBuild, CodeDeploy | - | *A fazer* |
| **6** | **17. Monitoring and Observability** | 📅 Planejado | CloudWatch Metrics, AWS X-Ray Tracing | - | *A fazer* |
| **6** | **18. Performance Optimization** | 📅 Planejado | Multi-layer Caching, Profiling, FinOps | - | *A fazer* |

---

## 📁 Estrutura de Diretórios do Projeto

```text
serverles-api/
├── adr/                                # Architecture Decision Records (Tomadas de Decisão)
│   └── 0001-use-java-21-and-gradle-kotlin-dsl-for-cdk.md
├── docs/                               # Documentações conceituais e diários de bordo de cada módulo
│   └── 01-serverless-api-cdk/
│       └── README.md                   # Detalhamento técnico teórico do Módulo 3
├── gradle/
│   └── wrapper/                        # Arquivos de bootstrap do Gradle Wrapper
│   └── libs.versions.toml              # Version Catalog centralizado (Gerenciamento de SCA)
├── lambda_code/                        # Código-fonte computacional das funções serveless (Python 3.12)
│   ├── get_product.py                  # Endpoint: GET /products/{id}
│   └── query_products.py               # Endpoint: GET /products
├── src/
│   ├── main/
│   │   java/com/petreca/
│   │       ├── MyCkdApp.java           # Classe principal (Entrypoint) do AWS CDK
│   │       └── ProductApiStack.java    # Definição e mapeamento da infraestrutura cloud
│   └── test/
│       java/com/petreca/
│           └── ProductApiStackTest.java # Testes de unidade e asserção de infraestrutura (JUnit 5)
├── build.gradle.kts                    # Script de compilação Kotlin DSL (Java 21 Toolchain)
├── cdk.json                            # Instruções de orquestração do CLI do AWS CDK
├── settings.gradle.kts                 # Configuração de escopo do projeto Gradle
└── README.md                           # Painel e Vitrine Principal do Repositório (Este Arquivo)
```

---

## ⚙️ Como Executar e Implantar o Projeto

### Pré-requisitos
*   Java 21 (configurado via SDKMAN! ou Toolchain)
*   AWS CLI configurado com credenciais de administrador ativas (`aws sts get-caller-identity`)
*   NodeJS 22+ e AWS CDK CLI instalado (`npm install -g aws-cdk`)

### 1. Validar a Infraestrutura Localmente (Testes de Shift-Left)
Para garantir que todos os recursos, permissões de IAM e runtimes estão corretos antes de provisionar recursos na nuvem, execute os testes unitários da stack:
```bash
./gradlew test
```

### 2. Sintetizar o Template do CloudFormation
Gere a representação declarativa da sua infraestrutura em formato JSON/YAML (localizado em `cdk.out/`):
```bash
cdk synth
```

### 3. Realizar o Deploy para a Nuvem AWS
Implante a API Gateway e as funções Lambda diretamente na sua conta AWS:
```bash
cdk deploy
```

### 4. Destruir os Recursos para Controle de Custos (FinOps)
Ao finalizar os testes manuais na nuvem, remova todos os recursos provisionados para evitar cobranças indesejadas:
```bash
cdk destroy
```