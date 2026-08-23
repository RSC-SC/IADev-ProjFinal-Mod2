from typing import Dict, Any
from src.state import PRReviewState


def encerrar_execucao(state: PRReviewState) -> Dict[str, Any]:
    total = state.get("processed_prs_count", 0)
    if state.get("error_message"):
        msg = state["error_message"]
    elif state.get("dry_run"):
        msg = (
            f"[DRY-RUN] {total} revisão(ões) gerada(s) e exibida(s) acima. "
            f"NADA foi postado no GitHub — aprove o conteúdo e execute sem "
            f"--dry-run para publicar."
        )
    else:
        msg = f"Revisão concluída. {total} PR(s) processado(s) com sucesso."
    return {"error_message": msg}
