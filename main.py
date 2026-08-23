import argparse
import os
from dotenv import load_dotenv

load_dotenv()

from src.graph import build_graph
from src.tools.observability import get_observer


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

    # Observabilidade (Issue #14): abre os dois sinais correlacionados por
    # run_id — log estruturado JSONL + registro de auditoria com latências.
    observer = get_observer()
    run_id = observer.start_run(
        repo_url=args.repo_url, dry_run=bool(args.dry_run),
        max_prs=max(1, args.max_prs),
    )
    print(f"[obs] run_id={run_id} — sinais sendo gravados em ./logs/")

    status = "ok"
    try:
        result = graph.invoke(initial_state)
    except Exception as e:  # crash inesperado: auditoria registra o evento
        status = "crashed"
        result = {
            "error_message": f"Execução interrompida por erro inesperado: {e}",
            "processed_prs_count": 0,
            "repo_owner": "",
            "repo_name": "",
        }

    paths = observer.finish_run(
        status=status,
        processed_prs=result.get("processed_prs_count", 0),
        final_message=result.get("error_message", ""),
        repo_owner=result.get("repo_owner", ""),
        repo_name=result.get("repo_name", ""),
    )

    print("\n" + "=" * 50)
    print(result.get("error_message", "Revisão concluída com sucesso!"))
    print("=" * 50)
    print(f"[obs] Log estruturado : {paths['structured_log']}")
    print(f"[obs] Auditoria       : {paths['audit']}")


if __name__ == "__main__":
    main()
