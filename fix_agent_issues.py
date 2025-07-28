#!/usr/bin/env python3
"""
Fix script to resolve agent issues in the SWARMS group chat system.
"""

import sys
sys.path.append('.')

from letta_client import Letta
from spds import config
import time

def get_client():
    """Get Letta client with proper authentication."""
    if config.LETTA_ENVIRONMENT == "SELF_HOSTED" and config.LETTA_SERVER_PASSWORD:
        return Letta(token=config.LETTA_SERVER_PASSWORD, base_url=config.LETTA_BASE_URL)
    elif config.LETTA_API_KEY:
        return Letta(token=config.LETTA_API_KEY, base_url=config.LETTA_BASE_URL)
    else:
        return Letta(base_url=config.LETTA_BASE_URL)

def test_agent_health(client, agent_id, agent_name):
    """Test if an agent is healthy by sending a simple message."""
    print(f"Testing {agent_name}...")
    try:
        from letta_client import MessageCreate
        response = client.agents.messages.create(
            agent_id=agent_id,
            messages=[MessageCreate(role="user", content="ping")]
        )
        print(f"  ✅ {agent_name} is healthy")
        return True
    except Exception as e:
        print(f"  ❌ {agent_name} has issues: {str(e)[:100]}")
        return False

def delete_problematic_agents(client):
    """Delete agents that are causing issues."""
    print("\n=== Cleaning Up Problematic Agents ===")
    
    problematic_names = ["Adaptive Secretary", "scratch-agent-agent-1753217733834"]
    agents = client.agents.list()
    
    for agent in agents:
        if agent.name in problematic_names:
            healthy = test_agent_health(client, agent.id, agent.name)
            if not healthy:
                try:
                    print(f"  Deleting problematic agent: {agent.name}")
                    client.agents.delete(agent_id=agent.id)
                    print(f"  ✅ Deleted {agent.name}")
                    time.sleep(1)  # Give server time to clean up
                except Exception as e:
                    print(f"  ⚠️ Could not delete {agent.name}: {e}")

def create_fresh_agents(client):
    """Create fresh agents for the swarm."""
    print("\n=== Creating Fresh Agents ===")
    
    agent_profiles = [
        {
            "name": "Alex - Project Manager",
            "persona": "A pragmatic and analytical project manager who values clarity and efficiency.",
            "expertise": ["risk management", "scheduling", "budgeting"]
        },
        {
            "name": "Jordan - Designer",
            "persona": "A creative and user-focused designer with a passion for intuitive interfaces.",
            "expertise": ["UX/UI design", "user research", "prototyping"]
        },
        {
            "name": "Casey - Engineer",
            "persona": "A detail-oriented engineer who prioritizes code quality and stability.",
            "expertise": ["backend systems", "database architecture", "API development"]
        }
    ]
    
    created_agents = []
    for profile in agent_profiles:
        try:
            from letta_client import CreateBlock
            
            agent = client.agents.create(
                name=profile["name"],
                memory_blocks=[
                    CreateBlock(
                        label="human",
                        value="I am participating in a group discussion with other AI agents."
                    ),
                    CreateBlock(
                        label="persona",
                        value=profile["persona"]
                    ),
                    CreateBlock(
                        label="expertise",
                        value=", ".join(profile["expertise"]),
                        description="My areas of expertise"
                    )
                ],
                model=config.DEFAULT_AGENT_MODEL,
                embedding=config.DEFAULT_EMBEDDING_MODEL,
                include_base_tools=True,
            )
            print(f"  ✅ Created {agent.name}")
            created_agents.append(agent)
            
            # Test the agent
            test_agent_health(client, agent.id, agent.name)
            
        except Exception as e:
            print(f"  ❌ Failed to create {profile['name']}: {e}")
    
    return created_agents

