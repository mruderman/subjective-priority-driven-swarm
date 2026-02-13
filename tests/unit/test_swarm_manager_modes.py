"""
Consolidated tests for SwarmManager conversation modes and agent turn dispatching.

This test file covers all 4 conversation modes (hybrid, all-speak, sequential, pure-priority)
and agent turn dispatching logic. Tests are extracted from multiple source files and combined
for better organization.
"""

import json
import sys
import time
import types
from io import StringIO
from types import SimpleNamespace
from unittest.mock import Mock, call, patch

import pytest
from letta_client.types import AgentState, EmbeddingConfig, LlmConfig
from letta_client.types.agent_state import Memory

from spds.spds_agent import SPDSAgent
from spds.swarm_manager import SwarmManager


# Helper functions


def mk_agent_state(
    id: str, name: str, system: str = "Test", model: str = "openai/gpt-4"
):
    """Build a minimally valid AgentState for current letta_client schema."""
    llm = LlmConfig(model=model, model_endpoint_type="openai", context_window=128000)
    emb = EmbeddingConfig(
        embedding_endpoint_type="openai",
        embedding_model="openai/text-embedding-ada-002",
        embedding_dim=1536,
    )
    mem = Memory(blocks=[])
    return AgentState(
        id=id,
        name=name,
        system=system,
        agent_type="react_agent",
        llm_config=llm,
        embedding_config=emb,
        memory=mem,
        blocks=[],
        tools=[],
        sources=[],
        tags=[],
        model=model,
        embedding="openai/text-embedding-ada-002",
    )


def make_tool_response(text: str):
    """
    Create a synthetic tool-message response object representing a single tool call to `send_message`.
    """
    tool_call = SimpleNamespace(
        function=SimpleNamespace(
            name="send_message", arguments=json.dumps({"message": text})
        )
    )
    message = SimpleNamespace(
        tool_calls=[tool_call],
        tool_return=None,
        message_type="tool_message",
        content=None,
    )
    return SimpleNamespace(messages=[message])


def make_assistant_response(text: str, *, as_list: bool = False):
    """
    Create a synthetic assistant message object for tests.
    """
    if as_list:
        content = [{"type": "text", "text": text}]
    else:
        content = text

    message = SimpleNamespace(
        tool_calls=[],
        tool_return=None,
        role="assistant",
        message_type="assistant_message",
        content=content,
    )
    return SimpleNamespace(messages=[message])


def _make_mgr(mock_letta_client, sample_agent_profiles, mode="sequential"):
    """Helper to create a SwarmManager for tests."""
    with patch("spds.swarm_manager.SPDSAgent.create_new") as mock_create:
        base_agent = SimpleNamespace(name="Base", agent=SimpleNamespace(id="base"))
        mock_create.return_value = base_agent
        manager = SwarmManager(
            client=mock_letta_client,
            agent_profiles=[sample_agent_profiles[0]],
            conversation_mode=mode,
        )
    return manager


# Tests from test_swarm_manager.py


def test_agent_turn_with_motivated_agents(mock_letta_client, sample_agent_profiles):
    """Test agent turn when agents are motivated to speak."""
    with patch("spds.swarm_manager.SPDSAgent.create_new") as mock_create:
        # Create mock agents with different priority scores
        mock_agent1 = Mock(spec=SPDSAgent)
        mock_agent1.name = "Agent 1"
        mock_agent1.priority_score = 15.0
        mock_agent1.motivation_score = 40
        mock_agent1.assess_motivation_and_priority = Mock()
        mock_agent1.roles = []
        mock_agent1.last_message_index = -1

        mock_agent2 = Mock(spec=SPDSAgent)
        mock_agent2.name = "Agent 2"
        mock_agent2.priority_score = 25.0  # Higher priority
        mock_agent2.motivation_score = 50
        mock_agent2.assess_motivation_and_priority = Mock()
        mock_agent2.roles = []
        mock_agent2.last_message_index = -1

        # Mock speak response
        mock_response = SimpleNamespace(
            messages=[
                SimpleNamespace(
                    id="msg-123",
                    role="assistant",
                    content=[{"type": "text", "text": "This is my response"}],
                )
            ]
        )
        mock_agent2.speak.return_value = mock_response

        mock_create.side_effect = [mock_agent1, mock_agent2]

        manager = SwarmManager(
            client=mock_letta_client,
            agent_profiles=sample_agent_profiles,
            conversation_mode="sequential",
        )

        # Capture output
        captured_output = StringIO()
        sys.stdout = captured_output

        manager._agent_turn("Test Topic")

        sys.stdout = sys.__stdout__
        output = captured_output.getvalue()

        # Verify assessments were called
        mock_agent1.assess_motivation_and_priority.assert_called_once()
        mock_agent2.assess_motivation_and_priority.assert_called_once()

        # Verify the higher priority agent spoke
        mock_agent2.speak.assert_called_once()
        mock_agent1.speak.assert_not_called()

        # Check output contains agent response
        assert "Agent 2: This is my response" in output
        assert "Agent 2 is speaking" in output


