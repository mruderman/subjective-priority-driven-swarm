#!/usr/bin/env python3
"""
Debug script to test Letta agent creation and visibility in group chat.
"""

import sys
sys.path.append('.')

from letta_client import Letta
from spds import config
import json

def test_letta_connection():
    """Test connection to Letta server."""
    print("=== Testing Letta Server Connection ===")
    print(f"Base URL: {config.LETTA_BASE_URL}")
    print(f"Environment: {config.LETTA_ENVIRONMENT}")
    
    try:
        # Initialize client based on environment
        if config.LETTA_ENVIRONMENT == "SELF_HOSTED" and config.LETTA_SERVER_PASSWORD:
            print("Using self-hosted authentication with password")
            client = Letta(token=config.LETTA_SERVER_PASSWORD, base_url=config.LETTA_BASE_URL)
        elif config.LETTA_API_KEY:
            print("Using API key authentication")
            client = Letta(token=config.LETTA_API_KEY, base_url=config.LETTA_BASE_URL)
        else:
            print("No authentication (local server)")
            client = Letta(base_url=config.LETTA_BASE_URL)
        
        print("✅ Client initialized successfully")
        return client
    except Exception as e:
        print(f"❌ Failed to initialize client: {e}")
        return None

def list_existing_agents(client):
    """List all existing agents on the server."""
    print("\n=== Listing Existing Agents ===")
    try:
        agents = client.agents.list()
        print(f"Found {len(agents)} agents:")
        for agent in agents:
            print(f"  - {agent.name} (ID: {agent.id})")
            print(f"    Model: {agent.model if hasattr(agent, 'model') else 'Unknown'}")
            print(f"    Created: {str(agent.created_at)[:10] if hasattr(agent, 'created_at') else 'Unknown'}")
        return agents
    except Exception as e:
        print(f"❌ Failed to list agents: {e}")
        return []

def create_test_agent(client):
    """Create a test agent to verify creation works."""
    print("\n=== Creating Test Agent ===")
    try:
        from letta_client import CreateBlock
        
        agent = client.agents.create(
            name="Debug Test Agent",
            memory_blocks=[
                CreateBlock(
                    label="human",
                    value="I am testing agent creation for the SWARMS group chat system."
                ),
                CreateBlock(
                    label="persona",
                    value="I am a test agent created to debug group chat functionality. I am helpful and technical."
                ),
                CreateBlock(
                    label="expertise",
                    value="debugging, testing, system validation",
                    description="Areas of expertise for this agent"
                )
            ],
            model=config.DEFAULT_AGENT_MODEL,
            embedding=config.DEFAULT_EMBEDDING_MODEL,
            include_base_tools=True,
        )
        print(f"✅ Created agent: {agent.name} (ID: {agent.id})")
        return agent
    except Exception as e:
        print(f"❌ Failed to create agent: {e}")
        print(f"Error type: {type(e).__name__}")
        import traceback
        traceback.print_exc()
        return None

def test_agent_message(client, agent_id):
    """Test sending a message to an agent."""
    print("\n=== Testing Agent Message ===")
    try:
        from letta_client import MessageCreate
        
        response = client.agents.messages.create(
            agent_id=agent_id,
            messages=[
                MessageCreate(
                    role="user",
                    content="Hello! Can you confirm you're working properly?"
                )
            ]
        )
        
        print("✅ Message sent successfully")
        print("Response messages:")
        for msg in response.messages:
            if hasattr(msg, 'message_type'):
                print(f"  - Type: {msg.message_type}")
                if msg.message_type == 'assistant_message' and hasattr(msg, 'content'):
                    print(f"    Content: {msg.content}")
        
        return True
    except Exception as e:
        print(f"❌ Failed to send message: {e}")
        return False

