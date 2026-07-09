import os
from typing import Dict, Any
from src.state import PRReviewState
from src.tools.github_tool import GitHubTool


def buscar_prs_pendentes(state: PRReviewState) -> Dict[str, Any]:
    tool = GitHubTool(os.getenv("GITHUB_TOKEN"))
    prs = tool.get_open_prs(state["repo_owner"], state["repo_name"])

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
    tool = GitHubTool(os.getenv("GITHUB_TOKEN"))
    diff = tool.get_pr_diff(state["repo_owner"], state["repo_name"], pr["number"])
    return {
        "current_pr": pr,
        "current_diff": diff,
        "pending_prs": state["pending_prs"][1:]
    }
