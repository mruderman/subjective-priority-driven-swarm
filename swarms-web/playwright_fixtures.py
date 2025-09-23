"""Utilities for deterministic Playwright fixtures used in test mode."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List

_DATA_PATH = Path(__file__).resolve().parent / 'tests' / 'e2e' / 'mock-data.json'

def _load_fixture_payload() -> Dict[str, Any]:
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
    payload = _load_fixture_payload()

    agents = payload.get('agents')
    if not isinstance(agents, list):
        agents = []

    normalized_agents: List[Dict[str, str]] = []
    for index, agent in enumerate(agents):
        if not isinstance(agent, dict):
            continue

        def _string_or(default: str, value: Any) -> str:
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
    """Return deterministic agent metadata for Playwright tests."""

    return [dict(agent) for agent in _get_cached_payload()['agents']]


def get_secretary_minutes() -> str:
    """Return the deterministic secretary minutes string for Playwright tests."""

    return _get_cached_payload()['secretary_minutes']


def get_agent_response() -> str:
    """Return the deterministic agent response text for Playwright tests."""

    return _get_cached_payload()['agent_response']
