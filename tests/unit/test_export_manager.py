"""Unit tests for :mod:`spds.export_manager`."""

from __future__ import annotations

import json
import os
from datetime import datetime, timedelta
from pathlib import Path

from spds.export_manager import ExportManager


def build_sample_meeting_data() -> dict:
    """Create a rich meeting payload for export tests."""
    start = datetime(2024, 1, 1, 9, 0, 0)
    metadata = {
        "topic": "AI Strategy Planning",
        "meeting_type": "board meeting",
        "start_time": start,
        "participants": ["Alice", "Bob", "Charlie"],
        "conversation_mode": "voice",
    }

    messages = [
        "I think we should adjust our strategy timeline to reflect new market data and maintain momentum for the rollout.",
        "What if we coordinate implementation milestones with marketing so our messaging lands alongside each feature?",
        "Maybe we should create a new approach that highlights automation, training, and thoughtful onboarding for every team.",
        "The key is ensuring our implementation roadmap includes risk mitigation and performance tracking from the outset.",
        "Important point: the budget must stay aligned with our strategy so we can invest in support without delay.",
        "Another in-depth message keeps momentum strong and reminds everyone about our shared objectives and big ideas.",
    ]
    speakers = ["Alice", "Bob", "Charlie", "Alice", "Bob", "Charlie"]

    conversation = [
        {
            "timestamp": start + timedelta(minutes=index * 5),
            "speaker": speaker,
            "message": message,
        }
        for index, (speaker, message) in enumerate(zip(speakers, messages))
    ]

    action_items = [
        {
            "description": "Draft follow-up report",
            "assignee": "Alice",
            "due_date": "2024-01-15",
            "status": "completed",
        },
        {
            "description": "Prepare budget proposal",
            "assignee": "Bob",
            "due_date": "2024-01-20",
            "status": "pending",
        },
        {
            "description": "Coordinate stakeholder meeting",
            "assignee": "Charlie",
            "due_date": "2024-01-25",
            "status": "pending",
        },
    ]

    decisions = [
        {"decision": "Approve Q1 roadmap"},
        {"decision": "Invest in new tooling"},
        {"decision": "Hire additional support staff"},
    ]

    stats = {
        "total_messages": len(conversation),
        "participants": {
            "Alice": {"messages": 3},
            "Bob": {"messages": 2},
            "Charlie": {"messages": 1},
        },
        "decisions": len(decisions),
        "action_items": len(action_items),
        "duration_minutes": 45,
        "messages_per_minute": 6,
    }

    return {
        "metadata": metadata,
        "conversation_log": conversation,
        "action_items": action_items,
        "decisions": decisions,
        "stats": stats,
        "topics_covered": ["Budget Planning", "Hiring Strategy"],
    }


def test_export_meeting_minutes_formal_contains_board_headers(tmp_path):
    manager = ExportManager(export_directory=str(tmp_path))
    meeting_data = build_sample_meeting_data()
    meeting_data["metadata"]["participants"] = [
        {"name": "Alice", "model": "gpt-4", "expertise": "Chair"},
        {"name": "Bob", "model": "gpt-4", "expertise": "CTO"},
        "Charlie",
    ]

    path = manager.export_meeting_minutes(
        meeting_data, format_type="formal", filename="board_minutes_test"
    )

    exported = Path(path)
    assert exported.exists()
    content = exported.read_text(encoding="utf-8")

    assert "CYAN SOCIETY" in content
    assert "### DISCUSSION AND ACTIONS" in content
    assert "- [ ] Draft follow-up report" in content


def test_export_meeting_minutes_casual_highlights_vibe(tmp_path):
    manager = ExportManager(export_directory=str(tmp_path))
    meeting_data = build_sample_meeting_data()

    path = manager.export_meeting_minutes(
        meeting_data, format_type="casual", filename="casual_notes_test"
    )

    exported = Path(path)
    content = exported.read_text(encoding="utf-8")

    assert "🎯 What We Talked About" in content
    assert "Key Insights" in content
    assert "📋 Action Items" in content


