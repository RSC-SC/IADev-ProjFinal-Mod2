import os
from typing import Dict, Any
from src.state import PRReviewState
from src.tools.github_tool import GitHubTool
from src.tools.memory_tool import save_review


def postar_comentario(state: PRReviewState) -> Dict[str, Any]:
    tool = GitHubTool(os.getenv("GITHUB_TOKEN"))
    pr = state["current_pr"]
    review = state["current_review"]

    body = f"""## 🤖 Revisão Automática de Código

{review}

---
*Gerado pelo Agente Revisor de PRs | IA para Desenvolvedores*"""

    tool.post_comment(state["repo_owner"], state["repo_name"], pr["number"], body)

    save_review(
        repo_owner=state["repo_owner"],
        repo_name=state["repo_name"],
        pr_number=pr["number"],
        pr_title=pr.get("title", ""),
        review=review,
        diff_summary=state["current_diff"][:500],
    )

    return {
        "processed_prs_count": state.get("processed_prs_count", 0) + 1,
        "current_pr": {},
        "current_diff": "",
        "current_review": ""
    }