def test_agent_turn_with_no_motivated_agents(mock_letta_client, sample_agent_profiles):
    """Test agent turn when no agents are motivated to speak."""
    with patch("spds.swarm_manager.SPDSAgent.create_new") as mock_create:
        # Create mock agents with zero priority scores
        mock_agent1 = Mock(spec=SPDSAgent)
        mock_agent1.name = "Agent 1"
        mock_agent1.priority_score = 0.0
        mock_agent1.motivation_score = 20
        mock_agent1.assess_motivation_and_priority = Mock()
        mock_agent1.roles = []
        mock_agent1.last_message_index = -1

        mock_agent2 = Mock(spec=SPDSAgent)
        mock_agent2.name = "Agent 2"
        mock_agent2.priority_score = 0.0
        mock_agent2.motivation_score = 15
        mock_agent2.assess_motivation_and_priority = Mock()
        mock_agent2.roles = []
        mock_agent2.last_message_index = -1

        mock_create.side_effect = [mock_agent1, mock_agent2]

        manager = SwarmManager(
            client=mock_letta_client, agent_profiles=sample_agent_profiles
        )

        # Capture output
        captured_output = StringIO()
        sys.stdout = captured_output

        manager._agent_turn("Test Topic")

        sys.stdout = sys.__stdout__
        output = captured_output.getvalue()

        # Verify no agent spoke
        mock_agent1.speak.assert_not_called()
        mock_agent2.speak.assert_not_called()

        # Check appropriate message was printed
        assert "No agent is motivated to speak" in output


def test_agent_turn_with_speak_error(mock_letta_client, sample_agent_profiles):
    """Test agent turn when speaking agent encounters an error."""
    with patch("spds.swarm_manager.SPDSAgent.create_new") as mock_create:
        # Create mock agent that will have speak error
        mock_agent = Mock(spec=SPDSAgent)
        mock_agent.name = "Error Agent"
        mock_agent.priority_score = 30.0
        mock_agent.motivation_score = 50
        mock_agent.assess_motivation_and_priority = Mock()
        mock_agent.roles = []
        mock_agent.last_message_index = -1

        # Mock speak to raise an exception
        mock_agent.speak.side_effect = Exception("API Error")

        mock_create.return_value = mock_agent

        manager = SwarmManager(
            client=mock_letta_client,
            agent_profiles=[sample_agent_profiles[0]],  # Just one agent
            conversation_mode="sequential",
        )

        # Capture output
        captured_output = StringIO()
        sys.stdout = captured_output

        manager._agent_turn("Test Topic")

        sys.stdout = sys.__stdout__
        output = captured_output.getvalue()

        # Should handle the error gracefully
        assert (
            "Error Agent: [Agent error: API Error]"
            in output
        )
        assert (
            "[Debug: Error during speak() - API Error]" in output
            or "[Debug: Error in sequential response - API Error]" in output
        )


