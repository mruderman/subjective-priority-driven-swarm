from types import SimpleNamespace
from io import StringIO
import sys
from unittest.mock import patch, Mock

import pytest

from spds.swarm_manager import SwarmManager


class DummyAgent:
    def __init__(self, name):
        self.name = name
        self.priority_score = 10
        self.motivation_score = 40

    def assess_motivation_and_priority(self, topic):
        pass

    def speak(self, conversation_history=""):
        return SimpleNamespace(messages=[SimpleNamespace(role="assistant", content=[{"type": "text", "text": f"Hello from {self.name}"}])])


def test_extract_agent_response_variants():
    client = Mock()
    # Build a manager with one agent via profiles
    with patch("spds.swarm_manager.SPDSAgent.create_new") as create_new:
        da = DummyAgent("A1")
        create_new.return_value = da
        mgr = SwarmManager(client=client, agent_profiles=[{"name": "A1", "persona": "p", "expertise": ["x"], "model": "openai/gpt-4", "embedding": "openai/text-embedding-ada-002"}], conversation_mode="sequential")

    # tool_calls path
    response = SimpleNamespace(messages=[SimpleNamespace(tool_calls=[SimpleNamespace(function=SimpleNamespace(name="send_message", arguments='{"message": "tc"}'))])])
    assert mgr._extract_agent_response(response) == "tc"

    # assistant role list-dict text
    response = SimpleNamespace(messages=[SimpleNamespace(role="assistant", content=[{"type": "text", "text": "hi"}])])
    assert mgr._extract_agent_response(response) == "hi"

    # fallback default
    response = SimpleNamespace(messages=[SimpleNamespace(role="system", content=None)])
    assert "trouble phrasing" in mgr._extract_agent_response(response)


def test_sequential_fairness_prints():
    client = Mock()
    with patch("spds.swarm_manager.SPDSAgent.create_new") as create_new:
        a = DummyAgent("A")
        b = DummyAgent("B")
        a.priority_score = 10
        b.priority_score = 20
        create_new.side_effect = [a, b]
        mgr = SwarmManager(client=client, agent_profiles=[{"name": "A", "persona": "p", "expertise": ["x"], "model": "openai/gpt-4", "embedding": "openai/text-embedding-ada-002"}, {"name": "B", "persona": "p", "expertise": ["x"], "model": "openai/gpt-4", "embedding": "openai/text-embedding-ada-002"}], conversation_mode="sequential")
    mgr.last_speaker = "B"
    captured = StringIO()
    sys.stdout = captured
    mgr._agent_turn("T")
    sys.stdout = sys.__stdout__
    out = captured.getvalue()
    assert "Fairness: Giving A a turn" in out


def test_pure_priority_mode():
    client = Mock()
    with patch("spds.swarm_manager.SPDSAgent.create_new") as create_new:
        a = DummyAgent("A")
        b = DummyAgent("B")
        a.priority_score = 10
        b.priority_score = 20
        create_new.side_effect = [a, b]
        mgr = SwarmManager(client=client, agent_profiles=[{"name": "A", "persona": "p", "expertise": ["x"], "model": "openai/gpt-4", "embedding": "openai/text-embedding-ada-002"}, {"name": "B", "persona": "p", "expertise": ["x"], "model": "openai/gpt-4", "embedding": "openai/text-embedding-ada-002"}], conversation_mode="pure_priority")
    captured = StringIO()
    sys.stdout = captured
    mgr._agent_turn("T")
    sys.stdout = sys.__stdout__
    out = captured.getvalue()
    assert "PURE PRIORITY MODE" in out

