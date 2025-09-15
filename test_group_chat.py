#!/usr/bin/env python3
"""
Test script to verify group chat functionality with secretary.
"""

import sys
sys.path.append('.')

from letta_client import Letta
from spds import config
from spds.swarm_manager import SwarmManager
import time

def get_client():
    """Get Letta client with proper authentication."""
    if config.LETTA_ENVIRONMENT == "SELF_HOSTED" and config.LETTA_SERVER_PASSWORD:
        return Letta(token=config.LETTA_SERVER_PASSWORD, base_url=config.LETTA_BASE_URL)
    elif config.LETTA_API_KEY:
        return Letta(token=config.LETTA_API_KEY, base_url=config.LETTA_BASE_URL)
    else:
        return Letta(base_url=config.LETTA_BASE_URL)

def test_group_chat_setup():
    """Test setting up a group chat with secretary."""
    print("🔧 Testing Group Chat Setup\n")
    
    client = get_client()
    
    # List available agents
    print("=== Available Agents ===")
    agents = client.agents.list()
    usable_agents = []
    for agent in agents:
        # Skip problematic agents
        if "Adaptive Secretary" in agent.name and "20" not in agent.name:
            continue
        if "scratch-agent" in agent.name:
            continue
        print(f"  - {agent.name} (ID: {agent.id})")
        usable_agents.append(agent)
    
    if len(usable_agents) < 2:
        print("\n❌ Not enough usable agents. Please run fix_agent_issues.py first.")
        return False
    
    # Use the first 3 usable agents
    agent_ids = [agent.id for agent in usable_agents[:3]]
    print(f"\n✅ Selected {len(agent_ids)} agents for group chat")
    
    # Test SwarmManager with secretary
    print("\n=== Testing SwarmManager with Secretary ===")
    try:
        manager = SwarmManager(
            client=client,
            agent_ids=agent_ids,
            conversation_mode="hybrid",
            enable_secretary=True,
            secretary_mode="adaptive",
            meeting_type="discussion"
        )
        print(f"✅ SwarmManager created successfully")
        print(f"   - Agents: {len(manager.agents)}")
        print(f"   - Secretary enabled: {manager.enable_secretary}")
        print(f"   - Mode: {manager.conversation_mode}")
        
        # Test starting a meeting
        if manager.secretary:
            print("\n=== Testing Meeting Start ===")
            topic = "Testing group chat functionality"
            participant_names = [agent.name for agent in manager.agents]
            
            manager.secretary.start_meeting(
                topic=topic,
                participants=participant_names,
                meeting_type="discussion"
            )
            print("✅ Meeting started successfully")
            
            # Test sending a message
            print("\n=== Testing Message Flow ===")
            test_message = "Hello everyone! Let's test if the group chat is working properly."
            
            # Update agent memories
            manager._update_agent_memories(test_message, "Test User")
            print("✅ Agent memories updated")
            
            # Secretary observes
            if manager.secretary:
                manager.secretary.observe_message("Test User", test_message)
                print("✅ Secretary observed message")
            
            # Test agent turn
            print("\n=== Testing Agent Responses ===")
            manager._agent_turn(topic)
            print("✅ Agent turn completed")
            
            # Wait a bit for processing
            time.sleep(2)
            
            # Test generating minutes
            print("\n=== Testing Meeting Minutes ===")
            try:
                minutes = manager.secretary.generate_minutes()
                if minutes and len(minutes) > 50:
                    print("✅ Meeting minutes generated successfully")
                    print("\nSample of minutes:")
                    print("-" * 50)
                    print(minutes[:500] + "..." if len(minutes) > 500 else minutes)
                    print("-" * 50)
                else:
                    print("⚠️ Minutes generated but seem too short")
            except Exception as e:
                print(f"❌ Failed to generate minutes: {e}")
            
            return True
            
    except Exception as e:
        print(f"❌ Failed to test SwarmManager: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Run the test."""
    print("🎯 SWARMS Group Chat Test\n")
    
    success = test_group_chat_setup()
    
    print("\n=== Test Summary ===")
    if success:
        print("✅ Group chat is working properly!")
        print("\nYou can now:")
        print("1. Run 'python3 -m spds.main' for interactive CLI")
        print("2. Run 'python3 swarms-web/app.py' for web interface")
    else:
        print("❌ Group chat test failed")
        print("\nTroubleshooting:")
        print("1. Check if Letta server is running")
        print("2. Verify authentication credentials")
        print("3. Run 'python3 fix_agent_issues.py' to create fresh agents")

if __name__ == "__main__":
    main()