# Web GUI Guide

The Web GUI lives in `swarms-web/` and provides a real-time, Bootstrap 5 interface with WebSocket updates.

## Run
```bash
. .venv-web/bin/activate
cd swarms-web
python run.py   # http://localhost:5002
```

## Highlights
- Visual agent selection with cards and checkboxes
- Four conversation modes (Hybrid, All-Speak, Sequential, Pure Priority)
- Live phases and scores during conversations
- Secretary panel with `/minutes`, `/export`, and other commands

## Tips
- Ensure your Letta environment variables are set (see docs/INSTALL.md)
- Secretary features generate minutes using the Letta API pattern

## E2E Tests (optional)
```bash
# from swarms-web/
# npx playwright install --with-deps
# npx playwright test --workers=1
```

If Playwright fails due to system packages, see docs/TROUBLESHOOTING.md.
