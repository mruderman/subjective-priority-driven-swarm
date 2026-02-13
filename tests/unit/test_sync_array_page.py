"""
Regression tests for SyncArrayPage compatibility.

The Letta SDK 1.7.x returns ``SyncArrayPage[T]`` from ``.list()`` methods.
This object is iterable but NOT subscriptable (no ``page[0]``, no ``len(page)``).
Five locations in the codebase were fixed to wrap results in ``list()`` to avoid
``TypeError: 'SyncArrayPage[Tool]' object is not subscriptable`` errors.

These tests use ``MockSyncArrayPage`` from conftest.py to verify that each
module handles paginated results correctly via ``list()`` wrapping.
"""

from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest
from letta_client.types import (
    AgentState,
    EmbeddingConfig,
    LlmConfig,
    Tool,
)
from letta_client.types.agent_state import Memory

from tests.conftest import MockSyncArrayPage


# ============================================================================
# Helper Functions
# ============================================================================


def _mk_agent_state(
    id: str, name: str, system: str = "Test", model: str = "openai/gpt-4"
):
    """Build a minimally valid AgentState."""
    llm = LlmConfig(model=model, model_endpoint_type="openai", context_window=128000)
    emb = EmbeddingConfig(
        embedding_endpoint_type="openai",
        embedding_model="openai/text-embedding-ada-002",
        embedding_dim=1536,
    )
    mem = Memory(blocks=[])
    return AgentState(
        id=id,
        name=name,
        system=system,
        agent_type="react_agent",
        llm_config=llm,
        embedding_config=emb,
        memory=mem,
        blocks=[],
        tools=[],
        sources=[],
        tags=[],
        model=model,
        embedding="openai/text-embedding-ada-002",
    )


# ============================================================================
# MockSyncArrayPage unit tests
# ============================================================================


class TestMockSyncArrayPage:
    """Verify MockSyncArrayPage faithfully mimics real SyncArrayPage behavior."""

    def test_mock_sync_array_page_iterable(self):
        """SyncArrayPage supports iteration via for-loop."""
        items = ["a", "b", "c"]
        page = MockSyncArrayPage(items)
        collected = []
        for item in page:
            collected.append(item)
        assert collected == ["a", "b", "c"]

    def test_mock_sync_array_page_not_subscriptable(self):
        """SyncArrayPage raises TypeError on subscript access (page[0])."""
        page = MockSyncArrayPage(["a", "b"])
        with pytest.raises(TypeError, match="not subscriptable"):
            _ = page[0]

    def test_mock_sync_array_page_no_len(self):
        """SyncArrayPage raises TypeError on len()."""
        page = MockSyncArrayPage(["a", "b"])
        with pytest.raises(TypeError, match="has no len"):
            len(page)

    def test_mock_sync_array_page_list_conversion(self):
        """list(page) correctly converts SyncArrayPage to a plain list."""
        items = [1, 2, 3]
        page = MockSyncArrayPage(items)
        result = list(page)
        assert result == [1, 2, 3]
        assert isinstance(result, list)

    def test_mock_sync_array_page_empty(self):
        """An empty SyncArrayPage is falsy and iterates to empty list."""
        page = MockSyncArrayPage([])
        assert not page  # falsy
        assert list(page) == []

    def test_mock_sync_array_page_truthy_when_non_empty(self):
        """A non-empty SyncArrayPage is truthy (supports truthiness checks)."""
        page = MockSyncArrayPage(["x"])
        assert page  # truthy

    def test_mock_sync_array_page_multiple_iterations(self):
        """SyncArrayPage can be iterated multiple times (unlike a generator)."""
        page = MockSyncArrayPage([10, 20])
        assert list(page) == [10, 20]
        assert list(page) == [10, 20]  # second iteration works


# ============================================================================
# Regression tests: modules that were fixed to wrap list() around SDK results
# ============================================================================


