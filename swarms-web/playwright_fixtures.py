"""Utilities for deterministic Playwright fixtures used in test mode."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List

_DATA_PATH = Path(__file__).resolve().parent / 'tests' / 'e2e' / 'mock-data.json'

def _load_fixture_payload() -> Dict[str, Any]:
    """
    Load and return the JSON fixture at _DATA_PATH as a dict.
    
    Attempts to open and parse the file located at the module-level _DATA_PATH. If the file is missing, contains invalid JSON, or the top-level value is not a JSON object (dict), an empty dict is returned instead of raising an exception.
    
    Returns:
        dict: Parsed JSON object on success, or an empty dict on error or invalid payload type.
    """
    try:
        with _DATA_PATH.open('r', encoding='utf-8') as handle:
            payload = json.load(handle)
    except FileNotFoundError:
        return {}
    except json.JSONDecodeError:
        return {}

    if not isinstance(payload, dict):
        return {}
    return payload


@lru_cache(maxsize=1)
def _get_cached_payload() -> Dict[str, Any]:
    """
    Return a normalized mock payload for deterministic test fixtures.
    
    Normalizes the raw JSON payload loaded from the fixture and returns a dict with three keys:
    - agents (List[Dict[str, str]]): A list of agent metadata dictionaries. Each agent has keys:
        - id: string identifier (defaults to "mock-agent-N" when missing or not a string)
        - name: display name (defaults to "Mock Agent N")
        - model: model name (defaults to "openai/gpt-4")
        - created_at: creation timestamp string (defaults to "2024-01-01")
      Non-dict entries in the raw 'agents' list are ignored; if 'agents' is missing or not a list, an empty list is returned.
    - secretary_minutes (str): The value of the raw 'secretaryMinutes' field if it is a string, otherwise an empty string.
    - agent_response (str): The value of the raw 'agentResponse' field if it is a string, otherwise an empty string.
    
    The returned payload is intended to be cached for repeated use in tests and provides deterministic, type-safe defaults for missing or malformed input.
    """
    payload = _load_fixture_payload()

    agents = payload.get('agents')
    if not isinstance(agents, list):
        agents = []

    normalized_agents: List[Dict[str, str]] = []
    for index, agent in enumerate(agents):
        if not isinstance(agent, dict):
            continue

        def _string_or(default: str, value: Any) -> str:
            """
            Return value if it is a string, otherwise return the provided default.
            
            Parameters:
                default (str): Fallback string to return when value is not a str.
                value (Any): Candidate value to check.
            
            Returns:
                str: value if it's a str, otherwise default.
            """
            return value if isinstance(value, str) else default

        normalized_agents.append(
            {
                'id': _string_or(f'mock-agent-{index + 1}', agent.get('id')),
                'name': _string_or(f'Mock Agent {index + 1}', agent.get('name')),
                'model': _string_or('openai/gpt-4', agent.get('model')),
                'created_at': _string_or('2024-01-01', agent.get('created_at')),
            }
        )

    secretary_minutes = payload.get('secretaryMinutes')
    agent_response = payload.get('agentResponse')

    return {
        'agents': normalized_agents,
        'secretary_minutes': secretary_minutes if isinstance(secretary_minutes, str) else '',
        'agent_response': agent_response if isinstance(agent_response, str) else '',
    }


def get_mock_agents() -> List[Dict[str, str]]:
    """
    Return a deterministic, shallow-copied list of agent metadata for Playwright tests.
    
    Each item is a dict with string fields: 'id', 'name', 'model', and 'created_at'. The data is loaded from a cached, normalized fixture and returned as new dict objects to avoid mutating the cached payload.
    
    Returns:
        List[Dict[str, str]]: A list of agent metadata dictionaries.
    """

    return [dict(agent) for agent in _get_cached_payload()['agents']]


def get_secretary_minutes() -> str:
    """Return the deterministic secretary minutes string for Playwright tests."""

    return _get_cached_payload()['secretary_minutes']


def get_agent_response() -> str:
    """
    Return the deterministic agent response text used by Playwright tests.
    
    Reads the normalized, cached fixture payload and returns the `agent_response` string.
    If the fixture is missing or `agentResponse` is not a string, an empty string is returned.
    """

    return _get_cached_payload()['agent_response']
