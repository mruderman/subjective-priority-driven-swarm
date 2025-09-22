# Repository Guidelines

## Project Structure & Module Organization
- `spds/` – Core Python package (CLI, agents, config, exports, integrations, session management).
- `spds/integrations/` – External tool integrations (Composio, MCP, registry management).
- `swarms-web/` – Flask web UI with WebSocket support (`app.py`, `run.py`, `templates/`, `static/`, E2E tests).
- `tests/` – Comprehensive Pytest suite (unit, integration, e2e tests with fixtures).
- `exports/` – Generated minutes/transcripts (organized by sessions).
- Root configs: `pyproject.toml`, `.flake8`, `pytest.ini`, `.pre-commit-config.yaml`, `Makefile`.
- Agent configs: `creative_swarm.json`, `openai_swarm.json`, `tool_swarm.json`, `vision_swarm.json`.

## Build, Test, and Development Commands
- Create env and install: `python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt`
- Web UI deps: `pip install -r swarms-web/requirements.txt && pip install git+https://github.com/letta-ai/letta-flask.git`
- Run CLI: `python -m spds.main` (interactive mode) or `python -m spds.main --help` for options
- Run Web: `cd swarms-web && python run.py` (http://localhost:5002)
- Session management: `python -m spds.main sessions list|show|delete`
- Tests + coverage: `pytest --cov=spds --cov-report=html` (HTML report in `htmlcov/`)
- Test categories: `pytest tests/unit/` (unit), `pytest tests/integration/` (integration), `pytest tests/e2e/` (e2e)
- Lint/format: `black . && isort . && flake8 && pylint spds`
- Pre-commit: `pre-commit install && pre-commit run -a`
- Makefile shortcuts: `make venv-cli`, `make run-cli`, `make venv-web`, `make run-web`, `make test`, `make coverage`

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

Model notes:
- Agent LLM models are configured per-agent in Letta. This app does not change an agent’s model at runtime.
- When the app creates ephemeral agents, it uses `DEFAULT_AGENT_MODEL` and `DEFAULT_EMBEDDING_MODEL` from `spds/config.py` as fallbacks.

Continuity policy:
- Prefer existing agents by ID or name. By default, `SPDS_ALLOW_EPHEMERAL_AGENTS=false` forbids new agent creation from profiles. Set it to `true` explicitly for demos or development.
  - To reuse a secretary, set `SECRETARY_AGENT_ID` or `SECRETARY_AGENT_NAME`.
- For the secretary, reuse via `SECRETARY_AGENT_ID` or `SECRETARY_AGENT_NAME`. Creation is blocked when ephemerals are disabled.

Troubleshooting note:

If you run into an installation error when setting up the web UI related to
`letta-flask` (for example, a `typing>=3.10.0.0` requirement error), see the
Troubleshooting section in `README.md` for workarounds (local shim, install
without-deps, or editing the upstream package metadata).

