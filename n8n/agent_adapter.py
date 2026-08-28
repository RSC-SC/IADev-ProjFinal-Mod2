#!/usr/bin/env python3
"""
Agente Adapter para n8n - Integração com Agente Revisor de PRs

Este script fornece uma interface HTTP para chamar o agente revisor de PRs,
facilitando a integração com plataformas de automação como n8n.

Uso:
    # Servidor HTTP
    python agent_adapter.py --server --port 8080

    # Chamada direta
    python agent_adapter.py --repo-url https://github.com/owner/repo --dry-run
"""

import argparse
import json
import os
import sys
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any, Dict

from dotenv import load_dotenv

# Adiciona o diretório raiz ao path para importar o agente
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

load_dotenv()


class AgentAdapter:
    """Adapter para chamar o agente revisor de PRs."""

    def __init__(self):
        self.graph = None
        self._initialize_agent()

    def _initialize_agent(self):
        """Inicializa o grafo do agente."""
        try:
            from src.graph import build_graph
            from src.tools.observability import get_observer

            self.graph = build_graph()
            self.observer = get_observer()
            print("[adapter] Agente inicializado com sucesso")
        except Exception as e:
            print(f"[adapter] Erro ao inicializar agente: {e}")
            self.graph = None

    def run_review(self, repo_url: str, dry_run: bool = True, max_prs: int = 3) -> Dict[str, Any]:
        """
        Executa a revisão de PRs para um repositório.

        Args:
            repo_url: URL do repositório GitHub
            dry_run: Se True, não posta reviews no GitHub
            max_prs: Número máximo de PRs a revisar

        Returns:
            Dict com resultado da execução
        """
        if not self.graph:
            return {
                "status": "error",
                "message": "Agente não inicializado",
                "stdout": "",
                "stderr": "Grafo do agente não disponível"
            }

        try:
            # Estado inicial do agente
            initial_state = {
                "repo_url": repo_url,
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
                "max_prs": max(1, max_prs),
                "dry_run": dry_run,
                "review_history": [],
                "final_message": "",
            }

            # Observabilidade
            run_id = self.observer.start_run(
                repo_url=repo_url,
                dry_run=dry_run,
                max_prs=max_prs,
            )

            # Executa o grafo
            start_time = time.time()
            result = self.graph.invoke(initial_state)
            execution_time = time.time() - start_time

            # Finaliza observabilidade
            paths = self.observer.finish_run(
                status="ok",
                processed_prs=result.get("processed_prs_count", 0),
                final_message=result.get("final_message", ""),
                repo_owner=result.get("repo_owner", ""),
                repo_name=result.get("repo_name", ""),
            )

            return {
                "status": "success",
                "run_id": run_id,
                "execution_time": execution_time,
                "repo_url": repo_url,
                "dry_run": dry_run,
                "processed_prs": result.get("processed_prs_count", 0),
                "final_message": result.get("final_message", ""),
                "stdout": result.get("final_message", ""),
                "stderr": "",
                "logs": paths,
            }

        except Exception as e:
            return {
                "status": "error",
                "message": str(e),
                "repo_url": repo_url,
                "dry_run": dry_run,
                "stdout": "",
                "stderr": str(e),
            }


class WebhookHandler(BaseHTTPRequestHandler):
    """Handler HTTP para receber webhooks do n8n."""

    agent_adapter = None

    def do_POST(self):
        """Processa requisições POST (webhooks)."""
        try:
            # Lê o corpo da requisição
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length)

            if content_length > 0:
                data = json.loads(post_data.decode('utf-8'))
            else:
                data = {}

            # Processa o webhook
            result = self._process_webhook(data)

            # Retorna resposta
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(result).encode('utf-8'))

        except Exception as e:
            self.send_response(500)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            error_response = {
                "status": "error",
                "message": str(e)
            }
            self.wfile.write(json.dumps(error_response).encode('utf-8'))

    def do_GET(self):
        """Processa requisições GET (health check)."""
        if self.path == '/health':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            health_response = {
                "status": "healthy",
                "service": "agente-revisor-prs",
                "version": "1.0.0"
            }
            self.wfile.write(json.dumps(health_response).encode('utf-8'))
        else:
            self.send_response(404)
            self.end_headers()

    def _process_webhook(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Processa webhook recebido do n8n/GitHub."""
        # Extrai dados do evento GitHub
        action = data.get("action", "")
        repository = data.get("repository", {})
        pull_request = data.get("pull_request", {})

        # Filtra eventos relevantes
        if action not in ["opened", "synchronize"]:
            return {
                "status": "ignored",
                "message": f"Ação '{action}' não processada"
            }

        # Extrai URL do repositório
        repo_url = repository.get("html_url", "")
        if not repo_url:
            return {
                "status": "error",
                "message": "URL do repositório não encontrada"
            }

        # Executa o agente
        result = self.agent_adapter.run_review(
            repo_url=repo_url,
            dry_run=True,  # Seguro por padrão
            max_prs=3
        )

        # Adiciona dados do PR
        result["pr_number"] = pull_request.get("number")
        result["pr_title"] = pull_request.get("title")
        result["pr_author"] = pull_request.get("user", {}).get("login")

        return result

    def log_message(self, format, *args):
        """Customiza log do servidor."""
        print(f"[{self.log_date_time_string()}] {format % args}")


def start_server(port: int = 8080):
    """Inicia o servidor HTTP."""
    print(f"[adapter] Iniciando servidor na porta {port}")
    print(f"[adapter] Webhook URL: http://localhost:{port}/webhook")
    print(f"[adapter] Health check: http://localhost:{port}/health")

    server = HTTPServer(('localhost', port), WebhookHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[adapter] Servidor interrompido")
        server.shutdown()


def main():
    """Ponto de entrada principal."""
    parser = argparse.ArgumentParser(
        description="Agente Adapter para n8n - Integração com Agente Revisor de PRs"
    )
    parser.add_argument(
        "--server",
        action="store_true",
        help="Inicia servidor HTTP para receber webhooks"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8080,
        help="Porta do servidor HTTP (padrão: 8080)"
    )
    parser.add_argument(
        "--repo-url",
        help="URL do repositório GitHub (para execução direta)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Executa em modo seguro (não posta reviews)"
    )
    parser.add_argument(
        "--max-prs",
        type=int,
        default=3,
        help="Número máximo de PRs a revisar (padrão: 3)"
    )

    args = parser.parse_args()

    # Inicializa o adapter
    adapter = AgentAdapter()

    if args.server:
        # Modo servidor
        WebhookHandler.agent_adapter = adapter
        start_server(args.port)
    elif args.repo_url:
        # Execução direta
        result = adapter.run_review(
            repo_url=args.repo_url,
            dry_run=args.dry_run,
            max_prs=args.max_prs
        )
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
