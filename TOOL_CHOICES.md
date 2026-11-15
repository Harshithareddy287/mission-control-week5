# Tool Choices

## Back end: FastAPI

- **Specific reason:** FastAPI validates the report form with Pydantic models (`app/models.py`), and `app/errors.py` turns each failure into a 422 response with a plain message per field, such as "Wind (knots) is required". Its native `async` support lets `app/checks.py` run the three model checks at the same time with `asyncio.gather`. Its `TestClient` lets the API tests run in-process, with no server and no network.
- **Rejected alternative:** Flask. It has no built-in request validation, and its async support is weaker, so the per-field error messages and the parallel checks would need extra libraries and glue code.
- **Customer concern:** "Can a bad or malicious report break the launch verdict?" Every request is validated before any work starts, and the verdict comes only from plain Python in `app/rules.py`, which never reads model output.

## Front end: Vanilla JS (HTML, CSS, JavaScript)

- **Specific reason:** The console is one form, a report list and a detail view, so plain HTML, CSS and JavaScript in `static/`, served by FastAPI itself, are enough. There is no build step, so one command (`make run`, which starts uvicorn) runs the whole app.
- **Rejected alternative:** React. It would add Node, a bundler and a second start command for a screen that has no complex client-side state.
- **Customer concern:** "Could a hostile note run script in the Flight Director's browser?" `static/app.js` renders all user and model text with `textContent`, never `innerHTML`, and `tests/test_console_api.py` fails if `innerHTML` ever appears.

## Database: SQLite

- **Specific reason:** Reports, results, briefings and approvals must still be there after a restart. Python's built-in `sqlite3` writes them to a single file (`mission_control.db`, or the path in `DB_PATH`) with no server to install, and `test_reports_survive_restart` in `tests/test_reports.py` confirms the data survives a new app instance.
- **Rejected alternative:** PostgreSQL. It would need a separate server running before the app or the tests could start, which breaks the one-command start for a single-console app.
- **Customer concern:** "Will we lose reports if the app crashes or restarts mid-countdown?" Each report is saved to the database file as soon as it is filed, before the pipeline runs, and the restart test proves the saved data comes back unchanged.

## Model: gpt-6-sol on Azure AI Foundry

- **Specific reason:** The classify, check and review steps send a JSON schema with `strict: True` through the OpenAI-compatible Responses API (`app/llm/openai_client.py`). The code then validates every reply again, and anything invalid falls back safely, for example to `other` / `high` in `app/classify.py`. Every call goes through the `LLMClient` interface in `app/llm/base.py`, so the tests use `FakeLLMClient` and need no network or API key.
- **Rejected alternative:** A self-hosted open-weight model. It would need GPU hosting, and its structured-output support is less reliable, for a pipeline that depends on schema-checked replies.
- **Customer concern:** "What does each report cost us?" `app/cost.py` calculates each step's and report's cost in code from the token counts, at the real Azure AI Foundry Global Standard prices of $2.00 input and $10.00 output per 1M tokens (set in `app/config.py`). In practice a report (8 steps, 6 model calls) costs about $0.005 when routine and about $0.009 when flagged, and the console shows the cost on every trace card.