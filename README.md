# AWS Developer Learning Plan — Enterprise Serverless API

[![AWS Certified](https://img.shields.io/badge/AWS-Certified_Cloud_Practitioner-FF9900?logo=amazon-aws&logoColor=white)](https://aws.amazon.com/certification/certified-cloud-practitioner/)
[![Java Version](https://img.shields.io/badge/Java-21_LTS-red?logo=openjdk&logoColor=white)](https://openjdk.org/projects/jdk/21/)
[![Python Version](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Gradle](https://img.shields.io/badge/Gradle-8.x_Kotlin_DSL-025E8D?logo=gradle&logoColor=white)](https://gradle.org/)
[![AWS CDK](https://img.shields.io/badge/AWS_CDK-v2_Java-FF9900?logo=amazon-aws&logoColor=white)](https://aws.amazon.com/cdk/v2/)
[![Amazon DynamoDB](https://img.shields.io/badge/Amazon_DynamoDB-4053D6?logo=amazondynamodb&logoColor=white)](https://aws.amazon.com/dynamodb/)
[![Amazon S3](https://img.shields.io/badge/Amazon_S3-569A31?logo=amazons3&logoColor=white)](https://aws.amazon.com/s3/)
[![Amazon ElastiCache](https://img.shields.io/badge/Amazon_ElastiCache_Redis-C7131F?logo=redis&logoColor=white)](https://aws.amazon.com/elasticache/)
[![AWS Systems Manager](https://img.shields.io/badge/AWS_Systems_Manager-Parameter_Store-FF9900?logo=amazon-aws&logoColor=white)](https://aws.amazon.com/systems-manager/)
[![Amazon EventBridge](https://img.shields.io/badge/Amazon_EventBridge-E7157B?logo=amazon-aws&logoColor=white)](https://aws.amazon.com/eventbridge/)
[![Amazon SQS](https://img.shields.io/badge/Amazon_SQS-E7157B?logo=amazon-aws&logoColor=white)](https://aws.amazon.com/sqs/)
[![Amazon SNS](https://img.shields.io/badge/Amazon_SNS-E7157B?logo=amazon-aws&logoColor=white)](https://aws.amazon.com/sns/)
[![Docker & Testcontainers](https://img.shields.io/badge/Testcontainers-DynamoDB_Local-2496ED?logo=docker&logoColor=white)](https://testcontainers.com/)
[![Pytest](https://img.shields.io/badge/Testing-Pytest_v8-0A9EDC?logo=pytest&logoColor=white)](https://docs.pytest.org/)
[![License](https://img.shields.io/badge/License-MIT-purple.svg)](LICENSE)

Este repositório registra a evolução prática e a elevação de maturidade técnica ao longo do **AWS Developer Learning Plan** (trilha oficial do AWS Skill Builder voltada ao desenvolvimento, segurança e operações de APIs em escala).

O projeto consiste em uma API Serverless para e-commerce, projetada sob os pilares de **Clean Architecture**, **DevSecOps Shift-Left**, **Tratamento de Erros Padronizado (ADR 0003)**, **Armazenamento Desacoplado de Mídias (S3)**, **Caching de Alta Performance (ElastiCache Redis/Valkey)**, **Governança de Configuração Dinâmica (SSM Parameter Store)**, **Arquitetura Orientada a Eventos (EventBridge)**, **Mensageria Assíncrona Resiliente (SQS & DLQ)** e **Notificações Multicanal (SNS Fanout)**.

---

## 🌟 O Diferencial de Engenharia ("Senior Mindset")

Em vez de limitar o projeto a scripts básicos propostos no curso, o ecossistema foi estruturado com padrões de **Enterprise Software Engineering**:

* **IaC Robusto e Tipado (Java 21 + Kotlin DSL):** Toda a Infraestrutura como Código (IaC) é declarada em **Java 21** usando **AWS CDK v2** e **Gradle Kotlin DSL**, otimizada para os *quality gates* do SonarQube através de `records` do Java 21 e Pattern Matching para `instanceof`.
* **Arquitetura Orientada a Eventos Desacoplada (Amazon EventBridge Custom Bus):** Roteamento inteligente de eventos de negócio (`online-store-events`) sob o padrão **Event-Carried State Transfer**, eliminando o acoplamento direto entre a API de borda e consumidores de segundo plano.
* **Processamento Assíncrono e Resiliência com Amazon SQS e DLQ:** Processamento de pedidos em segundo plano via fila `order-processing-queue` com *Long Polling* de 20s (FinOps) e isolamento automático de mensagens com falha em Dead Letter Queue (`order-processing-dlq`) via `RedrivePolicy` (`maxReceiveCount = 3`).
* **Padrão Transacional Compensatório (*Saga Pattern Rollback*):** Worker de segundo plano (`OrderProcessorWorker`) com mecanismo de estorno automático passo a passo para garantir consistência do sistema em falhas parciais de serviços de terceiros.
* **Notificações Multicanal com Amazon SNS (Pub/Sub & Fanout):** Transmissão simultânea de confirmações de pedidos para e-mail e SMS com filtragem declarativa por atributos de cliente (*FilterPolicy*).
* **Governança de Configurações com AWS Systems Manager Parameter Store:** Parâmetros operacionais e *feature flags* armazenados hierarquicamente (`/store/dev/config/`) na nuvem, com leitura cacheada em memória RAM local (`SSMParameterManager`) para zerar latência e custos de API.
* **Isolamento de Falhas com Circuit Breaker State Machine:** Disjuntor distribuído (`shared/circuit_breaker.py`) com três estados (`CLOSED`, `OPEN`, `HALF_OPEN`) protegendo a aplicação contra falhas em cascata em serviços externos, com *Fast-Fail* mapeado para HTTP 503.
* **Retentativas Inteligentes com Equal Jitter:** Evolução do decorador `@retry_with_backoff` utilizando a fórmula oficial do AWS Well-Architected Framework para eliminação de tempestades de retentativa (*Thundering Herd*).
* **Armazenamento de Mídias Desacoplado (S3 & Presigned URLs):** Upload direto de fotos de produtos para o Amazon S3 bypassando a API Gateway e a Lambda, reduzindo custos de banda e tempo de execução faturado a zero.
* **Caching de Alta Performance (ElastiCache Redis/Valkey):** Padrão **Cache-Aside** (*Lazy Loading*) em VPC com respostas de leitura em submilissegundos (aceleração comprovada de 376 ms para 6.84 ms) e invalidação explícita.
* **Clean Architecture & SOLID:** Separação estrita de responsabilidades no runtime Python 3.12 (`handlers/`, `domain/`, `repository/` e `shared/`).
* **Garantia de Qualidade Multi-Camadas (Shift-Left QA):**
  * **Unidade Python:** Handlers, Schemas Pydantic, S3 Event Processors, Cache, Circuit Breaker, SSM Manager e SQS Workers testados com `pytest-mock`, `moto v5` e `event_factory` (38+ testes unitários).
  * **Integração Real:** DAO testado contra container oficial do DynamoDB Local rodando via **Testcontainers**.
  * **Infraestrutura Java:** Testes de asserção da stack CDK (EventBridge, SQS, DLQ, SNS, SSM, S3, VPC, ElastiCache, DynamoDB) usando **JUnit 5** (13 testes).

---

## 🏛️ Arquitetura Atual do Projeto (Módulo 08)

A cada módulo concluído, a arquitetura evolui de forma incremental. O diagrama abaixo representa o estado atual do sistema com borda tratada, roteamento de eventos no EventBridge, filas SQS resilientes com DLQ, notificações SNS, gerenciamento de configurações no SSM Parameter Store, disjuntor distribuído, upload de mídias via Presigned URLs, processamento por eventos S3, caching em memória com ElastiCache e resiliência no DynamoDB:

![AWS Serverless Product API Architecture v6](./docs/06-adding-asynchronous-processing/architecture_v6.png)

> 📌 *Para visualizar os diagramas e documentações detalhadas das fases anteriores, acesse os READMEs específicos dentro da pasta [`docs/`](./docs/).*

---

## 🗺️ Painel de Evolução do Projeto (18 Módulos)

A tabela abaixo acompanha o ciclo de vida do e-commerce. O repositório evolui *in-place*. Para acessar o código em marcos anteriores, consulte as **Git Tags** ou as pastas em `docs/`.

| Fase | Módulo Técnico | Status | Tecnologias Chave | Versão / Tag | Documentação Detalhada |
| :---: | :--- | :---: | :--- | :---: | :---: |
| **0** | **1. Introduction to AWS Developer Learning Plan** | Concluído | AWS CLI, SDK, IAM | `v1.0.0-phase1.3` | [Acessar Docs](./docs/00-setup/README.md) |
| **0** | **2. Introduction to Being an AWS Developer** | Concluído | Compute Options (Lambda/ECS/EC2) | `v1.0.0-phase1.3` | [Acessar Docs](./docs/00-evaluation/README.md) |
| **1** | **3. Building Your First Serverless API** | Concluído | AWS CDK v2, Java 21, API Gateway, Lambda | `v1.0.0-phase1.3` | [Acessar Docs](./docs/01-serverless-api-cdk/README.md) |
| **1** | **4. Adding Data to Your API** | Concluído | Amazon DynamoDB, LocalStack E2E, Pydantic v2 | `v4.0.0` | [Acessar Docs](./docs/02-dynamodb-data-persistence/README.md) |
| **1** | **5. Testing and Error Handling** | Concluído | Clean Architecture, ADR 0003, Retry, Testcontainers | `v5.0.0` | [Acessar Docs](./docs/03-error-handling-resiliency/README.md) |
| **2** | **6. Scaling with Data Storage** | Concluído | Amazon S3, ElastiCache Valkey/Redis, Presigned URLs | `v6.0.0` | [Acessar Docs](./docs/04-scaling-data-storage/README.md) |
| **2** | **7. Advanced Lambda Patterns** | Concluído | SSM Parameter Store, Circuit Breaker, Equal Jitter | `v7.0.0` | [Acessar Docs](./docs/05-advanced-lambda-patterns/README.md) |
| **2** | **8. Adding Asynchronous Processing** | Concluído 🌟 | Amazon EventBridge, Amazon SQS, DLQ, Amazon SNS | `v8.0.0` | [Acessar Docs](./docs/06-adding-asynchronous-processing/README.md) |
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
│   ├── 0003-error-handling-resiliency-and-testing-strategy.md
│   ├── 0004-scaling-with-s3-and-elasticache-valkey.md
│   ├── 0005-advanced-lambda-patterns.md
│   └── 0006-asynchronous-processing-and-event-driven-architecture.md
├── docs/                               # Diários de Bordo e Aprofundamento Teórico
│   ├── 00-evaluation/                  # Avaliações iniciais do ecossistema AWS
│   ├── 00-setup/                       # Configuração de credenciais e ambiente local
│   ├── 01-serverless-api-cdk/          # Módulo 03: Primeiros Passos com CDK & Lambda
│   ├── 02-dynamodb-data-persistence/   # Módulo 04: Persistência NoSQL com DynamoDB
│   ├── 03-error-handling-resiliency/   # Módulo 05: Clean Architecture, Resiliência e QA
│   ├── 04-scaling-data-storage/        # Módulo 06: Amazon S3 & ElastiCache Caching
│   ├── 05-advanced-lambda-patterns/    # Módulo 07: AWS SSM Parameter Store & Circuit Breaker
│   └── 06-adding-asynchronous-processing/ # Módulo 08: Amazon EventBridge, SQS, DLQ e SNS
├── lambda_code/                        # Runtime Computacional Python 3.12 (Clean Architecture)
│   ├── domain/                         # Schemas Pydantic v2 (product_schema.py, event_schema.py)
│   ├── handlers/                       # Borda HTTP & SQS Worker (get, insert, query, update, upload_url, process_image, order_processor)
│   ├── repository/                     # Camada DAO (products_db.py) & Abstração de Cache (cache_db.py)
│   ├── shared/                         # ErrorClassifier, CircuitBreaker, SSMManager, EventPublisher, Resilience & Utilities
│   ├── tests/                          # Suíte de Testes Automatizados Python
│   │   ├── integration/                # Testes de Integração com Testcontainers + DynamoDB
│   │   └── unit/                       # Testes Unitários dos Handlers, Resiliência, SSM, Circuit Breaker, EventPublisher e SQS Worker
│   ├── utils/                          # EventFactory e Configurações de Mocks (conftest.py)
│   ├── vendor/                         # Dependências locais isoladas para testes e empacotamento
│   ├── pytest.ini                      # Configuração de PYTHONPATH e escopo do Pytest
│   ├── requirements.txt                # Dependências Otimizadas de Produção
│   └── requirements-dev.txt            # Dependências Completas de QA e Testes
├── lambda_layer/                       # Camada Isolada de Dependências para AWS Lambda
├── src/                                # Infraestrutura como Código (IaC) - AWS CDK em Java 21
│   ├── main/java/com/petreca/          # Stack Principal (ProductApiStack - DynamoDB, S3, Valkey, VPC, SSM, EventBridge, SQS, SNS)
│   └── test/java/com/petreca/          # Testes de Asserção de Infraestrutura em JUnit 5 (13 testes)
├── build.gradle.kts                    # Script de Compilação Gradle Kotlin DSL com automação de vendor
├── cdk.json                            # Configuração do Orquestrador AWS CDK
├── settings.gradle.kts                 # Configurações de Módulo Gradle
└── README.md                           # Vitrine Principal do Repositório (Este Arquivo)
```

---

## 🌐 Tabela de Endpoints da API

| Método | Endpoint | Descrição | Status Sucesso | Status Erro |
| :---: | :--- | :--- | :---: | :---: |
| `POST` | `/products` | Cadastra produto no DynamoDB e dispara evento no EventBridge | `201 Created` | `400` / `500` / `502` / `503` |
| `GET` | `/products/{id}` | Busca produto por ID (Cache-Aside Valkey -> DynamoDB) | `200 OK` | `400` / `404` / `500` |
| `PATCH` | `/products/{id}` | Atualização parcial atômica e invalidação de cache | `200 OK` | `400` / `404` / `500` / `503` |
| `GET` | `/products?category={cat}` | Consulta por Categoria (Cache-Aside -> GSI DynamoDB) | `200 OK` | `400` / `500` |
| `POST` | `/products/{id}/upload-url` | Gera Presigned URL temporária do S3 para upload de mídias | `200 OK` | `400` / `500` |

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
# Executar Testes Unitários Python (Handlers, Schemas, Cache, SSM, Circuit Breaker, EventPublisher e SQS Worker)
pytest lambda_code/tests/unit/

# Executar Testes de Integração Python (Sobe container DynamoDB Local via Testcontainers)
pytest lambda_code/tests/integration/

# Executar Testes de Infraestrutura Java (13 Asserções CDK com JUnit 5)
./gradlew test
```

### 3. Validação End-to-End na AWS Cloud (`cdk deploy`)
Como esta arquitetura utiliza recursos empresariais de nuvem privada (**VPC, Security Groups, ElastiCache, SSM Parameter Store, EventBridge, SQS, DLQ e SNS**), a validação E2E é realizada diretamente na AWS Cloud:

```bash
# 1. Compilação e empacotamento automático de dependências no vendor/
./gradlew clean build -x test

# 2. Deploy na conta da AWS
cdk deploy

# 3. Leitura direta do EventBus no Amazon EventBridge
aws events describe-event-bus --name "online-store-events"

# 4. Destruição da infraestrutura pós-teste (FinOps Zero Custo)
cdk destroy
```

---

## 📄 Decisões de Arquitetura (ADRs)

Todas as grandes escolhas técnicas do projeto são documentadas formalmente:
* 📜 **[ADR 0001: Java 21 & Gradle Kotlin DSL para AWS CDK](./adr/0001-use-java-21-and-gradle-kotlin-dsl-for-cdk.md)**
* 📜 **[ADR 0002: NoSQL DynamoDB & Validação Shift-Left com Pydantic v2](./adr/0002-use-nosql-dynamodb-and-pydantic-validation.md)**
* 📜 **[ADR 0003: Tratamento de Erros Padronizado, Resiliência e Estratégia de QA](./adr/0003-error-handling-resiliency-and-testing-strategy.md)**
* 📜 **[ADR 0004: Scaling com Amazon S3 & ElastiCache Caching](./adr/0004-scaling-with-s3-and-elasticache-valkey.md)**
* 📜 **[ADR 0005: Padrões Avançados de Lambda - SSM Caching, Circuit Breaker & Equal Jitter](./adr/0005-advanced-lambda-patterns.md)**
* 📜 **[ADR 0006: Adoção de Mensageria Assíncrona e Event-Driven com EventBridge, SQS, DLQ e SNS](./adr/0006-asynchronous-processing-and-event-driven-architecture.md)**

---

## 📝 Licença

Este projeto está sob a licença [MIT](LICENSE).