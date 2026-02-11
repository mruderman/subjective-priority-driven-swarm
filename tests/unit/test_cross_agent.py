"""Unit tests for spds.cross_agent — cross-agent messaging setup."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, Mock, call, patch

import pytest

from spds import cross_agent
from spds.cross_agent import (
    SESSION_TAG_PREFIX,
    attach_block_to_agents,
    attach_multi_agent_tools,
    create_swarm_context_block,
    make_session_tag,
    remove_session_tags,
    setup_cross_agent_messaging,
    tag_agents_for_session,
    teardown_cross_agent_messaging,
    update_swarm_context,
)

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mock_client():
    """Create a mock Letta client with agents, tools, and blocks resources."""
    client = MagicMock()
    return client


def _agent_state(agent_id: str, tags=None, tools=None):
    """Create a mock agent state."""
    state = SimpleNamespace(
        id=agent_id,
        tags=tags or [],
        tools=tools or [],
    )
    return state


# ---------------------------------------------------------------------------
# make_session_tag
# ---------------------------------------------------------------------------


class TestMakeSessionTag:
    def test_creates_prefixed_tag(self):
        tag = make_session_tag("abc-123")
        assert tag == f"{SESSION_TAG_PREFIX}abc-123"

    def test_includes_session_id(self):
        tag = make_session_tag("my-session")
        assert "my-session" in tag


# ---------------------------------------------------------------------------
# tag_agents_for_session
# ---------------------------------------------------------------------------


class TestTagAgentsForSession:
    def test_tags_agents(self):
        client = _mock_client()
        client.agents.retrieve.return_value = _agent_state("agent-1", tags=[])

        tag = tag_agents_for_session(client, ["agent-1"], "sess-1")

        assert tag == make_session_tag("sess-1")
        client.agents.update.assert_called_once()
        update_kwargs = client.agents.update.call_args
        assert make_session_tag("sess-1") in update_kwargs.kwargs.get(
            "tags", update_kwargs[1].get("tags", [])
        )

    def test_skips_already_tagged(self):
        client = _mock_client()
        existing_tag = make_session_tag("sess-1")
        client.agents.retrieve.return_value = _agent_state(
            "agent-1", tags=[existing_tag]
        )

        tag_agents_for_session(client, ["agent-1"], "sess-1")

        client.agents.update.assert_not_called()

    def test_handles_error_gracefully(self):
        client = _mock_client()
        client.agents.retrieve.side_effect = Exception("Server error")

        # Should not raise
        tag = tag_agents_for_session(client, ["agent-1"], "sess-1")
        assert tag == make_session_tag("sess-1")

    def test_tags_multiple_agents(self):
        client = _mock_client()
        client.agents.retrieve.return_value = _agent_state("a", tags=[])

        tag_agents_for_session(client, ["a-1", "a-2", "a-3"], "sess-1")

        assert client.agents.retrieve.call_count == 3
        assert client.agents.update.call_count == 3


# ---------------------------------------------------------------------------
# remove_session_tags
# ---------------------------------------------------------------------------


class TestRemoveSessionTags:
    def test_removes_tag(self):
        client = _mock_client()
        tag = make_session_tag("sess-1")
        client.agents.retrieve.return_value = _agent_state(
            "agent-1", tags=[tag, "other-tag"]
        )

        remove_session_tags(client, ["agent-1"], "sess-1")

        update_kwargs = client.agents.update.call_args
        tags_sent = update_kwargs.kwargs.get("tags", update_kwargs[1].get("tags"))
        assert tag not in tags_sent
        assert "other-tag" in tags_sent

    def test_noop_when_tag_not_present(self):
        client = _mock_client()
        client.agents.retrieve.return_value = _agent_state(
            "agent-1", tags=["other-tag"]
        )

        remove_session_tags(client, ["agent-1"], "sess-1")

        client.agents.update.assert_not_called()

    def test_handles_error_gracefully(self):
        client = _mock_client()
        client.agents.retrieve.side_effect = Exception("Server error")

        # Should not raise
        remove_session_tags(client, ["agent-1"], "sess-1")


# ---------------------------------------------------------------------------
# attach_multi_agent_tools
# ---------------------------------------------------------------------------


class TestAttachMultiAgentTools:
    def test_finds_and_attaches_tool(self):
        client = _mock_client()
        tool_obj = SimpleNamespace(id="tool-async-123", name="send_message_to_agent_async")
        client.tools.list.return_value = [tool_obj]
        client.agents.retrieve.return_value = _agent_state("agent-1", tools=[])

        result = attach_multi_agent_tools(client, ["agent-1"])

        assert result is True
        client.agents.tools.attach.assert_called_once_with(
            agent_id="agent-1", tool_id="tool-async-123"
        )

    def test_skips_already_attached(self):
        client = _mock_client()
        tool_obj = SimpleNamespace(id="tool-async-123", name="send_message_to_agent_async")
        client.tools.list.return_value = [tool_obj]
        existing_tool = SimpleNamespace(name="send_message_to_agent_async")
        client.agents.retrieve.return_value = _agent_state(
            "agent-1", tools=[existing_tool]
        )

        result = attach_multi_agent_tools(client, ["agent-1"])

        assert result is True
        client.agents.tools.attach.assert_not_called()

    def test_returns_false_when_tool_not_found(self):
        client = _mock_client()
        client.tools.list.return_value = []  # No multi-agent tools

        result = attach_multi_agent_tools(client, ["agent-1"])

        assert result is False

    def test_handles_attachment_error(self):
        client = _mock_client()
        tool_obj = SimpleNamespace(id="tool-async-123", name="send_message_to_agent_async")
        client.tools.list.return_value = [tool_obj]
        client.agents.retrieve.return_value = _agent_state("agent-1", tools=[])
        client.agents.tools.attach.side_effect = Exception("Attach failed")

        result = attach_multi_agent_tools(client, ["agent-1"])

        # Returns False because no agent was successfully attached
        assert result is False

    def test_multiple_agents_partial_success(self):
        client = _mock_client()
        tool_obj = SimpleNamespace(id="tool-async-123", name="send_message_to_agent_async")
        client.tools.list.return_value = [tool_obj]

        # First agent succeeds, second fails
        client.agents.retrieve.side_effect = [
            _agent_state("a-1", tools=[]),
            Exception("Not found"),
        ]

        result = attach_multi_agent_tools(client, ["a-1", "a-2"])

        assert result is True  # At least one succeeded


# ---------------------------------------------------------------------------
# create_swarm_context_block
# ---------------------------------------------------------------------------


class TestCreateSwarmContextBlock:
    def test_creates_block(self):
        client = _mock_client()
        block = SimpleNamespace(id="block-ctx-1")
        client.blocks.create.return_value = block

        result = create_swarm_context_block(
            client,
            topic="AI Strategy",
            participant_names=["Alice", "Bob"],
            session_id="sess-1",
        )

        assert result == "block-ctx-1"
        create_kwargs = client.blocks.create.call_args.kwargs
        assert create_kwargs["label"] == "swarm_context"
        assert "AI Strategy" in create_kwargs["value"]
        assert "Alice" in create_kwargs["value"]
        assert "Bob" in create_kwargs["value"]
        assert "sess-1" in create_kwargs["value"]

    def test_includes_extra_metadata(self):
        client = _mock_client()
        client.blocks.create.return_value = SimpleNamespace(id="block-1")

        create_swarm_context_block(
            client,
            topic="Test",
            participant_names=["A"],
            session_id="s-1",
            extra={"Conversation mode": "hybrid"},
        )

        value = client.blocks.create.call_args.kwargs["value"]
        assert "Conversation mode: hybrid" in value

    def test_handles_error(self):
        client = _mock_client()
        client.blocks.create.side_effect = Exception("Block creation failed")

        result = create_swarm_context_block(
            client, topic="Test", participant_names=["A"], session_id="s-1"
        )

        assert result is None


# ---------------------------------------------------------------------------
# attach_block_to_agents
# ---------------------------------------------------------------------------


class TestAttachBlockToAgents:
    def test_attaches_block(self):
        client = _mock_client()
        client.agents.retrieve.return_value = SimpleNamespace(memory=None)

        count = attach_block_to_agents(client, "block-1", ["a-1", "a-2"])

        assert count == 2
        assert client.agents.blocks.attach.call_count == 2

    def test_handles_error(self):
        client = _mock_client()
        client.agents.retrieve.side_effect = Exception("Not found")

        count = attach_block_to_agents(client, "block-1", ["a-1"])

        assert count == 0


# ---------------------------------------------------------------------------
# update_swarm_context
# ---------------------------------------------------------------------------


class TestUpdateSwarmContext:
    def test_updates_existing_key(self):
        client = _mock_client()
        client.blocks.retrieve.return_value = SimpleNamespace(
            value="Topic: Old Topic\nParticipants: Alice"
        )

        result = update_swarm_context(client, "block-1", {"Topic": "New Topic"})

        assert result is True
        new_value = client.blocks.update.call_args.kwargs["value"]
        assert "Topic: New Topic" in new_value
        assert "Participants: Alice" in new_value

    def test_adds_new_key(self):
        client = _mock_client()
        client.blocks.retrieve.return_value = SimpleNamespace(
            value="Topic: Test"
        )

        result = update_swarm_context(client, "block-1", {"Status": "active"})

        assert result is True
        new_value = client.blocks.update.call_args.kwargs["value"]
        assert "Status: active" in new_value
        assert "Topic: Test" in new_value

    def test_handles_error(self):
        client = _mock_client()
        client.blocks.retrieve.side_effect = Exception("Not found")

        result = update_swarm_context(client, "block-1", {"Topic": "Test"})

        assert result is False


# ---------------------------------------------------------------------------
# setup_cross_agent_messaging (high-level)
# ---------------------------------------------------------------------------


class TestSetupCrossAgentMessaging:
    @patch.object(cross_agent, "attach_block_to_agents", return_value=2)
    @patch.object(
        cross_agent,
        "create_swarm_context_block",
        return_value="block-ctx-1",
    )
    @patch.object(cross_agent, "attach_multi_agent_tools", return_value=True)
    @patch.object(
        cross_agent,
        "tag_agents_for_session",
        return_value="spds:session-sess-1",
    )
    def test_full_setup(self, mock_tag, mock_attach, mock_block, mock_attach_block):
        client = _mock_client()

        result = setup_cross_agent_messaging(
            client,
            agent_ids=["a-1", "a-2"],
            session_id="sess-1",
            topic="AI Strategy",
            participant_names=["Alice", "Bob"],
            conversation_mode="hybrid",
        )

        assert result["session_tag"] == "spds:session-sess-1"
        assert result["multi_agent_enabled"] is True
        assert result["swarm_context_block_id"] == "block-ctx-1"
        mock_tag.assert_called_once()
        mock_attach.assert_called_once()
        mock_block.assert_called_once()
        mock_attach_block.assert_called_once_with(
            client, "block-ctx-1", ["a-1", "a-2"]
        )

    @patch.object(cross_agent, "attach_block_to_agents")
    @patch.object(cross_agent, "create_swarm_context_block", return_value=None)
    @patch.object(cross_agent, "attach_multi_agent_tools", return_value=False)
    @patch.object(
        cross_agent,
        "tag_agents_for_session",
        return_value="spds:session-s1",
    )
    def test_partial_failure(self, mock_tag, mock_attach, mock_block, mock_attach_block):
        client = _mock_client()

        result = setup_cross_agent_messaging(
            client, agent_ids=["a-1"], session_id="s1"
        )

        assert result["multi_agent_enabled"] is False
        assert result["swarm_context_block_id"] is None
        mock_attach_block.assert_not_called()  # No block to attach


# ---------------------------------------------------------------------------
# teardown_cross_agent_messaging
# ---------------------------------------------------------------------------


class TestTeardownCrossAgentMessaging:
    @patch.object(cross_agent, "remove_session_tags")
    def test_calls_remove_tags(self, mock_remove):
        client = _mock_client()

        teardown_cross_agent_messaging(client, ["a-1", "a-2"], "sess-1")

        mock_remove.assert_called_once_with(client, ["a-1", "a-2"], "sess-1")


# ---------------------------------------------------------------------------
# SPDSAgent.create_new multi-agent support
# ---------------------------------------------------------------------------


class TestSPDSAgentMultiAgentTools:
    @patch("spds.spds_agent.letta_call")
    def test_create_new_with_multi_agent_tools(self, mock_letta_call):
        """create_new passes include_multi_agent_tools to agents.create."""
        mock_state = SimpleNamespace(
            id="agent-new",
            name="TestAgent",
            system="You are TestAgent. Your persona is: Tester. Your expertise is in: testing.",
            tools=[],
        )
        mock_letta_call.return_value = mock_state

        from spds.spds_agent import SPDSAgent

        with patch.object(SPDSAgent, "_ensure_assessment_tool"):
            agent = SPDSAgent.create_new(
                name="TestAgent",
                persona="Tester",
                expertise=["testing"],
                client=MagicMock(),
                include_multi_agent_tools=True,
                tags=["spds:session-test"],
            )

        # Check that create was called with multi-agent tools flag
        create_call_kwargs = mock_letta_call.call_args.kwargs
        assert create_call_kwargs.get("include_multi_agent_tools") is True
        assert "spds:session-test" in create_call_kwargs.get("tags", [])

    @patch("spds.spds_agent.letta_call")
    def test_create_new_without_multi_agent_tools(self, mock_letta_call):
        """create_new omits include_multi_agent_tools by default."""
        mock_state = SimpleNamespace(
            id="agent-new",
            name="TestAgent",
            system="You are TestAgent. Your persona is: Tester. Your expertise is in: testing.",
            tools=[],
        )
        mock_letta_call.return_value = mock_state

        from spds.spds_agent import SPDSAgent

        with patch.object(SPDSAgent, "_ensure_assessment_tool"):
            agent = SPDSAgent.create_new(
                name="TestAgent",
                persona="Tester",
                expertise=["testing"],
                client=MagicMock(),
            )

        create_call_kwargs = mock_letta_call.call_args.kwargs
        assert "include_multi_agent_tools" not in create_call_kwargs
        assert "tags" not in create_call_kwargs


# ---------------------------------------------------------------------------
# SwarmManager cross-agent integration
# ---------------------------------------------------------------------------


class TestSwarmManagerCrossAgent:
    def test_init_sets_session_id(self):
        """SwarmManager.__init__ assigns a session_id."""
        from spds.swarm_manager import SwarmManager

        mgr = object.__new__(SwarmManager)
        # Manually set minimum attrs needed
        mgr.client = MagicMock()
        mgr.agents = []
        mgr.enable_secretary = False
        mgr._secretary = None
        mgr.secretary_agent_id = None
        mgr.pending_nomination = None
        mgr.session_id = "test-session"
        mgr._cross_agent_info = None
        mgr.conversation_mode = "hybrid"
        mgr._history = []
        mgr.export_manager = MagicMock()

        assert mgr.session_id == "test-session"
        assert mgr._cross_agent_info is None

    @patch("spds.swarm_manager.setup_cross_agent_messaging")
    def test_setup_cross_agent(self, mock_setup):
        """_setup_cross_agent calls setup_cross_agent_messaging."""
        from spds.swarm_manager import SwarmManager

        mock_setup.return_value = {
            "session_tag": "spds:session-s1",
            "multi_agent_enabled": True,
            "swarm_context_block_id": "block-1",
        }

        mgr = object.__new__(SwarmManager)
        mgr.client = MagicMock()
        mock_agent = MagicMock()
        mock_agent.agent.id = "agent-1"
        mock_agent.name = "Alice"
        mgr.agents = [mock_agent]
        mgr.session_id = "s1"
        mgr.conversation_mode = "hybrid"
        mgr._cross_agent_info = None

        mgr._setup_cross_agent()

        assert mgr._cross_agent_info["multi_agent_enabled"] is True
        mock_setup.assert_called_once()

    @patch("spds.swarm_manager.teardown_cross_agent_messaging")
    def test_teardown_cross_agent(self, mock_teardown):
        """_teardown_cross_agent calls teardown_cross_agent_messaging."""
        from spds.swarm_manager import SwarmManager

        mgr = object.__new__(SwarmManager)
        mgr.client = MagicMock()
        mock_agent = MagicMock()
        mock_agent.agent.id = "agent-1"
        mgr.agents = [mock_agent]
        mgr.session_id = "s1"
        mgr._cross_agent_info = {
            "session_tag": "spds:session-s1",
            "multi_agent_enabled": True,
            "swarm_context_block_id": "block-1",
        }

        mgr._teardown_cross_agent()

        mock_teardown.assert_called_once_with(
            client=mgr.client,
            agent_ids=["agent-1"],
            session_id="s1",
        )

    def test_teardown_noop_without_cross_agent_info(self):
        """_teardown_cross_agent is a no-op when _cross_agent_info is None."""
        from spds.swarm_manager import SwarmManager

        mgr = object.__new__(SwarmManager)
        mgr.agents = [MagicMock()]
        mgr._cross_agent_info = None

        # Should not raise
        mgr._teardown_cross_agent()
