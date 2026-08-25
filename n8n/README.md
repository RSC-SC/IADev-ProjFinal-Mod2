# Integração n8n - Agente Revisor de PRs

## Visão Geral

Este diretório contém o workflow n8n para integrar o Agente Revisor de PRs com automação low-code.

## Workflow

O workflow `workflow_pr_review.json` implementa:

1. **GitHub Webhook Trigger** - Recebe eventos de PR (opened/synchronize)
2. **Filter PR Events** - Filtra apenas eventos relevantes
3. **Extract PR Data** - Extrai dados do PR (repo, número, título, autor)
4. **Execute PR Review Agent** - Executa o agente via CLI
5. **Post Review to GitHub** - Posta o review no PR
6. **Success/Error Response** - Retorna status da execução

## Configuração

### Pré-requisitos

1. **n8n Instance** - Cloud ou self-hosted
2. **GitHub Token** - PAT com escopo `repo`
3. **Python 3.10+** - Com dependências instaladas
4. **Variáveis de Ambiente** - Configuradas no `.env`

### Importar Workflow

1. Abra o n8n
2. Vá em **Workflows > Import from File**
3. Selecione `workflow_pr_review.json`
4. Configure as credenciais

### Configurar Credenciais

#### GitHub Token (HTTP Header Auth)

1. No n8n, vá em **Credentials > Add Credential**
2. Selecione **HTTP Header Auth**
3. Configure:
   - **Name**: `GitHub Token`
   - **Header Name**: `Authorization`
   - **Header Value**: `Bearer SEU_GITHUB_TOKEN`

### Configurar Webhook

1. Após importar o workflow, copie a URL do webhook
2. No GitHub, vá em **Settings > Webhooks > Add webhook**
3. Configure:
   - **Payload URL**: URL do webhook n8n
   - **Content type**: `application/json`
   - **Events**: Selecione **Pull requests**
   - **Active**: ✅

## Uso

### Execução Automática

Quando um PR for aberto ou atualizado:
1. GitHub envia evento para o webhook n8n
2. Workflow filtra eventos de PR
3. Executa o agente com `--dry-run`
4. Posta review no PR
5. Retorna status de sucesso

### Execução Manual

Para testar manualmente:
1. No n8n, clique em **Execute Workflow**
2. Envie um POST para o webhook:
   ```bash
   curl -X POST https://seu-n8n.com/webhook/github-pr-webhook \
     -H "Content-Type: application/json" \
     -d '{
       "action": "opened",
       "repository": {
         "html_url": "https://github.com/owner/repo"
       },
       "pull_request": {
         "number": 1,
         "title": "Test PR",
         "user": {
           "login": "testuser"
         }
       }
     }'
   ```

## Estrutura do Workflow

```
GitHub Webhook Trigger
    ↓
Filter PR Events (opened/synchronize)
    ↓
Extract PR Data (repo_url, pr_number, etc.)
    ↓
Execute PR Review Agent (python main.py <url> --dry-run)
    ↓
Post Review to GitHub (POST /repos/{owner}/{repo}/pulls/{pr}/reviews)
    ↓
Success Response (JSON)
```

## Logs e Observabilidade

O workflow gera logs em:
- **n8n Execution Log** - Histórico de execuções
- **Agent Logs** - `logs/` do agente (JSONL + audit JSON)
- **GitHub PR Review** - Review postado no PR

## Solução de Problemas

### Webhook não dispara
- Verifique se o webhook está ativo no GitHub
- Confirme a URL do webhook no n8n
- Verifique se o evento `pull_request` está habilitado

### Agente não executa
- Verifique se o Python está no PATH
- Confirme as dependências instaladas (`requirements.txt`)
- Verifique as variáveis de ambiente (`.env`)

### Review não posta
- Verifique o escopo do GitHub Token (`repo`)
- Confirme a URL da API no workflow
- Verifique os logs do n8n para erros

## Segurança

- **Variáveis Sensíveis**: Use as credenciais do n8n para tokens
- **Webhook Secret**: Configure um secret no GitHub e valide no n8n
- **Rate Limits**: O workflow respeita os rate limits do GitHub
- **Dry-run**: Por padrão, executa em modo seguro (sem postar)

## Personalização

### Modificar Comportamento

1. **Filtrar Repositórios**: Adicione condição no node "Filter PR Events"
2. **Mudar Comando**: Altere o comando no node "Execute PR Review Agent"
3. **Personalizar Review**: Modifique o template no node "Post Review to GitHub"
4. **Adicionar Notificações**: Inclua nodes de email/Slack após o review

### Adicionar Notificação Slack

1. Adicione um node **Slack** após "Post Review to GitHub"
2. Configure as credenciais do Slack
3. Envie mensagem com status do review

## 📚 Documentação Adicional

| Documento | Descrição |
|-----------|-----------|
| [GUIA_COMPLETO.md](GUIA_COMPLETO.md) | Guia detalhado de configuração e uso |
| [EXEMPLO_RAPIDO.md](EXEMPLO_RAPIDO.md) | Configuração em 5 minutos |
| [DIAGRAMA_WORKFLOW.md](DIAGRAMA_WORKFLOW.md) | Diagrama visual do workflow |
| [configurar.ps1](configurar.ps1) | Script de configuração automática |

## 🚀 Início Rápido

```bash
# 1. Configurar ambiente
.\configurar.ps1

# 2. Iniciar servidor (opcional)
.\configurar.ps1 -Server

# 3. Testar integração
.\configurar.ps1 -Test
```

## Referências

- [n8n Documentation](https://docs.n8n.io/)
- [GitHub Webhooks](https://docs.github.com/en/webhooks)
- [GitHub Pull Reviews API](https://docs.github.com/en/rest/pulls/reviews)
- [Agente Revisor de PRs - README](../README.md)