class TestSPDSAgentFindToolHandlesPaginated:
    """spds_agent.py: _find_tool_by_name wraps tools.list result in list()."""

    def test_find_tool_by_name_handles_paginated(self, mock_letta_client):
        """_find_tool_by_name works when client.tools.list returns a SyncArrayPage."""
        tool = Tool(
            id="tool-assess-123",
            name="perform_subjective_assessment",
            description="Assessment tool",
        )

        # Return a MockSyncArrayPage instead of a plain list
        mock_letta_client.tools.list.return_value = MockSyncArrayPage([tool])

        # Create agent with the tool already attached so _ensure_assessment_tool
        # finds it without calling create_from_function
        agent_state = _mk_agent_state(
            id="ag-1",
            name="TestAgent",
            system="You are TestAgent. Your persona is: Tester. Your expertise is in: testing.",
        )

        from spds.spds_agent import SPDSAgent

        agent = SPDSAgent(agent_state, mock_letta_client)

        # Now test _find_tool_by_name directly with paginated results
        mock_letta_client.tools.list.return_value = MockSyncArrayPage([tool])
        result = agent._find_tool_by_name("perform_subjective_assessment")

        assert result is not None
        assert result.id == "tool-assess-123"
        assert result.name == "perform_subjective_assessment"

    def test_find_tool_by_name_handles_empty_paginated(self, mock_letta_client):
        """_find_tool_by_name returns None when SyncArrayPage is empty."""
        mock_letta_client.tools.list.return_value = MockSyncArrayPage([])

        agent_state = _mk_agent_state(
            id="ag-2",
            name="TestAgent2",
            system="You are TestAgent2. Your persona is: Tester. Your expertise is in: testing.",
        )

        from spds.spds_agent import SPDSAgent

        agent = SPDSAgent(agent_state, mock_letta_client)

        mock_letta_client.tools.list.return_value = MockSyncArrayPage([])
        result = agent._find_tool_by_name("nonexistent_tool")

        assert result is None


class TestSwarmManagerLoadAgentsHandlesPaginated:
    """swarm_manager.py: _load_agents_by_name wraps agents.list result in list()."""

    def test_load_agents_by_name_handles_paginated(
        self, mock_letta_client, sample_agent_profiles
    ):
        """_load_agents_by_name works when client.agents.list returns a SyncArrayPage."""
        from spds.swarm_manager import SwarmManager

        agent_state = _mk_agent_state(
            id="ag-found-1",
            name="Test Agent 1",
            system="You are Test Agent 1. Your persona is: A test agent. Your expertise is in: testing.",
        )

        # client.agents.list returns MockSyncArrayPage containing one agent
        mock_letta_client.agents.list.return_value = MockSyncArrayPage([agent_state])

        with patch("spds.swarm_manager.SPDSAgent") as mock_spds_cls:
            mock_agent_instance = Mock()
            mock_agent_instance.name = "Test Agent 1"
            mock_agent_instance.agent = agent_state
            mock_agent_instance.roles = []
            mock_spds_cls.return_value = mock_agent_instance

            manager = SwarmManager.__new__(SwarmManager)
            manager.client = mock_letta_client
            manager.agents = []
            manager.conversation_mode = "hybrid"
            manager._secretary = None
            manager.secretary_agent_id = None
            manager.pending_nomination = None
            manager._cross_agent_info = None
            manager.session_id = "test-session-id"
            manager._event_callback = None
            manager._export_manager = None

            manager._load_agents_by_name(["Test Agent 1"])

            assert len(manager.agents) == 1
            mock_spds_cls.assert_called_once_with(agent_state, mock_letta_client)

    def test_load_agents_by_name_skips_missing_paginated(self, mock_letta_client):
        """_load_agents_by_name skips names that return empty SyncArrayPage."""
        from spds.swarm_manager import SwarmManager

        # Return empty SyncArrayPage (agent not found)
        mock_letta_client.agents.list.return_value = MockSyncArrayPage([])

        manager = SwarmManager.__new__(SwarmManager)
        manager.client = mock_letta_client
        manager.agents = []
        manager.conversation_mode = "hybrid"
        manager._secretary = None
        manager.secretary_agent_id = None
        manager.pending_nomination = None
        manager._cross_agent_info = None
        manager.session_id = "test-session-id"
        manager._event_callback = None
        manager._export_manager = None

        manager._load_agents_by_name(["Nonexistent Agent"])

        assert len(manager.agents) == 0


