"""Real model client (OpenAI-compatible Responses API, e.g. Azure AI Foundry).

`openai` is imported lazily, and the SDK client is only created on the first
call, so tests never need the package, a key or the network.
"""
from typing import Optional

from app import config
from app.llm.base import LLMResult


class OpenAIClient:
    def __init__(
        self,
        model: Optional[str] = None,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
    ):
        self.model = model or config.MODEL_NAME
        self.base_url = base_url or config.OPENAI_BASE_URL
        self._api_key = api_key or config.OPENAI_API_KEY
        self._client = None

    def __repr__(self) -> str:  # never show the key
        return f"OpenAIClient(model={self.model!r}, base_url={self.base_url!r})"

    def _get_client(self):
        if self._client is None:
            from openai import AsyncOpenAI  # lazy import

            self._client = AsyncOpenAI(base_url=self.base_url, api_key=self._api_key)
        return self._client

    async def complete(
        self, step: str, system: str, user: str, schema: Optional[dict] = None
    ) -> LLMResult:
        kwargs = {}
        if schema is not None:
            kwargs["text"] = {
                "format": {
                    "type": "json_schema",
                    "name": step,
                    "schema": schema,
                    "strict": True,
                }
            }

        response = await self._get_client().responses.create(
            model=self.model,
            instructions=system,
            input=user,
            **kwargs,
        )
        usage = response.usage
        return LLMResult(
            text=response.output_text or "",
            input_tokens=usage.input_tokens if usage else 0,
            output_tokens=usage.output_tokens if usage else 0,
        )
