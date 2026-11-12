from src.nodes.comment_poster import postar_comentario
from src.tools.observability import format_terminal_report


def test_format_terminal_report_completo():
    audit = {
        "run_id": "run_test_123",
        "total_duration_ms": 12500.0,
        "status": "completed",
        "outcome": "succeeded",
        "processed_prs": 1,
        "final_message": "Revisão concluída com sucesso.",
        "repo": {
            "url": "https://github.com/dono/repo",
            "owner": "dono",
            "name": "repo",
        },
        "nodes_latency": {
            "validar_entrada": {"calls": 1, "avg_ms": 1.2, "total_ms": 1.2},
            "analisar_codigo": {"calls": 1, "avg_ms": 5000.0, "total_ms": 5000.0},
        },
        "llm": {
            "providers_succeeded": ["OpenRouter"],
            "fallback_count": 0,
        },
        "security_alerts": [],
        "artifacts": {
            "structured_log": "logs/run_test_123.jsonl",
        },
        "audit_path": "logs/audit_test_123.json",
    }

    processed_reviews = [
        {
            "pr_number": 42,
            "pr_title": "feat: nova feature",
            "review": "## Pontos Positivos\n- Código limpo\n\n## Oportunidades de Melhoria\n- Adicionar testes",
            "metadata": "1 arquivo alterado",
            "dry_run": False,
        }
    ]

    report = format_terminal_report(
        audit=audit,
        processed_reviews=processed_reviews,
        history_path="reviews/dono_repo/history.json",
    )

    assert "📊 RESUMO DA EXECUÇÃO" in report
    assert "• Repositório:         https://github.com/dono/repo" in report
    assert "• Status / Desfecho:   completed · succeeded" in report
    assert "• PR(s) Processado(s): 1" in report
    assert "• Duração Total:       12.5s (12500.0 ms)" in report
    assert "• Provedor(es) LLM:    OpenRouter" in report
    assert "⏱️ LATÊNCIA POR NÓ NO GRAFO" in report
    assert "analisar_codigo" in report
    assert "🤖 REVISÃO PUBLICADA NO PR" in report
    assert "PR #42 — feat: nova feature" in report
    assert "[PUBLICADO] Postado no GitHub via API" in report
    assert "## Pontos Positivos" in report
    assert "📁 ARTEFATOS DE OBSERVABILIDADE GERADOS" in report
    assert "logs/run_test_123.jsonl" in report
    assert "logs/audit_test_123.json" in report
    assert "reviews/dono_repo/history.json" in report


def test_format_terminal_report_dry_run_e_sem_reviews():
    audit = {
        "run_id": "run_test_dry",
        "total_duration_ms": 500.0,
        "status": "completed",
        "outcome": "succeeded",
        "processed_prs": 0,
        "final_message": "Nenhum PR pendente.",
        "repo": {"url": "https://github.com/dono/repo"},
        "nodes_latency": {},
        "artifacts": {"structured_log": "logs/run_test_dry.jsonl"},
    }

    # Sem reviews
    report_empty = format_terminal_report(audit=audit, processed_reviews=[])
    assert "• Nenhuma revisão gerada para publicação nesta execução." in report_empty
    assert "• Nenhum nó registrado com métricas de latência." in report_empty

    # Com review dry-run
    reviews_dry = [
        {
            "pr_number": 99,
            "pr_title": "docs: atualiza readme",
            "review": "Revisão teste",
            "dry_run": True,
        }
    ]
    report_dry = format_terminal_report(audit=audit, processed_reviews=reviews_dry)
    assert "[DRY-RUN] Simulação — Não postado no GitHub" in report_dry
    assert "PR #99 — docs: atualiza readme" in report_dry


def test_postar_comentario_acumula_processed_reviews(monkeypatch, tmp_path):
    import src.tools.memory_tool as memory_tool
    from src.tools.github_tool import GitHubTool

    monkeypatch.setenv("GITHUB_TOKEN", "token_falso_mock_12345")
    monkeypatch.setattr(memory_tool, "REVIEWS_DIR", str(tmp_path))
    monkeypatch.setattr(GitHubTool, "post_comment", lambda self, owner, name, num, body: None)

    state = {
        "repo_url": "https://github.com/dono/repo",
        "repo_owner": "dono",
        "repo_name": "repo",
        "current_pr": {"number": 10, "title": "Refatoração"},
        "current_review": "## Pontos Positivos\n- Bom trabalho",
        "current_metadata_summary": "2 arquivos",
        "current_diff": "diff --git a b",
        "dry_run": False,
        "processed_prs_count": 0,
        "processed_reviews": [],
    }

    res = postar_comentario(state)
    assert res["processed_prs_count"] == 1
    assert len(res["processed_reviews"]) == 1
    item = res["processed_reviews"][0]
    assert item["pr_number"] == 10
    assert item["pr_title"] == "Refatoração"
    assert item["dry_run"] is False
    assert "## Pontos Positivos" in item["review"]
