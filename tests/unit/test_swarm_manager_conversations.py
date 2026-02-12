"""Tests for SwarmManager Conversations API integration (Phase 2)."""

from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

from spds import swarm_manager
from spds.swarm_manager import SwarmManager


def _make_mgr(**overrides):
    """Create a bare SwarmManager via __new__ with minimal required attrs."""
    mgr = object.__new__(SwarmManager)
    defaults = {
        "client": Mock(),
        "agents": [],
        "enable_secretary": False,
        "_secretary": None,
        "conversation_mode": "hybrid",
        "secretary_mode": "adaptive",
        "meeting_type": "discussion",
        "export_manager": Mock(),
        "_agent_messages_supports_otid": None,
        "_history": [],
        "secretary_agent_id": None,
        "pending_nomination": None,
        "session_id": "test-session-id",
        "_cross_agent_info": None,
        "_conversation_manager": Mock(),
        "_mcp_launchpad": None,
    }
    defaults.update(overrides)
    for k, v in defaults.items():
        setattr(mgr, k, v)
    return mgr


def _make_agent(name="Agent", agent_id="ag-1"):
    """Create a minimal SPDSAgent-like object."""
    agent = SimpleNamespace(
        name=name,
        agent=SimpleNamespace(id=agent_id),
        conversation_id=None,
        _conversation_manager=None,
        last_message_index=-1,
        roles=[],
    )
    return agent


class TestConversationManagerInit:
    def test_conversation_manager_created_in_init(self, mock_letta_client, sample_agent_profiles, monkeypatch):
        """SwarmManager.__init__ should create a ConversationManager."""
        monkeypatch.setenv("SPDS_MCP_ENABLED", "false")
        mock_letta_client.agents.list.return_value = []
        mock_letta_client.agents.create.return_value = SimpleNamespace(
            id="ag-1",
            name="Test Agent 1",
            system="You are Test Agent 1. Your persona is: A test agent. Your expertise is in: testing.",
            agent_type="react_agent",
            llm_config=SimpleNamespace(model="openai/gpt-4", model_endpoint_type="openai", context_window=128000),
            embedding_config=SimpleNamespace(embedding_endpoint_type="openai", embedding_model="openai/text-embedding-ada-002", embedding_dim=1536),
            memory=SimpleNamespace(blocks=[]),
            blocks=[],
            tools=["perform_subjective_assessment"],
            sources=[],
            tags=[],
            model="openai/gpt-4",
            embedding="openai/text-embedding-ada-002",
        )
        mock_letta_client.tools.list.return_value = [
            SimpleNamespace(id="tool-1", name="perform_subjective_assessment"),
        ]
        mock_letta_client.blocks = Mock()
        mock_letta_client.blocks.create = Mock(return_value=SimpleNamespace(id="block-1"))
        mock_letta_client.blocks.list = Mock(return_value=[])
        mock_letta_client.agents.blocks = Mock()
        mock_letta_client.agents.blocks.attach = Mock()
        mock_letta_client.agents.update = Mock()

        mgr = SwarmManager(mock_letta_client, agent_profiles=sample_agent_profiles)
        assert mgr._conversation_manager is not None
        assert hasattr(mgr._conversation_manager, "send_and_collect")


