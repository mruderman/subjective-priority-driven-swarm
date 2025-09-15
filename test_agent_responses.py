#!/usr/bin/env python3
"""
Test script to verify agent response improvements.
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

def test_agent_responses():
    """Test that agents can respond properly with new prompting."""
    print("🧪 Testing Agent Response Improvements\n")
    
    client = get_client()
    
    # Get agents (use the ones we created)
    agents = client.agents.list()
    usable_agents = [a for a in agents if any(name in a.name for name in ["Alex", "Jordan", "Casey"])]
    
    if len(usable_agents) < 2:
        print("❌ Not enough usable agents. Run fix_agent_issues.py first.")
        return False
    
    agent_ids = [agent.id for agent in usable_agents[:2]]
    print(f"Using agents: {[a.name for a in usable_agents[:2]]}")
    
    # Create manager without secretary for simplicity
    manager = SwarmManager(
        client=client,
        agent_ids=agent_ids,
        conversation_mode="hybrid",
        enable_secretary=False
    )
    
    # Test 1: Simple question
    print("\n=== Test 1: Simple Question ===")
    test_question = "What do you think is the most important skill for effective teamwork?"
    
    print(f"Question: {test_question}")
    
    # Update agent memories with the question
    manager._update_agent_memories(test_question, "Test User")
    print("✅ Updated agent memories")
    
    # Give a moment for processing
    time.sleep(1)
    
    # Test agent responses
    print("\n--- Agent Responses ---")
    topic = "teamwork skills"
    success_count = 0
    
    for i, agent in enumerate(manager.agents):
        print(f"\nTesting {agent.name}...")
        
        # Test motivation assessment
        agent.assess_motivation_and_priority(topic)
        print(f"  Motivation: {agent.motivation_score}, Priority: {agent.priority_score:.2f}")
        
        if agent.priority_score > 0:
            try:
                # Test initial response
                response = agent.speak(mode="initial", topic=topic)
                message_text = manager._extract_agent_response(response)
                
                print(f"  Response: {message_text[:150]}{'...' if len(message_text) > 150 else ''}")
                
                # Check if it's a real response or fallback
                if "having trouble" not in message_text and len(message_text) > 20:
                    success_count += 1
                    print(f"  ✅ Good response from {agent.name}")
                else:
                    print(f"  ⚠️ Fallback response from {agent.name}")
                
            except Exception as e:
                print(f"  ❌ Error from {agent.name}: {e}")
        else:
            print(f"  ⚠️ {agent.name} not motivated to respond")
    
    # Test 2: Follow-up question
    print("\n=== Test 2: Follow-up Question ===")
    followup = "Can you give a specific example of when teamwork made a difference?"
    
    print(f"Follow-up: {followup}")
    manager._update_agent_memories(followup, "Test User")
    
    time.sleep(1)
    
    followup_success = 0
    for agent in manager.agents:
        if agent.priority_score > 0:
            try:
                response = agent.speak(mode="response", topic="teamwork examples")
                message_text = manager._extract_agent_response(response)
                
                if "having trouble" not in message_text and len(message_text) > 20:
                    followup_success += 1
                    print(f"  ✅ Good follow-up from {agent.name}")
                    print(f"    {message_text[:100]}...")
                else:
                    print(f"  ⚠️ Fallback follow-up from {agent.name}")
                    
            except Exception as e:
                print(f"  ❌ Error from {agent.name}: {e}")
    
    # Summary
    print("\n=== Test Results ===")
    total_agents = len([a for a in manager.agents if a.priority_score > 0])
    print(f"Initial responses: {success_count}/{total_agents} agents gave good responses")
    print(f"Follow-up responses: {followup_success}/{total_agents} agents gave good follow-ups")
    
    if success_count >= total_agents // 2:
        print("✅ Agent response improvements are working!")
        return True
    else:
        print("❌ Still having issues with agent responses")
        print("\nTroubleshooting tips:")
        print("1. Check if agents have send_message tool enabled")
        print("2. Verify agent memory is being updated properly")
        print("3. Test with different topic phrasing")
        return False

def main():
    """Run the test."""
    print("🎯 Agent Response Testing\n")
    
    success = test_agent_responses()
    
    if success:
        print("\n🎉 Agent responses are working properly!")
        print("The group chat should now have more meaningful conversations.")
    else:
        print("\n🔧 Some issues remain. You may need to:")
        print("1. Check agent tool configurations")
        print("2. Verify Letta server stability")
        print("3. Consider creating fresh agents")

if __name__ == "__main__":
    main()