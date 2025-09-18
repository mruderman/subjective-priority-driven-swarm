import sys
from io import StringIO
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest


def test_main_ephemeral_default(monkeypatch):
    # Patch config profiles to small list
    from spds import config as real_config

    profiles = [
        {
            "name": "A",
            "persona": "p",
            "expertise": ["x"],
            "model": "openai/gpt-4",
            "embedding": "openai/text-embedding-ada-002",
        }
    ]

    calls = {}

    class DummySwarm:
        def __init__(self, **kwargs):
            calls["kwargs"] = kwargs

        def start_chat_with_topic(self, topic):
            calls["start_with_topic"] = topic

    with patch("spds.main.config.AGENT_PROFILES", profiles), patch(
        "spds.main.SwarmManager", DummySwarm
    ), patch("spds.main.Letta"):
        from spds.main import main

        # Provide topic input first
        monkeypatch.setattr("builtins.input", lambda prompt="": "My Topic")
        captured = StringIO()
        sys.stdout = captured
        main([])
        sys.stdout = sys.__stdout__

    assert calls["kwargs"]["agent_profiles"] == profiles
    assert calls["kwargs"]["conversation_mode"] == "sequential"
    assert calls["start_with_topic"] == "My Topic"
    out = captured.getvalue()
    assert "Swarm chat started" in out


def test_main_interactive_flag(monkeypatch):
    # interactive selection returns tuple
    selection = (["ag-1", "ag-2"], "TopicX", "hybrid", True, "adaptive", "discussion")

    container = {}

    class DummySwarm:
        def __init__(self, **kwargs):
            self.kwargs = kwargs
            self.started = None

        def start_chat_with_topic(self, topic):
            container["topic"] = topic

    with patch("spds.main.interactive_agent_selection", return_value=selection), patch(
        "spds.main.SwarmManager", DummySwarm
    ), patch("spds.main.Letta"):
        from spds.main import main

        captured = StringIO()
        sys.stdout = captured
        main(["--interactive"])
        sys.stdout = sys.__stdout__

    out = captured.getvalue()
    assert "Interactive agent selection" in out
    assert container.get("topic") == "TopicX"


def test_main_agent_ids(monkeypatch):
    class DummySwarm:
        def __init__(self, **kwargs):
            self.kwargs = kwargs
            DummySwarm.kwargs = kwargs

        def start_chat(self):
            pass

    with patch("spds.main.SwarmManager", DummySwarm), patch("spds.main.Letta"):
        from spds.main import main

        captured = StringIO()
        sys.stdout = captured
        main(["--agent-ids", "foo", "bar"])
        sys.stdout = sys.__stdout__

    assert DummySwarm.kwargs["agent_ids"] == ["foo", "bar"]
    assert DummySwarm.kwargs["conversation_mode"] == "sequential"


def test_main_swarm_config_invalid_path():
    from spds.main import main

    with pytest.raises(SystemExit) as ei:
        main(["--swarm-config", "does-not-exist.json"])
    assert ei.value.code == 1


def test_main_auth_selection_self_hosted_password():
    with patch("spds.main.config.LETTA_ENVIRONMENT", "SELF_HOSTED"), patch(
        "spds.main.config.LETTA_SERVER_PASSWORD", "pw"
    ), patch("spds.main.config.LETTA_API_KEY", ""), patch(
        "spds.main.config.LETTA_BASE_URL", "http://x"
    ), patch(
        "spds.main.SwarmManager"
    ) as SM, patch(
        "spds.main.Letta"
    ) as L:
        from spds.main import main

        # Minimal run: ephemeral topic
        with patch("builtins.input", return_value="T"):
            main([])
        L.assert_called()
        args, kwargs = L.call_args
        assert kwargs["token"] == "pw"
        assert kwargs["base_url"] == "http://x"


def test_main_handles_swarm_initialization_error(monkeypatch, capsys):
    class FailingSwarm:
        def __init__(self, **kwargs):
            raise ValueError("bad swarm config")

    with patch("spds.main.config.LETTA_ENVIRONMENT", "SELF_HOSTED"), patch(
        "spds.main.config.LETTA_SERVER_PASSWORD", ""
    ), patch("spds.main.config.LETTA_API_KEY", ""), patch(
        "spds.main.config.LETTA_BASE_URL", "http://x"
    ), patch("spds.main.SwarmManager", FailingSwarm), patch("spds.main.Letta"):
        from spds.main import main

        with pytest.raises(SystemExit) as excinfo:
            main(["--agent-ids", "ag-1"])

    assert excinfo.value.code == 1
    captured = capsys.readouterr()
    assert "Error initializing swarm" in captured.out
