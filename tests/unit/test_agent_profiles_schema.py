# tests/unit/test_agent_profiles_schema.py

import logging

import pytest
from pydantic import ValidationError

from spds.profiles_schema import (
    AgentProfile,
    ProfilesConfig,
    _compute_profiles_fingerprint,
    clear_profiles_cache,
    get_agent_profiles_validated,
    get_profiles_cache_info,
    validate_agent_profiles,
)


class TestAgentProfile:
    """Test individual agent profile validation."""

    def test_valid_agent_profile(self):
        """Test that a valid agent profile passes validation."""
        agent_data = {
            "name": "Test Agent",
            "persona": "A helpful test agent",
            "expertise": ["testing", "validation"],
            "model": "openai/gpt-4",
            "embedding": "openai/text-embedding-ada-002",
        }

        agent = AgentProfile(**agent_data)
        assert agent.name == "Test Agent"
        assert agent.persona == "A helpful test agent"
        assert agent.expertise == ["testing", "validation"]
        assert agent.model == "openai/gpt-4"
        assert agent.embedding == "openai/text-embedding-ada-002"

    def test_minimal_valid_agent_profile(self):
        """Test that minimal required fields work."""
        agent_data = {
            "name": "Minimal Agent",
            "persona": "Just the basics",
            "expertise": ["basic"],
        }

        agent = AgentProfile(**agent_data)
        assert agent.name == "Minimal Agent"
        assert agent.persona == "Just the basics"
        assert agent.expertise == ["basic"]
        assert agent.model is None
        assert agent.embedding is None

    def test_empty_name_fails(self):
        """Test that empty name fails validation."""
        agent_data = {"name": "", "persona": "Valid persona", "expertise": ["testing"]}

        with pytest.raises(ValidationError) as exc_info:
            AgentProfile(**agent_data)

        assert "cannot be empty" in str(exc_info.value)

    def test_empty_persona_fails(self):
        """Test that empty persona fails validation."""
        agent_data = {"name": "Valid Agent", "persona": "", "expertise": ["testing"]}

        with pytest.raises(ValidationError) as exc_info:
            AgentProfile(**agent_data)

        assert "cannot be empty" in str(exc_info.value)

    def test_empty_expertise_fails(self):
        """Test that empty expertise fails validation."""
        agent_data = {
            "name": "Valid Agent",
            "persona": "Valid persona",
            "expertise": [],
        }

        with pytest.raises(ValidationError) as exc_info:
            AgentProfile(**agent_data)

        assert "cannot be empty" in str(exc_info.value)

    def test_expertise_with_empty_items_fails(self):
        """Test that expertise with empty items fails validation."""
        agent_data = {
            "name": "Valid Agent",
            "persona": "Valid persona",
            "expertise": ["valid", "", "also valid"],
        }

        with pytest.raises(ValidationError) as exc_info:
            AgentProfile(**agent_data)

        assert "items cannot be empty" in str(exc_info.value)

    def test_non_list_expertise_fails(self):
        """Test that non-list expertise fails validation."""
        agent_data = {
            "name": "Valid Agent",
            "persona": "Valid persona",
            "expertise": "not a list",
        }

        with pytest.raises(ValidationError) as exc_info:
            AgentProfile(**agent_data)

        assert "should be a valid list" in str(exc_info.value)

    def test_extra_fields_allowed(self):
        """Test that extra fields are allowed with warning."""
        agent_data = {
            "name": "Test Agent",
            "persona": "A test agent",
            "expertise": ["testing"],
            "custom_field": "custom_value",
            "another_extra": 123,
        }

        agent = AgentProfile(**agent_data)
        assert agent.name == "Test Agent"
        # Extra fields should be accessible
        assert agent.custom_field == "custom_value"
        assert agent.another_extra == 123


