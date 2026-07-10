# Fluxo de Desenvolvimento (Instruções para o Agente IA)

Sempre que for realizada uma alteração no código deste projeto, o seguinte fluxo DEVE ser seguido:

## Fluxo Obrigatório

1. **Criar Issue no GitHub**
   - Descrever a tarefa com título e descrição claros
   - Adicionar labels se aplicável

2. **Criar branch a partir de `dev`**
   - Nome padrão: `feature/<descricao-curta>` ou `fix/<descricao-curta>`

3. **Implementar a alteração**
   - Fazer checkout na branch criada
   - Implementar o código conforme definido na Issue

4. **Commit**
   - Usar mensagens semânticas claras (ex: `feat:`, `fix:`, `docs:`, `refactor:`)

5. **Criar Pull Request para `dev`**
   - PR deve referenciar a Issue (ex: `Closes #1`)
   - Descrever as mudanças realizadas

6. **Documentar na Issue**
   - Atualizar a Issue com o link do PR e status da implementação

---

## 📌 Sessão Atual — 09/07/2026

### ✅ Concluído

| Issue | Título | PR | Status |
|-------|--------|----|--------|
| #1 | Estruturar projeto do Agente Revisor de PRs | [#2](https://github.com/RSC-SC/IADev-MiniProj-Mod2/pull/2) | ✅ Mergeado |
| #4 | Corrigir autenticação PyGithub e fluxo de validação | [#5](https://github.com/RSC-SC/IADev-MiniProj-Mod2/pull/5) | ✅ Mergeado |
| #6 | Suporte multi-provedor LLM (Gemini + OpenRouter) | [#7](https://github.com/RSC-SC/IADev-MiniProj-Mod2/pull/7) | 🔄 PR Aberto |
| #3 | Testar e validar execução do agente | — | ✅ Testado |

### 🧪 Testes Realizados
- **URL inválida** → rejeita sem chamar API ✅
- **URL sem PRs** → informa corretamente ✅
- **Gemini com quota excedida (429)** → fallback para OpenRouter ✅
- **Review completo postado** em https://github.com/RSC-SC/testeAgentePR/pull/1 ✅

### 📂 Estrutura do Projeto
```
Miniprojeto_Mod02/
├── .env.example              # GITHUB_TOKEN, GOOGLE_API_KEY, OPENROUTER_API_KEY
├── .gitignore
├── requirements.txt          # langgraph, langchain-google-genai, langchain-openai, PyGithub
├── AGENTS.md                 # Este arquivo (instruções do fluxo)
├── main.py                   # CLI: python main.py <url-do-repo>
├── docs/
│   └── prompts.md            # Registro dos prompts utilizados
└── src/
    ├── state.py              # PRReviewState (TypedDict)
    ├── graph.py              # Grafo LangGraph com validação + loop
    ├── nodes/
    │   ├── validation.py     # Valida URL e pelo menos uma chave LLM
    │   ├── pr_collector.py   # Busca PRs abertos + coleta diff
    │   ├── code_analyzer.py  # Análise com fallback Gemini → OpenRouter
    │   ├── comment_poster.py # Posta review no PR
    │   └── finish.py         # Encerra execução
    └── tools/
        └── github_tool.py    # Wrapper PyGithub (Auth.Token)
```

### 🔧 Stack Técnica
- **Framework:** LangGraph (StateGraph)
- **LLM Primário:** Google Gemini 2.0 Flash (via `langchain-google-genai`)
- **LLM Fallback:** OpenRouter — `nvidia/nemotron-3-super-120b-a12b:free` (via `langchain-openai`)
- **API GitHub:** PyGithub 2.9+ (`Auth.Token`)
- **Python:** 3.10.5

### 📋 Pendências / Próximos Passos
1. ⬜ **Mergear PR #7** (multi-provedor) em dev
2. ⬜ **README.md** — documentação completa do projeto
3. ⬜ **docs/prompts.md** — revisar/adicionar prompts
4. ⬜ **Apresentação (2 slides)** — problema, agente, fluxo, ferramentas
5. ⬜ **Criar .env com chave OpenRouter** para evitar depender do Gemini
6. ⬜ **Limpar branches locais** antigas (feature/estrutura-inicial-projeto, fix/autenticacao-pygithub-fluxo-validacao, feature/teste-validacao-agente)

### 🌿 Branches Ativas
| Branch | Base | Status |
|--------|------|--------|
| `feature/multi-provedor-gemini-openrouter` | dev | 🔄 Ativa (PR #7 aberto) |
| `feature/teste-validacao-agente` | dev | 🗑️ Obsoleta (pode deletar) |
