"""Observabilidade do Agente Revisor de PRs — DOIS sinais correlacionados.

Requisito 4.6 do Projeto Final: produzir e correlacionar pelo menos dois
sinais de observabilidade, sendo um deles logs estruturados.

Sinal 1 — LOG ESTRUTURADO (JSONL): ``logs/run_<run_id>.jsonl``
    Um evento JSON por linha, todos contendo ``run_id`` e ``ts`` (ISO-8601 UTC)
    e, quando aplicável, ``node`` e ``pr_number``. Permite reconstruir a
    sequência exata de nodes, decisões, erros e latências da execução.

Sinal 2 — REGISTRO DE AUDITORIA: ``logs/audit_<run_id>.json``
    Registro consolidado da execução: latência total e por node (mín/média/máx),
    provedores LLM utilizados e fallbacks, alertas de segurança, PRs processados,
    modo de autonomia e o caminho do log JSONL do MESMO run_id — correlação
    explícita entre os dois sinais.

Garantias:
- Thread-safe: os ramos paralelos do grafo (analisar_codigo / resumir_metadados)
  escrevem concorrentemente; todas as escritas são protegidas por Lock.
- Best-effort: falha de escrita de log/auditoria NUNCA propaga exceção para o
  grafo — observabilidade não pode derrubar a execução que ela observa.
"""

import json
import os
import threading
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

LOGS_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "logs")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def _safe_relpath(path: str) -> str:
    """Caminho relativo ao CWD; absoluto se atravessar unidades (C: vs E:)."""
    try:
        return os.path.relpath(path)
    except ValueError:
        return path