class TestProfilesConfig:
    """Test profiles configuration validation."""

    def test_valid_profiles_config(self):
        """Test that valid profiles configuration passes validation."""
        profiles_data = {
            "agents": [
                {
                    "name": "Agent 1",
                    "persona": "First agent",
                    "expertise": ["skill1", "skill2"],
                },
                {
                    "name": "Agent 2",
                    "persona": "Second agent",
                    "expertise": ["skill3", "skill4"],
                },
            ]
        }

        config = ProfilesConfig(**profiles_data)
        assert len(config.agents) == 2
        assert config.agents[0].name == "Agent 1"
        assert config.agents[1].name == "Agent 2"

    def test_empty_agents_list_fails(self):
        """Test that empty agents list fails validation."""
        profiles_data = {"agents": []}

        with pytest.raises(ValidationError) as exc_info:
            ProfilesConfig(**profiles_data)

        assert "At least one agent profile is required" in str(exc_info.value)

    def test_duplicate_agent_names_fails(self):
        """Test that duplicate agent names fail validation."""
        profiles_data = {
            "agents": [
                {
                    "name": "Duplicate Agent",
                    "persona": "First instance",
                    "expertise": ["skill1"],
                },
                {
                    "name": "Duplicate Agent",
                    "persona": "Second instance",
                    "expertise": ["skill2"],
                },
            ]
        }

        with pytest.raises(ValidationError) as exc_info:
            ProfilesConfig(**profiles_data)

        assert "Duplicate agent names found: Duplicate Agent" in str(exc_info.value)


class TestValidateAgentProfiles:
    """Test the validate_agent_profiles function."""

    def test_valid_profiles_list(self):
        """Test validation with a list of profiles."""
        profiles_list = [
            {
                "name": "Agent 1",
                "persona": "First agent",
                "expertise": ["skill1", "skill2"],
            },
            {
                "name": "Agent 2",
                "persona": "Second agent",
                "expertise": ["skill3", "skill4"],
            },
        ]

        config = validate_agent_profiles(profiles_list)
        assert len(config.agents) == 2
        assert config.agents[0].name == "Agent 1"
        assert config.agents[1].name == "Agent 2"

    def test_valid_profiles_dict(self):
        """Test validation with a dict containing agents list."""
        profiles_dict = {
            "agents": [
                {
                    "name": "Agent 1",
                    "persona": "First agent",
                    "expertise": ["skill1", "skill2"],
                }
            ]
        }

        config = validate_agent_profiles(profiles_dict)
        assert len(config.agents) == 1
        assert config.agents[0].name == "Agent 1"

    def test_invalid_format_fails(self):
        """Test that invalid format fails validation."""
        invalid_data = {"invalid_key": "invalid_value"}

        with pytest.raises(ValueError) as exc_info:
            validate_agent_profiles(invalid_data)

        assert "Invalid profiles format" in str(exc_info.value)

    def test_validation_error_with_agent_context(self):
        """Test that validation errors include agent context."""
        profiles_list = [
            {
                "name": "Bad Agent",
                "persona": "",  # Empty persona should fail
                "expertise": ["skill1"],
            }
        ]

        with pytest.raises(ValueError) as exc_info:
            validate_agent_profiles(profiles_list)

        error_msg = str(exc_info.value)
        assert "Agent 'Bad Agent'" in error_msg or "Bad Agent" in error_msg
        assert "persona" in error_msg

    def test_warning_for_unknown_fields(self, caplog):
        """Test that unknown fields generate warnings."""
        caplog.set_level(logging.WARNING)

        profiles_list = [
            {
                "name": "Agent with extras",
                "persona": "Has extra fields",
                "expertise": ["skill1"],
                "unknown_field": "value",
                "another_extra": 123,
            }
        ]

        validate_agent_profiles(profiles_list)

        # Check that warnings were logged
        warning_messages = [
            record.message for record in caplog.records if record.levelname == "WARNING"
        ]
        assert any("unknown fields" in msg for msg in warning_messages)
        assert any("unknown_field" in msg for msg in warning_messages)
        assert any("another_extra" in msg for msg in warning_messages)


