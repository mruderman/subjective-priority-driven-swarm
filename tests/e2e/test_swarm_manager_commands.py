"""High-level SwarmManager command handling exercised with stubbed agents.

These tests focus on slash-command logic, export wiring, and memory-awareness
utilities that power the interactive GUI/Playwright flows. By executing the
real SwarmManager methods with lightweight stubs we drive coverage over the
python backend that supports the Playwright experience without touching the
network.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest


class StubAgent:
    """Minimal SPDSAgent stand-in for command handling tests."""

    def __init__(self, agent_state: SimpleNamespace, client):
        self.client = client
        self.agent = agent_state
        self.name = agent_state.name
        self.expertise = ["testing", "analysis"]
        self.priority_score = 0.0
        self.motivation_score = 0.0

    @classmethod
    def create_new(
        cls,
        name: str,
        persona: str,
        expertise: list[str],
        client,
        model: str | None = None,
        embedding: str | None = None,
    ):
        state = SimpleNamespace(
            id=f"{name.lower().replace(' ', '-')}-id",
            name=name,
            system=(
                f"You are {name}. Your persona is: {persona}. "
                f"Your expertise is in: {', '.join(expertise)}."
            ),
            tools=[],
        )
        return cls(state, client)

    def assess_motivation_and_priority(self, topic: str):
        self.motivation_score = 6
        self.priority_score = 0.8

    def speak(self, conversation_history: str = "", **_):
        topic_hint = conversation_history or "topic"
        content = [{"text": f"Responding about {topic_hint}"}]
        return SimpleNamespace(
            messages=[SimpleNamespace(role="assistant", content=content)]
        )


class StubSecretary:
    def __init__(self, client, mode: str = "adaptive"):
        self.client = client
        self.mode = mode
        self.agent = SimpleNamespace(name="Secretary Bot")
        self.meeting_metadata = {"title": "Coverage Meeting"}
        self.conversation_log: list[tuple[str, str]] = []
        self.action_items: list[str] = []
        self.decisions: list[str] = []

    def generate_minutes(self) -> str:
        return "Minutes content"

    def set_mode(self, mode: str):
        self.mode = mode

    def add_action_item(self, item: str):
        self.action_items.append(item)

    def get_conversation_stats(self) -> dict:
        return {
            "messages": len(self.conversation_log),
            "actions": len(self.action_items),
        }

    def observe_message(self, agent_name: str, message: str):
        self.conversation_log.append((agent_name, message))


class StubExportManager:
    def export_meeting_minutes(self, meeting_data, style: str) -> str:
        return f"{style}-minutes.md"

    def export_raw_transcript(self, conversation, metadata) -> str:
        return "transcript.txt"

    def export_action_items(self, items, metadata) -> str:
        return "actions.txt"

    def export_executive_summary(self, meeting_data) -> str:
        return "summary.txt"

    def export_complete_package(self, meeting_data, mode: str) -> list[str]:
        return ["minutes.md", "summary.txt", "actions.txt"]


class FakeLettaClient:
    def __init__(self):
        self.agents = SimpleNamespace()
        self.agents.create = self._agents_create
        self.agents.retrieve = self._agents_retrieve
        self.agents.list = self._agents_list
        self.agents.messages = SimpleNamespace()
        self.agents.messages.create = self._agents_messages_create
        self.agents.tools = SimpleNamespace()
        self.agents.tools.attach = lambda **_: SimpleNamespace()
        self.agents.context = SimpleNamespace()
        self.agents.context.retrieve = self._agents_context_retrieve
        self.tools = SimpleNamespace()
        self.tools.create_from_function = lambda **_: SimpleNamespace(id="tool-1")

    def _agents_create(self, **kwargs):
        return SimpleNamespace(
            id="created-agent",
            name=kwargs.get("name", "Agent"),
            system=kwargs.get("system", ""),
            tools=[],
        )

    def _agents_retrieve(self, agent_id: str):
        return SimpleNamespace(
            id=agent_id, name=f"Agent {agent_id}", system="You are...", tools=[]
        )

    def _agents_list(self, name: str | None = None, limit: int = 1):
        if name == "missing":
            return []
        return [
            SimpleNamespace(
                id=f"{name}-id", name=name or "Listed", system="You are...", tools=[]
            )
        ]

    def _agents_messages_create(self, **_):
        return SimpleNamespace(
            messages=[
                SimpleNamespace(role="assistant", content=[{"text": "Generated"}])
            ]
        )

    def _agents_context_retrieve(self, **_):
        return {"num_recall_memory": 42, "num_archival_memory": 3}


@pytest.fixture
def configured_swarm_manager(monkeypatch: pytest.MonkeyPatch):
    import spds.swarm_manager as swarm_manager

    fake_client = FakeLettaClient()

    # Ensure helper functions are predictable and side-effect free.
    monkeypatch.setattr(
        swarm_manager, "letta_call", lambda op, fn, **kwargs: fn(**kwargs)
    )
    monkeypatch.setattr(swarm_manager, "SPDSAgent", StubAgent)
    monkeypatch.setattr(swarm_manager, "SecretaryAgent", StubSecretary)
    monkeypatch.setattr(swarm_manager, "ExportManager", lambda: StubExportManager())
    monkeypatch.setattr(
        swarm_manager,
        "create_memory_awareness_for_agent",
        lambda client, agent: f"Awareness for {agent.id}",
    )
    monkeypatch.setattr(swarm_manager, "track_message", lambda *_, **__: None)
    monkeypatch.setattr(swarm_manager, "track_action", lambda *_, **__: None)
    monkeypatch.setattr(swarm_manager, "track_system_event", lambda *_, **__: None)
    monkeypatch.setattr(swarm_manager.time, "sleep", lambda *_: None)

    profiles = [
        {"name": "Alex", "persona": "Planner", "expertise": ["planning"]},
        {"name": "Jordan", "persona": "Designer", "expertise": ["design"]},
    ]

    manager = swarm_manager.SwarmManager(
        client=fake_client,
        agent_profiles=profiles,
        enable_secretary=True,
        secretary_mode="formal",
        conversation_mode="hybrid",
    )

    # Observing secretary should record messages for export stats later.
    manager.secretary.observe_message("Alex", "Initial context")
    return manager


def test_memory_status_summary(configured_swarm_manager):
    summary = configured_swarm_manager.get_memory_status_summary()
    assert summary["total_agents"] == 2
    assert summary["agents_with_high_memory"] == 0
    assert summary["agents_status"][0]["recall_memory"] == 42


def test_memory_commands_with_and_without_secretary(
    configured_swarm_manager, monkeypatch
):
    # With secretary available
    assert configured_swarm_manager._handle_secretary_commands("/memory-status") is True
    assert (
        configured_swarm_manager._handle_secretary_commands("/memory-awareness") is True
    )

    # Without secretary – rebuild manager with secretary disabled for branch coverage.
    import spds.swarm_manager as swarm_manager

    fake_client = FakeLettaClient()
    monkeypatch.setattr(swarm_manager, "SPDSAgent", StubAgent)
    monkeypatch.setattr(
        swarm_manager, "letta_call", lambda op, fn, **kwargs: fn(**kwargs)
    )
    manager = swarm_manager.SwarmManager(
        client=fake_client,
        agent_profiles=[{"name": "Solo", "persona": "Tester", "expertise": ["qa"]}],
        enable_secretary=False,
    )

    # memory-status should still be handled; secretary commands warn but return True
    assert manager._handle_secretary_commands("/memory-status") is True
    assert manager._handle_secretary_commands("/minutes") is True
    assert manager._handle_secretary_commands("/unknown") is False


def test_secretary_commands_execute(configured_swarm_manager, capsys):
    mgr = configured_swarm_manager

    assert mgr._handle_secretary_commands("/minutes") is True
    assert mgr._handle_secretary_commands("/export transcript") is True
    assert mgr._handle_secretary_commands("/formal") is True
    assert mgr.secretary.mode == "formal"
    assert mgr._handle_secretary_commands("/casual") is True
    assert mgr.secretary.mode == "casual"
    assert mgr._handle_secretary_commands("/action-item Follow up with design") is True
    assert mgr.secretary.action_items == ["Follow up with design"]
    assert mgr._handle_secretary_commands("/stats") is True
    assert mgr._handle_secretary_commands("/help") is True

    mgr._show_secretary_help()
    output = capsys.readouterr().out
    assert "/export" in output


def test_export_options_prompt(configured_swarm_manager, monkeypatch):
    mgr = configured_swarm_manager

    # Ensure secretary observes some messages so stats change.
    mgr.secretary.observe_message("Jordan", "Second context")

    # Trigger export flow with a summary request.
    monkeypatch.setenv("PLAYWRIGHT_TEST", "0")
    monkeypatch.setattr("builtins.input", lambda prompt="": "/export summary")
    mgr._offer_export_options()

    # Unknown format should surface error branch.
    monkeypatch.setattr("builtins.input", lambda prompt="": "/export unknown")
    mgr._offer_export_options()


def test_notify_and_memory_awareness(configured_swarm_manager, capsys):
    mgr = configured_swarm_manager
    mgr._notify_secretary_agent_response("Alex", "Agreed")
    assert mgr.secretary.conversation_log[-1] == ("Alex", "Agreed")

    mgr.check_memory_awareness_status(silent=False)
    output = capsys.readouterr().out
    assert "Awareness" in output