class TestCreateAgentConversations:
    def test_creates_conversations_for_each_agent(self):
        agents = [_make_agent("Alice", "ag-1"), _make_agent("Bob", "ag-2")]
        cm = Mock()
        cm.create_agent_conversation.side_effect = ["conv-1", "conv-2"]
        mgr = _make_mgr(agents=agents, _conversation_manager=cm)

        mgr._create_agent_conversations("Test Topic")

        assert cm.create_agent_conversation.call_count == 2
        assert agents[0].conversation_id == "conv-1"
        assert agents[0]._conversation_manager is cm
        assert agents[1].conversation_id == "conv-2"
        assert agents[1]._conversation_manager is cm

    def test_passes_correct_metadata(self):
        agents = [_make_agent("Alice", "ag-1")]
        cm = Mock()
        cm.create_agent_conversation.return_value = "conv-1"
        mgr = _make_mgr(agents=agents, _conversation_manager=cm, session_id="sess-xyz")

        mgr._create_agent_conversations("My Topic")

        cm.create_agent_conversation.assert_called_once_with(
            agent_id="ag-1",
            session_id="sess-xyz",
            agent_name="Alice",
            topic="My Topic",
        )

    def test_failure_is_nonfatal(self):
        agents = [_make_agent("Alice", "ag-1"), _make_agent("Bob", "ag-2")]
        cm = Mock()
        cm.create_agent_conversation.side_effect = [RuntimeError("boom"), "conv-2"]
        mgr = _make_mgr(agents=agents, _conversation_manager=cm)

        mgr._create_agent_conversations("Topic")

        # Alice should fall back (None), Bob should succeed
        assert agents[0].conversation_id is None
        assert agents[0]._conversation_manager is None
        assert agents[1].conversation_id == "conv-2"
        assert agents[1]._conversation_manager is cm

    def test_no_op_without_conversation_manager(self):
        agents = [_make_agent("Alice", "ag-1")]
        mgr = _make_mgr(agents=agents, _conversation_manager=None)

        # Should not raise
        mgr._create_agent_conversations("Topic")
        assert agents[0].conversation_id is None

    def test_start_meeting_calls_create_conversations(self):
        """_start_meeting should call _create_agent_conversations."""
        agents = [_make_agent("Alice", "ag-1")]
        cm = Mock()
        cm.create_agent_conversation.return_value = "conv-1"
        mgr = _make_mgr(agents=agents, _conversation_manager=cm)

        # Stub methods called by _start_meeting
        mgr._append_history = Mock()

        mgr._start_meeting("Test Topic")

        cm.create_agent_conversation.assert_called_once()
        assert agents[0].conversation_id == "conv-1"


class TestSecretaryConversation:
    def test_start_meeting_creates_secretary_conversation(self):
        agents = [_make_agent("Alice", "ag-1")]
        sec = SimpleNamespace(
            agent=SimpleNamespace(id="ag-sec"),
            conversation_id=None,
            _conversation_manager=None,
            meeting_metadata={},
        )
        sec.start_meeting = Mock()
        cm = Mock()
        cm.create_agent_conversation.side_effect = ["conv-agent", "conv-sec"]
        mgr = _make_mgr(
            agents=agents,
            _conversation_manager=cm,
            _secretary=sec,
            enable_secretary=True,
        )
        mgr._append_history = Mock()

        mgr._start_meeting("Topic")

        # Agent + secretary = 2 create calls
        assert cm.create_agent_conversation.call_count == 2
        # Secretary should get its conversation set
        assert sec.conversation_id == "conv-sec"
        assert sec._conversation_manager is cm
        # Secretary start_meeting should be called
        sec.start_meeting.assert_called_once()

    def test_secretary_conversation_failure_nonfatal(self):
        agents = [_make_agent("Alice", "ag-1")]
        sec = SimpleNamespace(
            agent=SimpleNamespace(id="ag-sec"),
            conversation_id=None,
            _conversation_manager=None,
            meeting_metadata={},
        )
        sec.start_meeting = Mock()
        cm = Mock()
        # Agent succeeds, secretary fails
        cm.create_agent_conversation.side_effect = ["conv-agent", RuntimeError("fail")]
        mgr = _make_mgr(
            agents=agents,
            _conversation_manager=cm,
            _secretary=sec,
            enable_secretary=True,
        )
        mgr._append_history = Mock()

        mgr._start_meeting("Topic")

        # Secretary conversation_id should stay None
        assert sec.conversation_id is None
        # start_meeting should still be called
        sec.start_meeting.assert_called_once()

    def test_secretary_without_agent_skips_conversation(self):
        agents = [_make_agent("Alice", "ag-1")]
        sec = SimpleNamespace(
            agent=None,
            conversation_id=None,
            _conversation_manager=None,
            meeting_metadata={},
        )
        sec.start_meeting = Mock()
        cm = Mock()
        cm.create_agent_conversation.return_value = "conv-agent"
        mgr = _make_mgr(
            agents=agents,
            _conversation_manager=cm,
            _secretary=sec,
            enable_secretary=True,
        )
        mgr._append_history = Mock()

        mgr._start_meeting("Topic")

        # Only agent conversation, not secretary
        assert cm.create_agent_conversation.call_count == 1