class TestGetAgentProfilesValidated:
    """Test the get_agent_profiles_validated function."""

    def test_get_validated_profiles_with_cache(self, monkeypatch):
        """Test that caching works correctly."""
        # Mock the AGENT_PROFILES
        mock_profiles = [
            {"name": "Cached Agent", "persona": "From cache", "expertise": ["caching"]}
        ]
        monkeypatch.setattr("spds.config.AGENT_PROFILES", mock_profiles)

        # First call should validate and cache
        config1 = get_agent_profiles_validated()
        assert len(config1.agents) == 1
        assert config1.agents[0].name == "Cached Agent"

        # Second call should use cache
        config2 = get_agent_profiles_validated()
        assert config2 is config1  # Should be the same object due to caching

    def test_get_validated_profiles_with_source(self):
        """Test validation with explicit source."""
        source_profiles = [
            {"name": "Source Agent", "persona": "From source", "expertise": ["source"]}
        ]

        # Clear cache first to ensure we're using the source
        clear_profiles_cache()
        config = get_agent_profiles_validated(source_profiles)
        assert len(config.agents) == 1
        assert config.agents[0].name == "Source Agent"

    def test_clear_cache(self, monkeypatch):
        """Test that cache can be cleared."""
        # Mock the AGENT_PROFILES
        mock_profiles = [
            {
                "name": "Cache Test Agent",
                "persona": "Testing cache",
                "expertise": ["cache"],
            }
        ]
        monkeypatch.setattr("spds.config.AGENT_PROFILES", mock_profiles)

        # Get validated profiles (should cache)
        config1 = get_agent_profiles_validated()

        # Clear cache
        clear_profiles_cache()

        # Get validated profiles again (should re-validate)
        config2 = get_agent_profiles_validated()

        # Should be different objects
        assert config2 is not config1
        assert config2.agents[0].name == "Cache Test Agent"


class TestRealWorldProfiles:
    """Test with real-world profile examples."""

    def test_default_config_profiles(self):
        """Test validation with the default AGENT_PROFILES from config."""
        from spds import config

        # This should not raise any exceptions
        validated_config = validate_agent_profiles(config.AGENT_PROFILES)

        assert len(validated_config.agents) == 4  # Default has 4 agents
        agent_names = [agent.name for agent in validated_config.agents]
        assert "Alex" in agent_names
        assert "Jordan" in agent_names
        assert "Casey" in agent_names
        assert "Morgan" in agent_names

    def test_sample_json_profiles(self):
        """Test validation with sample JSON profiles."""

        # Test creative_swarm.json structure
        creative_profiles = [
            {
                "name": "Innovator Sam",
                "persona": "A creative thinker who challenges conventional approaches.",
                "expertise": ["innovation", "brainstorming", "lateral thinking"],
                "model": "anthropic/claude-3-5-sonnet-20241022",
                "embedding": "openai/text-embedding-ada-002",
            }
        ]

        config = validate_agent_profiles(creative_profiles)
        assert len(config.agents) == 1
        assert config.agents[0].name == "Innovator Sam"
        assert config.agents[0].model == "anthropic/claude-3-5-sonnet-20241022"

    def test_malformed_profiles(self):
        """Test validation with malformed profiles."""
        malformed_profiles = [
            {
                "name": "Bad Agent",
                # Missing persona
                "expertise": "not a list",  # Wrong type
                "model": 123,  # Wrong type for model
            }
        ]

        with pytest.raises(Exception):  # Will be ValueError or ValidationError
            validate_agent_profiles(malformed_profiles)


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_very_long_strings(self):
        """Test with very long strings."""
        long_name = "A" * 1000
        long_persona = "B" * 5000

        profiles = [
            {"name": long_name, "persona": long_persona, "expertise": ["long_string"]}
        ]

        config = validate_agent_profiles(profiles)
        assert config.agents[0].name == long_name
        assert config.agents[0].persona == long_persona

    def test_unicode_characters(self):
        """Test with unicode characters."""
        profiles = [
            {
                "name": "代理 🚀",
                "persona": "一个有帮助的代理 with émojis 🎉",
                "expertise": ["国际化", "émojis", "café"],
            }
        ]

        config = validate_agent_profiles(profiles)
        assert config.agents[0].name == "代理 🚀"
        assert "émojis" in config.agents[0].expertise

    def test_large_number_of_agents(self):
        """Test with a large number of agents."""
        profiles = []
        for i in range(100):
            profiles.append(
                {
                    "name": f"Agent {i}",
                    "persona": f"Agent number {i}",
                    "expertise": [f"skill_{i}"],
                }
            )

        config = validate_agent_profiles(profiles)
        assert len(config.agents) == 100
        assert config.agents[99].name == "Agent 99"

    def test_empty_expertise_item_after_strip(self):
        """Test expertise items that become empty after stripping."""
        profiles = [
            {
                "name": "Test Agent",
                "persona": "Test persona",
                "expertise": [
                    "valid",
                    "   ",
                    "also_valid",
                ],  # Middle item is whitespace
            }
        ]

        with pytest.raises(Exception):  # Will be ValueError or ValidationError
            validate_agent_profiles(profiles)