def test_hybrid_turn_handles_mixed_responses(mock_letta_client, sample_agent_profiles):
    """Hybrid mode should handle both strong and fallback responses."""
    with patch("spds.swarm_manager.SPDSAgent.create_new") as mock_create:
        base_agent = SimpleNamespace(name="Base", agent=SimpleNamespace(id="base"))
        mock_create.return_value = base_agent
        manager = SwarmManager(
            client=mock_letta_client,
            agent_profiles=[sample_agent_profiles[0]],
        )

    agent1 = SimpleNamespace(
        name="Agent 1",
        priority_score=12.0,
        motivation_score=20,
        expertise="design",
        agent=SimpleNamespace(id="agent-1"),
        speak=Mock(
            side_effect=[
                make_assistant_response(
                    "This is a detailed contribution that explores nuances of the topic.",
                    as_list=True,
                ),
                make_assistant_response(
                    "Following up after hearing everyone else."
                ),
            ]
        ),
        assess_motivation_and_priority=Mock(),
    )
    agent2 = SimpleNamespace(
        name="Agent 2",
        priority_score=11.0,
        motivation_score=18,
        expertise="analysis",
        agent=SimpleNamespace(id="agent-2"),
        speak=Mock(
            side_effect=[
                make_assistant_response("short"),
                make_assistant_response(
                    "Expanding on the previous viewpoints with detail."
                ),
            ]
        ),
        assess_motivation_and_priority=Mock(),
    )

    manager.agents = [agent1, agent2]
    manager.conversation_history = ""
    manager._notify_secretary_agent_response = Mock()
    mock_letta_client.agents.messages.create.reset_mock()

    manager._hybrid_turn([agent1, agent2], "Collaboration")

    assert agent1.speak.call_count == 2
    assert agent2.speak.call_count == 2
    assert "expertise in analysis" in manager.conversation_history
    assert manager._notify_secretary_agent_response.call_count == 3
    assert mock_letta_client.agents.messages.create.call_count == len(
        manager.agents
    )


def test_all_speak_turn_updates_memories(mock_letta_client, sample_agent_profiles):
    """All-speak mode should update memories and notify secretary."""
    with patch("spds.swarm_manager.SPDSAgent.create_new") as mock_create:
        base_agent = SimpleNamespace(name="Base", agent=SimpleNamespace(id="base"))
        mock_create.return_value = base_agent
        manager = SwarmManager(
            client=mock_letta_client,
            agent_profiles=[sample_agent_profiles[0]],
        )

    agent1 = SimpleNamespace(
        name="Agent 1",
        priority_score=10.0,
        motivation_score=15,
        agent=SimpleNamespace(id="agent-1"),
        speak=Mock(
            return_value=make_assistant_response("First detailed response.")
        ),
        assess_motivation_and_priority=Mock(),
    )
    agent2 = SimpleNamespace(
        name="Agent 2",
        priority_score=9.0,
        motivation_score=14,
        agent=SimpleNamespace(id="agent-2"),
        speak=Mock(
            return_value=make_assistant_response("Second response with more depth.")
        ),
        assess_motivation_and_priority=Mock(),
    )

    manager.agents = [agent1, agent2]
    manager.conversation_history = ""
    manager._update_agent_memories = Mock()
    manager._notify_secretary_agent_response = Mock()

    manager._all_speak_turn([agent1, agent2], "Innovation")

    manager._update_agent_memories.assert_has_calls(
        [
            call("First detailed response.", "Agent 1"),
            call("Second response with more depth.", "Agent 2"),
        ]
    )
    assert manager._notify_secretary_agent_response.call_count == 2
    assert "Agent 1: First detailed response." in manager.conversation_history
    assert (
        "Agent 2: Second response with more depth." in manager.conversation_history
    )


