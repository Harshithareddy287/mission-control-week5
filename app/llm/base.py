"""The one interface every model call goes through."""
from dataclasses import dataclass
from typing import Optional, Protocol, runtime_checkable

from app.config import llm_provider


@dataclass
class LLMResult:
    text: str
    input_tokens: int
    output_tokens: int


@runtime_checkable
class LLMClient(Protocol):
    async def complete(
        self, step: str, system: str, user: str, schema: Optional[dict] = None
    ) -> LLMResult:
        """Run one model call for a named pipeline step.

        `schema` is a JSON Schema; when given, the reply text must be JSON matching it.
        """
        ...


def get_client() -> LLMClient:
    """FakeLLMClient when LLM_PROVIDER == "fake" (the default), else OpenAIClient."""
    if llm_provider() == "fake":
        from app.llm.fake import FakeLLMClient

        return FakeLLMClient()
    from app.llm.openai_client import OpenAIClient

    return OpenAIClient()
