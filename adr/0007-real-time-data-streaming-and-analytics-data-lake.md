# ADR 0007: Real-Time Data Streaming com Amazon Data Firehose, Transformação em Voo via Lambda e Analytics Data Lake S3

---

## 01. Contexto & Declaração do Problema

À medida que a nossa plataforma Serverless para e-commerce se expande, o volume de eventos de telemetria e interações de usuários (como visualizações de produtos, buscas e compras) cresce continuamente.

Processar esses eventos de forma síncrona ou por meio de varreduras em lote (*batch processing*) apresenta três grandes limitações de engenharia:
1. **Atraso Analítico de Horas/Dias**: O processamento em lote impede que a equipe de dados e BI acesse dados de comportamento em tempo real para alimentar recomendações personalizadas ou sistemas instantâneos de detecção de fraude.
2. **Custo Elevado por WCU/RCU no NoSQL**: Salvar eventos de clique (*clickstreams*) de alto volume diretamente no banco de produção (DynamoDB) gera um custo desnecessário e risco de *throttling* de throughput.
3. **Acoplamento na Borda da API**: A captura de métricas analíticas não deve impactar a latência da requisição HTTP do cliente ou bloquear o fluxo de resposta.

---

## 02. Decisão Arquitetural

Decidimos implantar uma pipeline de **Real-Time Data Streaming** com **Amazon Data Firehose**, **AWS Lambda In-Flight Transformations** e um **Data Lake dedicado no Amazon S3**:

### 1. Amazon Data Firehose (`customer-activity-stream`)
* **Ingestão e Entrega Gerenciada**: Adotar o Amazon Data Firehose devido à sua escala 100% automática e integração nativa com o S3, eliminando a necessidade de gerenciar aplicações consumidoras ou partições (*shards*) como no Kinesis Data Streams.
* **Buffering & Compressão GZIP**: Configurar buffers otimizados de **1 MB** e **60 segundos** com compressão **GZIP** antes da gravação no S3, reduzindo os custos de armazenamento no Data Lake em até 80%.
* **CloudWatch Error Logging**: Ativar o `CloudWatchLoggingOptions` nativo sob o log group `/aws/kinesisfirehose/customer-activity-stream` para monitoria operacional sem alertas no console da AWS.

### 2. Bucket S3 Dedicado para o Data Lake (`AnalyticsDataLakeBucket`)
* **Isolamento de Segurança & IAM**: Criar um bucket exclusivo (`analytics-datalake-*`) segregado do bucket de mídias de produtos (`product-assets-*`), garantindo políticas IAM estritas e isolando dados internos confidenciais do e-commerce.
* **Governança FinOps de Ciclo de Vida**:
  - Dados Analíticos (`analytics/`): Transition para `S3 Standard-IA` em 90 dias, `S3 Glacier` em 180 dias e expiração aos 365 dias (1 ano).
  - Registros de Erro (`errors/`): Expiração automática aos 90 dias.

### 3. Transformação em Voo (*In-Flight Transformation*) com AWS Lambda (`handlers/stream_transformer.py`)
* **Processador Lambda e Timeout Fino (30s)**: A Lambda `StreamTransformerFunction` é configurada com timeout de 30 segundos no CDK (`Duration.seconds(30)`) para comportar lotes de até 500 registros sem estourar o limite padrão.
* **Cache em Memória por Lote (`local_product_cache`)**: A Lambda reutiliza buscas do mesmo produto dentro do mesmo lote em RAM local, reduzindo chamadas de rede no DynamoDB de N para 1 por lote.
* **Decodificação e Codificação Base64**: A Lambda decodifica a payload Base64, enriquece eventos de `product_view` com dados do produto diretamente no DynamoDB (`repository.table.get_item`), descarta atividades de robôs e testes (`result: 'Dropped'`) e re-codifica o JSON transformado em Base64 com quebra de linha `\n`.
* **Compatibilidade com Motores SQL**: A quebra de linha `\n` ao final de cada registro JSON garante compatibilidade nativa com motores de busca como **Amazon Athena** e **Amazon Redshift Spectrum**.

### 4. Isolamento de Falhas (`errors/firehose/`)
* Registros que falharem durante a transformação são marcados como `ProcessingFailed` e salvos automaticamente no prefixo `errors/firehose/` do S3 para investigação sem interromper o fluxo contínuo do Data Lake.

---

## 03. Consequências & Trade-offs

### Positivas
* **Análise Near Real-Time**: Dados de atividade do cliente chegam ao Data Lake em no máximo **60 segundos**.
* **FinOps Otimizado**: A filtragem de registros de teste (`Dropped`) e a compressão GZIP reduzem o consumo de armazenamento e custos no S3 em até 80%.
* **Desacoplamento de Borda**: As chamadas do `StreamPublisher` são não-bloqueantes (`try/except`), garantindo que qualquer oscilação do Firehose não afete a resposta HTTP `< 10 ms` entregue ao cliente.

### Desafios & Mitigações
* **Contrato Estrito de Base64**: O Firehose exige um contrato rígido de payload Base64. *Mitigação*: Cobertura de 100% com testes unitários em `test_stream_transformer.py` e `test_stream_publisher.py`.