class TestMCPLaunchpadBlocksListHandlesPaginated:
    """mcp_launchpad.py: create_ecosystem_block wraps blocks.list result in list()."""

    def test_create_ecosystem_block_handles_paginated(self, mock_mcp_letta_client):
        """create_ecosystem_block works when blocks.list returns a SyncArrayPage."""
        from spds.mcp_config import MCPServerEntry
        from spds.mcp_launchpad import MCPLaunchpad

        entry = MCPServerEntry(
            name="test-server",
            tier=2,
            server_type="sse",
            command="",
            args=[],
            url="http://localhost:3002/sse",
            scope="universal",
            description="Test server",
            categories=[],
        )

        existing_block = SimpleNamespace(id="block-existing-123", label="tool_ecosystem")

        # blocks.list returns MockSyncArrayPage with an existing block
        mock_mcp_letta_client.blocks.list.return_value = MockSyncArrayPage(
            [existing_block]
        )

        lp = MCPLaunchpad(mock_mcp_letta_client, [entry])
        block_id = lp.create_ecosystem_block()

        assert block_id == "block-existing-123"
        # Should reuse existing block, not create a new one
        mock_mcp_letta_client.blocks.create.assert_not_called()

    def test_create_ecosystem_block_creates_when_paginated_empty(
        self, mock_mcp_letta_client
    ):
        """create_ecosystem_block creates new block when blocks.list returns empty SyncArrayPage."""
        from spds.mcp_config import MCPServerEntry
        from spds.mcp_launchpad import MCPLaunchpad

        entry = MCPServerEntry(
            name="test-server",
            tier=2,
            server_type="sse",
            command="",
            args=[],
            url="http://localhost:3002/sse",
            scope="universal",
            description="Test server",
            categories=[],
        )

        # blocks.list returns empty MockSyncArrayPage (no existing block)
        mock_mcp_letta_client.blocks.list.return_value = MockSyncArrayPage([])

        lp = MCPLaunchpad(mock_mcp_letta_client, [entry])
        block_id = lp.create_ecosystem_block()

        assert block_id == "block-eco-123"  # from mock_mcp_letta_client fixture
        mock_mcp_letta_client.blocks.create.assert_called_once()


class TestSecretaryAgentHandlesPaginated:
    """secretary_agent.py: from_existing wraps agents.list result in list()."""

    def test_secretary_from_existing_by_name_handles_paginated(
        self, mock_letta_client, monkeypatch
    ):
        """SecretaryAgent._create_secretary_agent works with SyncArrayPage from agents.list."""
        from spds.secretary_agent import SecretaryAgent

        agent_state = _mk_agent_state(
            id="ag-sec-1",
            name="Secretary Bot",
            system="You are Secretary Bot. Your persona is: A meeting secretary. Your expertise is in: documentation.",
        )

        # Set up env vars for secretary name lookup (reuse-first policy)
        monkeypatch.setenv("SECRETARY_AGENT_NAME", "Secretary Bot")
        monkeypatch.delenv("SECRETARY_AGENT_ID", raising=False)

        # agents.list returns MockSyncArrayPage
        mock_letta_client.agents.list.return_value = MockSyncArrayPage([agent_state])

        sec = SecretaryAgent(mock_letta_client, mode="adaptive")

        # The agent should have been found via the paginated list
        assert sec.agent.id == "ag-sec-1"


class TestDiagnosticsHandlesPaginated:
    """diagnostics/check_agent_config.py: check_agent_by_name wraps agents in list()."""

    def test_check_agent_by_name_handles_paginated(self, mock_letta_client):
        """check_agent_by_name works when agents.list returns a SyncArrayPage."""
        from spds.diagnostics.check_agent_config import check_agent_by_name

        agent_state = _mk_agent_state(
            id="ag-diag-1",
            name="DiagAgent",
            system="You are DiagAgent. Your persona is: Diagnostic. Your expertise is in: analysis.",
        )

        # agents.list returns MockSyncArrayPage
        mock_letta_client.agents.list.return_value = MockSyncArrayPage([agent_state])

        # Mock agents.retrieve to return agent details (called by check_agent_by_id)
        mock_letta_client.agents.retrieve.return_value = agent_state

        result = check_agent_by_name(mock_letta_client, "DiagAgent")

        assert result["agent_id"] == "ag-diag-1"
        assert result["agent_name"] == "DiagAgent"

    def test_check_agent_by_name_empty_paginated(self, mock_letta_client):
        """check_agent_by_name returns error dict when SyncArrayPage is empty."""
        from spds.diagnostics.check_agent_config import check_agent_by_name

        mock_letta_client.agents.list.return_value = MockSyncArrayPage([])

        result = check_agent_by_name(mock_letta_client, "MissingAgent")

        assert "error" in result
