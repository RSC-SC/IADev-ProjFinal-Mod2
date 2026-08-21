from typing import Dict, Any
from src.state import PRReviewState


def _classify_size(num_files: int, num_lines: int) -> str:
    """Classificação simples de complexidade com base no tamanho do diff."""
    if num_lines <= 50 and num_files <= 3:
        return "Pequena"
    if num_lines <= 300 or num_files <= 10:
        return "Média"
    return "Grande"


def resumir_metadados(state: PRReviewState) -> Dict[str, Any]:
    """Gera um sumário de metadados do PR atual.

    Executa EM PARALELO ao nó `analisar_codigo` no grafo LangGraph:
    enquanto o LLM analisa o diff (operação lenta), este nó monta um
    resumo determinístico e rápido a partir dos metadados já coletados.
    O resultado é combinado por `postar_comentario`.
    """
    pr = state.get("current_pr", {}) or {}
    diff = state.get("current_diff", "") or ""

    diff_lines = [line for line in diff.splitlines() if line.strip()]
    num_files = sum(1 for line in diff_lines if line.startswith("## "))
    added = sum(1 for line in diff_lines if line.startswith("+"))
    removed = sum(1 for line in diff_lines if line.startswith("-"))
    complexity = _classify_size(num_files, len(diff_lines))

    summary = (
        f"- **PR:** #{pr.get('number', 'N/A')} — {pr.get('title', 'Sem título')}\n"
        f"- **Link:** {pr.get('url', 'N/A')}\n"
        f"- **Arquivos alterados:** {num_files}\n"
        f"- **Linhas no diff:** +{added} / -{removed} ({len(diff_lines)} linhas totais)\n"
        f"- **Complexidade estimada:** {complexity}"
    )

    return {"current_metadata_summary": summary}
