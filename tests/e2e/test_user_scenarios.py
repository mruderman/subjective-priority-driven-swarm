"""
End-to-end tests for complete user scenarios with mocked Letta server.
These tests simulate full user workflows from start to finish.
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
import json
from io import StringIO
import sys

from spds.main import main
from spds.swarm_manager import SwarmManager
from letta_client import Letta
from letta_client.types import AgentState, LettaResponse, Message, Tool


class TestE2EUserScenarios:
    """End-to-end tests for complete user scenarios."""
    
    @pytest.fixture
    def mock_letta_environment(self):
        """Mock complete Letta environment for E2E testing."""
        with patch('spds.config.LETTA_BASE_URL', 'http://localhost:8283'), \
             patch('spds.config.LETTA_API_KEY', 'test-key'), \
             patch('spds.config.LETTA_SERVER_PASSWORD', 'test-password'):
            yield
    
    @pytest.fixture
    def mock_letta_client_full(self):
        """Full mock of Letta client with all necessary methods."""
        client = Mock(spec=Letta)
        
        # Mock agents operations
        client.agents = Mock()
        client.agents.create = Mock()
        client.agents.retrieve = Mock()
        client.agents.list = Mock()
        client.agents.messages = Mock()
        client.agents.messages.create = Mock()
        client.agents.tools = Mock()
        client.agents.tools.attach = Mock()
        
        # Mock tools operations
        client.tools = Mock()
        client.tools.create_from_function = Mock()
        
        return client
    
    @pytest.fixture
    def sample_e2e_agent_states(self):
        """Sample agent states for E2E testing."""
        return [
            AgentState(
                id="ag-e2e-001",
                name="E2E Agent 1",
                system="You are E2E Agent 1. Your persona is: A project manager focused on planning. Your expertise is in: project management, planning, coordination.",
                model="openai/gpt-4",
                embedding="openai/text-embedding-ada-002",
                tools=[],
                memory={}
            ),
            AgentState(
                id="ag-e2e-002", 
                name="E2E Agent 2",
                system="You are E2E Agent 2. Your persona is: A technical developer focused on implementation. Your expertise is in: software development, architecture, debugging.",
                model="anthropic/claude-3-5-sonnet-20241022",
                embedding="openai/text-embedding-ada-002",
                tools=[],
                memory={}
            )
        ]
    
    @patch('spds.main.Letta')
    @patch('builtins.input')
    def test_ephemeral_swarm_conversation_scenario(self, mock_input, mock_letta_class, mock_letta_environment):
        """Test complete scenario: user runs ephemeral swarm and has conversation."""
        # Mock user inputs: topic, one message, then quit
        mock_input.side_effect = [
            "Project Planning Discussion",  # Topic
            "What should be our first priority for the new project?",  # User message
            "quit"  # Exit
        ]
        
        # Mock Letta client
        mock_client = Mock(spec=Letta)
        mock_letta_class.return_value = mock_client
        
        # Mock agent creation responses
        agent_states = [
            AgentState(
                id="ag-temp-001",
                name="Alex",
                system="You are Alex. Your persona is: A pragmatic project manager. Your expertise is in: risk management, scheduling, budgeting.",
                model="openai/gpt-4",
                embedding="openai/text-embedding-ada-002",
                tools=[],
                memory={}
            ),
            AgentState(
                id="ag-temp-002",
                name="Jordan", 
                system="You are Jordan. Your persona is: A creative designer. Your expertise is in: UX/UI design, user research, prototyping.",
                model="anthropic/claude-3-5-sonnet-20241022",
                embedding="openai/text-embedding-ada-002",
                tools=[],
                memory={}
            )
        ]
        
        mock_client.agents.create.side_effect = agent_states
        
        # Mock tool creation and attachment
        mock_tool = Tool(
            id="tool-assessment-001",
            name="perform_subjective_assessment",
            description="Assessment tool"
        )
        mock_client.tools.create_from_function.return_value = mock_tool
        mock_client.agents.tools.attach.side_effect = agent_states  # Return updated agents
        
        # Mock assessment tool responses (via agent messages)
        assessment_responses = [
            LettaResponse(messages=[
                Message(
                    id="msg-assess-001",
                    content=[],
                    message_type="tool_return_message",
                    tool_return='{"importance_to_self": 8, "perceived_gap": 7, "unique_perspective": 6, "emotional_investment": 5, "expertise_relevance": 9, "urgency": 7, "importance_to_group": 8}'
                )
            ]),
            LettaResponse(messages=[
                Message(
                    id="msg-assess-002", 
                    content=[],
                    message_type="tool_return_message",
                    tool_return='{"importance_to_self": 6, "perceived_gap": 5, "unique_perspective": 8, "emotional_investment": 4, "expertise_relevance": 6, "urgency": 5, "importance_to_group": 7}'
                )
            ])
        ]
        
        # Mock speaking responses
        speak_response = LettaResponse(messages=[
            Message(
                id="msg-speak-001",
                content=[{"type": "text", "text": "I think we should start with a thorough risk assessment and create a detailed project timeline."}],
                message_type="assistant_message"
            )
        ])
        
        # Set up mock responses in order
        mock_client.agents.messages.create.side_effect = [
            assessment_responses[0],  # Alex assessment
            assessment_responses[1],  # Jordan assessment  
            speak_response            # Alex speaking
        ]
        
        # Capture output
        captured_output = StringIO()
        sys.stdout = captured_output
        
        # Run main function with no arguments (ephemeral mode)
        main([])
        
        sys.stdout = sys.__stdout__
        output = captured_output.getvalue()
        
        # Verify expected workflow occurred
        assert "Creating swarm from temporary agent profiles" in output
        assert "Creating agent: Alex" in output
        assert "Creating agent: Jordan" in output
        assert "Swarm chat started" in output
        assert "Project Planning Discussion" in output
        assert "Assessing agent motivations" in output
        assert "Alex: I think we should start with a thorough risk assessment" in output
        assert "Exiting chat" in output
        
        # Verify API calls
        assert mock_client.agents.create.call_count == 2
        assert mock_client.tools.create_from_function.call_count == 2
        assert mock_client.agents.tools.attach.call_count == 2
    
    @patch('spds.main.Letta')
    @patch('builtins.input')
    def test_existing_agents_by_id_scenario(self, mock_input, mock_letta_class, mock_letta_environment, sample_e2e_agent_states):
        """Test scenario: user loads existing agents by ID and has conversation."""
        mock_input.side_effect = [
            "Technical Architecture Review",
            "How should we structure our microservices?",
            "quit"
        ]
        
        # Mock Letta client
        mock_client = Mock(spec=Letta)
        mock_letta_class.return_value = mock_client
        
        # Mock retrieving existing agents
        mock_client.agents.retrieve.side_effect = sample_e2e_agent_states
        
        # Mock tool attachment for existing agents
        mock_tool = Tool(
            id="tool-existing-001",
            name="perform_subjective_assessment", 
            description="Assessment tool"
        )
        mock_client.tools.create_from_function.return_value = mock_tool
        
        # Update agent states to include the tool
        updated_states = []
        for state in sample_e2e_agent_states:
            updated_state = AgentState(
                id=state.id,
                name=state.name,
                system=state.system,
                model=state.model,
                embedding=state.embedding,
                tools=[mock_tool],
                memory=state.memory
            )
            updated_states.append(updated_state)
        
        mock_client.agents.tools.attach.side_effect = updated_states
        
        # Mock assessment and speaking responses
        assessment_response = LettaResponse(messages=[
            Message(
                id="msg-assess-tech",
                content=[],
                message_type="tool_return_message",
                tool_return='{"importance_to_self": 9, "perceived_gap": 8, "unique_perspective": 7, "emotional_investment": 6, "expertise_relevance": 10, "urgency": 8, "importance_to_group": 9}'
            )
        ])
        
        speak_response = LettaResponse(messages=[
            Message(
                id="msg-speak-tech",
                content=[{"type": "text", "text": "For microservices architecture, I recommend starting with domain-driven design principles to identify service boundaries."}],
                message_type="assistant_message"
            )
        ])
        
        mock_client.agents.messages.create.side_effect = [
            assessment_response,  # Agent 1 assessment
            assessment_response,  # Agent 2 assessment
            speak_response        # Agent 2 speaking (higher priority)
        ]
        
        # Capture output
        captured_output = StringIO()
        sys.stdout = captured_output
        
        # Run main with agent IDs
        main(['--agent-ids', 'ag-e2e-001', 'ag-e2e-002'])
        
        sys.stdout = sys.__stdout__
        output = captured_output.getvalue()
        
        # Verify workflow
        assert "Loading swarm from existing agent IDs" in output
        assert "Retrieving agent: ag-e2e-001" in output
        assert "Retrieving agent: ag-e2e-002" in output
        assert "Technical Architecture Review" in output
        assert "E2E Agent 2: For microservices architecture, I recommend" in output
        
        # Verify correct API calls
        mock_client.agents.retrieve.assert_any_call(agent_id="ag-e2e-001")
        mock_client.agents.retrieve.assert_any_call(agent_id="ag-e2e-002")
    
    @patch('spds.main.Letta')
    @patch('builtins.input')
    def test_existing_agents_by_name_scenario(self, mock_input, mock_letta_class, mock_letta_environment, sample_e2e_agent_states):
        """Test scenario: user loads existing agents by name."""
        mock_input.side_effect = [
            "Team Collaboration",
            "How can we improve our development workflow?",
            "quit"
        ]
        
        # Mock Letta client
        mock_client = Mock(spec=Letta)
        mock_letta_class.return_value = mock_client
        
        # Mock finding agents by name
        mock_client.agents.list.side_effect = [
            [sample_e2e_agent_states[0]],  # Find first agent
            [sample_e2e_agent_states[1]]   # Find second agent
        ]
        
        # Mock tool setup and responses (similar to previous test)
        mock_tool = Tool(
            id="tool-name-001",
            name="perform_subjective_assessment",
            description="Assessment tool"
        )
        mock_client.tools.create_from_function.return_value = mock_tool
        
        updated_states = []
        for state in sample_e2e_agent_states:
            updated_state = AgentState(
                id=state.id,
                name=state.name,
                system=state.system,
                model=state.model,
                embedding=state.embedding,
                tools=[mock_tool],
                memory=state.memory
            )
            updated_states.append(updated_state)
        
        mock_client.agents.tools.attach.side_effect = updated_states
        
        # Mock responses
        assessment_response = LettaResponse(messages=[
            Message(
                id="msg-workflow",
                content=[],
                message_type="tool_return_message", 
                tool_return='{"importance_to_self": 7, "perceived_gap": 6, "unique_perspective": 8, "emotional_investment": 5, "expertise_relevance": 8, "urgency": 6, "importance_to_group": 8}'
            )
        ])
        
        speak_response = LettaResponse(messages=[
            Message(
                id="msg-workflow-speak",
                content=[{"type": "text", "text": "I suggest we implement continuous integration and establish clear code review processes."}],
                message_type="assistant_message"
            )
        ])
        
        mock_client.agents.messages.create.side_effect = [
            assessment_response, assessment_response, speak_response
        ]
        
        # Capture output
        captured_output = StringIO()
        sys.stdout = captured_output
        
        # Run main with agent names
        main(['--agent-names', 'E2E Agent 1', 'E2E Agent 2'])
        
        sys.stdout = sys.__stdout__
        output = captured_output.getvalue()
        
        # Verify workflow
        assert "Loading swarm from existing agent names" in output
        assert "Retrieving agent by name: E2E Agent 1" in output
        assert "Retrieving agent by name: E2E Agent 2" in output
        assert "Team Collaboration" in output
        assert "continuous integration" in output
        
        # Verify API calls
        mock_client.agents.list.assert_any_call(name="E2E Agent 1", limit=1)
        mock_client.agents.list.assert_any_call(name="E2E Agent 2", limit=1)
    
    @patch('spds.main.Letta')
    @patch('builtins.input')
    def test_custom_swarm_config_scenario(self, mock_input, mock_letta_class, mock_letta_environment):
        """Test scenario: user runs with custom swarm configuration file."""
        mock_input.side_effect = [
            "Creative Brainstorming",
            "What innovative features should we consider?",
            "quit"
        ]
        
        # Mock Letta client
        mock_client = Mock(spec=Letta)
        mock_letta_class.return_value = mock_client
        
        # Mock agent creation for creative swarm
        creative_agent_states = [
            AgentState(
                id="ag-creative-001",
                name="Innovator Sam",
                system="You are Innovator Sam. Your persona is: A creative thinker who challenges conventional approaches. Your expertise is in: innovation, brainstorming, lateral thinking, design thinking.",
                model="anthropic/claude-3-5-sonnet-20241022",
                embedding="openai/text-embedding-ada-002",
                tools=[],
                memory={}
            ),
            AgentState(
                id="ag-creative-002",
                name="Analyst Riley",
                system="You are Analyst Riley. Your persona is: A data-driven decision maker. Your expertise is in: data analysis, metrics, ROI calculation, statistical analysis.",
                model="openai/gpt-4", 
                embedding="openai/text-embedding-ada-002",
                tools=[],
                memory={}
            )
        ]
        
        mock_client.agents.create.side_effect = creative_agent_states
        
        # Mock tool setup
        mock_tool = Tool(
            id="tool-creative-001",
            name="perform_subjective_assessment",
            description="Assessment tool"
        )
        mock_client.tools.create_from_function.return_value = mock_tool
        mock_client.agents.tools.attach.side_effect = creative_agent_states
        
        # Mock creative responses
        creative_assessment = LettaResponse(messages=[
            Message(
                id="msg-creative-assess",
                content=[],
                message_type="tool_return_message",
                tool_return='{"importance_to_self": 9, "perceived_gap": 8, "unique_perspective": 10, "emotional_investment": 8, "expertise_relevance": 9, "urgency": 7, "importance_to_group": 8}'
            )
        ])
        
        analytical_assessment = LettaResponse(messages=[
            Message(
                id="msg-analytical-assess", 
                content=[],
                message_type="tool_return_message",
                tool_return='{"importance_to_self": 6, "perceived_gap": 7, "unique_perspective": 5, "emotional_investment": 4, "expertise_relevance": 7, "urgency": 5, "importance_to_group": 7}'
            )
        ])
        
        creative_speak = LettaResponse(messages=[
            Message(
                id="msg-creative-speak",
                content=[{"type": "text", "text": "What if we reimagined the entire user experience? I'm thinking about AI-powered personalization that adapts in real-time to user behavior patterns."}],
                message_type="assistant_message"
            )
        ])
        
        mock_client.agents.messages.create.side_effect = [
            creative_assessment, analytical_assessment, creative_speak
        ]
        
        # Capture output
        captured_output = StringIO()
        sys.stdout = captured_output
        
        # Run main with custom swarm config
        main(['--swarm-config', 'creative_swarm.json'])
        
        sys.stdout = sys.__stdout__
        output = captured_output.getvalue()
        
        # Verify workflow
        assert "Creating swarm from temporary agent profiles" in output
        assert "Creating agent: Innovator Sam" in output
        assert "Creating agent: Analyst Riley" in output
        assert "Creative Brainstorming" in output
        assert "AI-powered personalization" in output
        
        # Verify diverse models were used in agent creation
        create_calls = mock_client.agents.create.call_args_list
        models_used = [call[1]['model'] for call in create_calls]
        assert "anthropic/claude-3-5-sonnet-20241022" in models_used
        assert "openai/gpt-4" in models_used
    
    @patch('spds.main.Letta')
    @patch('builtins.input')
    def test_error_handling_scenario(self, mock_input, mock_letta_class, mock_letta_environment):
        """Test scenario: handling errors gracefully during conversation."""
        mock_input.side_effect = [
            "Error Testing",
            "Let's test error handling",
            "quit"
        ]
        
        # Mock Letta client with error conditions
        mock_client = Mock(spec=Letta)
        mock_letta_class.return_value = mock_client
        
        # Mock successful agent creation
        agent_state = AgentState(
            id="ag-error-001",
            name="Error Test Agent",
            system="You are Error Test Agent. Your persona is: A test agent. Your expertise is in: testing.",
            model="openai/gpt-4",
            embedding="openai/text-embedding-ada-002", 
            tools=[],
            memory={}
        )
        mock_client.agents.create.return_value = agent_state
        
        # Mock tool setup
        mock_tool = Tool(
            id="tool-error-001",
            name="perform_subjective_assessment",
            description="Assessment tool"
        )
        mock_client.tools.create_from_function.return_value = mock_tool
        mock_client.agents.tools.attach.return_value = agent_state
        
        # Mock assessment success but speaking failure
        assessment_response = LettaResponse(messages=[
            Message(
                id="msg-error-assess",
                content=[],
                message_type="tool_return_message",
                tool_return='{"importance_to_self": 8, "perceived_gap": 7, "unique_perspective": 6, "emotional_investment": 5, "expertise_relevance": 8, "urgency": 6, "importance_to_group": 7}'
            )
        ])
        
        # First call succeeds (assessment), second call fails (speaking)
        mock_client.agents.messages.create.side_effect = [
            assessment_response,
            Exception("Network error during speaking")
        ]
        
        # Capture output
        captured_output = StringIO()
        sys.stdout = captured_output
        
        # Run main (should handle error gracefully)
        main([])
        
        sys.stdout = sys.__stdout__
        output = captured_output.getvalue()
        
        # Verify error was handled gracefully
        assert "Error Testing" in output
        assert "Assessing agent motivations" in output
        assert ("Error Test Agent: I have some thoughts but I'm having trouble phrasing them." in output or
                "Error during speak()" in output)
        assert "Exiting chat" in output
    
    @patch('builtins.input')
    def test_eof_exit_scenario(self, mock_input):
        """Test scenario: user exits with Ctrl+D (EOF)."""
        # Mock EOF on topic input
        mock_input.side_effect = EOFError()
        
        # Capture output
        captured_output = StringIO()
        sys.stdout = captured_output
        
        # Run main (should handle EOF gracefully)
        main([])
        
        sys.stdout = sys.__stdout__
        output = captured_output.getvalue()
        
        # Verify graceful exit
        assert "Swarm chat started" in output
        assert "Exiting" in output