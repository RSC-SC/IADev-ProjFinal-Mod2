"""Testes da observabilidade (src/tools/observability.py).

PRIORIDADE DE RISCO #2: o RunObserver é singleton compartilhado pelos ramos
PARALELOS do grafo (fan-out analisar_codigo ∥ resumir_metadados). Uma race
condition corromperia o log JSONL; uma exceção de escrita derrubaria a
execução observada. Estes testes travam as duas garantias:
  1. Thread-safety: N threads escrevendo → todas as linhas íntegras;
  2. Best-effort: falha de I/O de log NUNCA propaga exceção.
"""

import json
import threading

from src.tools import observability
from src.tools.observability import RunObserver, get_observer


def read_jsonl(path):
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


class TestCicloDeVida:
    def test_start_run_cria_jsonl_com_run_start(self, tmp_path):
        obs = RunObserver(logs_dir=str(tmp_path / "logs"))
        run_id = obs.start_run(repo_url="https://github.com/a/b", dry_run=False)
        assert run_id == obs.run_id
        assert len(run_id.split("_")) >= 2  # <timestamp>_<uuid8>
        eventos = read_jsonl(obs._jsonl_path)
        assert eventos[0]["event"] == "run_start"
        assert eventos[0]["run_id"] == run_id
        assert "ts" in eventos[0]  # ISO-8601 UTC

    def test_finish_run_grava_auditoria_e_retorna_paths(self, fresh_observer):
        obs = fresh_observer
        obs.start_run(repo_url="https://github.com/a/b")
        paths = obs.finish_run(status="ok", processed_prs=2, final_message="fim")

        audit = json.load(open(paths["audit"], encoding="utf-8"))
        assert audit["status"] == "completed"
        assert audit["outcome"] == "succeeded"
        assert audit["processed_prs"] == 2
        assert audit["final_message"] == "fim"
        # correlação explícita entre os dois sinais (mesmo run_id nos artefatos)
        assert audit["run_id"] == obs.run_id
        assert obs.run_id in audit["artifacts"]["structured_log"]

    def test_outcome_failed_quando_no_sinaliza_erro(self, fresh_observer):
        obs = fresh_observer
        obs.start_run()
        obs.node_finished("analisar_codigo", 100.0, "error", error="boom")
        paths = obs.finish_run()
        audit = json.load(open(paths["audit"], encoding="utf-8"))
        assert audit["outcome"] == "failed"
        assert audit["nodes_with_errors"] == {"analisar_codigo": 1}

    def test_eventos_apos_finish_sao_ignorados(self, fresh_observer):
        obs = fresh_observer
        obs.start_run()
        paths = obs.finish_run()
        antes = len(read_jsonl(paths["structured_log"]))
        obs.log_event("evento_tardio")  # execução já encerrada
        depois = len(read_jsonl(paths["structured_log"]))
        assert antes == depois


class TestAgregacaoAuditoria:
    def test_latencia_por_node_min_media_max(self, fresh_observer):
        obs = fresh_observer
        obs.start_run()
        for d in (30.0, 10.0, 20.0):
            obs.node_finished("coletar_diff_pr", d, "ok")
        paths = obs.finish_run()
        lat = json.load(open(paths["audit"], encoding="utf-8"))["nodes_latency"]
        stats = lat["coletar_diff_pr"]
        assert stats["calls"] == 3
        assert stats["min_ms"] == 10.0
        assert stats["avg_ms"] == 20.0
        assert stats["max_ms"] == 30.0
        assert stats["total_ms"] == 60.0

    def test_fallback_llm_registrado_na_auditoria(self, fresh_observer):
        obs = fresh_observer
        obs.start_run()
        obs.llm_attempt("Gemini", False, 1500.0, error="404 model not found")
        obs.llm_attempt("OpenRouter", True, 900.0)
        paths = obs.finish_run()
        llm = json.load(open(paths["audit"], encoding="utf-8"))["llm"]
        assert llm["providers_succeeded"] == ["OpenRouter"]
        assert llm["fallback_count"] == 1
        assert llm["failed_attempts"][0]["provider"] == "Gemini"

    def test_security_alert_vai_para_os_dois_sinais(self, fresh_observer):
        obs = fresh_observer
        obs.start_run()
        obs.security_alert(42, high_signals=2, medium_signals=1, removed_lines=2)
        paths = obs.finish_run()
        alerts = json.load(open(paths["audit"], encoding="utf-8"))["security_alerts"]
        assert alerts == [
            {"pr_number": 42, "high_signals": 2,
             "medium_signals": 1, "removed_lines": 2}
        ]
        eventos = read_jsonl(paths["structured_log"])
        assert any(e["event"] == "security_alert" and e["pr_number"] == 42
                   for e in eventos)


class TestThreadSafetyEBestEffort:
    def test_escrita_concorrente_nao_perde_nem_corrompe_linhas(
        self, fresh_observer
    ):
        obs = fresh_observer
        obs.start_run()
        n_threads, por_thread = 16, 25

        def worker():
            for i in range(por_thread):
                obs.log_event("evt_paralelo", worker=threading.get_ident(), i=i)

        threads = [threading.Thread(target=worker) for _ in range(n_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        paths = obs.finish_run()  # fecha os sinais
        eventos = read_jsonl(paths["structured_log"])
        paralelos = [e for e in eventos if e["event"] == "evt_paralelo"]
        # TODAS as linhas escritas (nenhuma corrida sobrescreveu/apodreceu)
        assert len(paralelos) == n_threads * por_thread
        assert all(e["run_id"] == obs.run_id for e in paralelos)

    def test_best_effort_diretorio_invalido_nao_levanta_excecao(self, tmp_path):
        bloqueador = tmp_path / "arquivo_bloqueador"
        bloqueador.write_text("x", encoding="utf-8")  # arquivo NO lugar do dir
        obs = RunObserver(logs_dir=str(bloqueador / "subdir_impossivel"))
        obs.start_run()  # não deve levantar apesar de makedirs falhar
        obs.log_event("qualquer")  # nem aqui
        paths = obs.finish_run()  # nem na consolidação da auditoria
        assert "structured_log" in paths

    def test_best_effort_serializacao_da_auditoria_nao_derruba_fluxo(
        self, fresh_observer, monkeypatch
    ):
        def _dump_quebrado(*args, **kwargs):
            raise TypeError("serializacao impossivel")

        monkeypatch.setattr(observability.json, "dump", _dump_quebrado)
        obs = fresh_observer
        obs.start_run()
        paths = obs.finish_run()  # deve engolir a exceção silenciosamente
        assert paths["audit"] != ""


class TestSingleton:
    def test_get_observer_retorna_mesma_instancia(self, monkeypatch):
        original = observability._observer
        try:
            monkeypatch.setattr(observability, "_observer", None)
            assert get_observer() is get_observer()
        finally:
            observability._observer = original
