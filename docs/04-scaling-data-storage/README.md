# Módulo 06 — Scaling with Data Storage (Amazon S3 & ElastiCache Valkey)

Detalhamento conceitual, arquitetural e prático do armazenamento de arquivos binários no Amazon S3 via Presigned URLs, processamento reativo acionado por eventos S3 e otimização de performance com caching em memória via Amazon ElastiCache (Valkey / Redis).

---

## 01. Problema / Contexto
Com o crescimento do catálogo de produtos e aumento do tráfego de usuários, duas limitações críticas surgem em arquiteturas puramente NoSQL:

1. **Limitação de Armazenamento de Arquivos Binários:** O Amazon DynamoDB possui um limite de 400 KB por item e é otimizado para dados estruturados. Armazenar arquivos de mídia diretamente no banco inviabiliza a escala e gera custos elevados por Unidade de Capacidade de Escrita/Leitura (WCU/RCU).
2. **Gargalo de Latência e Custos por Consultas Repetitivas (Throttling & Hot Keys):** Consultas frequentes para produtos populares e buscas por categoria realizam chamadas constantes ao DynamoDB. Sem uma camada de cache em memória, o tempo de resposta aumenta e gera custo desnecessário por RCU.
3. **Overhead Computacional em Transferência de Mídia:** Enviar binários através da API Gateway e AWS Lambda consome memória RAM, estende o tempo de execução faturado e esbarra no limite de 10 MB de payload da API Gateway.

---

## 02. Objetivo
*   Implementar o armazenamento de mídias no **Amazon S3** desacoplado da borda HTTP por meio de **Presigned URLs** (`put_object` / `get_object`).
*   Construir uma arquitetura **Orientada a Eventos (*Event-Driven*)** com gatilhos do S3 (`s3:ObjectCreated:*`) para extrair metadados e atualizar o catálogo no DynamoDB assincronamente.
*   Implantar uma camada de cache em memória de alta performance com **Amazon ElastiCache (Valkey)** utilizando o padrão **Cache-Aside** (*Lazy Loading*) para respostas em submilissegundos.
*   Garantir resiliência total (**Graceful Degradation**): se o cache em memória falhar ou estiver indisponível, a aplicação redireciona automaticamente para o DynamoDB sem interromper o serviço.
*   Implementar governança de custos (**FinOps**) através de regras de ciclo de vida do S3 (*Lifecycle Rules*: Standard -> Standard-IA -> Glacier -> Expiration).
*   Cobrir 100% das novas capacidades com testes automatizados:
    *   **Testes de Infraestrutura Java:** Asserções CDK via JUnit 5 para Bucket S3, VPC, Security Group e Cluster ElastiCache Valkey.
    *   **Testes Unitários Python:** Validação dos handlers de Presigned URL, processamento reativo de eventos S3 e abstração de cache com `pytest`, `pytest-mock` e `moto`.
    *   **Testes de Integração Python:** Validação de expressões atômicas de atualização no DynamoDB via `Testcontainers`.

---

## 03. Solução
A aplicação foi expandida para criar um fluxo híbrido de armazenamento binário e caching em memória:

```text
                               ┌───────────────────────────┐
                               │       Cliente HTTP        │
                               └─────────────┬─────────────┘
                                             │
                      1. POST /products/{id}/image-upload-url
                                             │
                                             ▼
                               ┌───────────────────────────┐
                               │    Amazon API Gateway     │
                               └─────────────┬─────────────┘
                                             │
                                             ▼
                               ┌───────────────────────────┐
                               │   GenerateUploadUrlLambda │
                               └─────────────┬─────────────┘
                                             │ 2. Retorna Presigned URL (HTTP 200)
                                             ▼
                               ┌───────────────────────────┐
                               │   3. PUT Direto da Imagem │
                               └─────────────┬─────────────┘
                                             │
                                             ▼
┌──────────────────────────┐      ┌──────────────────────────┐
│ Amazon ElastiCache       │◄─────┤      Amazon S3           │
│ (Valkey / Redis)         │      │  (product-assets-bucket) │
└─────────────▲────────────┘      └─────────────┬────────────┘
              │                                 │ 4. Evento s3:ObjectCreated
              │ (Cache Hit / Miss)              ▼
              │                   ┌──────────────────────────┐
              ├───────────────────┤ ProcessImageMetadata     │
              │                   │ Lambda                   │
              │                   └─────────────┬────────────┘
              │                                 │
              │                                 │ 5. Atualiza Metadados
              ▼                                 ▼
┌────────────────────────────────────────────────────────────┐
│                  Amazon DynamoDB (Products)                │
└────────────────────────────────────────────────────────────┘
```

