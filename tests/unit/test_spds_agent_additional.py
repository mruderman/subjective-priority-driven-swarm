import re
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

from spds.spds_agent import SPDSAgent
from letta_client.types import AgentState


def mk_agent_state(name="Alice", system=None):
    if system is None:
        system = "You are Alice. Your persona is: Thoughtful helper. Your expertise is in: testing, debugging."
    return SimpleNamespace(id="a1", name=name, system=system, tools=[])


def test_parse_system_prompt_extracts_persona_and_expertise():
    state = mk_agent_state(system="You are Test. Your persona is: Researcher. Your expertise is in: ml, ai.")
    agent = SPDSAgent(state, client=Mock())
    assert "Researcher" in agent.persona
    assert any("ml" in e for e in agent.expertise)


def test_parse_assessment_response_handles_partial_and_missing_scores():
    state = mk_agent_state()
    agent = SPDSAgent(state, client=Mock())

    # Provide only some labeled scores
    text = "IMPORTANCE_TO_SELF: 8\nUNIQUE_PERSPECTIVE: 6"
    scores = agent._parse_assessment_response(text)
    assert scores["importance_to_self"] == 8
    assert scores["unique_perspective"] == 6
    # Missing keys should be filled with defaults
    assert scores["perceived_gap"] == 5


def test_assess_motivation_and_priority_uses_last_assessment(monkeypatch):
    state = mk_agent_state()
    client = Mock()
    agent = SPDSAgent(state, client=client)

    # Inject a last_assessment object with known fields
    Dummy = SimpleNamespace
    agent.last_assessment = Dummy(importance_to_self=8, perceived_gap=7, unique_perspective=6, emotional_investment=5, expertise_relevance=4, urgency=9, importance_to_group=8)

    # Monkeypatch _get_full_assessment so it doesn't call external
    monkeypatch.setattr(agent, "_get_full_assessment", lambda *a, **k: None)

    # Call assess
    agent.assess_motivation_and_priority(topic="T")

    assert agent.motivation_score == 8 + 7 + 6 + 5 + 4
    if agent.motivation_score >= 10:
        assert agent.priority_score >= 0


def test_speak_fallback_on_no_tool_calls(monkeypatch):
    state = mk_agent_state()
    # simulate agent with tools
    state.tools = [1]
    client = Mock()

    # configure client to raise the specific string error on first call then return a response
    def raise_no_tools(*a, **k):
        raise RuntimeError("No tool calls found")

    client.agents.messages.create.side_effect = [RuntimeError("No tool calls found"), SimpleNamespace(messages=[SimpleNamespace(content="ok")])]

    agent = SPDSAgent(state, client=client)
    # Should not raise
    res = agent.speak(conversation_history="", mode="initial", topic="X")
    assert res is not None
