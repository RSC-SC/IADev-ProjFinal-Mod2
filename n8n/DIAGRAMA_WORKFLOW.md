# Diagrama do Workflow n8n

## 📊 Fluxo de Execução

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         AGENTE REVISOR DE PRS                               │
│                              workflow n8n                                   │
└─────────────────────────────────────────────────────────────────────────────┘

┌──────────────────┐
│  GitHub (PR)     │
│  • PR Aberto     │
│  • PR Atualizado │
└────────┬─────────┘
         │
         │ Webhook Event
         ▼
┌──────────────────┐
│  1. GitHub       │
│  Webhook Trigger │
│  ─────────────── │
│  • Recebe POST   │
│  • URL: /webhook │
└────────┬─────────┘
         │
         │ JSON Payload
         ▼
┌──────────────────┐
│  2. Filter PR    │
│  Events          │
│  ─────────────── │
│  • opened ✅     │
│  • synchronize ✅│
│  • other ❌      │
└────────┬─────────┘
         │
         │ Apenas PRs relevantes
         ▼
┌──────────────────┐
│  3. Extract PR   │
│  Data            │
│  ─────────────── │
│  • repo_url      │
│  • pr_number     │
│  • pr_title      │
│  • pr_author     │
└────────┬─────────┘
         │
         │ Dados estruturados
         ▼
┌──────────────────┐
│  4. Execute PR   │
│  Review Agent    │
│  ─────────────── │
│  • python main.py│
│  • <repo_url>    │
│  • --dry-run     │
│  • Timeout: 60s  │
└────────┬─────────┘
         │
         │ stdout/stderr
         ▼
┌──────────────────┐
│  5. Post Review  │
│  to GitHub       │
│  ─────────────── │
│  • POST /reviews │
│  • Body: review  │
│  • Event: COMMENT│
└────────┬─────────┘
         │
         │ HTTP 200 OK
         ▼
┌──────────────────┐
│  6. Success      │
│  Response        │
│  ─────────────── │
│  • status: ok    │
│  • pr_number     │
│  • message       │
└──────────────────┘
```

---

## 🔄 Fluxo de Erro

```
┌──────────────────┐
│  4. Execute PR   │
│  Review Agent    │
│  ─────────────── │
│  • Erro na exec  │
│  • Timeout       │
│  • Python não    │
│    encontrado    │
└────────┬─────────┘
         │
         │ stderr
         ▼
┌──────────────────┐
│  Error Response  │
│  ─────────────── │
│  • status: error │
│  • message: erro │
│  • HTTP 500      │
└──────────────────┘
```

---

## 📋 Nodes Detalhados

### Node 1: GitHub Webhook Trigger

| Propriedade | Valor |
|-------------|-------|
| **Tipo** | `n8n-nodes-base.webhook` |
| **Método** | POST |
| **Path** | `github-pr-webhook` |
| **Response Mode** | `responseNode` |

**Payload Esperado:**
```json
{
  "action": "opened",
  "repository": {
    "html_url": "https://github.com/owner/repo"
  },
  "pull_request": {
    "number": 1,
    "title": "PR Title",
    "user": {
      "login": "username"
    }
  }
}
```

### Node 2: Filter PR Events

| Propriedade | Valor |
|-------------|-------|
| **Tipo** | `n8n-nodes-base.filter` |
| **Condições** | `action == "opened"` OR `action == "synchronize"` |

### Node 3: Extract PR Data

| Propriedade | Valor |
|-------------|-------|
| **Tipo** | `n8n-nodes-base.set` |
| **Campos** | `repo_url`, `pr_number`, `pr_title`, `pr_author`, `action` |

### Node 4: Execute PR Review Agent

| Propriedade | Valor |
|-------------|-------|
| **Tipo** | `n8n-nodes-base.executeCommand` |
| **Comando** | `python main.py {{repo_url}} --dry-run 2>&1` |
| **Timeout** | 60 segundos |

### Node 5: Post Review to GitHub

| Propriedade | Valor |
|-------------|-------|
| **Tipo** | `n8n-nodes-base.httpRequest` |
| **Método** | POST |
| **URL** | `https://api.github.com/repos/{owner}/{repo}/pulls/{pr}/reviews` |
| **Auth** | `Authorization: Bearer {token}` |

**Body:**
```json
{
  "body": "🤖 **Agente Revisor de PRs**\n\n...",
  "event": "COMMENT"
}
```

### Node 6: Success Response

| Propriedade | Valor |
|-------------|-------|
| **Tipo** | `n8n-nodes-base.respondToWebhook` |
| **Response** | JSON com status e mensagem |

---

## 🎨 Visualização no n8n

No editor do n8n, o workflow aparece assim:

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│   GitHub    │───▶│   Filter    │───▶│   Extract   │
│  Webhook    │    │   Events    │    │    Data     │
└─────────────┘    └─────────────┘    └─────────────┘
                                              │
                                              ▼
┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│   Success   │◀───│    Post     │◀───│   Execute   │
│  Response   │    │   Review    │    │    Agent    │
└─────────────┘    └─────────────┘    └─────────────┘
```

---

## 📊 Métricas de Execução

| Métrica | Descrição |
|---------|-----------|
| **Tempo Médio** | 30-60 segundos por PR |
| **Taxa de Sucesso** | >95% (com configuração correta) |
| **PRs por Execução** | 1-3 (configurável) |
| **Logs Gerados** | JSONL + audit JSON |

---

## 🔧 Configurações Padrão

```json
{
  "max_prs": 3,
  "dry_run": true,
  "timeout": 60,
  "retry": 3
}
```

---

## 🎯 Exemplo Real

### Input (GitHub Webhook)
```json
{
  "action": "opened",
  "repository": {
    "html_url": "https://github.com/RSC-SC/IADev-ProjFinal-Mod2"
  },
  "pull_request": {
    "number": 21,
    "title": "Fase 6 - Automação n8n",
    "user": {
      "login": "RSC-SC"
    }
  }
}
```

### Output (n8n Response)
```json
{
  "status": "success",
  "run_id": "abc123",
  "execution_time": 45.2,
  "repo_url": "https://github.com/RSC-SC/IADev-ProjFinal-Mod2",
  "dry_run": true,
  "processed_prs": 1,
  "final_message": "✅ Review concluído com sucesso!",
  "pr_number": 21,
  "pr_title": "Fase 6 - Automação n8n",
  "pr_author": "RSC-SC"
}
```

---

**Versão**: 1.0.0  
**Data**: 25/08/2026