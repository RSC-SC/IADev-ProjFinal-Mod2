import os
import logging
from typing import Dict, Any, Optional
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import SystemMessage, HumanMessage

from src.state import PRReviewState

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a senior code reviewer focused on best practices and readability.

Analyze the provided code diff and generate a structured review in Markdown with exactly two sections:

## Pontos Positivos
- List specific things the code does well

## Oportunidades de Melhoria
- List specific suggestions with line references when possible

Focus on: code readability, best practices, potential bugs, security concerns, and maintainability.
Be constructive and specific. Always reference file names and line numbers from the diff."""


def _try_gemini() -> Optional[BaseChatModel]:
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        return None
    try:
        from langchain_google_genai import ChatGoogleGenerativeAI
        return ChatGoogleGenerativeAI(
            model="gemini-2.0-flash",
            google_api_key=api_key
        )
    except Exception as e:
        logger.warning(f"Falha ao carregar Gemini: {e}")
        return None


def _try_openrouter() -> Optional[BaseChatModel]:
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        return None
    try:
        from langchain_openai import ChatOpenAI
        model = os.getenv("OPENROUTER_MODEL", "nvidia/nemotron-3-super-120b-a12b:free")
        return ChatOpenAI(
            model=model,
            api_key=api_key,
            base_url="https://openrouter.ai/api/v1",
            default_headers={
                "HTTP-Referer": "https://github.com/RSC-SC/IADev-MiniProj-Mod2",
                "X-Title": "Agente Revisor de PRs"
            }
        )
    except Exception as e:
        logger.warning(f"Falha ao carregar OpenRouter: {e}")
        return None


def _invoke_with_fallback(messages, providers) -> str:
    last_error = None
    for name, try_fn in providers:
        llm = try_fn()
        if llm is None:
            continue
        try:
            logger.info(f"Tentando provedor LLM: {name}")
            response = llm.invoke(messages)
            return response.content
        except Exception as e:
            logger.warning(f"Provedor {name} falhou: {e}")
            last_error = e
    raise RuntimeError(
        f"Nenhum provedor LLM conseguiu processar a requisicao. "
        f"Ultimo erro: {last_error}"
    )


def _get_providers():
    return [
        ("Gemini", _try_gemini),
        ("OpenRouter", _try_openrouter),
    ]


def analisar_codigo(state: PRReviewState) -> Dict[str, Any]:
    diff = state["current_diff"]
    messages = [
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=f"Review the following code diff:\n\n{diff}")
    ]
    review = _invoke_with_fallback(messages, _get_providers())
    return {"current_review": review}
