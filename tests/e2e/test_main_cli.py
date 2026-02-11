"""Exercise CLI entry points in spds.main to raise E2E coverage."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from spds import main as main_module


class DummySwarm:
    def __init__(self, *_, **kwargs):
        self.kwargs = kwargs
        self.started_with_topic = None
        self.started = False

    def start_chat(self):
        self.started = True

    def start_chat_with_topic(self, topic: str):
        self.started_with_topic = topic


@pytest.fixture(autouse=True)
def isolate_config(monkeypatch: pytest.MonkeyPatch):
    # Prevent real network/config lookups.
    monkeypatch.setattr(
        main_module.config,
        "validate_letta_config",
        lambda check_connectivity=False: True,
    )
    monkeypatch.setattr(main_module.config, "get_letta_password", lambda: "test-token")
    monkeypatch.setattr(
        main_module.config, "LETTA_ENVIRONMENT", "SELF_HOSTED", raising=False
    )
    monkeypatch.setattr(
        main_module.config, "LETTA_BASE_URL", "http://localhost:8283", raising=False
    )
    monkeypatch.setattr(
        main_module,
        "Letta",
        lambda *_, **__: SimpleNamespace(
            agents=SimpleNamespace(), tools=SimpleNamespace()
        ),
    )
    yield


def test_sessions_list_json(monkeypatch, capsys):
    """Test sessions list --json with mocked ConversationManager."""
    mock_conv = Mock()
    mock_conv.id = "conv-abc123"
    mock_conv.created_at = None
    mock_conv.updated_at = None
    mock_conv.summary = "Test Session"

    mock_cm = Mock()
    mock_cm.list_sessions.return_value = [mock_conv]
    mock_cm.get_session_summary.return_value = {
        "id": "conv-abc123",
        "agent_id": "agent-1",
        "summary": "Test Session",
        "created_at": "2026-02-11T00:00:00",
        "updated_at": "2026-02-11T00:00:00",
    }

    monkeypatch.setattr(
        main_module, "ConversationManager", lambda client: mock_cm
    )

    exit_code = main_module.main(
        ["sessions", "list", "--agent-id", "agent-1", "--json"]
    )
    assert exit_code == 0

    output = capsys.readouterr().out.strip()
    data = json.loads(output)
    assert data[0]["summary"] == "Test Session"


def test_sessions_resume_success_and_failure(monkeypatch, capsys):
    """Test sessions resume with mocked ConversationManager."""
    mock_cm = Mock()
    mock_cm.get_session.return_value = Mock(id="conv-123")

    monkeypatch.setattr(
        main_module, "ConversationManager", lambda client: mock_cm
    )

    ok_code = main_module.main(["sessions", "resume", "conv-123"])
    assert ok_code == 0
    capsys.readouterr()

    # Now test failure
    mock_cm.get_session.side_effect = Exception("Not found")
    err_code = main_module.main(["sessions", "resume", "missing-id"])
    assert err_code == 2
    stderr = capsys.readouterr().err
    assert "not found" in stderr.lower()


def test_session_id_sets_context(monkeypatch):
    """Test that --session-id sets the conversation context."""
    dummy_swarm = DummySwarm()
    monkeypatch.setattr(
        main_module, "SwarmManager", lambda *args, **kwargs: dummy_swarm
    )

    exit_code = main_module.main(["--session-id", "conv-999", "--agent-ids", "agent-1"])
    assert exit_code == 0
    assert dummy_swarm.started is True


def test_swarm_config_path(monkeypatch, tmp_path):
    profiles = [
        {
            "name": "Playwright Agent",
            "persona": "UI Specialist",
            "expertise": ["ui", "automation"],
            "model": "openai/gpt-4",
            "embedding": "openai/text-embedding-ada-002",
        }
    ]
    config_path = tmp_path / "swarm.json"
    config_path.write_text(json.dumps(profiles))

    dummy_swarm = DummySwarm()
    monkeypatch.setattr(
        main_module, "SwarmManager", lambda *args, **kwargs: dummy_swarm
    )

    # Provide canned input for topic prompt.
    monkeypatch.setattr("builtins.input", lambda prompt="": "Playwright Coverage")

    exit_code = main_module.main(["--swarm-config", str(config_path)])
    assert exit_code == 0
    assert dummy_swarm.started is True


def test_agent_ids_flow(monkeypatch, tmp_path):
    dummy_swarm = DummySwarm()

    # Mock Letta client to provide retrieve responses.
    agents_ns = SimpleNamespace()
    agents_ns.retrieve = lambda agent_id: SimpleNamespace(
        id=agent_id,
        name="Mock Agent",
        system="You are Mock Agent. Your persona is: Tester. Your expertise is in: testing.",
    )
    agents_ns.list = lambda **_: []
    agents_ns.messages = SimpleNamespace(
        create=lambda **_: SimpleNamespace(messages=[])
    )
    agents_ns.tools = SimpleNamespace(attach=lambda **_: SimpleNamespace())

    monkeypatch.setattr(
        main_module,
        "Letta",
        lambda *_, **__: SimpleNamespace(
            agents=agents_ns,
            tools=SimpleNamespace(
                create_from_function=lambda **_: SimpleNamespace(id="tool-1")
            ),
        ),
    )
    monkeypatch.setattr(
        main_module, "SwarmManager", lambda *args, **kwargs: dummy_swarm
    )

    exit_code = main_module.main(["--agent-ids", "agent-001"])
    assert exit_code == 0
    assert dummy_swarm.started is True
