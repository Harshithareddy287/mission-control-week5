"""Manual smoke test: one real classify call. NOT part of the test suite.

    python scripts/smoke_llm.py

Reads MODEL_NAME, OPENAI_BASE_URL and OPENAI_API_KEY from .env / the environment.
Makes one paid model call. Never prints the API key.
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import config  # noqa: E402  (loads .env on import)
from app.classify import classify  # noqa: E402
from app.llm.openai_client import OpenAIClient  # noqa: E402

SAMPLE_REPORT = {
    "name": "Smoke Test",
    "station": "Pad 39",
    "wind_knots": 12,
    "temp_c": 15,
    "fuel_pct": 99,
    "note": "Valve 3 on the LOX fill line is slow to close, about 4 seconds late.",
}


class RecordingClient:
    """Keeps the error that classify() would otherwise swallow into its fallback."""

    def __init__(self, inner):
        self.inner = inner
        self.error = None

    async def complete(self, *args, **kwargs):
        try:
            return await self.inner.complete(*args, **kwargs)
        except Exception as exc:
            self.error = exc
            raise


async def main() -> int:
    if not config.OPENAI_API_KEY:
        print("OPENAI_API_KEY is not set (add it to .env).")
        return 2

    client = RecordingClient(OpenAIClient())
    print(f"Model: {config.MODEL_NAME}")
    print(f"Endpoint: {config.OPENAI_BASE_URL or '(default OpenAI)'}")

    classification, result, fallback = await classify(client, SAMPLE_REPORT)

    print(f"Classification: subsystem={classification.subsystem} severity={classification.severity}")
    print(f"Fallback: {fallback}")
    print(f"Tokens: input={result.input_tokens} output={result.output_tokens}")
    if client.error is not None:
        print(f"Call failed: {type(client.error).__name__}: {client.error}")
    elif fallback:
        print(f"Model reply did not validate: {result.text[:300]!r}")
    return 1 if fallback else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