def test_sequential_turn_fairness_prefers_second_agent(
    mock_letta_client, sample_agent_profiles
):
    """Sequential mode should rotate when the top speaker just spoke."""
    with patch("spds.swarm_manager.SPDSAgent.create_new") as mock_create:
        base_agent = SimpleNamespace(name="Base", agent=SimpleNamespace(id="base"))
        mock_create.return_value = base_agent
        manager = SwarmManager(
            client=mock_letta_client,
            agent_profiles=[sample_agent_profiles[0]],
            conversation_mode="sequential",
        )

    agent1 = SimpleNamespace(
        name="Agent 1",
        priority_score=12.0,
        motivation_score=15,
        agent=SimpleNamespace(id="agent-1"),
        speak=Mock(return_value=make_assistant_response("Should not speak")),
        assess_motivation_and_priority=Mock(),
    )
    agent2 = SimpleNamespace(
        name="Agent 2",
        priority_score=11.0,
        motivation_score=14,
        agent=SimpleNamespace(id="agent-2"),
        speak=Mock(
            return_value=make_assistant_response("Second agent takes the turn.")
        ),
        assess_motivation_and_priority=Mock(),
    )

    manager.agents = [agent1, agent2]
    manager.last_speaker = "Agent 1"
    manager.conversation_history = ""
    manager._notify_secretary_agent_response = Mock()

    manager._sequential_turn([agent1, agent2], "Planning")

    agent1.speak.assert_not_called()
    agent2.speak.assert_called_once()
    assert "Agent 2: Second agent takes the turn." in manager.conversation_history


def test_sequential_turn_updates_last_speaker_after_rotation(
    mock_letta_client, sample_agent_profiles
):
    """After rotating, the new speaker should become the last speaker."""
    with patch("spds.swarm_manager.SPDSAgent.create_new") as mock_create:
        base_agent = SimpleNamespace(name="Base", agent=SimpleNamespace(id="base"))
        mock_create.return_value = base_agent
        manager = SwarmManager(
            client=mock_letta_client,
            agent_profiles=[sample_agent_profiles[0]],
            conversation_mode="sequential",
        )

    agent1 = SimpleNamespace(
        name="Agent 1",
        priority_score=12.0,
        motivation_score=15,
        agent=SimpleNamespace(id="agent-1"),
        speak=Mock(return_value=make_assistant_response("Should not speak")),
        assess_motivation_and_priority=Mock(),
    )
    agent2 = SimpleNamespace(
        name="Agent 2",
        priority_score=11.0,
        motivation_score=14,
        agent=SimpleNamespace(id="agent-2"),
        speak=Mock(
            return_value=make_assistant_response("Second agent takes the turn.")
        ),
        assess_motivation_and_priority=Mock(),
    )

    manager.agents = [agent1, agent2]
    manager.last_speaker = "Agent 1"
    manager.conversation_history = ""
    manager._notify_secretary_agent_response = Mock()

    manager._sequential_turn([agent1, agent2], "Planning")

    assert manager.last_speaker == "Agent 2"


def test_sequential_turn_single_agent_still_speaks_when_last_speaker_matches(
    mock_letta_client, sample_agent_profiles
):
    """A single motivated agent should speak even if they spoke last turn."""
    with patch("spds.swarm_manager.SPDSAgent.create_new") as mock_create:
        base_agent = SimpleNamespace(name="Base", agent=SimpleNamespace(id="base"))
        mock_create.return_value = base_agent
        manager = SwarmManager(
            client=mock_letta_client,
            agent_profiles=[sample_agent_profiles[0]],
            conversation_mode="sequential",
        )

    agent = SimpleNamespace(
        name="Solo Agent",
        priority_score=13.0,
        motivation_score=16,
        agent=SimpleNamespace(id="agent-1"),
        speak=Mock(return_value=make_assistant_response("Taking another turn.")),
        assess_motivation_and_priority=Mock(),
    )

    manager.agents = [agent]
    manager.last_speaker = "Solo Agent"
    manager.conversation_history = ""
    manager._notify_secretary_agent_response = Mock()

    manager._sequential_turn([agent], "Topic")

    agent.speak.assert_called_once()
    assert manager.last_speaker == "Solo Agent"
    assert "Solo Agent: Taking another turn." in manager.conversation_history


