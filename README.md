# Agente Revisor de PRs

Agente automatizado que revisa Pull Requests do GitHub usando Inteligência Artificial, focando em boas práticas de programação e legibilidade de código.

## Problema

Revisar manualmente Pull Requests é um processo demorado e sujeito a inconsistências. Em projetos com múltiplos PRs abertos, os revisores podem sobrecarregar-se ou deixar de apontar problemas importantes. A automação dessa tarefa permite um feedback mais rápido, padronizado e completo.

## Objetivo do Agente

O agente recebe a **URL de um repositório GitHub**, identifica todos os **PRs abertos**, analisa o código modificado de cada um usando um modelo de linguagem (LLM) e **posta um comentário estruturado** diretamente no PR com sugestões de melhoria.

## Fluxo com LangGraph

O agente é implementado com **LangGraph** (StateGraph), organizado em nós e arestas condicionais:

```
[Início]
   │
   ▼
┌─────────────────────┐
│  validar_entrada    │  ← Valida URL + verifica chaves de API
└─────────┬───────────┘
          │
          ▼
┌─────────────────────────┐    Não    ┌───────────────────┐
│  buscar_prs_pendentes   │ ────────▶ │ encerrar_execucao │
└─────────┬───────────────┘           └───────────────────┘
          │ Sim (tem PRs)
          ▼
┌─────────────────────┐
│ carregar_historico  │  ← Carrega revisões anteriores do JSON
└─────────┬───────────┘
          │
          ▼
┌──────────────────┐
│  coletar_diff_pr │ ◀──────────────┐
└────────┬─────────┘                │
          │                          │
          ▼                          │     Loop: processa cada PR
┌──────────────────┐                │   (até --max-prs)
│  sanitizar_diff  │ 🛡️ anti-injection│
└────────┬─────────┘                │
          │ (fan-out)                │
     ┌────┴─────────────┐            │
     ▼                  ▼            │
┌──────────────────┐ ┌──────────────────────┐│
│  analisar_codigo │ │  resumir_metadados   ││
│  (LLM, lento)    │ │  (determinístico, ⚡) ││
└────────┬─────────┘ └──────────┬───────────┘│
         └───────┬──────────────┘ (fan-in)    │
                 ▼                            │
        ┌──────────────────────┐              │ Sim (fila não vazia
        │  postar_comentario   │ ─────────────┘  e abaixo do limite)
        └──────────┬───────────┘
                   │ Não (fila vazia ou limite atingido)
                   ▼
          ┌───────────────────┐
          │ encerrar_execucao │
          └───────────────────┘
```

### Nós do Grafo

| Nó | Função |
|----|--------|
| `validar_entrada` | Valida formato da URL e verifica se as chaves de API estão configuradas |
| `buscar_prs_pendentes` | Lista todos os PRs abertos do repositório via API GitHub |
| `carregar_historico` | Carrega revisões anteriores do repositório para contexto do LLM |
| `coletar_diff_pr` | Baixa o diff do PR atual e o remove da fila de pendentes |
| `sanitizar_diff` | **🛡️ Governança:** detecta e neutraliza tentativas de prompt-injection no diff antes de qualquer contato com o LLM |
| `analisar_codigo` | Envia o diff sanitizado (envelope `<untrusted_content>`) ao LLM e gera a revisão estruturada |
| `resumir_metadados` | Gera sumário determinístico do PR (arquivos, linhas, complexidade) — roda **em paralelo** à análise do LLM |
| `postar_comentario` | Publica comentário combinando metadados + revisão no PR e salva no histórico; em `--dry-run`, apenas exibe no console (aprovação humana) |
| `encerrar_execucao` | Finaliza o processo com o resumo de PRs processados |

## Ferramenta Integrada

O agente utiliza a **API do GitHub** por meio da biblioteca **PyGithub**, executando duas ações reais:

1. **Leitura:** Busca PRs abertos e baixa o diff de cada um
2. **Escrita:** Posta comentários de revisão diretamente nos PRs

## Stack Técnica

| Componente | Tecnologia |
|------------|------------|
| Framework do Agente | LangGraph (StateGraph) |
| LLM Primário | Google Gemini (`GOOGLE_MODEL`, padrão `gemini-3.6-flash`) |
| LLM Fallback | OpenRouter — nvidia/nemotron-3-super-120b-a12b:free |
| API GitHub | PyGithub 2.9+ |
| Linguagem | Python 3.10+ |

## Como Executar

### 1. Clonar o repositório

```bash
git clone https://github.com/RSC-SC/IADev-ProjFinal-Mod2.git
cd IADev-ProjFinal-Mod2
```

### 2. Instalar dependências

```bash
pip install -r requirements.txt
```