1. **Desacoplamento de Upload via Presigned URLs (`handlers/generate_upload_url.py`):**
   O cliente solicita uma URL pré-assinada (`POST /products/{id}/upload-url`) válida por 1 hora com trava de `ContentType` (`image/jpeg`, `image/png`, `image/webp`), realizando o `PUT` diretamente para o S3.
2. **Processamento Reativo por Eventos S3 (`handlers/process_image_metadata.py`):**
   Acionado pelo evento `s3:ObjectCreated:*` na chave `products/{product_id}/{image_type}.jpg`. Executa `s3.head_object` para ler o tamanho do arquivo sem baixar o binário, associa a URL e os metadados ao DynamoDB e invalida o cache do produto.
3. **Caching em Memória com ElastiCache Valkey (`repository/cache_db.py` & `repository/products_db.py`):**
   Abstração desacoplada de cache com cliente `redis-py`. O `ProductsRepository` aplica o padrão Cache-Aside:
    - `get_by_id`: Consulta `product:{product_id}` no Valkey (TTL 3600s).
    - `find_by_category`: Consulta `search:category:{category}` no Valkey (TTL 1800s).
    - **Invalidação de Cache (*Cache Invalidation*):** Exclusão explícita de chaves durante atualizações (`save`, `update`, `add_image_to_product`).

---

## 04. Ferramentas

*   **Linguagem & Framework de Teste Computacional:** Python 3.12, Pytest, pytest-mock, Moto v5 (`mock_aws`), Testcontainers (DynamoDB Local), redis-py
*   **Linguagem & Framework de Teste IaC:** Java 21, JUnit 5, AWS CDK Assertions
*   **Contêineres & Emulação Local:** Docker, LocalStack v3 (`cdklocal`), Redis/Valkey
*   **Ferramenta de Deploy e CLI:** AWS CDK CLI, AWS CLI v2

---

## 05. Validação Local & Cobertura de Testes

### 5.1. Suíte de Testes Automatizados (Shift-Left)

A suíte completa é composta por 29 testes aprovados cobrindo todas as camadas da aplicação:

**1. Testes de Infraestrutura (Java CDK + JUnit 5):**
Na raiz do projeto:
```bash
./gradlew test
```
*   `ProductApiStackTest.java`: Valida a declaração da tabela DynamoDB, GSI `category-index`, Bucket S3 com SSE-S3 e PublicAccessBlock, VPC, Security Group na porta 6379 e Cluster ElastiCache Valkey.

**2. Testes Unitários do Runtime Python (Handlers, Pydantic & Cache):**
Dentro da pasta `lambda_code/`:
```bash
cd lambda_code
pytest tests/unit/
```
*   `test_generate_upload_url.py`: Testa geração de Presigned URL (200), ID ausente (400), tipo de conteúdo não suportado (400) e falhas S3 (500).
*   `test_process_image_metadata.py`: Processamento de evento S3 com atualização do DynamoDB (200) e eventos vazios.
*   `test_cache_db.py`: Testa leitura/gravação no Valkey/Redis com `decimal_serializer` e *Graceful Degradation* em caso de falha do Redis.
*   `test_get_product.py`, `test_insert_product.py`, `test_query_product.py`, `test_update_product.py`, `test_resilience.py`: Mantidos com 100% de aprovação.

