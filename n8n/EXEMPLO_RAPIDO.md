# Exemplo Rápido: Configuração em 5 Minutos

## 🚀 Início Rápido

Este guia mostra como configurar a integração n8n + Agente Revisor de PRs em apenas 5 minutos.

---

## Passo 1: Conta n8n (1 minuto)

1. Acesse https://n8n.io/
2. Clique em **"Get Started"**
3. Crie uma conta com email ou Google
4. Você terá uma URL como: `https://seu-nome.app.n8n.cloud/`

---

## Passo 2: GitHub Token (1 minuto)

1. Acesse https://github.com/settings/tokens
2. Clique em **"Generate new token (classic)"**
3. Nome: `n8n-agent-reviewer`
4. Escopo: Marque apenas **`repo`**
5. Clique em **"Generate token"**
6. **COPIE O TOKEN** (aparece apenas uma vez!)

---

## Passo 3: Importar Workflow (1 minuto)

1. No n8n, clique em **"New Workflow"**
2. Clique no menu **"..."** → **"Import from File"**
3. Selecione o arquivo `n8n/workflow_pr_review.json`
4. O workflow será importado automaticamente

---

## Passo 4: Configurar Credencial (1 minuto)

1. No workflow, clique no node **"Post Review to GitHub"**
2. Em **"Credential"**, clique em **"Create New"**
3. Selecione **"HTTP Header Auth"**
4. Configure:
   - **Name**: `GitHub Token`
   - **Header Name**: `Authorization`
   - **Header Value**: `Bearer COLE_SEU_TOKEN_AQUI`
5. Clique em **"Save"**
6. Selecione a credencial criada

---

## Passo 5: Ativar Workflow (1 minuto)

1. Clique no botão **"Active"** no canto superior direito
2. Copie a URL do webhook que aparece
3. Pronto! O workflow está rodando

---

## 🎯 Testando a Integração

### Teste 1: Webhook Manual

1. No n8n, vá em **"Executions"** para ver o histórico
2. No GitHub, abra um novo Pull Request
3. Volte ao n8n e veja se o workflow executou

### Teste 2: Via curl

```bash
# Substitua pelos seus dados
curl -X POST https://SEU-N8N.app.n8n.cloud/webhook/github-pr-webhook \
  -H "Content-Type: application/json" \
  -d '{
    "action": "opened",
    "repository": {
      "html_url": "https://github.com/SEU-USUARIO/SEU-REPOSITORIO"
    },
    "pull_request": {
      "number": 1,
      "title": "Meu Primeiro PR",
      "user": {
        "login": "SEU-USUARIO"
      }
    }
  }'
```

---

## 📊 O que Acontece

Quando um PR é aberto:

1. **GitHub** envia evento para o n8n
2. **n8n** filtra e extrai dados do PR
3. **Agente** executa `python main.py <url> --dry-run`
4. **Review** é gerado pela IA
5. **n8n** posta o review no PR
6. **Você** vê o review no GitHub!

---

## ⚠️ Importante

- **Modo Dry-Run**: Por padrão, o agente NÃO posta nada no GitHub (modo seguro)
- **Para postar de verdade**, altere o comando para:
  ```bash
  python main.py {{repo_url}}
  ```
  (remova `--dry-run`)

---

## 🎉 Pronto!

Agora toda vez que alguém abrir um PR no seu repositório, o agente automaticamente:
1. Analisará o código
2. Gerará um review com sugestões
3. Postará o review no PR

---

## 📱 Precisa de Ajuda?

- **Guia Completo**: Veja `n8n/GUIA_COMPLETO.md`
- **Documentação**: Veja `n8n/README.md`
- **Evidências**: Veja `docs/evidencias/fase6_n8n.md`

---

**Tempo total**: ~5 minutos  
**Dificuldade**: Fácil  
**Resultado**: Automação completa de code review! 🚀