"""Regressão do bug de produção: histórico com review em formato de LISTA.

Contexto real: `analisar_codigo` monta o contexto de memória concatenando o
campo `review` do histórico. Quando o LLM (via provider/versão da lib) retorna
o conteúdo como lista de blocos — ex.: [{"type": "text", "text": "..."}] — e
esse vetor era persistido no histórico, a concatenação no nó quebrava com:

    can only concatenate list (not "str") to list

(isso ocorreu em execução real; ver logs/run_20260828_143722_454ca42b.jsonl → run_end crashed).

Correção em duas camadas:
  1. ORIGEM  — save_review normaliza o review para string antes de persistir;
  2. LEITURA — analisar_codigo lê o review de forma defensiva (_as_text),
              mantendo resiliência a históricos já corrompidos no disco.
"""

import json
from types import SimpleNamespace

from conftest import base_state

from src.tools.memory_tool import _review_to_text, save_review


class RecordingModel:
    """ChatModel fake: devolve review fixa e registra as mensagens recebidas."""

    def __init__(self, content="## Pontos Positivos\n- Código limpo.\n"):
        self.content = content
        self.calls = []

    def invoke(self, messages):
        self.calls.append(messages)
        return SimpleNamespace(content=self.content)


# --------------------------------------------------------------------------- #
# Camada de ORIGEM: save_review / _review_to_text
# --------------------------------------------------------------------------- #
class TestSaveReviewNormalizaParaString:
    def test_review_lista_de_blocos_vira_string(self, isolated_memory):
        """response.content em formato [{"type":"text","text":...}] → string."""
        review_list = [
            {"type": "text", "text": "## Pontos Positivos\n- Código limpo.\n"}
        ]
        save_review(
            repo_owner="dono",
            repo_name="repo",
            pr_number=1,
            pr_title="Fix",
            review=review_list,
            diff_summary="+linha",
        )

        path = isolated_memory / "dono_repo" / "history.json"
        dados = json.load(open(path, encoding="utf-8"))
        assert isinstance(dados[0]["review"], str)
        assert "Pontos Positivos" in dados[0]["review"]

    def test_review_lista_com_multiplos_blocos_concatenados(self, isolated_memory):
        review_list = [
            {"type": "text", "text": "A"},
            " -B",
            {"type": "text", "text": "\n"},
        ]
        save_review("dono", "repo", 2, "T", review_list, "sum")
        path = isolated_memory / "dono_repo" / "history.json"
        dados = json.load(open(path, encoding="utf-8"))
        assert dados[0]["review"] == "A -B\n"

    def test_review_string_ja_fica_intacta(self, isolated_memory):
        save_review("dono", "repo", 3, "T", "texto simples", "sum")
        path = isolated_memory / "dono_repo" / "history.json"
        dados = json.load(open(path, encoding="utf-8"))
        assert dados[0]["review"] == "texto simples"

    def test_review_tipos_corrompidos_fallback_string(self):
        assert _review_to_text(None) == "None"
        assert _review_to_text(123) == "123"
        assert _review_to_text("já string") == "já string"


# --------------------------------------------------------------------------- #
# Camada de LEITURA: analisar_codigo resiliente a histórico corrompido
# --------------------------------------------------------------------------- #
class TestAnalisarCodigoResilienteAoHistorico:
    def test_historico_com_review_lista_nao_quebra(self, monkeypatch):
        """Regressão do bug real: review em lista no histórico não derruba o grafo."""
        from src.nodes.code_analyzer import analisar_codigo

        # Provider LLM fake (evita rede/chaves reais)
        model = RecordingModel()
        monkeypatch.setattr(
            "src.nodes.code_analyzer._get_providers",
            lambda: [("FakeLLM", lambda: model)],
        )

        # Histórico com entrada corrompida (review = lista de blocos)
        state = base_state(
            current_pr={"number": 9, "title": "Demo"},
            current_diff_sanitized="+x = 1\n",
            review_history=[
                {
                    "pr_number": 8,
                    "pr_title": "Antigo",
                    "review": [
                        {"type": "text", "text": "## Pontos Positivos\n- ok."}
                    ],
                }
            ],
        )

        # Não deve lançar exceção (era aqui que o crash acontecia)
        out = analisar_codigo(state)
        assert out["current_review"] == model.content

        # E o LLM recebeu o histórico como TEXTO (não quebrou na montagem)
        _, human = model.calls[0]
        assert "Pontos Positivos" in human.content

    def test_historico_misto_string_e_lista(self, monkeypatch):
        from src.nodes.code_analyzer import analisar_codigo

        model = RecordingModel()
        monkeypatch.setattr(
            "src.nodes.code_analyzer._get_providers",
            lambda: [("FakeLLM", lambda: model)],
        )

        state = base_state(
            current_pr={"number": 10, "title": "Demo"},
            current_diff_sanitized="+x = 1\n",
            review_history=[
                {"pr_number": 1, "pr_title": "A",
                 "review": "texto de string normal"},
                {"pr_number": 2, "pr_title": "B",
                 "review": [{"type": "text", "text": "## bloco lista"}]},
            ],
        )

        out = analisar_codigo(state)
        assert out["current_review"] == model.content
        _, human = model.calls[0]
        assert "texto de string normal" in human.content
        assert "## bloco lista" in human.content
