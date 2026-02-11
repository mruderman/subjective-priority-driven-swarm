"""Tests for spds.mcp_launchpad — MCP Launchpad tool discovery and execution."""

import json
from types import SimpleNamespace
from unittest.mock import Mock, patch, MagicMock

import pytest

from spds.mcp_config import MCPServerEntry
from spds.mcp_launchpad import MCPLaunchpad, _ECOSYSTEM_BLOCK_MAX_CHARS


def _make_entry(name="test-server", tier=1, server_type="stdio", **kwargs):
    """Helper to create an MCPServerEntry with defaults."""
    return MCPServerEntry(
        name=name,
        tier=tier,
        server_type=server_type,
        command=kwargs.get("command", "npx"),
        args=kwargs.get("args", []),
        url=kwargs.get("url", ""),
        scope=kwargs.get("scope", "universal"),
        description=kwargs.get("description", "Test server"),
        categories=kwargs.get("categories", []),
    )


def _make_mock_server(name, server_id="srv-123", tools=None):
    """Create a mock server object."""
    tool_objs = []
    if tools:
        for t in tools:
            tool_objs.append(SimpleNamespace(
                id=t.get("id", f"tool-{t['name']}"),
                name=t["name"],
                description=t.get("description", ""),
            ))
    return SimpleNamespace(
        id=server_id,
        server_name=name,
        name=name,
        tools=tool_objs,
    )


@pytest.fixture
def mock_client(mock_mcp_letta_client):
    """Alias for the MCP-extended mock client."""
    return mock_mcp_letta_client


class TestRegisterServers:
    def test_registers_new_server(self, mock_client):
        entry = _make_entry(name="seq-think")
        mock_client.mcp_servers.list.return_value = []
        mock_client.mcp_servers.create.return_value = SimpleNamespace(
            id="srv-new", server_name="seq-think"
        )

        lp = MCPLaunchpad(mock_client, [entry])
        results = lp.register_servers()

        assert results["seq-think"] is True
        mock_client.mcp_servers.create.assert_called_once()

    def test_reuses_existing_server(self, mock_client):
        entry = _make_entry(name="seq-think")
        existing = SimpleNamespace(id="srv-exist", server_name="seq-think", name="seq-think")
        mock_client.mcp_servers.list.return_value = [existing]

        lp = MCPLaunchpad(mock_client, [entry])
        results = lp.register_servers()

        assert results["seq-think"] is True
        mock_client.mcp_servers.create.assert_not_called()

    def test_handles_registration_failure(self, mock_client):
        entry = _make_entry(name="bad-server")
        mock_client.mcp_servers.list.return_value = []
        mock_client.mcp_servers.create.side_effect = RuntimeError("connection refused")

        lp = MCPLaunchpad(mock_client, [entry])
        results = lp.register_servers()

        assert results["bad-server"] is False

    def test_handles_list_failure(self, mock_client):
        entry = _make_entry(name="test")
        mock_client.mcp_servers.list.side_effect = RuntimeError("timeout")
        mock_client.mcp_servers.create.return_value = SimpleNamespace(
            id="srv-new", server_name="test"
        )

        lp = MCPLaunchpad(mock_client, [entry])
        results = lp.register_servers()

        # Should still attempt creation since existing list failed
        assert results["test"] is True


class TestBuildCatalog:
    def test_catalogs_server_tools(self, mock_client):
        entry = _make_entry(name="github", tier=2, server_type="sse")
        server = _make_mock_server("github", tools=[
            {"name": "create_issue", "description": "Create a GitHub issue"},
            {"name": "list_repos", "description": "List repositories"},
        ])

        lp = MCPLaunchpad(mock_client, [entry])
        lp._registered_servers["github"] = server
        mock_client.mcp_servers.retrieve.return_value = server

        catalog = lp.build_catalog()

        assert "github" in catalog
        assert len(catalog["github"]) == 2
        assert catalog["github"][0]["name"] == "create_issue"

    def test_handles_missing_server_id(self, mock_client):
        entry = _make_entry(name="bad")
        lp = MCPLaunchpad(mock_client, [entry])
        lp._registered_servers["bad"] = SimpleNamespace(server_name="bad")  # no .id

        catalog = lp.build_catalog()
        assert catalog == {}

    def test_handles_retrieve_failure(self, mock_client):
        entry = _make_entry(name="fail")
        lp = MCPLaunchpad(mock_client, [entry])
        lp._registered_servers["fail"] = SimpleNamespace(id="srv-fail", server_name="fail")
        mock_client.mcp_servers.retrieve.side_effect = RuntimeError("oops")

        catalog = lp.build_catalog()
        assert catalog["fail"] == []


