"""Tests for spds.conversations.ConversationManager."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from spds.conversations import ConversationManager, _STREAM_SKIP_TYPES


@pytest.fixture
def cm(mock_letta_client):
    """ConversationManager wired to the shared mock client."""
    return ConversationManager(mock_letta_client)


# ------------------------------------------------------------------
# Existing method tests
# ------------------------------------------------------------------


class TestCreateSession:
    def test_creates_conversation_and_returns_id(self, cm, mock_letta_client):
        mock_letta_client.conversations.create.return_value = SimpleNamespace(id="conv-abc")
        cid = cm.create_session("ag-1", summary="hello")
        mock_letta_client.conversations.create.assert_called_once_with(
            agent_id="ag-1", summary="hello"
        )
        assert cid == "conv-abc"

    def test_empty_summary_passes_none(self, cm, mock_letta_client):
        mock_letta_client.conversations.create.return_value = SimpleNamespace(id="conv-x")
        cm.create_session("ag-1", summary="")
        mock_letta_client.conversations.create.assert_called_once_with(
            agent_id="ag-1", summary=None
        )


class TestSendMessage:
    def test_sends_user_message(self, cm, mock_letta_client):
        mock_letta_client.conversations.messages.create.return_value = iter([])
        cm.send_message("conv-1", "hi")
        mock_letta_client.conversations.messages.create.assert_called_once_with(
            conversation_id="conv-1",
            messages=[{"role": "user", "content": "hi"}],
        )


class TestListMessages:
    def test_returns_list(self, cm, mock_letta_client):
        msg1 = SimpleNamespace(content="a")
        msg2 = SimpleNamespace(content="b")
        mock_letta_client.conversations.messages.list.return_value = [msg1, msg2]
        result = cm.list_messages("conv-1", limit=10, order="desc")
        assert result == [msg1, msg2]


class TestListSessions:
    def test_returns_conversations_attr(self, cm, mock_letta_client):
        convs = [SimpleNamespace(id="c1"), SimpleNamespace(id="c2")]
        mock_letta_client.conversations.list.return_value = SimpleNamespace(conversations=convs)
        result = cm.list_sessions("ag-1")
        assert result == convs

    def test_falls_back_to_list(self, cm, mock_letta_client):
        mock_letta_client.conversations.list.return_value = [SimpleNamespace(id="c1")]
        result = cm.list_sessions("ag-1")
        assert len(result) == 1


class TestGetSession:
    def test_delegates_to_retrieve(self, cm, mock_letta_client):
        mock_letta_client.conversations.retrieve.return_value = SimpleNamespace(id="conv-1")
        result = cm.get_session("conv-1")
        assert result.id == "conv-1"


class TestUpdateSummary:
    def test_updates_summary(self, cm, mock_letta_client):
        cm.update_summary("conv-1", "new summary")
        mock_letta_client.conversations.update.assert_called_once_with(
            conversation_id="conv-1", summary="new summary"
        )


class TestGetSessionSummary:
    def test_builds_summary_dict(self, cm, mock_letta_client):
        from datetime import datetime

        ts = datetime(2026, 1, 15, 10, 30)
        mock_letta_client.conversations.retrieve.return_value = SimpleNamespace(
            id="conv-1", agent_id="ag-1", summary="test", created_at=ts, updated_at=ts
        )
        result = cm.get_session_summary("conv-1")
        assert result["id"] == "conv-1"
        assert result["agent_id"] == "ag-1"
        assert "2026" in result["created_at"]


# ------------------------------------------------------------------
# New Phase 2 methods
# ------------------------------------------------------------------


class TestSendAndCollect:
    def test_collects_content_messages(self, cm, mock_letta_client):
        chunks = [
            SimpleNamespace(message_type="assistant_message", content="hello"),
            SimpleNamespace(message_type="ping"),
            SimpleNamespace(message_type="tool_call_message", tool_call="x"),
            SimpleNamespace(message_type="usage_statistics", stats={}),
            SimpleNamespace(message_type="stop_reason"),
        ]
        mock_letta_client.conversations.messages.create.return_value = iter(chunks)
        result = cm.send_and_collect("conv-1", [{"role": "user", "content": "hi"}])
        # Should keep assistant_message and tool_call_message, skip the rest
        assert len(result.messages) == 2
        assert result.messages[0].message_type == "assistant_message"
        assert result.messages[1].message_type == "tool_call_message"

    def test_empty_stream_returns_empty_messages(self, cm, mock_letta_client):
        mock_letta_client.conversations.messages.create.return_value = iter([])
        result = cm.send_and_collect("conv-1", [{"role": "user", "content": "hi"}])
        assert result.messages == []

    def test_skips_error_message_type(self, cm, mock_letta_client):
        chunks = [
            SimpleNamespace(message_type="error_message", error="oops"),
            SimpleNamespace(message_type="assistant_message", content="ok"),
        ]
        mock_letta_client.conversations.messages.create.return_value = iter(chunks)
        result = cm.send_and_collect("conv-1", [{"role": "user", "content": "hi"}])
        assert len(result.messages) == 1
        assert result.messages[0].content == "ok"

    def test_chunks_without_message_type_are_kept(self, cm, mock_letta_client):
        """Chunks missing message_type should be kept (defensive)."""
        chunk = SimpleNamespace(content="raw data")
        mock_letta_client.conversations.messages.create.return_value = iter([chunk])
        result = cm.send_and_collect("conv-1", [{"role": "user", "content": "x"}])
        assert len(result.messages) == 1


class TestCreateAgentConversation:
    def test_creates_with_spds_summary(self, cm, mock_letta_client):
        mock_letta_client.conversations.create.return_value = SimpleNamespace(id="conv-new")
        cid = cm.create_agent_conversation(
            agent_id="ag-1",
            session_id="sess-abc",
            agent_name="Alice",
            topic="Testing",
        )
        assert cid == "conv-new"
        call_args = mock_letta_client.conversations.create.call_args
        assert call_args.kwargs["summary"] == "spds:sess-abc|Alice|Testing"

    def test_handles_empty_name_and_topic(self, cm, mock_letta_client):
        mock_letta_client.conversations.create.return_value = SimpleNamespace(id="conv-2")
        cid = cm.create_agent_conversation(agent_id="ag-1", session_id="s1")
        call_args = mock_letta_client.conversations.create.call_args
        assert call_args.kwargs["summary"] == "spds:s1||"


class TestFindSessionsBySpdsId:
    def test_filters_by_prefix(self, cm, mock_letta_client):
        convs = [
            SimpleNamespace(id="c1", summary="spds:sess-1|Alice|Test"),
            SimpleNamespace(id="c2", summary="spds:sess-2|Bob|Other"),
            SimpleNamespace(id="c3", summary="spds:sess-1|Bob|Test"),
            SimpleNamespace(id="c4", summary="unrelated"),
        ]
        mock_letta_client.conversations.list.return_value = convs
        result = cm.find_sessions_by_spds_id("ag-1", "sess-1")
        assert len(result) == 2
        assert result[0].id == "c1"
        assert result[1].id == "c3"

    def test_returns_empty_when_no_match(self, cm, mock_letta_client):
        mock_letta_client.conversations.list.return_value = []
        result = cm.find_sessions_by_spds_id("ag-1", "nonexistent")
        assert result == []

    def test_handles_none_summary(self, cm, mock_letta_client):
        convs = [SimpleNamespace(id="c1", summary=None)]
        mock_letta_client.conversations.list.return_value = convs
        result = cm.find_sessions_by_spds_id("ag-1", "sess-1")
        assert result == []


class TestParseSpdsummary:
    def test_parses_full_summary(self):
        result = ConversationManager.parse_spds_summary("spds:sess-1|Alice|Testing")
        assert result == {
            "session_id": "sess-1",
            "agent_name": "Alice",
            "topic": "Testing",
        }

    def test_handles_topic_with_pipes(self):
        result = ConversationManager.parse_spds_summary("spds:s1|Bob|A|B|C")
        assert result["topic"] == "A|B|C"

    def test_returns_none_for_non_spds(self):
        assert ConversationManager.parse_spds_summary("regular summary") is None

    def test_returns_none_for_empty_string(self):
        assert ConversationManager.parse_spds_summary("") is None

    def test_returns_none_for_none(self):
        assert ConversationManager.parse_spds_summary(None) is None

    def test_handles_minimal_spds_summary(self):
        result = ConversationManager.parse_spds_summary("spds:s1")
        assert result == {"session_id": "s1", "agent_name": "", "topic": ""}


# ------------------------------------------------------------------
# Web session config methods
# ------------------------------------------------------------------


class TestWebSessionConfig:
    """Tests for list_all_sessions, save_web_session_config, get_web_session_config."""

    def test_list_all_sessions_returns_list(self, cm, mock_letta_client):
        convs = [SimpleNamespace(id="c1"), SimpleNamespace(id="c2")]
        mock_letta_client.conversations.list.return_value = SimpleNamespace(
            conversations=convs
        )
        result = cm.list_all_sessions()
        mock_letta_client.conversations.list.assert_called_once_with(limit=50)
        assert result == convs

    def test_list_all_sessions_empty(self, cm, mock_letta_client):
        mock_letta_client.conversations.list.return_value = SimpleNamespace(
            conversations=[]
        )
        result = cm.list_all_sessions()
        assert result == []

    def test_list_all_sessions_fallback_to_list(self, cm, mock_letta_client):
        """When result has no .conversations attr, falls back to list()."""
        items = [SimpleNamespace(id="c1")]
        mock_letta_client.conversations.list.return_value = items
        result = cm.list_all_sessions()
        assert result == items

    def test_save_web_session_config(self, cm, mock_letta_client):
        mock_letta_client.conversations.create.return_value = SimpleNamespace(
            id="conv-cfg-1"
        )
        config = {"agent_ids": ["ag-1", "ag-2"], "mode": "hybrid"}
        cid = cm.save_web_session_config("ag-1", "web-sess-abc", config)

        assert cid == "conv-cfg-1"
        call_args = mock_letta_client.conversations.create.call_args
        summary = call_args.kwargs["summary"]
        # Summary should contain the prefix, session id, and JSON payload
        assert summary.startswith("spds:web|config|web-sess-abc|")
        import json
        json_part = summary.split("web-sess-abc|", 1)[1]
        assert json.loads(json_part) == config

    def test_get_web_session_config_found(self, cm, mock_letta_client):
        import json
        config = {"agent_ids": ["ag-1"], "mode": "all-speak"}
        summary = f"spds:web|config|sess-42|{json.dumps(config)}"
        convs = [SimpleNamespace(id="c1", summary=summary)]
        mock_letta_client.conversations.list.return_value = convs
        result = cm.get_web_session_config("ag-1", "sess-42")
        assert result == config

    def test_get_web_session_config_not_found(self, cm, mock_letta_client):
        """Returns None when no conversation matches the session ID."""
        convs = [
            SimpleNamespace(id="c1", summary="spds:web|config|other-sess|{}"),
            SimpleNamespace(id="c2", summary="unrelated summary"),
        ]
        mock_letta_client.conversations.list.return_value = convs
        result = cm.get_web_session_config("ag-1", "sess-missing")
        assert result is None

    def test_get_web_session_config_invalid_json(self, cm, mock_letta_client):
        """Returns None when the JSON payload is malformed."""
        summary = "spds:web|config|sess-bad|{not valid json"
        convs = [SimpleNamespace(id="c1", summary=summary)]
        mock_letta_client.conversations.list.return_value = convs
        result = cm.get_web_session_config("ag-1", "sess-bad")
        assert result is None

    def test_get_web_session_config_none_summary(self, cm, mock_letta_client):
        """Handles conversations with None summary gracefully."""
        convs = [SimpleNamespace(id="c1", summary=None)]
        mock_letta_client.conversations.list.return_value = convs
        result = cm.get_web_session_config("ag-1", "sess-x")
        assert result is None


class TestStreamSkipTypes:
    def test_expected_types_present(self):
        assert "ping" in _STREAM_SKIP_TYPES
        assert "usage_statistics" in _STREAM_SKIP_TYPES
        assert "stop_reason" in _STREAM_SKIP_TYPES
        assert "error_message" in _STREAM_SKIP_TYPES
        assert "assistant_message" not in _STREAM_SKIP_TYPES
