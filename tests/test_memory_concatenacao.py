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


# --------------------------------------------------------------------------- #
# Regressão PR #19: response.content como LISTA de ContentBlocks no RESULTADO
# --------------------------------------------------------------------------- #
# Contexto real (demo do vídeo, PR #19 — testeAgentePR): o Gemini devolveu
# `response.content` como lista de blocos [{"type": "text", "text": "..."}]
# em vez de string. A normalização existente só cobria o histórico; o
# `current_review` ia cru para o post, gerando um markdown "sujo" (repr de
# lista) no comentário do GitHub. Correção: `_as_text` na origem do estado +
# `_review_to_text` defensivo no comment_poster.
class RecordingListModel:
    """ChatModel fake que devolve response.content como LISTA de ContentBlocks
    (o comportamento real observado no PR #19)."""

    def __init__(self, blocks=None):
        self.blocks = blocks or [
            {"type": "text", "text": "## Pontos Positivos\n- Código limpo.\n"}
        ]

    def invoke(self, messages):
        return SimpleNamespace(content=self.blocks)


class TestCurrentReviewNormalizadoParaPostagem:
    def test_analisar_codigo_normaliza_lista_de_blocks(self, monkeypatch):
        """Regressão PR #19: current_review deve vir SEMPRE como markdown string."""
        from src.nodes.code_analyzer import analisar_codigo

        blocks = [
            {"type": "text", "text": "## Pontos Positivos\n- Código limpo.\n"},
            {"type": "text", "text": "## Oportunidades\n- Usar unicodedata.\n"},
        ]
        model = RecordingListModel(blocks)
        monkeypatch.setattr(
            "src.nodes.code_analyzer._get_providers",
            lambda: [("FakeLLM", lambda: model)],
        )

        state = base_state(
            current_pr={"number": 19, "title": "TextUtils"},
            current_diff_sanitized="+x = 1\n",
            review_history=[],
        )

        out = analisar_codigo(state)
        assert isinstance(out["current_review"], str)
        assert out["current_review"] == (
            "## Pontos Positivos\n- Código limpo.\n"
            "## Oportunidades\n- Usar unicodedata.\n"
        )

    def test_analisar_codigo_string_continua_intacta(self, monkeypatch):
        from src.nodes.code_analyzer import analisar_codigo

        model = RecordingModel(content="## ok\n- texto")
        monkeypatch.setattr(
            "src.nodes.code_analyzer._get_providers",
            lambda: [("FakeLLM", lambda: model)],
        )
        state = base_state(
            current_pr={"number": 20, "title": "X"},
            current_diff_sanitized="+x\n",
        )
        out = analisar_codigo(state)
        assert out["current_review"] == "## ok\n- texto"

    def test_postar_comentario_body_limpo_com_review_lista(self, monkeypatch):
        """Regressão PR #19: o BODY montado usa markdown plano, não o repr."""
        from src.nodes.comment_poster import postar_comentario

        posted = []

        class FakeGitHubTool:
            def __init__(self, token):  # noqa: ANN001
                assert token

            def post_comment(self, owner, repo_name, pr_number, body):
                posted.append(body)

        monkeypatch.setattr(
            "src.nodes.comment_poster.GitHubTool", FakeGitHubTool
        )
        monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
        monkeypatch.setenv("GITHUB_TOKEN", "test-token-fake")

        state = base_state(
            repo_owner="RSC-SC",
            repo_name="testeAgentePR",
            current_pr={"number": 19, "title": "TextUtils"},
            current_metadata_summary="- **PR:** #19",
            current_review=[
                {"type": "text", "text": "## Pontos Positivos\n- Código limpo.\n"},
                {"type": "text", "text": "## Oportunidades\n- Usar unicodedata.\n"},
            ],
            current_diff="+x = 1\n",
            dry_run=False,
        )

        out = postar_comentario(state)
        assert out["processed_prs_count"] == 1
        assert len(posted) == 1
        body = posted[0]
        # Não deve conter o repr da lista:
        assert "'type': 'text'" not in body
        assert "extras" not in body
        assert "[{" not in body
        # Deve conter o markdown real:
        assert "## 🤖 Revisão Automática de Código" in body
        assert "## Pontos Positivos" in body
        assert "## Oportunidades" in body
        assert "Usar unicodedata" in body
