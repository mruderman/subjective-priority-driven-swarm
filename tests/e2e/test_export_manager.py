"""End-to-end style coverage for ExportManager and session export helpers."""

from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import Mock

import pytest

from spds import export_manager as export_module
from spds.export_manager import (
    ExportManager,
    build_session_summary,
    export_session_to_json,
    export_session_to_markdown,
    restore_session_from_json,
)


@pytest.fixture
def export_dir(tmp_path, monkeypatch):
    export_path = tmp_path / "exports"
    monkeypatch.setattr(
        export_module.config, "DEFAULT_EXPORT_DIRECTORY", str(export_path)
    )
    export_path.mkdir(parents=True, exist_ok=True)
    return export_path


@pytest.fixture
def manager(export_dir):
    return ExportManager()


def _sample_meeting_data():
    now = datetime.now(timezone.utc)
    return {
        "metadata": {
            "topic": "Playwright Coverage",
            "participants": ["Alex", "Jordan"],
            "start_time": now - timedelta(minutes=15),
            "conversation_mode": "hybrid",
        },
        "conversation_log": [
            {
                "timestamp": now - timedelta(minutes=10),
                "speaker": "Alex",
                "message": "Initial thoughts",
            },
            {
                "timestamp": now - timedelta(minutes=9),
                "speaker": "Jordan",
                "message": "Follow up",
            },
        ],
        "action_items": [
            {
                "description": "Prepare summary",
                "assignee": "Alex",
                "due_date": "Tomorrow",
                "status": "pending",
            }
        ],
        "decisions": [
            {
                "decision": "Adopt new testing suite",
                "actor": "Jordan",
                "ts": now.isoformat(),
            }
        ],
        "stats": {
            "duration_minutes": 45,
            "participants": {
                "Alex": {"messages": 3},
                "Jordan": {"messages": 2},
            },
            "total_messages": 5,
        },
    }


def test_export_manager_generates_files(manager, export_dir, tmp_path):
    meeting_data = _sample_meeting_data()

    formal_minutes = manager.export_meeting_minutes(meeting_data, "formal")
    casual_minutes = manager.export_meeting_minutes(
        meeting_data, "casual", filename="custom_notes"
    )
    transcript = manager.export_raw_transcript(
        meeting_data["conversation_log"], meeting_data["metadata"]
    )
    structured = manager.export_structured_data(meeting_data)
    actions = manager.export_action_items(
        meeting_data["action_items"], meeting_data["metadata"]
    )
    formatted = manager.export_formatted_conversation(
        meeting_data["conversation_log"], meeting_data["metadata"]
    )
    summary = manager.export_executive_summary(meeting_data)
    package_files = manager.export_complete_package(meeting_data, format_type="formal")

    for path in [
        formal_minutes,
        casual_minutes,
        transcript,
        structured,
        actions,
        formatted,
        summary,
        *package_files,
    ]:
        assert Path(path).exists()

    # Ensure list_exports returns sorted paths.
    exports_list = manager.list_exports()
    assert exports_list == sorted(exports_list)

    # Force one file to appear old and trigger cleanup.
    old_file = Path(formal_minutes)
    old_time = (datetime.now() - timedelta(days=40)).timestamp()
    os.utime(old_file, (old_time, old_time))
    removed = manager.cleanup_old_exports(days_old=30)
    assert removed >= 1


def test_session_summary_and_restore(tmp_path, export_dir):
    """Test build_session_summary with messages and export functions."""
    now = datetime.now(timezone.utc)
    messages = [
        {
            "message_type": "user_message",
            "role": "user",
            "content": "Hello world",
            "created_at": now,
        },
        {
            "message_type": "assistant_message",
            "role": "assistant",
            "content": "Hi there! How can I help?",
            "created_at": now + timedelta(seconds=5),
        },
    ]

    summary = build_session_summary(messages=messages)
    assert len(summary["messages"]) == 2
    assert "Hello world" in summary["minutes_markdown"]
    assert summary["actions"] == []
    assert summary["decisions"] == []

    # Test export with mocked ConversationManager
    mock_cm = Mock()
    mock_cm.list_messages.return_value = messages
    mock_cm.get_session_summary.return_value = {
        "id": "conv-123",
        "summary": "Test conversation",
        "created_at": now.isoformat(),
        "updated_at": now.isoformat(),
    }

    md_path = export_session_to_markdown(
        "conv-123",
        conversation_manager=mock_cm,
        dest_dir=tmp_path / "session_exports",
    )
    json_path = export_session_to_json(
        "conv-123",
        conversation_manager=mock_cm,
        dest_dir=tmp_path / "session_exports",
    )
    assert md_path.exists()
    assert json_path.exists()

    # Verify JSON content
    with json_path.open() as f:
        data = json.load(f)
    assert "messages" in data
    assert len(data["messages"]) == 2

    # restore_session_from_json is now a deprecation stub
    assert restore_session_from_json(json_path) is None
    assert restore_session_from_json(tmp_path / "missing.json") is None
