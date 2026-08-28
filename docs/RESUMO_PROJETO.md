# Resumo do Projeto Final - Agente Revisor de PRs

## Visão Geral

O **Agente Revisor de PRs** é uma solução de automação de code review que utiliza Inteligência Artificial para analisar Pull Requests do GitHub, identificar problemas e sugestões de melhoria, e postar comentários estruturados diretamente nos PRs.

## Objetivo

Automatizar o processo de revisão de código, proporcionando:
- **Feedback rápido** em minutos após abertura do PR
- **Padronização** das revisões com foco em boas práticas
- **Escalabilidade** para projetos com múltiplos PRs abertos
- **Segurança** com defesa contra prompt-injection

## Stack Técnica

| Componente | Tecnologia |
|------------|------------|
| Framework | LangGraph (StateGraph) |
| LLM Primário | Google Gemini |
| LLM Fallback | OpenRouter |
| API GitHub | PyGithub |
| Automação | n8n |
| Testes | pytest (102 testes) |
| CI/CD | GitHub Actions |

## Funcionalidades Principais

### 1. Análise Automatizada
- Validação de URL e chaves de API
- Coleta de PRs abertos via API GitHub
- Download e sanitização de diffs
- Análise com LLM (fallback automático)
- Geração de review estruturado

### 2. Segurança (3 Camadas)
- **Detecção**: Regex para identificar prompt-injection
- **Neutralização**: Substituição de conteúdo malicioso
- **Encapsulamento**: Envelope `<untrusted_content>` para o LLM

### 3. Observabilidade
- **JSONL estruturado**: Eventos por linha com run_id
- **Auditoria JSON**: Consolidação com latências e métricas
- **Correlação**: Dois sinais vinculados por run_id único

### 4. Automação (n8n)
- **Trigger**: Webhook do GitHub (PR opened/synchronize)
- **Execução**: Agente via CLI automaticamente
- **Saída**: Review postado no PR + logs

### 5. Qualidade
- **102 testes pytest** (100% offline)
- **Pipeline CI** com lint, testes e build
- **Análise de logs** com detecção de anomalias

## Fases de Desenvolvimento

| Fase | Escopo | Entregáveis |
|------|--------|-------------|
| F0 | Preparação | Branches, AGENTS.md, prompts.md |
| F1 | Paralelização | Grafo paralelo, GitHubTool resiliente, cenários |
| F2 | Segurança | Sanitização anti injection, --dry-run |
| F3 | Observabilidade | JSONL + auditoria com latência |
| F4 | QA | 102 testes pytest, processo de QA |
| F5 | DevOps | Pipeline CI, análise de logs |
| F6 | Automação | Integração n8n |
| F7 | Finalização | README, merge main, submissão |

## Métricas de Qualidade

| Métrica | Valor |
|---------|-------|
| Testes | 102 |
| Cobertura de código | Alta |
| Tempo de execução | ~1s (CI) |
| Taxa de sucesso | >95% |
| Fallback LLM | Automático |

## Estrutura de Pastas

```
IADev-ProjFinal-Mod2/
├── src/           # Código-fonte do agente
├── tests/         # 102 testes pytest
├── n8n/           # Integração com n8n
├── scripts/       # Scripts utilitários
├── docs/          # Documentação e evidências
├── logs/          # Logs de execução
├── reviews/       # Histórico de revisões
└── .github/       # Pipeline CI
```

## Como Usar

### Execução Simples
```bash
python main.py https://github.com/owner/repo
```

### Com Limites
```bash
python main.py https://github.com/owner/repo --max-prs 5
```

### Modo Seguro (dry-run)
```bash
python main.py https://github.com/owner/repo --dry-run
```

### Via n8n (Automação)
1. Importar `n8n/workflow_pr_review.json`
2. Configurar credenciais
3. Adicionar webhook no GitHub

## Documentação

| Documento | Descrição |
|-----------|-----------|
| [README](../README.md) | Documentação principal |
| [Segurança](seguranca.md) | Modelo de ameaça e defesas |
| [Cenários](cenarios.md) | Cenários de uso e falha |
| [Prompts](prompts.md) | Registro de prompts utilizados |
| [QA](qa/processo_qa_ia.md) | Processo de QA com IA |
| [n8n](../n8n/README.md) | Integração com n8n |

## Evidências

| Fase | Evidência |
|------|-----------|
| F2 | [Segurança](evidencias/fase2_seguranca_evidencia.md) |
| F3 | [Observabilidade](evidencias/observabilidade.md) |
| F4 | [QA com IA](evidencias/fase4_ia_code_review.md) |
| F5 | [DevOps](evidencias/fase5_devops.md) |
| F6 | [n8n](evidencias/fase6_n8n.md) |

## Conclusão

O projeto atendeu todos os requisitos do Projeto Final Módulo 2, demonstrando:

1. **Capacidade técnica**: Agente funcional com LangGraph
2. **Segurança**: Defesa contra prompt-injection
3. **Observabilidade**: Logs estruturados e auditoria
4. **Qualidade**: 102 testes automatizados
5. **Automação**: Integração com n8n
6. **Documentação**: Extensiva e organizada

---

**Projeto Final Módulo 2 - IA para Desenvolvedores (SCTEC)**  
**Prazo**: 31/08/2026  
**Status**: ✅ Concluído