#!/usr/bin/env python3
"""Test script for live conversation with priority-based turn-taking."""

from letta_client import Letta
from spds import config
from spds.swarm_manager import SwarmManager
import json

def test_live_conversation():
    print("🎭 Testing Live Conversation with Priority-Based Turn-Taking")
    print("=" * 60)
    
    try:
        # Initialize Letta client with proper authentication
        if config.LETTA_ENVIRONMENT == "SELF_HOSTED" and config.LETTA_SERVER_PASSWORD:
            client = Letta(token=config.LETTA_SERVER_PASSWORD, base_url=config.LETTA_BASE_URL)
        elif config.LETTA_API_KEY:
            client = Letta(token=config.LETTA_API_KEY, base_url=config.LETTA_BASE_URL)
        else:
            client = Letta(base_url=config.LETTA_BASE_URL)
        
        # Load creative swarm
        with open('creative_swarm.json', 'r') as f:
            creative_profiles = json.load(f)
        
        # Create swarm
        print("\n🚀 Creating swarm...")
        swarm = SwarmManager(client=client, agent_profiles=creative_profiles)
        print(f"✅ Created swarm with {len(swarm.agents)} agents")
        
        # Test conversation topic
        topic = "Should we prioritize developing a new AI ethics framework or focus on improving existing model capabilities?"
        print(f"\n💬 Topic: {topic}")
        
        # Simulate conversation
        conversation_history = []
        
        # Initial human message
        human_msg = f"Human: {topic}"
        conversation_history.append(human_msg)
        print(f"\n{human_msg}")
        
        # Initialize swarm conversation history
        swarm.conversation_history = "\n".join(conversation_history) + "\n"
        
        # Get 3 rounds of responses
        for round_num in range(3):
            print(f"\n📊 Round {round_num + 1} - Agent Priority Calculations:")
            print("--- Assessing agent motivations ---")
            
            # Calculate priorities for all agents
            for agent in swarm.agents:
                agent.assess_motivation_and_priority(swarm.conversation_history, topic)
                print(f"  - {agent.name}: Motivation = {agent.motivation_score}, Priority = {agent.priority_score:.2f}")
            
            # Get agents sorted by priority (filter by motivation, sort by priority)
            motivated_agents = sorted(
                [agent for agent in swarm.agents if agent.motivation_score >= config.PARTICIPATION_THRESHOLD],
                key=lambda x: x.priority_score,
                reverse=True,
            )
            
            if not motivated_agents:
                print("\n❌ No agent is motivated to speak (all below threshold)")
                break
            
            # Select highest priority speaker
            speaker = motivated_agents[0]
            print(f"\n🎯 Next speaker: {speaker.name}")
            print(f"   Priority score: {speaker.priority_score:.2f}")
            print(f"   Motivation: {speaker.motivation_score}")
            
            # Get agent's response
            print(f"\n💭 {speaker.name} is speaking...")
            try:
                response = speaker.speak(swarm.conversation_history)
                # Extract text from response - handle different response formats
                message_text = None
                
                if hasattr(response, 'messages') and response.messages:
                    # Look through messages for the actual response
                    for msg in reversed(response.messages):
                        # Check if this is a tool return with send_message
                        if hasattr(msg, 'tool_calls') and msg.tool_calls:
                            for tool_call in msg.tool_calls:
                                if hasattr(tool_call, 'function') and tool_call.function.name == 'send_message':
                                    # Extract the message from tool call arguments
                                    try:
                                        args = json.loads(tool_call.function.arguments)
                                        message_text = args.get('message', '')
                                        break
                                    except:
                                        pass
                        
                        # If not a tool call, try regular content extraction
                        if not message_text and hasattr(msg, 'content'):
                            if isinstance(msg.content, str):
                                message_text = msg.content
                            elif isinstance(msg.content, list) and msg.content:
                                # Handle list of content items
                                content_item = msg.content[0]
                                if hasattr(content_item, 'text'):
                                    message_text = content_item.text
                                elif isinstance(content_item, str):
                                    message_text = content_item
                        
                        if message_text:
                            break
                
                if not message_text:
                    message_text = "I have some thoughts but I'm having trouble phrasing them."
                    
            except Exception as e:
                message_text = "I have some thoughts but I'm having trouble phrasing them."
                print(f"[Debug: Error during speak() - {e}]")
            
            # Add to conversation history
            agent_msg = f"{speaker.name}: {message_text}"
            conversation_history.append(agent_msg)
            swarm.conversation_history += agent_msg + "\n"
            print(f"\n{agent_msg}")
            
            # Show assessment details
            if speaker.last_assessment:
                print(f"\n📈 Assessment Details:")
                print(f"   - Importance to self: {speaker.last_assessment.importance_to_self}")
                print(f"   - Expertise relevance: {speaker.last_assessment.expertise_relevance}")
                print(f"   - Unique perspective: {speaker.last_assessment.unique_perspective}")
                print(f"   - Urgency: {speaker.last_assessment.urgency}")
        
        print("\n✅ Live conversation test completed successfully!")
        
    except Exception as e:
        print(f"\n❌ Error during live conversation test: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_live_conversation()