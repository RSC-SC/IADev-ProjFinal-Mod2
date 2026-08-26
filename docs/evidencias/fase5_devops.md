# ⚙️ Evidência F5 — DevOps Inteligente: pipeline CI + IA analisando logs + anomalia/risco

> **Fase 5** · Issue #7 · critério 13 da rubrica (0,50 pt)
> Pipeline real executado no GitHub Actions + análise de logs por IA (≥2 etapas)
> + detecção de anomalia e estimativa de tendência/risco sobre dados reais.

---

## 1. O pipeline CI (GitHub Actions)

| Item | Valor |
|------|-------|
| Workflow | `.github/workflows/ci.yml` |
| Gatilhos | `push` (main/develop) + `pull_request` → develop |
| Etapas | `lint` (ruff) · `test` (pytest) · `build-validate` (compileall + smoke de importação) |
| Artefatos | Cada etapa salva seu log (`log-lint`, `log-pytest`, `log-build`) |
| Segredos | **Zero** — a suíte é 100% offline (herança da Fase 4) |

**Primeira execução real** — PR [#19](https://github.com/RSC-SC/IADev-ProjFinal-Mod2/pull/19), run
[`32790103818`](https://github.com/RSC-SC/IADev-ProjFinal-Mod2/actions/runs/32790103818):

| Job | Resultado | Início → Fim (UTC) |
|-----|-----------|--------------------|
| Lint (ruff) | ✅ success | 23:36:36 → 23:37:07 (~31s) |
| Testes (pytest) | ✅ success | 23:36:35 → 23:37:01 (~26s) |
| Build e validação | ✅ success | 23:36:35 → 23:36:56 (~21s) |

Decisões de design do pipeline:
- **Etapas paralelas** (jobs independentes): feedback mais rápido; o gate real é o PR verde.
- **Logs como artefatos**: cada etapa faz `tee` do output para um arquivo versionado como
  artefato — é essa matéria-prima que a IA analisa na seção 2.
- **`concurrency` com cancelamento**: pushes sucessivos na mesma branch não acumulam runs.
- **Sem segredos por construção**: os 102 testes usam fakes/mocks (Fase 4), então o CI roda
  em fork/pr sem expor credenciais — superfície de ataque reduzida.

---

## 2. IA analisa os logs das etapas do pipeline

**Método:** os logs brutos dos jobs foram extraídos com `gh run view --log` (225 KB) e as
seções relevantes de cada etapa submetidas à análise da IA orquestradora
(RSC-Orchestrator AI). O prompt utilizado está registrado em
[`docs/prompts.md`](../prompts.md), seção 9. Trechos e leituras abaixo.

### 2.1 Etapa lint (ruff)

Trecho analisado:

```text
Lint (ruff)  Verificar código com ruff   python -m ruff check . 2>&1 | tee lint_output.txt
Lint (ruff)  Verificar código com ruff   All checks passed!
```

**Leitura da IA:**
1. *Zero violações na passada completa* — mas honestidade exige o contexto: o commit que
   tornou isto possível corrigiu 34 apontamentos reais (imports não ordenados, `raise`
   sem `from`, variáveis ambíguas/mortas). Os 68 apontamentos de modernização de type
   hints (PEP 585/604) foram **documentados como dívida consciente** no `pyproject.toml`,
   não escondidos — a config registra o porquê.
2. *Achado secundário no log*: `DeprecationWarning DEP0169 (url.parse)` emitido pelo
   runtime Node **dentro da action `actions/upload-artifact@v4`** — risco de terceiros,
   não de código nosso. Ação sugerida: acompanhar releases da action (baixa prioridade).
   É exatamente o tipo de sinal que passa despercebido sem leitura sistemática de log.

### 2.2 Etapa testes (pytest)

Trecho analisado:

```text
Testes (pytest)  Rodar suíte offline (102 testes)   collecting ... collected 102 items
Testes (pytest)  Rodar suíte offline (102 testes)   ============= 102 passed in 0.94s ==============
```

**Leitura da IA:**
1. **Anomalia de performance ambiente-dependente detectada ao comparar execuções**:
   a suíte roda em **0,94s no runner Linux** vs **~7–9,5s na máquina local Windows**
   (mesmos 102 testes). Hipóteses ordenadas: (a) antivírus com varredura em tempo real
   sobre criação/remoção de arquivos temporários dos fixtures; (b) overhead do sistema
   de arquivos NTFS vs tmpfs/ext4 no `tmp_path`. Conclusão prática: o custo é de
   **ambiente, não do código sob teste** — nenhum teste é lento por si; nenhuma ação no
   CI é necessária (0,94s é desprezível no orçamento do pipeline).
2. **Validação da promessa anti-instabilidade da F4 em máquina virgem**: coleta limpa,
   zero falhas, zero dependência de rede/chaves num ambiente nunca antes usado — os
   fakes/mocks sustentam determinismo fora da máquina de desenvolvimento.
3. `-ra` (do `pytest.ini`) não produziu sumário de skips: nada é pulado condicionalmente
   — a suíte se comporta identicamente em qualquer plataforma.

### 2.3 Etapa build/validação

Trecho analisado:

```text
Build e validação  Instalar dependências de produção   Successfully installed PyGithub-2.10.0 ... langgraph-1.2.11 ... [~50 pacotes]
Build e validação  Smoke de importação                  Grafo compilado: CompiledStateGraph
Build e validação  Salvar log do build como artefato    Final size is 180 bytes
```

**Leitura da IA:**
1. **Contrato de importação saudável**: o grafo compila (`CompiledStateGraph`) numa
   máquina sem `.env`, sem chaves e sem rede — prova que nenhuma credencial é exigida
   em tempo de importação; validação de token fica corretamente em runtime (nó
   `validar_entrada`). Refatorações futuras que violarem esse contrato quebrarão o CI
   aqui, cedo e barato.
2. **Resolução de dependências limpa no Python 3.10.21** — confirma a claim "Python
   3.10+" do README em ambiente controlado (a máquina local usa 3.11.9).
3. `log-build` tem **180 bytes**: `compileall -q` silencioso + linha do smoke — artefato
   mínimo por design; ruído de log ficaria em contradição com a etapa cujo objetivo é
   só provar compilabilidade.

### 2.4 Leitura cruzada das três etapas

- **Tempo de parede total ~35s** com jobs paralelos; dominado por `pip install`
  (~15–20s em cada job). Melhoria futura barata: cache de pip via
  `actions/setup-python` (`cache: pip`) — registrada como oportunidade, não aplicada
  nesta fase para manter o diff focado.
- Nenhuma etapa depende de outra → falha isolada não bloqueia diagnóstico das demais;
  os três artefatos de log permitem pós-mortem mesmo com cancelamento parcial.

---

## 3. Anomalia + tendência + estimativa de risco (dados reais)

Ferramenta: [`scripts/pipeline_log_analyzer.py`](../../scripts/pipeline_log_analyzer.py)
(stdlib pura, também utilizável no CI). Entrada: os **8 sinais de auditoria reais**
(`logs/audit_*.json`) produzidos nas execuções das Fases 3 e 4.

### 3.1 Ciclo de refinamento da própria análise (v1 → v3)

| Versão | Problema encontrado | Correção |
|--------|--------------------|----------|
| v1 (z-score clássico) | Sinalizava **ruído** (`encerrar_execucao`, 0,01 ms, z=−2,65 — precisão float) e **mascarava o outlier real** (`sanitizar_diff` 49,9 ms ficou em z=1,41 porque o próprio outlier infla o desvio-padrão — efeito de mascaramento com amostra pequena, n=3) | v2: z-score **robusto mediana/MAD** + filtro de nós triviais (mediana ≥ 5 ms) |
| v2 | Flag `--exclude` **silenciosamente não excluía nada**: casamento por `startswith("192715")` nunca casa pois o run_id começa com a data (`20260823_...`) | v3: casamento por fragmento contido no run_id — bug pego na validação das 3 visões |

O v1 demonstrou empiricamente o problema metodológico que justifica o método robusto —
a correção não foi especulativa.

### 3.2 Anomalias detectadas nos sinais reais

| # | Nó / Run | Valor vs baseline | z robusto | Interpretação |
|---|----------|-------------------|-----------|---------------|
| 1 | `sanitizar_diff` · run `20260824_114222` | **49,9 ms** vs mediana 9,27 ms | **+7,41** | Mesma run contém **39 sinais de segurança** (diff adversarial do PR #18). Custo cresce com a hostilidade do payload — comportamento projetado, agora quantificado |
| 2 | `buscar_prs_pendentes` · run `20260823_195022` | 1049,8 ms vs mediana 2015 ms | −7,42 | Run com GITHUB_TOKEN 401: caminho de **falha rápida** funcionou (sem retries longos em erro permanente — decisão da Fase 1) |

### 3.3 Tendência (execuções produtivas, ≥1 PR)

Série real: 42,5 s → 33,8 s → 35,1 s → inclinação **−3686,9 ms/execução** (−17,3%,
decrescente); no recorte do estado atual: +4,0% (**estável**). Sem deriva de latência
que indique degradação.

### 3.4 Estimativa de risco — heurística transparente em 3 visões

Pontuação explícita (+1 qualquer falha; +1 taxa >25%; +1 fallback; +1/anomalia, cap 2;
0=BAIXO, 1–2=MÉDIO, ≥3=ALTO):

| Visão | Runs | Taxa de falha | Score | Risco | Leitura honesta |
|-------|------|---------------|-------|-------|-----------------|
| Bruto | 8 | 62,5% | 4 | **ALTO** | Dominado por 4 experimentos intencionais (URL inválida) + 401 + falso-positivo pré-fix |
| Operacional (sem experimentos) | 4 | 50% | 5 | **ALTO** | Ainda carrega problemas já resolvidos no período (token renovado; outcome corrigido no PR #17) |
| Estado atual (pós-refinamentos) | 2 | 0% | 0 | **BAIXO** | Únicas 2 execuções sob a configuração atual: ambas succeeded; anomalia restante é comportamento projetado do sanitizador |

**Conclusão analítica:** o risco bruto alto não descreve o sistema — descreve o
processo de desenvolvimento (experimentos + refinamento). Isolando a configuração
atual, o perfil é BAIXO com tendência estável. Limitação declarada: n=2 no recorte
atual é amostra pequena; o analisador marca os baselines como "não confiáveis" nesse
cenário em vez de inventar confiança estatística.

---

## 4. Reprodução

```bash
# Pipeline: aberto automaticamente a cada PR/push (ver aba Actions)

# Analisador local (3 visões):
python scripts/pipeline_log_analyzer.py                                        # bruto
python scripts/pipeline_log_analyzer.py --exclude 192715 192942 193145 195947  # operacional
python scripts/pipeline_log_analyzer.py --exclude 192715 192942 193145 195947 \
       195022 195055                                                           # estado atual
python scripts/pipeline_log_analyzer.py --json                                 # machine-readable

# Logs brutos do CI (insumo da análise de IA):
gh run view <run_id> --log
```
