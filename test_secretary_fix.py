#!/usr/bin/env python3
"""Simple test to verify secretary property fix works correctly."""

# Create a minimal mock to test the property logic
class MockAgent:
    def __init__(self, agent_id, name):
        self.id = agent_id
        self.name = name

class MockSPDSAgent:
    def __init__(self, agent_id, name):
        self.agent = MockAgent(agent_id, name)
        self.name = name
        self.roles = []

class SimplifiedSwarmManager:
    """Simplified version with just the secretary property logic."""

    def __init__(self):
        self._secretary = None
        self.secretary_agent_id = None
        self.agents = [
            MockSPDSAgent("agent-1", "Agent One"),
            MockSPDSAgent("agent-2", "Agent Two"),
            MockSPDSAgent("agent-3", "Agent Three"),
        ]

    @property
    def secretary(self):
        """Backward-compatible accessor for secretary.

        Returns:
            - The dedicated SecretaryAgent instance if one was created during init
            - The role-assigned agent (SPDSAgent) if secretary_agent_id is set
            - None if no secretary is assigned
        """
        # Return dedicated SecretaryAgent if it exists (old system)
        if self._secretary is not None:
            return self._secretary
        # Fall back to role-based secretary (new system)
        return self.get_secretary()

    @secretary.setter
    def secretary(self, value):
        """Set the secretary to a SecretaryAgent instance."""
        self._secretary = value

    def get_secretary(self):
        """Returns the agent object that has the 'secretary' role."""
        if self.secretary_agent_id:
            return self.get_agent_by_id(self.secretary_agent_id)
        return None

    def get_agent_by_id(self, agent_id):
        """Get agent by ID."""
        for agent in self.agents:
            if agent.agent.id == agent_id:
                return agent
        return None

    def assign_role(self, agent_id, role):
        """Assigns a role to a specific agent."""
        agent = self.get_agent_by_id(agent_id)
        if agent and role not in agent.roles:
            agent.roles.append(role)
            if role == "secretary":
                self.secretary_agent_id = agent.agent.id
                # Clear other agents' secretary role if exclusive
                for other_agent in self.agents:
                    if other_agent.agent.id != agent_id and "secretary" in other_agent.roles:
                        other_agent.roles.remove("secretary")

def test_secretary_property():
    """Test the secretary property with role-based assignment."""

    print("Testing secretary property fix...")
    print("=" * 70)

    # Create swarm manager
    swarm = SimplifiedSwarmManager()

    print("\n1. Initial State (no secretary):")
    print(f"   swarm._secretary: {swarm._secretary}")
    print(f"   swarm.secretary_agent_id: {swarm.secretary_agent_id}")
    print(f"   swarm.secretary (property): {swarm.secretary}")

    # Test: export check should fail
    if not swarm.secretary:
        print(f"   ✓ Export check correctly fails: bool(swarm.secretary) = {bool(swarm.secretary)}")
    else:
        print(f"   ✗ UNEXPECTED: Export check should fail but passed")
        return False

    print("\n2. Assigning secretary role to Agent One:")
    swarm.assign_role("agent-1", "secretary")
    print(f"   swarm._secretary: {swarm._secretary}")
    print(f"   swarm.secretary_agent_id: {swarm.secretary_agent_id}")
    print(f"   swarm.secretary (property): {swarm.secretary}")

    # Test: export check should now pass
    if swarm.secretary:
        print(f"   ✓ Export check correctly passes: bool(swarm.secretary) = {bool(swarm.secretary)}")
        print(f"   ✓ Secretary name: {swarm.secretary.name}")
    else:
        print(f"   ✗ FAIL: Export check should pass but failed")
        return False

    print("\n3. Testing backward compatibility (setting _secretary directly):")
    class MockSecretaryAgent:
        def __init__(self):
            self.name = "Direct Secretary"

    swarm2 = SimplifiedSwarmManager()
    swarm2._secretary = MockSecretaryAgent()

    if swarm2.secretary and swarm2.secretary.name == "Direct Secretary":
        print(f"   ✓ Old system still works: {swarm2.secretary.name}")
    else:
        print(f"   ✗ FAIL: Backward compatibility broken")
        return False

    print("\n" + "=" * 70)
    print("✅ ALL TESTS PASSED!")
    print("\nSummary:")
    print("  • Property returns None when no secretary assigned")
    print("  • Property returns role-assigned agent after assign_role()")
    print("  • Export checks (if swarm.secretary) work correctly")
    print("  • Backward compatibility maintained with _secretary")
    return True

if __name__ == "__main__":
    import sys
    try:
        success = test_secretary_property()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
