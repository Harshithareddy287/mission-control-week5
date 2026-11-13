# Mission Control — project rules
- Stack: FastAPI back end, vanilla JS front end (no frameworks, no build step), SQLite via Python's sqlite3, model gpt-6-sol via the openai package.
- Only build what the current prompt asks for, on the current feature branch.
- Launch verdict and violations come ONLY from app/rules.py (plain Python, never a model). No model output may ever change the verdict.
- Every model call goes through the LLMClient interface in app/llm/base.py. Tests use FakeLLMClient. Tests must pass with LLM_PROVIDER=fake, no network, no API key.
- Write tests for every feature in tests/. Run `pytest -q` after changes and fix all failures before finishing.
- Front end: render user or model text with textContent, never innerHTML.
- README keeps exactly two commands: start `uvicorn app.main:app --reload`, test `pytest`.
- Do NOT run any git commands (no branch, add, commit, push or PR). The developer handles all git operations. Only write code and run pytest.
