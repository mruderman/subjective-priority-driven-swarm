# spds/profiles_schema.py

import logging
from typing import Any, List, Optional, Union

from pydantic import BaseModel, Field, ValidationError, field_validator

logger = logging.getLogger(__name__)


class AgentProfile(BaseModel):
    """Pydantic model for individual agent profile validation."""

    name: str = Field(..., description="The agent's name/identifier")
    persona: str = Field(..., description="The agent's personality description")
    expertise: List[str] = Field(..., description="List of agent's expertise areas")
    model: Optional[str] = Field(None, description="The model to use for this agent")
    embedding: Optional[str] = Field(None, description="The embedding model to use")

    # Allow extra fields for backward compatibility
    model_config = {"extra": "allow"}

    @field_validator("name", "persona")
    @classmethod
    def validate_required_strings(cls, v: str) -> str:
        """Ensure required string fields are not empty."""
        if not v or not str(v).strip():
            raise ValueError("cannot be empty")
        return str(v).strip()

    @field_validator("expertise")
    @classmethod
    def validate_expertise(cls, v: List[str]) -> List[str]:
        """Ensure expertise is a list of non-empty strings."""
        if not isinstance(v, list):
            raise ValueError("must be a list")

        if not v:
            raise ValueError("cannot be empty")

        # Validate each expertise item
        validated_expertise = []
        for item in v:
            if not item or not str(item).strip():
                raise ValueError("items cannot be empty")
            validated_expertise.append(str(item).strip())

        return validated_expertise


class ProfilesConfig(BaseModel):
    """Top-level container for agent profiles configuration."""

    agents: List[AgentProfile] = Field(..., description="List of agent profiles")

    model_config = {"extra": "forbid"}  # Don't allow extra fields at the top level

    @field_validator("agents")
    @classmethod
    def validate_agents(cls, v: List[AgentProfile]) -> List[AgentProfile]:
        """Ensure we have at least one agent."""
        if not v:
            raise ValueError("At least one agent profile is required")

        # Check for duplicate agent names
        names = [agent.name for agent in v]
        if len(names) != len(set(names)):
            duplicates = [name for name in set(names) if names.count(name) > 1]
            raise ValueError(f"Duplicate agent names found: {', '.join(duplicates)}")

        return v


def validate_agent_profiles(profiles: Union[dict, list, Any]) -> ProfilesConfig:
    """
    Validate agent profiles configuration.

    Args:
        profiles: Agent profiles data (can be dict with 'agents' key or list of agents)

    Returns:
        ProfilesConfig: Validated profiles configuration

    Raises:
        ValidationError: If validation fails with detailed error messages
    """
    try:
        # Handle different input formats
        if isinstance(profiles, dict) and "agents" in profiles:
            # Already in the expected format
            data = profiles
        elif isinstance(profiles, list):
            # Convert list of agents to expected format
            data = {"agents": profiles}
        else:
            raise ValueError(
                "Invalid profiles format: expected list of agents or dict with 'agents' key"
            )

        # Parse and validate
        config = ProfilesConfig(**data)

        # Log warnings for unknown fields in each agent
        for i, agent in enumerate(config.agents):
            agent_dict = agent.model_dump(exclude_unset=True)
            known_fields = set(AgentProfile.model_fields.keys())
            unknown_fields = set(agent_dict.keys()) - known_fields

            if unknown_fields:
                logger.warning(
                    f"Agent '{agent.name}' (index {i}) has unknown fields: {', '.join(sorted(unknown_fields))}. "
                    "These fields are allowed but not part of the standard schema."
                )

        return config

    except ValidationError as e:
        # Enhance error messages with more context
        errors = []
        for error in e.errors():
            loc = error["loc"]
            msg = error["msg"]

            # Build a more descriptive error message
            if len(loc) >= 2 and loc[0] == "agents":
                agent_index = loc[1]
                if isinstance(agent_index, int):
                    # Try to get agent name for better error reporting
                    try:
                        if isinstance(profiles, list) and agent_index < len(profiles):
                            agent_name = profiles[agent_index].get(
                                "name", f"agent_{agent_index}"
                            )
                        elif (
                            isinstance(profiles, dict)
                            and "agents" in profiles
                            and agent_index < len(profiles["agents"])
                        ):
                            agent_name = profiles["agents"][agent_index].get(
                                "name", f"agent_{agent_index}"
                            )
                        else:
                            agent_name = f"agent_{agent_index}"
                    except (IndexError, KeyError, AttributeError):
                        agent_name = f"agent_{agent_index}"

                    field_path = (
                        ".".join(str(x) for x in loc[2:]) if len(loc) > 2 else "field"
                    )
                    errors.append(f"Agent '{agent_name}' {field_path}: {msg}")
                else:
                    errors.append(f"Agents {field_path}: {msg}")
            else:
                errors.append(f"{'.'.join(str(x) for x in loc)}: {msg}")

        # Create a new ValueError with enhanced message
        error_msg = "Agent profile validation failed:\n" + "\n".join(
            f"  - {error}" for error in errors
        )
        raise ValueError(error_msg) from e


