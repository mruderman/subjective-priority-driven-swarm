"""
Unit tests for spds.swarm_manager module.
"""
import pytest
from unittest.mock import Mock, patch, MagicMock, call
from io import StringIO
import sys

from letta_client.types import AgentState, LettaResponse, Message
from letta_client.errors import NotFoundError

from spds.swarm_manager import SwarmManager
from spds.spds_agent import SPDSAgent


class TestSwarmManager:
    """Test the SwarmManager class."""
    
    def test_init_with_agent_profiles(self, mock_letta_client, sample_agent_profiles):
        """Test SwarmManager initialization with agent profiles."""
        with patch('spds.swarm_manager.SPDSAgent.create_new') as mock_create:
            # Mock created agents
            mock_agent1 = Mock(spec=SPDSAgent)
            mock_agent1.name = "Test Agent 1"
            mock_agent2 = Mock(spec=SPDSAgent)
            mock_agent2.name = "Test Agent 2"
            mock_create.side_effect = [mock_agent1, mock_agent2]
            
            manager = SwarmManager(
                client=mock_letta_client,
                agent_profiles=sample_agent_profiles
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
                    embedding="openai/text-embedding-ada-002"
                ),
                call(
                    name="Test Agent 2",
                    persona="Another test agent",
                    expertise=["analysis", "reporting"],
                    client=mock_letta_client,
                    model="anthropic/claude-3-5-sonnet-20241022",
                    embedding="openai/text-embedding-ada-002"
                )
            ]
            mock_create.assert_has_calls(expected_calls)
    
    def test_init_with_agent_ids(self, mock_letta_client):
        """Test SwarmManager initialization with agent IDs."""
        agent_ids = ["ag-123", "ag-456"]
        
        # Mock agent states
        mock_agent_state1 = AgentState(
            id="ag-123", name="Agent 1", system="Test", model="gpt-4", 
            embedding="ada", tools=[], memory={}
        )
        mock_agent_state2 = AgentState(
            id="ag-456", name="Agent 2", system="Test", model="gpt-4",
            embedding="ada", tools=[], memory={}
        )
        
        mock_letta_client.agents.retrieve.side_effect = [mock_agent_state1, mock_agent_state2]
        
        with patch('spds.swarm_manager.SPDSAgent') as mock_spds_agent:
            mock_agent1 = Mock()
            mock_agent2 = Mock()
            mock_spds_agent.side_effect = [mock_agent1, mock_agent2]
            
            manager = SwarmManager(
                client=mock_letta_client,
                agent_ids=agent_ids
            )
            
            assert len(manager.agents) == 2
            mock_letta_client.agents.retrieve.assert_has_calls([
                call(agent_id="ag-123"),
                call(agent_id="ag-456")
            ])
    
    def test_init_with_agent_names(self, mock_letta_client):
        """Test SwarmManager initialization with agent names."""
        agent_names = ["Agent One", "Agent Two"]
        
        # Mock agent states
        mock_agent_state1 = AgentState(
            id="ag-123", name="Agent One", system="Test", model="gpt-4",
            embedding="ada", tools=[], memory={}
        )
        mock_agent_state2 = AgentState(
            id="ag-456", name="Agent Two", system="Test", model="gpt-4",
            embedding="ada", tools=[], memory={}
        )
        
        mock_letta_client.agents.list.side_effect = [
            [mock_agent_state1],  # First call returns Agent One
            [mock_agent_state2]   # Second call returns Agent Two
        ]
        
        with patch('spds.swarm_manager.SPDSAgent') as mock_spds_agent:
            mock_agent1 = Mock()
            mock_agent2 = Mock()
            mock_spds_agent.side_effect = [mock_agent1, mock_agent2]
            
            manager = SwarmManager(
                client=mock_letta_client,
                agent_names=agent_names
            )
            
            assert len(manager.agents) == 2
            mock_letta_client.agents.list.assert_has_calls([
                call(name="Agent One", limit=1),
                call(name="Agent Two", limit=1)
            ])
    
    def test_init_with_no_agents_raises_error(self, mock_letta_client):
        """Test that initializing with no agents raises ValueError."""
        with pytest.raises(ValueError, match="Swarm manager initialized with no agents"):
            SwarmManager(client=mock_letta_client)
    
    def test_load_agents_by_id_with_missing_agent(self, mock_letta_client):
        """Test loading agents by ID when some agents are not found."""
        agent_ids = ["ag-123", "ag-missing", "ag-456"]
        
        # Mock retrieval with one NotFoundError
        mock_agent_state1 = AgentState(
            id="ag-123", name="Agent 1", system="Test", model="gpt-4",
            embedding="ada", tools=[], memory={}
        )
        mock_agent_state3 = AgentState(
            id="ag-456", name="Agent 3", system="Test", model="gpt-4",
            embedding="ada", tools=[], memory={}
        )
        
        def mock_retrieve(agent_id):
            if agent_id == "ag-missing":
                raise NotFoundError("Agent not found")
            elif agent_id == "ag-123":
                return mock_agent_state1
            elif agent_id == "ag-456":
                return mock_agent_state3
        
        mock_letta_client.agents.retrieve.side_effect = mock_retrieve
        
        with patch('spds.swarm_manager.SPDSAgent') as mock_spds_agent:
            mock_agent1 = Mock()
            mock_agent3 = Mock()
            mock_spds_agent.side_effect = [mock_agent1, mock_agent3]
            
            # Capture stdout to check warning message
            captured_output = StringIO()
            sys.stdout = captured_output
            
            manager = SwarmManager(
                client=mock_letta_client,
                agent_ids=agent_ids
            )
            
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
        mock_agent_state1 = AgentState(
            id="ag-123", name="Agent One", system="Test", model="gpt-4",
            embedding="ada", tools=[], memory={}
        )
        mock_agent_state3 = AgentState(
            id="ag-456", name="Agent Three", system="Test", model="gpt-4",
            embedding="ada", tools=[], memory={}
        )
        
        def mock_list(name, limit):
            if name == "Missing Agent":
                return []  # Empty list means not found
            elif name == "Agent One":
                return [mock_agent_state1]
            elif name == "Agent Three":
                return [mock_agent_state3]
        
        mock_letta_client.agents.list.side_effect = mock_list
        
        with patch('spds.swarm_manager.SPDSAgent') as mock_spds_agent:
            mock_agent1 = Mock()
            mock_agent3 = Mock()
            mock_spds_agent.side_effect = [mock_agent1, mock_agent3]
            
            # Capture stdout to check warning message
            captured_output = StringIO()
            sys.stdout = captured_output
            
            manager = SwarmManager(
                client=mock_letta_client,
                agent_names=agent_names
            )
            
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
                "embedding": "openai/text-embedding-ada-002"
            },
            {
                "name": "Claude Agent", 
                "persona": "An Anthropic agent",
                "expertise": ["reasoning"],
                "model": "anthropic/claude-3-5-sonnet-20241022",
                "embedding": "openai/text-embedding-ada-002"
            }
        ]
        
        with patch('spds.swarm_manager.SPDSAgent.create_new') as mock_create:
            mock_agent1 = Mock()
            mock_agent2 = Mock()
            mock_create.side_effect = [mock_agent1, mock_agent2]
            
            manager = SwarmManager(
                client=mock_letta_client,
                agent_profiles=profiles
            )
            
            # Verify agents were created with model-specific parameters
            expected_calls = [
                call(
                    name="GPT Agent",
                    persona="An OpenAI agent",
                    expertise=["analysis"],
                    client=mock_letta_client,
                    model="openai/gpt-4",
                    embedding="openai/text-embedding-ada-002"
                ),
                call(
                    name="Claude Agent",
                    persona="An Anthropic agent",
                    expertise=["reasoning"],
                    client=mock_letta_client,
                    model="anthropic/claude-3-5-sonnet-20241022",
                    embedding="openai/text-embedding-ada-002"
                )
            ]
            mock_create.assert_has_calls(expected_calls)
    
    def test_agent_turn_with_motivated_agents(self, mock_letta_client, sample_agent_profiles):
        """Test agent turn when agents are motivated to speak."""
        with patch('spds.swarm_manager.SPDSAgent.create_new') as mock_create:
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
            mock_message = Message(
                id="msg-123",
                content="This is my response",
                role="assistant"
            )
            mock_response = LettaResponse(messages=[mock_message])
            mock_agent2.speak.return_value = mock_response
            
            mock_create.side_effect = [mock_agent1, mock_agent2]
            
            manager = SwarmManager(
                client=mock_letta_client,
                agent_profiles=sample_agent_profiles
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
    
    def test_agent_turn_with_no_motivated_agents(self, mock_letta_client, sample_agent_profiles):
        """Test agent turn when no agents are motivated to speak."""
        with patch('spds.swarm_manager.SPDSAgent.create_new') as mock_create:
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
                client=mock_letta_client,
                agent_profiles=sample_agent_profiles
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
    
    def test_agent_turn_with_speak_error(self, mock_letta_client, sample_agent_profiles):
        """Test agent turn when speaking agent encounters an error."""
        with patch('spds.swarm_manager.SPDSAgent.create_new') as mock_create:
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
                agent_profiles=[sample_agent_profiles[0]]  # Just one agent
            )
            
            # Capture output
            captured_output = StringIO()
            sys.stdout = captured_output
            
            manager._agent_turn("Test Topic")
            
            sys.stdout = sys.__stdout__
            output = captured_output.getvalue()
            
            # Should handle the error gracefully
            assert "Error Agent: I have some thoughts but I'm having trouble phrasing them." in output
            assert "[Debug: Error during speak() - API Error]" in output
    
    @patch('builtins.input')
    def test_start_chat_basic_flow(self, mock_input, mock_letta_client, sample_agent_profiles):
        """Test basic chat flow with user input."""
        # Mock user inputs: topic, one message, then quit
        mock_input.side_effect = ["Testing Discussion", "Let's talk about testing", "quit"]
        
        with patch('spds.swarm_manager.SPDSAgent.create_new') as mock_create:
            mock_agent = Mock(spec=SPDSAgent)
            mock_agent.name = "Test Agent"
            mock_agent.priority_score = 30.0
            mock_agent.motivation_score = 50
            mock_agent.assess_motivation_and_priority = Mock()
            
            # Mock successful speak
            mock_message = Message(
                id="msg-123",
                content="Great point about testing!",
                role="assistant"
            )
            mock_response = LettaResponse(messages=[mock_message])
            mock_agent.speak.return_value = mock_response
            
            mock_create.return_value = mock_agent
            
            manager = SwarmManager(
                client=mock_letta_client,
                agent_profiles=[sample_agent_profiles[0]]
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
    
    @patch('builtins.input')
    def test_start_chat_eof_handling(self, mock_input, mock_letta_client, sample_agent_profiles):
        """Test chat handling of EOF (Ctrl+D)."""
        # Mock EOFError on topic input
        mock_input.side_effect = EOFError()
        
        with patch('spds.swarm_manager.SPDSAgent.create_new') as mock_create:
            mock_agent = Mock()
            mock_create.return_value = mock_agent
            
            manager = SwarmManager(
                client=mock_letta_client,
                agent_profiles=[sample_agent_profiles[0]]
            )
            
            # Capture output
            captured_output = StringIO()
            sys.stdout = captured_output
            
            manager.start_chat()
            
            sys.stdout = sys.__stdout__
            output = captured_output.getvalue()
            
            # Should handle EOF gracefully
            assert "Exiting" in output