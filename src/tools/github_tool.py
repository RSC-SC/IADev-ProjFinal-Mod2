from github import Github
from typing import List, Dict, Any


class GitHubTool:
    def __init__(self, token: str):
        self.client = Github(token)

    def get_open_prs(self, owner: str, repo_name: str) -> List[Dict[str, Any]]:
        repo = self.client.get_repo(f"{owner}/{repo_name}")
        prs = repo.get_pulls(state="open")
        return [
            {"number": pr.number, "title": pr.title, "url": pr.html_url}
            for pr in prs
        ]

    def get_pr_diff(self, owner: str, repo_name: str, pr_number: int) -> str:
        repo = self.client.get_repo(f"{owner}/{repo_name}")
        pr = repo.get_pull(pr_number)
        files = pr.get_files()
        diff_parts = []
        for file in files:
            patch = file.patch or "(binary or no diff)"
            diff_parts.append(f"## {file.filename} ({file.status})\n{patch}")
        return "\n\n".join(diff_parts)

    def post_comment(self, owner: str, repo_name: str, pr_number: int, body: str):
        repo = self.client.get_repo(f"{owner}/{repo_name}")
        pr = repo.get_pull(pr_number)
        pr.create_issue_comment(body)
