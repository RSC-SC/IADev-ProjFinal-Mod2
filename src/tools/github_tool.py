import re
import time
import logging
from typing import List, Dict, Any, Optional, Callable

from github import Github, Auth, GithubException

logger = logging.getLogger(__name__)


class GitHubToolError(Exception):
    """Falha estruturada da GitHubTool.

    Carrega contexto operacional para tratamento upstream nos nós:
    - operation: qual operação falhou (ex.: 'get_open_prs')
    - status_code: código HTTP quando disponível (None p/ erro local)
    - original_error: mensagem original da exceção
    """

    def __init__(self, operation: str, original_error: str = "",
                 status_code: Optional[int] = None):
        self.operation = operation
        self.status_code = status_code
        self.original_error = original_error
        http_part = f" [HTTP {status_code}]" if status_code else ""
        super().__init__(f"GitHubTool falhou em '{operation}'{http_part}: {original_error}")


# Erros HTTP que valem retry (transitórios). Demais (401/403/404/422) são permanentes.
_TRANSIENT_STATUS_CODES = {408, 429, 500, 502, 503, 504}
_REPO_NAME_PATTERN = re.compile(r"^[A-Za-z0-9_.-]+$")


class GitHubTool:
    """Wrapper resiliente da API GitHub (PyGithub).

    Garantias:
    - Validação de entradas antes de qualquer chamada de rede
    - Timeout em todas as requisições
    - Retry limitado com backoff crescente apenas em falhas transitórias
    - Falhas sempre estruturadas como GitHubToolError (nunca exceções cruas)
    """

    def __init__(self, token: str, timeout: int = 30,
                 max_retries: int = 3, retry_backoff_seconds: float = 2.0):
        self._validate_token(token)
        self.max_retries = max(1, max_retries)
        self.retry_backoff_seconds = max(0.0, retry_backoff_seconds)
        try:
            self.client = Github(auth=Auth.Token(token), timeout=timeout, per_page=50)
        except Exception as e:
            raise GitHubToolError("inicializacao", str(e))

    # ------------------------------------------------------------------ #
    # Validação de entradas
    # ------------------------------------------------------------------ #
    @staticmethod
    def _validate_token(token: str) -> None:
        if not token or not isinstance(token, str) or not token.strip():
            raise GitHubToolError(
                "validacao",
                "GITHUB_TOKEN ausente ou inválido (verifique o .env)",
            )

    @staticmethod
    def _validate_repo(owner: str, repo_name: str) -> None:
        if not owner or not _REPO_NAME_PATTERN.match(owner):
            raise GitHubToolError(
                "validacao", f"Nome de owner inválido: '{owner}'"
            )
        if not repo_name or not _REPO_NAME_PATTERN.match(repo_name):
            raise GitHubToolError(
                "validacao", f"Nome de repositório inválido: '{repo_name}'"
            )

    @staticmethod
    def _validate_pr_number(pr_number: int) -> None:
        if not isinstance(pr_number, int) or pr_number <= 0:
            raise GitHubToolError(
                "validacao", f"Número de PR inválido: {pr_number!r}"
            )

    # ------------------------------------------------------------------ #
    # Execução com retry limitado e falhas estruturadas
    # ------------------------------------------------------------------ #
    def _execute_with_retry(self, operation: str, func: Callable) -> Any:
        last_error: Optional[GithubException] = None
        for attempt in range(1, self.max_retries + 1):
            try:
                return func()
            except GithubException as e:
                status = getattr(e, "status", None)
                logger.warning(
                    "GitHubTool '%s' falhou na tentativa %d/%d (HTTP %s)",
                    operation, attempt, self.max_retries, status,
                )
                last_error = e
                if status not in _TRANSIENT_STATUS_CODES:
                    break  # permanente: não insiste
                if attempt < self.max_retries:
                    time.sleep(self.retry_backoff_seconds * attempt)
            except Exception as e:  # erro de rede/local inesperado -> transitório
                logger.warning(
                    "GitHubTool '%s' erro inesperado na tentativa %d/%d: %s",
                    operation, attempt, self.max_retries, e,
                )
                wrapped = GithubException(status=None, data=str(e))
                last_error = wrapped
                if attempt < self.max_retries:
                    time.sleep(self.retry_backoff_seconds * attempt)

        raise GitHubToolError(
            operation,
            str(getattr(last_error, "data", last_error)),
            getattr(last_error, "status", None),
        )

    # ------------------------------------------------------------------ #
    # Operações públicas
    # ------------------------------------------------------------------ #
    def get_open_prs(self, owner: str, repo_name: str) -> List[Dict[str, Any]]:
        """Lista PRs abertos do repositório. Saída validada antes do retorno."""
        self._validate_repo(owner, repo_name)

        def _fetch():
            repo = self.client.get_repo(f"{owner}/{repo_name}")
            pulls = repo.get_pulls(state="open")
            result = []
            for pr in pulls:
                item = {"number": getattr(pr, "number", None),
                        "title": getattr(pr, "title", ""),
                        "url": getattr(pr, "html_url", "")}
                if item["number"] is None:
                    continue  # entrada malformada é descartada
                result.append(item)
            return result

        return self._execute_with_retry("get_open_prs", _fetch)

    def get_pr_diff(self, owner: str, repo_name: str, pr_number: int) -> str:
        """Retorna o diff concatenado dos arquivos alterados do PR."""
        self._validate_repo(owner, repo_name)
        self._validate_pr_number(pr_number)

        def _fetch():
            repo = self.client.get_repo(f"{owner}/{repo_name}")
            pr = repo.get_pull(pr_number)
            files = pr.get_files()
            diff_parts = []
            for file in files:
                patch = file.patch or "(binary or no diff)"
                diff_parts.append(f"## {file.filename} ({file.status})\n{patch}")
            return "\n\n".join(diff_parts)

        return self._execute_with_retry("get_pr_diff", _fetch)

    def post_comment(self, owner: str, repo_name: str, pr_number: int,
                     body: str) -> Dict[str, Any]:
        """Posta um comentário no PR. Retorna confirmação estruturada."""
        self._validate_repo(owner, repo_name)
        self._validate_pr_number(pr_number)
        if not body or not body.strip():
            raise GitHubToolError("validacao", "Corpo do comentário vazio")

        def _post():
            repo = self.client.get_repo(f"{owner}/{repo_name}")
            pr = repo.get_pull(pr_number)
            comment = pr.create_issue_comment(body)
            return {"posted": True, "comment_id": getattr(comment, "id", None)}

        return self._execute_with_retry("post_comment", _post)
