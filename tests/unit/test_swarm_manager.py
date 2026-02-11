"""
Unit tests for spds.swarm_manager module.
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


def _make_not_found_error(message="Not found"):
    resp = httpx.Response(404, request=httpx.Request("GET", "http://test"))
    from letta_client import NotFoundError
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


from letta_client import NotFoundError

from spds.spds_agent import SPDSAgent
from spds.swarm_manager import SwarmManager


def make_tool_response(text: str):
    """
    Create a synthetic tool-message response object representing a single tool call to `send_message`.

    The returned object is a SimpleNamespace with a `messages` list containing one message SimpleNamespace that mimics a tool-generated message:
    - message_type is "tool_message"
    - the message contains a single `tool_call` whose `function.name` is "send_message" and whose `function.arguments` is a JSON string encoding {"message": text}

    Parameters:
        text (str): The message text to embed as the `message` argument of the simulated `send_message` tool call.

    Returns:
        SimpleNamespace: An object with shape compatible with tests that expect tool-based agent responses (i.e., has a `messages` attribute with the described message structure).
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

    Useful in unit tests to simulate an assistant response. By default the message content is a plain string; set `as_list=True` to produce a list-style content payload (a list containing a single dict with keys `type` and `text`).

    Parameters:
        text (str): The assistant's text content.
        as_list (bool, optional): When True, wrap `text` in a list-style content object. Defaults to False.

    Returns:
        types.SimpleNamespace: A SimpleNamespace with a `messages` attribute containing a single assistant message. Each message includes `role`, `message_type`, `content`, and placeholders for `tool_calls` and `tool_return`.
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


