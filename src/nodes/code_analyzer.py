import os
from typing import Dict, Any
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import SystemMessage, HumanMessage

from src.state import PRReviewState

SYSTEM_PROMPT = """You are a senior code reviewer focused on best practices and readability.

Analyze the provided code diff and generate a structured review in Markdown with exactly two sections:

## Pontos Positivos
- List specific things the code does well

## Oportunidades de Melhoria
- List specific suggestions with line references when possible

Focus on: code readability, best practices, potential bugs, security concerns, and maintainability.
Be constructive and specific. Always reference file names and line numbers from the diff."""


def _get_llm():
    return ChatGoogleGenerativeAI(
        model="gemini-2.0-flash",
        google_api_key=os.getenv("GOOGLE_API_KEY")
    )


def analisar_codigo(state: PRReviewState) -> Dict[str, Any]:
    llm = _get_llm()
    diff = state["current_diff"]
    response = llm.invoke([
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=f"Review the following code diff:\n\n{diff}")
    ])
    return {"current_review": response.content}
