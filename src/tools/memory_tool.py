import json
import os
from typing import Any, Dict, List

REVIEWS_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "reviews")


def _get_repo_path(repo_owner: str, repo_name: str) -> str:
    repo_dir = os.path.join(REVIEWS_DIR, f"{repo_owner}_{repo_name}")
    os.makedirs(repo_dir, exist_ok=True)
    return os.path.join(repo_dir, "history.json")


def load_history(repo_owner: str, repo_name: str, limit: int = 5) -> List[Dict[str, Any]]:
    path = _get_repo_path(repo_owner, repo_name)
    if not os.path.exists(path):
        return []
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return data[-limit:]
    except (OSError, json.JSONDecodeError):
        return []


def _review_to_text(review: Any) -> str:
    """Normaliza o review para STRING antes de persistir.

    O `response.content` do LLM pode ser uma lista de blocos de conteúdo
    (ex.: [{"type": "text", "text": "..."}]) dependendo do provider/versão
    da lib. Gravar esse vetor diretamente corrompe o histórico e quebra a
    montagem do contexto no nó `analisar_codigo` (bug de produção:
    "can only concatenate list (not \"str\") to list"). Normaliza aqui na
    ORIGEM, garantindo que o armazenamento seja sempre texto plano.
    """
    if isinstance(review, str):
        return review
    if isinstance(review, (list, tuple)):
        parts = []
        for block in review:
            if isinstance(block, dict):
                parts.append(block.get("text", ""))
            else:
                parts.append(str(block))
        return "".join(parts)
    return str(review)


def save_review(
    repo_owner: str,
    repo_name: str,
    pr_number: int,
    pr_title: str,
    review: str,
    diff_summary: str,
    posted: bool = True,
    mode: str = "full",
) -> None:
    path = _get_repo_path(repo_owner, repo_name)
    history = []
    if os.path.exists(path):
        try:
            with open(path, encoding="utf-8") as f:
                history = json.load(f)
        except (OSError, json.JSONDecodeError):
            history = []

    entry = {
        "pr_number": pr_number,
        "pr_title": pr_title,
        "review": _review_to_text(review),
        "diff_summary": diff_summary[:500],
        # Governança/auditoria da memória:
        #   posted=False → revisão gerada em modo dry-run, nunca publicada
        #   mode="dry_run" | "full" → contexto de geração da entrada
        "posted": posted,
        "mode": mode,
    }
    history.append(entry)

    with open(path, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)
