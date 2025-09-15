PYTHON ?= python3
VENV ?= .venv

.PHONY: venv-cli venv-web install-cli install-web run-cli run-web test lint fmt coverage

venv-cli:
	$(PYTHON) -m venv $(VENV)
	. $(VENV)/bin/activate && pip install -U pip setuptools wheel && pip install -r requirements.txt

venv-web:
	$(PYTHON) -m venv $(VENV)-web
	. $(VENV)-web/bin/activate && pip install -U pip setuptools wheel && pip install -r swarms-web/requirements.txt && pip install git+https://github.com/letta-ai/letta-flask.git

install-cli: venv-cli

install-web: venv-web

run-cli:
	. $(VENV)/bin/activate && $(PYTHON) -m spds.main

run-web:
	. $(VENV)-web/bin/activate && cd swarms-web && $(PYTHON) run.py

test:
	. $(VENV)/bin/activate && pytest -q

coverage:
	. $(VENV)/bin/activate && pytest --cov=spds --cov-report=term-missing

lint:
	. $(VENV)/bin/activate && flake8 && pylint spds || true

fmt:
	. $(VENV)/bin/activate && isort . && black .

