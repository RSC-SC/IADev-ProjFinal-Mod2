import json
import os
from typing import List, Dict, Any


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
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data[-limit:]
    except (json.JSONDecodeError, IOError):
        return []


def save_review(
    repo_owner: str,
    repo_name: str,
    pr_number: int,
    pr_title: str,
    review: str,
    diff_summary: str,
) -> None:
    path = _get_repo_path(repo_owner, repo_name)
    history = []
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                history = json.load(f)
        except (json.JSONDecodeError, IOError):
            history = []

    entry = {
        "pr_number": pr_number,
        "pr_title": pr_title,
        "review": review,
        "diff_summary": diff_summary[:500],
    }
    history.append(entry)

    with open(path, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)
