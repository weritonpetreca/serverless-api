# Módulo 02 (Fase 0) — Framework de Decisão Computacional na AWS

Avaliação teórica e arquitetural para a tomada de decisão consciente do modelo de computação ideal para hospedar a API do catálogo de produtos do nosso e-commerce.

---

## 01. Problema / Contexto
Ao projetar a arquitetura de uma API de catálogo de e-commerce, a escolha do serviço de computação ideal impacta diretamente o custo financeiro do projeto, a velocidade de entrega da equipe de engenharia e a complexidade de manutenção das operações.

Uma escolha inadequada pode resultar em:
1.  **Custos Ociosos Desnecessários:** Manter instâncias ligadas 24x7 com baixo volume de tráfego, pagando por infraestrutura que não está sendo utilizada.
2.  **Sobrecarga Operacional (Overhead):** Equipes pequenas gastando tempo precioso aplicando patches de segurança no sistema operacional, configurando auto-scaling de máquinas virtuais e gerenciando redes em vez de focar no produto de negócios.
3.  **Incompatibilidade de Limites de Execução:** Escolher plataformas serverless para tarefas de processamento pesado que ultrapassam os limites de timeout da plataforma (como jobs longos de processamento de imagens de produtos).

---

## 02. Objetivo
*   Avaliar as três principais plataformas de computação da AWS: **AWS Lambda (Serverless)**, **Amazon ECS (Containers/Fargate)** e **Amazon EC2 (Máquinas Virtuais)**.
*   Estruturar um framework de decisão arquitetural claro, pesando trade-offs de custo, escalabilidade, limite de execução e complexidade operacional.
*   Selecionar o modelo ideal para hospedar a API de produtos, justificando a escolha com base nas necessidades iniciais do negócio.

---

## 03. Solução (O Framework de Decisão)
Realizamos uma análise comparativa profunda sob as principais dimensões arquiteturais:

### 📊 Tabela de Comparação Técnica

| Critério | AWS Lambda | Amazon ECS (Fargate) | Amazon EC2 |
| :--- | :---: | :---: | :---: |
| **Modelo de Custos** | Pay-per-use (por milissegundo de execução) | Pago por recursos alocados (vCPU/RAM por segundo) | Pago por hora de instância ligada (independente de uso) |
| **Complexidade Operacional** | **Quase Zero** (A AWS gerencia o sistema operacional e escalabilidade) | **Baixa** (Containers sem servidores com Fargate, mas exige design de rede e Docker) | **Alta** (Desenvolvedor gerencia patches de SO, segurança, redes e balanceadores de carga) |
| **Tempo de Startup** | Milissegundos (Sujeito a latência inicial de *Cold Start*) | Segundos / Minutos | Minutos |
| **Limite de Timeout** | Máximo **15 minutos** por execução | Sem limite de tempo de execução | Sem limite de tempo de execução |
| **Escalabilidade** | Instantânea e automática (escala com base em requisições concorrentes) | Automática, mas baseada em regras de escalonamento métrico (CPU/Memória) | Gerenciada via Auto Scaling Groups (métrica de instâncias) |

---

## 04. Justificativa da Escolha para a API de Catálogo
Decidimos utilizar o **AWS Lambda** para o início da operação do e-commerce devido aos seguintes fatores:

1.  **Custo Zero Inicial:** O catálogo possui tráfego imprevisível e baixo no início. Com a precificação baseada em chamadas (pay-per-use) combinada com o AWS Free Tier, o custo operacional inicial será de **$0.00**.
2.  **Operação Simplificada (Zero Server Management):** Sem necessidade de gerenciar atualizações de patches de segurança ou provisionar infraestrutura de servidores, permitindo foco total na evolução rápida de funcionalidades.
3.  **Escalabilidade Integrada:** O Lambda escalará instantaneamente de zero requisições para milhares de requisições por segundo durante eventos sazonais de compras, sem exigir intervenção de DevOps.

---

## 05. Aprendizados & Conclusões
*   **Limites do Serverless:** Embora o Lambda seja ideal para a API de busca de produtos, ele possui um limite estrito de timeout de 15 minutos e um espaço efêmero de armazenamento temporário limitado. Se futuramente precisarmos de processamentos de lote extremamente longos, avaliaremos a migração dessas tarefas específicas para o **Amazon ECS com AWS Fargate**.
*   **Acoplamento de Infraestrutura:** Ao escolher o Lambda, o ideal é manter o código de negócios isolado das especificidades da AWS, facilitando eventuais portabilidades futuras se as necessidades de computação mudarem.