# Cache for validated profiles with fingerprint-based invalidation
import hashlib
import json
from typing import Tuple

_validated_profiles_cache: Optional[ProfilesConfig] = None
_cache_fingerprint: Optional[str] = None


def _compute_profiles_fingerprint(profiles_source: Union[dict, list]) -> str:
    """
    Compute a stable fingerprint for the profiles source data.

    Args:
        profiles_source: The profiles data to fingerprint

    Returns:
        str: A stable hash representing the profiles data
    """
    # Convert to JSON string with sorted keys for stable hashing
    json_str = json.dumps(profiles_source, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(json_str.encode("utf-8")).hexdigest()


def get_agent_profiles_validated(
    profiles_source: Optional[Union[dict, list]] = None,
) -> ProfilesConfig:
    """
    Get validated agent profiles, with cache invalidation based on source fingerprint.

    The cache is automatically invalidated when the source profiles data changes.
    This ensures that changes to config.AGENT_PROFILES are always reflected
    without manual cache clearing.

    Args:
        profiles_source: Optional source of profiles. If None, uses config.AGENT_PROFILES.

    Returns:
        ProfilesConfig: Validated profiles configuration
    """
    global _validated_profiles_cache, _cache_fingerprint

    # Determine the actual source
    actual_source = profiles_source
    if actual_source is None:
        from spds import config

        actual_source = config.AGENT_PROFILES

    # Compute fingerprint of current source
    current_fingerprint = _compute_profiles_fingerprint(actual_source)

    # Check if cache is valid (exists and fingerprint matches)
    cache_valid = (
        _validated_profiles_cache is not None
        and _cache_fingerprint == current_fingerprint
    )

    if not cache_valid:
        # Cache miss or invalidation - validate and store
        _validated_profiles_cache = validate_agent_profiles(actual_source)
        _cache_fingerprint = current_fingerprint
        logger.debug(
            f"Profiles cache updated with fingerprint: {current_fingerprint[:8]}..."
        )

    return _validated_profiles_cache


def clear_profiles_cache():
    """
    Clear the cached validated profiles.

    This forces the next call to get_agent_profiles_validated() to re-validate
    the profiles source, regardless of whether the source data has changed.
    """
    global _validated_profiles_cache, _cache_fingerprint
    _validated_profiles_cache = None
    _cache_fingerprint = None
    logger.debug("Profiles cache manually cleared")


def get_profiles_cache_info() -> Tuple[bool, Optional[str]]:
    """
    Get information about the current cache state.

    Returns:
        Tuple[bool, Optional[str]]: (is_cached, fingerprint_prefix)
            - is_cached: Whether profiles are currently cached
            - fingerprint_prefix: First 8 characters of cache fingerprint, or None
    """
    return (
        _validated_profiles_cache is not None,
        _cache_fingerprint[:8] if _cache_fingerprint else None,
    )
