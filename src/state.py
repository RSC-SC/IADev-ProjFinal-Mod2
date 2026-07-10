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
    processed_prs_count: int
    review_history: List[Dict[str, Any]]