class TestEcosystemContent:
    def test_generates_tier2_content(self, mock_client):
        entries = [
            _make_entry(name="github", tier=2, description="GitHub ops"),
        ]
        lp = MCPLaunchpad(mock_client, entries)
        lp._catalog = {
            "github": [
                {"name": "create_issue", "description": "Create issue"},
                {"name": "list_repos", "description": "List repos"},
            ],
        }

        content = lp.generate_ecosystem_content()
        assert "github" in content
        assert "create_issue" in content
        assert "list_repos" in content

    def test_excludes_tier1_from_content(self, mock_client):
        entries = [
            _make_entry(name="seq-think", tier=1),
        ]
        lp = MCPLaunchpad(mock_client, entries)
        lp._catalog = {
            "seq-think": [{"name": "think", "description": "Think sequentially"}],
        }

        content = lp.generate_ecosystem_content()
        # Tier 1 tools should not appear in ecosystem content
        assert "think" not in content or "seq-think" not in content

    def test_truncates_long_content(self, mock_client):
        entries = [_make_entry(name=f"srv-{i}", tier=2, description="X" * 200) for i in range(50)]
        lp = MCPLaunchpad(mock_client, entries)
        lp._catalog = {
            f"srv-{i}": [{"name": f"tool-{j}", "description": "D" * 80} for j in range(10)]
            for i in range(50)
        }

        content = lp.generate_ecosystem_content()
        assert len(content) <= _ECOSYSTEM_BLOCK_MAX_CHARS


class TestEcosystemBlock:
    def test_creates_new_block(self, mock_client):
        entry = _make_entry(name="test", tier=2)
        lp = MCPLaunchpad(mock_client, [entry])
        lp._catalog = {"test": []}

        mock_client.blocks.list.return_value = []
        mock_client.blocks.create.return_value = SimpleNamespace(id="block-new")

        block_id = lp.create_ecosystem_block()
        assert block_id == "block-new"
        mock_client.blocks.create.assert_called_once()

    def test_reuses_existing_block(self, mock_client):
        entry = _make_entry(name="test", tier=2)
        lp = MCPLaunchpad(mock_client, [entry])
        lp._catalog = {"test": []}

        existing = SimpleNamespace(id="block-existing")
        mock_client.blocks.list.return_value = [existing]

        block_id = lp.create_ecosystem_block()
        assert block_id == "block-existing"
        mock_client.blocks.create.assert_not_called()

    def test_attaches_to_agents(self, mock_client):
        entry = _make_entry(name="test", tier=2)
        lp = MCPLaunchpad(mock_client, [entry])
        lp._ecosystem_block_id = "block-123"

        lp.attach_ecosystem_block(["ag-1", "ag-2"])
        assert mock_client.agents.blocks.attach.call_count == 2


class TestTier1ToolAttachment:
    def test_attaches_tier1_tools(self, mock_client):
        entry = _make_entry(name="seq", tier=1)
        lp = MCPLaunchpad(mock_client, [entry])
        lp._catalog = {
            "seq": [{"id": "tool-think", "name": "think", "description": ""}],
        }

        lp.attach_tier1_tools(["ag-1", "ag-2"])
        assert mock_client.agents.tools.attach.call_count == 2

    def test_skips_when_disabled(self, mock_client, monkeypatch):
        monkeypatch.setenv("SPDS_MCP_TIER1_ENABLED", "false")
        entry = _make_entry(name="seq", tier=1)
        lp = MCPLaunchpad(mock_client, [entry])
        lp._catalog = {"seq": [{"id": "t1", "name": "think", "description": ""}]}

        lp.attach_tier1_tools(["ag-1"])
        mock_client.agents.tools.attach.assert_not_called()


