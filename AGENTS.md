# Fluxo de Desenvolvimento (Instruções para o Agente IA)

Sempre que for realizada uma alteração no código deste projeto, o seguinte fluxo DEVE ser seguido:

## Fluxo Obrigatório

1. **Criar Issue no GitHub**
   - Descrever a tarefa com título e descrição claros
   - Adicionar labels se aplicável

2. **Criar branch a partir de `develop`**
   - Nome padrão: `feature/<descricao-curta>`, `fix/<descricao-curta>` ou `docs/<descricao-curta>`

3. **Implementar a alteração**
   - Fazer checkout na branch criada
   - Implementar o código conforme definido na Issue

4. **Commit**
   - Usar mensagens semânticas claras (ex: `feat:`, `fix:`, `docs:`, `refactor:`, `chore:`)

5. **Criar Pull Request para `develop`**
   - PR deve referenciar a Issue (ex: `Closes #1`)
   - Descrever as mudanças realizadas

6. **Documentar na Issue**
   - Atualizar a Issue com o link do PR e status da implementação

7. **Integração**
   - `feature/*` → `develop` (via PR)
   - `develop` → `main` apenas em marcos estáveis (versão final obrigatoriamente na `main`)

---

## 📌 Contexto Atual — Projeto Final Módulo 2

| Item | Valor |
|------|-------|
| **Repositório** | https://github.com/RSC-SC/IADev-ProjFinal-Mod2 |
| **Fase** | Evolução do Mini-Projeto (entregue 20/07/26) → Projeto Final |
| **Prazo** | 31/08/2026 às 15h (submissão no AVA) |
| **Peso** | 60% da nota do módulo |
| **Fluxo Git** | `main` ← `develop` ← `feature/*` |

> O plano detalhado de trabalho (8 fases), a análise de gaps contra a rubrica e o log de decisões estão no documento externo `PLANO_PROJETO_FINAL_MOD2.md` (fora do repositório).

### ✅ Baseline (Mini-Projeto concluído)
- Agente LangGraph funcional: valida URL → lista PRs abertos → analisa diff com LLM → posta review no PR
- Fallback LLM: Gemini 2.0 Flash → OpenRouter (`nemotron-3-super-120b-a12b:free`)
- Memória: histórico de revisões em JSON (`reviews/`) injetado no prompt
- README completo (escopo mini), prompts documentados, apresentação em `docs/`

### 📂 Estrutura do Projeto
```
IADev-ProjFinal-Mod2/
├── .env.example              # GITHUB_TOKEN, GOOGLE_API_KEY, OPENROUTER_API_KEY, OPENROUTER_MODEL
├── .gitignore                # Ignora .env e enunciados (.md/.pdf)
├── requirements.txt          # langgraph, langchain-google-genai, langchain-openai, PyGithub, python-dotenv
├── AGENTS.md                 # Este arquivo (instruções do fluxo)
├── main.py                   # CLI: python main.py <url-do-repo>
├── reviews/                  # Histórico de revisões (JSON, gerado automaticamente)
├── docs/
│   ├── prompts.md            # Registro dos prompts utilizados
│   └── Agente Revisor de PRs.pptx/pdf  # Apresentação (2 slides)
└── src/
    ├── state.py              # PRReviewState (TypedDict)
    ├── graph.py              # Grafo LangGraph com validação + loop
    ├── nodes/
    │   ├── validation.py     # Valida URL e pelo menos uma chave LLM
    │   ├── pr_collector.py   # Busca PRs abertos + coleta diff
    │   ├── history_loader.py # Carrega histórico de revisões
    │   ├── code_analyzer.py  # Análise com fallback Gemini → OpenRouter
    │   ├── comment_poster.py # Posta review no PR + salva no histórico
    │   └── finish.py         # Encerra execução
    └── tools/
        ├── github_tool.py    # Wrapper PyGithub (Auth.Token)
        ├── sanitizer.py      # Defesa anti prompt-injection (detecção/neutralização/envelope)
        ├── observability.py  # Dois sinais correlacionados: JSONL estruturado + auditoria com latência
        └── memory_tool.py    # Leitura/escrita do histórico JSON
```

### 🔧 Stack Técnica
- **Framework:** LangGraph (StateGraph)
- **LLM Primário:** Google Gemini (`GOOGLE_MODEL`, padrão `gemini-3.6-flash`, via `langchain-google-genai`)
- **LLM Fallback:** OpenRouter — `nvidia/nemotron-3-super-120b-a12b:free` (via `langchain-openai`)
- **API GitHub:** PyGithub 2.9+ (`Auth.Token`)
- **Python:** 3.10+

### 📋 Roadmap do Projeto Final (resumo — detalhes no plano externo)

| Fase | Escopo | Status |
|------|--------|--------|
| F0 | Preparação: branches main/develop, AGENTS.md, prompts.md, Kanban | ✅ Concluída (20/08/26) |
| F1 | Paralelização no grafo + robustez GitHubTool + 2 cenários documentados | ✅ Concluída (21/08/26) |
| F2 | Sanitização anti prompt-injection + limites de autonomia (--dry-run) | ✅ |
| F3 | Logs estruturados JSON + auditoria com latência (2 sinais correlacionados) | ✅ |
| F4 | Testes pytest gerados/refinados com IA + review do próprio agente em PR real | ✅ Suíte 102 testes em /tests (docs/qa/) |
| F5 | Pipeline CI (lint/testes/build) + análise de logs por IA + anomalia + risco | ✅ CI verde no PR #19 (evidência em docs/evidencias/fase5_devops.md) |
| F6 | Automação low-code n8n integrada (trigger + saída observável) | ✅ PR #21 (evidência em docs/evidencias/fase6_n8n.md) |
| F7 | README final, refinamentos documentados, merge main, vídeo, submissão AVA | ⬜ |

### 🌿 Branches
| Branch | Papel |
|--------|-------|
| `main` | Produção — versão final avaliada |
| `develop` | Integração — base das feature branches |
