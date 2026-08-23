import argparse
import os
from dotenv import load_dotenv

load_dotenv()

from src.graph import build_graph


def parse_args():
    parser = argparse.ArgumentParser(
        description="Agente Revisor de PRs — analisa PRs abertos de um repositório GitHub"
    )
    parser.add_argument("repo_url", help="URL do repositório GitHub (ex.: https://github.com/dono/repositorio)")
    parser.add_argument(
        "--max-prs",
        type=int,
        default=int(os.getenv("MAX_PRS", "3")),
        help="Limite máximo de PRs a revisar nesta execução (padrão: 3)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help=(
            "Limite de autonomia: gera as revisões e exibe no console, mas NÃO "
            "posta nada no GitHub (postagem só ocorre com aprovação humana)"
        ),
    )
    return parser.parse_args()


def main():
    args = parse_args()

    graph = build_graph()

    initial_state = {
        "repo_url": args.repo_url,
        "repo_owner": "",
        "repo_name": "",
        "is_valid": True,
        "error_message": "",
        "pending_prs": [],
        "current_pr": {},
        "current_diff": "",
        "current_diff_sanitized": "",
        "security_report": {},
        "current_review": "",
        "current_metadata_summary": "",
        "processed_prs_count": 0,
        "max_prs": max(1, args.max_prs),
        "dry_run": bool(args.dry_run),
        "review_history": [],
    }

    result = graph.invoke(initial_state)

    print("\n" + "=" * 50)
    print(result.get("error_message", "Revisão concluída com sucesso!"))
    print("=" * 50)


if __name__ == "__main__":
    main()
