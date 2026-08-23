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
| LLM Primário | Google Gemini 2.0 Flash |
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

## Exemplo de Entrada

```bash
python main.py https://github.com/RSC-SC/testeAgentePR
```

## Exemplo de Saída

```
Provedor Gemini falhou: ... RESOURCE_EXHAUSTED ... (fallback para OpenRouter)
Tentando provedor LLM: OpenRouter

==================================================
Revisão concluída. 1 PR(s) processado(s) com sucesso.
==================================================
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

## Limitações da Solução

- **Quota do Gemini:** no tier gratuito, a quota é limitada; o fallback para OpenRouter mitiga isso
- **Modelo gratuito do OpenRouter:** pode ter latência maior e qualidade variável
- **Análise por diff:** não considera o contexto completo do repositório, apenas as linhas alteradas
- **Histórico local:** o histórico de revisões é armazenado em JSON local, não sincronizado entre máquinas
- **Defesa anti-injection:** baseada em padrões conhecidos; mitiga (não elimina) injeções semânticas sofisticadas — ver `docs/seguranca.md`

## Estrutura do Projeto

```
IADev-ProjFinal-Mod2/
├── .env.example              # Template de variáveis de ambiente
├── .gitignore                # Arquivos ignorados pelo Git
├── requirements.txt          # Dependências do projeto
├── main.py                   # Ponto de entrada (CLI, com --dry-run)
├── reviews/                  # Histórico de revisões (JSON, gerado automaticamente)
├── docs/
│   ├── prompts.md            # Registro dos prompts utilizados
│   ├── seguranca.md          # Modelo de ameaça + defesas anti prompt-injection
│   ├── cenarios.md           # Cenários de uso (fluxo principal + falhas)
│   └── evidencias/           # Evidências empíricas por fase
└── src/
    ├── state.py              # Estado compartilhado (TypedDict)
    ├── graph.py              # Grafo LangGraph
    ├── nodes/
    │   ├── validation.py     # Validação de entrada
    │   ├── pr_collector.py   # Coleta de PRs e diffs
    │   ├── diff_sanitizer.py # 🛡️ Sanitização anti prompt-injection
    │   ├── history_loader.py # Carrega histórico de revisões
    │   ├── code_analyzer.py  # Análise de código com LLM (prompt blindado)
    │   ├── metadata_summarizer.py # Sumário determinístico (ramo paralelo)
    │   ├── comment_poster.py # Postagem de comentários (+ modo dry-run)
    │   └── finish.py         # Encerramento
    └── tools/
        ├── github_tool.py    # Wrapper da API GitHub (PyGithub)
        ├── sanitizer.py      # 🛡️ Detecção/neutralização de injeção (puro, testável)
        └── memory_tool.py    # Leitura/escrita de histórico em JSON
```
