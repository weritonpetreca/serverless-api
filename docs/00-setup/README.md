# Módulo 01 (Fase 0) — Configuração de Ambiente & Fundações AWS

Análise de conceitos fundamentais estabelecidos para preparar o ambiente de desenvolvimento local para a construção de sistemas produtivos na nuvem AWS.

---

## 01. Problema / Contexto
A configuração inadequada de credenciais e ambientes locais de desenvolvimento é uma das principais brechas de segurança em projetos de nuvem. O uso de credenciais estáticas de longa duração (como chaves de acesso do IAM gravadas diretamente em arquivos de configuração locais `~/.aws/credentials`) expõe a infraestrutura corporativa a sérios riscos de vazamento e roubo de credenciais.

Além disso, a falta de padronização nas ferramentas locais (CLI, SDK e IDE) dificulta a colaboração entre equipes e gera o clássico problema do *"funciona na minha máquina, mas quebra na esteira"*.

---

## 02. Objetivo
*   Estabelecer uma infraestrutura de credenciais segura, rotativa e baseada em privilégios temporários utilizando o **AWS IAM Identity Center (antigo AWS SSO)**.
*   Configurar e validar as ferramentas fundamentais de controle e integração localmente: **AWS CLI**, **AWS SDK** e ambiente integrado de desenvolvimento (IDE).
*   Garantir conformidade com as diretrizes recomendadas de segurança do AWS Well-Architected Framework desde o primeiro dia de projeto.

---

## 03. Solução
A fundação do projeto foi estabelecida com os seguintes pilares de infraestrutura local:

1.  **Autenticação via AWS IAM Identity Center (SSO):**
    *   Substituição de chaves estáticas (`Access Key` / `Secret Key`) por logins rotativos de curta duração.
    *   Configuração do comando `aws sso login` integrado ao navegador para geração de credenciais temporárias renováveis automaticamente.
2.  **Configuração de Perfis do AWS CLI:**
    *   Criação de perfis nomeados (*named profiles*) organizados por ambiente no arquivo `~/.aws/config`, separando de forma explícita ambientes de desenvolvimento, homologação e produção.
3.  **Padronização do SDK e IDE:**
    *   Configuração das extensões locais (como AWS Toolkit no IntelliJ IDEA) mapeadas aos perfis do SSO local para depuração em tempo real.
    *   Validação de chamada de identidade inicial via comando de controle de sessão do Security Token Service (STS).

---

## 04. Ferramentas
*   **AWS IAM Identity Center:** Gerenciamento centralizado de SSO e credenciais rotativas.
*   **AWS CLI v2:** Interface de linha de comando oficial da AWS.
*   **AWS SDK (Java):** Biblioteca de integração integrada ao ciclo de vida do projeto Gradle.
*   **AWS STS:** Serviço de Token de Segurança para validação de sessões temporárias.

---

## 05. Resultado
O ambiente de desenvolvimento local foi estabelecido de forma blindada contra vazamentos de segurança e pronto para receber deploys de IaC.

*   **Validação de Credenciais Ativas:**
    O comando de segurança de token foi executado localmente confirmando a autenticação via SSO sem a necessidade de expor chaves estáticas no sistema de arquivos:
    ```bash
    aws sts get-caller-identity
    ```
    *Retorno esperado:* Exibição do ID da conta AWS de sandbox, identificando o perfil SSO dinâmico ativo de forma segura.

---

## 06. Aprendizados & Troubleshooting
*   **Gerenciamento de Sessão Expirada:** Sessões temporárias expiram automaticamente após o tempo limite definido pelo administrador (geralmente entre 1 e 12 horas). O erro comum `Token expired` é resolvido de forma imediata rodando `aws sso login` sem a necessidade de reconfigurar perfis manualmente.
*   **Isolamento de Contas:** O uso de Perfis Nomeados impede deploys acidentais em contas de produção. Executar `cdk deploy --profile dev` garante que a stack seja enviada estritamente ao ambiente correto de testes.