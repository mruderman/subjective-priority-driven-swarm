"""
Shared pytest fixtures and configuration for SPDS tests.
"""
import pytest
from unittest.mock import Mock, MagicMock
from letta_client.types import AgentState, Tool, LettaResponse, Message, ToolReturnMessage
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

@pytest.fixture
def sample_agent_state():
    """Sample AgentState for testing."""
    return AgentState(
        id="ag-test-123",
        name="Test Agent",
        system="You are Test Agent. Your persona is: A test agent for unit testing. Your expertise is in: testing, validation.",
        model="openai/gpt-4",
        embedding="openai/text-embedding-ada-002",
        tools=[],
        memory={}
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
            "embedding": "openai/text-embedding-ada-002"
        },
        {
            "name": "Test Agent 2", 
            "persona": "Another test agent",
            "expertise": ["analysis", "reporting"],
            "model": "anthropic/claude-3-5-sonnet-20241022",
            "embedding": "openai/text-embedding-ada-002"
        }
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
        importance_to_group=8
    )

@pytest.fixture
def mock_tool_state():
    """Mock Tool for testing."""
    return Tool(
        id="tool-test-123",
        name="perform_subjective_assessment",
        description="Test tool"
    )

@pytest.fixture
def mock_message_response():
    """Mock LettaResponse for testing."""
    message = Message(
        id="msg-test-123",
        content="Test response",
        role="assistant"
    )
    return LettaResponse(messages=[message])