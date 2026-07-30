# ADR 0004: Adição de Amazon S3 (Presigned URLs & Event Triggers) e ElastiCache (Valkey) com Padrão Cache-Aside

## Contexto
O catálogo de produtos exige o armazenamento de fotos e imagens de alta resolução. O armazenamento binário no DynamoDB é inviável devido ao limite de 400 KB por item e custo elevado por WCU/RCU. Além disso, o throughput de leitura em produtos populares e buscas recorrentes por categoria gera gargalos de latência e consumo de throughput no banco NoSQL.

## Decisão
1. **Amazon S3 para Armazenamento de Mídias**:
   - Utilizar o Amazon S3 para armazenar imagens sob a convenção de chaves `products/{product_id}/{image_type}.jpg`.
   - Implementar o padrão **Presigned URLs** (`put_object` e `get_object`) para permitir que o cliente HTTP faça o upload/download diretamente para o S3, liberando a Lambda e a API Gateway do tráfego de dados binários.
   - Ativar **S3 Event Notifications** para acionar assincronamente a Lambda `ProcessImageMetadataFunction` no evento `s3:ObjectCreated:*`.

2. **Amazon ElastiCache (Engine Valkey / Redis)**:
   - Adotar o engine **Valkey** (substituto open-source e de alta performance totalmente compatível com Redis) gerenciado pelo Amazon ElastiCache.
   - Implementar o padrão **Cache-Aside** (Lazy Loading) na camada de repositório Python via biblioteca `redis-py`.
   - Adotar TTLs diferenciados por tipo de dado (3600s para detalhes de produto, 1800s para resultados de busca/categoria).
   - Implementar invalidação explícita de cache (*Cache Invalidation*) nas mutações (`PATCH` / `PUT` / `DELETE`).

3. **Fallback e Tolerância a Falhas**:
   - Em caso de indisponibilidade ou *timeout* do ElastiCache, a aplicação deve falhar de forma transparente (*Graceful Degradation*), buscando os dados diretamente no DynamoDB sem interromper a API.

## Consequências
- **Positivas**:
  - Latência de leitura reduzida para < 5ms em hits de cache.
  - Custo computacional de banda na API Gateway / Lambda reduzido a zero para transferência de arquivos binários.
  - Desacoplamento total entre upload de mídia e atualização de banco de dados.
- **Desafios / Mitigações**:
  - Complexidade de invalidação de cache (mitigada com invalidação direcionada por chave e padrão de chaves estruturado).
  - Necessidade de subredes e VPC no CDK caso o ElastiCache seja implantado em modo gerenciado em nuvem privada (mitigada localmente via emulação Docker/LocalStack/fakeredis).