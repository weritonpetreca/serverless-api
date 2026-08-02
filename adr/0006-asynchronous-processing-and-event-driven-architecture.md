# ADR 0006: Adoção de Mensageria Assíncrona e Arquitetura Orientada a Eventos com Amazon EventBridge, Amazon SQS, DLQ e Amazon SNS

---

## 01. Contexto & Problema

À medida que a nossa **Serverless Product API** evoluiu com suporte a persistência no DynamoDB, mídias no S3, cache no ElastiCache Redis e resiliência com Circuit Breaker, a borda da aplicação permanecia operando de forma essencialmente **síncrona (blocking)**.

Em cenários reais de e-commerce:
1. **Latência de Resposta Elevada**: Quando um cliente realiza um pedido ou atualiza um item no catálogo, executar todas as etapas secundárias (validação de estoque, cobrança, emissão de etiqueta de entrega, envio de e-mails/SMS de confirmação e atualização de analítica) síncronamente na requisição HTTP força o usuário a aguardar 5+ segundos pela resposta.
2. **Acoplamento Forte & Ponto Único de Falha**: Se o serviço secundário de envio de e-mails sofresse uma instabilidade momentânea, toda a requisição HTTP do usuário falhava, cancelando o pedido ou gerando estado inconsistente no banco de dados.
3. **Impossibilidade de Escala Independente**: Cada etapa da ordem possui requisitos de throughput diferentes. Forçar a execução sequencial impede a escala independente de cada worker de segundo plano.

---

## 02. Decisão Arquitetural

Decidimos transformar a arquitetura do e-commerce em uma **Arquitetura Orientada a Eventos Desacoplada e Assíncrona (*Event-Driven Architecture*)**, utilizando o trio de mensageria da AWS:

### 1. Amazon EventBridge (Barramento Customizado `online-store-events`)
* **Barramento Customizado**: Criamos o `EventBus` denominado `online-store-events` para isolar os eventos de negócio da aplicação em relação a eventos de sistema da conta AWS.
* **Padrão Event-Carried State Transfer**: Os eventos publicados (`DetailType: "Order Placed"`, `Source: "store.orders"`) carregarão a payload de dados completa (ID do pedido, itens, valores, dados do cliente), evitando que os consumidores precisem fazer chamadas adicionais de leitura (*read-backs*) ao DynamoDB.
* **Validação Shift-Left (Pydantic v2)**: O utilitário `EventPublisher` valida a estrutura do evento com o schema `OrderPlacedEventDetail` antes de chamar a API `put_events` do Boto3.

### 2. Amazon SQS + Dead Letter Queue (DLQ)
* **Fila Principal (`order-processing-queue`)**: Fila SQS Standard configurada com *Visibility Timeout* de 300 segundos (5 minutos) e retenção de 14 dias.
* **FinOps — Long Polling (`ReceiveMessageWaitTimeSeconds = 20`)**: A fila aguarda até 20 segundos para retornar mensagens, reduzindo o custo de requisições SQS ociosas em até 98%.
* **Dead Letter Queue (`order-processing-dlq`)**: Fila de quarentena vinculada com `maxReceiveCount = 3`. Se uma mensagem falhar 3 vezes consecutivas no worker, ela é isolada na DLQ para investigação sem perda de dados.
* **Gatilho Lambda Event Source Mapping**: A função `OrderProcessorWorker` consome a fila SQS em lotes (`BatchSize = 10`, `MaximumBatchingWindowInSeconds = 5s`), otimizando o custo de invocações.

### 3. Amazon SNS (Tópico de Notificação Multicanal `customer-notifications-topic`)
* **Padrão Pub/Sub & Fanout**: O worker publica no tópico SNS `customer-notifications-topic`, transmitindo notificações multicanal (e-mail, SMS) de forma desacoplada aos assinantes.

### 4. Transações Compensatórias (*Saga Pattern / Step Rollback*)
* No worker `OrderProcessorWorker`, se uma etapa posterior falhar (ex: emissão de frete) após etapas anteriores terem sido concluídas (ex: cobrança de pagamento), o worker executa ações compensatórias em ordem reversa (`_rollback_completed_steps`) antes de re-lançar a exceção para o SQS.

---

## 03. Consequências & Trade-offs

### Consequências Positivas
* **NPS & Experiência do Cliente**: A API Gateway responde `201 Created` ou `202 Accepted` em < 150 ms, enquanto o processamento pesado acontece de forma transparente em segundo plano.
* **Resiliência Zero Message Loss**: Mensagens com falhas de código ou dados corrompidos são isoladas na DLQ para auditoria e *Redrive*, sem bloquear as demais mensagens da fila.
* **Desacoplamento Total**: Novos consumidores (ex: analítica, recomendação, fraude) podem assinar o barramento `online-store-events` no EventBridge sem necessidade de alterar o código da API de produtos.
* **Governança DevSecOps**: Padrão de exceções unificado no `error_handler.py` (`EventPublishError` mapeado para HTTP 502 Bad Gateway).

### Trade-offs & Mitigações
* **Consistência Eventual (*Eventual Consistency*)**: O estoque e os e-mails de confirmação são atualizados assincronamente em alguns milissegundos após a resposta HTTP. *Mitigação*: Feedback claro na interface informando que o pedido está em processamento.
* **Risco de Mensagens Duplicadas em Filas Standard**: Filas SQS Standard garantem entrega *at-least-once*. *Mitigação*: O worker processa os pedidos de forma idempotente usando o `order_id` como chave única.

---

## 04. Conformidade com os Pilares do AWS Well-Architected Framework

* **Excelente Operacional**: Monitoramento integrado via métricas do CloudWatch (`ApproximateNumberOfMessagesVisible`, `FailedInvocations`) e rastreamento de DLQ.
* **Segurança (DevSecOps)**: Permissões IAM de menor privilégio (`grantPutEventsTo`, `grantPublish`, `grantReadWriteData`).
* **Confiabilidade**: Retry automático no SQS, isolamento em DLQ e estorno compensatório (*Saga Rollback*).
* **Eficiência de Performance**: *Long Polling* no SQS e loteamento (*Batching*) na invocação da Lambda.
* **Otimização de Custos (FinOps)**: Desacoplamento que zera o tempo faturado ocioso de instâncias de borda.