"""Tests for the creative swarm configuration data."""

import json
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit


def test_creative_swarm_profiles_have_expected_structure():
    root = Path(__file__).resolve().parents[2]
    json_path = root / "creative_swarm.json"

    profiles = json.loads(json_path.read_text(encoding="utf-8"))
    assert isinstance(profiles, list)
    assert len(profiles) > 0

    for profile in profiles:
        assert profile["name"]
        assert profile["persona"]
        assert isinstance(profile["expertise"], list)
        assert all(isinstance(area, str) and area for area in profile["expertise"])