class TestFinalizeConversations:
    def test_updates_summaries_for_agents(self):
        agents = [_make_agent("Alice", "ag-1"), _make_agent("Bob", "ag-2")]
        agents[0].conversation_id = "conv-1"
        agents[1].conversation_id = "conv-2"
        cm = Mock()
        cm.get_session.return_value = SimpleNamespace(summary="spds:s1|Alice|Topic")
        mgr = _make_mgr(
            agents=agents,
            _conversation_manager=cm,
            _history=[Mock(), Mock(), Mock()],
            conversation_mode="hybrid",
        )

        mgr._finalize_conversations()

        assert cm.update_summary.call_count == 2
        # Check that the summary includes completed status
        # update_summary is called as update_summary(conv_id, summary)
        first_call_summary = cm.update_summary.call_args_list[0][0][1]
        assert "completed" in first_call_summary
        assert "msgs=3" in first_call_summary
        assert "mode=hybrid" in first_call_summary

    def test_includes_secretary_conversation(self):
        agents = [_make_agent("Alice", "ag-1")]
        agents[0].conversation_id = "conv-1"
        sec = SimpleNamespace(conversation_id="conv-sec")
        cm = Mock()
        cm.get_session.return_value = SimpleNamespace(summary="spds:s1|Secretary|Topic")
        mgr = _make_mgr(
            agents=agents,
            _conversation_manager=cm,
            _secretary=sec,
            _history=[],
        )

        mgr._finalize_conversations()

        # 1 agent + 1 secretary = 2 update calls
        assert cm.update_summary.call_count == 2

    def test_skips_agents_without_conversation_id(self):
        agents = [_make_agent("Alice", "ag-1"), _make_agent("Bob", "ag-2")]
        agents[0].conversation_id = "conv-1"
        # Bob has no conversation_id
        cm = Mock()
        cm.get_session.return_value = SimpleNamespace(summary="old")
        mgr = _make_mgr(agents=agents, _conversation_manager=cm)

        mgr._finalize_conversations()

        assert cm.update_summary.call_count == 1

    def test_failure_is_nonfatal(self):
        agents = [_make_agent("Alice", "ag-1")]
        agents[0].conversation_id = "conv-1"
        cm = Mock()
        cm.get_session.side_effect = RuntimeError("server error")
        mgr = _make_mgr(agents=agents, _conversation_manager=cm)

        # Should not raise
        mgr._finalize_conversations()

    def test_no_op_without_conversation_manager(self):
        agents = [_make_agent("Alice", "ag-1")]
        agents[0].conversation_id = "conv-1"
        mgr = _make_mgr(agents=agents, _conversation_manager=None)

        # Should not raise
        mgr._finalize_conversations()

    def test_end_meeting_calls_finalize(self):
        agents = [_make_agent("Alice", "ag-1")]
        agents[0].conversation_id = "conv-1"
        cm = Mock()
        cm.get_session.return_value = SimpleNamespace(summary="old")
        mgr = _make_mgr(
            agents=agents,
            _conversation_manager=cm,
            _history=[],
        )
        mgr._teardown_cross_agent = Mock()

        mgr._end_meeting()

        cm.update_summary.assert_called_once()
