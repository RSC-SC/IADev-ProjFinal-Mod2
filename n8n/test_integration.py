#!/usr/bin/env python3
"""
Script de teste para a integração n8n - Agente Revisor de PRs

Este script testa a integração do agente com o n8n, simulando webhooks
e validando o fluxo de execução.
"""

import json
import requests
import sys
import time
from typing import Dict, Any


def test_health_check(base_url: str) -> bool:
    """Testa o health check do servidor."""
    try:
        response = requests.get(f"{base_url}/health", timeout=5)
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Health check: {data.get('status')}")
            return True
        else:
            print(f"❌ Health check falhou: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Health check erro: {e}")
        return False


def test_webhook_simulation(base_url: str, repo_url: str) -> bool:
    """Simula um webhook do GitHub."""
    try:
        # Payload simulado do GitHub
        payload = {
            "action": "opened",
            "repository": {
                "html_url": repo_url,
                "name": "test-repo",
                "full_name": "test-owner/test-repo"
            },
            "pull_request": {
                "number": 1,
                "title": "Test PR",
                "user": {
                    "login": "testuser"
                },
                "html_url": f"{repo_url}/pull/1"
            }
        }

        print(f"📤 Enviando webhook para {base_url}/webhook...")
        response = requests.post(
            f"{base_url}/webhook",
            json=payload,
            timeout=30
        )

        if response.status_code == 200:
            data = response.json()
            print(f"✅ Webhook processado: {data.get('status')}")
            print(f"   PR: {data.get('pr_number')} - {data.get('pr_title')}")
            print(f"   Mensagem: {data.get('final_message', 'N/A')[:100]}...")
            return True
        else:
            print(f"❌ Webhook falhou: {response.status_code}")
            print(f"   Resposta: {response.text[:200]}")
            return False

    except Exception as e:
        print(f"❌ Webhook erro: {e}")
        return False


def test_direct_execution(repo_url: str, dry_run: bool = True) -> bool:
    """Testa execução direta do agente."""
    try:
        from agent_adapter import AgentAdapter

        print(f"🤖 Testando execução direta do agente...")
        print(f"   Repositório: {repo_url}")
        print(f"   Modo: {'dry-run' if dry_run else 'produção'}")

        adapter = AgentAdapter()
        result = adapter.run_review(
            repo_url=repo_url,
            dry_run=dry_run,
            max_prs=1
        )

        if result.get("status") == "success":
            print(f"✅ Execução bem-sucedida")
            print(f"   Run ID: {result.get('run_id')}")
            print(f"   Tempo: {result.get('execution_time', 0):.2f}s")
            print(f"   PRs processados: {result.get('processed_prs', 0)}")
            print(f"   Mensagem: {result.get('final_message', 'N/A')[:100]}...")
            return True
        else:
            print(f"❌ Execução falhou: {result.get('message')}")
            return False

    except Exception as e:
        print(f"❌ Execução erro: {e}")
        return False


def main():
    """Função principal de teste."""
    print("🧪 Teste de Integração n8n - Agente Revisor de PRs")
    print("=" * 60)

    # Configurações
    base_url = "http://localhost:8080"
    repo_url = "https://github.com/RSC-SC/IADev-ProjFinal-Mod2"

    # Parse de argumentos
    if len(sys.argv) > 1:
        base_url = sys.argv[1]
    if len(sys.argv) > 2:
        repo_url = sys.argv[2]

    print(f"📍 Base URL: {base_url}")
    print(f"📦 Repositório: {repo_url}")
    print()

    # Testes
    tests = [
        ("Health Check", lambda: test_health_check(base_url)),
        ("Webhook Simulation", lambda: test_webhook_simulation(base_url, repo_url)),
        ("Direct Execution", lambda: test_direct_execution(repo_url, dry_run=True)),
    ]

    results = []
    for test_name, test_func in tests:
        print(f"\n🔍 Testando: {test_name}")
        print("-" * 40)
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"❌ Erro inesperado: {e}")
            results.append((test_name, False))

    # Resumo
    print("\n" + "=" * 60)
    print("📊 Resumo dos Testes")
    print("=" * 60)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} - {test_name}")

    print(f"\n🎯 Resultado: {passed}/{total} testes passaram")

    if passed == total:
        print("🎉 Todos os testes passaram!")
        return 0
    else:
        print("⚠️  Alguns testes falharam")
        return 1


if __name__ == "__main__":
    sys.exit(main())