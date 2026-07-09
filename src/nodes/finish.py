from typing import Dict, Any
from src.state import PRReviewState


def encerrar_execucao(state: PRReviewState) -> Dict[str, Any]:
    total = state.get("processed_prs_count", 0)
    msg = f"Revisão concluída. {total} PR(s) processado(s) com sucesso."
    if state.get("error_message"):
        msg = state["error_message"]
    return {"error_message": msg}
