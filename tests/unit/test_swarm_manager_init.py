"""
Consolidated unit tests for SwarmManager initialization, agent loading, role management,
configuration, chat flow, and reset operations.

This module combines tests from:
- test_swarm_manager.py
- test_swarm_manager_core.py
- test_swarm_manager_coverage_boost.py
- test_swarm_manager_generated.py
- test_swarm_manager_uncovered.py
"""

import json
import sys
from io import StringIO
from types import SimpleNamespace
from unittest.mock import MagicMock, Mock, call, patch

import httpx
import pytest
from letta_client.types import (
    AgentState,
    EmbeddingConfig,
    LlmConfig,
)
from letta_client.types.agents import LettaResponse, Message
from letta_client.types.agent_state import Memory
from letta_client import NotFoundError

from spds.spds_agent import SPDSAgent
from spds.swarm_manager import SwarmManager


# ============================================================================
# Helper Functions
# ============================================================================


def _make_not_found_error(message="Not found"):
    resp = httpx.Response(404, request=httpx.Request("GET", "http://test"))
    return NotFoundError(message, response=resp, body={"detail": message})


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


def _make_mgr(mock_letta_client, sample_agent_profiles):
    """Helper function to create a SwarmManager instance for testing."""
    with patch("spds.swarm_manager.SPDSAgent.create_new") as mock_create:
        mock_agent = Mock(spec=SPDSAgent)
        mock_agent.name = "Test Agent"
        mock_create.return_value = mock_agent

        manager = SwarmManager(
            client=mock_letta_client,
            agent_profiles=[sample_agent_profiles[0]],
            conversation_mode="sequential",
        )
    return manager


# ============================================================================
# Tests from test_swarm_manager.py
# ============================================================================


def test_init_with_agent_profiles(mock_letta_client, sample_agent_profiles):
    """Test SwarmManager initialization with agent profiles."""
    with patch("spds.swarm_manager.SPDSAgent.create_new") as mock_create:
        # Mock created agents
        mock_agent1 = Mock(spec=SPDSAgent)
        mock_agent1.name = "Test Agent 1"
        mock_agent2 = Mock(spec=SPDSAgent)
        mock_agent2.name = "Test Agent 2"
        mock_create.side_effect = [mock_agent1, mock_agent2]

        manager = SwarmManager(
            client=mock_letta_client,
            agent_profiles=sample_agent_profiles,
            conversation_mode="sequential",
        )

        assert len(manager.agents) == 2
        assert manager.agents[0] == mock_agent1
        assert manager.agents[1] == mock_agent2
        assert manager.conversation_history == ""

        # Verify agents were created with correct parameters
        expected_calls = [
            call(
                name="Test Agent 1",
                persona="A test agent for validation",
                expertise=["testing", "validation"],
                client=mock_letta_client,
                model="openai/gpt-4",
                embedding="openai/text-embedding-ada-002",
            ),
            call(
                name="Test Agent 2",
                persona="Another test agent",
                expertise=["analysis", "reporting"],
                client=mock_letta_client,
                model="anthropic/claude-3-5-sonnet-20241022",
                embedding="openai/text-embedding-ada-002",
            ),
        ]
        mock_create.assert_has_calls(expected_calls)


def test_init_with_agent_ids(mock_letta_client):
    """Test SwarmManager initialization with agent IDs."""
    agent_ids = ["ag-123", "ag-456"]

    # Mock agent states
    mock_agent_state1 = mk_agent_state(
        id="ag-123", name="Agent 1", system="Test", model="openai/gpt-4"
    )
    mock_agent_state2 = mk_agent_state(
        id="ag-456", name="Agent 2", system="Test", model="openai/gpt-4"
    )

    mock_letta_client.agents.retrieve.side_effect = [
        mock_agent_state1,
        mock_agent_state2,
    ]

    with patch("spds.swarm_manager.SPDSAgent") as mock_spds_agent:
        mock_agent1 = Mock()
        mock_agent2 = Mock()
        mock_spds_agent.side_effect = [mock_agent1, mock_agent2]

        manager = SwarmManager(client=mock_letta_client, agent_ids=agent_ids)

        assert len(manager.agents) == 2
        mock_letta_client.agents.retrieve.assert_has_calls(
            [call(agent_id="ag-123"), call(agent_id="ag-456")]
        )