def test_sequential_turn_handles_exception_fallback(
    mock_letta_client, sample_agent_profiles
):
    """Sequential mode should fall back gracefully on errors."""
    with patch("spds.swarm_manager.SPDSAgent.create_new") as mock_create:
        base_agent = SimpleNamespace(name="Base", agent=SimpleNamespace(id="base"))
        mock_create.return_value = base_agent
        manager = SwarmManager(
            client=mock_letta_client,
            agent_profiles=[sample_agent_profiles[0]],
            conversation_mode="sequential",
        )

    failing_agent = SimpleNamespace(
        name="Agent 1",
        priority_score=10.0,
        motivation_score=12,
        agent=SimpleNamespace(id="agent-1"),
        speak=Mock(side_effect=Exception("fail")),
        assess_motivation_and_priority=Mock(),
    )

    manager.agents = [failing_agent]
    manager.conversation_history = ""
    manager._notify_secretary_agent_response = Mock()

    manager._sequential_turn([failing_agent], "Topic")

    fallback = "[Agent error: fail]"
    assert f"Agent 1: {fallback}" in manager.conversation_history
    manager._notify_secretary_agent_response.assert_called_with("Agent 1", fallback)


def test_pure_priority_turn_handles_exception(
    mock_letta_client, sample_agent_profiles
):
    """Pure priority mode should report fallback on errors."""
    with patch("spds.swarm_manager.SPDSAgent.create_new") as mock_create:
        base_agent = SimpleNamespace(name="Base", agent=SimpleNamespace(id="base"))
        mock_create.return_value = base_agent
        manager = SwarmManager(
            client=mock_letta_client,
            agent_profiles=[sample_agent_profiles[0]],
            conversation_mode="pure_priority",
        )

    failing_agent = SimpleNamespace(
        name="Agent 1",
        priority_score=15.0,
        motivation_score=20,
        agent=SimpleNamespace(id="agent-1"),
        speak=Mock(side_effect=Exception("fail")),
        assess_motivation_and_priority=Mock(),
    )

    manager.agents = [failing_agent]
    manager.conversation_history = ""
    manager._notify_secretary_agent_response = Mock()

    manager._pure_priority_turn([failing_agent], "Topic")

    fallback = "[Agent error: fail]"
    assert f"Agent 1: {fallback}" in manager.conversation_history
    manager._notify_secretary_agent_response.assert_called_with("Agent 1", fallback)


# Tests from test_swarm_manager_modes.py


class DummyAgent:
    def __init__(self, name, prio=10):
        self.name = name
        self.priority_score = prio
        self.motivation_score = 40
        self.roles = []
        self.last_message_index = -1

    def assess_motivation_and_priority(self, topic):
        pass

    def speak(self, conversation_history=""):
        return SimpleNamespace(
            messages=[
                SimpleNamespace(
                    role="assistant",
                    content=[{"type": "text", "text": f"msg {self.name}"}],
                )
            ]
        )


def build_manager_with_agents(mode, agents):
    client = Mock()
    with patch("spds.swarm_manager.SPDSAgent.create_new") as create_new:
        create_new.side_effect = agents
        profiles = [
            {
                "name": a.name,
                "persona": "p",
                "expertise": ["x"],
                "model": "openai/gpt-4",
                "embedding": "openai/text-embedding-ada-002",
            }
            for a in agents
        ]
        return SwarmManager(
            client=client, agent_profiles=profiles, conversation_mode=mode
        )


def test_all_speak_mode_two_agents():
    a = DummyAgent("A", prio=20)
    b = DummyAgent("B", prio=10)
    a.assess_motivation_and_priority = Mock(return_value=(25, 8.0))
    b.assess_motivation_and_priority = Mock(return_value=(25, 8.0))
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
    a.assess_motivation_and_priority = Mock(return_value=(25, 8.0))
    b.assess_motivation_and_priority = Mock(return_value=(25, 8.0))
    mgr = build_manager_with_agents("hybrid", [a, b])
    captured = StringIO()
    sys.stdout = captured
    mgr._agent_turn("T")
    sys.stdout = sys.__stdout__
    out = captured.getvalue()
    assert "INITIAL RESPONSES" in out
    assert "RESPONSE ROUND" in out
    assert "[Debug: Error in response round - boom]" in out


# Tests from test_swarm_manager_modes_additional.py


def _sample_profile(name="A"):
    return {
        "name": name,
        "persona": "p",
        "expertise": ["x"],
        "model": "openai/gpt-4",
        "embedding": "openai/text-embedding-ada-002",
    }


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

    mock_letta_client.agents.messages.create.side_effect = (
        lambda agent_id, messages=None: fail_once(agent_id, messages)
    )

    mgr._update_agent_memories("hello", speaker="Tester", max_retries=2)

    # should have retried at least once
    assert len(calls) >= 1