class RunObserver:
    """Ciclo de vida dos sinais de uma execução do agente.

    Uso típico:
        observer = get_observer()
        observer.start_run(repo_url=..., dry_run=..., max_prs=...)
        ... (nodes instrumentados emitem eventos automaticamente) ...
        observer.finish_run(status=..., processed_prs=..., final_message=...)
    """

    def __init__(self, logs_dir: str = LOGS_DIR):
        self._logs_dir = os.path.abspath(logs_dir)
        self._lock = threading.Lock()
        self._active = False

        self.run_id: str = ""
        self._jsonl_path: str = ""
        self._audit_path: str = ""
        self._t0_perf: float = 0.0
        self._started_iso: str = ""
        self._repo_url: str = ""

        # Agregações para a auditoria (sinal 2)
        self._node_latencies: Dict[str, List[float]] = {}
        self._nodes_with_errors: Dict[str, int] = {}
        self._llm_providers_used: List[str] = []
        self._llm_failed_attempts: List[Dict[str, Any]] = []
        self._security_alerts: List[Dict[str, Any]] = []

    # ------------------------------------------------------------------ #
    # Ciclo de vida
    # ------------------------------------------------------------------ #
    def start_run(self, repo_url: str = "", dry_run: bool = False,
                  max_prs: int = 0) -> str:
        """Abre os dois sinais para uma nova execução e retorna o run_id."""
        with self._lock:
            stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            self.run_id = f"{stamp}_{uuid.uuid4().hex[:8]}"
            self._jsonl_path = os.path.join(
                self._logs_dir, f"run_{self.run_id}.jsonl"
            )
            self._audit_path = os.path.join(
                self._logs_dir, f"audit_{self.run_id}.json"
            )
            self._t0_perf = time.perf_counter()
            self._started_iso = _now_iso()
            self._repo_url = repo_url
            self._node_latencies = {}
            self._nodes_with_errors = {}
            self._llm_providers_used = []
            self._llm_failed_attempts = []
            self._security_alerts = []
            self._active = True

        self.log_event("run_start", repo_url=repo_url, dry_run=dry_run,
                       max_prs=max_prs)
        return self.run_id

    def finish_run(self, status: str = "ok", processed_prs: int = 0,
                   final_message: str = "", repo_owner: str = "",
                   repo_name: str = "") -> Dict[str, str]:
        """Consolida a auditoria (sinal 2), emite run_end e devolve os caminhos.

        Semântica dos campos de resultado:
        - ``status``  : ciclo de vida da execução → "completed" | "crashed"
        - ``outcome`` : desfecho de negócio → "succeeded" | "failed"
          (falhou se QUALQUER nó sinalizou erro estruturado)
        """
        total_ms = round((time.perf_counter() - self._t0_perf) * 1000, 2)

        self.log_event("run_end", status=status, total_duration_ms=total_ms,
                       processed_prs=processed_prs)

        # Best-effort TOTAL: qualquer falha ao consolidar a auditoria
        # (construção, serialização ou escrita) jamais derruba o fluxo.
        with self._lock:
            self._active = False
            audit: Dict[str, Any] = {}
            try:
                audit = {
                    "run_id": self.run_id,
                    "started_at": self._started_iso,
                    "finished_at": _now_iso(),
                    "total_duration_ms": total_ms,
                    "status": "completed" if status == "ok" else "crashed",
                    "outcome": (
                        "failed" if self._nodes_with_errors else "succeeded"
                    ),
                    "processed_prs": processed_prs,
                    "final_message": final_message,
                    "repo": {"url": self._repo_url, "owner": repo_owner,
                             "name": repo_name},
                    "nodes_latency": {
                        name: {
                            "calls": len(values),
                            "min_ms": round(min(values), 2),
                            "avg_ms": round(sum(values) / len(values), 2),
                            "max_ms": round(max(values), 2),
                            "total_ms": round(sum(values), 2),
                        }
                        for name, values in sorted(self._node_latencies.items())
                    },
                    "nodes_with_errors": dict(
                        sorted(self._nodes_with_errors.items())
                    ),
                    "llm": {
                        "providers_succeeded": list(self._llm_providers_used),
                        "failed_attempts": list(self._llm_failed_attempts),
                        "fallback_count": len(self._llm_failed_attempts),
                    },
                    "security_alerts": list(self._security_alerts),
                    # Correlação explícita entre os dois sinais:
                    "artifacts": {"structured_log":
                                  _safe_relpath(self._jsonl_path)},
                }
                os.makedirs(self._logs_dir, exist_ok=True)
                with open(self._audit_path, "w", encoding="utf-8") as f:
                    json.dump(audit, f, ensure_ascii=False, indent=2)
            except Exception:
                pass

        return {
            "structured_log": self._jsonl_path,
            "audit": self._audit_path,
            "audit_data": audit,
        }

    # ------------------------------------------------------------------ #
    # Eventos dos nós (instrumentação central no grafo)
    # ------------------------------------------------------------------ #
    def node_started(self, node: str, pr_number: Optional[int] = None) -> None:
        self.log_event("node_start", node=node, pr_number=pr_number)

    def node_finished(self, node: str, duration_ms: float, status: str,
                      pr_number: Optional[int] = None, error: str = "") -> None:
        with self._lock:
            if self._active:
                self._node_latencies.setdefault(node, []).append(duration_ms)
                if status != "ok":
                    self._nodes_with_errors[node] = (
                        self._nodes_with_errors.get(node, 0) + 1
                    )
        self.log_event(
            "node_end", node=node, duration_ms=round(duration_ms, 2),
            status=status, pr_number=pr_number, error=error,
        )

    def log_error(self, source: str, message: str,
                  pr_number: Optional[int] = None) -> None:
        """Erro de negócio tratado por um nó (falha estruturada, sem traceback)."""
        self.log_event("error", node=source, message=message,
                       pr_number=pr_number)

    # ------------------------------------------------------------------ #
    # Eventos de domínio
    # ------------------------------------------------------------------ #
    def llm_attempt(self, provider: str, ok: bool, duration_ms: float,
                    error: str = "") -> None:
        """Resultado de uma tentativa de provedor LLM (fallback visível)."""
        with self._lock:
            if ok and provider not in self._llm_providers_used:
                self._llm_providers_used.append(provider)
            if not ok:
                self._llm_failed_attempts.append({
                    "provider": provider,
                    "duration_ms": round(duration_ms, 2),
                    "error": error[:300],
                })
        self.log_event(
            "llm_provider_result" if not ok else "llm_provider_success",
            provider=provider, duration_ms=round(duration_ms, 2),
            error=error[:300] if error else "",
        )

    def security_alert(self, pr_number: Optional[int], high_signals: int,
                       medium_signals: int, removed_lines: int) -> None:
        """Sinais de prompt-injection neutralizados pelo sanitizador."""
        with self._lock:
            self._security_alerts.append({
                "pr_number": pr_number,
                "high_signals": high_signals,
                "medium_signals": medium_signals,
                "removed_lines": removed_lines,
            })
        self.log_event(
            "security_alert", pr_number=pr_number, high_signals=high_signals,
            medium_signals=medium_signals, removed_lines=removed_lines,
        )

    # ------------------------------------------------------------------ #
    # Escrita base do sinal 1 (JSONL) — thread-safe e best-effort
    # ------------------------------------------------------------------ #
    def log_event(self, event: str, **fields: Any) -> None:
        record: Dict[str, Any] = {
            "ts": _now_iso(),
            "run_id": self.run_id,
            "event": event,
        }
        record.update({k: v for k, v in fields.items() if v is not None})
        line = json.dumps(record, ensure_ascii=False)

        with self._lock:
            if not self._active and event != "run_end":
                return  # execução já encerrada: ignora eventos tardios
            try:
                os.makedirs(self._logs_dir, exist_ok=True)
                with open(self._jsonl_path, "a", encoding="utf-8") as f:
                    f.write(line + "\n")
            except OSError:
                pass  # best-effort


# Singleton do processo: nodes e tools compartilham a mesma execução.
_observer: Optional[RunObserver] = None
_observer_lock = threading.Lock()