def test_init_with_agent_names(mock_letta_client):
    """Test SwarmManager initialization with agent names."""
    agent_names = ["Agent One", "Agent Two"]

    # Mock agent states
    mock_agent_state1 = mk_agent_state(
        id="ag-123", name="Agent One", system="Test", model="openai/gpt-4"
    )
    mock_agent_state2 = mk_agent_state(
        id="ag-456", name="Agent Two", system="Test", model="openai/gpt-4"
    )

    mock_letta_client.agents.list.side_effect = [
        [mock_agent_state1],  # First call returns Agent One
        [mock_agent_state2],  # Second call returns Agent Two
    ]

    with patch("spds.swarm_manager.SPDSAgent") as mock_spds_agent:
        mock_agent1 = Mock()
        mock_agent2 = Mock()
        mock_spds_agent.side_effect = [mock_agent1, mock_agent2]

        manager = SwarmManager(client=mock_letta_client, agent_names=agent_names)

        assert len(manager.agents) == 2
        mock_letta_client.agents.list.assert_has_calls(
            [call(name="Agent One", limit=1), call(name="Agent Two", limit=1)]
        )


def test_init_with_no_agents_raises_error(mock_letta_client):
    """Test that initializing with no agents raises ValueError."""
    with pytest.raises(
        ValueError, match="Swarm manager initialized with no agents"
    ):
        SwarmManager(client=mock_letta_client)


def test_load_agents_by_id_with_missing_agent(mock_letta_client):
    """Test loading agents by ID when some agents are not found."""
    agent_ids = ["ag-123", "ag-missing", "ag-456"]

    # Mock retrieval with one NotFoundError
    mock_agent_state1 = mk_agent_state(
        id="ag-123", name="Agent 1", system="Test", model="openai/gpt-4"
    )
    mock_agent_state3 = mk_agent_state(
        id="ag-456", name="Agent 3", system="Test", model="openai/gpt-4"
    )

    def mock_retrieve(agent_id):
        if agent_id == "ag-missing":
            raise _make_not_found_error("Agent not found")
        elif agent_id == "ag-123":
            return mock_agent_state1
        elif agent_id == "ag-456":
            return mock_agent_state3

    mock_letta_client.agents.retrieve.side_effect = mock_retrieve

    with patch("spds.swarm_manager.SPDSAgent") as mock_spds_agent:
        mock_agent1 = Mock()
        mock_agent3 = Mock()
        mock_spds_agent.side_effect = [mock_agent1, mock_agent3]

        # Capture stdout to check warning message
        captured_output = StringIO()
        sys.stdout = captured_output

        manager = SwarmManager(client=mock_letta_client, agent_ids=agent_ids)

        sys.stdout = sys.__stdout__

        # Should only have 2 agents (missing one skipped)
        assert len(manager.agents) == 2

        # Check warning was printed
        output = captured_output.getvalue()
        assert "WARNING: Agent with ID 'ag-missing' not found" in output


def test_load_agents_by_name_with_missing_agent(mock_letta_client):
    """Test loading agents by name when some agents are not found."""
    agent_names = ["Agent One", "Missing Agent", "Agent Three"]

    # Mock agent states
    mock_agent_state1 = mk_agent_state(
        id="ag-123", name="Agent One", system="Test", model="openai/gpt-4"
    )
    mock_agent_state3 = mk_agent_state(
        id="ag-456", name="Agent Three", system="Test", model="openai/gpt-4"
    )

    def mock_list(name, limit):
        if name == "Missing Agent":
            return []  # Empty list means not found
        elif name == "Agent One":
            return [mock_agent_state1]
        elif name == "Agent Three":
            return [mock_agent_state3]

    mock_letta_client.agents.list.side_effect = mock_list

    with patch("spds.swarm_manager.SPDSAgent") as mock_spds_agent:
        mock_agent1 = Mock()
        mock_agent3 = Mock()
        mock_spds_agent.side_effect = [mock_agent1, mock_agent3]

        # Capture stdout to check warning message
        captured_output = StringIO()
        sys.stdout = captured_output

        manager = SwarmManager(client=mock_letta_client, agent_names=agent_names)

        sys.stdout = sys.__stdout__

        # Should only have 2 agents (missing one skipped)
        assert len(manager.agents) == 2

        # Check warning was printed
        output = captured_output.getvalue()
        assert "WARNING: Agent with name 'Missing Agent' not found" in output


