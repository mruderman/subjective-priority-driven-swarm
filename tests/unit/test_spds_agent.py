"""
Unit tests for spds.spds_agent module.
"""

import json
from types import SimpleNamespace
from unittest.mock import MagicMock, Mock, patch

import pytest
from letta_client.types import (
    AgentState,
    EmbeddingConfig,
    LettaResponse,
    LlmConfig,
    Memory,
    Message,
    Tool,
)


def mk_agent_state(
    id: str, name: str, system: str, model: str = "openai/gpt-4", tools=None
):
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
        tools=tools or [],
        sources=[],
        tags=[],
        model=model,
        embedding="openai/text-embedding-ada-002",
    )


from letta_client.errors import NotFoundError

from spds import tools
from spds.spds_agent import SPDSAgent
from spds.tools import SubjectiveAssessment


class TestSPDSAgent:
    """Test the SPDSAgent class."""

    def test_init_with_agent_state(
        self, mock_letta_client, sample_agent_state, mock_tool_state
    ):
        """Test SPDSAgent initialization with existing AgentState."""
        # Build an agent state with tool already attached (can't mutate frozen model)
        agent_state = mk_agent_state(
            id="ag-test-123",
            name="Test Agent",
            system="You are Test Agent. Your persona is: A test agent for unit testing. Your expertise is in: testing, validation.",
            model="openai/gpt-4",
        )
        agent_state_tools = [mock_tool_state]
        agent_state = AgentState(
            id=agent_state.id,
            name=agent_state.name,
            system=agent_state.system,
            agent_type=agent_state.agent_type,
            llm_config=agent_state.llm_config,
            embedding_config=agent_state.embedding_config,
            memory=agent_state.memory,
            tools=agent_state_tools,
            sources=[],
            tags=[],
            model=agent_state.model,
            embedding=agent_state.embedding,
        )

        agent = SPDSAgent(agent_state, mock_letta_client)

        assert agent.client == mock_letta_client
        assert agent.agent.id == agent_state.id
        assert agent.name == "Test Agent"
        assert agent.motivation_score == 0
        assert agent.priority_score == 0
        assert agent.last_assessment is None

    def test_parse_system_prompt_with_valid_format(self, mock_letta_client):
        """Test parsing system prompt with proper persona and expertise format."""
        agent_state = mk_agent_state(
            id="ag-test-123",
            name="Test Agent",
            system="You are Test Agent. Your persona is: A helpful testing assistant. Your expertise is in: unit testing, validation, QA. You are part of a swarm.",
            model="openai/gpt-4",
        )

        agent = SPDSAgent(agent_state, mock_letta_client)

        assert agent.persona == "A helpful testing assistant"
        assert agent.expertise == ["unit testing", "validation", "QA"]

    def test_parse_system_prompt_with_missing_info(self, mock_letta_client):
        """Test parsing system prompt with missing persona/expertise."""
        agent_state = mk_agent_state(
            id="ag-test-123",
            name="Test Agent",
            system="You are a basic agent without proper formatting.",
            model="openai/gpt-4",
        )

        agent = SPDSAgent(agent_state, mock_letta_client)

        assert agent.persona == "A helpful assistant."
        assert agent.expertise == [""]

    @patch("spds.spds_agent.config")
    def test_create_new_agent_with_default_models(self, mock_config, mock_letta_client):
        """Test creating new agent with default model configuration."""
        mock_config.DEFAULT_AGENT_MODEL = "openai/gpt-4"
        mock_config.DEFAULT_EMBEDDING_MODEL = "openai/text-embedding-ada-002"

        # Mock the client.agents.create response
        mock_agent_state = mk_agent_state(
            id="ag-new-123",
            name="New Agent",
            system="You are New Agent. Your persona is: A test agent. Your expertise is in: testing. You are part of a swarm.",
            model="openai/gpt-4",
        )
        mock_letta_client.agents.create.return_value = mock_agent_state

        agent = SPDSAgent.create_new(
            name="New Agent",
            persona="A test agent",
            expertise=["testing"],
            client=mock_letta_client,
        )

        # Verify client.agents.create was called with correct parameters
        mock_letta_client.agents.create.assert_called_once()
        call_args = mock_letta_client.agents.create.call_args

        assert call_args[1]["name"] == "New Agent"
        assert call_args[1]["model"] == "openai/gpt-4"
        assert call_args[1]["embedding"] == "openai/text-embedding-ada-002"
        assert call_args[1]["include_base_tools"] == True
        assert "You are New Agent" in call_args[1]["system"]
        assert "A test agent" in call_args[1]["system"]
        assert "testing" in call_args[1]["system"]

    @patch("spds.spds_agent.config")
    def test_create_new_agent_with_custom_models(self, mock_config, mock_letta_client):
        """Test creating new agent with custom model configuration."""
        mock_config.DEFAULT_AGENT_MODEL = "openai/gpt-4"
        mock_config.DEFAULT_EMBEDDING_MODEL = "openai/text-embedding-ada-002"

        # Mock the client.agents.create response
        mock_agent_state = mk_agent_state(
            id="ag-new-456",
            name="Custom Agent",
            system="You are Custom Agent. Your persona is: An AI assistant. Your expertise is in: analysis. You are part of a swarm.",
            model="anthropic/claude-3-5-sonnet-20241022",
        )
        mock_letta_client.agents.create.return_value = mock_agent_state

        agent = SPDSAgent.create_new(
            name="Custom Agent",
            persona="An AI assistant",
            expertise=["analysis"],
            client=mock_letta_client,
            model="anthropic/claude-3-5-sonnet-20241022",
            embedding="openai/text-embedding-ada-002",
        )

        # Verify client.agents.create was called with custom models
        call_args = mock_letta_client.agents.create.call_args
        assert call_args[1]["model"] == "anthropic/claude-3-5-sonnet-20241022"
        assert call_args[1]["embedding"] == "openai/text-embedding-ada-002"

    def test_ensure_assessment_tool_already_attached(
        self, mock_letta_client, mock_tool_state
    ):
        """Test tool attachment when tool is already present."""
        # Mock agent state with tool already attached
        agent_state = mk_agent_state(
            id="ag-test-123",
            name="Test Agent",
            system="Test system prompt",
            model="openai/gpt-4",
            tools=[mock_tool_state],
        )

        agent = SPDSAgent(agent_state, mock_letta_client)

        # Tool creation should not be called since tool is already present
        mock_letta_client.tools.create_from_function.assert_not_called()
        assert agent.assessment_tool == mock_tool_state

    def test_ensure_assessment_tool_needs_attachment(self, mock_letta_client):
        """Test tool attachment when tool is not present."""
        # Mock agent state without the tool
        agent_state = mk_agent_state(
            id="ag-test-123",
            name="Test Agent",
            system="Test system prompt",
            model="openai/gpt-4",
        )

        # Mock tool creation
        mock_tool = Tool(
            id="tool-assessment-123",
            name="perform_subjective_assessment",
            description="Assessment tool",
        )
        mock_letta_client.tools.create_from_function.return_value = mock_tool

        # Mock tool attachment
        updated_agent_state = mk_agent_state(
            id="ag-test-123",
            name="Test Agent",
            system="Test system prompt",
            model="openai/gpt-4",
            tools=[mock_tool],
        )
        mock_letta_client.agents.tools.attach.return_value = updated_agent_state

        agent = SPDSAgent(agent_state, mock_letta_client)

        # Verify tool was created and attached
        mock_letta_client.tools.create_from_function.assert_called_once()
        mock_letta_client.agents.tools.attach.assert_called_once_with(
            agent_id="ag-test-123", tool_id="tool-assessment-123"
        )
        assert agent.assessment_tool == mock_tool
        assert agent.agent == updated_agent_state

    def test_ensure_assessment_tool_attach_failure(self, mock_letta_client):
        """Ensure attach errors do not prevent tool availability."""
        agent_state = mk_agent_state(
            id="ag-test-999",
            name="Test Agent",
            system="Test system prompt",
            model="openai/gpt-4",
        )

        mock_tool = Tool(
            id="tool-assessment-999",
            name="perform_subjective_assessment",
            description="Assessment tool",
        )
        mock_letta_client.tools.create_from_function.return_value = mock_tool
        mock_letta_client.agents.tools.attach.side_effect = RuntimeError("attach failed")

        agent = SPDSAgent(agent_state, mock_letta_client)

        # Accept both new (func=) and legacy (function=, return_model=) signatures
        mock_letta_client.tools.create_from_function.assert_called_once()
        _, kwargs = mock_letta_client.tools.create_from_function.call_args
        assert kwargs.get("name") == "perform_subjective_assessment"
        assert (
            kwargs.get("description")
            == "Perform a holistic subjective assessment of the conversation"
        )
        assert (
            kwargs.get("func") == tools.perform_subjective_assessment
            or kwargs.get("function") == tools.perform_subjective_assessment
        )
        mock_letta_client.agents.tools.attach.assert_called_once_with(
            agent_id="ag-test-999", tool_id="tool-assessment-999"
        )
        assert agent.assessment_tool == mock_tool
        # Agent should remain the original state since attach failed
        assert agent.agent == agent_state

    @patch("spds.spds_agent.tools.perform_subjective_assessment")
    @patch("spds.spds_agent.track_action", Mock())
    def test_get_full_assessment_with_tool_return(
        self,
        mock_assessment_func,
        mock_letta_client,
        sample_agent_state,
        sample_assessment,
    ):
        """Test assessment when agent properly returns tool result."""
        agent = SPDSAgent(sample_agent_state, mock_letta_client)

        # Mock successful tool return in message response
        response = SimpleNamespace(
            messages=[
                SimpleNamespace(
                    id="msg-tool-123",
                    role="tool",
                    content=[
                        {
                            "type": "text",
                            "text": '{"importance_to_self": 8, "perceived_gap": 6, "unique_perspective": 7, "emotional_investment": 5, "expertise_relevance": 9, "urgency": 7, "importance_to_group": 8}',
                        }
                    ],
                )
            ]
        )
        mock_letta_client.agents.messages.create.return_value = response

        agent._get_full_assessment("test conversation", "test topic")

        assert agent.last_assessment is not None
        assert agent.last_assessment.importance_to_self == 8
        assert agent.last_assessment.expertise_relevance == 9

    @patch("spds.spds_agent.tools.perform_subjective_assessment")
    @patch("spds.spds_agent.track_action", Mock())
    def test_get_full_assessment_parses_tool_call_arguments(
        self,
        mock_assessment_func,
        mock_letta_client,
        mock_tool_state,
    ):
        """Tool call arguments should yield a structured assessment."""
        agent_state = mk_agent_state(
            id="ag-tool-parse",
            name="Tool Agent",
            system="Test system prompt",
            model="openai/gpt-4",
            tools=[mock_tool_state],
        )

        agent = SPDSAgent(agent_state, mock_letta_client)
        tool_call = SimpleNamespace(
            function=SimpleNamespace(
                name="send_message",
                arguments=json.dumps(
                    {
                        "message": "IMPORTANCE_TO_SELF: 9\nPERCEIVED_GAP: 7\nUNIQUE_PERSPECTIVE: 6\nEMOTIONAL_INVESTMENT: 5\nEXPERTISE_RELEVANCE: 8\nURGENCY: 4\nIMPORTANCE_TO_GROUP: 7"
                    }
                ),
            )
        )
        response = SimpleNamespace(messages=[SimpleNamespace(tool_calls=[tool_call], tool_return=None, content=None)])
        mock_letta_client.agents.messages.create.return_value = response

        agent._get_full_assessment("conversation", "topic")

        mock_assessment_func.assert_not_called()
        assert agent.last_assessment.importance_to_self == 9
        assert agent.last_assessment.urgency == 4
        assert agent.last_assessment.importance_to_group == 7

    @patch("spds.spds_agent.tools.perform_subjective_assessment")
    @patch("spds.spds_agent.track_action", Mock())
    def test_get_full_assessment_fallback(
        self,
        mock_assessment_func,
        mock_letta_client,
        sample_agent_state,
        sample_assessment,
    ):
        """Test assessment fallback when no tool return found."""
        agent = SPDSAgent(sample_agent_state, mock_letta_client)

        # Mock response without tool return
        response = SimpleNamespace(
            messages=[
                SimpleNamespace(
                    id="msg-regular-123",
                    role="assistant",
                    content=[{"type": "text", "text": "I'm thinking about this..."}],
                )
            ]
        )
        mock_letta_client.agents.messages.create.return_value = response
        mock_assessment_func.return_value = sample_assessment

        agent._get_full_assessment("test conversation", "test topic")

        # Should fall back to direct function call
        mock_assessment_func.assert_called_once_with(
            "test topic", "test conversation", agent.persona, agent.expertise
        )
        assert agent.last_assessment == sample_assessment

    @patch("spds.spds_agent.tools.perform_subjective_assessment")
    @patch("spds.spds_agent.track_action", Mock())
    def test_get_full_assessment_tool_call_without_scores_uses_local_fallback(
        self,
        mock_assessment_func,
        mock_letta_client,
        mock_tool_state,
        sample_assessment,
    ):
        """Blank tool-call messages trigger local subjective assessment."""
        agent_state = mk_agent_state(
            id="ag-tool-fallback",
            name="Tool Agent",
            system="Test system prompt",
            model="openai/gpt-4",
            tools=[mock_tool_state],
        )
        agent = SPDSAgent(agent_state, mock_letta_client)

        empty_tool_call = SimpleNamespace(
            function=SimpleNamespace(name="send_message", arguments=json.dumps({"message": ""}))
        )
        response = SimpleNamespace(
            messages=[
                SimpleNamespace(
                    tool_calls=[empty_tool_call],
                    tool_return=None,
                    content=None,
                )
            ]
        )
        mock_letta_client.agents.messages.create.return_value = response
        mock_assessment_func.return_value = sample_assessment

        agent._get_full_assessment("conversation", "topic")

        mock_assessment_func.assert_called_once_with(
            "topic", "conversation", agent.persona, agent.expertise
        )
        assert agent.last_assessment == sample_assessment

    @patch("spds.spds_agent.config")
    def test_assess_motivation_and_priority_above_threshold(
        self, mock_config, mock_letta_client, sample_agent_state, sample_assessment
    ):
        """Test priority calculation when motivation exceeds threshold."""
        mock_config.PARTICIPATION_THRESHOLD = 30
        mock_config.URGENCY_WEIGHT = 0.6
        mock_config.IMPORTANCE_WEIGHT = 0.4

        agent = SPDSAgent(sample_agent_state, mock_letta_client)
        agent.last_assessment = sample_assessment

        with patch.object(agent, "_get_full_assessment") as mock_assess:
            agent.assess_motivation_and_priority("test topic")

        # Calculate expected motivation score (sum of first 5 dimensions)
        expected_motivation = 8 + 6 + 7 + 5 + 9  # = 35
        assert agent.motivation_score == expected_motivation

        # Calculate expected priority score (urgency * 0.6 + importance_to_group * 0.4)
        expected_priority = 7 * 0.6 + 8 * 0.4  # = 4.2 + 3.2 = 7.4
        assert agent.priority_score == expected_priority

    @patch("spds.spds_agent.config")
    def test_assess_motivation_and_priority_below_threshold(
        self, mock_config, mock_letta_client, sample_agent_state
    ):
        """Test priority calculation when motivation is below threshold."""
        mock_config.PARTICIPATION_THRESHOLD = 50  # Higher threshold
        mock_config.URGENCY_WEIGHT = 0.6
        mock_config.IMPORTANCE_WEIGHT = 0.4

        # Create low-motivation assessment
        low_assessment = SubjectiveAssessment(
            importance_to_self=2,
            perceived_gap=1,
            unique_perspective=2,
            emotional_investment=1,
            expertise_relevance=3,
            urgency=5,
            importance_to_group=6,
        )

        agent = SPDSAgent(sample_agent_state, mock_letta_client)
        agent.last_assessment = low_assessment

        with patch.object(agent, "_get_full_assessment") as mock_assess:
            agent.assess_motivation_and_priority("test topic")

        expected_motivation = 2 + 1 + 2 + 1 + 3  # = 9 (below threshold of 50)
        assert agent.motivation_score == expected_motivation
        assert agent.priority_score == 0  # Should be 0 when below threshold

    def test_speak_method(
        self, mock_letta_client, sample_agent_state, mock_message_response
    ):
        """Test the speak method."""
        agent = SPDSAgent(sample_agent_state, mock_letta_client)
        mock_letta_client.agents.messages.create.return_value = mock_message_response

        conversation_history = "Previous conversation content"
        response = agent.speak(conversation_history)

        # Verify correct API call
        mock_letta_client.agents.messages.create.assert_called_once_with(
            agent_id="ag-test-123",
            messages=[
                {
                    "role": "user",
                    "content": f"{conversation_history}\nBased on my assessment, here is my contribution:",
                }
            ],
        )
        assert response == mock_message_response

    def test_speak_with_tools_history_prompt(
        self, mock_letta_client, mock_tool_state
    ):
        """History prompts should mention send_message when tools are present."""
        agent_state = mk_agent_state(
            id="ag-history",
            name="History Agent",
            system="You are History Agent. Your persona is: Recorder. Your expertise is in: testing.",
            model="openai/gpt-4",
            tools=[mock_tool_state],
        )

        agent = SPDSAgent(agent_state, mock_letta_client)
        mock_letta_client.agents.messages.create.return_value = SimpleNamespace(messages=[])

        history = "Line 1\nLine 2"
        agent.speak(history, mode="initial", topic="Topic")

        sent_prompt = mock_letta_client.agents.messages.create.call_args[1]["messages"][0][
            "content"
        ]
        expected_prompt = f"""{history}

Based on this conversation, I want to contribute. Please use the send_message tool to share your response. Remember to call the send_message function with your response as the message parameter."""
        assert sent_prompt == expected_prompt

    def test_speak_with_tools_topic_prompts(
        self, mock_letta_client, mock_tool_state
    ):
        """Initial and response prompts should change with mode when tools are attached."""
        agent_state = mk_agent_state(
            id="ag-topic",
            name="Topic Agent",
            system="You are Topic Agent. Your persona is: Analyst. Your expertise is in: testing.",
            model="openai/gpt-4",
            tools=[mock_tool_state],
        )

        agent = SPDSAgent(agent_state, mock_letta_client)
        mock_letta_client.agents.messages.create.return_value = SimpleNamespace(messages=[])

        agent.speak("", mode="initial", topic="Topic")
        initial_prompt = mock_letta_client.agents.messages.create.call_args[1]["messages"][
            0
        ]["content"]
        expected_initial = (
            "Based on my assessment of the topic 'Topic', I want to share my initial thoughts and "
            "perspective. Please use the send_message tool to contribute your viewpoint to this "
            "discussion. Remember to call the send_message function with your response as the "
            "message parameter."
        )
        assert initial_prompt == expected_initial

        mock_letta_client.agents.messages.create.reset_mock()

        agent.speak("", mode="response", topic="Topic")
        response_prompt = mock_letta_client.agents.messages.create.call_args[1]["messages"][
            0
        ]["content"]
        expected_response = (
            "Based on what everyone has shared about 'Topic', I'd like to respond to the discussion. "
            "Please use the send_message tool to share your response, building on or reacting to what "
            "others have said. Remember to call the send_message function with your response as the "
            "message parameter."
        )
        assert response_prompt == expected_response

    def test_speak_without_tools_topic_prompts(self, mock_letta_client):
        """Without tools, prompts should omit tool instructions."""
        agent_state = mk_agent_state(
            id="ag-no-tools",
            name="Topic Agent",
            system="You are Topic Agent. Your persona is: Analyst. Your expertise is in: testing.",
            model="openai/gpt-4",
        )

        agent = SPDSAgent(agent_state, mock_letta_client)
        mock_letta_client.agents.messages.create.return_value = SimpleNamespace(messages=[])

        agent.speak("", mode="initial", topic="Topic")
        initial_prompt = mock_letta_client.agents.messages.create.call_args[1]["messages"][
            0
        ]["content"]
        assert (
            initial_prompt
            == "Based on my assessment of 'Topic', here is my initial contribution:"
        )

        mock_letta_client.agents.messages.create.reset_mock()

        agent.speak("", mode="response", topic="Topic")
        response_prompt = mock_letta_client.agents.messages.create.call_args[1]["messages"][
            0
        ]["content"]
        assert (
            response_prompt
            == "Based on the discussion about 'Topic', here is my response:"
        )

    def test_agent_string_representation(self, mock_letta_client, sample_agent_state):
        """Test that agent can be represented as string."""
        agent = SPDSAgent(sample_agent_state, mock_letta_client)

        # Should not raise an error
        str_repr = str(agent)
        assert "Test Agent" in str_repr or "SPDSAgent" in str_repr