def get_observer() -> RunObserver:
    global _observer
    with _observer_lock:
        if _observer is None:
            _observer = RunObserver()
        return _observer


def format_terminal_report(
    audit: Dict[str, Any],
    processed_reviews: Optional[List[Dict[str, Any]]] = None,
    history_path: str = "",
) -> str:
    """Gera um relatório completo e estruturado para exibição no terminal.

    Seções geradas:
    1. 📊 RESUMO DA EXECUÇÃO
    2. ⏱️ LATÊNCIA POR NÓ NO GRAFO
    3. 🤖 REVISÃO PUBLICADA NO PR
    4. 📁 ARTEFATOS DE OBSERVABILIDADE GERADOS
    """
    reviews = processed_reviews or []
    lines: List[str] = []
    sep_double = "=" * 70
    sep_single = "-" * 70

    # 1. Resumo da Execução
    lines.append(sep_double)
    lines.append("📊 RESUMO DA EXECUÇÃO")
    lines.append(sep_double)

    repo_info = audit.get("repo", {}) or {}
    repo_url = repo_info.get("url") or "N/A"
    status = audit.get("status", "unknown")
    outcome = audit.get("outcome", "unknown")
    processed_count = audit.get("processed_prs", 0)
    total_ms = audit.get("total_duration_ms", 0.0)
    duration_s = round(total_ms / 1000.0, 2)

    llm_info = audit.get("llm", {}) or {}
    providers = ", ".join(llm_info.get("providers_succeeded", [])) or "Nenhum"
    fallbacks = llm_info.get("fallback_count", 0)
    alerts_count = len(audit.get("security_alerts", []) or [])

    lines.append(f"• Repositório:         {repo_url}")
    lines.append(f"• Status / Desfecho:   {status} · {outcome}")
    lines.append(f"• PR(s) Processado(s): {processed_count}")
    lines.append(f"• Duração Total:       {duration_s}s ({total_ms:.1f} ms)")
    lines.append(f"• Provedor(es) LLM:    {providers} (fallbacks: {fallbacks})")
    lines.append(f"• Alertas Segurança:   {alerts_count}")

    # 2. Latência por Nó no Grafo
    lines.append("\n" + sep_single)
    lines.append("⏱️ LATÊNCIA POR NÓ NO GRAFO")
    lines.append(sep_single)

    nodes_latency = audit.get("nodes_latency", {}) or {}
    if nodes_latency:
        lines.append(f"{'Nó':<26} {'Chamadas':>8} {'Média (ms)':>12} {'Total (ms)':>12}")
        lines.append("-" * 62)
        for node_name, stats in nodes_latency.items():
            calls = stats.get("calls", 0)
            avg_ms = stats.get("avg_ms", 0.0)
            node_total = stats.get("total_ms", 0.0)
            lines.append(f"{node_name:<26} {calls:>8} {avg_ms:>12.2f} {node_total:>12.2f}")
    else:
        lines.append("• Nenhum nó registrado com métricas de latência.")

    # 3. Revisão Publicada no PR
    lines.append("\n" + sep_single)
    lines.append("🤖 REVISÃO PUBLICADA NO PR")
    lines.append(sep_single)

    if reviews:
        for idx, item in enumerate(reviews, 1):
            pr_num = item.get("pr_number") or "?"
            pr_title = item.get("pr_title") or ""
            is_dry = item.get("dry_run", False)
            mode_str = "[DRY-RUN] Simulação — Não postado no GitHub" if is_dry else "[PUBLICADO] Postado no GitHub via API"

            title_part = f" — {pr_title}" if pr_title else ""
            lines.append(f"PR #{pr_num}{title_part}")
            lines.append(f"Status: {mode_str}")

            metadata = str(item.get("metadata", "") or "").strip()
            if metadata:
                lines.append(f"Metadados: {metadata}")

            review_text = str(item.get("review", "") or "").strip()
            if review_text:
                lines.append("\n" + review_text)

            if idx < len(reviews):
                lines.append("\n" + "~" * 50)
    else:
        lines.append("• Nenhuma revisão gerada para publicação nesta execução.")

    # 4. Artefatos de Observabilidade Gerados
    lines.append("\n" + sep_single)
    lines.append("📁 ARTEFATOS DE OBSERVABILIDADE GERADOS")
    lines.append(sep_single)

    artifacts = audit.get("artifacts", {}) or {}
    log_path = artifacts.get("structured_log") or "N/A"
    lines.append(f"• Log Estruturado (JSONL) : {log_path}")
    if "audit_path" in audit and audit["audit_path"]:
        lines.append(f"• Auditoria e Métricas   : {audit['audit_path']}")
    if history_path:
        lines.append(f"• Histórico de Revisões   : {history_path}")

    final_msg = audit.get("final_message", "")
    if final_msg:
        lines.append("\n" + sep_double)
        lines.append(f"Mensagem Final: {final_msg}")
        lines.append(sep_double)

    return "\n".join(lines)