def test_secretary_creation(client):
    """Test creating a secretary agent."""
    print("\n=== Testing Secretary Agent Creation ===")
    try:
        from spds.secretary_agent import SecretaryAgent
        
        secretary = SecretaryAgent(client, mode="adaptive")
        print(f"✅ Secretary created: {secretary.agent.name if secretary.agent else 'Unknown'}")
        
        # Test secretary start meeting
        secretary.start_meeting(
            topic="Debug Test Meeting",
            participants=["Test Agent 1", "Test Agent 2"],
            meeting_type="discussion"
        )
        
        # Test secretary observe message
        secretary.observe_message("Test User", "This is a test message for the secretary.")
        
        print("✅ Secretary functionality tested")
        return secretary
    except Exception as e:
        print(f"❌ Failed to create/test secretary: {e}")
        import traceback
        traceback.print_exc()
        return None

def test_swarm_manager(client):
    """Test SwarmManager with existing agents."""
    print("\n=== Testing SwarmManager ===")
    try:
        from spds.swarm_manager import SwarmManager
        
        # First, get existing agents
        agents = client.agents.list()
        if len(agents) < 2:
            print("⚠️  Not enough agents for swarm test. Creating test agents...")
            # Create a couple of test agents
            agent_profiles = [
                {
                    "name": "Test Alex",
                    "persona": "A test project manager",
                    "expertise": ["testing", "debugging"]
                },
                {
                    "name": "Test Jordan",
                    "persona": "A test designer",
                    "expertise": ["UI", "testing"]
                }
            ]
            manager = SwarmManager(
                client=client,
                agent_profiles=agent_profiles,
                conversation_mode="hybrid",
                enable_secretary=True
            )
        else:
            # Use existing agents
            agent_ids = [agent.id for agent in agents[:3]]  # Use first 3 agents
            print(f"Using agents: {agent_ids}")
            manager = SwarmManager(
                client=client,
                agent_ids=agent_ids,
                conversation_mode="hybrid",
                enable_secretary=True
            )
        
        print(f"✅ SwarmManager created with {len(manager.agents)} agents")
        print(f"Secretary enabled: {manager.enable_secretary}")
        
        # Test agent turn without starting full chat
        print("\nTesting agent motivation assessment...")
        topic = "Debug test topic"
        manager._update_agent_memories("This is a test message about debugging", "Test User")
        manager._agent_turn(topic)
        
        return manager
    except Exception as e:
        print(f"❌ Failed to test SwarmManager: {e}")
        import traceback
        traceback.print_exc()
        return None

def main():
    """Run all debug tests."""
    print("🐛 SWARMS Debug Script - Testing Agent Creation and Visibility\n")
    
    # Test 1: Connection
    client = test_letta_connection()
    if not client:
        print("\n❌ Cannot proceed without client connection")
        return
    
    # Test 2: List agents
    existing_agents = list_existing_agents(client)
    
    # Test 3: Create agent
    test_agent = create_test_agent(client)
    
    # Test 4: Send message
    if test_agent:
        test_agent_message(client, test_agent.id)
    
    # Test 5: Secretary
    secretary = test_secretary_creation(client)
    
    # Test 6: SwarmManager
    swarm = test_swarm_manager(client)
    
    # Summary
    print("\n=== Debug Summary ===")
    print(f"✓ Client connection: {'Success' if client else 'Failed'}")
    print(f"✓ Existing agents: {len(existing_agents)}")
    print(f"✓ Agent creation: {'Success' if test_agent else 'Failed'}")
    print(f"✓ Secretary: {'Success' if secretary else 'Failed'}")
    print(f"✓ SwarmManager: {'Success' if swarm else 'Failed'}")
    
    # Cleanup - delete test agent
    if test_agent and client:
        try:
            print("\nCleaning up test agent...")
            client.agents.delete(agent_id=test_agent.id)
            print("✅ Test agent deleted")
        except Exception as e:
            print(f"⚠️  Could not delete test agent: {e}")

if __name__ == "__main__":
    main()