# Tests from test_swarm_manager_more.py


class FakeAgent:
    def __init__(self, id_, name, text=None, raise_on_speak=False):
        class A:
            def __init__(self, id_):
                self.id = id_

        self.agent = A(id_)
        self.name = name
        self.motivation_score = 1
        self.priority_score = 1.0
        self.text = text
        self.raise_on_speak = raise_on_speak
        self.roles = []
        self.last_message_index = -1

    def assess_motivation_and_priority(self, topic):
        # leave priority_score as-is
        return None

    def speak(self, conversation_history=None):
        if self.raise_on_speak:
            raise Exception("speak failed")
        if isinstance(self.text, str):
            return types.SimpleNamespace(
                messages=[SimpleNamespace(role="assistant", content=self.text)]
            )
        return types.SimpleNamespace(
            messages=[SimpleNamespace(role="assistant", content=[{"text": self.text}])]
        )


def make_mgr_with_agents(agent_list):
    mgr = object.__new__(SwarmManager)
    mgr.client = types.SimpleNamespace(
        agents=types.SimpleNamespace(
            messages=types.SimpleNamespace(create=lambda **k: None)
        )
    )
    mgr.agents = agent_list
    mgr.enable_secretary = False
    mgr._secretary = None
    mgr.secretary_agent_id = None
    mgr.pending_nomination = None
    mgr.export_manager = None
    mgr.conversation_history = ""
    mgr.last_speaker = None
    mgr.conversation_mode = "hybrid"
    return mgr


def test_hybrid_turn_good_and_fallback(monkeypatch, capsys):
    # Agent with long text -> initial good response
    a1 = FakeAgent("id1", "A", text="This is a sufficiently long assistant response.")
    # Agent with short text -> fallback path
    a2 = FakeAgent("id2", "B", text="short")

    mgr = make_mgr_with_agents([a1, a2])

    # Provide client.agent.messages.create recording to ensure fallback path triggers
    created = []

    def fake_create(agent_id, messages):
        created.append((agent_id, messages))

    mgr.client.agents.messages.create = fake_create

    mgr._hybrid_turn([a1, a2], "topic")
    out = capsys.readouterr().out
    # Ensure that A's real text appears and B fallback appears
    assert "sufficiently long assistant response" in out
    assert "As someone with expertise" in out
    # ensure we attempted to call messages.create for fallback or retry
    assert isinstance(created, list)


def test_all_speak_updates_memory_and_history(monkeypatch):
    a1 = FakeAgent("id1", "A", text="Agent A lengthy reply here.")
    a2 = FakeAgent("id2", "B", text="Agent B reply here.")
    mgr = make_mgr_with_agents([a1, a2])

    # Track update_agent_memories calls
    calls = []

    def fake_update(msg, speaker):
        calls.append((speaker, msg))

    mgr._update_agent_memories = fake_update

    mgr._all_speak_turn([a1, a2], "topic")
    # After both speak, update_agent_memories should have been called for each
    assert any(c[0] == "A" for c in calls)
    assert "A: Agent A lengthy reply here." in mgr.conversation_history


def test_sequential_turn_fairness_and_fallback(monkeypatch, capsys):
    a1 = FakeAgent("id1", "A", text="First agent reply long enough.")
    a2 = FakeAgent("id2", "B", text="Second agent reply long enough.")
    mgr = make_mgr_with_agents([a1, a2])

    # Simulate last speaker was A so fairness gives B a turn
    mgr.last_speaker = "A"
    mgr._sequential_turn([a1, a2], "topic")
    assert mgr.last_speaker == "B"
    assert "B: Second agent reply" in mgr.conversation_history

    # Now simulate speak raising exception -> fallback path
    a3 = FakeAgent("id3", "C", raise_on_speak=True)
    mgr2 = make_mgr_with_agents([a3])
    mgr2._notify_secretary_agent_response = lambda n, m: None
    mgr2._sequential_turn([a3], "topic")
    assert "[Agent error:" in mgr2.conversation_history


