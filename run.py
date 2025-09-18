#!/usr/bin/env python3
"""
Repository-level run.py shim for Playwright webServer.

This script forwards execution to `swarms-web/run.py` so the Playwright
config (which runs `python run.py` from the repository root) will start the
web UI correctly without modifying the Playwright config.
"""
import os
import sys

ROOT = os.path.dirname(__file__)
WEB_RUN = os.path.join(ROOT, "swarms-web", "run.py")

if not os.path.exists(WEB_RUN):
    print(f"Error: expected web runner at {WEB_RUN} but it does not exist.")
    sys.exit(2)

# Execute the web runner with the same Python interpreter, forwarding args
os.execv(sys.executable, [sys.executable, WEB_RUN] + sys.argv[1:])
