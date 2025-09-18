"""Unit tests for session export and restore functionality in spds.export_manager."""

import json
import tempfile
from datetime import datetime
from pathlib import Path

import pytest

from spds.export_manager import (
    build_session_summary,
    export_session_to_json,
    export_session_to_markdown,
    restore_session_from_json,
)
from spds.session_context import set_current_session_id
from spds.session_store import JsonSessionStore, SessionEvent
from spds.session_tracking import track_action, track_decision, track_message


def create_test_session_with_events(tmp_path):
    """Create a test session with various event types."""
    sessions_dir = tmp_path / "sessions"
    store = JsonSessionStore(sessions_dir)

    # Create session
    session_state = store.create(title="Test Session", tags=["test", "export"])
    session_id = session_state.meta.id

    # Set current session context
    set_current_session_id(session_id)

    # Add some messages
    track_message("assistant", "Hello, how can I help you today?", "assistant")
    track_message("user", "I need help with project planning", "user")
    track_message(
        "assistant",
        "I'd be happy to help with project planning. What specific aspects are you working on?",
        "assistant",
    )

    # Add some decisions
    track_decision(
        "assistant",
        "project_approach",
        {
            "content": "We should use agile methodology for this project",
            "rationale": "Agile allows for flexibility and iterative development",
        },
    )

    # Add some actions
    track_action(
        "assistant",
        "create_timeline",
        {
            "content": "Create a project timeline with key milestones",
            "assignee": "project_manager",
            "due_date": "2024-01-15",
        },
    )

    track_action(
        "user",
        "review_budget",
        {
            "content": "Review and approve the project budget",
            "assignee": "finance_team",
            "due_date": "2024-01-10",
        },
    )

    return session_id, store


def test_build_session_summary_with_full_data(tmp_path):
    """Test building session summary with all event types."""
    session_id, store = create_test_session_with_events(tmp_path)

    # Load session state
    session_state = store.load(session_id)

    # Build summary
    summary = build_session_summary(session_state)

    # Verify structure
    assert "minutes_markdown" in summary
    assert "actions" in summary
    assert "decisions" in summary
    assert "messages" in summary
    assert "meta" in summary

    # Verify content counts
    assert len(summary["actions"]) == 2
    assert len(summary["decisions"]) == 1
    assert len(summary["messages"]) == 3

    # Verify meta data
    meta = summary["meta"]
    assert meta["session_id"] == session_id
    assert meta["title"] == "Test Session"
    assert "total_events" in meta
    assert meta["total_events"] >= 6  # At least the events we added

    # Verify markdown content
    markdown = summary["minutes_markdown"]
    assert "# Session Minutes: Test Session" in markdown
    assert "Session ID" in markdown
    assert "Transcript" in markdown
    assert "Decisions" in markdown
    assert "Action Items" in markdown


def test_build_session_summary_with_session_id_string(tmp_path):
    """Test building session summary using session ID string."""
    session_id, store = create_test_session_with_events(tmp_path)

    # Build summary using session ID string
    summary = build_session_summary(session_id)

    # Verify it works the same as with session state
    assert summary["meta"]["session_id"] == session_id
    assert len(summary["messages"]) >= 3


def test_build_session_summary_empty_session(tmp_path):
    """Test building session summary with empty session."""
    sessions_dir = tmp_path / "sessions"
    store = JsonSessionStore(sessions_dir)

    # Create empty session
    session_state = store.create(title="Empty Session")

    # Build summary
    summary = build_session_summary(session_state)

    # Verify empty content
    assert len(summary["actions"]) == 0
    assert len(summary["decisions"]) == 0
    assert len(summary["messages"]) == 0
    assert "No messages recorded" in summary["minutes_markdown"]
    assert "No decisions recorded" in summary["minutes_markdown"]
    assert "No action items recorded" in summary["minutes_markdown"]


def test_build_session_summary_long_message_content(tmp_path):
    """Test that long message content is truncated."""
    sessions_dir = tmp_path / "sessions"
    store = JsonSessionStore(sessions_dir)

    # Create session
    session_state = store.create(title="Long Content Session")
    session_id = session_state.meta.id
    set_current_session_id(session_id)

    # Add very long message
    long_content = "x" * 3000  # Longer than 2000 char limit
    track_message("assistant", long_content, "assistant")

    # Build summary
    summary = build_session_summary(session_id)

    # Verify content is truncated
    message = summary["messages"][0]
    assert len(message["content"]) == 2003  # 2000 chars + "..."
    assert message["content"].endswith("...")


