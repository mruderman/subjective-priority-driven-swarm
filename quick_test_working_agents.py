#!/usr/bin/env python3
"""
Quick test using only working agents to verify response improvements.
"""

import sys

sys.path.append(".")

from letta_client import Letta, MessageCreate

from spds import config
from spds.swarm_manager import SwarmManager


def get_client():
    """Get Letta client with proper authentication."""
    if config.LETTA_ENVIRONMENT == "SELF_HOSTED" and config.LETTA_SERVER_PASSWORD:
        return Letta(token=config.LETTA_SERVER_PASSWORD, base_url=config.LETTA_BASE_URL)
    elif config.LETTA_API_KEY:
        return Letta(token=config.LETTA_API_KEY, base_url=config.LETTA_BASE_URL)
    else:
        return Letta(base_url=config.LETTA_BASE_URL)


def test_working_agents():
    """Test with known working agents."""
    print("🔧 Quick Test with Working Agents\n")

    client = get_client()

    # Use specific working agents
    working_agent_names = [
        "Alex - Project Manager",
        "companion-agent-1753201615269-sleeptime",
    ]

    agents = client.agents.list()
    working_agents = [a for a in agents if a.name in working_agent_names]

    if len(working_agents) < 2:
        print("❌ Not enough working agents found")
        return False

    agent_ids = [a.id for a in working_agents]
    print(f"Using working agents: {[a.name for a in working_agents]}")

    # Test individual agent responses
    print("\n=== Testing Individual Agent Responses ===")

    for agent in working_agents:
        print(f"\nTesting {agent.name}:")

        # Update agent memory with a question
        test_question = "What's your perspective on AI collaboration in teams?"
        try:
            client.agents.messages.create(
                agent_id=agent.id,
                messages=[MessageCreate(role="user", content=f"User: {test_question}")],
            )
            print("  ✅ Memory updated")
        except Exception as e:
            print(f"  ❌ Memory update failed: {e}")
            continue

        # Create a temporary SPDSAgent wrapper for testing
        from spds.spds_agent import SPDSAgent

        spds_agent = SPDSAgent(agent, client)

        # Test motivation assessment
        try:
            spds_agent.assess_motivation_and_priority("AI collaboration")
            print(
                f"  📊 Motivation: {spds_agent.motivation_score}, Priority: {spds_agent.priority_score:.2f}"
            )
        except Exception as e:
            print(f"  ⚠️ Assessment error: {e}")
            spds_agent.motivation_score = 35  # Set manually for testing
            spds_agent.priority_score = 7.0

        # Test speak method with new prompting
        if spds_agent.priority_score > 0:
            try:
                response = spds_agent.speak(
                    mode="initial", topic="AI collaboration in teams"
                )

                # Extract response
                message_text = ""
                for msg in response.messages:
                    if (
                        hasattr(msg, "message_type")
                        and msg.message_type == "assistant_message"
                    ):
                        if hasattr(msg, "content") and msg.content:
                            message_text = msg.content
                            break

                if not message_text:
                    message_text = (
                        "I have some thoughts but I'm having trouble expressing them."
                    )

                print(
                    f"  💬 Response: {message_text[:200]}{'...' if len(message_text) > 200 else ''}"
                )

                # Check quality
                if "having trouble" not in message_text and len(message_text) > 30:
                    print(f"  ✅ Good response from {agent.name}")
                    return True
                else:
                    print(f"  ⚠️ Generic response from {agent.name}")

            except Exception as e:
                print(f"  ❌ Response error: {e}")

    return False


def test_with_swarm_manager():
    """Test with SwarmManager using working agents."""
    print("\n=== Testing with SwarmManager ===")

    client = get_client()

    # Get working agents
    agents = client.agents.list()
    working_agents = []

    for agent in agents:
        if agent.name in [
            "Alex - Project Manager",
            "companion-agent-1753201615269-sleeptime",
        ]:
            try:
                # Quick health check
                client.agents.messages.create(
                    agent_id=agent.id,
                    messages=[MessageCreate(role="user", content="ping")],
                )
                working_agents.append(agent)
            except:
                pass

    if len(working_agents) < 2:
        print("❌ Not enough healthy agents")
        return False

    agent_ids = [a.id for a in working_agents[:2]]

    try:
        manager = SwarmManager(
            client=client,
            agent_ids=agent_ids,
            conversation_mode="sequential",  # Use simpler mode
            enable_secretary=False,  # No secretary for this test
        )

        print(f"✅ Manager created with {len(manager.agents)} agents")

        # Send a simple message
        test_message = "What are the benefits of AI-human collaboration?"
        print(f"\nTest message: {test_message}")

        # Update memories (with retry logic)
        manager._update_agent_memories(test_message, "Test User")

        # Test single agent turn
        topic = "AI-human collaboration"
        print(f"\nTesting agent turn with topic: {topic}")

        # Manually test one agent
        motivated_agent = None
        for agent in manager.agents:
            try:
                agent.assess_motivation_and_priority(topic)
                if agent.priority_score > 0:
                    motivated_agent = agent
                    break
            except:
                continue

        if motivated_agent:
            print(
                f"✅ {motivated_agent.name} is motivated (priority: {motivated_agent.priority_score:.2f})"
            )

            try:
                response = motivated_agent.speak(mode="initial", topic=topic)
                message_text = manager._extract_agent_response(response)

                print(f"📝 Response: {message_text}")

                if "having trouble" not in message_text and len(message_text) > 20:
                    print("✅ Improved prompting is working!")
                    return True
                else:
                    print("⚠️ Still getting generic responses")

            except Exception as e:
                print(f"❌ Response failed: {e}")

    except Exception as e:
        print(f"❌ Manager test failed: {e}")

    return False


def main():
    """Run the tests."""
    success1 = test_working_agents()
    success2 = test_with_swarm_manager()

    print("\n=== Summary ===")
    if success1 or success2:
        print("✅ Response improvements are working!")
        print("\nThe updated prompting should resolve the issues you saw.")
        print("\nTo use the improved system:")
        print("1. Run 'python3 -m spds.main' and select working agents")
        print("2. Or use the web interface: 'python3 swarms-web/app.py'")
    else:
        print("❌ Still having issues")
        print("\nThe Letta server may be unstable. Try:")
        print("1. Restarting the Letta server")
        print("2. Creating completely fresh agents")
        print("3. Using a different Letta server instance")


if __name__ == "__main__":
    main()
