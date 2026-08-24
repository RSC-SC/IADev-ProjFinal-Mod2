"""Fixtures compartilhadas da suíte de QA do Agente Revisor de PRs.

Gerada/refinada com IA na Fase 4 (QA Inteligente — Issue #6).
Processo documentado em docs/qa/processo_qa_ia.md.

Garantias da suíte:
- ZERO rede: LLM e API GitHub são sempre mockados (testes determinísticos);
- ZERO efeito colateral: logs/observabilidade e histórico de revisões são
  redirecionados para diretórios temporários via fixtures;
- Isolamento do singleton de observabilidade entre testes.
"""

import sys
from pathlib import Path

import pytest

# Garante que o pacote `src` seja importável a partir de qualquer CWD
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.tools.observability import RunObserver  # noqa: E402


@pytest.fixture
def fresh_observer(tmp_path, monkeypatch):
    """RunObserver isolado gravando em tmp_path, injetado em TODOS os
    namespaces que referenciam get_observer (o grafo importa por valor)."""
    obs = RunObserver(logs_dir=str(tmp_path / "logs"))

    def _fake_get():
        return obs

    monkeypatch.setattr("src.tools.observability.get_observer", _fake_get)
    monkeypatch.setattr("src.graph.get_observer", _fake_get, raising=False)
    monkeypatch.setattr(
        "src.nodes.diff_sanitizer.get_observer", _fake_get, raising=False
    )
    monkeypatch.setattr(
        "src.nodes.code_analyzer.get_observer", _fake_get, raising=False
    )
    return obs


@pytest.fixture
def llm_env(monkeypatch):
    """Ambiente mínimo para validar_entrada passar SEM chaves reais."""
    monkeypatch.setenv("GITHUB_TOKEN", "test-token-fake")
    monkeypatch.setenv("GOOGLE_API_KEY", "test-google-key")
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)


@pytest.fixture
def isolated_memory(tmp_path, monkeypatch):
    """Redireciona o histórico de revisões (reviews/) para tmp_path."""
    import src.tools.memory_tool as memory_tool

    reviews_dir = tmp_path / "reviews"
    monkeypatch.setattr(memory_tool, "REVIEWS_DIR", str(reviews_dir))
    return reviews_dir


def base_state(**overrides):
    """Estado inicial completo (mesma forma usada pelo main.py)."""
    state = {
        "repo_url": "https://github.com/dono/repositorio",
        "repo_owner": "",
        "repo_name": "",
        "is_valid": True,
        "error_message": "",
        "pending_prs": [],
        "current_pr": {},
        "current_diff": "",
        "current_diff_sanitized": "",
        "security_report": {},
        "current_review": "",
        "current_metadata_summary": "",
        "processed_prs_count": 0,
        "max_prs": 3,
        "dry_run": False,
        "review_history": [],
        "final_message": "",
    }
    state.update(overrides)
    return state
