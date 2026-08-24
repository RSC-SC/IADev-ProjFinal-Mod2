"""Testes do nó terminal e do wrapper de instrumentação.

PRIORIDADE DE RISCO #4: REGRESSÃO da Issue #16 — a mensagem final vivia em
`error_message`, o que fazia o wrapper auditar execução bem-sucedida como
outcome: failed (falso-positivo). Estes testes travam a semântica:
  - `final_message` = desfecho de negócio (sucesso OU falha);
  - `error_message` = falha estruturada REAL;
  - outcome da auditoria só vira `failed` com erro estruturado.
"""

import json

import pytest
from conftest import base_state

from src.graph import _instrumented
from src.nodes.finish import encerrar_execucao


class TestEncerrarExecucao:
    def test_com_erro_real_final_message_propaga_o_erro(self):
        state = base_state(error_message="Erro ao buscar PRs abertos: X",
                           processed_prs_count=0)
        result = encerrar_execucao(state)
        assert result["final_message"] == "Erro ao buscar PRs abertos: X"

    def test_dry_run_mensagem_explicita_de_nao_postagem(self):
        state = base_state(dry_run=True, error_message="", processed_prs_count=2)
        msg = encerrar_execucao(state)["final_message"]
        assert "[DRY-RUN]" in msg
        assert "NADA foi postado" in msg
        assert "2" in msg

    def test_execucao_normal_mensagem_de_sucesso(self):
        state = base_state(dry_run=False, error_message="",
                           processed_prs_count=3)
        msg = encerrar_execucao(state)["final_message"]
        assert "Revisão concluída" in msg
        assert "3 PR(s)" in msg

    def test_prioridade_erro_sobre_dry_run(self):
        state = base_state(dry_run=True,
                           error_message="falha no meio do lote",
                           processed_prs_count=1)
        assert encerrar_execucao(state)["final_message"] == \
            "falha no meio do lote"


class TestWrapperInstrumentado:
    """_instrumented alimenta os DOIS sinais sem alterar o resultado do nó."""

    @pytest.fixture(autouse=True)
    def _run_aberta(self, fresh_observer):
        """main.py abre os sinais antes do invoke — contrato reproduzido."""
        fresh_observer.start_run(repo_url="https://github.com/a/b")

    def test_no_com_error_message_audita_como_erro(self, fresh_observer):
        def no_que_falha(state):
            return {"error_message": "diff indisponível"}

        wrapped = _instrumented("coletar_diff_pr", no_que_falha)
        out = wrapped(base_state())
        assert out["error_message"] == "diff indisponível"

        paths = fresh_observer.finish_run()
        audit = json.load(open(paths["audit"], encoding="utf-8"))
        assert audit["outcome"] == "failed"
        assert audit["nodes_with_errors"] == {"coletar_diff_pr": 1}

    def test_no_bem_sucedido_com_final_message_NAO_e_falso_positivo(
        self, fresh_observer
    ):
        """REGRESSÃO Issue #16: final_message ≠ erro; outcome deve ser succeeded."""
        def no_terminal_ok(state):
            return {"final_message": "Revisão concluída. 2 PR(s)"}

        wrapped = _instrumented("encerrar_execucao", no_terminal_ok)
        wrapped(base_state())

        paths = fresh_observer.finish_run()
        audit = json.load(open(paths["audit"], encoding="utf-8"))
        assert audit["outcome"] == "succeeded"  # antes do fix: failed
        assert audit["nodes_with_errors"] == {}

    def test_excecao_do_no_repropagada_e_registrada(self, fresh_observer):
        def no_explodindo(state):
            raise ValueError("bug inesperado")

        wrapped = _instrumented("analisar_codigo", no_explodindo)
        with pytest.raises(ValueError):
            wrapped(base_state())
        # o evento exception foi registrado no sinal 1 (JSONL)
        eventos = [
            json.loads(line)
            for line in open(fresh_observer._jsonl_path, encoding="utf-8")
        ]
        fins = [e for e in eventos if e["event"] == "node_end"
                and e.get("node") == "analisar_codigo"]
        assert len(fins) == 1
        assert fins[0]["status"] == "exception"
        assert "bug inesperado" in fins[0]["error"]

    def test_wrapper_nunca_altera_retorno_do_no(self, fresh_observer):
        esperado = {"current_review": "ok", "processed_prs_count": 7}

        def no_normal(state):
            return dict(esperado)

        out = _instrumented("postar_comentario", no_normal)(base_state())
        assert out == esperado

    def test_correlacao_por_pr_number_no_log(self, fresh_observer):
        state = base_state(current_pr={"number": 123, "title": "t"})
        _instrumented("sanitizar_diff", lambda s: {})(state)
        eventos = [
            json.loads(line)
            for line in open(fresh_observer._jsonl_path, encoding="utf-8")
        ]
        assert all(e.get("pr_number") == 123 for e in eventos
                   if e["event"].startswith("node_"))
