from typing import TypedDict, List, Dict, Any


class PRReviewState(TypedDict):
    repo_url: str
    repo_owner: str
    repo_name: str
    is_valid: bool
    error_message: str
    pending_prs: List[Dict[str, Any]]
    current_pr: Dict[str, Any]
    current_diff: str
    current_review: str
    current_metadata_summary: str  # gerado em paralelo à análise do diff
    processed_prs_count: int
    max_prs: int  # limite explícito de iterações do loop (autonomia delimitada)
    review_history: List[Dict[str, Any]]