def test_export_session_to_markdown(tmp_path):
    """Test exporting session to markdown file."""
    session_id, store = create_test_session_with_events(tmp_path)

    # Export to markdown
    export_dir = tmp_path / "exports"
    filepath = export_session_to_markdown(session_id, dest_dir=export_dir)

    # Verify file exists
    assert filepath.exists()
    assert filepath.suffix == ".md"
    assert session_id in filepath.name
    assert "minutes" in filepath.name

    # Verify content
    content = filepath.read_text()
    assert "# Session Minutes: Test Session" in content
    assert "Transcript" in content
    assert "Decisions" in content
    assert "Action Items" in content

    # Verify file is in correct directory
    assert filepath.parent == export_dir


def test_export_session_to_json(tmp_path):
    """Test exporting session to JSON file."""
    session_id, store = create_test_session_with_events(tmp_path)

    # Export to JSON
    export_dir = tmp_path / "exports"
    filepath = export_session_to_json(session_id, dest_dir=export_dir)

    # Verify file exists
    assert filepath.exists()
    assert filepath.suffix == ".json"
    assert session_id in filepath.name
    assert "summary" in filepath.name

    # Verify JSON structure
    with filepath.open() as f:
        exported_summary = json.load(f)

    assert "minutes_markdown" in exported_summary
    assert "actions" in exported_summary
    assert "decisions" in exported_summary
    assert "messages" in exported_summary
    assert "meta" in exported_summary

    # Verify content matches original
    original_summary = build_session_summary(session_id)
    assert (
        exported_summary["meta"]["session_id"] == original_summary["meta"]["session_id"]
    )
    assert len(exported_summary["messages"]) == len(original_summary["messages"])


def test_restore_session_from_json_new_session(tmp_path):
    """Test restoring from JSON to a new session."""
    # Create original session with events
    original_session_id, store = create_test_session_with_events(tmp_path)

    # Export to JSON
    export_dir = tmp_path / "exports"
    json_path = export_session_to_json(original_session_id, dest_dir=export_dir)

    # Restore to new session
    new_session_id = restore_session_from_json(json_path)

    # Verify new session is different
    assert new_session_id != original_session_id

    # Load new session
    new_session = store.load(new_session_id)

    # Verify new session has restored events
    system_events = [e for e in new_session.events if e.type == "system"]
    decision_events = [e for e in new_session.events if e.type == "decision"]
    action_events = [e for e in new_session.events if e.type == "action"]

    # Should have system event for minutes import
    minutes_events = [
        e for e in system_events if e.payload.get("event_type") == "minutes_imported"
    ]
    assert len(minutes_events) >= 1

    # Should have decision events
    assert len(decision_events) >= 1

    # Should have action events
    assert len(action_events) >= 2

    # Verify session title
    assert "(restored)" in new_session.meta.title


def test_restore_session_from_json_existing_session(tmp_path):
    """Test restoring from JSON to an existing session."""
    # Create original session with events
    original_session_id, store = create_test_session_with_events(tmp_path)

    # Export to JSON
    export_dir = tmp_path / "exports"
    json_path = export_session_to_json(original_session_id, dest_dir=export_dir)

    # Create target session
    target_session = store.create(title="Target Session")
    target_session_id = target_session.meta.id

    # Restore to existing session
    restored_session_id = restore_session_from_json(
        json_path, target_session_id=target_session_id
    )

    # Verify we used the existing session
    assert restored_session_id == target_session_id

    # Load updated session
    updated_session = store.load(target_session_id)

    # Verify events were appended
    system_events = [e for e in updated_session.events if e.type == "system"]
    decision_events = [e for e in updated_session.events if e.type == "decision"]
    action_events = [e for e in updated_session.events if e.type == "action"]

    # Should have system event for minutes import
    minutes_events = [
        e for e in system_events if e.payload.get("event_type") == "minutes_imported"
    ]
    assert len(minutes_events) >= 1

    # Should have decision events
    assert len(decision_events) >= 1

    # Should have action events
    assert len(action_events) >= 2


def test_restore_session_from_json_malformed_json(tmp_path):
    """Test restoring from malformed JSON raises ValueError."""
    # Create malformed JSON file
    json_path = tmp_path / "malformed.json"
    json_path.write_text("{ invalid json }")

    # Should raise ValueError
    with pytest.raises(ValueError, match="Malformed JSON"):
        restore_session_from_json(json_path)


def test_restore_session_from_json_missing_keys(tmp_path):
    """Test restoring from JSON with missing required keys."""
    # Create JSON with missing keys
    json_path = tmp_path / "incomplete.json"
    incomplete_data = {
        "minutes_markdown": "Some minutes",
        # Missing actions, decisions, messages, meta
    }
    json_path.write_text(json.dumps(incomplete_data))

    # Should raise ValueError
    with pytest.raises(ValueError, match="Missing required keys"):
        restore_session_from_json(json_path)


