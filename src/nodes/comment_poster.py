import os
from typing import Dict, Any
from src.state import PRReviewState
from src.tools.github_tool import GitHubTool


def postar_comentario(state: PRReviewState) -> Dict[str, Any]:
    tool = GitHubTool(os.getenv("GITHUB_TOKEN"))
    pr = state["current_pr"]
    review = state["current_review"]

    body = f"""## 🤖 Revisão Automática de Código

{review}

---
*Gerado pelo Agente Revisor de PRs | IA para Desenvolvedores*"""

    tool.post_comment(state["repo_owner"], state["repo_name"], pr["number"], body)

    return {
        "processed_prs_count": state.get("processed_prs_count", 0) + 1,
        "current_pr": {},
        "current_diff": "",
        "current_review": ""
    }
