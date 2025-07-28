# Repository Guidelines

## Project Structure & Module Organization
- `spds/` – Core Python package (CLI, agents, config, exports).
- `swarms-web/` – Flask web UI (`app.py`, `run.py`, `templates/`, `static/`).
- `tests/` – Pytest suite.
- `exports/` – Generated minutes/transcripts.
- Root configs: `pyproject.toml`, `.flake8`, `pytest.ini`, `.pre-commit-config.yaml`.

## Build, Test, and Development Commands
- Create env and install: `python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt`
- Web UI deps: `pip install -r swarms-web/requirements.txt`
- Run CLI: `python -m spds.main`
- Run Web: `cd swarms-web && python run.py` (http://localhost:5002)
- Tests + coverage: `pytest` (HTML report in `htmlcov/`)
- Lint/format: `black . && isort . && flake8 && pylint spds`
- Pre-commit: `pre-commit install && pre-commit run -a`

## Coding Style & Naming Conventions
- Python 3.8+; 4-space indentation.
- Formatting: Black (88 cols), Isort (`profile=black`).
- Linting: Flake8 (ignores `E203,W503`), Pylint tuned in `pyproject.toml`.
- Naming: `snake_case` for modules/functions, `CamelCase` for classes, `UPPER_CASE` for constants.
- Keep imports ordered; prefer type hints; add concise docstrings for public functions.

## Testing Guidelines
- Framework: Pytest with markers: `unit`, `integration`, `e2e`, `slow`.
- Conventions (from `pytest.ini`): files `test_*.py`, classes `Test*`, functions `test_*`.
- Typical runs: `pytest -m 'not slow'` or `pytest tests/spds`.
- New/changed code should include tests; aim for meaningful coverage (reports via `--cov=spds`).

## Commit & Pull Request Guidelines
- Commits: imperative, present tense; keep focused. Examples:
  - `Fix webapp alignment: pass topic to agent`
  - `Performance: remove API overhead in CLI`
- Reference issues (`Fixes #123`).
- PRs must include: clear description, rationale, test plan, and screenshots for UI changes.
- CI hygiene: run `pre-commit run -a` and `pytest` locally before opening/merging.

## Security & Configuration Tips
- Secrets: never commit `.env`; use `.env.example` when adding new keys.
- Core envs: `LETTA_API_KEY`, `LETTA_PASSWORD`, `LETTA_BASE_URL`, `LETTA_ENVIRONMENT`.
- Config lives in `spds/config.py`; avoid logging secrets; prefer environment variables over hardcoding.

