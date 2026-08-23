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

## 3. Execução real bem-sucedida (com PRs e LLM)

Execução real pós-refinamento (Issue #16), modo `--dry-run --max-prs 2`, contra
o repositório de testes com 10+ PRs abertos:

```bash
python main.py "https://github.com/RSC-SC/testeAgentePR" --dry-run --max-prs 2
```

### 3.1 Sinal 1 — JSONL (`run_20260823_200020_1b6bf5b0.jsonl`, resumido)

```
20:00:20.461 run_start   repo=https://github.com/RSC-SC/testeAgentePR dry_run=true max_prs=2
20:00:20.461 node_end    validar_entrada        0.3 ms  ok
20:00:22.538 node_end    buscar_prs_pendentes 2065.8 ms  ok          ← API GitHub (rede)
20:00:22.538 node_end    carregar_historico     1.0 ms  ok  pr=11
20:00:26.373 node_end    coletar_diff_pr     3832.3 ms  ok  pr=11   ← download do diff
20:00:26.389 node_end    sanitizar_diff        10.8 ms  ok  pr=11   🛡️
20:00:26.404 node_start  analisar_codigo + resumir_metadados            ← FAN-OUT PARALELO (mesmo ts)
20:00:26.404 node_end    resumir_metadados      0.1 ms  ok  pr=11    ⚡ determinístico
20:00:39.179 llm_provider_success  provider=Gemini dur=9689ms           ← inferência LLM
20:00:39.194 node_end    analisar_codigo    12803.8 ms  ok  pr=11
20:00:39.210 node_end    postar_comentario     1.7 ms  ok  pr=11   ← dry-run: nada postado
   ... (loop repete para o PR #10) ...
20:00:54.221 llm_provider_success  provider=Gemini dur=10621ms
20:00:54.237 node_end    encerrar_execucao      0.0 ms  ok
20:00:54.237 run_end     total_duration_ms=33780.91 processed_prs=2
```

Reconstrução visível pelo log: fluxo sequencial → loop por PR (`pr_number`
correlacionado em cada evento) → fan-out dos ramos paralelo (timestamps
idênticos) → fan-in na postagem → encerramento limpo.

### 3.2 Sinal 2 — Auditoria (`audit_20260823_200020_1b6bf5b0.json`)

```json
{
  "run_id": "20260823_200020_1b6bf5b0",
  "status": "completed", "outcome": "succeeded",
  "processed_prs": 2,
  "total_duration_ms": 33780.91,
  "nodes_latency": {
    "analisar_codigo":      { "calls": 2, "avg_ms": 12476.0, "max_ms": 12803.8 },
    "coletar_diff_pr":      { "calls": 2, "avg_ms": 3349.4,  "max_ms": 3832.3 },
    "buscar_prs_pendentes": { "calls": 1, "avg_ms": 2065.8 },
    "sanitizar_diff":       { "calls": 2, "avg_ms": 5.6 },
    "postar_comentario":    { "calls": 2, "avg_ms": 2.1 },
    "resumir_metadados":    { "calls": 2, "avg_ms": 0.1 }
  },
  "llm": { "providers_succeeded": ["Gemini"], "failed_attempts": [], "fallback_count": 0 }
}
```

Leituras de operação possíveis com os dados: ~74% do tempo total é inferência
LLM (`analisar_codigo`), o ramo paralelo de metadados é desprezível (0,1 ms),
e cada iteração do loop custa ~16 s dominadas por rede + LLM.

## 4. Fallback de LLM capturado em execução real

Na primeira validação real (run `20260823_195055_2c2f6c7d`), o modelo então
configurado respondia 404 e o fallback agiu — registrado nos dois sinais:

```jsonl
{"event": "llm_provider_result",  "provider": "Gemini",     "duration_ms": 566,  "error": "404 NOT_FOUND: models/gemini-2.0-flash is no longer available...", ...}
{"event": "llm_provider_success", "provider": "OpenRouter", "duration_ms": 10724, ...}
```

Auditoria correspondente: `"providers_succeeded": ["OpenRouter"]`,
`"failed_attempts": [{provider: Gemini, ...}]`, `"fallback_count": 1`.
A execução terminou `completed/succeeded` com 2 PRs revisados via OpenRouter —
resiliência funcionando exatamente como projetada.

## 5. Ciclo de refinamento orientado por observabilidade (Issue #16)

Exemplo de refinamento documentado conforme exigido pela rubrica
(problema observado → alteração realizada → resultado obtido), com os sinais
como fonte primária de diagnóstico:

### Problema 1 — `outcome: failed` em execução bem-sucedida

- **Observado:** run processou 2 PRs com sucesso, mas a auditoria registrou
  `"outcome": "failed"` e evento `error` espúrio originado de `encerrar_execucao`.
- **Diagnóstico pelos sinais:** o JSONL mostrou `node_end status=error` no nó de
  encerramento sem nenhuma falha real anterior — o nó retornava a mensagem final
  pelo campo `error_message`, que o wrapper interpreta como falha estruturada.
- **Alteração:** novo campo `final_message` no estado; `encerrar_execucao`
  retorna nele a mensagem final; `main.py` exibe esse campo. Erros reais
  continuam em `error_message`.
- **Resultado (run `20260823_200020_1b6bf5b0`):** `"outcome": "succeeded"`,
  `nodes_with_errors: {}` e nenhum `error` espúrio no JSONL.

### Problema 2 — modelo LLM primário descontinuado

- **Observado:** ambas as análises caíram no fallback com `404 NOT_FOUND:
  models/gemini-2.0-flash is no longer available` (modelo aposentado pela Google).
- **Alteração:** modelo Gemini agora configurável via env `GOOGLE_MODEL`
  (padrão `gemini-3.6-flash`, sugerido pela própria API), alinhado à exigência
  de configuração por variável de ambiente; `.env.example` atualizado.
- **Resultado:** execução seguinte completou as duas análises direto no Gemini
  (`llm_provider_success provider=Gemini dur≈10s`, `fallback_count: 0`),
  eliminando a dependência do fallback gratuito.

## 6. Garantias de projeto

- **Thread-safe**: os ramos paralelos do grafo escrevem concorrentemente; todas as escritas usam `threading.Lock`.
- **Observabilidade nunca derruba o fluxo**: toda escrita é *best-effort* — falha de disco/caminho é silenciada e a execução prossegue.
- **Sem segredos**: os artefatos não contêm tokens nem conteúdo de diff completo (apenas contagens e mensagens de erro).
- **`logs/` fora do git** (`.gitignore`): artefatos de runtime não poluem o repositório; evidências selecionadas vão para `docs/evidencias/`.

## 7. Como reproduzir

```bash
# Cenário de falha controlada (não exige chaves):
python main.py "https://github.com/exemplo_repo_invalido"

# Cenário completo real (com chaves configuradas no .env):
python main.py "https://github.com/RSC-SC/testeAgentePR" --dry-run --max-prs 2

# Inspecionar os sinais:
cat logs/run_<run_id>.jsonl
cat logs/audit_<run_id>.json
```
