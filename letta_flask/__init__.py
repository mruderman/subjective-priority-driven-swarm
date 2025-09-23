"""Minimal local shim for `letta_flask` used in tests and local runs.

This shim provides a tiny compatibility layer exposing the names
expected by `swarms-web/app.py`: LettaFlask and LettaFlaskConfig.

It intentionally implements a no-op behavior suitable for local testing
and Playwright-driven E2E tests where the external package is not
available or fails to install due to packaging metadata issues.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class LettaFlaskConfig:
    base_url: Optional[str] = None
    api_key: Optional[str] = None


class LettaFlask:
    """A minimal stand-in for the real LettaFlask.

    The real package integrates with Letta services; for tests we only
    need the object to be present and to support init_app(app).
    """

    def __init__(self, config: Optional[LettaFlaskConfig] = None):
        self.config = config
        # track whether init_app was called
        self._inited = False

    def init_app(self, app):
        # store a reference on the Flask app for introspection in tests
        setattr(app, "letta_flask_config", self.config)
        self._inited = True

    # Provide a no-op context manager API used by some codepaths
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False