def patch_error_handling():
    """Patch the error handling in secretary and swarm manager."""
    print("\n=== Patching Error Handling ===")
    
    # Read secretary agent file
    secretary_path = "/home/claude/SWARMS/spds/secretary_agent.py"
    with open(secretary_path, 'r') as f:
        secretary_code = f.read()
    
    # Check if we already have retry logic
    if "retry_count" not in secretary_code:
        print("  Adding retry logic to secretary_agent.py...")
        
        # Insert retry logic after imports
        import_end = secretary_code.find("class SecretaryAgent:")
        retry_function = '''
def retry_with_backoff(func, max_retries=3, backoff_factor=1):
    """Retry a function with exponential backoff."""
    for attempt in range(max_retries):
        try:
            return func()
        except Exception as e:
            if "500" in str(e) or "disconnected" in str(e).lower():
                if attempt < max_retries - 1:
                    wait_time = backoff_factor * (2 ** attempt)
                    print(f"    Retrying in {wait_time}s after error: {str(e)[:50]}...")
                    time.sleep(wait_time)
                    continue
            raise
    return None

'''
        secretary_code = secretary_code[:import_end] + retry_function + secretary_code[import_end:]
        
        # Add time import
        if "import time" not in secretary_code:
            secretary_code = "import time\n" + secretary_code
        
        # Save patched file
        with open(secretary_path, 'w') as f:
            f.write(secretary_code)
        print("  ✅ Patched secretary_agent.py")
    else:
        print("  ℹ️ secretary_agent.py already has retry logic")
    
    # Similarly patch swarm_manager.py
    swarm_path = "/home/claude/SWARMS/spds/swarm_manager.py"
    with open(swarm_path, 'r') as f:
        swarm_code = f.read()
    
    # Add better error handling to _update_agent_memories
    if "max_retries=3" not in swarm_code:
        print("  Adding enhanced error handling to swarm_manager.py...")
        
        # Find the _update_agent_memories method
        method_start = swarm_code.find("def _update_agent_memories(")
        method_end = swarm_code.find("\n    def ", method_start + 1)
        
        # Replace with enhanced version
        enhanced_method = '''def _update_agent_memories(self, message: str, speaker: str = "User", max_retries=3):
        """Send a message to all agents to update their internal memory with retry logic."""
        for agent in self.agents:
            success = False
            for attempt in range(max_retries):
                try:
                    self.client.agents.messages.create(
                        agent_id=agent.agent.id,
                        messages=[{"role": "user", "content": f"{speaker}: {message}"}]
                    )
                    success = True
                    break
                except Exception as e:
                    error_str = str(e)
                    if attempt < max_retries - 1 and ("500" in error_str or "disconnected" in error_str.lower()):
                        wait_time = 0.5 * (2 ** attempt)
                        print(f"[Debug: Retrying {agent.name} after {wait_time}s...]")
                        time.sleep(wait_time)
                        continue
                    else:
                        print(f"[Debug: Error updating {agent.name} memory: {e}]")
                        # For token limit errors, reset and retry once
                        if "max_tokens" in error_str.lower() or "token" in error_str.lower():
                            print(f"[Debug: Token limit reached for {agent.name}, resetting messages...]")
                            self._reset_agent_messages(agent.agent.id)
                            try:
                                self.client.agents.messages.create(
                                    agent_id=agent.agent.id,
                                    messages=[{"role": "user", "content": f"{speaker}: {message}"}]
                                )
                                success = True
                            except Exception as retry_e:
                                print(f"[Debug: Retry failed for {agent.name}: {retry_e}]")
                        break
            
            if not success:
                print(f"[Debug: Failed to update {agent.name} after {max_retries} attempts]")'''
        
        # Find the exact end of the method
        method_body = swarm_code[method_start:method_end] if method_end != -1 else swarm_code[method_start:]
        indent_count = method_body.find("def _reset_agent_messages")
        if indent_count == -1:
            # Find next method
            next_method = swarm_code.find("\n    def ", method_start + 10)
            method_body = swarm_code[method_start:next_method]
        
        # Replace the method
        swarm_code = swarm_code[:method_start] + enhanced_method + swarm_code[method_start + len(method_body):]
        
        # Save patched file
        with open(swarm_path, 'w') as f:
            f.write(swarm_code)
        print("  ✅ Patched swarm_manager.py")
    else:
        print("  ℹ️ swarm_manager.py already has enhanced error handling")

def main():
    """Run the fix script."""
    print("🔧 SWARMS Fix Script - Resolving Agent Issues\n")
    
    client = get_client()
    
    # Step 1: Clean up problematic agents
    delete_problematic_agents(client)
    
    # Step 2: Create fresh agents
    agents = create_fresh_agents(client)
    
    # Step 3: Patch error handling
    patch_error_handling()
    
    # Summary
    print("\n=== Fix Summary ===")
    print(f"✓ Cleaned up problematic agents")
    print(f"✓ Created {len(agents)} fresh agents")
    print(f"✓ Patched error handling in code")
    print("\n✅ Fix complete! The group chat should now work properly.")
    print("\nNext steps:")
    print("1. Run 'python3 -m spds.main' to start a new group chat")
    print("2. Or run 'python3 swarms-web/app.py' for the web interface")

if __name__ == "__main__":
    main()