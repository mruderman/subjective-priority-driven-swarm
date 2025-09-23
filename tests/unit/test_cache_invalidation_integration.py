# tests/unit/test_cache_invalidation_integration.py

"""
Integration tests demonstrating cache invalidation behavior
for the agent profiles system.

This test suite shows how the cache invalidation mechanism
works in realistic scenarios.
"""

import pytest
from unittest.mock import patch

from spds.profiles_schema import (
    get_agent_profiles_validated,
    clear_profiles_cache,
    get_profiles_cache_info,
)


class TestCacheInvalidationIntegration:
    """Integration tests for cache invalidation in realistic scenarios."""

    def setup_method(self):
        """Clear cache before each test."""
        clear_profiles_cache()

    def test_config_change_detection_simulation(self):
        """
        Simulate a realistic scenario where config.AGENT_PROFILES changes
        during runtime and the cache automatically invalidates.
        """
        # Simulate initial configuration
        initial_config = [
            {
                "name": "Production Agent 1",
                "persona": "A production-ready agent",
                "expertise": ["production", "monitoring"],
                "model": "openai/gpt-4",
            }
        ]

        # Simulate configuration update (e.g., from environment variable change)
        updated_config = [
            {
                "name": "Production Agent 1",
                "persona": "A production-ready agent",
                "expertise": ["production", "monitoring"],
                "model": "openai/gpt-4.1",  # Model upgrade
            },
            {
                "name": "Production Agent 2",
                "persona": "A new production agent",
                "expertise": ["deployment", "scaling"],
                "model": "anthropic/claude-3-5-sonnet",
            }
        ]

        # Mock the config module to simulate runtime changes
        with patch("spds.config.AGENT_PROFILES", initial_config):
            # First access - should load and cache initial config
            config1 = get_agent_profiles_validated()
            assert len(config1.agents) == 1
            assert config1.agents[0].model == "openai/gpt-4"
            
            # Verify cache is populated
            is_cached, fingerprint1 = get_profiles_cache_info()
            assert is_cached is True

            # Simulate config change (e.g., config reload, environment variable update)
            with patch("spds.config.AGENT_PROFILES", updated_config):
                # Next access should detect change and invalidate cache
                config2 = get_agent_profiles_validated()
                assert len(config2.agents) == 2
                assert config2.agents[0].model == "openai/gpt-4.1"
                assert config2.agents[1].name == "Production Agent 2"
                
                # Verify cache was invalidated and updated
                is_cached2, fingerprint2 = get_profiles_cache_info()
                assert is_cached2 is True
                assert fingerprint1 != fingerprint2

    def test_cli_integration_scenario(self):
        """
        Test scenario that simulates how the CLI team will use the cache invalidation.
        This demonstrates the expected behavior when config.AGENT_PROFILES changes.
        """
        # Initial profiles (e.g., default configuration)
        default_profiles = [
            {"name": "Default Agent", "persona": "Default persona", "expertise": ["general"]}
        ]

        # Custom profiles (e.g., loaded from user configuration file)
        custom_profiles = [
            {"name": "Custom Agent 1", "persona": "Custom persona 1", "expertise": ["custom1"]},
            {"name": "Custom Agent 2", "persona": "Custom persona 2", "expertise": ["custom2"]},
        ]

        # Step 1: Application starts with default profiles
        with patch("spds.config.AGENT_PROFILES", default_profiles):
            config1 = get_agent_profiles_validated()
            assert config1.agents[0].name == "Default Agent"
            
            cache_info1 = get_profiles_cache_info()
            assert cache_info1[0] is True  # Cache populated

        # Step 2: User loads custom configuration (simulating CLI workflow)
        # In real scenario, CLI team would update config.AGENT_PROFILES and call get_agent_profiles_validated()
        with patch("spds.config.AGENT_PROFILES", custom_profiles):
            config2 = get_agent_profiles_validated()
            assert len(config2.agents) == 2
            assert config2.agents[0].name == "Custom Agent 1"
            assert config2.agents[1].name == "Custom Agent 2"
            
            # Verify cache was automatically invalidated
            cache_info2 = get_profiles_cache_info()
            assert cache_info2[0] is True  # Cache repopulated
            assert cache_info2[1] != cache_info1[1]  # Different fingerprint

        # Step 3: Return to default profiles (e.g., reset configuration)
        with patch("spds.config.AGENT_PROFILES", default_profiles):
            config3 = get_agent_profiles_validated()
            assert config3.agents[0].name == "Default Agent"
            
            # Verify cache was invalidated again
            cache_info3 = get_profiles_cache_info()
            assert cache_info3[1] == cache_info1[1]  # Same fingerprint as step 1

    def test_explicit_source_vs_config_interaction(self):
        """
        Test interaction between explicit source parameter and config.AGENT_PROFILES.
        This shows how the cache handles mixed usage patterns.
        """
        config_profiles = [
            {"name": "Config Agent", "persona": "From config", "expertise": ["config"]}
        ]
        
        explicit_profiles = [
            {"name": "Explicit Agent", "persona": "From parameter", "expertise": ["explicit"]}
        ]

        with patch("spds.config.AGENT_PROFILES", config_profiles):
            # Use config.AGENT_PROFILES (default behavior)
            config1 = get_agent_profiles_validated()
            assert config1.agents[0].name == "Config Agent"
            fingerprint1 = get_profiles_cache_info()[1]

            # Use explicit source - should invalidate cache
            config2 = get_agent_profiles_validated(explicit_profiles)
            assert config2.agents[0].name == "Explicit Agent"
            fingerprint2 = get_profiles_cache_info()[1]
            assert fingerprint1 != fingerprint2

            # Return to config - should invalidate cache again
            config3 = get_agent_profiles_validated()
            assert config3.agents[0].name == "Config Agent"
            fingerprint3 = get_profiles_cache_info()[1]
            assert fingerprint3 == fingerprint1  # Same as first call

    def test_performance_characteristics(self):
        """
        Test that demonstrates the performance benefits of caching
        while ensuring cache invalidation works correctly.
        """
        profiles = [
            {"name": f"Agent {i}", "persona": f"Persona {i}", "expertise": [f"skill{i}"]}
            for i in range(10)  # 10 agents
        ]

        with patch("spds.config.AGENT_PROFILES", profiles):
            # First call - cold cache
            config1 = get_agent_profiles_validated()
            assert len(config1.agents) == 10

            # Second call - warm cache (should be same object)
            config2 = get_agent_profiles_validated()
            assert config2 is config1  # Exact same object reference

            # Modify profiles slightly
            modified_profiles = profiles.copy()
            modified_profiles[0]["persona"] = "Modified Persona 0"

            with patch("spds.config.AGENT_PROFILES", modified_profiles):
                # Should detect change and invalidate
                config3 = get_agent_profiles_validated()
                assert config3 is not config1  # Different object
                assert config3.agents[0].persona == "Modified Persona 0"

    def test_error_handling_with_cache_invalidation(self):
        """
        Test that cache invalidation doesn't interfere with proper error handling.
        """
        valid_profiles = [
            {"name": "Valid Agent", "persona": "Valid", "expertise": ["valid"]}
        ]

        invalid_profiles = [
            {"name": "", "persona": "Invalid", "expertise": ["invalid"]}  # Empty name
        ]

        with patch("spds.config.AGENT_PROFILES", valid_profiles):
            # Load valid profiles into cache
            config = get_agent_profiles_validated()
            assert config.agents[0].name == "Valid Agent"
            assert get_profiles_cache_info()[0] is True

            with patch("spds.config.AGENT_PROFILES", invalid_profiles):
                # Invalid profiles should raise error, not use cache
                with pytest.raises(ValueError):
                    get_agent_profiles_validated()

                # Cache should still be from valid profiles call
                # (error doesn't update cache)
                cache_info = get_profiles_cache_info()
                assert cache_info[0] is True  # Still cached

            # Return to valid profiles - should work normally
            config2 = get_agent_profiles_validated()
            assert config2.agents[0].name == "Valid Agent"