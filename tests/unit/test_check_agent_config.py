"""
Unit tests for spds.diagnostics.check_agent_config module.

Tests cover the main diagnostic entry points:
- check_agent_by_name: Find agent by name and return config report
- check_agent_by_id: Retrieve agent details and build diagnostic report
- check_all_agents: Iterate all agents and collect reports
- check_tool_execution_env: Test server-side tool execution environment
"""

import logging
from types import SimpleNamespace
from unittest.mock import Mock, patch

import httpx
import pytest
from letta_client import NotFoundError
from letta_client.types import Tool

from tests.conftest import MockSyncArrayPage, _mk_agent_state

# Import the module under test (for monkeypatching letta_call)
import spds.diagnostics.check_agent_config as diag_module
from spds.diagnostics.check_agent_config import (
    MODELS_WITH_ISSUES,
    RECOMMENDED_MODELS,
    check_agent_by_id,
    check_agent_by_name,
    check_all_agents,
    check_tool_execution_env,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_not_found_error(message="Not found"):
    """Create a NotFoundError matching the letta_client 1.x constructor."""
    resp = httpx.Response(404, request=httpx.Request("GET", "http://test"))
    return NotFoundError(message, response=resp, body={"detail": message})


def _passthrough_letta_call(operation_name, fn, *args, **kwargs):
    """Replace letta_call with a simple passthrough (no retries/timeouts)."""
    # Strip the 'timeout' kwarg that letta_call would inject
    kwargs.pop("timeout", None)
    return fn(*args, **kwargs)


def _make_tools(*names):
    """Create a list of mock Tool objects with the given names."""
    return [
        Tool(id=f"tool-{i}", name=name, description=f"Tool {name}")
        for i, name in enumerate(names)
    ]


# ---------------------------------------------------------------------------
# TestCheckAgentByName
# ---------------------------------------------------------------------------


class TestCheckAgentByName:
    """Tests for check_agent_by_name function."""

    def test_check_agent_by_name_found(self, mock_letta_client, monkeypatch):
        """When an agent matching the name exists, return its config dict."""
        monkeypatch.setattr(diag_module, "letta_call", _passthrough_letta_call)

        agent = _mk_agent_state(
            id="ag-found-1",
            name="Alice",
            system="You are Alice.",
            model="openai/gpt-4.1",
        )
        # agents.list returns a SyncArrayPage-like object
        mock_letta_client.agents.list.return_value = MockSyncArrayPage([agent])

        # agents.retrieve returns full agent detail (called by check_agent_by_id)
        mock_letta_client.agents.retrieve.return_value = agent

        # agents.tools.list returns the agent's tools
        tools = _make_tools("send_message", "perform_subjective_assessment")
        mock_letta_client.agents.tools.list.return_value = tools

        result = check_agent_by_name(mock_letta_client, "Alice")

        # Should not have an error key
        assert "error" not in result
        # Should have standard config keys
        assert result["agent_id"] == "ag-found-1"
        assert result["agent_name"] == "Alice"
        assert result["model"] == "openai/gpt-4.1"
        assert "tools" in result
        assert "recommendations" in result

    def test_check_agent_by_name_not_found(self, mock_letta_client, monkeypatch):
        """When no agent matches the name, return an error dict."""
        monkeypatch.setattr(diag_module, "letta_call", _passthrough_letta_call)

        # Empty result set
        mock_letta_client.agents.list.return_value = MockSyncArrayPage([])

        result = check_agent_by_name(mock_letta_client, "NonExistent")

        assert "error" in result
        assert "not found" in result["error"].lower()
        assert result["agent_name"] == "NonExistent"
        assert "recommendations" in result
        assert len(result["recommendations"]) > 0

    def test_check_agent_by_name_multiple_matches(
        self, mock_letta_client, monkeypatch, caplog
    ):
        """When multiple agents share the same name, use first and log a warning."""
        monkeypatch.setattr(diag_module, "letta_call", _passthrough_letta_call)

        agent1 = _mk_agent_state(
            id="ag-dup-1", name="Duplicate", system="First", model="openai/gpt-4"
        )
        agent2 = _mk_agent_state(
            id="ag-dup-2", name="Duplicate", system="Second", model="openai/gpt-4"
        )
        mock_letta_client.agents.list.return_value = MockSyncArrayPage([agent1, agent2])
        mock_letta_client.agents.retrieve.return_value = agent1
        mock_letta_client.agents.tools.list.return_value = _make_tools("send_message")

        with caplog.at_level(logging.WARNING, logger="spds.diagnostics.check_agent_config"):
            result = check_agent_by_name(mock_letta_client, "Duplicate")

        # First match should be used
        assert result["agent_id"] == "ag-dup-1"
        # Warning should be logged
        assert any("Multiple agents" in msg for msg in caplog.messages)


# ---------------------------------------------------------------------------
# TestCheckAgentById
# ---------------------------------------------------------------------------


class TestCheckAgentById:
    """Tests for check_agent_by_id function."""

    def test_check_agent_by_id_returns_config(self, mock_letta_client, monkeypatch):
        """Verify the config dict has all expected keys."""
        monkeypatch.setattr(diag_module, "letta_call", _passthrough_letta_call)

        agent = _mk_agent_state(
            id="ag-cfg-1",
            name="ConfigTest",
            system="You are ConfigTest.",
            model="openai/gpt-4.1",
        )
        mock_letta_client.agents.retrieve.return_value = agent
        mock_letta_client.agents.tools.list.return_value = _make_tools(
            "send_message", "perform_subjective_assessment"
        )

        result = check_agent_by_id(mock_letta_client, "ag-cfg-1")

        # Required keys from the report
        expected_keys = {
            "agent_id",
            "agent_name",
            "model",
            "tools",
            "recommendations",
        }
        assert expected_keys.issubset(result.keys())
        assert result["agent_id"] == "ag-cfg-1"
        assert result["agent_name"] == "ConfigTest"
        assert result["model"] == "openai/gpt-4.1"
        assert "send_message" in result["tools"]
        assert "perform_subjective_assessment" in result["tools"]
        assert result["has_send_message"] is True
        assert result["has_assessment_tool"] is True

    def test_check_agent_by_id_not_found(self, mock_letta_client, monkeypatch):
        """When agents.retrieve raises NotFoundError, return an error dict."""
        monkeypatch.setattr(diag_module, "letta_call", _passthrough_letta_call)

        mock_letta_client.agents.retrieve.side_effect = _make_not_found_error(
            "Agent not found"
        )

        result = check_agent_by_id(mock_letta_client, "ag-missing-1")

        assert "error" in result
        assert result["agent_id"] == "ag-missing-1"
        assert "recommendations" in result
        assert len(result["recommendations"]) > 0

    def test_check_agent_by_id_recommended_model_no_warning(
        self, mock_letta_client, monkeypatch
    ):
        """A recommended model should produce a checks_passed entry, not a warning."""
        monkeypatch.setattr(diag_module, "letta_call", _passthrough_letta_call)

        recommended_model = RECOMMENDED_MODELS[0]
        agent = _mk_agent_state(
            id="ag-rec-1",
            name="RecModel",
            system="Test",
            model=recommended_model,
        )
        mock_letta_client.agents.retrieve.return_value = agent
        mock_letta_client.agents.tools.list.return_value = _make_tools("send_message")

        result = check_agent_by_id(mock_letta_client, "ag-rec-1")

        # Should have a checks_passed entry for the model
        assert any(
            recommended_model in check for check in result.get("checks_passed", [])
        )
        # No model-related warning
        model_warnings = [
            w for w in result.get("warnings", []) if "model" in w.lower()
        ]
        assert len(model_warnings) == 0

    def test_check_agent_by_id_non_recommended_model_warns(
        self, mock_letta_client, monkeypatch
    ):
        """A non-recommended model should produce a warning with recommendation."""
        monkeypatch.setattr(diag_module, "letta_call", _passthrough_letta_call)

        agent = _mk_agent_state(
            id="ag-unrec-1",
            name="UnrecModel",
            system="Test",
            model="some-unknown/model-v1",
        )
        mock_letta_client.agents.retrieve.return_value = agent
        mock_letta_client.agents.tools.list.return_value = _make_tools("send_message")

        result = check_agent_by_id(mock_letta_client, "ag-unrec-1")

        # Should have a model-related warning
        model_warnings = [
            w for w in result.get("warnings", []) if "model" in w.lower()
        ]
        assert len(model_warnings) > 0
        # Should have a recommendation for better models
        assert any(
            "best results" in rec.lower() or "use:" in rec.lower()
            for rec in result.get("recommendations", [])
        )

    def test_check_agent_by_id_known_issue_model_warns(
        self, mock_letta_client, monkeypatch
    ):
        """A model with known issues should produce a specific warning."""
        monkeypatch.setattr(diag_module, "letta_call", _passthrough_letta_call)

        issue_model = MODELS_WITH_ISSUES[0]
        agent = _mk_agent_state(
            id="ag-issue-1",
            name="IssueModel",
            system="Test",
            model=issue_model,
        )
        mock_letta_client.agents.retrieve.return_value = agent
        mock_letta_client.agents.tools.list.return_value = _make_tools("send_message")

        result = check_agent_by_id(mock_letta_client, "ag-issue-1")

        # Should mention known issues in warnings
        assert any(
            "known" in w.lower() and "issue" in w.lower()
            for w in result.get("warnings", [])
        )

    def test_check_agent_by_id_missing_send_message(
        self, mock_letta_client, monkeypatch
    ):
        """Missing send_message tool should produce an issue."""
        monkeypatch.setattr(diag_module, "letta_call", _passthrough_letta_call)

        agent = _mk_agent_state(
            id="ag-nosend-1", name="NoSend", system="Test", model="openai/gpt-4"
        )
        mock_letta_client.agents.retrieve.return_value = agent
        # No send_message in tools
        mock_letta_client.agents.tools.list.return_value = _make_tools(
            "some_other_tool"
        )

        result = check_agent_by_id(mock_letta_client, "ag-nosend-1")

        assert result["has_send_message"] is False
        assert any("send_message" in issue for issue in result.get("issues", []))

    def test_check_agent_by_id_missing_assessment_tool(
        self, mock_letta_client, monkeypatch
    ):
        """Missing assessment tool should produce a warning (not an issue)."""
        monkeypatch.setattr(diag_module, "letta_call", _passthrough_letta_call)

        agent = _mk_agent_state(
            id="ag-noassess-1", name="NoAssess", system="Test", model="openai/gpt-4"
        )
        mock_letta_client.agents.retrieve.return_value = agent
        mock_letta_client.agents.tools.list.return_value = _make_tools("send_message")

        result = check_agent_by_id(mock_letta_client, "ag-noassess-1")

        assert result["has_assessment_tool"] is False
        assert any(
            "assessment" in w.lower() for w in result.get("warnings", [])
        )


# ---------------------------------------------------------------------------
# TestCheckAllAgents
# ---------------------------------------------------------------------------


class TestCheckAllAgents:
    """Tests for check_all_agents function."""

    def test_check_all_agents(self, mock_letta_client, monkeypatch):
        """Two agents on the server should produce a list of two report dicts."""
        monkeypatch.setattr(diag_module, "letta_call", _passthrough_letta_call)

        agent1 = _mk_agent_state(
            id="ag-all-1", name="Agent1", system="Test", model="openai/gpt-4"
        )
        agent2 = _mk_agent_state(
            id="ag-all-2", name="Agent2", system="Test", model="openai/gpt-4"
        )
        mock_letta_client.agents.list.return_value = MockSyncArrayPage([agent1, agent2])

        # agents.retrieve returns the corresponding agent
        def retrieve_side_effect(**kwargs):
            aid = kwargs.get("agent_id")
            if aid == "ag-all-1":
                return agent1
            return agent2

        mock_letta_client.agents.retrieve.side_effect = retrieve_side_effect
        mock_letta_client.agents.tools.list.return_value = _make_tools("send_message")

        reports = check_all_agents(mock_letta_client)

        assert isinstance(reports, list)
        assert len(reports) == 2
        ids = {r["agent_id"] for r in reports}
        assert ids == {"ag-all-1", "ag-all-2"}
        # Each report should have standard keys
        for report in reports:
            assert "agent_name" in report
            assert "model" in report
            assert "recommendations" in report

    def test_check_all_agents_empty(self, mock_letta_client, monkeypatch):
        """Empty agent list should return an empty report list."""
        monkeypatch.setattr(diag_module, "letta_call", _passthrough_letta_call)

        mock_letta_client.agents.list.return_value = MockSyncArrayPage([])

        reports = check_all_agents(mock_letta_client)

        assert isinstance(reports, list)
        assert len(reports) == 0


# ---------------------------------------------------------------------------
# TestCheckToolExecutionEnv
# ---------------------------------------------------------------------------


class TestCheckToolExecutionEnv:
    """Tests for check_tool_execution_env function."""

    def test_check_tool_execution_env_success(self, mock_letta_client, monkeypatch):
        """Successful tool creation/run/cleanup should return 'passed' status."""
        monkeypatch.setattr(diag_module, "letta_call", _passthrough_letta_call)

        # Mock the tool creation returning a tool with an id
        created_tool = SimpleNamespace(id="tool-diag-123", name="test_tool_function")
        mock_letta_client.tools.create_from_function.return_value = created_tool
        mock_letta_client.tools.delete = Mock()

        result = check_tool_execution_env(mock_letta_client)

        assert result["status"] == "passed"
        assert "test_name" in result
        assert any("successful" in c.lower() for c in result.get("checks_passed", []))
        # Cleanup should have been attempted
        mock_letta_client.tools.delete.assert_called_once_with(tool_id="tool-diag-123")

    def test_check_tool_execution_env_failure(self, mock_letta_client, monkeypatch):
        """Tool creation failure should return 'failed' status with issues."""
        monkeypatch.setattr(diag_module, "letta_call", _passthrough_letta_call)

        # Simulate tool creation failing (e.g., pydantic not available on server)
        mock_letta_client.tools.create_from_function.side_effect = RuntimeError(
            "ModuleNotFoundError: No module named 'pydantic'"
        )

        result = check_tool_execution_env(mock_letta_client)

        assert result["status"] == "failed"
        assert len(result.get("issues", [])) > 0
        assert len(result.get("recommendations", [])) > 0
        # Should detect pydantic-specific failure
        assert any("pydantic" in issue.lower() for issue in result["issues"])

    def test_check_tool_execution_env_generic_failure(
        self, mock_letta_client, monkeypatch
    ):
        """Non-pydantic failure should still report failure with generic message."""
        monkeypatch.setattr(diag_module, "letta_call", _passthrough_letta_call)

        mock_letta_client.tools.create_from_function.side_effect = RuntimeError(
            "Connection refused"
        )

        result = check_tool_execution_env(mock_letta_client)

        assert result["status"] == "failed"
        assert len(result.get("issues", [])) > 0
        # Should NOT mention pydantic for a generic error
        assert not any("pydantic" in issue.lower() for issue in result["issues"])
