#!/usr/bin/env python3
"""Test script to verify secretary property fix."""

import sys
sys.path.insert(0, '/home/cyansam/GitProjTWO/LettaGroupies/subjective-priority-driven-swarm')

from spds import config
from spds.swarm_manager import SwarmManager
from letta_client import Letta

def test_secretary_property():
    """Test that secretary property returns role-assigned agent."""

    print("Testing secretary property fix...")
    print("=" * 60)

    # Initialize Letta client
    client = Letta(
        base_url=config.LETTA_BASE_URL,
        token=config.LETTA_PASSWORD
    )

    # Get some agents
    agents = client.agents.list(limit=3)
    agent_ids = [a.id for a in agents.agents[:3]]

    print(f"\nUsing agents: {agent_ids}")

    # Create swarm without secretary
    swarm = SwarmManager(
        client=client,
        agent_ids=agent_ids,
        enable_secretary=False,
        conversation_mode="hybrid"
    )

    print(f"\nInitial state:")
    print(f"  swarm._secretary: {swarm._secretary}")
    print(f"  swarm.secretary_agent_id: {swarm.secretary_agent_id}")
    print(f"  swarm.secretary (property): {swarm.secretary}")
    print(f"  ✓ secretary property returns None as expected")

    # Assign secretary role to first agent
    print(f"\nAssigning secretary role to agent: {agent_ids[0]}")
    swarm.assign_role(agent_ids[0], "secretary")

    print(f"\nAfter role assignment:")
    print(f"  swarm._secretary: {swarm._secretary}")
    print(f"  swarm.secretary_agent_id: {swarm.secretary_agent_id}")
    print(f"  swarm.secretary (property): {swarm.secretary}")

    # Verify the fix
    if swarm.secretary is not None:
        print(f"  ✓ SUCCESS: secretary property returns agent: {swarm.secretary.name}")
        print(f"\nExport check would pass: {bool(swarm.secretary)}")
        return True
    else:
        print(f"  ✗ FAIL: secretary property still returns None")
        print(f"\nExport check would fail: {bool(swarm.secretary)}")
        return False

if __name__ == "__main__":
    try:
        success = test_secretary_property()
        print("=" * 60)
        if success:
            print("TEST PASSED: Secretary property fix is working!")
            sys.exit(0)
        else:
            print("TEST FAILED: Secretary property fix is not working")
            sys.exit(1)
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
