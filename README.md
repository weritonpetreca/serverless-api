# AWS Developer Learning Plan — Enterprise Serverless API

[![AWS Certified](https://img.shields.io/badge/AWS-Certified_Cloud_Practitioner-FF9900?logo=amazon-aws&logoColor=white)](https://aws.amazon.com/certification/certified-cloud-practitioner/)
[![Java Version](https://img.shields.io/badge/Java-21_LTS-red?logo=openjdk&logoColor=white)](https://openjdk.org/projects/jdk/21/)
[![Python Version](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Gradle](https://img.shields.io/badge/Gradle-8.x_Kotlin_DSL-025E8D?logo=gradle&logoColor=white)](https://gradle.org/)
[![AWS CDK](https://img.shields.io/badge/AWS_CDK-v2_Java-FF9900?logo=amazon-aws&logoColor=white)](https://aws.amazon.com/cdk/v2/)
[![Amazon DynamoDB](https://img.shields.io/badge/Amazon_DynamoDB-4053D6?logo=amazondynamodb&logoColor=white)](https://aws.amazon.com/dynamodb/)
[![Docker & Testcontainers](https://img.shields.io/badge/Testcontainers-DynamoDB_Local-2496ED?logo=docker&logoColor=white)](https://testcontainers.com/)
[![LocalStack](https://img.shields.io/badge/LocalStack-v3-00B2FF?logo=localstack&logoColor=white)](https://localstack.cloud/)
[![Pytest](https://img.shields.io/badge/Testing-Pytest_v8-0A9EDC?logo=pytest&logoColor=white)](https://docs.pytest.org/)
[![License](https://img.shields.io/badge/License-MIT-purple.svg)](LICENSE)

Este repositório registra a evolução prática e a elevação de maturidade técnica ao longo do **AWS Developer Learning Plan** (trilha oficial do AWS Skill Builder voltada ao desenvolvimento, segurança e operações de APIs em escala).

O projeto consiste em uma API Serverless para e-commerce, projetada sob os pilares de **Clean Architecture**, **DevSecOps Shift-Left**, **Tratamento de Erros Padronizado (ADR 0003)** e **Resiliência Distribuída (Exponential Backoff + Jitter)**.

---

## 🌟 O Diferencial de Engenharia ("Senior Mindset")

Em vez de limitar o projeto a scripts básicos propostos no curso, o ecossistema foi estruturado com padrões de **Enterprise Software Engineering**:

* **IaC Robusto e Tipado (Java 21 + Kotlin DSL):** Toda a Infraestrutura como Código (IaC) é declarada em **Java 21** usando **AWS CDK v2** e **Gradle Kotlin DSL**, eliminando erros de configuração em tempo de síntese.
* **Computação Otimizada (Python 3.12 + Lambda Layers):** Lambdas de alta performance com tempo de inicialização reduzido (*low cold start*), isolando dependências de terceiros (como Pydantic v2) em **Lambda Layers**.
* **Clean Architecture & SOLID:** Separação estrita de responsabilidades no runtime Python:
    * `handlers/`: Interceptação e contrato HTTP API Gateway.
    * `domain/`: Schemas de validação declarativos com **Pydantic v2** (Shift-Left Security).
    * `repository/`: Abstração de acesso a dados (DAO Pattern) desacoplada do runtime.
    * `shared/`: Modulo centralizado de classificação de erros (**`ErrorClassifier`**) e resiliência (**`@retry_with_backoff`**).
* **Tratamento de Erros Padronizado (ADR 0003):** Contrato estrito de erros JSON (`type`, `message`, `timestamp`, `request_id`, `details`, `suggestions`) para visibilidade e rastreabilidade no CloudWatch Logs.
* **Garantia de Qualidade Multi-Camadas (Shift-Left QA):**
    * **Unidade Python:** Handlers e regras de negócio testadas com `pytest-mock` e `event_factory`.
    * **Integração Real:** DAO testado contra container do DynamoDB Local rodando via **Testcontainers**.
    * **Infraestrutura Java:** Testes de asserção da stack CDK usando **JUnit 5**.
    * **E2E Local:** Validação completa sem custos na AWS através do **LocalStack v3** (`cdklocal`).

---

## 🏛️ Arquitetura Atual do Projeto (Módulo 05)

A cada módulo concluído, a arquitetura evolui de forma incremental. O diagrama abaixo representa o estado atual do sistema com borda tratada, resiliência no DynamoDB e camadas de logs:

![AWS Serverless Product API Architecture v3](./docs/03-error-handling-resiliency/architecture_v3.png)

> 📌 *Para visualizar os diagramas das fases anteriores, acesse os READMEs específicos dentro da pasta [`docs/`](./docs/).*

---

## 🗺️ Painel de Evolução do Projeto (18 Módulos)

A tabela abaixo acompanha o ciclo de vida do e-commerce. O repositório evolui *in-place*. Para acessar o código em marcos anteriores, consulte as **Git Tags** ou as pastas em `docs/`.

| Fase | Módulo Técnico | Status | Tecnologias Chave | Versão / Tag | Documentação Detalhada |
| :---: | :--- | :---: | :--- | :---: | :---: |
| **0** | **1. Introduction to AWS Developer Learning Plan** | Concluído | AWS CLI, SDK, IAM | `v1.0.0-phase1.3` | [Acessar Docs](./docs/00-setup/README.md) |
| **0** | **2. Introduction to Being an AWS Developer** | Concluído | Compute Options (Lambda/ECS/EC2) | `v1.0.0-phase1.3` | [Acessar Docs](./docs/00-evaluation/README.md) |
| **1** | **3. Building Your First Serverless API** | Concluído | AWS CDK v2, Java 21, API Gateway, Lambda | `v1.0.0-phase1.3` | [Acessar Docs](./docs/01-serverless-api-cdk/README.md) |
| **1** | **4. Adding Data to Your API** | Concluído | Amazon DynamoDB, LocalStack E2E, Pydantic v2 | `v4.0.0` | [Acessar Docs](./docs/02-dynamodb-data-persistence/README.md) |
| **1** | **5. Testing and Error Handling** | Concluído 🌟 | Clean Architecture, ADR 0003, Retry, Testcontainers | `v5.0.0` | [Acessar Docs](./docs/03-error-handling-resiliency/README.md) |
| **2** | **6. Scaling with Data Storage** | 📅 Planejado | Amazon S3, Amazon ElastiCache, CDN | - | *A fazer* |
| **2** | **7. Advanced Lambda Patterns** | 📅 Planejado | Advanced Layers, Dynamic Config | - | *A fazer* |
| **2** | **8. Adding Asynchronous Processing** | 📅 Planejado | Amazon SQS, Amazon SNS, EventBridge | - | *A fazer* |
| **2** | **9. Real-time Data Streaming** | 📅 Planejado | Amazon Data Firehose, Continuous Streams | - | *A fazer* |
| **3** | **10. Containerized Applications** | 📅 Planejado | Docker, Amazon ECS, AWS Fargate | - | *A fazer* |
| **3** | **11. Building APIs on Amazon EC2** | 📅 Planejado | Amazon EC2, ALB, Auto Scaling | - | *A fazer* |
| **3** | **12. Integration and Advanced Testing** | 📅 Planejado | Integration Tests, Mocking External APIs | - | *A fazer* |
| **4** | **13. User Authentication & Authorization** | 📅 Planejado | Amazon Cognito, OAuth2, JWT Roles | - | *A fazer* |
| **4** | **14. Securing Data and Secrets** | 📅 Planejado | AWS Secrets Manager, KMS Encryption | - | *A fazer* |
| **5** | **15. Infrastructure as Code** | 📅 Planejado | Multi-Environment, AWS AppConfig | - | *A fazer* |
| **5** | **16. CI/CD Automation** | 📅 Planejado | AWS CodePipeline, GitHub Actions | - | *A fazer* |
| **6** | **17. Monitoring and Observability** | 📅 Planejado | CloudWatch Metrics, AWS X-Ray Tracing | - | *A fazer* |
| **6** | **18. Performance Optimization** | 📅 Planejado | Multi-layer Caching, Profiling, FinOps | - | *A fazer* |

---

## 📂 Estrutura de Diretórios do Repositório

```text
serverless-api/
├── adr/                                # Architecture Decision Records (Tomadas de Decisão)
│   ├── 0001-use-java-21-and-gradle-kotlin-dsl-for-cdk.md
│   ├── 0002-use-nosql-dynamodb-and-pydantic-validation.md
│   └── 0003-error-handling-resiliency-and-testing-strategy.md
├── docs/                               # Diários de Bordo e Aprofundamento Teórico
│   ├── 00-evaluation/                  # Avaliações iniciais do ecossistema AWS
│   ├── 00-setup/                       # Configuração de credenciais e ambiente local
│   ├── 01-serverless-api-cdk/          # Módulo 03: Primeiros Passos com CDK & Lambda
│   ├── 02-dynamodb-data-persistence/   # Módulo 04: Persistência NoSQL com DynamoDB
│   └── 03-error-handling-resiliency/   # Módulo 05: Clean Architecture, Resiliência e QA
├── lambda_code/                        # Runtime Computacional Python 3.12 (Clean Architecture)
│   ├── domain/                         # Schemas e Validações Pydantic v2 (product_schema.py)
│   ├── handlers/                       # Borda HTTP (get, insert, query, update)
│   ├── repository/                     # Camada DAO de Persistência (products_db.py)
│   ├── shared/                         # ErrorClassifier, Resilience Decorator & Utilities
│   ├── tests/                          # Suíte de Testes Automatizados Python
│   │   ├── integration/                # Testes de Integração com Testcontainers + DynamoDB
│   │   └── unit/                       # Testes Unitários dos Handlers e Resiliência
│   ├── utils/                          # EventFactory e Configurações de Mocks (conftest.py)
│   ├── vendor/                         # Dependências locais isoladas para testes rápidos
│   ├── pytest.ini                      # Configuração de PYTHONPATH e escopo do Pytest
│   ├── requirements.txt                # Dependências Otimizadas de Produção
│   └── requirements-dev.txt            # Dependências Completas de QA e Testes
├── lambda_layer/                       # Camada Isolada de Dependências para AWS Lambda
├── src/                                # Infraestrutura como Código (IaC) - AWS CDK em Java 21
│   ├── main/java/com/petreca/          # Stack Principal (ProductApiStack) e Entrypoint (MyCdkApp)
│   └── test/java/com/petreca/          # Testes de Asserção de Infraestrutura em JUnit 5
├── build.gradle.kts                    # Script de Compilação Gradle Kotlin DSL
├── cdk.json                            # Configuração do Orquestrador AWS CDK
├── settings.gradle.kts                 # Configurações de Módulo Gradle
└── README.md                           # Vitrine Principal do Repositório (Este Arquivo)
```

---

## 🌐 Tabela de Endpoints da API

| Método | Endpoint | Descrição | Status Sucesso | Status Erro |
| :---: | :--- | :--- | :---: | :---: |
| `POST` | `/products` | Cadastra um novo produto | `201 Created` | `400` / `500` |
| `GET` | `/products/{id}` | Busca produto por ID (UUID) | `200 OK` | `400` / `404` / `500` |
| `PATCH` | `/products/{id}` | Atualização parcial atômica | `200 OK` | `400` / `404` / `500` |
| `GET` | `/products?category={cat}` | Consulta indexada via GSI | `200 OK` | `400` / `500` |

---

## ⚙️ Como Executar e Testar o Projeto Localmente

### 1. Preparar o Ambiente Virtual Python (Na Raiz)
```bash
# Criar e ativar o ambiente virtual na raiz do repositório
python3 -m venv .venv
source .venv/bin/activate

# Instalar as dependências de desenvolvimento e QA
pip install -r lambda_code/requirements-dev.txt
```

### 2. Executar os Testes Automatizados (Shift-Left QA)
```bash
# Executar Testes Unitários Python (Handlers, Schemas & Resiliência)
pytest lambda_code/tests/unit/

# Executar Testes de Integração Python (Sobe container DynamoDB Local via Testcontainers)
pytest lambda_code/tests/integration/

# Executar Testes de Infraestrutura Java (Asserções CDK com JUnit 5)
./gradlew test
```

### 3. Deploy e Validação End-to-End no LocalStack
```bash
# Iniciar o LocalStack em segundo plano
localstack start -d

# Executar o bootstrap e deploy via cdklocal
cdklocal bootstrap
cdklocal deploy

# Exemplo de chamada POST com validação de contrato
curl -k -X POST https://<API_ID>.execute-api.localhost.localstack.cloud:4566/prod/products \
     -H "Content-Type: application/json" \
     -d '{"title": "Espada de Prata", "category": "Home", "description": "Lâmina para monstros.", "price": 850.00}'
```

---

## 📄 Decisões de Arquitetura (ADRs)

Todas as grandes escolhas técnicas do projeto são documentadas formalmente:
* 📜 **[ADR 0001: Java 21 & Gradle Kotlin DSL para AWS CDK](./adr/0001-use-java-21-and-gradle-kotlin-dsl-for-cdk.md)**
* 📜 **[ADR 0002: NoSQL DynamoDB & Validação Shift-Left com Pydantic v2](./adr/0002-use-nosql-dynamodb-and-pydantic-validation.md)**
* 📜 **[ADR 0003: Tratamento de Erros Padronizado, Resiliência e Estratégia de QA](./adr/0003-error-handling-resiliency-and-testing-strategy.md)**

---

## 📝 Licença

Este projeto está sob a licença [MIT](LICENSE).