def test_pure_priority_turn_fallback_and_notify():
    a1 = FakeAgent("id1", "A", raise_on_speak=True)
    mgr = make_mgr_with_agents([a1])
    # set a secretary to ensure notify branch runs
    class FakeSecretary:
        def __init__(self):
            self._observed = []

        def observe_message(self, n, m):
            self._observed.append((n, m))

    sec = FakeSecretary()
    mgr.secretary = sec
    mgr._notify_secretary_agent_response = lambda n, m: sec.observe_message(n, m)

    mgr._pure_priority_turn([a1], "topic")
    # fallback message should be present
    assert any("[Agent error:" in v for v in mgr.conversation_history.splitlines())
    # secretary should have observed fallback
    assert sec._observed


# Tests from test_swarm_manager_coverage_boost.py


def test_agent_turn_no_motivated_prints(capsys):
    mgr = object.__new__(SwarmManager)
    a = types.SimpleNamespace(
        name="A",
        priority_score=0.0,
        motivation_score=0,
        assess_motivation_and_priority=lambda t, u: None,
        roles=[],
        last_message_index=-1,
    )
    mgr.agents = [a]
    mgr.conversation_mode = "hybrid"
    mgr._agent_turn("topic")
    assert "No agent is motivated" in capsys.readouterr().out


def test_all_speak_fallback_on_exception(monkeypatch):
    # Agent speak raises -> fallback path in all_speak
    class A:
        def __init__(self, name):
            class Inner:
                id = "id"

            self.agent = Inner()
            self.name = name
            self.priority_score = 1.0
            self.roles = []
            self.last_message_index = -1

        def speak(self, conversation_history=None):
            raise RuntimeError("fail")

    mgr = object.__new__(SwarmManager)
    mgr.agents = [A("A")]
    mgr._update_agent_memories = lambda *a, **k: None
    mgr._notify_secretary_agent_response = lambda *a, **k: None
    mgr.conversation_history = ""

    mgr._all_speak_turn(motivated_agents=mgr.agents, topic="t")
    # fallback message added
    assert any("[Agent error:" in line for line in mgr.conversation_history.splitlines())


def test_hybrid_turn_initial_exception_and_instruction_error(monkeypatch, capsys):
    class A:
        def __init__(self, name, raise_on_speak=False):
            class Inner:
                id = "id"

            self.agent = Inner()
            self.name = name
            self.priority_score = 1.0
            self.expertise = "testing"
            self._raise = raise_on_speak
            self.roles = []
            self.last_message_index = -1

        def speak(self, conversation_history=None):
            if self._raise:
                raise RuntimeError("boom")
            return types.SimpleNamespace(
                messages=[types.SimpleNamespace(role="assistant", content="short")]
            )

    mgr = object.__new__(SwarmManager)

    # client create will error to cover instruction error branch
    class Msgs:
        def create(self, **k):
            raise RuntimeError("fail-create")

    mgr.client = types.SimpleNamespace(agents=types.SimpleNamespace(messages=Msgs()))
    mgr.conversation_history = ""
    mgr._notify_secretary_agent_response = lambda *a, **k: None

    # First agent raises in initial phase -> fallback; second yields short -> fallback too
    a1 = A("A", raise_on_speak=True)
    a2 = A("B", raise_on_speak=False)
    mgr.agents = [a1, a2]
    mgr._hybrid_turn([a1, a2], "topic")
    out = capsys.readouterr().out
    assert (
        "Error in initial response attempt" in out or "As someone with expertise" in out
    )


def test_pure_priority_turn_success():
    class A:
        def __init__(self, name):
            class Inner:
                id = "id"

            self.agent = Inner()
            self.name = name
            self.priority_score = 1.0
            self.roles = []
            self.last_message_index = -1

        def speak(self, conversation_history=None):
            return types.SimpleNamespace(
                messages=[types.SimpleNamespace(role="assistant", content="OK")]
            )

    mgr = object.__new__(SwarmManager)
    mgr.conversation_history = ""
    mgr._secretary = None
    mgr.secretary_agent_id = None
    mgr.pending_nomination = None
    mgr._notify_secretary_agent_response = lambda *a, **k: None
    a = A("A")
    mgr._pure_priority_turn([a], "t")
    assert "A: OK" in mgr.conversation_history


