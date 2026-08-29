# Evidência — Démo ao vivo do Agente no PR de Teste (Fase 7 / Vídeo)

> Data: 29/08/2026 · Fluxo completo: **gerar PR de demonstração → agente revisa → posta review real no GitHub**

## Objetivo

Para a gravação do vídeo de apresentação final (Fase 7), foi **simulado um Pull
Request** no repositório de testes e o agente foi executado de ponta a ponta,
**postando** a revisão automaticamente. Esta evidência registra o que foi feito e
o resultado observado.

## 1. PR de demonstração criado

| Campo | Valor |
|-------|-------|
| Repositório | https://github.com/RSC-SC/testeAgentePR |
| **PR** | [#19 — feat: adiciona módulo TextUtils para processamento de texto](https://github.com/RSC-SC/testeAgentePR/pull/19) |
| Branch | `feature/text-utils` |
| Base | `main` |
| Criado | 2026-08-29T19:26:24Z |
| Arquivos | 3 (`text_utils.py`, `test_text_utils.py`, `README.md`) |
| Diff | +102 / −1 (109 linhas) |

O módulo foi construído com **pontos reais de melhoria** (de propósito) para dar
material à revisão do agente: teste de `remover_acentos("OLÁ")` que falha,
mapeamento manual de acentos em vez de `unicodedata`, ausência de type hints,
`.split(" ")` não idiomático e tratamento inconsistente de `None`.

## 2. Execução do agente (modo real — posta no GitHub)

```bash
python main.py https://github.com/RSC-SC/testeAgentePR --max-prs 1
```

### Observabilidade (run `20260829_193149_e49137a3`)

| Métrica | Valor |
|---------|-------|
| Desfecho | `succeeded` · status `completed` |
| PRs processados | 1 (PR #19) |
| Duração total | 24,1 s |
| Análise LLM (Gemini) | 15,96 s |
| Coleta do diff | 2,90 s |
| Listagem de PRs | 2,12 s |
| Postagem do review | 3,07 s |
| Provedor LLM | Gemini (sem fallback, sem erros) |
| Alertas de segurança | 0 |

Artefatos:
- Log estruturado: `logs/run_20260829_193149_e49137a3.jsonl`
- Auditoria: `logs/audit_20260829_193149_e49137a3.json`

## 3. Review postado no PR #19

O agente postou o comentário **"🤖 Revisão Automática de Código"** no PR #19 com:

- **Metadados**: PR #19, 3 arquivos, +102/−1, complexidade média.
- **Pontos positivos**: testes + documentação incluídos; tratamento de `None`/vazio em `normalizar_texto`.
- **Oportunidades de melhoria** (identificadas automaticamente pelo LLM):
  1. **Teste unitário com falha** — `test_remover_acentos_maiusculas` espera `"OLA"` e o código retorna `"OLÁ"`.
  2. **Usar `unicodedata`** no lugar do mapeamento manual de acentos (com código sugerido no payload).
  3. **`.split()` sem argumentos** é mais idiomático que `.split(" ")`.
  4. **Falta de Type Hints** e docstring em `contar_palavras`.
  5. **Tratamento inconsistente de `None`** entre `normalizar_texto` e `remover_acentos`.

> O agente detectou exatamente os problemas plantados — demonstrando valor real do code review automatizado.

## 4. Sequência de segurança (dry-run / autonomia)

Também foi validado em modo **`--dry-run`** (run `20260829_192728_fe6d04ba`):
o review foi **gerado e exibido no console sem postar nada no GitHub**,
confirmando o limite de autonomia (aprovação humana antes de publicar).

## 5. Uso no vídeo

- Roteiro de gravação: `docs/ROTEIRO_VIDEO.md` (material de gravação, fora do versionamento).
- O PR #19 foi criado como alvo fresco de demonstração; como é o PR aberto mais
  recente do repositório, com `--max-prs 1` o agente o revisa primeiro.
