# Cenários de Uso

Este documento descreve os **dois cenários oficiais** de uso do Agente Revisor de PRs:
o fluxo principal (operação normal) e o cenário de risco/falha (operações adversas),
com o comportamento observável esperado em cada caso.

---

## Cenário 1 — Fluxo Principal: repositório com PRs abertos

**Objetivo:** demonstrar a operação completa do agente — da URL recebida até os
comentários de revisão postados nos PRs.

### Pré-condições
- `.env` configurado com `GITHUB_TOKEN` e pelo menos uma chave LLM
  (`GOOGLE_API_KEY` ou `OPENROUTER_API_KEY`)
- Repositório GitHub acessível pelo token com **pelo menos 1 PR aberto**

### Execução

```bash
python main.py https://github.com/RSC-SC/testeAgentePR --max-prs 3
```

### Fluxo no grafo

```
validar_entrada ──▶ buscar_prs_pendentes ──▶ carregar_historico
                                                    │
                                                    ▼
                                            coletar_diff_pr
                                            ╱              ╲
                              analisar_codigo        resumir_metadados   ⚡ paralelo
                                  (LLM)             (determinístico)
                                            ╲              ╱
                                             postar_comentario
                                                    │
                                        (próximo PR ou encerrar)
```

- `analisar_codigo` (lento, chamada de LLM com fallback Gemini → OpenRouter) roda
  **em paralelo** com `resumir_metadados` (rápido, determinístico)
- O loop repete por cada PR aberto, **limitado a `--max-prs`** (padrão: 3)

### Saída observável

1. **Terminal:** mensagem final `Revisão concluída. N PR(s) processado(s) com sucesso.`
2. **GitHub:** comentário postado em cada PR revisitado, no formato:

```markdown
## 🤖 Revisão Automática de Código

### 📋 Metadados do PR
- **PR:** #12 — feat: adicionar endpoint de login
- **Link:** https://github.com/dono/repo/pull/12
- **Arquivos alterados:** 3
- **Linhas no diff:** +87 / -12 (110 linhas totais)
- **Complexidade estimada:** Pequena

---

## Pontos Positivos
- ...

## Oportunidades de Melhoria
- ...
```

3. **Histórico local:** cada revisão é anexada em `reviews/<owner>_<repo>/history.json`
   e injetada como contexto nas execuções seguintes (evita sugestões repetidas).

---

## Cenário 2 — Cenário de Risco/Falha

O agente foi projetado para **nunca derrubar a execução com traceback**: falhas são
convertidas em mensagens estruturadas e o grafo termina de forma controlada.

| # | Situação adversa | Camada que trata | Comportamento observável |
|---|------------------|------------------|--------------------------|
| 2a | URL inválida | `validar_entrada` | Erro imediato, **sem nenhuma chamada de rede** |
| 2b | `GITHUB_TOKEN` ausente ou nenhuma chave LLM | `validar_entrada` | Bloqueio local com instrução de correção do `.env` |
| 2c | Repo inexistente/sem acesso (HTTP 404) | `GitHubTool` | Falha permanente: **1 tentativa apenas**, mensagem estruturada |
| 2d | Instabilidade na API GitHub (HTTP 500/503) | `GitHubTool` | **Retry limitado a 3 tentativas** com backoff crescente; se persistir, erro estruturado |
| 2e | Repo sem PRs abertos | `buscar_prs_pendentes` | Mensagem informativa, execução termina normalmente |
| 2f | Quota do Gemini excedida (HTTP 429) | `analisar_codigo` | **Fallback automático para OpenRouter**; revisão segue normalmente |
| 2g | Todos os provedores LLM falham | `analisar_codigo` | Grafo termina limpo com diagnóstico (`Erro ao analisar o PR #N`) |
| 2h | Falha ao postar comentário (ex.: PR travado) | `postar_comentario` | Termina limpo; PR não é contabilizado nem entra no histórico |

### Exemplos executáveis

**2a — URL inválida** (sem rede):

```bash
python main.py "nao-e-uma-url"
# ==================================================
# Erro: URL inválida. Use o formato https://github.com/dono/repositorio
# ==================================================
```

**2e — Repo sem PRs abertos:**

```bash
python main.py https://github.com/dono/repo-sem-prs
# ==================================================
# Nenhum Pull Request aberto encontrado no repositório
# ==================================================
```

**2f — Quota do Gemini excedida** (observável no log do terminal):

```
WARNING: Provedor Gemini falhou: 429 RESOURCE_EXHAUSTED ...
Tentando provedor LLM: OpenRouter
==================================================
Revisão concluída. 1 PR(s) processado(s) com sucesso.
==================================================
```

### Limite de autonomia

A flag `--max-prs N` delimita quantos PRs o agente pode processar numa única
execução (padrão: 3), mesmo que existam mais PRs abertos — evitando consumo
descontrolado de quota de LLM e de escritas na API do GitHub.
