# Troubleshooting

## `letta-flask` install error: typing>=3.10.0.0
If pip fails with:
```
ERROR: Could not find a version that satisfies the requirement typing>=3.10.0.0 (from letta-flask)
ERROR: No matching distribution found for typing>=3.10.0.0
```
This comes from an invalid dependency constraint in the upstream package.

Workarounds:
- Use the repository’s local shim (recommended for development). The repo includes a minimal `letta_flask` package that satisfies the Web UI imports; running the web server from the repo root will import it without installing `letta-flask`.
- Install without dependencies:
  ```bash
  pip install --no-deps git+https://github.com/letta-ai/letta-flask.git
  ```
  Ensure `letta-client` and other runtime deps are already installed.
- Clone and edit metadata (advanced): remove/fix the `typing` constraint in pyproject/setup, then `pip install .`.

## Playwright/Browser deps
If Playwright cannot install browsers due to apt issues, resolve system keyrings and rerun:
```bash
# from swarms-web/
# npx playwright install --with-deps
```
Run tests with one worker to reduce timing races:
```bash
# npx playwright test --workers=1
```

## Server doesn’t start
- Check your `.env` and connectivity (use `spds.config.validate_letta_config(check_connectivity=True)`).
- Review logs printed at startup; Flask/SocketIO errors will appear in the console.
