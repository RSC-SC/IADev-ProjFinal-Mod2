import re
import os
from typing import Dict, Any
from src.state import PRReviewState


def validar_entrada(state: PRReviewState) -> Dict[str, Any]:
    url = state.get("repo_url", "").strip()

    padrao = r"https?://(?:www\.)?github\.com/([^/]+)/([^/]+?)(?:\.git|/)?$"
    match = re.match(padrao, url)

    if not match:
        return {
            "is_valid": False,
            "error_message": "Erro: URL inválida. Use o formato https://github.com/dono/repositorio"
        }

    owner = match.group(1)
    repo_name = match.group(2)

    if not os.getenv("GITHUB_TOKEN"):
        return {
            "is_valid": False,
            "error_message": "Erro: GITHUB_TOKEN não configurado no ambiente"
        }

    if not os.getenv("GOOGLE_API_KEY"):
        return {
            "is_valid": False,
            "error_message": "Erro: GOOGLE_API_KEY não configurada no ambiente"
        }

    return {
        "repo_owner": owner,
        "repo_name": repo_name,
        "is_valid": True,
        "error_message": ""
    }