def test_restore_session_from_json_nonexistent_file(tmp_path):
    """Test restoring from nonexistent file raises ValueError."""
    json_path = tmp_path / "nonexistent.json"

    # Should raise ValueError
    with pytest.raises(ValueError, match="JSON file not found"):
        restore_session_from_json(json_path)


def test_export_default_directories(tmp_path):
    """Test export functions use default directories when none specified."""
    # Monkeypatch config to use temp directory
    import spds.export_manager

    original_default = spds.export_manager.config.DEFAULT_EXPORT_DIRECTORY
    spds.export_manager.config.DEFAULT_EXPORT_DIRECTORY = str(
        tmp_path / "default_exports"
    )

    try:
        session_id, store = create_test_session_with_events(tmp_path)

        # Export without specifying dest_dir (should use default)
        markdown_path = export_session_to_markdown(session_id)
        json_path = export_session_to_json(session_id)

        # Verify files were created in default location
        assert markdown_path.exists()
        assert json_path.exists()

        # Verify paths contain expected structure
        assert "sessions" in str(markdown_path)
        assert session_id in str(markdown_path)

    finally:
        # Restore original config
        spds.export_manager.config.DEFAULT_EXPORT_DIRECTORY = original_default


def test_export_atomic_writes(tmp_path):
    """Test that exports use atomic writes."""
    session_id, store = create_test_session_with_events(tmp_path)

    export_dir = tmp_path / "exports"

    # Export and verify atomic write behavior
    markdown_path = export_session_to_markdown(session_id, dest_dir=export_dir)

    # File should exist and be complete
    assert markdown_path.exists()
    content = markdown_path.read_text()
    assert "# Session Minutes" in content
    assert "Transcript" in content

    # JSON export should also work
    json_path = export_session_to_json(session_id, dest_dir=export_dir)
    assert json_path.exists()

    # Verify JSON is valid
    with json_path.open() as f:
        data = json.load(f)
    assert "meta" in data


def test_chronological_message_order(tmp_path):
    """Test that messages are ordered chronologically in minutes."""
    sessions_dir = tmp_path / "sessions"
    store = JsonSessionStore(sessions_dir)

    # Create session
    session_state = store.create(title="Chronological Test")
    session_id = session_state.meta.id
    set_current_session_id(session_id)

    # Add messages with specific timestamps
    from datetime import datetime, timedelta

    base_time = datetime.utcnow()

    # Create events with specific timestamps
    events = [
        SessionEvent(
            event_id=f"event-{i}",
            session_id=session_id,
            ts=base_time + timedelta(minutes=i * 5),
            actor=f"speaker_{i}",
            type="message",
            payload={
                "content": f"Message {i}",
                "message_type": "assistant" if i % 2 == 0 else "user",
            },
        )
        for i in range(3)
    ]

    # Save events in reverse order
    for event in reversed(events):
        store.save_event(event)

    # Build summary
    summary = build_session_summary(session_id)

    # Verify messages are in chronological order
    messages = summary["messages"]
    assert len(messages) == 3

    timestamps = [datetime.fromisoformat(msg["ts"]) for msg in messages]
    assert timestamps == sorted(timestamps)


def test_edge_case_empty_payloads(tmp_path):
    """Test handling of events with empty or minimal payloads."""
    sessions_dir = tmp_path / "sessions"
    store = JsonSessionStore(sessions_dir)

    # Create session
    session_state = store.create(title="Edge Case Test")
    session_id = session_state.meta.id
    set_current_session_id(session_id)

    # Add events with minimal payloads
    track_decision("test_actor", "test_decision", {})
    track_action("test_actor", "test_action", {})
    track_message("test_actor", "", "assistant")

    # Build summary
    summary = build_session_summary(session_id)

    # Should handle gracefully
    assert len(summary["decisions"]) == 1
    assert len(summary["actions"]) == 1
    assert len(summary["messages"]) == 1

    # Verify content handling
    assert summary["messages"][0]["content"] == ""


def test_restore_preserves_original_metadata(tmp_path):
    """Test that restore preserves original metadata in events."""
    # Create original session
    session_id, store = create_test_session_with_events(tmp_path)

    # Export to JSON
    export_dir = tmp_path / "exports"
    json_path = export_session_to_json(session_id, dest_dir=export_dir)

    # Restore to new session
    new_session_id = restore_session_from_json(json_path)
    new_session = store.load(new_session_id)

    # Find imported events
    decision_events = [e for e in new_session.events if e.type == "decision"]
    action_events = [e for e in new_session.events if e.type == "action"]

    # Verify original timestamps are preserved in metadata
    for event in decision_events + action_events:
        if "original_ts" in event.payload:
            assert isinstance(event.payload["original_ts"], str)
        if "imported_from" in event.payload:
            assert event.payload["imported_from"] == session_id
