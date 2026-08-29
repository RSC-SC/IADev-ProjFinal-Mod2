"""Testes da seleção de provedor LLM primário via LLM_PRIMARY_PROVIDER (Issue #31).

Cobre:
  1. Padrão (sem env / vazio) → Gemini primeiro (comportamento atual);
  2. LLM_PRIMARY_PROVIDER=gemini → Gemini primeiro;
  3. LLM_PRIMARY_PROVIDER=openrouter → OpenRouter primeiro;
  4. Valor inválido → padrão (Gemini primeiro), sem quebrar;
  5. Case-insensitive;
  6. Fallback com ordem invertida: OpenRouter primário falha → Gemini assume;
  7. OpenRouter primário com sucesso → Gemini nem é tentado;
  8. Fluxo completo de analisar_codigo com OpenRouter primário (saída estruturada).
"""

from types import SimpleNamespace

from conftest import base_state

from src.nodes import code_analyzer as ca
from src.nodes.code_analyzer import _invoke_with_fallback, analisar_codigo


class RecordingModel:
    """ChatModel fake: devolve review fixa e registra as mensagens recebidas."""

    def __init__(self, content="## Pontos Positivos\n- Código limpo.\n"):
        self.content = content
        self.calls = []

    def invoke(self, messages):
        self.calls.append(messages)
        return SimpleNamespace(content=self.content)


class ExplodingModel(RecordingModel):
    """Modelo cujo provedor sempre falha (simula quota esgotada / rede fora)."""

    def invoke(self, messages):
        self.calls.append(messages)
        raise ConnectionError("falha simulada no provedor")


def _providers_names():
    return [name for name, _ in ca._get_providers()]


class TestOrdemDosProvedores:
    def test_padrao_sem_env_gemini_primeiro(self, monkeypatch):
        monkeypatch.delenv("LLM_PRIMARY_PROVIDER", raising=False)
        assert _providers_names() == ["Gemini", "OpenRouter"]

    def test_env_vazio_gemini_primeiro(self, monkeypatch):
        monkeypatch.setenv("LLM_PRIMARY_PROVIDER", "")
        assert _providers_names() == ["Gemini", "OpenRouter"]

    def test_env_gemini_explicito(self, monkeypatch):
        monkeypatch.setenv("LLM_PRIMARY_PROVIDER", "gemini")
        assert _providers_names() == ["Gemini", "OpenRouter"]

    def test_env_openrouter_primeiro(self, monkeypatch):
        monkeypatch.setenv("LLM_PRIMARY_PROVIDER", "openrouter")
        assert _providers_names() == ["OpenRouter", "Gemini"]

    def test_env_case_insensitive(self, monkeypatch):
        monkeypatch.setenv("LLM_PRIMARY_PROVIDER", "OpenRouter")
        assert _providers_names() == ["OpenRouter", "Gemini"]

    def test_env_invalido_usa_padrao(self, monkeypatch):
        monkeypatch.setenv("LLM_PRIMARY_PROVIDER", "mistral")
        assert _providers_names() == ["Gemini", "OpenRouter"]


class TestFallbackComOrdemInvertida:
    def test_openrouter_primeiro_sucesso(self, monkeypatch, fresh_observer):
        openrouter_model = RecordingModel("## Pontos Positivos\n- OpenRouter.\n")
        gemini_model = RecordingModel("não deveria ser chamado")
        monkeypatch.setenv("LLM_PRIMARY_PROVIDER", "openrouter")
        monkeypatch.setattr(ca, "_try_openrouter", lambda: openrouter_model)
        monkeypatch.setattr(ca, "_try_gemini", lambda: gemini_model)

        messages = [("system", "x"), ("human", "y")]
        result = _invoke_with_fallback(messages, ca._get_providers())

        assert result == "## Pontos Positivos\n- OpenRouter.\n"
        assert len(gemini_model.calls) == 0  # primário teve sucesso

    def test_openrouter_primeiro_falha_gemini_assume(self, monkeypatch, fresh_observer):
        openrouter_model = ExplodingModel()
        gemini_model = RecordingModel("## Pontos Positivos\n- Gemini fallback.\n")
        monkeypatch.setenv("LLM_PRIMARY_PROVIDER", "openrouter")
        monkeypatch.setattr(ca, "_try_openrouter", lambda: openrouter_model)
        monkeypatch.setattr(ca, "_try_gemini", lambda: gemini_model)

        messages = [("system", "x"), ("human", "y")]
        result = _invoke_with_fallback(messages, ca._get_providers())

        assert result == "## Pontos Positivos\n- Gemini fallback.\n"
        assert len(openrouter_model.calls) == 1  # primário foi tentado e falhou


class TestAnalisarCodigoComOpenRouterPrimario:
    def test_fluxo_completo_saida_estruturada(self, monkeypatch, fresh_observer):
        model = RecordingModel("## Pontos Positivos\n- OK\n")
        monkeypatch.setenv("LLM_PRIMARY_PROVIDER", "openrouter")
        monkeypatch.setattr(ca, "_try_openrouter", lambda: model)
        monkeypatch.setattr(ca, "_try_gemini", lambda: model)

        state = base_state(
            current_pr={"number": 21, "title": "Demo DateHandler"},
            current_diff_sanitized="+def hoje():\n+    return date.today()\n",
            review_history=[],
        )
        out = analisar_codigo(state)

        # Mesmo contrato estabelecido na Issue #27: current_review é markdown plano
        assert out["current_review"] == "## Pontos Positivos\n- OK\n"
