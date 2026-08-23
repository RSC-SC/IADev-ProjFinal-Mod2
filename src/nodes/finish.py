from typing import Dict, Any
from src.state import PRReviewState


def encerrar_execucao(state: PRReviewState) -> Dict[str, Any]:
    """Nó terminal: consolida a mensagem FINAL da execução.

    Refinamento (Issue #16): a mensagem final agora retorna em `final_message`,
    não mais em `error_message`. Motivo: o wrapper de observabilidade trata
    `error_message` como falha estruturada; uma execução bem-sucedida era
    registrada com `outcome: failed` na auditoria (falso-positivo).
    Erros REAIS continuam em `error_message` no estado, preservando a lógica
    de propagação entre nós.
    """
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
    return {"final_message": msg}
