# Guia Completo: Integração n8n com Agente Revisor de PRs

## 📋 Índice

1. [Visão Geral](#visão-geral)
2. [Pré-requisitos](#pré-requisitos)
3. [Configuração do n8n](#configuração-do-n8n)
4. [Importação do Workflow](#importação-do-workflow)
5. [Configuração de Credenciais](#configuração-de-credenciais)
6. [Configuração do Webhook no GitHub](#configuração-do-webhook-no-github)
7. [Teste da Integração](#teste-da-integração)
8. [Exemplos Práticos](#exemplos-práticos)
9. [Personalização](#personalização)
10. [Solução de Problemas](#solução-de-problemas)

---

## Visão Geral

### O que é esta integração?

Esta integração permite que o **Agente Revisor de PRs** seja executado automaticamente sempre que um Pull Request for aberto ou atualizado no GitHub, utilizando a plataforma de automação **n8n**.

### Fluxo de Execução

```
GitHub (PR Event) → n8n Webhook → Execute Agent → Post Review → Notification
```

### Benefícios

- **Automação Total**: Não precisa executar o agente manualmente
- **Tempo Real**: Review em minutos após abertura do PR
- **Observabilidade**: Logs completos no n8n e no agente
- **Flexível**: Pode ser personalizado conforme necessidade

---

## Pré-requisitos

### 1. Conta n8n

**Opção A: n8n Cloud (Recomendado para iniciantes)**
- Acesse: https://n8n.io/
- Crie uma conta gratuita
- Vantagem: Sem necessidade de configurar servidor

**Opção B: n8n Self-Hosted (Para usuários avançados)**
- Instale via Docker: `docker run -it --rm --name n8n -p 5678:5678 -v ~/.n8n:/home/node/.n8n n8nio/n8n`
- Vantagem: Controle total, dados locais

### 2. GitHub Token

1. Acesse: https://github.com/settings/tokens
2. Clique em **"Generate new token (classic)"**
3. Selecione escopo: **`repo`** (controle total de repositórios)
4. Copie o token gerado (será mostrado apenas uma vez)

### 3. Python 3.10+

Verifique sua versão:
```bash
python --version
# Deve mostrar 3.10 ou superior
```

### 4. Dependências Instaladas

No diretório do projeto:
```bash
pip install -r requirements.txt
```

---

## Configuração do n8n

### Opção A: n8n Cloud

1. Acesse https://app.n8n.cloud/
2. Faça login na sua conta
3. Clique em **"New Workflow"**
4. Nomeie: **"Agente Revisor de PRs"**

### Opção B: n8n Self-Hosted

1. Inicie o n8n:
   ```bash
   docker run -it --rm \
     --name n8n \
     -p 5678:5678 \
     -v ~/.n8n:/home/node/.n8n \
     -e N8N_BASIC_AUTH_ACTIVE=true \
     -e N8N_BASIC_AUTH_USER=admin \
     -e N8N_BASIC_AUTH_PASSWORD=suasenha \
     n8nio/n8n
   ```

2. Acesse: http://localhost:5678
3. Clique em **"New Workflow"**
4. Nomeie: **"Agente Revisor de PRs"**

---

## Importação do Workflow

### Passo 1: Baixar o Workflow

O arquivo do workflow está em: `n8n/workflow_pr_review.json`

### Passo 2: Importar no n8n

1. No n8n, clique no menu **"..."** (três pontos) no canto superior direito
2. Selecione **"Import from File"**
3. Selecione o arquivo `workflow_pr_review.json`
4. Clique em **"Import"**

### Passo 3: Verificar a Estrutura

Após importar, você verá os seguintes nodes:

```
GitHub Webhook Trigger → Filter PR Events → Extract PR Data → Execute PR Review Agent → Post Review to GitHub → Success Response
```

---

## Configuração de Credenciais

### Credencial 1: GitHub Token

1. No n8n, vá em **"Credentials"** no menu lateral
2. Clique em **"Add Credential"**
3. Busque por **"HTTP Header Auth"**
4. Configure:
   - **Name**: `GitHub Token`
   - **Header Name**: `Authorization`
   - **Header Value**: `Bearer SEU_GITHUB_TOKEN_AQUI`
5. Clique em **"Save"**

### Credencial 2: Webhook URL (Opcional)

Se quiser usar webhook secret (recomendado para produção):

1. No n8n, vá em **"Credentials"**
2. Adicione **"GitHub API"**
3. Configure com seu token

---

## Configuração do Webhook no GitHub

### Passo 1: Copiar URL do Webhook

1. No workflow importado, clique no node **"GitHub Webhook Trigger"**
2. Copie a URL que aparece (ex: `https://seu-n8n.com/webhook/github-pr-webhook`)
3. **Importante**: Esta URL será usada no GitHub

### Passo 2: Configurar Webhook no GitHub

1. Acesse seu repositório no GitHub
2. Vá em **Settings → Webhooks → Add webhook**
3. Configure:
   - **Payload URL**: Cole a URL copiada do n8n
   - **Content type**: `application/json`
   - **Secret**: (Opcional) Gere um secret para segurança
   - **Events**: Selecione **"Pull requests"**
   - **Active**: ✅ Marque como ativo
4. Clique em **"Add webhook"**

### Passo 3: Testar o Webhook

1. No n8n, clique em **"Execute Workflow"**
2. No GitHub, abra um novo Pull Request
3. Volte ao n8n e verifique se o workflow foi executado

---

## Teste da Integração

### Teste 1: Health Check

```bash
# Se estiver usando o agent_adapter.py em modo servidor
curl http://localhost:8080/health

# Resposta esperada:
{
  "status": "healthy",
  "service": "agente-revisor-prs",
  "version": "1.0.0"
}
```

### Teste 2: Simulação de Webhook

```bash
curl -X POST http://localhost:8080/webhook \
  -H "Content-Type: application/json" \
  -d '{
    "action": "opened",
    "repository": {
      "html_url": "https://github.com/seu-usuario/seu-repositorio"
    },
    "pull_request": {
      "number": 1,
      "title": "Test PR",
      "user": {
        "login": "seu-usuario"
      }
    }
  }'
```

### Teste 3: Execução via n8n

1. No n8n, clique em **"Execute Workflow"**
2. Verifique os logs de cada node
3. Confirme que o review foi postado no PR

---

## Exemplos Práticos

### Exemplo 1: Configuração Básica

**Cenário**: Você quer que o agente execute automaticamente quando um PR for aberto.

**Configuração**:
1. Importe o workflow
2. Configure o GitHub Token
3. Configure o webhook no GitHub
4. Teste abrindo um PR

**Resultado**: O agente executará automaticamente e postará o review no PR.

### Exemplo 2: Modo Dry-Run (Seguro)

**Cenário**: Você quer testar sem postar reviews no GitHub.

**Configuração**:
1. No node **"Execute PR Review Agent"**, altere o comando:
   ```bash
   python main.py {{repo_url}} --dry-run
   ```
2. Execute o workflow
3. Verifique os logs no n8n

**Resultado**: O agente executa, mas não posta nada no GitHub.

### Exemplo 3: Múltiplos Repositórios

**Cenário**: Você quer monitorar vários repositórios.

**Configuração**:
1. Configure webhooks em cada repositório
2. Aponte todos para a mesma URL do n8n
3. O workflow processará todos os eventos

**Resultado**: Um único workflow monitora múltiplos repositórios.

### Exemplo 4: Notificação por Email

**Cenário**: Você quer receber um email quando o review for concluído.

**Configuração**:
1. Adicione um node **"Send Email"** após **"Post Review to GitHub"**
2. Configure as credenciais de email
3. Personalize a mensagem

**Resultado**: Você recebe um email a cada review concluído.

---

## Personalização

### 1. Filtrar Repositórios

Para processar apenas repositórios específicos:

1. No node **"Filter PR Events"**, adicione uma condição:
   ```json
   {
     "conditions": {
       "string": [
         {
           "value1": "={{ $json.body.repository.full_name }}",
           "operation": "equals",
           "value2": "seu-usuario/seu-repositorio"
         }
       ]
     }
   }
   ```

### 2. Alterar Comando do Agente

Para usar parâmetros diferentes:

1. No node **"Execute PR Review Agent"**, altere:
   ```bash
   python main.py {{repo_url}} --max-prs 5
   ```

### 3. Adicionar Notificação Slack

1. Adicione um node **"Slack"** após **"Post Review to GitHub"**
2. Configure as credenciais do Slack
3. Envie mensagem:
   ```json
   {
     "channel": "#code-reviews",
     "text": "Review concluído para PR #{{pr_number}}: {{pr_title}}"
   }
   ```

### 4. Logging Personalizado

Para enviar logs para um serviço externo:

1. Adicione um node **"HTTP Request"** após **"Post Review to GitHub"**
2. Configure para enviar dados para seu serviço de logging

---

## Solução de Problemas

### Problema 1: Webhook não dispara

**Sintomas**: O workflow não inicia quando um PR é aberto.

**Soluções**:
1. Verifique se o webhook está ativo no GitHub
2. Confirme a URL do webhook no n8n
3. Verifique se o evento `pull_request` está habilitado
4. Teste o webhook manualmente:
   ```bash
   curl -X POST https://seu-n8n.com/webhook/github-pr-webhook \
     -H "Content-Type: application/json" \
     -d '{"test": true}'
   ```

### Problema 2: Agente não executa

**Sintomas**: O node "Execute PR Review Agent" falha.

**Soluções**:
1. Verifique se o Python está no PATH
2. Confirme as dependências instaladas:
   ```bash
   pip install -r requirements.txt
   ```
3. Verifique as variáveis de ambiente (`.env`)
4. Teste o agente manualmente:
   ```bash
   python main.py https://github.com/seu-usuario/seu-repositorio --dry-run
   ```

### Problema 3: Review não posta

**Sintomas**: O agente executa, mas o review não aparece no PR.

**Soluções**:
1. Verifique o escopo do GitHub Token (`repo`)
2. Confirme a URL da API no workflow
3. Verifique os logs do n8n para erros
4. Teste a API do GitHub manualmente:
   ```bash
   curl -X POST https://api.github.com/repos/seu-usuario/seu-repositorio/pulls/1/reviews \
     -H "Authorization: Bearer SEU_TOKEN" \
     -H "Content-Type: application/json" \
     -d '{"body": "Teste", "event": "COMMENT"}'
   ```

### Problema 4: Timeout na execução

**Sintomas**: O workflow falha por timeout.

**Soluções**:
1. Reduza o número de PRs: `--max-prs 1`
2. Use `--dry-run` para testes
3. Verifique a conexão com a internet
4. Aumente o timeout no n8n (node settings)

### Problema 5: Erros de autenticação

**Sintomas**: Erro 401 ou 403 na execução.

**Soluções**:
1. Verifique se o token está correto
2. Confirme o escopo do token (`repo`)
3. Gere um novo token se necessário
4. Verifique se o token não expirou

---

## Dicas Avançadas

### 1. Usar Webhook Secret

Para mayor segurança:

1. Gere um secret no GitHub
2. No n8n, valide o secret no node **"GitHub Webhook Trigger"**
3. Use HMAC para validação

### 2. Rate Limiting

O GitHub tem limites de taxa:
- 5,000 requisições por hora (autenticado)
- O agente respeita esses limites
- Monitore os logs para identificar problemas

### 3. Logs e Monitoramento

- **n8n**: Histórico de execuções no painel
- **Agente**: Logs em `logs/` (JSONL + audit JSON)
- **GitHub**: Reviews visíveis nos PRs

### 4. Backup e Recuperação

- Exporte workflows regularmente
- Mantenha cópias das credenciais
- Documente as configurações

---

## Referências

- [n8n Documentation](https://docs.n8n.io/)
- [GitHub Webhooks](https://docs.github.com/en/webhooks)
- [GitHub Pull Reviews API](https://docs.github.com/en/rest/pulls/reviews)
- [Agente Revisor de PRs - README](../README.md)

---

**Versão**: 1.0.0  
**Data**: 25/08/2026  
**Autor**: Agente Orquestrador AI