"""
Shared pytest fixtures and configuration for SPDS tests.
"""

from types import SimpleNamespace
from unittest.mock import MagicMock, Mock

import pytest
from letta_client.types import (
    AgentState,
    EmbeddingConfig,
    LettaResponse,
    LlmConfig,
    Memory,
    Message,
    Tool,
    ToolReturnMessage,
)

from spds.tools import SubjectiveAssessment


@pytest.fixture
def mock_letta_client():
    """Mock Letta client for testing without server dependency."""
    client = Mock()

    # Mock agent operations
    client.agents = Mock()
    client.agents.create = Mock()
    client.agents.retrieve = Mock()
    client.agents.list = Mock()
    client.agents.messages = Mock()
    client.agents.messages.create = Mock()
    client.agents.tools = Mock()
    client.agents.tools.attach = Mock()

    # Mock tool operations
    client.tools = Mock()
    client.tools.create_from_function = Mock()

    return client


def _mk_agent_state(id: str, name: str, system: str, model: str = "openai/gpt-4"):
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
        tools=[],
        sources=[],
        tags=[],
        model=model,
        embedding="openai/text-embedding-ada-002",
    )


@pytest.fixture
def sample_agent_state():
    """Sample AgentState for testing."""
    return _mk_agent_state(
        id="ag-test-123",
        name="Test Agent",
        system=(
            "You are Test Agent. Your persona is: A test agent for unit testing. "
            "Your expertise is in: testing, validation."
        ),
        model="openai/gpt-4",
    )


@pytest.fixture
def sample_agent_profiles():
    """Sample agent profiles for testing."""
    return [
        {
            "name": "Test Agent 1",
            "persona": "A test agent for validation",
            "expertise": ["testing", "validation"],
            "model": "openai/gpt-4",
            "embedding": "openai/text-embedding-ada-002",
        },
        {
            "name": "Test Agent 2",
            "persona": "Another test agent",
            "expertise": ["analysis", "reporting"],
            "model": "anthropic/claude-3-5-sonnet-20241022",
            "embedding": "openai/text-embedding-ada-002",
        },
    ]


@pytest.fixture
def sample_conversation_history():
    """Sample conversation history for testing."""
    return """System: The topic is 'Testing Strategy'.
You: What should our testing approach be?
Agent1: I think we need comprehensive unit tests.
Agent2: We should also consider integration testing."""


@pytest.fixture
def sample_assessment():
    """Sample SubjectiveAssessment for testing."""
    return SubjectiveAssessment(
        importance_to_self=8,
        perceived_gap=6,
        unique_perspective=7,
        emotional_investment=5,
        expertise_relevance=9,
        urgency=7,
        importance_to_group=8,
    )


@pytest.fixture
def mock_tool_state():
    """Mock Tool for testing."""
    return Tool(
        id="tool-test-123",
        name="perform_subjective_assessment",
        description="Test tool",
    )


@pytest.fixture
def mock_message_response():
    """Mock response with assistant text message."""
    return SimpleNamespace(
        messages=[
            SimpleNamespace(
                id="msg-test-123",
                role="assistant",
                content=[{"type": "text", "text": "Test response"}],
            )
        ]
    )


@pytest.fixture(autouse=True)
def set_ephemeral_agents_env(monkeypatch):
    """Set SPDS_ALLOW_EPHEMERAL_AGENTS to 'true' for all tests."""
    monkeypatch.setenv("SPDS_ALLOW_EPHEMERAL_AGENTS", "true")