def test_create_agents_from_profiles_with_model_config(mock_letta_client):
    """Test creating agents from profiles with model configuration."""
    profiles = [
        {
            "name": "GPT Agent",
            "persona": "An OpenAI agent",
            "expertise": ["analysis"],
            "model": "openai/gpt-4",
            "embedding": "openai/text-embedding-ada-002",
        },
        {
            "name": "Claude Agent",
            "persona": "An Anthropic agent",
            "expertise": ["reasoning"],
            "model": "anthropic/claude-3-5-sonnet-20241022",
            "embedding": "openai/text-embedding-ada-002",
        },
    ]

    with patch("spds.swarm_manager.SPDSAgent.create_new") as mock_create:
        mock_agent1 = Mock()
        mock_agent2 = Mock()
        mock_create.side_effect = [mock_agent1, mock_agent2]

        manager = SwarmManager(client=mock_letta_client, agent_profiles=profiles)

        # Verify agents were created with model-specific parameters
        expected_calls = [
            call(
                name="GPT Agent",
                persona="An OpenAI agent",
                expertise=["analysis"],
                client=mock_letta_client,
                model="openai/gpt-4",
                embedding="openai/text-embedding-ada-002",
            ),
            call(
                name="Claude Agent",
                persona="An Anthropic agent",
                expertise=["reasoning"],
                client=mock_letta_client,
                model="anthropic/claude-3-5-sonnet-20241022",
                embedding="openai/text-embedding-ada-002",
            ),
        ]
        mock_create.assert_has_calls(expected_calls)


@patch("builtins.input")
def test_start_chat_basic_flow(
    mock_input, mock_letta_client, sample_agent_profiles
):
    """Test basic chat flow with user input."""
    # Mock user inputs: topic, one message, then quit
    mock_input.side_effect = [
        "Testing Discussion",
        "Let's talk about testing",
        "quit",
    ]

    with patch("spds.swarm_manager.SPDSAgent.create_new") as mock_create:
        mock_agent = Mock(spec=SPDSAgent)
        mock_agent.name = "Test Agent"
        mock_agent.priority_score = 30.0
        mock_agent.motivation_score = 50
        mock_agent.assess_motivation_and_priority = Mock()

        # Mock successful speak
        mock_response = SimpleNamespace(
            messages=[
                SimpleNamespace(
                    id="msg-123",
                    role="assistant",
                    content=[
                        {"type": "text", "text": "Great point about testing!"}
                    ],
                )
            ]
        )
        mock_agent.speak.return_value = mock_response

        mock_create.return_value = mock_agent

        manager = SwarmManager(
            client=mock_letta_client, agent_profiles=[sample_agent_profiles[0]]
        )

        # Capture output
        captured_output = StringIO()
        sys.stdout = captured_output

        manager.start_chat()

        sys.stdout = sys.__stdout__
        output = captured_output.getvalue()

        # Verify conversation flow
        assert "Swarm chat started" in output
        assert "Test Agent: Great point about testing!" in output
        assert "Exiting chat" in output


@patch("builtins.input")
def test_start_chat_eof_handling(
    mock_input, mock_letta_client, sample_agent_profiles
):
    """Test chat handling of EOF (Ctrl+D)."""
    # Mock EOFError on topic input
    mock_input.side_effect = EOFError()

    with patch("spds.swarm_manager.SPDSAgent.create_new") as mock_create:
        mock_agent = Mock()
        mock_create.return_value = mock_agent

        manager = SwarmManager(
            client=mock_letta_client, agent_profiles=[sample_agent_profiles[0]]
        )

        # Capture output
        captured_output = StringIO()
        sys.stdout = captured_output

        manager.start_chat()

        sys.stdout = sys.__stdout__
        output = captured_output.getvalue()

        # Should handle EOF gracefully
        assert "Exiting" in output


# ============================================================================
# Tests from test_swarm_manager_core.py
# ============================================================================


def test_init_no_agents_raises():
    """Test that initializing without agents raises ValueError."""
    import spds.swarm_manager as sm

    dummy_client = SimpleNamespace()
    with pytest.raises(ValueError):
        sm.SwarmManager(client=dummy_client, conversation_mode="hybrid")