class TestSwarmManager:
    """Test the SwarmManager class."""

    def test_init_with_agent_profiles(self, mock_letta_client, sample_agent_profiles):
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

    def test_init_with_agent_ids(self, mock_letta_client):
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

    def test_init_with_agent_names(self, mock_letta_client):
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

    def test_init_with_no_agents_raises_error(self, mock_letta_client):
        """Test that initializing with no agents raises ValueError."""
        with pytest.raises(
            ValueError, match="Swarm manager initialized with no agents"
        ):
            SwarmManager(client=mock_letta_client)

    def test_load_agents_by_id_with_missing_agent(self, mock_letta_client):
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

    def test_load_agents_by_name_with_missing_agent(self, mock_letta_client):
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

    def test_create_agents_from_profiles_with_model_config(self, mock_letta_client):
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

    def test_agent_turn_with_motivated_agents(
        self, mock_letta_client, sample_agent_profiles
    ):
        """Test agent turn when agents are motivated to speak."""
        with patch("spds.swarm_manager.SPDSAgent.create_new") as mock_create:
            # Create mock agents with different priority scores
            mock_agent1 = Mock(spec=SPDSAgent)
            mock_agent1.name = "Agent 1"
            mock_agent1.priority_score = 15.0
            mock_agent1.motivation_score = 40
            mock_agent1.assess_motivation_and_priority = Mock()

            mock_agent2 = Mock(spec=SPDSAgent)
            mock_agent2.name = "Agent 2"
            mock_agent2.priority_score = 25.0  # Higher priority
            mock_agent2.motivation_score = 50
            mock_agent2.assess_motivation_and_priority = Mock()

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

    def test_agent_turn_with_no_motivated_agents(
        self, mock_letta_client, sample_agent_profiles
    ):
        """Test agent turn when no agents are motivated to speak."""
        with patch("spds.swarm_manager.SPDSAgent.create_new") as mock_create:
            # Create mock agents with zero priority scores
            mock_agent1 = Mock(spec=SPDSAgent)
            mock_agent1.name = "Agent 1"
            mock_agent1.priority_score = 0.0
            mock_agent1.motivation_score = 20
            mock_agent1.assess_motivation_and_priority = Mock()

            mock_agent2 = Mock(spec=SPDSAgent)
            mock_agent2.name = "Agent 2"
            mock_agent2.priority_score = 0.0
            mock_agent2.motivation_score = 15
            mock_agent2.assess_motivation_and_priority = Mock()

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

    def test_agent_turn_with_speak_error(
        self, mock_letta_client, sample_agent_profiles
    ):
        """Test agent turn when speaking agent encounters an error."""
        with patch("spds.swarm_manager.SPDSAgent.create_new") as mock_create:
            # Create mock agent that will have speak error
            mock_agent = Mock(spec=SPDSAgent)
            mock_agent.name = "Error Agent"
            mock_agent.priority_score = 30.0
            mock_agent.motivation_score = 50
            mock_agent.assess_motivation_and_priority = Mock()

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
                "Error Agent: I have some thoughts but I'm having trouble phrasing them."
                in output
            )
            assert (
                "[Debug: Error during speak() - API Error]" in output
                or "[Debug: Error in sequential response - API Error]" in output
            )

    @patch("builtins.input")
    def test_start_chat_basic_flow(
        self, mock_input, mock_letta_client, sample_agent_profiles
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
        self, mock_input, mock_letta_client, sample_agent_profiles
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

    def test_update_agent_memories_handles_token_reset(
        self,
        mock_letta_client,
        sample_agent_profiles,
    ):
        """Token limit errors should trigger a reset and retry."""
        with patch("spds.swarm_manager.SPDSAgent.create_new") as mock_create:
            dummy_agent = SimpleNamespace(
                name="Agent 1", agent=SimpleNamespace(id="agent-1")
            )
            mock_create.return_value = dummy_agent
            manager = SwarmManager(
                client=mock_letta_client,
                agent_profiles=[sample_agent_profiles[0]],
            )

        manager._reset_agent_messages = Mock()
        mock_letta_client.agents.messages.create.side_effect = [
            Exception("token limit exceeded"),
            None,
        ]

        manager._update_agent_memories(
            "Important update", speaker="Facilitator", max_retries=2
        )

        manager._reset_agent_messages.assert_called_once_with("agent-1")
        assert mock_letta_client.agents.messages.create.call_count == 2

    def test_update_agent_memories_token_reset_retry_failure(
        self,
        mock_letta_client,
        sample_agent_profiles,
        capsys,
    ):
        """If the retry after a reset fails, we should log the failure."""
        with patch("spds.swarm_manager.SPDSAgent.create_new") as mock_create:
            dummy_agent = SimpleNamespace(
                name="Agent 1", agent=SimpleNamespace(id="agent-1")
            )
            mock_create.return_value = dummy_agent
            manager = SwarmManager(
                client=mock_letta_client,
                agent_profiles=[sample_agent_profiles[0]],
            )

        manager._reset_agent_messages = Mock()
        mock_letta_client.agents.messages.create.side_effect = [
            Exception("token limit exceeded"),
            Exception("still failing"),
        ]

        manager._update_agent_memories(
            "Critical update", speaker="Facilitator", max_retries=2
        )

        manager._reset_agent_messages.assert_called_once_with("agent-1")
        assert mock_letta_client.agents.messages.create.call_count == 2

        output = capsys.readouterr().out
        assert "Token limit reached for Agent 1" in output
        assert "Retry failed for Agent 1: still failing" in output
        assert "Failed to update Agent 1 after 2 attempts" in output

    def test_update_agent_memories_reports_failure_after_retries(
        self,
        mock_letta_client,
        sample_agent_profiles,
        capsys,
    ):
        """A non-retryable error should report the failure without retry."""
        with patch("spds.swarm_manager.SPDSAgent.create_new") as mock_create:
            dummy_agent = SimpleNamespace(
                name="Agent 1", agent=SimpleNamespace(id="agent-1")
            )
            mock_create.return_value = dummy_agent
            manager = SwarmManager(
                client=mock_letta_client,
                agent_profiles=[sample_agent_profiles[0]],
            )

        mock_letta_client.agents.messages.create.side_effect = Exception("hard failure")

        manager._update_agent_memories("Another update", max_retries=2)

        output = capsys.readouterr().out
        assert "Failed to update Agent 1" in output

    def test_get_agent_message_count_success_and_error(
        self,
        mock_letta_client,
        sample_agent_profiles,
    ):
        """_get_agent_message_count should handle success and exceptions."""
        with patch("spds.swarm_manager.SPDSAgent.create_new") as mock_create:
            dummy_agent = SimpleNamespace(
                name="Agent 1", agent=SimpleNamespace(id="agent-1")
            )
            mock_create.return_value = dummy_agent
            manager = SwarmManager(
                client=mock_letta_client,
                agent_profiles=[sample_agent_profiles[0]],
            )

        mock_letta_client.agents.messages.list.return_value = [1, 2, 3]
        assert manager._get_agent_message_count("agent-1") == 3

        mock_letta_client.agents.messages.list.side_effect = RuntimeError("boom")
        assert manager._get_agent_message_count("agent-1") == 0

    def test_warm_up_agent_success_and_failure(
        self,
        mock_letta_client,
        sample_agent_profiles,
    ):
        """_warm_up_agent should return True on success and False on failure."""
        with patch("spds.swarm_manager.SPDSAgent.create_new") as mock_create:
            dummy_agent = SimpleNamespace(
                name="Agent 1", agent=SimpleNamespace(id="agent-1")
            )
            mock_create.return_value = dummy_agent
            manager = SwarmManager(
                client=mock_letta_client,
                agent_profiles=[sample_agent_profiles[0]],
            )

        test_agent = SimpleNamespace(
            name="Agent 1", agent=SimpleNamespace(id="agent-1")
        )

        mock_letta_client.agents.messages.create.return_value = None
        with patch("spds.swarm_manager.time.sleep") as sleep_mock:
            assert manager._warm_up_agent(test_agent, "Topic") is True
            sleep_mock.assert_called()

        mock_letta_client.agents.messages.create.side_effect = Exception("fail")
        assert manager._warm_up_agent(test_agent, "Topic") is False

    def test_extract_agent_response_variants(
        self,
        mock_letta_client,
        sample_agent_profiles,
    ):
        """_extract_agent_response should handle tool calls, lists, and fallbacks."""
        with patch("spds.swarm_manager.SPDSAgent.create_new") as mock_create:
            dummy_agent = SimpleNamespace(
                name="Agent 1", agent=SimpleNamespace(id="agent-1")
            )
            mock_create.return_value = dummy_agent
            manager = SwarmManager(
                client=mock_letta_client,
                agent_profiles=[sample_agent_profiles[0]],
            )

        tool_response = make_tool_response("From tool call")
        assert manager._extract_agent_response(tool_response) == "From tool call"

        list_response = make_assistant_response("From list content", as_list=True)
        assert manager._extract_agent_response(list_response) == "From list content"

        empty_message = SimpleNamespace(
            tool_calls=[],
            tool_return=None,
            message_type=None,
            content=None,
        )
        empty_response = SimpleNamespace(messages=[empty_message])
        assert (
            manager._extract_agent_response(empty_response)
            == "I have some thoughts but I'm having trouble phrasing them."
        )

    def test_hybrid_turn_handles_mixed_responses(
        self,
        mock_letta_client,
        sample_agent_profiles,
    ):
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

    def test_all_speak_turn_updates_memories(
        self,
        mock_letta_client,
        sample_agent_profiles,
    ):
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
        self,
        mock_letta_client,
        sample_agent_profiles,
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
        self,
        mock_letta_client,
        sample_agent_profiles,
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
        self,
        mock_letta_client,
        sample_agent_profiles,
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
        self,
        mock_letta_client,
        sample_agent_profiles,
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

        fallback = "I have some thoughts but I'm having trouble phrasing them."
        assert f"Agent 1: {fallback}" in manager.conversation_history
        manager._notify_secretary_agent_response.assert_called_with("Agent 1", fallback)

    def test_pure_priority_turn_handles_exception(
        self,
        mock_letta_client,
        sample_agent_profiles,
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

        fallback = (
            "I have thoughts on this topic but I'm having difficulty expressing them."
        )
        assert f"Agent 1: {fallback}" in manager.conversation_history
        manager._notify_secretary_agent_response.assert_called_with("Agent 1", fallback)

    def test_start_meeting_with_secretary_sets_metadata(
        self,
        mock_letta_client,
        sample_agent_profiles,
    ):
        """_start_meeting should coordinate with the secretary and log the topic."""
        with patch("spds.swarm_manager.SPDSAgent.create_new") as mock_create:
            base_agent = SimpleNamespace(name="Base", agent=SimpleNamespace(id="base"))
            mock_create.return_value = base_agent
            manager = SwarmManager(
                client=mock_letta_client,
                agent_profiles=[sample_agent_profiles[0]],
            )

        secretary = SimpleNamespace(
            start_meeting=Mock(),
            meeting_metadata={},
        )
        manager.secretary = secretary
        manager.meeting_type = "planning"
        manager.conversation_history = ""
        manager.conversation_mode = "hybrid"
        manager.agents = [
            SimpleNamespace(name="Agent 1"),
            SimpleNamespace(name="Agent 2"),
        ]

        manager._start_meeting("Strategy")

        secretary.start_meeting.assert_called_once_with(
            topic="Strategy",
            participants=["Agent 1", "Agent 2"],
            meeting_type="planning",
        )
        assert secretary.meeting_metadata["conversation_mode"] == "hybrid"
        assert "System: The topic is 'Strategy'." in manager.conversation_history

    def test_handle_secretary_commands_without_secretary(
        self, mock_letta_client, sample_agent_profiles, capsys
    ):
        """Secretary-specific commands should warn when secretary is disabled."""
        with patch("spds.swarm_manager.SPDSAgent.create_new") as mock_create:
            base_agent = SimpleNamespace(name="Base", agent=SimpleNamespace(id="base"))
            mock_create.return_value = base_agent
            manager = SwarmManager(
                client=mock_letta_client,
                agent_profiles=[sample_agent_profiles[0]],
            )

        manager.secretary = None

        handled = manager._handle_secretary_commands("/minutes")
        output = capsys.readouterr().out

        assert handled is True
        assert "Secretary is not enabled" in output

    def test_handle_secretary_commands_routes_to_secretary(
        self, mock_letta_client, sample_agent_profiles, capsys
    ):
        """Commands should call through to the secretary when available."""
        with patch("spds.swarm_manager.SPDSAgent.create_new") as mock_create:
            base_agent = SimpleNamespace(name="Base", agent=SimpleNamespace(id="base"))
            mock_create.return_value = base_agent
            manager = SwarmManager(
                client=mock_letta_client,
                agent_profiles=[sample_agent_profiles[0]],
            )

        secretary = SimpleNamespace(
            generate_minutes=Mock(return_value="minutes text"),
            set_mode=Mock(),
            add_action_item=Mock(),
            get_conversation_stats=Mock(return_value={"summary": "stats"}),
            meeting_metadata={"topic": "Strategy"},
            conversation_log="log",
            action_items=["Do something"],
            decisions=["Decide"],
            mode="adaptive",
            observe_message=Mock(),
        )
        manager.secretary = secretary
        manager._handle_export_command = Mock()

        assert manager._handle_secretary_commands("/minutes") is True
        assert secretary.generate_minutes.called
        assert "minutes text" in capsys.readouterr().out

        assert manager._handle_secretary_commands("/export summary") is True
        manager._handle_export_command.assert_called_with("summary")

        assert manager._handle_secretary_commands("/formal") is True
        secretary.set_mode.assert_any_call("formal")
        assert "Secretary mode changed to formal" in capsys.readouterr().out

        assert manager._handle_secretary_commands("/casual") is True
        secretary.set_mode.assert_any_call("casual")

        assert manager._handle_secretary_commands("/action-item Prepare report") is True
        secretary.add_action_item.assert_called_with("Prepare report")

        assert manager._handle_secretary_commands("/action-item") is True
        assert "Usage: /action-item" in capsys.readouterr().out

        assert manager._handle_secretary_commands("/stats") is True
        assert "summary" in capsys.readouterr().out

    def test_handle_secretary_commands_memory_reports(
        self, mock_letta_client, sample_agent_profiles, capsys
    ):
        """Memory commands should run even without a secretary."""
        with patch("spds.swarm_manager.SPDSAgent.create_new") as mock_create:
            base_agent = SimpleNamespace(name="Base", agent=SimpleNamespace(id="base"))
            mock_create.return_value = base_agent
            manager = SwarmManager(
                client=mock_letta_client,
                agent_profiles=[sample_agent_profiles[0]],
            )

        summary = {
            "total_agents": 2,
            "agents_with_high_memory": 1,
            "total_messages_across_agents": 123,
            "agents_status": [
                {
                    "name": "Agent 1",
                    "recall_memory": 600,
                    "archival_memory": 2,
                    "high_memory": True,
                }
            ],
        }
        manager.get_memory_status_summary = Mock(return_value=summary)
        manager.check_memory_awareness_status = Mock()

        assert manager._handle_secretary_commands("/memory-status") is True
        status_output = capsys.readouterr().out
        assert "Total agents: 2" in status_output
        assert "Agents with >500 messages" in status_output

        assert manager._handle_secretary_commands("/memory-awareness") is True
        manager.check_memory_awareness_status.assert_called_with(silent=False)

    def test_handle_export_command_variants(
        self, mock_letta_client, sample_agent_profiles
    ):
        """_handle_export_command should dispatch to the correct exporter."""
        with patch("spds.swarm_manager.SPDSAgent.create_new") as mock_create:
            base_agent = SimpleNamespace(name="Base", agent=SimpleNamespace(id="base"))
            mock_create.return_value = base_agent
            manager = SwarmManager(
                client=mock_letta_client,
                agent_profiles=[sample_agent_profiles[0]],
                enable_secretary=True,
            )

        manager.secretary = SimpleNamespace(
            meeting_metadata={"topic": "Topic"},
            conversation_log="log",
            action_items=["Item"],
            decisions=["Decision"],
            get_conversation_stats=Mock(return_value={"summary": "stats"}),
            mode="adaptive",
        )
        manager.export_manager = Mock()
        manager.export_manager.export_meeting_minutes.return_value = "minutes.md"

        manager._handle_export_command("minutes")
        meeting_data = manager.export_manager.export_meeting_minutes.call_args[0][0]
        assert meeting_data["metadata"]["topic"] == "Topic"

        manager.export_manager.export_executive_summary.return_value = "summary.md"
        manager._handle_export_command("summary")
        manager.export_manager.export_executive_summary.assert_called()

        manager.export_manager.export_complete_package.return_value = ["one", "two"]
        manager._handle_export_command("all")
        manager.export_manager.export_complete_package.assert_called_with(
            meeting_data, "adaptive"
        )

    def test_handle_export_command_unknown_format(
        self, mock_letta_client, sample_agent_profiles, capsys
    ):
        """Unknown export formats should notify the user."""
        with patch("spds.swarm_manager.SPDSAgent.create_new") as mock_create:
            base_agent = SimpleNamespace(name="Base", agent=SimpleNamespace(id="base"))
            mock_create.return_value = base_agent
            manager = SwarmManager(
                client=mock_letta_client,
                agent_profiles=[sample_agent_profiles[0]],
                enable_secretary=True,
            )

        manager.secretary = SimpleNamespace(
            meeting_metadata={},
            conversation_log="",
            action_items=[],
            decisions=[],
            get_conversation_stats=Mock(return_value={}),
            mode="adaptive",
        )
        manager.export_manager = Mock()

        manager._handle_export_command("unknown")
        output = capsys.readouterr().out
        assert "Unknown export format" in output

    def test_offer_export_options_invokes_command(
        self, mock_letta_client, sample_agent_profiles
    ):
        """_offer_export_options should forward user input to command handler."""
        with patch("spds.swarm_manager.SPDSAgent.create_new") as mock_create:
            base_agent = SimpleNamespace(name="Base", agent=SimpleNamespace(id="base"))
            mock_create.return_value = base_agent
            manager = SwarmManager(
                client=mock_letta_client,
                agent_profiles=[sample_agent_profiles[0]],
                enable_secretary=True,
            )

        manager.secretary = SimpleNamespace(
            meeting_metadata={},
            conversation_log="",
            action_items=[],
            decisions=[],
            mode="adaptive",
            get_conversation_stats=Mock(return_value={}),
        )
        manager._handle_secretary_commands = Mock()

        with patch("builtins.input", return_value="/minutes"):
            manager._offer_export_options()

        manager._handle_secretary_commands.assert_called_once_with("/minutes")

    def test_notify_secretary_agent_response(
        self, mock_letta_client, sample_agent_profiles
    ):
        """_notify_secretary_agent_response should forward to secretary when present."""
        with patch("spds.swarm_manager.SPDSAgent.create_new") as mock_create:
            base_agent = SimpleNamespace(name="Base", agent=SimpleNamespace(id="base"))
            mock_create.return_value = base_agent
            manager = SwarmManager(
                client=mock_letta_client,
                agent_profiles=[sample_agent_profiles[0]],
            )

        observer = Mock()
        manager.secretary = SimpleNamespace(observe_message=observer)

        manager._notify_secretary_agent_response("Agent", "Message")

        observer.assert_called_once_with("Agent", "Message")

    def test_check_memory_awareness_status_outputs_info(
        self, mock_letta_client, sample_agent_profiles, capsys
    ):
        """Memory awareness information should be printed when available."""
        with patch("spds.swarm_manager.SPDSAgent.create_new") as mock_create:
            base_agent = SimpleNamespace(name="Base", agent=SimpleNamespace(id="base"))
            mock_create.return_value = base_agent
            manager = SwarmManager(
                client=mock_letta_client,
                agent_profiles=[sample_agent_profiles[0]],
            )

        manager.agents = [
            SimpleNamespace(name="Agent 1", agent=SimpleNamespace(id="agent-1")),
            SimpleNamespace(name="Agent 2", agent=SimpleNamespace(id="agent-2")),
        ]

        with patch(
            "spds.swarm_manager.create_memory_awareness_for_agent"
        ) as awareness_patch:
            awareness_patch.side_effect = ["Awareness message", RuntimeError("fail")]

            manager.check_memory_awareness_status(silent=False)

        output = capsys.readouterr().out
        assert "Awareness message" in output
        assert "Could not generate memory awareness" in output

    def test_check_memory_awareness_status_silent(
        self, mock_letta_client, sample_agent_profiles, capsys
    ):
        """Silent checks should not print anything."""
        with patch("spds.swarm_manager.SPDSAgent.create_new") as mock_create:
            base_agent = SimpleNamespace(name="Base", agent=SimpleNamespace(id="base"))
            mock_create.return_value = base_agent
            manager = SwarmManager(
                client=mock_letta_client,
                agent_profiles=[sample_agent_profiles[0]],
            )

        manager.agents = [
            SimpleNamespace(name="Agent 1", agent=SimpleNamespace(id="agent-1"))
        ]

        capsys.readouterr()

        with patch(
            "spds.swarm_manager.create_memory_awareness_for_agent",
            return_value="Message",
        ):
            manager.check_memory_awareness_status(silent=True)

        assert capsys.readouterr().out == ""

    def test_get_memory_status_summary_with_errors(
        self, mock_letta_client, sample_agent_profiles
    ):
        """get_memory_status_summary should handle errors per agent."""
        with patch("spds.swarm_manager.SPDSAgent.create_new") as mock_create:
            base_agent = SimpleNamespace(name="Base", agent=SimpleNamespace(id="base"))
            mock_create.return_value = base_agent
            manager = SwarmManager(
                client=mock_letta_client,
                agent_profiles=[sample_agent_profiles[0]],
            )

        manager.agents = [
            SimpleNamespace(name="Agent 1", agent=SimpleNamespace(id="agent-1")),
            SimpleNamespace(name="Agent 2", agent=SimpleNamespace(id="agent-2")),
        ]

        mock_letta_client.agents.context = Mock()
        mock_letta_client.agents.context.retrieve.side_effect = [
            {"num_recall_memory": 600, "num_archival_memory": 2},
            RuntimeError("fail"),
        ]

        summary = manager.get_memory_status_summary()

        assert summary["total_agents"] == 2
        assert summary["agents_with_high_memory"] == 1
        assert summary["total_messages_across_agents"] == 600
        assert summary["agents_status"][0]["high_memory"] is True
        assert summary["agents_status"][1]["error"] == "fail"
