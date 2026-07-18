# ADR 0003: Estratégia de Tratamento de Erros, Resiliência de Dados e Garantia de Qualidade (QA)

## 1. Contexto e Problema
Até o momento (Módulo 4), a API de catálogo de produtos é capaz de receber dados, validá-los via Pydantic e persisti-los no Amazon DynamoDB. No entanto, o sistema opera sob a premissa do "caminho feliz" (happy path). Em um cenário real de produção de escala corporativa, a falta de resiliência e o tratamento inadequado de falhas geram impactos severos:

* Vazamento de Detalhes Internos ou Erros Genéricos: Exceções não capturadas resultam em respostas HTTP 500 Internal Server Error brutas ou expõem stack traces internos para o cliente final, violando regras básicas de segurança cibernética.


* Efeito Manada (Thundering Herd) no Banco de Dados: Quando o DynamoDB sofre degradação ou limitação de taxa (throttling), retentativas imediatas e simultâneas disparadas por múltiplas instâncias concorrentes de funções Lambda estressam ainda mais o serviço, impedindo sua recuperação.


* Perda de Operações Assíncronas: Falhas em execuções assíncronas (como atualizações de inventário) desaparecem sem deixar rastros se a função falhar após as retentativas nativas, impossibilitando auditorias ou reprocessamentos manuais.


* Falta de Confiança no Deploy (Ausência de QA): Alterações no código de negócio ou na configuração de tabelas são validadas manualmente, aumentando o risco de regressões em produção.

## 2. Decisões Técnicas
Para mitigar esses riscos e alinhar a API com os padrões de produção exigidos pelo AWS Developer Learning Plan, adotamos o seguinte conjunto de decisões:

### 2.1. Contrato de Erro Padronizado (Camada Síncrona)
Fica determinado que nenhuma exceção crua sairá das funções Lambda síncronas (integradas ao API Gateway). Todas as falhas capturadas serão traduzidas em um contrato JSON estrito, previsível e semanticamente correto:

```JSON
{
  "error": {
    "type": "string",
    "message": "string",
    "timestamp": "string (ISO-8601 UTC)",
    "request_id": "string (AWS Request ID)",
    "details": {},
    "suggestions": []
  }
}
```

### 2.2. Classificação Centralizada de Exceções (`ErrorClassifier`)
O código computacional em Python implementará um componente desacoplado de domínio encarregado de mapear exceções em seus respectivos códigos de status HTTP correspondentes, separando erros de cliente (não retentáveis) de erros de infraestrutura (retentáveis):

* ValidationError (Pydantic v2) ➔ HTTP 400 (Bad Request). Não retentável.
* ProductNotFoundError ➔ HTTP 404 (Not Found). Não retentável.
* DatabaseTimeoutException / ProvisionedThroughputExceededException ➔ HTTP 503 (Service Unavailable) ou HTTP 429 (Too Many Requests). Retentável.

### 2.3. Algoritmo de Resiliência: Exponential Backoff com Jitter
Toda operação que realize chamadas de rede para o Amazon DynamoDB ou APIs de terceiros que apresente falha transitória (erros de timeout ou limite de taxa) deverá ser interceptada por um decorador de retentativa inteligente.

* O tempo de espera entre as retentativas crescerá exponencialmente ($base\_delay \times 2^{attempt}$).
* Será adicionado um Jitter (fator de variação aleatória de até 10% sobre o tempo calculado) para quebrar o sincronismo de retentativas concorrentes, neutralizando o efeito manada.

### 2.4. Proteção de Infraestrutura: Circuit Breaker Pattern
Para chamadas a serviços downstream instáveis (como APIs de pagamento ou fornecedores externos), será implementado um mecanismo de Circuit Breaker com três estados:

* CLOSED: Operação normal. Falhas são contabilizadas.
* OPEN: O limite de falhas consecutivas foi atingido. Chamadas externas são bloqueadas imediatamente por um tempo determinado (recovery_timeout), retornando uma resposta de degradação graciosa (dados em cache ou fila de contingência) sem sobrecarregar o parceiro.
* HALF-OPEN: O tempo de recuperação expirou. O sistema permite um número limitado de chamadas de teste para verificar se o serviço downstream se estabilizou.

### 2.5. Resiliência Assíncrona na Infraestrutura (AWS CDK + Java 21)
O provisionamento da infraestrutura como código (IaC) via CDK configurará os mecanismos de segurança nativos da nuvem:

* Dead-Letter Queue (DLQ): Uma fila Amazon SQS isolada será acoplada às funções Lambda assíncronas.
* Lambda Destinations: Configuração de políticas de destino direcionando eventos com falha terminal (OnFailure) para a DLQ após esgotadas as 2 retentativas nativas da AWS.

### 2.6. Estratégia de Cobertura de Testes Significativos (>80%)
A validação de qualidade será automatizada e integrada localmente para garantir o paradigma Shift-Left:

* Testes Unitários da Infraestrutura (Java 21 + JUnit 5): Asserções rígidas garantindo que os Handlers da Lambda possuem as DLQs configuradas antes de sintetizar o template do CloudFormation.
* Testes Unitários da Computação (Python 3.12 + Pytest + Moto): Criação de cenários de testes reais simulando falhas de conexão de rede, timeouts induzidos e payloads corrompidos usando fábricas de eventos do API Gateway (APIGatewayEventFactory), eliminando testes superficiais.

## 3. Consequências
### * Pontos Positivos (Benefícios):
  * Alta Disponibilidade: O sistema auto-regenera falhas intermitentes de rede através do Backoff com Jitter.
  * Zero Perda de Dados: Falhas catastróficas assíncronas são retidas na DLQ por até 14 dias para análise forense e reprocessamento.
  * Excelente DX e UX: Clientes recebem sugestões claras de correção de payloads, enquanto engenheiros ganham rastreabilidade total via request_id unificado no CloudWatch Logs.
  * Segurança de Código: Cobertura de testes abrangente barra regressões funcionais antes de alcançar as esteiras de CI/CD.

### * Pontos Negativos (Trade-offs):
  * Complexidade de Código: Introdução de decoradores e gerenciadores de estado (Circuit Breaker) aumentam ligeiramente a base de código do projeto.
  * Gerenciamento de Infraestrutura: Requer monitoramento extra sobre o volume de mensagens mortas estacionadas na DLQ (Alertas de FinOps/Operações).