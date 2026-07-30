# ADR 0004: Scaling com Amazon S3 (Presigned URLs & Event Triggers) e ElastiCache (Redis/Valkey Cache-Aside)

## Status
Aprovado

## Contexto
O catálogo de produtos exige o armazenamento de fotos e imagens de alta resolução. O armazenamento binário direto no DynamoDB é inviável devido ao limite de 400 KB por item e custo elevado por WCU/RCU. Além disso, o throughput de leitura em produtos populares e buscas recorrentes por categoria gera gargalos de latência e consumo de capacidade no banco NoSQL.

## Decisão

1. **Amazon S3 para Armazenamento de Mídias**:
    - Utilizar o Amazon S3 para armazenar imagens sob a convenção de chaves `products/{product_id}/{image_type}.jpg`.
    - Implementar o padrão **Presigned URLs** (`put_object` e `get_object`) para permitir que o cliente HTTP faça o upload/download diretamente para o S3, liberando a API Gateway e as Lambdas do tráfego de dados binários (bypassando o limite de 10 MB de payload).
    - Ativar **S3 Event Notifications** para acionar assincronamente a Lambda `ProcessImageMetadataFunction` no evento `s3:ObjectCreated:*` para extração de metadados e associação ao produto no DynamoDB.
    - Implementar regras de ciclo de vida FinOps (*Lifecycle Rules*): **S3 Standard-IA** aos 30 dias, **S3 Glacier** aos 90 dias e exclusão aos **2555 dias (7 anos)**.

2. **Amazon ElastiCache for Redis / Valkey (Engine & Compatibilidade)**:
    - **Decisão de Engine no CDK**: Adotar o **Amazon ElastiCache for Redis** (`cache.t3.micro`) no recurso `AWS::ElastiCache::CacheCluster`.
    - **Justificativa de Infraestrutura**: O projeto mantém a compatibilidade com a iniciativa *open-source* Valkey. Contudo, a especificação da API do AWS CloudFormation restringe a string de engine `"valkey"` apenas a clusters com grupos de replicação (`AWS::ElastiCache::ReplicationGroup`). Para mantermos a simplicidade e o custo otimizado de um nó único (`cache.t3.micro`), definimos a engine como `"redis"` na declaração do CDK.
    - **Compatibilidade de Runtime**: Como o Valkey é um substituto 100% compatível (*drop-in replacement*) com o protocolo do Redis, o cliente `redis-py` utilizado no runtime Python comunica-se de forma idêntica tanto com clusters Valkey quanto Redis na porta `6379`.
    - **Padrão Cache-Aside (Lazy Loading)**: Aplicar o cache na camada de repositório (`ProductsRepository` e `CacheRepository`) com TTLs de 3600s para produtos e 1800s para buscas por categoria.
    - **Invalidação Explícita (*Cache Invalidation*)**: Excluir chaves afetadas durante chamadas de mutação (`save`, `update`, `add_image_to_product`).

3. **Resiliência e Tolerância a Falhas (*Graceful Degradation*)**:
    - Em caso de indisponibilidade, timeout de rede ou exceção `redis.RedisError`, o `CacheRepository` deve tratar a falha de forma transparente, registrando um log no CloudWatch e executando o *fallback* direto para o DynamoDB sem interromper o serviço.

## Consequências

- **Positivas**:
    - Latência de leitura reduzida para submilissegundos (< 7ms) em hits de cache.
    - Custo computacional de banda na API Gateway e AWS Lambda reduzido a zero para transferência de arquivos de imagem.
    - Otimização FinOps com transições automáticas de classes de armazenamento no S3.
    - Desacoplamento total entre upload de mídia e persistência no banco NoSQL.
- **Desafios / Mitigações**:
    - **Isolamento de Rede**: O ElastiCache exige VPC e Security Groups. As Lambdas foram configuradas em subredes privadas com permissões de saída na porta `6379`.
    - **Divergência de Mocks em Testes**: Resolvido com uso de `mock_aws` no Moto v5 e reatribuição da variável de repositório no escopo dos testes unitários para preservar *Warm Starts* em produção.