def test_export_raw_transcript_includes_metadata_lines(tmp_path):
    manager = ExportManager(export_directory=str(tmp_path))
    conversation = [
        {
            "timestamp": datetime(2024, 1, 1, 9, 0, 0),
            "speaker": "Alice",
            "message": "Hello team.",
        },
        {
            "timestamp": datetime(2024, 1, 1, 9, 5, 0),
            "speaker": "Bob",
            "message": "Following up on the earlier topic.",
        },
    ]
    metadata = {"topic": "Daily Stand-up", "participants": ["Alice", "Bob"]}

    path = manager.export_raw_transcript(conversation, metadata, filename="transcript")
    content = Path(path).read_text(encoding="utf-8")

    assert "Conversation Transcript" in content
    assert "Topic: Daily Stand-up" in content
    assert "[09:00:00] Alice: Hello team." in content
    assert "End of transcript - 2 messages total" in content


def test_export_raw_transcript_fills_missing_fields(tmp_path):
    manager = ExportManager(export_directory=str(tmp_path))
    conversation = [
        {
            "message": "Message without metadata triggers fallback handling for speaker and timestamp.",
        }
    ]
    metadata = {"topic": "Edge Cases", "participants": []}

    path = manager.export_raw_transcript(
        conversation, metadata, filename="transcript_defaults"
    )
    content = Path(path).read_text(encoding="utf-8")

    assert "Participants: " in content
    assert "Unknown: Message without metadata" in content


def test_export_structured_data_serializes_nested_datetimes(tmp_path):
    manager = ExportManager(export_directory=str(tmp_path))
    meeting_data = build_sample_meeting_data()
    meeting_data["metadata"]["end_time"] = meeting_data["metadata"][
        "start_time"
    ] + timedelta(hours=1)
    meeting_data["notes"] = [
        {
            "created_at": meeting_data["metadata"]["start_time"],
            "content": "Detailed note",
        }
    ]

    path = manager.export_structured_data(meeting_data, filename="structured")
    exported = Path(path)
    assert exported.exists()

    data = json.loads(exported.read_text(encoding="utf-8"))
    assert datetime.fromisoformat(data["metadata"]["start_time"])
    assert (
        data["notes"][0]["created_at"]
        == meeting_data["metadata"]["start_time"].isoformat()
    )


def test_export_action_items_mixed_status_counts(tmp_path):
    manager = ExportManager(export_directory=str(tmp_path))
    action_items = [
        {
            "description": "Finalize deck",
            "assignee": "Alice",
            "due_date": "2024-01-10",
            "status": "completed",
        },
        {
            "description": "Update roadmap",
            "assignee": "Bob",
            "due_date": "2024-01-12",
            "status": "pending",
        },
    ]
    metadata = {"topic": "Quarterly Planning"}

    path = manager.export_action_items(action_items, metadata, filename="actions")
    content = Path(path).read_text(encoding="utf-8")

    assert "**Total Items**: 2" in content
    assert "✅ Completed: 1" in content
    assert "📊 Progress: 50%" in content


def test_export_action_items_empty_list_message(tmp_path):
    manager = ExportManager(export_directory=str(tmp_path))

    path = manager.export_action_items(
        [], {"topic": "Weekly Sync"}, filename="actions_empty"
    )
    content = Path(path).read_text(encoding="utf-8")

    assert "No action items were recorded." in content


def test_export_formatted_conversation_groups_by_speaker(tmp_path):
    manager = ExportManager(export_directory=str(tmp_path))
    conversation = [
        {
            "timestamp": datetime(2024, 1, 1, 10, 0, 0),
            "speaker": "Alice",
            "message": "Initial thought for the day.",
        },
        {
            "timestamp": datetime(2024, 1, 1, 10, 1, 0),
            "speaker": "Alice",
            "message": "Follow-up point to expand the idea.",
        },
        {
            "timestamp": datetime(2024, 1, 1, 10, 2, 0),
            "speaker": "Bob",
            "message": "Response and additional suggestions.",
        },
    ]
    metadata = {
        "topic": "Brainstorm",
        "participants": ["Alice", "Bob"],
        "start_time": datetime(2024, 1, 1, 10, 0, 0),
        "conversation_mode": "text",
    }

    path = manager.export_formatted_conversation(
        conversation, metadata, filename="formatted"
    )
    content = Path(path).read_text(encoding="utf-8")

    assert content.count("## 🤖 Alice") == 1
    assert "## 🤖 Bob" in content
    assert "**Total messages**: 3" in content


