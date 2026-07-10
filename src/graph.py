from langgraph.graph import StateGraph, END
from src.state import PRReviewState
from src.nodes.validation import validar_entrada
from src.nodes.pr_collector import buscar_prs_pendentes
from src.nodes.pr_collector import coletar_diff_pr
from src.nodes.code_analyzer import analisar_codigo
from src.nodes.comment_poster import postar_comentario
from src.nodes.finish import encerrar_execucao


def _is_valid(state: PRReviewState) -> str:
    if not state.get("is_valid", False) and state.get("error_message"):
        return "encerrar_execucao"
    return "buscar_prs_pendentes"


def _has_pending_prs(state: PRReviewState) -> str:
    if state["pending_prs"]:
        return "coletar_diff_pr"
    return "encerrar_execucao"


def _after_post(state: PRReviewState) -> str:
    if state["pending_prs"]:
        return "coletar_diff_pr"
    return "encerrar_execucao"


def build_graph() -> StateGraph:
    builder = StateGraph(PRReviewState)

    builder.add_node("validar_entrada", validar_entrada)
    builder.add_node("buscar_prs_pendentes", buscar_prs_pendentes)
    builder.add_node("coletar_diff_pr", coletar_diff_pr)
    builder.add_node("analisar_codigo", analisar_codigo)
    builder.add_node("postar_comentario", postar_comentario)
    builder.add_node("encerrar_execucao", encerrar_execucao)

    builder.set_entry_point("validar_entrada")

    builder.add_conditional_edges(
        "validar_entrada",
        _is_valid,
        {"buscar_prs_pendentes": "buscar_prs_pendentes", "encerrar_execucao": "encerrar_execucao"}
    )
    builder.add_conditional_edges(
        "buscar_prs_pendentes",
        _has_pending_prs,
        {"coletar_diff_pr": "coletar_diff_pr", "encerrar_execucao": "encerrar_execucao"}
    )
    builder.add_edge("coletar_diff_pr", "analisar_codigo")
    builder.add_edge("analisar_codigo", "postar_comentario")
    builder.add_conditional_edges(
        "postar_comentario",
        _after_post,
        {"coletar_diff_pr": "coletar_diff_pr", "encerrar_execucao": "encerrar_execucao"}
    )
    builder.add_edge("encerrar_execucao", END)

    return builder.compile()
