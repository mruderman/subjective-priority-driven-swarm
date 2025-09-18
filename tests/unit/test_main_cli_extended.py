import sys
from io import StringIO
from unittest.mock import patch

import pytest


def test_main_agent_names():
    class DummySwarm:
        def __init__(self, **kwargs):
            DummySwarm.kwargs = kwargs

        def start_chat(self):
            pass

    with patch("spds.main.SwarmManager", DummySwarm), patch("spds.main.Letta"):
        from spds.main import main

        captured = StringIO()
        sys.stdout = captured
        main(["--agent-names", "Alice", "Bob"])
        sys.stdout = sys.__stdout__

    assert DummySwarm.kwargs["agent_names"] == ["Alice", "Bob"]


def test_main_swarm_config_happy():
    profiles = [
        {
            "name": "A",
            "persona": "p",
            "expertise": ["x"],
            "model": "openai/gpt-4",
            "embedding": "openai/text-embedding-ada-002",
        },
        {
            "name": "B",
            "persona": "p",
            "expertise": ["y"],
            "model": "openai/gpt-4",
            "embedding": "openai/text-embedding-ada-002",
        },
    ]

    class DummySwarm:
        called = {}

        def __init__(self, **kwargs):
            DummySwarm.called["kwargs"] = kwargs

        def start_chat(self):
            DummySwarm.called["start_chat"] = True

    with patch("spds.main.load_swarm_from_file", return_value=profiles), patch(
        "spds.main.SwarmManager", DummySwarm
    ), patch("spds.main.Letta"):
        from spds.main import main

        captured = StringIO()
        sys.stdout = captured
        main(["--swarm-config", "dummy.json"])
        sys.stdout = sys.__stdout__

    assert DummySwarm.called["kwargs"]["agent_profiles"] == profiles
    assert DummySwarm.called.get("start_chat") is True


def test_main_interactive_cancel():
    with patch("spds.main.interactive_agent_selection", return_value=None), patch(
        "spds.main.Letta"
    ):
        from spds.main import main

        with pytest.raises(SystemExit) as ei:
            main(["--interactive"])
        assert ei.value.code == 1


def test_main_cloud_api_key():
    with patch("spds.main.config.LETTA_ENVIRONMENT", "LETTA_CLOUD"), patch(
        "spds.main.config.LETTA_SERVER_PASSWORD", ""
    ), patch("spds.main.config.LETTA_API_KEY", "api-key"), patch(
        "spds.main.config.LETTA_BASE_URL", "http://x"
    ), patch(
        "spds.main.SwarmManager"
    ) as SM, patch(
        "spds.main.Letta"
    ) as L:
        from spds.main import main

        with patch("builtins.input", return_value="T"):
            main([])
        _, kwargs = L.call_args
        assert kwargs["token"] == "api-key"
        assert kwargs["base_url"] == "http://x"


def test_main_no_auth_baseurl_only(monkeypatch):
    monkeypatch.delenv("LETTA_PASSWORD", raising=False)
    monkeypatch.delenv("LETTA_SERVER_PASSWORD", raising=False)
    with patch("spds.main.config.LETTA_ENVIRONMENT", "SELF_HOSTED"), patch(
        "spds.main.config.LETTA_API_KEY", ""
    ), patch(
        "spds.main.config.LETTA_BASE_URL", "http://x"
    ), patch(
        "spds.main.SwarmManager"
    ) as SM, patch(
        "spds.main.Letta"
    ) as L:
        from spds.main import main

        with patch("builtins.input", return_value="T"):
            main([])
        _, kwargs = L.call_args
        assert "token" not in kwargs
        assert kwargs["base_url"] == "http://x"
