"""Analisador de sinais de execucao do agente (Fase 5 - DevOps Inteligente).

Consome os sinais de observabilidade da Fase 3 (``logs/audit_*.json``) e produz:

1. Inventario das execucoes (outcome, PRs, duracao, fallback, alertas de seguranca);
2. Baseline de latencia por no entre execucoes (media +- desvio-padrao);
3. Deteccao de anomalias por z-score (|z| >= Z_THRESHOLD, com amostra minima);
4. Tendencia da duracao total (regressao linear simples sobre as execucoes que
   processaram >= 1 PR -- validacoes abortadas em milissegundos poluiriam a serie);
5. Estimativa HEURISTICA e TRANSPARENTE de risco de falha, calculavel sobre o
   conjunto completo ou sobre um subconjunto operacional via ``--exclude``
   (execucoes experimentais documentadas na evidencia da Fase 3).

Uso::

    python scripts/pipeline_log_analyzer.py
    python scripts/pipeline_log_analyzer.py --exclude 192715 192942 193145 195947 195055
    python scripts/pipeline_log_analyzer.py --json

Sem dependencias externas (stdlib pura) -- roda localmente e no CI.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

# --- Parametros da analise (explicitos p/ auditoria) -------------------------
Z_THRESHOLD = 2.0          # |z| >= 2 -> ~95% de significancia bilateral
MIN_SAMPLES = 3            # minimo de amostras p/ baseline confiavel por no
MIN_NODE_MEDIAN_MS = 5.0   # nos abaixo disso sao deterministicos/sub-ruído:
                           # variancia nao tem significado operacional e o
                           # z-score so captura ruido de precisao (falso +
                           # na v1: "anomalia" de 0.01 ms em encerrar_execucao).
                           # Na pratica separa nos de rede/LLM (>1 s) e o
                           # sanitizador (~9 ms) dos nos triviais (<2 ms).
RISK_ANOMALY_CAP = 2       # anomalias nao devem dominar o score de risco

LOGS_DIR = Path("logs")


# --- Carga -------------------------------------------------------------------
def load_audits(logs_dir: Path) -> list[dict]:
    """Carrega todos os audit_*.json ordenados cronologicamente (run_id)."""
    audits = []
    for path in sorted(logs_dir.glob("audit_*.json")):
        with path.open(encoding="utf-8") as fh:
            data = json.load(fh)
        sec_high = sum(int(a.get("high_signals", 0)) for a in data.get("security_alerts", []))
        audits.append(
            {
                "run_id": data.get("run_id", path.stem),
                "started_at": data.get("started_at", ""),
                "outcome": data.get("outcome", ""),
                "processed_prs": int(data.get("processed_prs", 0)),
                "total_duration_ms": float(data.get("total_duration_ms", 0.0)),
                "fallback_count": int(data.get("llm", {}).get("fallback_count", 0)),
                "sec_high": sec_high,
                "nodes_latency": {
                    name: float(v.get("avg_ms", 0.0))
                    for name, v in data.get("nodes_latency", {}).items()
                },
                "_file": str(path),
            }
        )
    return audits


def filter_excluded(audits: list[dict], exclude_fragments: list[str]) -> tuple[list[dict], set[str]]:
    """Separa execucoes excluidas do subconjunto ativo.

    O casamento e por FRAGMENTO contido no run_id (formato
    ``AAAAMMDD_HHMMSS_hash``): passar ``192715`` exclui qualquer run cujo
    horario seja 19:27:15, independentemente da data.
    """
    active = [
        a for a in audits
        if not any(f and f in a["run_id"] for f in exclude_fragments)
    ]
    excluded = {a["run_id"] for a in audits if a not in active}
    return active, excluded


# --- Estatistica -------------------------------------------------------------
def _mean(xs: list[float]) -> float:
    return sum(xs) / len(xs)


def _pstdev(xs: list[float], mu: float) -> float:
    return math.sqrt(sum((x - mu) ** 2 for x in xs) / len(xs))


def _median(xs: list[float]) -> float:
    s = sorted(xs)
    n = len(s)
    mid = n // 2
    return s[mid] if n % 2 else (s[mid - 1] + s[mid]) / 2


def _mad(xs: list[float], med: float) -> float:
    """Desvio absoluto mediano (MAD) -- estatistica robusta a outliers."""
    return _median([abs(x - med) for x in xs])


def build_baseline(active: list[dict]) -> dict[str, dict]:
    """Baseline de latencia media por no (media/desvio descritivos + mediana/MAD
    para o teste de anomalia, robusto quando a amostra e pequena).

    Motivacao (refinamento da v1): com n=3 execucoes, um unico outlier infla o
    desvio-padrao e ESCAPA da propria deteccao (efeito de mascaramento) --
    sanitizar_diff=49,9 ms produziu z=1,41 com z-score classico. O z robusto
    baseado em mediana/MAD nao sofre desse efeito.
    """
    baseline = {}
    all_nodes = sorted({n for a in active for n in a["nodes_latency"]})
    for node in all_nodes:
        samples = [a["nodes_latency"][node] for a in active if node in a["nodes_latency"]]
        mu = _mean(samples)
        med = _median(samples)
        mad = _mad(samples, med)
        baseline[node] = {
            "samples": len(samples),
            "mean_ms": mu,
            "std_ms": _pstdev(samples, mu),
            "median_ms": med,
            "mad_ms": mad,
            "reliable": len(samples) >= MIN_SAMPLES and med >= MIN_NODE_MEDIAN_MS,
        }
    return baseline


def detect_anomalies(active: list[dict], baseline: dict[str, dict]) -> list[dict]:
    """Anomalias por z-score ROBUSTO (0.6745*(x-mediana)/MAD) nos nos com
    baseline suficiente (amostra minima + mediana acima do ruido)."""
    found = []
    for a in active:
        for node, value in a["nodes_latency"].items():
            base = baseline[node]
            if not base["reliable"] or base["mad_ms"] == 0:
                continue
            z = 0.6745 * (value - base["median_ms"]) / base["mad_ms"]
            if abs(z) >= Z_THRESHOLD:
                found.append(
                    {
                        "run_id": a["run_id"],
                        "node": node,
                        "value_ms": value,
                        "baseline_median_ms": round(base["median_ms"], 2),
                        "z": round(z, 2),
                        "same_run_sec_high": a["sec_high"],
                    }
                )
    return sorted(found, key=lambda f: abs(f["z"]), reverse=True)


def linear_trend(durations_ms: list[float]) -> dict:
    """Inclinacao (ms por execucao) e variacao percentual primeira->ultima."""
    n = len(durations_ms)
    if n < 2:
        return {"samples": n, "slope_ms_per_run": None, "pct_change": None}
    xs = list(range(n))
    mx, my = _mean([float(x) for x in xs]), _mean(durations_ms)
    denom = sum((x - mx) ** 2 for x in xs)
    slope = sum((x - mx) * (y - my) for x, y in zip(xs, durations_ms, strict=True)) / denom
    pct = (durations_ms[-1] - durations_ms[0]) / durations_ms[0] * 100
    return {"samples": n, "slope_ms_per_run": round(slope, 1), "pct_change": round(pct, 1)}


def estimate_risk(active: list[dict], anomalies: list[dict]) -> dict:
    """Estimativa de risco com pontuacao explicita (auditoravel).

    Pontuacao:
      +1 se ha qualquer falha; +1 adicional se failure_rate > 25%;
      +1 se alguma execucao usou fallback (instabilidade do provedor primario);
      +1 por anomalia detectada, limitada a RISK_ANOMALY_CAP.
    Niveis: 0 = BAIXO | 1..2 = MEDIO | >=3 = ALTO.
    """
    total = len(active)
    failures = sum(1 for a in active if a["outcome"] == "failed")
    failure_rate = failures / total if total else 0.0
    used_fallback = any(a["fallback_count"] > 0 for a in active)

    points = 0
    reasons = []
    if failures > 0:
        points += 1
        reasons.append(f"falhas no periodo: {failures}/{total}")
    if failure_rate > 0.25:
        points += 1
        reasons.append(f"taxa de falha {failure_rate:.0%} > 25%")
    if used_fallback:
        points += 1
        reasons.append("fallback de LLM acionado em >= 1 execucao")
    anomaly_points = min(len(anomalies), RISK_ANOMALY_CAP)
    if anomaly_points:
        points += anomaly_points
        reasons.append(f"anomalias de latencia: {len(anomalies)} (pontua ate {RISK_ANOMALY_CAP})")

    level = "BAIXO" if points == 0 else ("MEDIO" if points <= 2 else "ALTO")
    return {
        "points": points,
        "level": level,
        "reasons": reasons,
        "failure_rate": round(failure_rate, 3),
        "runs_evaluated": total,
        "anomalies_count": len(anomalies),
    }


# --- Saida -------------------------------------------------------------------
def render_report(audits, active, excluded_ids, baseline, anomalies, trend_work, risk) -> str:
    lines = []
    add = lines.append
    add("=" * 78)
    add("ANALISE DE LOGS E RISCO - Agente Revisor de PRs (Fase 5)")
    add("=" * 78)

    add("")
    add(f"[1] INVENTARIO DE EXECUCOES: {len(audits)} sinais ({len(excluded_ids)} excluida(s) da analise)")
    add("-" * 78)
    for a in audits:
        tag = " (EXCLUIDA)" if a["run_id"] in excluded_ids else ""
        add(
            f"  {a['run_id']} | outcome={a['outcome'] or '(vazio)':10} | prs={a['processed_prs']} "
            f"| {a['total_duration_ms']:>9.0f} ms | fallback={a['fallback_count']} "
            f"| sec_high={a['sec_high']}{tag}"
        )

    add("")
    add(f"[2] BASELINE DE LATENCIA POR NO (n >= {MIN_SAMPLES} E mediana >= {MIN_NODE_MEDIAN_MS:.0f} ms => confiavel)")
    add("-" * 78)
    for node, b in baseline.items():
        rel = "sim" if b["reliable"] else "nao"
        add(
            f"  {node:22} media={b['mean_ms']:>10.1f} ms  mediana={b['median_ms']:>9.1f} ms"
            f"  MAD={b['mad_ms']:>8.1f} ms  n={b['samples']}  confiavel={rel}"
        )

    add("")
    add(f"[3] ANOMALIAS DETECTADAS (z robusto |0.6745*(x-med)/MAD| >= {Z_THRESHOLD})")
    add("-" * 78)
    if not anomalies:
        add("  Nenhuma anomalia com baseline suficiente.")
    for f in anomalies:
        ctx = f" [mesma run com {f['same_run_sec_high']} sinal(is) de seguranca]" if f["same_run_sec_high"] else ""
        add(
            f"  {f['run_id']} | {f['node']:20} {f['value_ms']:>9.1f} ms "
            f"(mediana {f['baseline_median_ms']:>9.2f} ms) | z={f['z']}{ctx}"
        )

    add("")
    add("[4] TENDENCIA DA DURACAO TOTAL (somente execucoes com >= 1 PR processado)")
    add("-" * 78)
    if trend_work["slope_ms_per_run"] is None:
        add("  Amostra insuficiente para tendencia.")
    else:
        direction = "estavel" if abs(trend_work["pct_change"]) < 15 else (
            "crescente" if trend_work["pct_change"] > 0 else "decrescente"
        )
        add(
            f"  n={trend_work['samples']} execucoes produtivas | inclinacao="
            f"{trend_work['slope_ms_per_run']} ms/execucao | variacao "
            f"primeira->ultima = {trend_work['pct_change']}% ({direction})"
        )

    add("")
    add("[5] ESTIMATIVA DE RISCO DE FALHA (heuristica transparente)")
    add("-" * 78)
    add(f"  Conjunto avaliado : {risk['runs_evaluated']} execucao(oes)")
    add(f"  Taxa de falha     : {risk['failure_rate']:.1%}")
    for reason in risk["reasons"]:
        add(f"  - criterio: {reason}")
    add(f"  PONTUACAO: {risk['points']} => RISCO {risk['level']}")
    add("=" * 78)
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--logs-dir", type=Path, default=LOGS_DIR)
    parser.add_argument(
        "--exclude",
        nargs="*",
        default=[],
        help="fragmentos de run_id (ex.: horario 192715) a excluir da analise "
             "(experimentos documentados)",
    )
    parser.add_argument("--json", action="store_true", help="saida em JSON")
    args = parser.parse_args(argv)

    if not args.logs_dir.exists():
        print(f"ERRO: diretorio de logs inexistente: {args.logs_dir}", file=sys.stderr)
        return 2

    audits = load_audits(args.logs_dir)
    if not audits:
        print("Nenhum audit_*.json encontrado; nada a analisar.", file=sys.stderr)
        return 2

    active, excluded_ids = filter_excluded(audits, args.exclude)
    baseline = build_baseline(active)
    anomalies = detect_anomalies(active, baseline)

    work_durations = [a["total_duration_ms"] for a in active if a["processed_prs"] >= 1]
    trend_work = linear_trend(work_durations)
    risk = estimate_risk(active, anomalies)

    if args.json:
        payload = {
            "inventory": [{k: v for k, v in a.items() if k != "_file"} for a in audits],
            "excluded_run_ids": sorted(excluded_ids),
            "baseline": baseline,
            "anomalies": anomalies,
            "trend_productive_runs": trend_work,
            "risk": risk,
        }
        print(json.dumps(payload, ensure_ascii=True, indent=2))
    else:
        print(render_report(audits, active, excluded_ids, baseline, anomalies, trend_work, risk))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