def test_init_with_agent_ids_uses_retrieve(monkeypatch):
    """Test initialization with agent IDs uses retrieve method."""
    import spds.swarm_manager as sm

    # Stub SPDSAgent so we don't require real AgentState
    class StubAgent:
        def __init__(self, agent_state, client):
            self.agent = agent_state
            self.name = getattr(agent_state, "name", "A")

    monkeypatch.setattr(sm, "SPDSAgent", StubAgent)

    # Dummy client with agents.retrieve
    class DummyAgents:
        def retrieve(self, agent_id):
            return SimpleNamespace(id=agent_id, name=f"Agent-{agent_id}", system="")

    dummy_client = SimpleNamespace(agents=DummyAgents())

    mgr = sm.SwarmManager(client=dummy_client, agent_ids=["1"], conversation_mode="hybrid")
    assert len(mgr.agents) == 1
    assert mgr.agents[0].agent.id == "1"


def test_init_with_profiles_ephemeral_disabled_raises(monkeypatch):
    """Test that profiles raise error when ephemeral agents disabled."""
    import spds.swarm_manager as sm
    from spds import config

    monkeypatch.setattr(config, "get_allow_ephemeral_agents", lambda: False)

    dummy_client = SimpleNamespace(agents=SimpleNamespace())
    with pytest.raises(ValueError):
        sm.SwarmManager(
            client=dummy_client,
            agent_profiles=[{"name": "X", "persona": "p", "expertise": ["e"]}],
        )


# ============================================================================
# Tests from test_swarm_manager_coverage_boost.py
# ============================================================================


def test_init_invalid_mode_raises(monkeypatch):
    """Test that invalid conversation mode raises ValueError."""
    import spds.swarm_manager as sm

    class StubSPDSAgent:
        def __init__(self, state, client):
            class A:
                def __init__(self, id_):
                    self.id = id_
            self.agent = A(getattr(state, "id", "stub-id"))
            self.name = getattr(state, "name", "Stub")

    monkeypatch.setattr(sm, "SPDSAgent", StubSPDSAgent)

    class DummyAgents:
        def retrieve(self, agent_id):
            return SimpleNamespace(id=agent_id, name="A")

    client = SimpleNamespace(agents=DummyAgents())
    with pytest.raises(ValueError):
        sm.SwarmManager(
            client, agent_ids=["ok"], conversation_mode="not-a-mode"
        )


def test_secretary_init_failure_sets_flag_false(monkeypatch):
    """Test that secretary initialization failure sets flag to False."""
    import spds.swarm_manager as sm

    class StubSPDSAgent:
        def __init__(self, state, client):
            class A:
                def __init__(self, id_):
                    self.id = id_
            self.agent = A(getattr(state, "id", "stub-id"))
            self.name = getattr(state, "name", "Stub")

    class RaisingSecretary:
        def __init__(self, *a, **kw):
            raise RuntimeError("boom")

    monkeypatch.setattr(sm, "SPDSAgent", StubSPDSAgent)
    monkeypatch.setattr(sm, "SecretaryAgent", RaisingSecretary)

    class DummyAgents:
        def retrieve(self, agent_id):
            return SimpleNamespace(id=agent_id, name="A")

    client = SimpleNamespace(agents=DummyAgents())
    mgr = sm.SwarmManager(
        client, agent_ids=["ok"], enable_secretary=True, secretary_mode="adaptive"
    )
    assert mgr.enable_secretary is False


def test_load_agents_by_id_not_found_then_success(monkeypatch):
    """Test loading agents by ID with NotFoundError then success."""
    import spds.swarm_manager as sm

    class StubSPDSAgent:
        def __init__(self, state, client):
            class A:
                def __init__(self, id_):
                    self.id = id_
            self.agent = A(getattr(state, "id", "stub-id"))
            self.name = getattr(state, "name", "Stub")

    monkeypatch.setattr(sm, "SPDSAgent", StubSPDSAgent)

    class DummyAgents:
        def __init__(self):
            self.seq = [_make_not_found_error("missing"), SimpleNamespace(id="ok2", name="B")]

        def retrieve(self, agent_id):
            effect = self.seq.pop(0)
            if isinstance(effect, Exception):
                raise effect
            return effect

    client = SimpleNamespace(agents=DummyAgents())
    mgr = sm.SwarmManager(
        client, agent_ids=["missing", "ok2"], conversation_mode="hybrid"
    )
    # One agent should be loaded
    assert len(mgr.agents) == 1 and mgr.agents[0].name == "B"


