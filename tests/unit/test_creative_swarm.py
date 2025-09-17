"""Tests for the creative swarm configuration data."""
import ast
import importlib.util
from pathlib import Path
import pytest

pytestmark = pytest.mark.unit

def test_creative_swarm_profiles_have_expected_structure():
    root = Path(__file__).resolve().parents[2]
    module_path = root / "spds" / "creative-swarm.py"

    spec = importlib.util.spec_from_file_location("spds.creative_swarm_data", module_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # Execute module for coverage

    profiles = ast.literal_eval(module_path.read_text())

    assert isinstance(profiles, list)
    assert {profile["name"] for profile in profiles} == {"Lyra", "Orion", "Scribe"}

    for profile in profiles:
        assert profile["persona"]
        assert isinstance(profile["expertise"], list)
        assert all(isinstance(area, str) and area for area in profile["expertise"])
