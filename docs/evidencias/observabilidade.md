# Evidência de Observabilidade — Dois Sinais Correlacionados (Fase F3)

> **Issue:** [#14 — feat(observabilidade): logs estruturados JSON + registro de auditoria com latência](https://github.com/RSC-SC/IADev-ProjFinal-Mod2/issues/14)
> **Requisito atendido:** 4.6 Observabilidade e resiliência — *"Produzir e correlacionar pelo menos dois sinais de observabilidade, sendo um deles logs estruturados... Utilizar esses sinais para investigar pelo menos uma execução, permitindo identificar seu fluxo, decisões relevantes, erros e latência."*

---

## 1. Os dois sinais

| # | Sinal | Arquivo | Granularidade |
|---|-------|---------|---------------|
| 1 | **Log estruturado** (JSONL — um evento JSON por linha) | `logs/run_<run_id>.jsonl` | Cada evento: `node_start`, `node_end` (+ `duration_ms`), `error`, `llm_provider_result`, `llm_provider_success`, `security_alert`, `run_start`, `run_end` |
| 2 | **Registro de auditoria** (JSON consolidado) | `logs/audit_<run_id>.json` | Latências agregadas por nó (min/média/máx/total), provedores LLM, contagem de fallbacks, alertas de segurança, nós com erro, desfecho |

**Correlação:** todo evento do sinal 1 carrega o mesmo `run_id` presente no nome
do arquivo e no campo `run_id` da auditoria. A auditoria referencia
explicitamente o caminho do JSONL correspondente em `artifacts.structured_log`.
Campos `ts` (ISO-8601 UTC), `node` e `pr_number` permitem cruzar qualquer
evento dos dois sinais numa linha do tempo única.

## 2. Execução investigada (cenário de risco/falha)

Comando executado:

```bash
python main.py "https://github.com/exemplo_repo_invalido"
```

Entrada propositalmente inválida → o grafo deve **bloquear na validação,
terminar de forma limpa (sem traceback)** e registrar tudo nos dois sinais.

Console produzido:

```
[obs] run_id=20260823_192942_e4a1f047 — sinais sendo gravados em ./logs/

==================================================
Erro: URL inválida. Use o formato https://github.com/dono/repositorio
==================================================
[obs] Log estruturado : ...\logs\run_20260823_192942_e4a1f047.jsonl
[obs] Auditoria       : ...\logs\audit_20260823_192942_e4a1f047.json
```

### 2.1 Sinal 1 — Log estruturado (`run_20260823_192942_e4a1f047.jsonl`)

```jsonl
{"ts": "2026-08-23T19:29:42.347+00:00", "run_id": "20260823_192942_e4a1f047", "event": "run_start", "repo_url": "https://github.com/exemplo_repo_invalido", "dry_run": false, "max_prs": 3}
{"ts": "2026-08-23T19:29:42.362+00:00", "run_id": "20260823_192942_e4a1f047", "event": "node_start", "node": "validar_entrada"}
{"ts": "2026-08-23T19:29:42.362+00:00", "run_id": "20260823_192942_e4a1f047", "event": "error", "node": "validar_entrada", "message": "Erro: URL inválida. Use o formato https://github.com/dono/repositorio"}
{"ts": "2026-08-23T19:29:42.362+00:00", "run_id": "20260823_192942_e4a1f047", "event": "node_end", "node": "validar_entrada", "duration_ms": 0.4, "status": "error", "error": "Erro: URL inválida. Use o formato https://github.com/dono/repositorio"}
{"ts": "2026-08-23T19:29:42.362+00:00", "run_id": "20260823_192942_e4a1f047", "event": "node_start", "node": "encerrar_execucao"}
{"ts": "2026-08-23T19:29:42.362+00:00", "run_id": "20260823_192942_e4a1f047", "event": "error", "node": "encerrar_execucao", "message": "Erro: URL inválida. Use o formato https://github.com/dono/repositorio"}
{"ts": "2026-08-23T19:29:42.362+00:00", "run_id": "20260823_192942_e4a1f047", "event": "node_end", "node": "encerrar_execucao", "duration_ms": 0.01, "status": "error", "error": "..."}
{"ts": "2026-08-23T19:29:42.365+00:00", "run_id": "20260823_192942_e4a1f047", "event": "run_end", "status": "ok", "total_duration_ms": 18.72, "processed_prs": 0}
```

Leitura da execução pelo log: a rota condicional `validar_entrada → encerrar_execucao`
foi acionada (edge de falha), nenhum outro nó executou, erro identificado com
origem exata (`validar_entrada`) e duração por nó.

### 2.2 Sinal 2 — Auditoria (`audit_20260823_192942_e4a1f047.json`)

```json
{
  "run_id": "20260823_192942_e4a1f047",
  "started_at": "2026-08-23T19:29:42.347+00:00",
  "finished_at": "2026-08-23T19:29:42.362+00:00",
  "total_duration_ms": 18.72,
  "status": "completed",
  "outcome": "failed",
  "processed_prs": 0,
  "final_message": "Erro: URL inválida. Use o formato https://github.com/dono/repositorio",
  "repo": { "url": "https://github.com/exemplo_repo_invalido", "owner": "", "name": "" },
  "nodes_latency": {
    "validar_entrada":   { "calls": 1, "min_ms": 0.4,  "avg_ms": 0.4,  "max_ms": 0.4,  "total_ms": 0.4 },
    "encerrar_execucao": { "calls": 1, "min_ms": 0.01, "avg_ms": 0.01, "max_ms": 0.01, "total_ms": 0.01 }
  },
  "nodes_with_errors": { "validar_entrada": 1, "encerrar_execucao": 1 },
  "llm": { "providers_succeeded": [], "failed_attempts": [], "fallback_count": 0 },
  "security_alerts": [],
  "artifacts": { "structured_log": "logs\\run_20260823_192942_e4a1f047.jsonl" }
}
```

Semântica dos campos de resultado:

- `status`: ciclo de vida do processo — `completed` (grafo encerrou normalmente) vs. `crashed` (exceção inesperada);
- `outcome`: desfecho de negócio — `failed` porque algum nó sinalizou erro estruturado.

### 2.3 Investigação reconstruída a partir dos sinais

| Pergunta de investigação | Resposta | Fonte |
|---|---|---|
| Qual foi o fluxo percorrido? | `validar_entrada → encerrar_execucao` (rota curta de bloqueio) | JSONL (`node_start`/`node_end`) |
| Onde ocorreu o erro? | Em `validar_entrada`, mensagem estruturada sem traceback | JSONL (`error`) + auditoria (`nodes_with_errors`) |
| Quanto tempo durou cada etapa? | Validação: 0,40 ms; total da run: 18,72 ms | Auditoria (`nodes_latency`, `total_duration_ms`) |
| Houve chamada LLM ou fallback? | Não — falhou antes; `fallback_count: 0` | Auditoria (`llm`) |
| A execução terminou limpa? | Sim — `status: completed` (falha de entrada ≠ crash) | Auditoria (`status`/`outcome`) |
| Os dois sinais são da mesma execução? | Sim — mesmo `run_id`; auditoria aponta o caminho do JSONL | Ambos |

## 3. Comportamento em execução completa (com PRs)

Em uma execução com revisão real de PRs, os mesmos mecanismos registram:

- `node_end` de **cada iteração do loop** com `pr_number` correlacionado (inclusive os nós paralelos `analisar_codigo` e `resumir_metadados`);
- **Fallback de LLM**: tentativa que falha gera `llm_provider_result` com latência e causa; a bem-sucedida gera `llm_provider_success`. A auditoria consolida em `llm.providers_succeeded`, `llm.failed_attempts` e `llm.fallback_count`;
- **Prompt-injection neutralizado**: `security_alert` com severidades e linhas removidas, também consolidado em `audit.security_alerts`.

Exemplo real capturado durante os testes da tool (PR simulado nº 42):

```jsonl
{"event": "llm_provider_result", "provider": "Gemini", "duration_ms": 120.5, "error": "429 quota exceeded", ...}
{"event": "llm_provider_success", "provider": "OpenRouter", "duration_ms": 2310.8, ...}
{"event": "security_alert", "pr_number": 42, "high_signals": 2, "medium_signals": 1, "removed_lines": 3, ...}
```

Auditoria correspondente (trecho):

```json
"llm": {
  "providers_succeeded": ["OpenRouter"],
  "failed_attempts": [{ "provider": "Gemini", "duration_ms": 120.5, "error": "429 quota exceeded" }],
  "fallback_count": 1
},
"security_alerts": [{ "pr_number": 42, "high_signals": 2, "medium_signals": 1, "removed_lines": 3 }]
```

## 4. Garantias de projeto

- **Thread-safe**: os ramos paralelos do grafo escrevem concorrentemente; todas as escritas usam `threading.Lock`.
- **Observabilidade nunca derruba o fluxo**: toda escrita é *best-effort* — falha de disco/caminho é silenciada e a execução prossegue.
- **Sem segredos**: os artefatos não contêm tokens nem conteúdo de diff completo (apenas contagens e mensagens de erro).
- **`logs/` fora do git** (`.gitignore`): artefatos de runtime não poluem o repositório; evidências selecionadas vão para `docs/evidencias/`.

## 5. Como reproduzir

```bash
# Cenário de falha controlada (não exige chaves):
python main.py "https://github.com/exemplo_repo_invalido"

# Inspecionar os sinais:
cat logs/run_<run_id>.jsonl
cat logs/audit_<run_id>.json
```
