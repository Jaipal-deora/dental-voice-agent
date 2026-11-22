from typing import Any

from openai import AsyncOpenAI

from dental_agent.config import settings

client = AsyncOpenAI(
    api_key = settings.llm_api_key or "unset",
    base_url = settings.groq_base_url,
    max_retries=0,
    timeout=settings.agent_timeout_s,
)

def reasoning_args(model:str) -> dict[str,Any]:
    if model.startswith("openai/gpt-oss"):
        return {"reasoning_effort": settings.reasoning_effort}
    return {}
