"""Testes da GitHubTool resiliente (src/tools/github_tool.py).

PRIORIDADE DE RISCO #3: única fronteira com a API externa (GitHub).
Riscos travados aqui: entradas inválidas JAMAIS chegam à rede; retry só
ocorre em falhas TRANSITÓRIAS (nunca em 401/404 — evita dormir à toa);
falhas sempre estruturadas como GitHubToolError.

Estratégia: o cliente PyGithub é substituído por fakes em memória —
ZERO rede, ZERO sleeps (retry_backoff_seconds=0).
"""

from types import SimpleNamespace

import pytest
from github import GithubException

from src.tools.github_tool import GitHubTool, GitHubToolError


@pytest.fixture
def tool():
    """GitHubTool com backoff zero e client fake substituível pelo teste."""
    t = GitHubTool(token="token-teste", timeout=5,
                   max_retries=3, retry_backoff_seconds=0.0)
    return t


def make_repo(pull_factory=None, files=None):
    repo = SimpleNamespace(
        get_pulls=lambda state: pull_factory or [],
        get_pull=lambda n: SimpleNamespace(
            get_files=lambda: files or [],
            create_issue_comment=lambda body: SimpleNamespace(id=777),
        ),
    )
    return SimpleNamespace(get_repo=lambda full: repo)


class TestValidacaoDeEntradas:
    @pytest.mark.parametrize("token", [None, "", "   "])
    def test_token_ausente_ou_vazio(self, token):
        with pytest.raises(GitHubToolError) as exc:
            GitHubTool(token=token)
        assert exc.value.operation == "validacao"

    def test_owner_com_caracteres_invalidos_nao_chama_rede(self, tool):
        chamadas = []
        tool.client = SimpleNamespace(
            get_repo=lambda f: chamadas.append(f) or make_repo()
        )
        with pytest.raises(GitHubToolError) as exc:
            tool.get_open_prs("dono/evil", "repo")
        assert exc.value.operation == "validacao"
        assert chamadas == []  # bloqueado ANTES de qualquer I/O

    @pytest.mark.parametrize("owner,repo", [
        ("", ""), ("ok-owner", "../traversal"), ("a b", "c"),
    ])
    def test_repo_names_invalidos(self, tool, owner, repo):
        with pytest.raises(GitHubToolError):
            tool.get_open_prs(owner, repo)

    @pytest.mark.parametrize("pr_number", [0, -7, "12", 1.5, None])
    def test_numero_de_pr_invalido(self, tool, pr_number):
        with pytest.raises(GitHubToolError):
            tool.get_pr_diff("dono", "repo", pr_number)

    def test_corpo_de_comentario_vazio(self, tool):
        with pytest.raises(GitHubToolError) as exc:
            tool.post_comment("dono", "repo", 1, "   ")
        assert exc.value.operation == "validacao"


class FakeFlakyRepo:
    """Repo que falha N vezes antes de responder."""

    def __init__(self, fail_times, status):
        self.fail_times = fail_times
        self.status = status
        self.calls = 0

    def get_pulls(self, state):
        self.calls += 1
        if self.calls <= self.fail_times:
            raise GithubException(status=self.status, data={"message": "err"})
        return [SimpleNamespace(number=1, title="PR", html_url="url")]

    get_repo = lambda self, full: self  # noqa: E731


class TestRetryLimitado:
    def test_retry_em_falha_transitoria_ate_sucesso(self, tool):
        flaky = FakeFlakyRepo(fail_times=2, status=503)
        tool.client = flaky
        prs = tool.get_open_prs("dono", "repo")
        assert flaky.calls == 3  # 2 falhas + 1 sucesso
        assert prs == [{"number": 1, "title": "PR", "url": "url"}]

    def test_falha_permanente_nao_tem_retry(self, tool):
        flaky = FakeFlakyRepo(fail_times=99, status=404)
        tool.client = flaky
        with pytest.raises(GitHubToolError) as exc:
            tool.get_open_prs("dono", "repo")
        assert flaky.calls == 1  # permanente: para na 1ª tentativa
        assert exc.value.status_code == 404

    @pytest.mark.parametrize("status", [500, 502, 503, 504, 408, 429])
    def test_todos_os_status_transitorios_esgotam_e_estruturam(self, tool, status):
        flaky = FakeFlakyRepo(fail_times=99, status=status)
        tool.client = flaky
        with pytest.raises(GitHubToolError) as exc:
            tool.get_open_prs("dono", "repo")
        assert flaky.calls == tool.max_retries  # esgotou as tentativas
        assert exc.value.status_code == status
        assert exc.value.operation == "get_open_prs"

    def test_excecao_inesperada_e_tratada_como_transitoria(self, tool):
        class RepoQuebrado(FakeFlakyRepo):
            def get_pulls(self, state):
                self.calls += 1
                raise ValueError("conexao resetada")

        quebrado = RepoQuebrado(0, 0)
        tool.client = quebrado
        with pytest.raises(GitHubToolError) as exc:
            tool.get_open_prs("dono", "repo")
        assert quebrado.calls == tool.max_retries
        assert "conexao resetada" in str(exc.value)

    def test_rate_limit_403_e_permanente_sem_sleep(self, tool):
        # Decisão registrada no plano: 403/429... 429 é transitorio, mas 403
        # (rate limit do GitHub em token sem permissão) é PERMANENTE p/ CLI.
        flaky = FakeFlakyRepo(fail_times=99, status=403)
        tool.client = flaky
        with pytest.raises(GitHubToolError) as exc:
            tool.get_open_prs("dono", "repo")
        assert flaky.calls == 1


class TestOperacoes:
    def test_get_open_prs_descarta_item_malformado(self, tool):
        pulls = [
            SimpleNamespace(number=None, title="sem numero", html_url="x"),
            SimpleNamespace(number=9, title="válido", html_url="u9"),
        ]
        tool.client = make_repo(pull_factory=pulls)
        prs = tool.get_open_prs("dono", "repo")
        assert prs == [{"number": 9, "title": "válido", "url": "u9"}]

    def test_get_pr_diff_concatena_secoes_por_arquivo(self, tool):
        files = [
            SimpleNamespace(filename="src/a.py", status="modified",
                            patch="+print('a')"),
            SimpleNamespace(filename="img/logo.png", status="added",
                            patch=None),  # binário → marcador explícito
        ]
        tool.client = make_repo(files=files)
        diff = tool.get_pr_diff("dono", "repo", 5)
        assert diff.startswith("## src/a.py (modified)")
        assert "+print('a')" in diff
        assert "(binary or no diff)" in diff
        assert "## img/logo.png (added)" in diff

    def test_post_comment_retorna_confirmacao_estruturada(self, tool):
        tool.client = make_repo()
        result = tool.post_comment("dono", "repo", 3, "corpo da revisão")
        assert result["posted"] is True
        assert result["comment_id"] == 777