class TestUseMcpToolRegistration:
    def test_registers_and_attaches(self, mock_client):
        entry = _make_entry(name="github", tier=2)
        lp = MCPLaunchpad(mock_client, [entry])

        mock_client.tools.list.return_value = []
        mock_client.tools.create_from_function.return_value = SimpleNamespace(id="tool-umt")

        lp.ensure_use_mcp_tool(["ag-1"])

        mock_client.tools.create_from_function.assert_called_once()
        assert lp._use_mcp_tool_id == "tool-umt"
        mock_client.agents.tools.attach.assert_called_once()

    def test_skips_when_no_tier2(self, mock_client):
        entry = _make_entry(name="seq", tier=1)
        lp = MCPLaunchpad(mock_client, [entry])

        lp.ensure_use_mcp_tool(["ag-1"])
        mock_client.tools.create_from_function.assert_not_called()

    def test_reuses_existing_tool(self, mock_client):
        entry = _make_entry(name="github", tier=2)
        lp = MCPLaunchpad(mock_client, [entry])

        existing = SimpleNamespace(id="tool-existing", name="use_mcp_tool")
        mock_client.tools.list.return_value = [existing]

        lp.ensure_use_mcp_tool(["ag-1"])
        mock_client.tools.create_from_function.assert_not_called()
        assert lp._use_mcp_tool_id == "tool-existing"


class TestFulfillAndExecute:
    def test_successful_execution(self, mock_client):
        entry = _make_entry(name="github", tier=2)
        lp = MCPLaunchpad(mock_client, [entry])
        lp._attached_tools["github/create_issue"] = "tool-ci"

        mock_client.agents.tools.run.return_value = SimpleNamespace(
            tool_return="Issue #42 created"
        )

        result = lp.fulfill_and_execute(
            "ag-1", "github", "create_issue", {"title": "Bug fix"}
        )
        assert "Issue #42 created" in result

    def test_unknown_tool_returns_error(self, mock_client):
        lp = MCPLaunchpad(mock_client, [])
        result = lp.fulfill_and_execute("ag-1", "unknown", "nonexistent", {})
        assert "Error" in result
        assert "Unknown tool" in result

    def test_execution_failure(self, mock_client):
        entry = _make_entry(name="github", tier=2)
        lp = MCPLaunchpad(mock_client, [entry])
        lp._attached_tools["github/create_issue"] = "tool-ci"

        mock_client.agents.tools.run.side_effect = RuntimeError("server error")

        result = lp.fulfill_and_execute(
            "ag-1", "github", "create_issue", {"title": "Bug"}
        )
        assert "Error executing" in result


class TestCatalogSummary:
    def test_empty_catalog(self, mock_client):
        lp = MCPLaunchpad(mock_client, [])
        assert "No MCP servers registered" in lp.get_catalog_summary()

    def test_summary_with_tools(self, mock_client):
        entry = _make_entry(name="github", tier=2, description="GitHub ops")
        lp = MCPLaunchpad(mock_client, [entry])
        lp._catalog = {
            "github": [
                {"name": "create_issue", "description": "Create issue"},
            ],
        }

        summary = lp.get_catalog_summary()
        assert "github" in summary
        assert "Tier 2" in summary
        assert "create_issue" in summary
        assert "GitHub ops" in summary


class TestRefreshCatalog:
    def test_rebuilds_and_updates_block(self, mock_client):
        entry = _make_entry(name="test", tier=2)
        server = _make_mock_server("test", tools=[
            {"name": "new_tool", "description": "Newly added"},
        ])
        lp = MCPLaunchpad(mock_client, [entry])
        lp._registered_servers["test"] = server
        lp._ecosystem_block_id = "block-123"
        mock_client.mcp_servers.retrieve.return_value = server

        lp.refresh_catalog()

        assert "test" in lp._catalog
        mock_client.blocks.update.assert_called_once()
