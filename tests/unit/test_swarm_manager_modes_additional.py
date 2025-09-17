from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

from spds.swarm_manager import SwarmManager


def _sample_profile(name="A"):
    return {"name": name, "persona": "p", "expertise": ["x"], "model": "openai/gpt-4", "embedding": "openai/text-embedding-ada-002"}


def test_update_agent_memories_retries_on_error(mock_letta_client, capsys):
    # create manager with one agent
    with patch("spds.swarm_manager.SPDSAgent.create_new") as mock_create:
        mock_agent = Mock()
        mock_agent.name = "A"
        mock_agent.agent = SimpleNamespace(id="a1")
        mock_create.return_value = mock_agent

        mgr = SwarmManager(client=mock_letta_client, agent_profiles=[_sample_profile()])

    # simulate create failing first then succeeding
    calls = []

    def fail_once(agent_id, messages=None):
        if not calls:
            calls.append(1)
            raise RuntimeError("500 internal")
        return None

    mock_letta_client.agents.messages.create.side_effect = lambda agent_id, messages=None: fail_once(agent_id, messages)

    mgr._update_agent_memories("hello", speaker="Tester", max_retries=2)

    # should have retried at least once
    assert len(calls) >= 1


def test_agent_turn_dispatches_modes(mock_letta_client):
    # Create three agents and set their priority scores
    with patch("spds.swarm_manager.SPDSAgent.create_new") as mock_create:
        a1 = Mock(); a1.name = "A"; a1.agent = SimpleNamespace(id="a1"); a1.priority_score=5
        a2 = Mock(); a2.name = "B"; a2.agent = SimpleNamespace(id="a2"); a2.priority_score=3
        a3 = Mock(); a3.name = "C"; a3.agent = SimpleNamespace(id="a3"); a3.priority_score=1
        mock_create.side_effect = [a1, a2, a3]

        mgr = SwarmManager(client=mock_letta_client, agent_profiles=[_sample_profile("A"), _sample_profile("B"), _sample_profile("C")], conversation_mode="sequential")

    # Patch assessment and speak to avoid external calls
    for a in mgr.agents:
        a.assess_motivation_and_priority = Mock()
        a.priority_score = 5
        a.speak = Mock(return_value=SimpleNamespace(messages=[SimpleNamespace(content="hi")]))

    # Run an agent turn; should not raise
    mgr._agent_turn("Test topic")

    # Now force pure_priority
    mgr.conversation_mode = "pure_priority"
    mgr._agent_turn("Test topic")

    # And all_speak
    mgr.conversation_mode = "all_speak"
    mgr._agent_turn("Test topic")

    # And hybrid
    mgr.conversation_mode = "hybrid"
    mgr._agent_turn("Test topic")
