"""End-to-end style coverage for ExportManager and session export helpers."""

from __future__ import annotations

import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest

from spds import export_manager as export_module
from spds.export_manager import (
    ExportManager,
    build_session_summary,
    export_session_to_json,
    export_session_to_markdown,
    restore_session_from_json,
)
from spds.session_store import (
    JsonSessionStore,
    SessionEvent,
    set_default_session_store,
    reset_default_session_store,
)


@pytest.fixture
def export_dir(tmp_path, monkeypatch):
    export_path = tmp_path / "exports"
    monkeypatch.setattr(export_module.config, "DEFAULT_EXPORT_DIRECTORY", str(export_path))
    export_path.mkdir(parents=True, exist_ok=True)
    return export_path


@pytest.fixture
def manager(export_dir):
    return ExportManager()


def _sample_meeting_data():
    now = datetime.utcnow()
    return {
        "metadata": {
            "topic": "Playwright Coverage",
            "participants": ["Alex", "Jordan"],
            "start_time": now - timedelta(minutes=15),
            "conversation_mode": "hybrid",
        },
        "conversation_log": [
            {"timestamp": now - timedelta(minutes=10), "speaker": "Alex", "message": "Initial thoughts"},
            {"timestamp": now - timedelta(minutes=9), "speaker": "Jordan", "message": "Follow up"},
        ],
        "action_items": [
            {"description": "Prepare summary", "assignee": "Alex", "due_date": "Tomorrow", "status": "pending"}
        ],
        "decisions": [
            {"decision": "Adopt new testing suite", "actor": "Jordan", "ts": now.isoformat()}
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
    casual_minutes = manager.export_meeting_minutes(meeting_data, "casual", filename="custom_notes")
    transcript = manager.export_raw_transcript(meeting_data["conversation_log"], meeting_data["metadata"])
    structured = manager.export_structured_data(meeting_data)
    actions = manager.export_action_items(meeting_data["action_items"], meeting_data["metadata"])
    formatted = manager.export_formatted_conversation(meeting_data["conversation_log"], meeting_data["metadata"])
    summary = manager.export_executive_summary(meeting_data)
    package_files = manager.export_complete_package(meeting_data, format_type="formal")

    for path in [formal_minutes, casual_minutes, transcript, structured, actions, formatted, summary, *package_files]:
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


def test_session_summary_and_restore(tmp_path, export_dir, monkeypatch):
    store = JsonSessionStore(tmp_path / "sessions")
    set_default_session_store(store)

    session = store.create(title="Minutes Session")
    base_event = SessionEvent(
        event_id="evt-1",
        session_id=session.meta.id,
        ts=datetime.utcnow(),
        actor="Alex",
        type="message",
        payload={"content": "Hello world", "message_type": "user"},
    )
    store.save_event(base_event)
    decision_event = SessionEvent(
        event_id="evt-2",
        session_id=session.meta.id,
        ts=datetime.utcnow(),
        actor="Jordan",
        type="decision",
        payload={"decision_type": "proposal", "details": {"content": "Approve plan"}},
    )
    store.save_event(decision_event)
    action_event = SessionEvent(
        event_id="evt-3",
        session_id=session.meta.id,
        ts=datetime.utcnow(),
        actor="Alex",
        type="action",
        payload={"action_type": "task", "details": {"content": "Write report"}},
    )
    store.save_event(action_event)

    session = store.load(session.meta.id)
    summary = build_session_summary(session)
    assert summary["actions"] and summary["decisions"] and summary["messages"]

    md_path = export_session_to_markdown(session.meta.id, dest_dir=tmp_path / "session_exports")
    json_path = export_session_to_json(session.meta.id, dest_dir=tmp_path / "session_exports")
    assert md_path.exists()
    assert json_path.exists()

    restored_events = {"systems": [], "decisions": [], "actions": []}

    import spds.session_tracking as session_tracking
    import spds.session_context as session_context

    monkeypatch.setattr(
        session_tracking,
        "track_system_event",
        lambda *args, **kwargs: restored_events["systems"].append((args, kwargs)),
    )
    monkeypatch.setattr(
        session_tracking,
        "track_decision",
        lambda *args, **kwargs: restored_events["decisions"].append((args, kwargs)),
    )
    monkeypatch.setattr(
        session_tracking,
        "track_action",
        lambda *args, **kwargs: restored_events["actions"].append((args, kwargs)),
    )
    monkeypatch.setattr(session_context, "set_current_session_id", lambda *args, **kwargs: None)

    restored_id = restore_session_from_json(json_path)
    assert isinstance(restored_id, str)
    assert restored_events["decisions"]
    assert restored_events["actions"]

    # Invalid paths should raise helpful errors
    with pytest.raises(ValueError):
        restore_session_from_json(tmp_path / "missing.json")

    bad_json = tmp_path / "bad.json"
    bad_json.write_text("not-json")
    with pytest.raises(ValueError):
        restore_session_from_json(bad_json)

    reset_default_session_store()
