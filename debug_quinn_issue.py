#!/usr/bin/env python3
"""Debug script to investigate Quinn's tool call issue."""

import json

from letta_client import Letta

from spds import config
from spds.swarm_manager import SwarmManager


def debug_quinn_issue():
    print("🔍 Debugging Quinn's Tool Call Issue")
    print("=" * 60)

    try:
        # Initialize Letta client
        client = Letta(token=config.LETTA_API_KEY, base_url=config.LETTA_BASE_URL)

        # Load creative swarm
        with open("creative_swarm.json", "r") as f:
            creative_profiles = json.load(f)

        # Create swarm
        print("\n🚀 Creating swarm...")
        swarm = SwarmManager(client=client, agent_profiles=creative_profiles)

        # Find Quinn
        quinn = None
        for agent in swarm.agents:
            if agent.name == "Philosopher Quinn":
                quinn = agent
                break

        if not quinn:
            print("❌ Quinn not found!")
            return

        print(f"\n📊 Quinn's Agent Details:")
        print(f"  - Agent ID: {quinn.agent.id}")
        print(f"  - Model: {getattr(quinn.agent, 'model', 'Unknown')}")
        print(
            f"  - Tools attached: {len(quinn.agent.tools) if hasattr(quinn.agent, 'tools') else 'Unknown'}"
        )

        if hasattr(quinn.agent, "tools") and quinn.agent.tools:
            print("\n🔧 Tools attached to Quinn:")
            for tool in quinn.agent.tools:
                print(
                    f"  - {tool.name}: {getattr(tool, 'description', 'No description')}"
                )

        # Check system prompt
        if hasattr(quinn.agent, "system"):
            print(f"\n📝 Quinn's System Prompt:")
            print(f"{quinn.agent.system[:200]}...")

        # Try different message formats
        print("\n🧪 Testing different message approaches:")

        # Test 1: Simple message without tool expectation
        print("\n1️⃣ Simple direct message:")
        try:
            response = client.agents.messages.create(
                agent_id=quinn.agent.id,
                messages=[
                    {
                        "role": "user",
                        "content": "Hello Quinn, what are your thoughts on AI ethics?",
                    }
                ],
            )
            print("✅ Success! Response received")
            if hasattr(response, "messages") and response.messages:
                print(f"Response: {response.messages[-1].content}")
        except Exception as e:
            print(f"❌ Error: {e}")

        # Test 2: Message with explicit no-tool instruction
        print("\n2️⃣ Message with no-tool instruction:")
        try:
            response = client.agents.messages.create(
                agent_id=quinn.agent.id,
                messages=[
                    {
                        "role": "user",
                        "content": "Please respond directly without using any tools. What are your thoughts on AI ethics?",
                    }
                ],
            )
            print("✅ Success! Response received")
        except Exception as e:
            print(f"❌ Error: {e}")

        # Test 3: Check if we can list agent messages
        print("\n3️⃣ Checking agent message history:")
        try:
            messages = client.agents.messages.list(agent_id=quinn.agent.id, limit=5)
            print(f"Found {len(messages)} messages in history")
        except Exception as e:
            print(f"❌ Error listing messages: {e}")

    except Exception as e:
        print(f"\n❌ Error during debugging: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    debug_quinn_issue()
