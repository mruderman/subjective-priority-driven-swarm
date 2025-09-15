from io import StringIO
import sys
from types import SimpleNamespace
from unittest.mock import patch, Mock

from spds.swarm_manager import SwarmManager


class DummyAgent:
    def __init__(self, name, prio=10):
        self.name = name
        self.priority_score = prio
        self.motivation_score = 40
    def assess_motivation_and_priority(self, topic):
        pass
    def speak(self, conversation_history=""):
        return SimpleNamespace(messages=[SimpleNamespace(role="assistant", content=[{"type": "text", "text": f"msg {self.name}"}])])


def build_manager_with_agents(mode, agents):
    client = Mock()
    with patch("spds.swarm_manager.SPDSAgent.create_new") as create_new:
        create_new.side_effect = agents
        profiles = [
            {"name": a.name, "persona": "p", "expertise": ["x"], "model": "openai/gpt-4", "embedding": "openai/text-embedding-ada-002"}
            for a in agents
        ]
        return SwarmManager(client=client, agent_profiles=profiles, conversation_mode=mode)


def test_all_speak_mode_two_agents():
    a = DummyAgent("A", prio=20)
    b = DummyAgent("B", prio=10)
    mgr = build_manager_with_agents("all_speak", [a, b])
    captured = StringIO()
    sys.stdout = captured
    mgr._agent_turn("T")
    sys.stdout = sys.__stdout__
    out = captured.getvalue()
    assert "ALL SPEAK MODE" in out
    assert "A: msg A" in out
    assert "B: msg B" in out


def test_hybrid_turn_error_in_response():
    class ErrAgent(DummyAgent):
        def __init__(self, name, prio):
            super().__init__(name, prio)
            self._calls = 0
        def speak(self, conversation_history=""):
            self._calls += 1
            if self._calls == 2:
                raise Exception("boom")
            return super().speak(conversation_history)

    a = DummyAgent("A", prio=20)
    b = ErrAgent("B", prio=10)
    mgr = build_manager_with_agents("hybrid", [a, b])
    captured = StringIO()
    sys.stdout = captured
    mgr._agent_turn("T")
    sys.stdout = sys.__stdout__
    out = captured.getvalue()
    assert "INITIAL RESPONSES" in out
    assert "RESPONSE ROUND" in out
    assert "[Debug: Error in response round - boom]" in out


def test_secretary_commands_without_secretary():
    mgr = build_manager_with_agents("sequential", [DummyAgent("A", 10)])
    captured = StringIO()
    sys.stdout = captured
    handled = mgr._handle_secretary_commands("/minutes")
    sys.stdout = sys.__stdout__
    out = captured.getvalue()
    assert handled is True
    assert "Secretary is not enabled" in out
    assert mgr._handle_secretary_commands("/foo") is False


def test_export_command_without_secretary():
    mgr = build_manager_with_agents("sequential", [DummyAgent("A", 10)])
    captured = StringIO()
    sys.stdout = captured
    mgr._handle_export_command("")
    sys.stdout = sys.__stdout__
    out = captured.getvalue()
    assert "Secretary not available" in out

