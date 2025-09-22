# Installation & Setup

This guide helps you get the project running quickly for both the Web GUI and CLI.

## Prerequisites
- Python 3.10+
- A Letta ADE server (cloud or self-hosted)

## Create virtual environments
```bash
# CLI venv
python -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt

# Web venv (recommended to isolate web deps)
python -m venv .venv-web && . .venv-web/bin/activate
pip install -r swarms-web/requirements.txt
```

## Configure environment
Create a `.env` at the repo root or export variables in your shell.
```bash
# Core Letta configuration
LETTA_API_KEY=your-api-key        # For Letta Cloud
LETTA_PASSWORD=your-server-pass   # For self-hosted auth (preferred)
LETTA_BASE_URL=http://localhost:8283
LETTA_ENVIRONMENT=SELF_HOSTED     # Or LETTA_CLOUD

# Optional
LOG_LEVEL=INFO
SPDS_INIT_LOGGING=1
LETTA_VALIDATE_CONNECTIVITY=1
```
Notes:
- If both LETTA_PASSWORD and LETTA_SERVER_PASSWORD are set, the app uses LETTA_PASSWORD and logs a deprecation warning for the latter.

## Run the Web GUI
```bash
. .venv-web/bin/activate
cd swarms-web && python run.py
# Open http://localhost:5002
```

## Run the CLI
```bash
. .venv/bin/activate
python -m spds.main
```

## Testing
```bash
# Python tests
pytest --cov=spds --cov-report=html

# Browser E2E (optional; requires Node/Playwright)
# from swarms-web/
# npx playwright install --with-deps
# npx playwright test --workers=1
```

---

If you hit a `typing>=3.10.0.0` error while installing `letta-flask`, see docs/TROUBLESHOOTING.md.
