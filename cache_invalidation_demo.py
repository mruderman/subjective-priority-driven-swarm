#!/usr/bin/env python3
"""
Demonstration script for agent profiles cache invalidation.

This script shows how the cache automatically invalidates when
config.AGENT_PROFILES changes, providing a practical example
for the CLI team.
"""

import sys
import os
from unittest.mock import patch

# Add the project root to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from spds.profiles_schema import (
    get_agent_profiles_validated,
    clear_profiles_cache,
    get_profiles_cache_info,
)


def print_cache_info(step_name):
    """Helper to print current cache state."""
    is_cached, fingerprint = get_profiles_cache_info()
    status = "CACHED" if is_cached else "NOT CACHED"
    fp_display = fingerprint if fingerprint else "None"
    print(f"  Cache Status: {status}, Fingerprint: {fp_display}")


def main():
    """Demonstrate cache invalidation behavior."""
    
    print("=" * 60)
    print("AGENT PROFILES CACHE INVALIDATION DEMONSTRATION")
    print("=" * 60)
    
    # Clear any existing cache
    clear_profiles_cache()
    print("\n1. INITIAL STATE")
    print_cache_info("Initial")
    
    # Initial profiles configuration
    initial_profiles = [
        {
            "name": "Demo Agent Alpha",
            "persona": "A demonstration agent for cache testing",
            "expertise": ["demo", "testing", "cache"],
            "model": "openai/gpt-4",
        }
    ]
    
    print("\n2. FIRST LOAD (Cache Miss)")
    print("Loading initial profiles...")
    with patch("spds.config.AGENT_PROFILES", initial_profiles):
        config1 = get_agent_profiles_validated()
        print(f"  Loaded {len(config1.agents)} agent(s)")
        print(f"  Agent name: {config1.agents[0].name}")
        print(f"  Agent model: {config1.agents[0].model}")
        print_cache_info("After first load")
    
    print("\n3. SECOND LOAD (Cache Hit)")
    print("Loading same profiles again...")
    with patch("spds.config.AGENT_PROFILES", initial_profiles):
        config2 = get_agent_profiles_validated()
        print(f"  Same object reference: {config2 is config1}")
        print_cache_info("After second load")
    
    # Modified profiles configuration
    modified_profiles = [
        {
            "name": "Demo Agent Alpha",
            "persona": "A demonstration agent for cache testing",
            "expertise": ["demo", "testing", "cache"],
            "model": "openai/gpt-4.1",  # Model upgrade!
        },
        {
            "name": "Demo Agent Beta", 
            "persona": "A second demonstration agent",
            "expertise": ["demo", "collaboration"],
            "model": "anthropic/claude-3-5-sonnet",
        }
    ]
    
    print("\n4. CONFIGURATION CHANGE (Cache Invalidation)")
    print("Simulating config.AGENT_PROFILES change...")
    with patch("spds.config.AGENT_PROFILES", modified_profiles):
        config3 = get_agent_profiles_validated()
        print(f"  Loaded {len(config3.agents)} agent(s)")
        print(f"  Agent 1 model: {config3.agents[0].model}")
        print(f"  Agent 2 name: {config3.agents[1].name}")
        print(f"  Different object reference: {config3 is not config1}")
        print_cache_info("After configuration change")
    
    print("\n5. RETURN TO ORIGINAL (Cache Invalidation Again)")
    print("Returning to original configuration...")
    with patch("spds.config.AGENT_PROFILES", initial_profiles):
        config4 = get_agent_profiles_validated()
        print(f"  Loaded {len(config4.agents)} agent(s)")
        print(f"  Agent model: {config4.agents[0].model}")
        print(f"  Different from config3: {config4 is not config3}")
        print(f"  Different from config1: {config4 is not config1}")  # New object due to invalidation
        print_cache_info("After return to original")
    
    # Test explicit source parameter
    explicit_profiles = [
        {
            "name": "Explicit Source Agent",
            "persona": "Loaded via explicit source parameter",
            "expertise": ["explicit", "parameter"],
        }
    ]
    
    print("\n6. EXPLICIT SOURCE PARAMETER")
    print("Using explicit source parameter...")
    config5 = get_agent_profiles_validated(explicit_profiles)
    print(f"  Agent name: {config5.agents[0].name}")
    print(f"  Different from previous: {config5 is not config4}")
    print_cache_info("After explicit source")
    
    print("\n7. MANUAL CACHE CLEAR")
    print("Manually clearing cache...")
    clear_profiles_cache()
    print_cache_info("After manual clear")
    
    print("\n8. RELOAD AFTER CLEAR")
    print("Reloading after manual clear...")
    config6 = get_agent_profiles_validated(explicit_profiles)
    print(f"  Agent name: {config6.agents[0].name}")
    print(f"  Different object: {config6 is not config5}")
    print_cache_info("After reload")
    
    print("\n" + "=" * 60)
    print("DEMONSTRATION COMPLETE")
    print("=" * 60)
    print("\nKey Takeaways:")
    print("• Cache automatically invalidates when data changes")
    print("• Identical data reuses cached objects (performance benefit)")
    print("• Explicit source parameter vs config.AGENT_PROFILES both work")
    print("• Manual cache clearing forces re-validation")
    print("• Fingerprint changes reflect data modifications")


if __name__ == "__main__":
    main()