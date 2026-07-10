# Prompts Utilizados no Projeto

Este arquivo registra os principais prompts utilizados durante o planejamento, implementação e melhoria do agente.

---

## 1. Prompt de Sistema do Agente Revisor

**Arquivo:** `src/nodes/code_analyzer.py`

**Finalidade:** Prompt de sistema enviado ao Gemini para orientar a análise de código durante a execução do agente.

```
You are a senior code reviewer focused on best practices and readability.

Analyze the provided code diff and generate a structured review in Markdown with exactly two sections:

## Pontos Positivos
- List specific things the code does well

## Oportunidades de Melhoria
- List specific suggestions with line references when possible

Focus on: code readability, best practices, potential bugs, security concerns, and maintainability.
Be constructive and specific. Always reference file names and line numbers from the diff.
```

---

## 2. Prompt de Planejamento do Projeto

**Finalidade:** Prompt utilizado para definir o escopo e a arquitetura do agente com o usuário.

```
Definir um agente LangGraph para automatizar a revisão de Pull Requests no GitHub.

Requisitos:
- Entrada: URL do repositório GitHub
- O agente deve listar todos os PRs abertos
- Para cada PR: baixar o diff, analisar com LLM, postar comentário
- Foco em boas práticas e legibilidade
- Saída estruturada em Markdown (Pontos Positivos / Oportunidades de Melhoria)
- Projeto individual
```

---

## 3. Prompt de Decisão Técnica — Stack

**Finalidade:** Prompt para escolha do provedor de LLM e biblioteca de integração com GitHub.

```
Qual provedor de LLM usar para análise de código?
- OpenAI (GPT-4o-mini)
- Anthropic (Claude 3.5 Sonnet)
- Google (Gemini 2.0 Flash)
- Ollama (modelo local)

Biblioteca para API do GitHub:
- PyGithub (abstração oficial, mais segura)
- requests (chamadas diretas)

Decisão: Gemini 2.0 Flash + PyGithub
```

---

---

## 5. Prompt de Decisão Técnica — Provedor OpenRouter

**Finalidade:** Integração com OpenRouter como alternativa ao Gemini.

```
Adicionar suporte a múltiplos provedores de LLM com fallback:

1. Se GOOGLE_API_KEY estiver preenchida → Gemini 2.0 Flash
2. Se OPENROUTER_API_KEY estiver preenchida → OpenRouter
3. Se ambas preenchidas → tentar Gemini primeiro, fallback para OpenRouter
4. Se nenhuma → erro informando necessário configurar ao menos uma

OpenRouter usa API compatível com OpenAI.
Base URL: https://openrouter.ai/api/v1
Modelo gratuito: nvidia/nemotron-3-super-120b-a12b:free
Pacote: langchain-openai (ChatOpenAI)
```

## 4. Prompt de Estrutura do Grafo

**Finalidade:** Prompt para definição do fluxo do grafo LangGraph.

```
Fluxo do agente:

[Início]
  → validar_entrada (valida URL + variáveis de ambiente)
  → buscar_prs_pendentes (lista PRs abertos via PyGithub)
  → carregar_historico (lê reviews anteriores do JSON)
  → Borda Condicional: pending_prs vazia?
      ├── Sim → encerrar_execucao
      └── Não → coletar_diff_pr → analisar_codigo(Gemini/OpenRouter) → postar_comentario
                 ↻ volta para verificar pending_prs novamente

State: PRReviewState com repo_url, owner, name, pending_prs, current_pr,
       current_diff, current_review, processed_prs_count, review_history
```

---

## 6. Prompt de Memória — Revisões Anteriores

**Finalidade:** Instrução adicionada ao system prompt para orientar o LLM a considerar revisões anteriores e evitar repetições.

```
IMPORTANT: Previous reviews have been provided as context. Avoid repeating
suggestions that were already made and addressed. Focus on new or recurring issues.
```
