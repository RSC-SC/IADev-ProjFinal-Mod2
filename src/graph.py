from langgraph.graph import StateGraph, END
from src.state import PRReviewState
from src.nodes.validation import validar_entrada
from src.nodes.pr_collector import buscar_prs_pendentes
from src.nodes.pr_collector import coletar_diff_pr
from src.nodes.diff_sanitizer import sanitizar_diff
from src.nodes.code_analyzer import analisar_codigo
from src.nodes.metadata_summarizer import resumir_metadados
from src.nodes.comment_poster import postar_comentario
from src.nodes.finish import encerrar_execucao
from src.nodes.history_loader import carregar_historico


def _is_valid(state: PRReviewState) -> str:
    if not state.get("is_valid", False) and state.get("error_message"):
        return "encerrar_execucao"
    return "buscar_prs_pendentes"


def _has_pending_prs(state: PRReviewState) -> str:
    if state["pending_prs"]:
        return "carregar_historico"
    return "encerrar_execucao"


def _reached_limit(state: PRReviewState) -> bool:
    """Limite explícito de iterações do loop (autonomia delimitada)."""
    max_prs = state.get("max_prs", 0)
    if max_prs is not None and max_prs > 0:
        return state.get("processed_prs_count", 0) >= max_prs
    return False


def _after_post(state: PRReviewState) -> str:
    if state["pending_prs"] and not _reached_limit(state):
        return "coletar_diff_pr"
    return "encerrar_execucao"


def build_graph() -> StateGraph:
    builder = StateGraph(PRReviewState)

    builder.add_node("validar_entrada", validar_entrada)
    builder.add_node("buscar_prs_pendentes", buscar_prs_pendentes)
    builder.add_node("carregar_historico", carregar_historico)
    builder.add_node("coletar_diff_pr", coletar_diff_pr)
    builder.add_node("sanitizar_diff", sanitizar_diff)
    builder.add_node("analisar_codigo", analisar_codigo)
    builder.add_node("resumir_metadados", resumir_metadados)
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
        {"carregar_historico": "carregar_historico", "encerrar_execucao": "encerrar_execucao"}
    )
    builder.add_edge("carregar_historico", "coletar_diff_pr")

    # Governança: TODO diff passa pelo sanitizador antes de qualquer uso
    builder.add_edge("coletar_diff_pr", "sanitizar_diff")

    # Fan-out: análise do diff (LLM) e resumo de metadados rodam EM PARALELO,
    # ambos consumindo o conteúdo JÁ SANITIZADO
    builder.add_edge("sanitizar_diff", "analisar_codigo")
    builder.add_edge("sanitizar_diff", "resumir_metadados")

    # Fan-in: ambos os ramos alimentam a postagem do comentário
    builder.add_edge("analisar_codigo", "postar_comentario")
    builder.add_edge("resumir_metadados", "postar_comentario")

    builder.add_conditional_edges(
        "postar_comentario",
        _after_post,
        {"coletar_diff_pr": "coletar_diff_pr", "encerrar_execucao": "encerrar_execucao"}
    )
    builder.add_edge("encerrar_execucao", END)

    return builder.compile()