class TestCacheInvalidation:
    """Test cache invalidation functionality for agent profiles."""

    def setup_method(self):
        """Clear cache before each test."""
        clear_profiles_cache()

    def test_fingerprint_computation_stable(self):
        """Test that fingerprint computation is stable for same data."""
        profiles = [
            {"name": "Agent 1", "persona": "Test persona", "expertise": ["skill1"]},
            {"name": "Agent 2", "persona": "Another persona", "expertise": ["skill2"]},
        ]

        fingerprint1 = _compute_profiles_fingerprint(profiles)
        fingerprint2 = _compute_profiles_fingerprint(profiles)

        assert fingerprint1 == fingerprint2
        assert isinstance(fingerprint1, str)
        assert len(fingerprint1) == 64  # SHA256 hex digest length

    def test_fingerprint_computation_different_data(self):
        """Test that different data produces different fingerprints."""
        profiles1 = [
            {"name": "Agent 1", "persona": "Test persona", "expertise": ["skill1"]}
        ]
        profiles2 = [
            {"name": "Agent 2", "persona": "Different persona", "expertise": ["skill2"]}
        ]

        fingerprint1 = _compute_profiles_fingerprint(profiles1)
        fingerprint2 = _compute_profiles_fingerprint(profiles2)

        assert fingerprint1 != fingerprint2

    def test_fingerprint_order_insensitive_for_dict_keys(self):
        """Test that dictionary key order doesn't affect fingerprint."""
        # Same data, different key order
        profiles1 = [
            {
                "name": "Agent",
                "persona": "Test",
                "expertise": ["skill"],
                "model": "gpt-4",
            }
        ]
        profiles2 = [
            {
                "expertise": ["skill"],
                "name": "Agent",
                "model": "gpt-4",
                "persona": "Test",
            }
        ]

        fingerprint1 = _compute_profiles_fingerprint(profiles1)
        fingerprint2 = _compute_profiles_fingerprint(profiles2)

        assert fingerprint1 == fingerprint2

    def test_fingerprint_order_sensitive_for_list_order(self):
        """Test that list order affects fingerprint (as it should)."""
        profiles1 = [
            {"name": "Agent 1", "persona": "First", "expertise": ["skill1"]},
            {"name": "Agent 2", "persona": "Second", "expertise": ["skill2"]},
        ]
        profiles2 = [
            {"name": "Agent 2", "persona": "Second", "expertise": ["skill2"]},
            {"name": "Agent 1", "persona": "First", "expertise": ["skill1"]},
        ]

        fingerprint1 = _compute_profiles_fingerprint(profiles1)
        fingerprint2 = _compute_profiles_fingerprint(profiles2)

        assert fingerprint1 != fingerprint2

    def test_cache_invalidation_on_data_change(self, monkeypatch):
        """Test that cache is invalidated when source data changes."""
        # Setup initial profiles
        initial_profiles = [
            {
                "name": "Initial Agent",
                "persona": "Initial persona",
                "expertise": ["initial"],
            }
        ]
        monkeypatch.setattr("spds.config.AGENT_PROFILES", initial_profiles)

        # First call should cache
        config1 = get_agent_profiles_validated()
        assert config1.agents[0].name == "Initial Agent"

        # Verify cache info
        is_cached, fingerprint = get_profiles_cache_info()
        assert is_cached is True
        assert fingerprint is not None

        # Change the profiles
        changed_profiles = [
            {
                "name": "Changed Agent",
                "persona": "Changed persona",
                "expertise": ["changed"],
            }
        ]
        monkeypatch.setattr("spds.config.AGENT_PROFILES", changed_profiles)

        # Second call should detect change and invalidate cache
        config2 = get_agent_profiles_validated()
        assert config2.agents[0].name == "Changed Agent"

        # Verify cache was updated
        is_cached2, fingerprint2 = get_profiles_cache_info()
        assert is_cached2 is True
        assert fingerprint2 is not None
        assert fingerprint != fingerprint2

    def test_cache_reuse_when_data_unchanged(self, monkeypatch):
        """Test that cache is reused when data hasn't changed."""
        profiles = [
            {
                "name": "Unchanged Agent",
                "persona": "Unchanged",
                "expertise": ["unchanged"],
            }
        ]
        monkeypatch.setattr("spds.config.AGENT_PROFILES", profiles)

        # First call
        config1 = get_agent_profiles_validated()
        is_cached1, fingerprint1 = get_profiles_cache_info()

        # Second call with same data
        config2 = get_agent_profiles_validated()
        is_cached2, fingerprint2 = get_profiles_cache_info()

        # Should be the exact same object (cache hit)
        assert config2 is config1
        assert is_cached1 is True
        assert is_cached2 is True
        assert fingerprint1 == fingerprint2

    def test_cache_invalidation_with_explicit_source(self):
        """Test cache invalidation when using explicit source parameter."""
        source1 = [
            {
                "name": "Source 1 Agent",
                "persona": "From source 1",
                "expertise": ["source1"],
            }
        ]
        source2 = [
            {
                "name": "Source 2 Agent",
                "persona": "From source 2",
                "expertise": ["source2"],
            }
        ]

        # First call with source1
        config1 = get_agent_profiles_validated(source1)
        assert config1.agents[0].name == "Source 1 Agent"

        # Second call with source2 should invalidate cache
        config2 = get_agent_profiles_validated(source2)
        assert config2.agents[0].name == "Source 2 Agent"
        assert config2 is not config1

    def test_cache_behavior_mixed_source_and_config(self, monkeypatch):
        """Test cache behavior when mixing explicit source and config.AGENT_PROFILES."""
        # Setup config profiles
        config_profiles = [
            {"name": "Config Agent", "persona": "From config", "expertise": ["config"]}
        ]
        monkeypatch.setattr("spds.config.AGENT_PROFILES", config_profiles)

        # Explicit source profiles
        source_profiles = [
            {"name": "Source Agent", "persona": "From source", "expertise": ["source"]}
        ]

        # Call with config (source=None)
        config1 = get_agent_profiles_validated()
        assert config1.agents[0].name == "Config Agent"

        # Call with explicit source should invalidate cache
        config2 = get_agent_profiles_validated(source_profiles)
        assert config2.agents[0].name == "Source Agent"
        assert config2 is not config1

        # Call with config again should invalidate cache again
        config3 = get_agent_profiles_validated()
        assert config3.agents[0].name == "Config Agent"
        assert config3 is not config2
        assert config3 is not config1  # New object due to cache invalidation

    def test_manual_cache_clear(self, monkeypatch):
        """Test manual cache clearing functionality."""
        profiles = [
            {"name": "Test Agent", "persona": "Test persona", "expertise": ["testing"]}
        ]
        monkeypatch.setattr("spds.config.AGENT_PROFILES", profiles)

        # Load into cache
        config1 = get_agent_profiles_validated()
        is_cached1, fingerprint1 = get_profiles_cache_info()
        assert is_cached1 is True
        assert fingerprint1 is not None

        # Manual clear
        clear_profiles_cache()
        is_cached2, fingerprint2 = get_profiles_cache_info()
        assert is_cached2 is False
        assert fingerprint2 is None

        # Next call should re-validate
        config2 = get_agent_profiles_validated()
        assert config2 is not config1  # New object
        assert config2.agents[0].name == "Test Agent"  # Same data

        is_cached3, fingerprint3 = get_profiles_cache_info()
        assert is_cached3 is True
        assert fingerprint3 == fingerprint1  # Same fingerprint for same data

    def test_cache_with_complex_nested_changes(self, monkeypatch):
        """Test cache invalidation with complex nested data changes."""
        # Initial complex structure
        initial_profiles = [
            {
                "name": "Complex Agent",
                "persona": "Complex persona",
                "expertise": ["skill1", "skill2", "skill3"],
                "model": "openai/gpt-4",
                "embedding": "openai/text-embedding-ada-002",
                "custom_field": {"nested": {"value": 123}},
            }
        ]
        monkeypatch.setattr("spds.config.AGENT_PROFILES", initial_profiles)

        config1 = get_agent_profiles_validated()
        fingerprint1 = get_profiles_cache_info()[1]

        # Change nested value
        changed_profiles = [
            {
                "name": "Complex Agent",
                "persona": "Complex persona",
                "expertise": ["skill1", "skill2", "skill3"],
                "model": "openai/gpt-4",
                "embedding": "openai/text-embedding-ada-002",
                "custom_field": {"nested": {"value": 456}},  # Changed nested value
            }
        ]
        monkeypatch.setattr("spds.config.AGENT_PROFILES", changed_profiles)

        config2 = get_agent_profiles_validated()
        fingerprint2 = get_profiles_cache_info()[1]

        assert config2 is not config1
        assert fingerprint1 != fingerprint2

    def test_cache_invalidation_preserves_validation_errors(self):
        """Test that cache invalidation still properly validates data."""
        # Valid profiles first
        valid_profiles = [
            {"name": "Valid Agent", "persona": "Valid", "expertise": ["valid"]}
        ]
        config = get_agent_profiles_validated(valid_profiles)
        assert len(config.agents) == 1

        # Invalid profiles should raise error, not use cache
        invalid_profiles = [
            {"name": "", "persona": "Invalid", "expertise": ["invalid"]}  # Empty name
        ]

        with pytest.raises(ValueError) as exc_info:
            get_agent_profiles_validated(invalid_profiles)

        assert "cannot be empty" in str(exc_info.value)

    def test_get_profiles_cache_info_functionality(self):
        """Test the get_profiles_cache_info helper function."""
        # Initially no cache
        is_cached, fingerprint = get_profiles_cache_info()
        assert is_cached is False
        assert fingerprint is None

        # After caching
        profiles = [{"name": "Test", "persona": "Test", "expertise": ["test"]}]
        get_agent_profiles_validated(profiles)

        is_cached, fingerprint = get_profiles_cache_info()
        assert is_cached is True
        assert fingerprint is not None
        assert len(fingerprint) == 8  # First 8 characters of SHA256

        # After clearing
        clear_profiles_cache()
        is_cached, fingerprint = get_profiles_cache_info()
        assert is_cached is False
        assert fingerprint is None