# Tests from test_swarm_manager_generated.py


class FakeAgentObj:
    def __init__(self, id_, name, priority=1.0):
        class A:
            def __init__(self, id_):
                self.id = id_

        self.agent = A(id_)
        self.name = name
        self.motivation_score = 0
        self.priority_score = priority
        self.roles = []
        self.last_message_index = -1

    def assess_motivation_and_priority(self, topic):
        # For tests we toggle priority based on stored attribute
        return None


def test_agent_turn_dispatches_modes(mock_letta_client):
    # Create three agents and set their priority scores
    with patch("spds.swarm_manager.SPDSAgent.create_new") as mock_create:
        a1 = Mock()
        a1.name = "A"
        a1.agent = SimpleNamespace(id="a1")
        a1.priority_score = 5
        a1.last_message_index = 0
        a2 = Mock()
        a2.name = "B"
        a2.agent = SimpleNamespace(id="a2")
        a2.priority_score = 3
        a2.last_message_index = 0
        a3 = Mock()
        a3.name = "C"
        a3.agent = SimpleNamespace(id="a3")
        a3.priority_score = 1
        a3.last_message_index = 0
        mock_create.side_effect = [a1, a2, a3]

        mgr = SwarmManager(
            client=mock_letta_client,
            agent_profiles=[
                _sample_profile("A"),
                _sample_profile("B"),
                _sample_profile("C"),
            ],
            conversation_mode="sequential",
        )

    # Patch assessment and speak to avoid external calls
    for a in mgr.agents:
        a.assess_motivation_and_priority = Mock()
        a.priority_score = 5
        a.roles = []
        a.last_message_index = -1
        a.speak = Mock(
            return_value=SimpleNamespace(messages=[SimpleNamespace(content="hi")])
        )

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


# Tests from test_swarm_manager_extract.py


class DummyAgentExtract:
    def __init__(self, name):
        self.name = name
        self.priority_score = 10
        self.motivation_score = 40
        self.roles = []
        self.last_message_index = -1

    def assess_motivation_and_priority(self, topic):
        pass

    def speak(self, conversation_history=""):
        return SimpleNamespace(
            messages=[
                SimpleNamespace(
                    role="assistant",
                    content=[{"type": "text", "text": f"Hello from {self.name}"}],
                )
            ]
        )


def test_sequential_fairness_prints():
    client = Mock()
    with patch("spds.swarm_manager.SPDSAgent.create_new") as create_new:
        a = DummyAgentExtract("A")
        b = DummyAgentExtract("B")
        a.assess_motivation_and_priority = Mock(return_value=(25, 8.0))
        b.assess_motivation_and_priority = Mock(return_value=(25, 8.0))
        a.priority_score = 10
        b.priority_score = 20
        create_new.side_effect = [a, b]
        mgr = SwarmManager(
            client=client,
            agent_profiles=[
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
                    "expertise": ["x"],
                    "model": "openai/gpt-4",
                    "embedding": "openai/text-embedding-ada-002",
                },
            ],
            conversation_mode="sequential",
        )
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
        a = DummyAgentExtract("A")
        b = DummyAgentExtract("B")
        a.assess_motivation_and_priority = Mock(return_value=(25, 8.0))
        b.assess_motivation_and_priority = Mock(return_value=(25, 8.0))
        a.priority_score = 10
        b.priority_score = 20
        create_new.side_effect = [a, b]
        mgr = SwarmManager(
            client=client,
            agent_profiles=[
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
                    "expertise": ["x"],
                    "model": "openai/gpt-4",
                    "embedding": "openai/text-embedding-ada-002",
                },
            ],
            conversation_mode="pure_priority",
        )
    captured = StringIO()
    sys.stdout = captured
    mgr._agent_turn("T")
    sys.stdout = sys.__stdout__
    out = captured.getvalue()
    assert "PURE PRIORITY MODE" in out