### 3. Configurar variáveis de ambiente

Crie um arquivo `.env` na raiz do projeto:

```bash
cp .env.example .env
```

Edite o `.env` com suas credenciais:

```env
GITHUB_TOKEN=seu_token_aqui
GOOGLE_API_KEY=sua_chave_aqui        # Opcional (se tiver quota)
OPENROUTER_API_KEY=sua_chave_aqui    # Opcional (fallback gratuito)
```

> **Nota:** Configure pelo menos uma chave de LLM (Google ou OpenRouter).

### 4. Executar o agente

```bash
python main.py https://github.com/dono/repositorio

# Opcional: limitar quantos PRs revisar nesta execução (padrão: 3)
python main.py https://github.com/dono/repositorio --max-prs 5

# Limite de autonomia: gera as revisões no console, mas NÃO posta no GitHub
# (postagem só ocorre após aprovação humana, em execução sem a flag)
python main.py https://github.com/dono/repositorio --dry-run
```

## Cenários de Uso

Os dois cenários oficiais — **fluxo principal** (repo com PRs abertos) e
**cenário de risco/falha** (URL inválida, quota excedida → fallback, API
instável, repo sem PRs) — estão documentados em
[`docs/cenarios.md`](docs/cenarios.md), incluindo comportamento observável
de cada falha.

## Segurança e Governança

O diff de um PR é **conteúdo externo não confiável**: pode conter tentativas de
*prompt-injection* que instruam o LLM a ignorar regras, alterar a revisão ou vazar
segredos. A defesa é em profundidade, em 3 camadas:

1. **Detecção** — regex determinísticas (EN + PT) com severidade alta/média sobre cada linha do diff;
2. **Neutralização** — linhas maliciosas substituídas por placeholder auditável antes do LLM; relatório estruturado no estado;
3. **Encapsulamento** — diff higienizado vai ao LLM dentro de `<untrusted_content>`, com SYSTEM_PROMPT contendo regras de segurança inultrapassáveis.

Complementos de governança:

- **`--dry-run`** — limita a autonomia de escrita: revisão só chega ao GitHub com aprovação humana;
- **Transparência** — quando há sinais detectados, o comentário postado inclui a seção `🛡️ Nota de Segurança` com o total neutralizado;
- **Auditoria** — histórico local distingue revisões postadas (`posted: true`) de geradas em dry-run (`posted: false`).

Detalhes completos (modelo de ameaça + payload adversarial demonstrado): [`docs/seguranca.md`](docs/seguranca.md)
e evidência empírica em [`docs/evidencias/fase2_seguranca_evidencia.md`](docs/evidencias/fase2_seguranca_evidencia.md).

## Observabilidade — Dois Sinais Correlacionados

Toda execução produz **dois sinais de observabilidade correlacionados por um `run_id` único**:

| Sinal | Arquivo | Conteúdo |
|-------|---------|----------|
| **Log estruturado (JSONL)** | `logs/run_<run_id>.jsonl` | Um evento JSON por linha: `run_start`, `node_start`, `node_end` (+`duration_ms`), `error`, `llm_provider_result/success` (fallback), `security_alert`, `run_end` |
| **Registro de auditoria (JSON)** | `logs/audit_<run_id>.json` | Consolidação da execução: latência total e por nó (mín/média/máx), provedores LLM usados, contagem de fallbacks, alertas de segurança, nós com erro, desfecho (`succeeded`/`failed`) |

Como os sinais se correlacionam: todo evento carrega o mesmo `run_id` + timestamp
ISO-8601 UTC + `node` + `pr_number`; a auditoria referencia o caminho exato do
JSONL da mesma execução em `artifacts.structured_log`. Isso permite reconstruir
o fluxo, as decisões, os erros e a latência de qualquer execução passada.

Garantias: escritas **thread-safe** (compatíveis com o fan-out paralelo do grafo),
*best-effort* (falha de log jamais derruba a execução) e sem segredos nos artefatos.

Investigação real de uma execução documentada em:
[`docs/evidencias/observabilidade.md`](docs/evidencias/observabilidade.md)

## ⚙️ DevOps e CI — Pipeline com Análise de Logs por IA

O repositório possui pipeline **GitHub Actions** (`.github/workflows/ci.yml`) com três
etapas paralelas acionadas a cada PR/push:

| Etapa | O que faz | Artefato |
|-------|-----------|----------|
| **Lint** | `ruff check .` (config justificada em `pyproject.toml`) | `log-lint` |
| **Testes** | suíte offline de 102 testes (~1s no CI) | `log-pytest` |
| **Build/validação** | `compileall` + smoke de importação do grafo (sem rede/chaves) | `log-build` |

