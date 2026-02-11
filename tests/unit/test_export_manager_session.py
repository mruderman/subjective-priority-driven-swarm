"""Unit tests for session export and restore functionality in spds.export_manager.

These tests exercise the new Conversations-API-based signatures:
- build_session_summary(conversation_manager=..., conversation_id=..., messages=...)
- export_session_to_markdown(conversation_id, conversation_manager=..., dest_dir=...)
- export_session_to_json(conversation_id, conversation_manager=..., dest_dir=...)
- restore_session_from_json() -> None  (deprecation stub)
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest

from spds.export_manager import (
    build_session_summary,
    export_session_to_json,
    export_session_to_markdown,
    restore_session_from_json,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_messages(contents, role="assistant"):
    """Build a list of message dicts suitable for build_session_summary."""
    msgs = []
    for i, text in enumerate(contents):
        msgs.append({
            "message_type": "assistant_message" if role == "assistant" else "user_message",
            "role": role,
            "content": text,
            "created_at": datetime(2026, 1, 1, 12, i, 0, tzinfo=timezone.utc).isoformat(),
        })
    return msgs


def _mock_conversation_manager(messages=None, summary_dict=None):
    """Create a mock ConversationManager that returns given messages."""
    cm = MagicMock()
    cm.list_messages.return_value = messages or []
    cm.get_session_summary.return_value = summary_dict or {"id": "conv-123"}
    return cm


# ---------------------------------------------------------------------------
# build_session_summary with messages list
# ---------------------------------------------------------------------------

class TestBuildSessionSummaryMessages:
    """Tests for build_session_summary(messages=[...])."""

    def test_with_full_message_list(self):
        """Messages are extracted and markdown is generated."""
        msgs = _make_messages(["Hello world", "How are you?", "Great, thanks!"])
        summary = build_session_summary(messages=msgs)

        assert "minutes_markdown" in summary
        assert "actions" in summary
        assert "decisions" in summary
        assert "messages" in summary
        assert "meta" in summary

        assert len(summary["messages"]) == 3
        assert summary["messages"][0]["content"] == "Hello world"
        assert summary["messages"][2]["content"] == "Great, thanks!"
        # actions and decisions are always empty in the new API
        assert summary["actions"] == []
        assert summary["decisions"] == []

    def test_with_empty_message_list(self):
        """Empty message list produces summary with no messages."""
        summary = build_session_summary(messages=[])

        assert len(summary["messages"]) == 0
        assert "No messages recorded" in summary["minutes_markdown"]

    def test_raises_when_no_args(self):
        """Calling with no arguments raises ValueError."""
        with pytest.raises(ValueError, match="Provide either"):
            build_session_summary()

    def test_raises_when_only_conversation_manager(self):
        """Passing conversation_manager without conversation_id raises."""
        cm = _mock_conversation_manager()
        with pytest.raises(ValueError, match="Provide either"):
            build_session_summary(conversation_manager=cm)

    def test_raises_when_only_conversation_id(self):
        """Passing conversation_id without conversation_manager raises."""
        with pytest.raises(ValueError, match="Provide either"):
            build_session_summary(conversation_id="conv-123")

    def test_long_message_truncation(self):
        """Content longer than 2000 chars is truncated with ellipsis."""
        long_text = "x" * 3000
        msgs = _make_messages([long_text])
        summary = build_session_summary(messages=msgs)

        extracted = summary["messages"][0]
        assert len(extracted["content"]) == 2003  # 2000 + "..."
        assert extracted["content"].endswith("...")

    def test_empty_content_skipped(self):
        """Messages with empty content are skipped."""
        msgs = [
            {"message_type": "assistant_message", "role": "assistant", "content": "", "created_at": ""},
            {"message_type": "user_message", "role": "user", "content": "hi", "created_at": ""},
        ]
        summary = build_session_summary(messages=msgs)
        assert len(summary["messages"]) == 1
        assert summary["messages"][0]["content"] == "hi"

    def test_markdown_output_structure(self):
        """Verify key sections in the generated markdown."""
        msgs = _make_messages(["First point", "Second point"])
        summary = build_session_summary(messages=msgs)
        md = summary["minutes_markdown"]

        assert "# Session Minutes:" in md
        assert "## Transcript" in md
        assert "## Decisions" in md
        assert "## Action Items" in md
        assert "First point" in md
        assert "Second point" in md

    def test_dict_and_object_messages(self):
        """build_session_summary handles both dict and object-style messages."""
        # Object-style message (simulates a Letta message object)
        obj_msg = Mock()
        obj_msg.message_type = "assistant_message"
        obj_msg.role = "assistant"
        obj_msg.content = "Object message"
        obj_msg.created_at = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

        # Dict-style message
        dict_msg = {
            "message_type": "user_message",
            "role": "user",
            "content": "Dict message",
            "created_at": "2026-01-01T12:01:00+00:00",
        }

        summary = build_session_summary(messages=[obj_msg, dict_msg])
        assert len(summary["messages"]) == 2
        assert summary["messages"][0]["content"] == "Object message"
        assert summary["messages"][1]["content"] == "Dict message"


# ---------------------------------------------------------------------------
# build_session_summary with ConversationManager
# ---------------------------------------------------------------------------

class TestBuildSessionSummaryConversationManager:
    """Tests for build_session_summary(conversation_manager=..., conversation_id=...)."""

    def test_fetches_from_conversation_manager(self):
        """Messages are fetched from the ConversationManager."""
        raw_msgs = _make_messages(["Server-side message"])
        cm = _mock_conversation_manager(
            messages=raw_msgs,
            summary_dict={"id": "conv-abc", "summary": "Test Convo"},
        )

        summary = build_session_summary(
            conversation_manager=cm,
            conversation_id="conv-abc",
        )

        cm.list_messages.assert_called_once_with("conv-abc")
        cm.get_session_summary.assert_called_once_with("conv-abc")
        assert len(summary["messages"]) == 1
        assert summary["meta"]["id"] == "conv-abc"

    def test_meta_fallback_on_summary_error(self):
        """If get_session_summary raises, meta falls back to {id: ...}."""
        cm = _mock_conversation_manager(messages=_make_messages(["msg"]))
        cm.get_session_summary.side_effect = RuntimeError("API error")

        summary = build_session_summary(
            conversation_manager=cm,
            conversation_id="conv-fallback",
        )

        assert summary["meta"] == {"id": "conv-fallback"}


# ---------------------------------------------------------------------------
# restore_session_from_json (deprecation stub)
# ---------------------------------------------------------------------------

class TestRestoreSessionFromJson:
    """Tests for the deprecated restore_session_from_json stub."""

    def test_returns_none(self, tmp_path):
        """Stub always returns None regardless of arguments."""
        result = restore_session_from_json(tmp_path / "anything.json")
        assert result is None

    def test_returns_none_with_target_session_id(self, tmp_path):
        """Stub returns None even with target_session_id."""
        result = restore_session_from_json(
            tmp_path / "anything.json",
            target_session_id="some-id",
        )
        assert result is None


# ---------------------------------------------------------------------------
# export_session_to_markdown / export_session_to_json
# ---------------------------------------------------------------------------

class TestExportFunctions:
    """Tests for export_session_to_markdown and export_session_to_json."""

    def test_export_to_markdown(self, tmp_path):
        """Exports markdown file via ConversationManager."""
        msgs = _make_messages(["Hello", "World"])
        cm = _mock_conversation_manager(
            messages=msgs,
            summary_dict={"id": "conv-md", "summary": "MD Test"},
        )

        filepath = export_session_to_markdown(
            "conv-md",
            conversation_manager=cm,
            dest_dir=tmp_path / "exports",
        )

        assert filepath.exists()
        assert filepath.suffix == ".md"
        assert "conv-md" in filepath.name

        content = filepath.read_text()
        assert "# Session Minutes:" in content
        assert "Hello" in content
        assert "World" in content

    def test_export_to_json(self, tmp_path):
        """Exports JSON file via ConversationManager."""
        msgs = _make_messages(["Alpha", "Beta"])
        cm = _mock_conversation_manager(
            messages=msgs,
            summary_dict={"id": "conv-json", "summary": "JSON Test"},
        )

        filepath = export_session_to_json(
            "conv-json",
            conversation_manager=cm,
            dest_dir=tmp_path / "exports",
        )

        assert filepath.exists()
        assert filepath.suffix == ".json"
        assert "conv-json" in filepath.name

        with filepath.open() as f:
            data = json.load(f)

        assert "minutes_markdown" in data
        assert "actions" in data
        assert "decisions" in data
        assert "messages" in data
        assert "meta" in data
        assert len(data["messages"]) == 2

    def test_export_default_directory(self, tmp_path):
        """When dest_dir is None, uses config.DEFAULT_EXPORT_DIRECTORY."""
        import spds.export_manager

        original = spds.export_manager.config.DEFAULT_EXPORT_DIRECTORY
        spds.export_manager.config.DEFAULT_EXPORT_DIRECTORY = str(
            tmp_path / "default_exports"
        )

        try:
            msgs = _make_messages(["message"])
            cm = _mock_conversation_manager(
                messages=msgs,
                summary_dict={"id": "conv-default"},
            )

            md_path = export_session_to_markdown("conv-default", conversation_manager=cm)
            json_path = export_session_to_json("conv-default", conversation_manager=cm)

            assert md_path.exists()
            assert json_path.exists()
            assert "sessions" in str(md_path)
            assert "conv-default" in str(md_path)
        finally:
            spds.export_manager.config.DEFAULT_EXPORT_DIRECTORY = original
