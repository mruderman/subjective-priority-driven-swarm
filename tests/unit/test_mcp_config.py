"""Tests for spds.mcp_config — MCP server configuration loading."""

import json
import os
from pathlib import Path
from types import SimpleNamespace

import pytest

from spds.mcp_config import (
    MCPServerEntry,
    _resolve_env_vars,
    entry_to_letta_config,
    load_mcp_config,
)


@pytest.fixture
def config_file(tmp_path):
    """Create a temporary mcp-servers.json and return its path."""
    data = {
        "tier1": {
            "sequential-thinking": {
                "type": "stdio",
                "command": "npx",
                "args": ["-y", "@anthropic/mcp-sequential-thinking"],
                "scope": "universal",
                "description": "Sequential reasoning",
            }
        },
        "tier2": {
            "github": {
                "type": "sse",
                "url": "http://localhost:3002/sse",
                "scope": "universal",
                "description": "GitHub operations",
                "categories": ["vcs"],
            }
        },
    }
    path = tmp_path / "mcp-servers.json"
    path.write_text(json.dumps(data))
    return str(path)


class TestLoadMcpConfig:
    def test_valid_json_parsing(self, config_file):
        entries = load_mcp_config(config_file)
        assert len(entries) == 2
        tier1 = [e for e in entries if e.tier == 1]
        tier2 = [e for e in entries if e.tier == 2]
        assert len(tier1) == 1
        assert len(tier2) == 1
        assert tier1[0].name == "sequential-thinking"
        assert tier2[0].name == "github"

    def test_tier_separation(self, config_file):
        entries = load_mcp_config(config_file)
        st = next(e for e in entries if e.name == "sequential-thinking")
        gh = next(e for e in entries if e.name == "github")
        assert st.tier == 1
        assert gh.tier == 2
        assert st.server_type == "stdio"
        assert gh.server_type == "sse"

    def test_stdio_entry_fields(self, config_file):
        entries = load_mcp_config(config_file)
        st = next(e for e in entries if e.name == "sequential-thinking")
        assert st.command == "npx"
        assert st.args == ["-y", "@anthropic/mcp-sequential-thinking"]
        assert st.scope == "universal"
        assert st.description == "Sequential reasoning"

    def test_sse_entry_fields(self, config_file):
        entries = load_mcp_config(config_file)
        gh = next(e for e in entries if e.name == "github")
        assert gh.url == "http://localhost:3002/sse"
        assert gh.categories == ["vcs"]

    def test_missing_file_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            load_mcp_config(str(tmp_path / "nonexistent.json"))

    def test_invalid_json_raises(self, tmp_path):
        bad = tmp_path / "bad.json"
        bad.write_text("{not valid json")
        with pytest.raises(json.JSONDecodeError):
            load_mcp_config(str(bad))

    def test_unknown_type_skipped(self, tmp_path):
        data = {
            "tier1": {
                "unknown-server": {
                    "type": "websocket",
                    "url": "ws://localhost:8080",
                }
            },
            "tier2": {},
        }
        path = tmp_path / "mcp-servers.json"
        path.write_text(json.dumps(data))
        entries = load_mcp_config(str(path))
        assert len(entries) == 0

    def test_empty_tiers(self, tmp_path):
        data = {"tier1": {}, "tier2": {}}
        path = tmp_path / "mcp-servers.json"
        path.write_text(json.dumps(data))
        entries = load_mcp_config(str(path))
        assert entries == []


class TestEnvVarResolution:
    def test_env_var_resolved(self, monkeypatch):
        monkeypatch.setenv("MY_TOKEN", "secret123")
        assert _resolve_env_vars("Bearer ${MY_TOKEN}") == "Bearer secret123"

    def test_env_var_with_default(self):
        result = _resolve_env_vars("${NONEXISTENT_VAR:-fallback}")
        assert result == "fallback"

    def test_unset_env_var_no_default_preserved(self, monkeypatch):
        monkeypatch.delenv("TOTALLY_MISSING", raising=False)
        result = _resolve_env_vars("${TOTALLY_MISSING}")
        assert result == "${TOTALLY_MISSING}"

    def test_env_in_config(self, tmp_path, monkeypatch):
        monkeypatch.setenv("GH_TOKEN", "ghp_abc")
        data = {
            "tier1": {},
            "tier2": {
                "github": {
                    "type": "sse",
                    "url": "http://localhost:3002/sse",
                    "env": {"GITHUB_TOKEN": "${GH_TOKEN}"},
                }
            },
        }
        path = tmp_path / "mcp-servers.json"
        path.write_text(json.dumps(data))
        entries = load_mcp_config(str(path))
        assert entries[0].env["GITHUB_TOKEN"] == "ghp_abc"


class TestEntryToLettaConfig:
    def test_stdio_config(self):
        entry = MCPServerEntry(
            name="test", tier=1, server_type="stdio",
            command="npx", args=["-y", "test-pkg"],
        )
        config = entry_to_letta_config(entry)
        # Letta SDK config types are TypedDicts (dict subclasses)
        assert config["command"] == "npx"
        assert config["args"] == ["-y", "test-pkg"]
        assert config["mcp_server_type"] == "stdio"

    def test_sse_config(self):
        entry = MCPServerEntry(
            name="test", tier=2, server_type="sse",
            url="http://localhost:3002/sse",
        )
        config = entry_to_letta_config(entry)
        assert config["sse_url"] == "http://localhost:3002/sse"
        assert config["mcp_server_type"] == "sse"

    def test_unsupported_type_raises(self):
        entry = MCPServerEntry(name="test", tier=1, server_type="unknown")
        with pytest.raises(ValueError, match="Unsupported"):
            entry_to_letta_config(entry)
