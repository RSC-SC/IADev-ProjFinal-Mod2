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
            try:
                audit: Dict[str, Any] = {
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
                        "providers_succeeded": self._llm_providers_used,
                        "failed_attempts": self._llm_failed_attempts,
                        "fallback_count": len(self._llm_failed_attempts),
                    },
                    "security_alerts": self._security_alerts,
                    # Correlação explícita entre os dois sinais:
                    "artifacts": {"structured_log":
                                  _safe_relpath(self._jsonl_path)},
                }
                os.makedirs(self._logs_dir, exist_ok=True)
                with open(self._audit_path, "w", encoding="utf-8") as f:
                    json.dump(audit, f, ensure_ascii=False, indent=2)
            except Exception:
                pass

        return {"structured_log": self._jsonl_path, "audit": self._audit_path}

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