def test_load_agents_by_name_warning_and_success(monkeypatch, capsys):
    """Test loading agents by name with empty result then success."""
    import spds.swarm_manager as sm

    class StubSPDSAgent:
        def __init__(self, state, client):
            class A:
                def __init__(self, id_):
                    self.id = id_
            self.agent = A(getattr(state, "id", "stub-id"))
            self.name = getattr(state, "name", "Stub")

    monkeypatch.setattr(sm, "SPDSAgent", StubSPDSAgent)

    # First call returns empty, second returns one
    class Agents:
        def __init__(self):
            self.calls = 0

        def list(self, name=None, limit=1):
            self.calls += 1
            if self.calls == 1:
                return []
            return [SimpleNamespace(id="x", name="Found")]

    client = SimpleNamespace(agents=Agents())

    # First: empty triggers warning -> but no agents overall should raise later
    with pytest.raises(ValueError):
        sm.SwarmManager(client, agent_names=["Nope"])
    out = capsys.readouterr().out
    assert "not found" in out

    # Second: with a found agent
    mgr = sm.SwarmManager(client, agent_names=["Found"])
    assert mgr.agents and mgr.agents[0].name == "Found"


def test_init_from_profiles(monkeypatch):
    """Test initialization from agent profiles."""
    import spds.swarm_manager as sm

    class StubSPDSAgent:
        @classmethod
        def create_new(cls, name, persona, expertise, client, model=None, embedding=None):
            obj = object.__new__(cls)
            obj.name = name
            class A:
                id = f"{name}-id"
            obj.agent = A()
            return obj

    monkeypatch.setattr(sm, "SPDSAgent", StubSPDSAgent)
    client = SimpleNamespace()
    profiles = [
        {
            "name": "P1",
            "persona": "p",
            "expertise": ["x"],
            "model": None,
            "embedding": None,
        }
    ]
    mgr = sm.SwarmManager(client, agent_profiles=profiles)
    assert mgr.agents and mgr.agents[0].name == "P1"


def test_start_chat_quit_immediately(monkeypatch, capsys):
    """Test start_chat with immediate quit."""
    import spds.swarm_manager as sm

    mgr = object.__new__(sm.SwarmManager)
    mgr.conversation_mode = "hybrid"
    mgr._start_meeting = lambda topic: None
    mgr._agent_turn = lambda topic: None
    mgr._end_meeting = lambda: None
    mgr._handle_secretary_commands = lambda s: False
    mgr._secretary = None
    mgr.secretary_agent_id = None

    monkeypatch.setattr(__import__("builtins"), "input", lambda prompt="": "quit")
    mgr.start_chat()
    out = capsys.readouterr().out
    assert "Swarm chat started" in out and "Exiting chat." in out


def test_start_chat_with_topic_secretary_banner_and_quit(monkeypatch, capsys):
    """Test start_chat_with_topic with secretary banner and quit."""
    import spds.swarm_manager as sm

    class Sec:
        def __init__(self):
            class A:
                name = "SecName"
            self.agent = A()
            self.mode = "adaptive"

    mgr = object.__new__(sm.SwarmManager)
    mgr.conversation_mode = "hybrid"
    mgr._start_meeting = lambda topic: None
    mgr._agent_turn = lambda topic: None
    mgr._end_meeting = lambda: None
    mgr._handle_secretary_commands = lambda s: False
    mgr.secretary = Sec()

    monkeypatch.setattr(__import__("builtins"), "input", lambda prompt="": "quit")
    mgr.start_chat_with_topic("T")
    out = capsys.readouterr().out
    assert "Secretary: SecName" in out and "Exiting chat." in out


# ============================================================================
# Tests from test_swarm_manager_generated.py
# ============================================================================


def test_reset_agent_messages_handles_exception(capsys):
    """Test that reset_agent_messages handles exceptions gracefully."""
    import spds.swarm_manager as sm

    class Msgs:
        def reset(self, agent_id):
            raise Exception("boom")

    client = SimpleNamespace(agents=SimpleNamespace(messages=Msgs()))
    mgr = object.__new__(sm.SwarmManager)
    mgr.client = client

    # Should not raise
    mgr._reset_agent_messages("agent-42")
    captured = capsys.readouterr()
    assert "Failed to reset messages" in captured.out


# ============================================================================
# Tests from test_swarm_manager_uncovered.py
# ============================================================================