def test_export_executive_summary_truncates_lists(tmp_path):
    manager = ExportManager(export_directory=str(tmp_path))
    meeting_data = build_sample_meeting_data()
    meeting_data["decisions"] = [
        {"decision": f"Decision {index}"} for index in range(4)
    ]
    meeting_data["action_items"] = [
        {"description": f"Task {index}", "assignee": f"Owner {index}"}
        for index in range(5)
    ]
    meeting_data["stats"].update({"decisions": 4, "action_items": 5})

    path = manager.export_executive_summary(meeting_data, filename="summary")
    content = Path(path).read_text(encoding="utf-8")

    assert "Executive Summary" in content
    assert "...and 1 more decisions" in content
    assert "...and 2 more action items" in content
    assert "Effectiveness" in content


def test_export_complete_package_with_full_data_returns_expected_files(tmp_path):
    manager = ExportManager(export_directory=str(tmp_path))
    meeting_data = build_sample_meeting_data()

    exported_paths = manager.export_complete_package(meeting_data, format_type="formal")

    assert len(exported_paths) == 6
    for path in exported_paths:
        assert Path(path).exists()


def test_export_complete_package_skips_transcript_when_no_log(tmp_path):
    manager = ExportManager(export_directory=str(tmp_path))
    meeting_data = build_sample_meeting_data()
    meeting_data["conversation_log"] = []
    meeting_data["action_items"] = []

    exported_paths = manager.export_complete_package(meeting_data, format_type="casual")

    assert len(exported_paths) == 3
    for path in exported_paths:
        assert Path(path).exists()
    assert not any("transcript" in path for path in exported_paths)


def test_list_exports_handles_missing_directory(tmp_path):
    manager = ExportManager(export_directory=str(tmp_path / "missing"))

    assert manager.list_exports() == []


def test_list_exports_returns_sorted_paths(tmp_path):
    manager = ExportManager(export_directory=str(tmp_path))
    filenames = ["z_file.txt", "a_file.txt", "m_file.txt"]
    for name in filenames:
        (tmp_path / name).write_text(name, encoding="utf-8")

    listed = manager.list_exports()

    expected = sorted(str(tmp_path / name) for name in filenames)
    assert listed == expected


def test_cleanup_old_exports_removes_files(tmp_path):
    manager = ExportManager(export_directory=str(tmp_path))
    old_file = tmp_path / "old.txt"
    new_file = tmp_path / "new.txt"
    old_file.write_text("old", encoding="utf-8")
    new_file.write_text("new", encoding="utf-8")

    past_time = (datetime.now() - timedelta(days=40)).timestamp()
    os.utime(old_file, (past_time, past_time))

    removed = manager.cleanup_old_exports(days_old=30)

    assert removed == 1
    assert not old_file.exists()
    assert new_file.exists()


def test_cleanup_old_exports_returns_none_when_directory_missing(tmp_path):
    manager = ExportManager(export_directory=str(tmp_path))
    missing_directory = tmp_path / "missing"
    manager.export_directory = missing_directory

    result = manager.cleanup_old_exports(days_old=1)
    assert result is None


def test_generate_filename_includes_prefix_and_timestamp_format(tmp_path):
    manager = ExportManager(export_directory=str(tmp_path))

    filename = manager._generate_filename("testprefix")
    assert filename.startswith("testprefix_")
    timestamp = filename.split("testprefix_")[1]
    datetime.strptime(timestamp, "%Y%m%d_%H%M%S")


def test_prepare_for_json_handles_various_types(tmp_path):
    manager = ExportManager(export_directory=str(tmp_path))
    data = {
        "when": datetime(2024, 2, 2, 12, 30, 0),
        "items": [
            datetime(2024, 2, 3, 15, 45, 0),
            {"nested": datetime(2024, 2, 4, 8, 15, 0)},
        ],
        "value": "text",
    }

    prepared = manager._prepare_for_json(data)

    assert prepared["when"] == datetime(2024, 2, 2, 12, 30, 0).isoformat()
    assert prepared["items"][0] == datetime(2024, 2, 3, 15, 45, 0).isoformat()
    assert prepared["items"][1]["nested"] == datetime(2024, 2, 4, 8, 15, 0).isoformat()
    assert prepared["value"] == "text"
