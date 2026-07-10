import sys
import os
from dotenv import load_dotenv

load_dotenv()

from src.graph import build_graph


def main():
    if len(sys.argv) < 2:
        print("Uso: python main.py <url-do-repositorio>")
        print("Exemplo: python main.py https://github.com/dono/repositorio")
        sys.exit(1)

    repo_url = sys.argv[1]

    graph = build_graph()

    initial_state = {
        "repo_url": repo_url,
        "repo_owner": "",
        "repo_name": "",
        "is_valid": True,
        "error_message": "",
        "pending_prs": [],
        "current_pr": {},
        "current_diff": "",
        "current_review": "",
        "processed_prs_count": 0,
        "review_history": [],
    }

    result = graph.invoke(initial_state)

    print("\n" + "=" * 50)
    print(result.get("error_message", "Revisão concluída com sucesso!"))
    print("=" * 50)


if __name__ == "__main__":
    main()