**3. Testes de Integração do Repositório (Testcontainers + DynamoDB):**
```bash
pytest tests/integration/
```
*   `test_products_db_integration.py`: Sobe um container `amazon/dynamodb-local` via Docker e valida chamadas físicas de `save`, `get_by_id`, `update` e a expressão atômica de `add_image_to_product`.

---

### 5.2. Teste de Integração End-to-End no LocalStack (`cdklocal`)

Para validar a orquestração de todos os recursos localmente via Docker sem custos de nuvem:

**1. Inicializar o LocalStack e Subir a Infraestrutura:**
```bash
localstack start -d

# Compilar o código Java do CDK e implantar no LocalStack
./gradlew clean build -x test
rm -rf cdk.out/
cdklocal bootstrap
cdklocal deploy
```

**2. Execução de Requisições de Teste via Terminal (`curl`):**

* **Cenário A: Solicitando URL Pré-assinada de Upload (POST - HTTP 200 OK)**
  ```bash
  curl -X POST "https://<API_ID>.execute-api.localhost.localstack.cloud:4566/prod/products/prod_123/upload-url?type=main&content_type=image/jpeg"
  ```

* **Cenário B: Upload Direto da Imagem para o Amazon S3 (PUT - HTTP 200 OK)**
  ```bash
  curl -X PUT -H "Content-Type: image/jpeg" --data-binary "@minha_foto.jpg" "<PRESIGNED_URL_OBTIDA>"
  ```

---

## 06. Implantação e Validação na AWS Cloud

Após a validação nos testes locais, a infraestrutura é enviada para a nuvem real da AWS:

### 6.1. Deploy da Infraestrutura
```bash
cdk deploy
```

### 6.2. Rastreabilidade no CloudWatch
Execute uma chamada de upload e consulte os logs de processamento reativo no Amazon CloudWatch:

```bash
aws logs filter-log-events \
    --log-group-name "/aws/lambda/ProductApiStack-ProcessImageMetadataFunction" \
    --filter-pattern "prod_123"
```

### 6.3. Destruição dos Recursos (FinOps)
Ao finalizar a validação em nuvem, destrua a stack para zerar custos de infraestrutura:
```bash
cdk destroy
```

---

## 07. Aprendizados & Troubleshooting (Maturidade Técnica)

### 🧠 Troubleshooting 01: Divergência de Tipos no DynamoDB (`TypeError: Float types are not supported`)
* **O Problema:** Tentar salvar valores do tipo `float` nativo do Python diretamente no DynamoDB lança um erro do Boto3.
* **A Resolução:** Todos os atributos financeiros são mantidos estritamente como `Decimal("350.00")` no repositório.

### 🧠 Troubleshooting 02: Atribuição de Lista em vez de String na Chave S3
* **O Problema:** A separação da chave S3 `object_key.split("/")` retornava uma lista `['products', 'prod_123', 'main.jpg']`, e atribuir a lista inteira para `product_id` causava `ResourceNotFoundException` no DynamoDB.
* **A Resolução:** A extração foi ajustada para `product_id = key_parts`.

### 🧠 Troubleshooting 03: Moto v5 `mock_aws` e Instanciação de Módulos Globais
* **O Problema:** Instanciar `ProductsRepository()` no topo do módulo fazia o Boto3 capturar a tabela antes do contexto em memória do `mock_aws` ser ativado no teste.
* **A Resolução:** Mantivemos a instância no topo global para maximizar os *Warm Starts* em produção, e reatribuímos `process_image_metadata.repository = ProductsRepository()` dentro do escopo do teste.

---

## 08. Análise FinOps & Resiliência

* **Governança FinOps no S3:** A transição automática para `S3 Standard-IA` em 30 dias e `Glacier` em 90 dias reduz os custos de armazenamento de mídias antigas em até 80%.
* **Desacoplamento de Borda:** O upload via Presigned URL reduz o custo de banda e o tempo de execução faturado na AWS Lambda a zero durante o envio de arquivos pesados.
* **Graceful Degradation no Caching:** Falhas de rede ou timeout no ElastiCache Valkey são tratadas silenciosamente pela abstração `CacheRepository`, mantendo a disponibilidade da API via fallback transparente para o DynamoDB.