Destaques de projeto:
- **Zero segredos no pipeline**: os testes são offline por construção (Fase 4), então o
  CI roda sem nenhuma credencial exposta.
- Cada etapa publica seu log como artefato, permitindo **análise posterior por IA**
  (leitura técnica, hipóteses de anomalia e ações recomendadas) — evidência real em
  [`docs/evidencias/fase5_devops.md`](docs/evidencias/fase5_devops.md), incluindo a
  detecção da diferença de tempo da suíte entre runner Linux (0,94 s) e Windows local.
- `scripts/pipeline_log_analyzer.py` analisa os sinais de observabilidade da aplicação
  (seção anterior): **detecção robusta de anomalias** (mediana/MAD), tendência de
  latência e estimativa transparente de risco de falha em múltiplas visões
  (bruto × operacional × estado atual).

## Exemplo de Entrada

```bash
python main.py https://github.com/RSC-SC/testeAgentePR
```

## Exemplo de Saída

```
[obs] run_id=20260823_193500_ab12cd34 — sinais sendo gravados em ./logs/
Provedor Gemini falhou: ... RESOURCE_EXHAUSTED ... (fallback para OpenRouter)
Tentando provedor LLM: OpenRouter

==================================================
Revisão concluída. 1 PR(s) processado(s) com sucesso.
==================================================
[obs] Log estruturado : ...\logs\run_20260823_193500_ab12cd34.jsonl
[obs] Auditoria       : ...\logs\audit_20260823_193500_ab12cd34.json
```

O comentário postado no PR:

```markdown
## 🤖 Revisão Automática de Código

### 📋 Metadados do PR
- **PR:** #12 — feat: exemplo
- **Link:** https://github.com/dono/repo/pull/12
- **Arquivos alterados:** 2
- **Linhas no diff:** +34 / -6 (48 linhas totais)
- **Complexidade estimada:** Pequena

---

## Pontos Positivos
- Boa utilização de tipos no Python
- Código bem organizado e legível

## Oportunidades de Melhoria
- Adicionar tratamento de exceções na função `processar_dados`
- Incluir docstrings nos módulos públicos

---
*Gerado pelo Agente Revisor de PRs | IA para Desenvolvedores*
```

## Principais Decisões Técnicas

| Decisão | Justificativa |
|---------|---------------|
| **LangGraph** como framework | Permite modelar o fluxo como um grafo com nós, arestas e loops condicionais |
| **Gemini + OpenRouter** com fallback | Gemini como opção principal; OpenRouter gratuito como alternativa quando a quota do Gemini é excedida |
| **PyGithub** em vez de requests | Biblioteca oficial que abstrai a API GitHub de forma mais segura e organizada |
| **TypedDict** para o estado | Tipagem estática do estado facilita manutenção e depuração |
| **Regex** para validação de URL | Valida a entrada sem gastar tokens de LLM |
| **Loop condicional** no grafo | Permite processar múltiplos PRs em uma única execução |
| **Sanitização em 3 camadas** | Detecção regex + neutralização + envelope `<untrusted_content>`: conteúdo externo não sobrepõe as regras da aplicação |
| **`--dry-run`** como limite de autonomia | Revisão gerada só é publicada com aprovação humana explícita |
| **Seção 🛡️ no comentário** | Transparência: autor do PR fica ciente de tentativas de manipulação neutralizadas |
| **Dois sinais correlacionados por `run_id`** | JSONL estruturado (sequência exata de eventos) + auditoria consolidada (latências e desfecho) permitem investigar qualquer execução |
| **Instrumentação via wrapper no grafo** | Latência/eventos medidos centralmente em `build_graph()` — os nós permanecem focados na lógica de negócio |

## Limitações da Solução

- **Quota do Gemini:** no tier gratuito, a quota é limitada; o fallback para OpenRouter mitiga isso
- **Modelo gratuito do OpenRouter:** pode ter latência maior e qualidade variável
- **Análise por diff:** não considera o contexto completo do repositório, apenas as linhas alteradas
- **Histórico local:** o histórico de revisões é armazenado em JSON local, não sincronizado entre máquinas
- **Defesa anti-injection:** baseada em padrões conhecidos; mitiga (não elimina) injeções semânticas sofisticadas — ver `docs/seguranca.md`

## Automação com n8n

O agente pode ser integrado à plataforma de automação low-code **n8n** para execução automática sempre que um PR for aberto ou atualizado:

```
GitHub (PR Event) → n8n Webhook → Execute Agent → Post Review → Notification
```

### Configuração Rápida

1. Importe o workflow: `n8n/workflow_pr_review.json`
2. Configure a credencial GitHub Token no n8n
3. Adicione o webhook no GitHub (Settings → Webhooks)
4. Ative o workflow

