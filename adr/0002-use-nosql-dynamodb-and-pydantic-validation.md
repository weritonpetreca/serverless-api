# ADR 0002: Adoção do Amazon DynamoDB e Validação com Pydantic v2

## Contexto
O projeto `serverless-api` necessita de uma camada de persistência de dados persistente, resiliente e de baixíssimo tempo de resposta para substituir os mocks em memória utilizados nas fases anteriores. Além disso, por se tratar de uma API pública exposta via API Gateway, é imperativo blindar a aplicação contra injeção de payloads maliciosos, dados inconsistentes (como preços negativos ou nulos) e garantir o alinhamento com práticas de Segurança Shift-Left na camada de computação serverless (AWS Lambda).

## Decisão
Decidimos adotar o **Amazon DynamoDB** como banco de dados NoSQL e a biblioteca **Pydantic v2** para validação estrita de esquemas em tempo de execução no Python.

1. **Amazon DynamoDB:**
    - Adotado o modelo de provisionamento sob demanda (`PAY_PER_REQUEST`) para garantir escalabilidade horizontal automática e custo zero em repouso (FinOps).
    - Definição de chave de partição simples (`id` como UUIDv4).
    - Criação de um Global Secondary Index (GSI) chamado `category-index` (com partição no atributo `category`) para viabilizar consultas otimizadas sem a necessidade de operações custosas de `Scan`.

2. **Validação com Pydantic v2:**
    - Toda entrada de dados nos endpoints de mutação (`POST /products` e `PATCH /products/{id}`) é interceptada e validada por esquemas declarativos rígidos do Pydantic antes de atingir a lógica do banco de dados.
    - Tratamento de exceções centralizado para retornar respostas amigáveis de erro (`HTTP 400 Bad Request`) em caso de violação de contrato.

3. **Arquitetura de Testes Locais e Deploy Efêmero (LocalStack):**
    - Para contornar a limitação de montagem física de Lambda Layers no LocalStack Community Edition (versão gratuita), adotou-se o padrão de empacotamento *Fat Lambda* local isolado via pasta `vendor/` e injeção da variável de ambiente `PYTHONPATH` (`/var/task:/var/task/vendor`) na stack do CDK.
    - O diretório `lambda_code/vendor/` é estritamente ignorado no `.gitignore` raiz do projeto para manter o repositório livre de dependências de terceiros de forma limpa.

## Consequências e Trade-offs

### Prós:
* **Escalabilidade Infinita e Custo Baixo:** O DynamoDB escala instantaneamente para lidar com picos de tráfego sem intervenção manual e sem custos operacionais de servidor dedicado.
* **Segurança na Borda (Shift-Left):** O payload é validado e rejeitado na entrada da Lambda. Dados corrompidos ou maliciosos nunca chegam a consumir capacidade de escrita do DynamoDB.
* **Isolamento e DX Limpa:** O uso da pasta `vendor/` com `PYTHONPATH` garantiu o funcionamento do LocalStack localmente sem poluir o workspace do desenvolvedor ou rastrear dependências do Python no Git.

### Contras:
* **Desserialização de Tipos Decimal:** O SDK `boto3` retorna valores numéricos do DynamoDB como o tipo `Decimal` do Python. Foi necessária a criação de um serializador JSON personalizado na camada de utilitários (`response_utils.py`) para evitar falhas de tipagem ao responder ao cliente HTTP.
* **Modelagem NoSQL Rígida:** Diferente do modelo relacional, alterações futuras em padrões de busca complexos exigem o planejamento prévio e provisionamento de novos índices (GSIs).