import os
from typing import Dict, Any
from src.state import PRReviewState
from src.tools.github_tool import GitHubTool, GitHubToolError


def buscar_prs_pendentes(state: PRReviewState) -> Dict[str, Any]:
    try:
        tool = GitHubTool(os.getenv("GITHUB_TOKEN"))
        prs = tool.get_open_prs(state["repo_owner"], state["repo_name"])
    except GitHubToolError as e:
        # Falha estruturada: grafo termina de forma limpa com mensagem clara
        return {
            "pending_prs": [],
            "error_message": f"Erro ao buscar PRs abertos: {e}",
        }

    if not prs:
        return {
            "pending_prs": [],
            "error_message": "Nenhum Pull Request aberto encontrado no repositório"
        }

    return {
        "pending_prs": prs,
        "error_message": ""
    }


def coletar_diff_pr(state: PRReviewState) -> Dict[str, Any]:
    pr = state["pending_prs"][0]
    try:
        tool = GitHubTool(os.getenv("GITHUB_TOKEN"))
        diff = tool.get_pr_diff(state["repo_owner"], state["repo_name"], pr["number"])
    except GitHubToolError as e:
        # Falha estruturada: interrompe o lote com diagnóstico do PR problemático
        return {
            "pending_prs": [],
            "error_message": (
                f"Erro ao coletar diff do PR #{pr.get('number', '?')}: {e}"
            ),
        }

    return {
        "current_pr": pr,
        "current_diff": diff,
        "pending_prs": state["pending_prs"][1:]
    }
