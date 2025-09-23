"""Exercise CLI entry points in spds.main to raise E2E coverage."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from spds import main as main_module
from spds.session_store import (
    JsonSessionStore,
    reset_default_session_store,
    set_default_session_store,
)


class DummySwarm:
    def __init__(self, *_, **kwargs):
        self.kwargs = kwargs
        self.started_with_topic = None
        self.started = False

    def start_chat(self):
        self.started = True

    def start_chat_with_topic(self, topic: str):
        self.started_with_topic = topic


def _install_session_store(tmp_path: Path):
    store = JsonSessionStore(tmp_path / "sessions")
    set_default_session_store(store)
    return store


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
    reset_default_session_store()


def test_sessions_list_json(tmp_path, monkeypatch, capsys):
    store = _install_session_store(tmp_path)
    session = store.create(title="CLI Coverage")
    store.save_event(session.events[0])

    exit_code = main_module.main(["sessions", "list", "--json"])
    assert exit_code == 0

    output = capsys.readouterr().out.strip()
    data = json.loads(output)
    assert data[0]["title"] == "CLI Coverage"


def test_sessions_resume_success_and_failure(tmp_path, monkeypatch, capsys):
    store = _install_session_store(tmp_path)
    session = store.create(title="Resume")

    ok_code = main_module.main(["sessions", "resume", session.meta.id])
    assert ok_code == 0
    capsys.readouterr()  # clear captured output

    err_code = main_module.main(["sessions", "resume", "missing-id"])
    assert err_code == 2
    stderr = capsys.readouterr().err
    assert "not found" in stderr


def test_new_session_flag_triggers_swarm(monkeypatch, tmp_path):
    _install_session_store(tmp_path)

    dummy_swarm = DummySwarm()
    monkeypatch.setattr(
        main_module, "SwarmManager", lambda *args, **kwargs: dummy_swarm
    )

    exit_code = main_module.main(
        ["--new-session", "Kickoff", "--agent-ids", "agent-123"]
    )
    assert exit_code == 0
    assert dummy_swarm.started is True


def test_swarm_config_path(monkeypatch, tmp_path):
    _install_session_store(tmp_path)

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
    _install_session_store(tmp_path)

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
