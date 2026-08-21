import os
from typing import Dict, Any
from src.state import PRReviewState
from src.tools.github_tool import GitHubTool, GitHubToolError
from src.tools.memory_tool import save_review


def postar_comentario(state: PRReviewState) -> Dict[str, Any]:
    # Fan-in: este nó recebe edges dos ramos paralelos (análise e metadados).
    # Se o ramo de análise sinalizou erro, nada deve ser publicado.
    if state.get("error_message"):
        return {}

    pr = state["current_pr"]
    review = state["current_review"]
    metadata = state.get("current_metadata_summary", "")

    body = f"""## 🤖 Revisão Automática de Código

### 📋 Metadados do PR
{metadata}

---

{review}

---
*Gerado pelo Agente Revisor de PRs | IA para Desenvolvedores*"""

    try:
        tool = GitHubTool(os.getenv("GITHUB_TOKEN"))
        result = tool.post_comment(
            state["repo_owner"], state["repo_name"], pr["number"], body
        )
    except GitHubToolError as e:
        # Falha estruturada: não conta o PR nem salva histórico; termina limpo
        return {
            "pending_prs": [],
            "error_message": (
                f"Erro ao postar comentário no PR #{pr.get('number', '?')}: {e}"
            ),
        }

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
        "current_review": "",
        "current_metadata_summary": ""
    }
