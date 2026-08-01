# ADR 0005: Padrões Avançados de Lambda - Caching do SSM Parameter Store, Máquina de Estados do Circuit Breaker e Resiliência com Equal Jitter

## Contexto e Declaração do Problema
À medida que a plataforma de e-commerce Serverless se expande, as funções AWS Lambda conectam-se cada vez mais a integrações externas, APIs de terceiros e configurações específicas por ambiente. Confiar puramente em variáveis de ambiente estáticas ou valores hardcoded apresenta três grandes desafios corporativos:

1. **Overhead de Redeploy para Alterações de Configuração**: Modificar limites operacionais (timeouts, limiares de resiliência ou *feature flags*) exige o *redeploy* de stacks do CloudFormation ou do código das Lambdas.
2. **Falhas em Cascata (*Thundering Herd*)**: Quando um serviço externo ou banco de dados sofre uma indisponibilidade, retentar chamadas continuamente a partir de centenas de instâncias concorrentes de Lambdas sobrecarrega a infraestrutura em recuperação e esgota a memória de execução das funções.
3. **Quality Gates de Análise Estática (Conformidade no SonarQube)**: O código Java 21 do CDK deve aderir a regras estritas de análise estática, prevenindo métodos com número excessivo de parâmetros (`java:S107`) e expressões booleanas gratuitas (`java:S2589`).

## Drivers de Decisão
* **Agilidade Operacional**: Modificar configurações em tempo de execução dinamicamente sem necessidade de *redeploy* de código ou infraestrutura.
* **Resiliência e Isolamento de Falhas**: Prevenir falhas em cascata quando dependências externas falharem.
* **Otimização de Custos e Performance**: Eliminar *throttling* de API e latência zerando chamadas repetidas ao cachear parâmetros em memória.
* **DevSecOps e Qualidade de Código**: Manter conformidade sem avisos no SonarQube com segurança de tipos no Java 21.

## Decisões Tomadas

### 1. Configuração Centralizada com AWS Systems Manager (SSM) Parameter Store & Cache TTL em Memória
* **Infraestrutura (Java 21 CDK)**:
    - Declarar parâmetros hierárquicos sob o caminho `/store/{env}/config/` (`api_timeout`, `circuit_breaker_threshold`, `feature_flag_image_processing`).
    - Resolver o prefixo de ambiente dinamicamente via CDK Context (`this.getNode().tryGetContext("environment")`).
    - Conceder permissões IAM de leitura de menor privilégio (`grantRead`) por função.
* **Runtime (Python 3.12)**:
    - Implementar o `SSMParameterManager` em `shared/config_manager.py` com cache local em memória RAM (`ttl_seconds=300`).
    - Implementar *fallback* gracioso para valores padrão caso o SSM esteja inacessível ou retorne um `ClientError`.

### 2. Padrão Circuit Breaker Distribuído (`shared/circuit_breaker.py`)
* Implementar uma máquina de estados com três estados:
    - **CLOSED**: Operação normal. As requisições passam. Falhas consecutivas incrementam um contador.
    - **OPEN**: Disparado quando `failure_count >= failure_threshold` (5). Rejeita chamadas imediatamente (*Fast-Fail*) lançando a exceção `CircuitBreakerOpenError` durante o tempo de recuperação `recovery_timeout` (30 segundos), sem chamar o serviço com falha.
    - **HALF_OPEN**: Entra após a expiração do `recovery_timeout`. Permite chamadas de teste (`success_threshold=2`). Se bem-sucedido, retorna para **CLOSED**; se falhar, reabre para **OPEN**.
* **Mapeamento de Erro na API Gateway**: Mapear `CircuitBreakerOpenError` no `ErrorClassifier` (`shared/error_handler.py`) para retornar uma resposta estruturada de **HTTP 503 Service Unavailable** conforme a **ADR 0003**.

### 3. Backoff Exponencial com Equal Jitter (`shared/resilience.py`)
* Evoluir o decorador de retentativas `@retry_with_backoff` para implementar a fórmula de **Equal Jitter** oficial do AWS Well-Architected Framework:
  $$\text{wait\_time} = \left(\frac{\text{exponential\_delay}}{2}\right) + \text{random.uniform}\left(0, \frac{\text{exponential\_delay}}{2}\right)$$
  garantindo um limite inferior de espera previsível enquanto aleatoriza o limite superior para eliminar tempestades de retentativa.

### 4. Refatoração para Quality Gates do SonarQube (Java 21 CDK)
* **Regra de Contagem de Parâmetros (`java:S107`)**: Encapsular os parâmetros de VPC e Security Group no record do Java 21 `public record LambdaNetworkConfig(Vpc vpc, SecurityGroup securityGroup) {}`, reduzindo a contagem de parâmetros do método auxiliar de 8 para **7**.
* **Regra de Expressão Booleana Gratuitosa (`java:S2589`)**: Substituir checagens manuais de *null* pelo Pattern Matching do Java 21 para `instanceof`:
  `(envObj instanceof String envStr && !envStr.isBlank()) ? envStr : "dev"`.

## Consequências

### Positivas
* **Controle de Funcionalidades Sem Redeploy**: Alterar *feature flags* ou ajustar timeouts no SSM Parameter Store produz efeito imediato em todas as instâncias quentes de Lambdas em até 5 minutos (ou imediatamente no *cold start*).
* **Prevenção de Falhas em Cascata**: A abertura do disjuntor corta a carga sobre APIs de terceiros indisponíveis, protegendo o *core* do backend Serverless.
* **Redução de Custo e Latência**: O cache de parâmetros em memória reduz o custo de chamadas de API do SSM e zera a latência de I/O em execuções *warm*.
* **Conformidade de Código Limpo**: Aprovação total nos *quality gates* do SonarQube utilizando recursos modernos do Java 21.

### Desafios e Mitigações
* **Atraso na Propagação de Parâmetros**: Alterações feitas no SSM Parameter Store levam até 300 segundos (5 minutos) para refletir em containers quentes de Lambdas devido ao cache em memória.
    * *Mitigação*: O parâmetro de TTL pode ser reduzido dinamicamente ou limpo em *cold starts* caso uma propagação imediata seja requerida.