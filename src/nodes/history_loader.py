from typing import Any, Dict

from src.state import PRReviewState
from src.tools.memory_tool import load_history


def carregar_historico(state: PRReviewState) -> Dict[str, Any]:
    history = load_history(state["repo_owner"], state["repo_name"], limit=5)
    return {"review_history": history}