Documentação completa: [`n8n/README.md`](n8n/README.md) | [`n8n/GUIA_COMPLETO.md`](n8n/GUIA_COMPLETO.md)

## Testes

O projeto possui **102 testes pytest** executados 100% offline:

```bash
# Executar todos os testes
pytest tests/ -v

# Executar com cobertura
pytest tests/ --cov=src --cov-report=html
```

| Módulo | Testes | Prioridade |
|--------|--------|------------|
| Sanitizer (anti injection) | 38 | Crítica |
| GitHub Tool | 26 | Alta |
| Grafo E2E | 18 | Alta |
| Observabilidade | 11 | Média |
| Finish/Wrapper | 9 | Média |

Detalhes: [`docs/qa/processo_qa_ia.md`](docs/qa/processo_qa_ia.md)

## Estrutura do Projeto

```
IADev-ProjFinal-Mod2/
├── .env.example              # Template de variáveis de ambiente
├── .gitignore                # Arquivos ignorados pelo Git
├── requirements.txt          # Dependências do projeto
├── main.py                   # Ponto de entrada (CLI, com --dry-run e ciclo de vida de observabilidade)
├── reviews/                  # Histórico de revisões (JSON, gerado automaticamente)
├── logs/                     # Sinais de observabilidade por execução (JSONL + auditoria, gerados a cada run)
├── n8n/                      # Integração com n8n (automação low-code)
│   ├── workflow_pr_review.json  # Workflow exportável
│   ├── agent_adapter.py      # Script de integração
│   └── README.md             # Documentação de uso
├── tests/                    # 102 testes pytest (offline)
│   ├── test_sanitizer.py     # 38 testes do sanitizador
│   ├── test_github_tool.py   # 26 testes da ferramenta GitHub
│   ├── test_graph_e2e.py     # 18 testes E2E do grafo
│   ├── test_observability.py # 11 testes de observabilidade
│   └── test_finish_and_wrapper.py # 9 testes auxiliares
├── scripts/
│   └── pipeline_log_analyzer.py # Análise de logs com anomalia/risco
├── docs/
│   ├── prompts.md            # Registro dos prompts utilizados
│   ├── seguranca.md          # Modelo de ameaça + defesas anti prompt-injection
│   ├── cenarios.md           # Cenários de uso (fluxo principal + falhas)
│   ├── qa/                   # Processo de QA com IA
│   └── evidencias/           # Evidências empíricas por fase
├── .github/workflows/
│   └── ci.yml                # Pipeline CI (lint + testes + build)
└── src/
    ├── state.py              # Estado compartilhado (TypedDict)
    ├── graph.py              # Grafo LangGraph (nós instrumentados com observabilidade)
    ├── nodes/
    │   ├── validation.py     # Validação de entrada
    │   ├── pr_collector.py   # Coleta de PRs e diffs
    │   ├── diff_sanitizer.py # 🛡️ Sanitização anti prompt-injection (+ security_alert)
    │   ├── history_loader.py # Carrega histórico de revisões
    │   ├── code_analyzer.py  # Análise de código com LLM (prompt blindado + eventos de fallback)
    │   ├── metadata_summarizer.py # Sumário determinístico (ramo paralelo)
    │   ├── comment_poster.py # Postagem de comentários (+ modo dry-run)
    │   └── finish.py         # Encerramento
    └── tools/
        ├── github_tool.py    # Wrapper da API GitHub (PyGithub)
        ├── sanitizer.py      # 🛡️ Detecção/neutralização de injeção (puro, testável)
        ├── observability.py  # 📊 Dois sinais correlacionados: JSONL estruturado + auditoria com latência
        └── memory_tool.py    # Leitura/escrita de histórico em JSON
```

## Roadmap do Projeto Final

| Fase | Escopo | Status |
|------|--------|--------|
| F0 | Preparação: branches, AGENTS.md, prompts.md | ✅ |
| F1 | Paralelização + robustez GitHubTool + cenários | ✅ |
| F2 | Sanitização anti prompt-injection + --dry-run | ✅ |
| F3 | Logs estruturados JSON + auditoria com latência | ✅ |
| F4 | Testes pytest (102) gerados/refinados com IA | ✅ |
| F5 | Pipeline CI + análise de logs por IA | ✅ |
| F6 | Automação n8n integrada (trigger + saída observável) | ✅ |
| F7 | README final, refinamentos, merge main, submissão | ✅ |

## Créditos

Desenvolvido como Projeto Final do Módulo 2 - **IA para Desenvolvedores** (SCTEC).

---

*Agente Revisor de PRs v2.0 — Automação de code review com IA*
