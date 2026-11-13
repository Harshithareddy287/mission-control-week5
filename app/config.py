"""App-wide settings: model, endpoint, prices, provider selection.

Values come from the environment. A local .env file (if present) is loaded
first, without overriding variables that are already set. Tests set
MISSION_CONTROL_SKIP_DOTENV=1 so a developer's .env never leaks into them.
"""
import os
from pathlib import Path

ENV_FILE = Path(__file__).resolve().parent.parent / ".env"


def load_env_file() -> bool:
    """Load .env into os.environ if it exists and loading isn't disabled."""
    if os.environ.get("MISSION_CONTROL_SKIP_DOTENV") == "1" or not ENV_FILE.is_file():
        return False
    from dotenv import load_dotenv

    return load_dotenv(ENV_FILE, override=False)


load_env_file()

MODEL_NAME = os.environ.get("MODEL_NAME") or "gpt-6-sol"
OPENAI_BASE_URL = os.environ.get("OPENAI_BASE_URL") or None  # e.g. Azure AI Foundry endpoint
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY") or None

# USD per 1,000,000 tokens.
# TODO: copy the real gpt-6-sol prices from the provider's pricing page.
# These are placeholders so cost maths can be built and tested.
INPUT_PRICE_PER_1M = 2.00
OUTPUT_PRICE_PER_1M = 8.00


def llm_provider() -> str:
    """Current provider from env; read at call time so tests can change it."""
    return os.environ.get("LLM_PROVIDER", "fake").strip().lower() or "fake"


LLM_PROVIDER = llm_provider()
