# ADR 0008: Containerização do Microsserviço de Recomendação com Amazon ECS, AWS Fargate e Amazon ECR

---

## 1. Contexto e Problema (Context & Problem Statement)

A plataforma e-commerce necessitava de um **Motor de Recomendação Personalizado** capaz de analisar grandes volumes de dados comportamentais de cliques e compras armazenados no **Amazon S3 Data Lake** (gerados via Amazon Data Firehose) e ranquear produtos por similaridade de forma eficiente.

A utilização do modelo tradicional Serverless (AWS Lambda) para processar esses dados sob demanda apresentava limitações de tempo limite de execução (15 minutos), necessidade de inicialização a frio (*Cold Start*) ao carregar bibliotecas densas de inteligência/análise em memória, e restrições de empacotamento.

Para atender aos requisitos de **alta disponibilidade, isolamento de recursos e execução contínua sem cold starts**, decidimos adotar a **containerização** para o Microsserviço de Recomendação.

---

## 2. Opções Consideradas (Considered Options)

1. **Opção 1: AWS Lambda com Imagem de Contêiner (Container Image)**
    - *Prós*: Mantém o modelo orientado a eventos sob demanda.
    - *Contras*: Sujeito a Cold Starts de inicialização e limites de timeout de requisição em borda.

2. **Opção 2: Amazon ECS com Instâncias EC2 Gerenciadas (EC2 Launch Type)**
    - *Prós*: Controle total sobre o sistema operacional subjacente e tipos de instâncias.
    - *Contras*: Sobrecarga operacional para gerenciar o provisionamento, patching e scaling de servidores EC2.

3. **Opção 3: Amazon ECS com AWS Fargate (Serverless Container Launch Type)**
    - *Prós*: Abstração total de servidores (*Serverless Container*), isolamento por tarefa, suporte nativo a Multi-AZ, taxa de bilhetagem por vCPU/Memória alocada, e integração direta com o Application Load Balancer (ALB).
    - *Contras*: Custo contínuo por hora de execução do contêiner.

---

## 3. Decisão de Arquitetura (Decision Outcome)

Decidimos adotar a **Opção 3 (Amazon ECS com AWS Fargate + Application Load Balancer + Amazon ECR)** para orquestrar o microsserviço de recomendação.

### Detalhes da Implementação:
- **Repositório Privado no Amazon ECR (`store-recommendations`)**: Armazena as imagens Docker compiladas do microsserviço com varredura automática de vulnerabilidades (`imageScanOnPush = true`) e política de ciclo de vida FinOps retendo as 10 imagens mais recentes.
- **Orquestração de Contêineres no Amazon ECS (`recommendations-cluster`)**: Cluster Serverless gerenciado pelo AWS Fargate.
- **Serviço Fargate em Alta Disponibilidade Multi-AZ**: Instanciação de 2 tarefas ativas simultâneas (0.25 vCPU e 512 MB de RAM cada) distribuídas entre subnets privadas em duas Zonas de Disponibilidade.
- **Application Load Balancer (ALB)**: Balanceador de carga público roteando tráfego HTTP na porta 80 para os contêineres na porta 8000, com *Health Check* configurado no endpoint `/health`.
- **Descompactação de Data Lake em Tempo Real**: O microsserviço Python/Flask acessa o S3 Data Lake, descompacta os arquivos `.gz` gravados pelo Amazon Data Firehose em memória RAM, computa os pesos de engajamento por categoria do usuário (`product_view = 1.0`, `purchase = 3.0`), executa a busca otimizada no GSI `category-index` do DynamoDB e devolve os Top 5 produtos recomendados por similaridade de conteúdo.

---

## 4. Consequências e Trade-offs (Consequences & Trade-offs)

### Positivas (+):
- **Zero Cold Start**: O serviço responde instantaneamente às chamadas do ALB sem latência de inicialização.
- **Alta Disponibilidade e Resiliência**: Resiliência Multi-AZ garantida com 2 tarefas rodando em subnets privadas distintas.
- **Segurança DevSecOps**: Varredura automática de imagens no ECR e execução sob usuário não-root (`USER appuser`) no Dockerfile (regra `docker:S6471`).
- **Desempenho NoSQL Otimizado**: A consulta no DynamoDB utiliza a chave de partição do GSI `category-index`, reduzindo o consumo de RCUs em ~90%.
- **FinOps & Limpeza de Logs**: Filtro de log customizado no Flask para suprimir chamadas de sucesso do Health Check (`GET /health`), economizando custos de ingestão no CloudWatch.

### Desafios / Mitigações (-):
- **Custo Fixo Mensal**: O Fargate cobra por hora de execução contínua. Para ambientes de desenvolvimento/sandbox, o recurso é gerenciado com destruição/criação via IaC (`cdk destroy`).

---

## 5. Conformidade e Regras SonarQube

- **`docker:S6471`**: Criação do usuário `appuser` sem privilégios de root no Dockerfile.
- **`docker:S6470`**: Evitado o uso de `COPY . .` recursivo no Dockerfile; cópia explícita de `COPY recommendation_service.py .`.
- **`python:S3776`**: Decomposição do leitor do S3 Data Lake em funções utilitárias `_process_log_record` para manter a complexidade cognitiva < 10.
- **`python:S7622`**: Uso do Boto3 Paginator (`s3_client.get_paginator('list_objects_v2')`) para navegação segura de todos os arquivos no S3 Data Lake.