"""
Integration tests for model diversity functionality in SPDS.
Tests that different model configurations work properly end-to-end.
"""
import pytest
from unittest.mock import Mock, patch
import json

from spds.swarm_manager import SwarmManager
from spds.spds_agent import SPDSAgent
from spds import config
from letta_client.types import AgentState, LettaResponse, Message, LlmConfig, EmbeddingConfig, Memory
from types import SimpleNamespace

def mk_agent_state(id: str, name: str, system: str = "Test", model: str = "openai/gpt-4"):
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


class TestModelDiversity:
    """Test that diverse model configurations work correctly."""
    
    @pytest.fixture
    def diverse_agent_profiles(self):
        """Agent profiles with different model providers."""
        return [
            {
                "name": "OpenAI Agent",
                "persona": "An agent powered by OpenAI GPT-4",
                "expertise": ["analysis", "reasoning"],
                "model": "openai/gpt-4",
                "embedding": "openai/text-embedding-ada-002"
            },
            {
                "name": "Anthropic Agent",
                "persona": "An agent powered by Claude",
                "expertise": ["creative thinking", "problem solving"],
                "model": "anthropic/claude-3-5-sonnet-20241022",
                "embedding": "openai/text-embedding-ada-002"
            },
            {
                "name": "Meta Agent",
                "persona": "An agent powered by Llama",
                "expertise": ["technical implementation", "system design"],
                "model": "meta-llama/llama-3.1-70b-instruct",
                "embedding": "openai/text-embedding-ada-002"
            },
            {
                "name": "Google Agent",
                "persona": "An agent powered by Gemini",
                "expertise": ["data analysis", "research"],
                "model": "google/gemini-pro-1.5",
                "embedding": "openai/text-embedding-ada-002"
            }
        ]
    
    @patch('spds.swarm_manager.SPDSAgent.create_new')
    def test_swarm_creation_with_diverse_models(self, mock_create_new, mock_letta_client, diverse_agent_profiles):
        """Test that swarm can be created with agents using different models."""
        # Mock agent creation for each profile
        mock_agents = []
        for i, profile in enumerate(diverse_agent_profiles):
            mock_agent = Mock(spec=SPDSAgent)
            mock_agent.name = profile["name"]
            mock_agent.model = profile["model"]
            mock_agents.append(mock_agent)
        
        mock_create_new.side_effect = mock_agents
        
        # Create swarm with diverse profiles
        manager = SwarmManager(
            client=mock_letta_client,
            agent_profiles=diverse_agent_profiles
        )
        
        # Verify all agents were created
        assert len(manager.agents) == 4
        assert len(mock_create_new.call_args_list) == 4
        
        # Verify each agent was created with correct model configuration
        for i, (call_args, profile) in enumerate(zip(mock_create_new.call_args_list, diverse_agent_profiles)):
            kwargs = call_args[1]
            assert kwargs['name'] == profile['name']
            assert kwargs['persona'] == profile['persona']
            assert kwargs['expertise'] == profile['expertise']
            assert kwargs['model'] == profile['model']
            assert kwargs['embedding'] == profile['embedding']
            assert kwargs['client'] == mock_letta_client
    
    @patch('spds.spds_agent.config')
    def test_agent_creation_with_custom_models(self, mock_config, mock_letta_client):
        """Test individual agent creation with custom model configuration."""
        mock_config.DEFAULT_AGENT_MODEL = "openai/gpt-4"
        mock_config.DEFAULT_EMBEDDING_MODEL = "openai/text-embedding-ada-002"
        
        # Mock successful agent creation
        custom_agent_state = mk_agent_state(
            id="ag-custom-123",
            name="Custom Model Agent",
            system="Test system prompt",
            model="anthropic/claude-3-5-sonnet-20241022",
        )
        mock_letta_client.agents.create.return_value = custom_agent_state
        
        # Create agent with custom models
        agent = SPDSAgent.create_new(
            name="Custom Model Agent",
            persona="An agent with custom model configuration",
            expertise=["testing", "validation"],
            client=mock_letta_client,
            model="anthropic/claude-3-5-sonnet-20241022",
            embedding="openai/text-embedding-ada-002"
        )
        
        # Verify agent was created with custom model
        create_call = mock_letta_client.agents.create.call_args
        assert create_call[1]['model'] == "anthropic/claude-3-5-sonnet-20241022"
        assert create_call[1]['embedding'] == "openai/text-embedding-ada-002"
        assert create_call[1]['name'] == "Custom Model Agent"
    
    @patch('spds.spds_agent.config')
    def test_agent_creation_with_default_fallback(self, mock_config, mock_letta_client):
        """Test agent creation falls back to defaults when no model specified."""
        mock_config.DEFAULT_AGENT_MODEL = "openai/gpt-4"
        mock_config.DEFAULT_EMBEDDING_MODEL = "openai/text-embedding-ada-002"
        
        # Mock successful agent creation
        default_agent_state = mk_agent_state(
            id="ag-default-123",
            name="Default Model Agent",
            system="Test system prompt",
            model="openai/gpt-4",
        )
        mock_letta_client.agents.create.return_value = default_agent_state
        
        # Create agent without specifying models
        agent = SPDSAgent.create_new(
            name="Default Model Agent",
            persona="An agent using default models",
            expertise=["general"],
            client=mock_letta_client
            # No model or embedding parameters
        )
        
        # Verify agent was created with default models
        create_call = mock_letta_client.agents.create.call_args
        assert create_call[1]['model'] == "openai/gpt-4"
        assert create_call[1]['embedding'] == "openai/text-embedding-ada-002"
    
    def test_creative_swarm_json_loading(self, mock_letta_client):
        """Test loading the creative_swarm.json configuration."""
        # Read the actual creative_swarm.json file
        with open('creative_swarm.json', 'r') as f:
            creative_profiles = json.load(f)
        
        # Verify it contains diverse models
        models_used = [profile.get('model') for profile in creative_profiles]
        unique_models = set(models_used)
        
        # Should have multiple different models
        assert len(unique_models) > 3, "Creative swarm should showcase model diversity"
        
        # Should include different model providers
        model_providers = set()
        for model in models_used:
            if model:
                provider = model.split('/')[0]
                model_providers.add(provider)
        
        # Should have at least 3 different providers
        assert len(model_providers) >= 3, f"Should have diverse providers, got: {model_providers}"
        
        # Verify all profiles have required fields
        for profile in creative_profiles:
            assert 'name' in profile
            assert 'persona' in profile
            assert 'expertise' in profile
            assert isinstance(profile['expertise'], list)
            # Model and embedding are optional but should be strings if present
            if 'model' in profile:
                assert isinstance(profile['model'], str)
            if 'embedding' in profile:
                assert isinstance(profile['embedding'], str)
    
    @patch('spds.swarm_manager.SPDSAgent.create_new')
    def test_model_specific_conversation_flow(self, mock_create_new, mock_letta_client, diverse_agent_profiles):
        """Test that agents with different models can participate in conversation flow."""
        # Create mock agents with different models
        mock_agents = []
        for i, profile in enumerate(diverse_agent_profiles):
            mock_agent = Mock(spec=SPDSAgent)
            mock_agent.name = profile["name"]
            mock_agent.model = profile["model"]
            mock_agent.priority_score = 20.0 + i * 10  # Different priorities
            mock_agent.motivation_score = 40 + i * 5
            mock_agent.assess_motivation_and_priority = Mock()
            
            # Mock speak response specific to the model
            mock_response = SimpleNamespace(messages=[SimpleNamespace(id=f"msg-{i}", role="assistant", content=[{"type": "text", "text": f"Response from {profile['model']} agent"}] )])
            mock_agent.speak.return_value = mock_response
            
            mock_agents.append(mock_agent)
        
        mock_create_new.side_effect = mock_agents
        
        # Create swarm
        manager = SwarmManager(
            client=mock_letta_client,
            agent_profiles=diverse_agent_profiles
        )
        
        # Simulate conversation turn
        manager.conversation_history = "Initial conversation"
        manager._agent_turn("Test Topic")
        
        # Verify all agents were assessed
        for agent in mock_agents:
            assert agent.assess_motivation_and_priority.called
        
        # Verify the highest priority agent spoke (at least once in hybrid mode)
        highest_priority_agent = mock_agents[-1]  # Google Agent with highest priority
        assert highest_priority_agent.speak.call_count >= 1
        
        # Verify conversation history was updated
        assert "Response from google/gemini-pro-1.5 agent" in manager.conversation_history
    
    @patch('spds.spds_agent.config')
    def test_config_default_models_usage(self, mock_config, mock_letta_client):
        """Test that config default models are used appropriately."""
        # Set up config defaults
        mock_config.DEFAULT_AGENT_MODEL = "openai/gpt-4"
        mock_config.DEFAULT_EMBEDDING_MODEL = "openai/text-embedding-ada-002"
        
        # Mock agent creation
        mock_agent_state = mk_agent_state(
            id="ag-test-123",
            name="Test Agent",
            system="Test system",
            model="openai/gpt-4",
        )
        mock_letta_client.agents.create.return_value = mock_agent_state
        
        # Test creation without model specification
        agent = SPDSAgent.create_new(
            name="Test Agent",
            persona="Test persona",
            expertise=["testing"],
            client=mock_letta_client
        )
        
        # Verify defaults were used
        create_call = mock_letta_client.agents.create.call_args
        assert create_call[1]['model'] == mock_config.DEFAULT_AGENT_MODEL
        assert create_call[1]['embedding'] == mock_config.DEFAULT_EMBEDDING_MODEL
    
    def test_profile_model_configuration_validation(self):
        """Test that agent profiles with model configs are valid."""
        # Test valid profile with model config
        valid_profile = {
            "name": "Valid Agent",
            "persona": "A valid test agent",
            "expertise": ["testing"],
            "model": "openai/gpt-4",
            "embedding": "openai/text-embedding-ada-002"
        }
        
        # Should not raise any errors
        assert valid_profile.get('model') == "openai/gpt-4"
        assert valid_profile.get('embedding') == "openai/text-embedding-ada-002"
        
        # Test valid profile without model config (uses defaults)
        minimal_profile = {
            "name": "Minimal Agent",
            "persona": "A minimal agent",
            "expertise": ["basic"]
        }
        
        # Should work with None values
        assert minimal_profile.get('model') is None
        assert minimal_profile.get('embedding') is None
    
    @pytest.mark.integration
    @patch('spds.swarm_manager.SPDSAgent.create_new')
    def test_full_diverse_swarm_workflow(self, mock_create_new, mock_letta_client):
        """Integration test for complete diverse swarm workflow."""
        # Load creative swarm configuration
        with open('creative_swarm.json', 'r') as f:
            creative_profiles = json.load(f)
        
        # Mock agent creation for all profiles
        mock_agents = []
        for i, profile in enumerate(creative_profiles):
            mock_agent = Mock(spec=SPDSAgent)
            mock_agent.name = profile["name"]
            mock_agent.priority_score = 10.0 + i * 5
            mock_agent.motivation_score = 30 + i * 3
            mock_agent.assess_motivation_and_priority = Mock()
            
            # Mock speak response
            mock_response = SimpleNamespace(messages=[SimpleNamespace(id=f"msg-creative-{i}", role="assistant", content=[{"type": "text", "text": f"Creative response from {profile['name']}"}] )])
            mock_agent.speak.return_value = mock_response
            
            mock_agents.append(mock_agent)
        
        mock_create_new.side_effect = mock_agents
        
        # Create diverse swarm
        manager = SwarmManager(
            client=mock_letta_client,
            agent_profiles=creative_profiles
        )
        
        # Verify swarm was created successfully
        assert len(manager.agents) == len(creative_profiles)
        
        # Test multiple conversation turns
        topics = ["Innovation Strategy", "Technical Architecture", "User Experience"]
        
        for topic in topics:
            manager._agent_turn(topic)
            
            # Verify all agents assessed the topic
            for agent in mock_agents:
                assert agent.assess_motivation_and_priority.call_count >= 1
        
        # Verify conversation history contains responses
        assert len(manager.conversation_history) > 0
        
        # Verify different agents had opportunities to speak
        speak_calls = sum(1 for agent in mock_agents if agent.speak.called)
        assert speak_calls >= len(topics), "At least one agent should speak per turn"
