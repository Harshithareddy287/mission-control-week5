PYTHON := python3
VENV := .venv
BIN := $(VENV)/bin
STAMP := $(VENV)/.requirements-installed

.PHONY: run test setup

# Create .venv if missing and install requirements.txt (re-runs when it changes).
$(STAMP): requirements.txt
	test -d $(VENV) || $(PYTHON) -m venv $(VENV)
	$(BIN)/python -m pip install -r requirements.txt
	touch $(STAMP)

setup: $(STAMP)

run: setup
	$(BIN)/uvicorn app.main:app --reload

test: setup
	LLM_PROVIDER=fake $(BIN)/python -m pytest -q