def test_start_chat_eof_inner_loop(monkeypatch, capsys):
    """Test start_chat EOF handling in inner loop."""
    import spds.swarm_manager as sm

    mgr = object.__new__(sm.SwarmManager)
    mgr.conversation_mode = "hybrid"
    mgr._start_meeting = lambda topic: None
    mgr._agent_turn = lambda topic: None
    mgr._end_meeting = lambda: None
    mgr._handle_secretary_commands = lambda s: False
    mgr._secretary = None
    mgr.secretary_agent_id = None

    # First call returns a topic, second call simulates Ctrl+D (EOF)
    seq = iter(["some topic"])

    def input_stub(prompt=""):
        try:
            return next(seq)
        except StopIteration:
            raise EOFError()

    monkeypatch.setattr(__import__("builtins"), "input", input_stub)
    mgr.start_chat()
    out = capsys.readouterr().out
    assert "Exiting chat." in out


def test_start_chat_with_topic_eof_inner_loop(monkeypatch, capsys):
    """Test start_chat_with_topic EOF handling in inner loop."""
    import spds.swarm_manager as sm

    mgr = object.__new__(sm.SwarmManager)
    mgr.conversation_mode = "hybrid"
    mgr._start_meeting = lambda topic: None
    mgr._agent_turn = lambda topic: None
    mgr._end_meeting = lambda: None
    mgr._handle_secretary_commands = lambda s: False
    mgr._secretary = None
    mgr.secretary_agent_id = None
    mgr.pending_nomination = None

    # Simulate EOF immediately in the inner loop
    def input_stub(prompt=""):
        raise EOFError()

    monkeypatch.setattr(__import__("builtins"), "input", input_stub)
    mgr.start_chat_with_topic("T")
    out = capsys.readouterr().out
    assert "Exiting chat." in out


def test_start_chat_secretary_command_continue(monkeypatch, capsys):
    """Test start_chat with secretary command that triggers continue."""
    import spds.swarm_manager as sm

    mgr = object.__new__(sm.SwarmManager)
    mgr.conversation_mode = "hybrid"
    mgr._start_meeting = lambda topic: None
    mgr._agent_turn = lambda topic: None
    mgr._end_meeting = lambda: None
    mgr._secretary = None
    mgr.secretary_agent_id = None

    # Inputs: topic, a secretary-command which should be handled and cause 'continue', then quit
    seq = iter(["topic", "/minutes", "quit"])

    def input_stub(prompt=""):
        try:
            return next(seq)
        except StopIteration:
            raise EOFError()

    monkeypatch.setattr(__import__("builtins"), "input", input_stub)
    mgr.start_chat()
    out = capsys.readouterr().out
    assert "Secretary is not enabled" in out or "❌ Secretary is not enabled" in out
    assert "Exiting chat." in out


def test_start_chat_observe_message_called(monkeypatch):
    """Test that secretary observe_message is called during chat."""
    import spds.swarm_manager as sm

    mgr = object.__new__(sm.SwarmManager)
    mgr.conversation_mode = "hybrid"
    mgr._start_meeting = lambda topic: None
    mgr._agent_turn = lambda topic: None
    mgr._end_meeting = lambda: None
    mgr._handle_secretary_commands = lambda s: False
    mgr.conversation_history = ""
    mgr.last_speaker = None
    mgr.meeting_type = "discussion"
    mgr.conversation_mode = "hybrid"
    flag = SimpleNamespace(called=False)

    def observe(who, msg):
        flag.called = True

    mgr.secretary = SimpleNamespace(
        agent=SimpleNamespace(name="Sec"),
        mode="adaptive",
        observe_message=observe,
    )

    seq = iter(["topic", "hello", "quit"])

    def input_stub(prompt=""):
        try:
            return next(seq)
        except StopIteration:
            raise EOFError()

    monkeypatch.setattr(__import__("builtins"), "input", input_stub)
    mgr.start_chat()
    assert flag.called is True


def test_reset_agent_messages_success(capsys):
    """Test successful reset of agent messages."""
    import spds.swarm_manager as sm

    class Msgs:
        def reset(self, agent_id=None):
            return None

    class Agents:
        def __init__(self):
            self.messages = Msgs()

    mgr = object.__new__(sm.SwarmManager)
    mgr.client = SimpleNamespace(agents=Agents())
    mgr._reset_agent_messages("xyz")
    out = capsys.readouterr().out
    assert "Successfully reset messages for agent xyz" in out
