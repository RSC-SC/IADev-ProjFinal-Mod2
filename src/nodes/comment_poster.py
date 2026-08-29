import os
from typing import Any, Dict

from src.state import PRReviewState
from src.tools.github_tool import GitHubTool, GitHubToolError
from src.tools.memory_tool import _review_to_text, save_review


def _security_section(security_report: Dict[str, Any]) -> str:
    """Gera a seção 🛡️ Segurança do comentário quando há sinais detectados.

    Transparência de governança: o autor do PR e os revisores humanos ficam
    cientes de que o conteúdo suspeito foi neutralizado antes do LLM.
    """
    if not security_report:
        return ""
    high = security_report.get("high_signals", 0)
    medium = security_report.get("medium_signals", 0)
    removed = security_report.get("removed_lines", 0)
    if high == 0 and medium == 0:
        return ""

    lines = ["\n---\n", "### 🛡️ Nota de Segurança"]
    if high > 0:
        lines.append(
            f"- ⚠️ **{high} padrão(ões) de possível prompt-injection detectado(s)** "
            f"no diff; {removed} linha(s) foram neutralizada(s) ANTES do envio ao LLM."
        )
    if medium > 0:
        lines.append(
            f"- ℹ️ {medium} sinal(is) contextual(is) suspeito(s) registrado(s) para auditoria."
        )
    lines.append("- O conteúdo externo não altera as regras deste agente.")
    return "\n".join(lines) + "\n"


def _safe_print(text: str) -> None:
    """print resiliente a consoles Windows (cp1252) sem suporte a Unicode."""
    try:
        print(text)
    except UnicodeEncodeError:
        print(text.encode("ascii", errors="replace").decode("ascii"))


def _print_dry_run(pr_number, review: str) -> None:
    """Superfície de aprovação humana no modo dry-run."""
    bar = "=" * 60
    _safe_print(f"\n{bar}")
    _safe_print(f"[DRY-RUN] Revisão gerada para o PR #{pr_number}")
    _safe_print("           NÃO postada — aguardando aprovação humana")
    _safe_print(bar)
    _safe_print(review)
    _safe_print(bar)
    _safe_print("[DRY-RUN] Fim da revisão (nada foi enviado ao GitHub)\n")


def postar_comentario(state: PRReviewState) -> Dict[str, Any]:
    # Fan-in: este nó recebe edges dos ramos paralelos (análise e metadados).
    # Se o ramo de análise sinalizou erro, nada deve ser publicado.
    if state.get("error_message"):
        return {}

    pr = state["current_pr"]
    # Camada defensiva: garante que o review seja sempre markdown plano,
    # mesmo que `current_review` venha como lista de ContentBlocks (ex.:
    # provider que retorna [{"type": "text", "text": "..."}] em vez de str).
    review = _review_to_text(state["current_review"])
    metadata = state.get("current_metadata_summary", "")
    dry_run = bool(state.get("dry_run", False))

    # ------------------------------------------------------------------
    # Limite de autonomia (--dry-run): a revisão existe, mas NADA é
    # escrito no GitHub. A publicação exige uma execução sem --dry-run,
    # i.e., aprovação humana explícita do conteúdo.
    # ------------------------------------------------------------------
    if dry_run:
        _print_dry_run(pr.get("number", "?"), review)
        save_review(
            repo_owner=state["repo_owner"],
            repo_name=state["repo_name"],
            pr_number=pr["number"],
            pr_title=pr.get("title", ""),
            review=review,
            diff_summary=state["current_diff"][:500],
            posted=False,
            mode="dry_run",
        )
        return {
            "processed_prs_count": state.get("processed_prs_count", 0) + 1,
            "current_pr": {},
            "current_diff": "",
            "current_diff_sanitized": "",
            "current_review": "",
            "current_metadata_summary": "",
        }

    body = f"""## 🤖 Revisão Automática de Código

### 📋 Metadados do PR
{metadata}

---

{review}
{_security_section(state.get("security_report", {}) or {})}
---
*Gerado pelo Agente Revisor de PRs | IA para Desenvolvedores*"""

    try:
        tool = GitHubTool(os.getenv("GITHUB_TOKEN"))
        tool.post_comment(state["repo_owner"], state["repo_name"], pr["number"], body)
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
        posted=True,
        mode="full",
    )

    return {
        "processed_prs_count": state.get("processed_prs_count", 0) + 1,
        "current_pr": {},
        "current_diff": "",
        "current_diff_sanitized": "",
        "current_review": "",
        "current_metadata_summary": "",
    }
