# Mission Control — Go/No-Go Launch Console

Engineers file anomaly reports; a pipeline classifies them, checks launch limits in code,
runs safety checks, drafts a reviewed briefing, and the Flight Director approves it.

**Stack:** FastAPI · vanilla JS · SQLite · gpt-6-sol

## Setup (once)
    python3 -m venv .venv && source .venv/bin/activate
    pip install -r requirements.txt

## Start the app
    uvicorn app.main:app --reload

Open http://127.0.0.1:8000

## Run the tests
    pytest

Tests need no network and no API key (model calls use a fake client).
