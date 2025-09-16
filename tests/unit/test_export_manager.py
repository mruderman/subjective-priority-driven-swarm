import json
from datetime import datetime
from pathlib import Path

import pytest

from spds.export_manager import ExportManager


@pytest.fixture
def export_manager(tmp_path):
    return ExportManager(export_directory=tmp_path)


def read_text(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


def test_export_executive_summary_includes_top_items(export_manager):
    meeting_data = {
        "metadata": {
            "topic": "Budget Review",
            "participants": ["Alex", "Jordan", "Casey"],
        },
        "decisions": [
            {"decision": "Approve Q1 budget"},
            {"decision": "Delay hiring plan"},
            {"decision": "Increase marketing investment"},
            {"decision": "Adopt new CRM"},
        ],
        "action_items": [
            {"description": "Prepare revised budget", "assignee": "Jordan"},
            {"description": "Update CRM requirements", "assignee": "Casey"},
            {"description": "Draft communications plan", "assignee": "Alex"},
        ],
        "stats": {
            "duration_minutes": 45,
            "participants": {"Alex": 5, "Jordan": 4, "Casey": 3},
            "total_messages": 18,
        },
    }

    summary_path = export_manager.export_executive_summary(
        meeting_data, filename="executive_summary_focus"
    )

    content = read_text(summary_path)
    assert "**Meeting**: Budget Review" in content
    assert "- Approve Q1 budget" in content
    assert "- *...and 1 more decisions*" in content
    assert "- Draft communications plan (Alex)" in content
    assert "- **Effectiveness**: High" in content


def test_export_executive_summary_handles_missing_sections(export_manager):
    meeting_data = {
        "metadata": {
            "topic": "Standup Recap",
            "participants": ["Alex"],
        },
        "decisions": [],
        "action_items": [],
        "stats": {
            "duration_minutes": 10,
            "participants": {},
            "total_messages": 2,
        },
    }

    summary_path = export_manager.export_executive_summary(
        meeting_data, filename="executive_summary_minimal"
    )

    content = read_text(summary_path)
    assert "**Meeting**: Standup Recap" in content
    assert "### Decisions Made" not in content
    assert "### Action Items" not in content
    assert "- **Effectiveness**: Moderate" in content


def test_export_complete_package_generates_all_formats(export_manager, monkeypatch):
    monkeypatch.setattr(
        export_manager,
        "_generate_filename",
        lambda prefix: f"{prefix}_CONST",
    )

    meeting_data = {
        "metadata": {
            "topic": "Roadmap Planning",
            "participants": ["Alex", "Jordan"],
            "conversation_mode": "adaptive",
            "start_time": datetime(2024, 5, 1, 9, 0),
        },
        "conversation_log": [
            {
                "timestamp": datetime(2024, 5, 1, 9, 0),
                "speaker": "Alex",
                "message": "We need to revisit the delivery timeline to account for the new compliance work and integration tasks.",
            },
            {
                "timestamp": datetime(2024, 5, 1, 9, 5),
                "speaker": "Jordan",
                "message": "Design will adjust milestones so engineering has buffer for validation and rollout communications.",
            },
        ],
        "action_items": [
            {
                "description": "Draft updated roadmap",
                "assignee": "Alex",
                "due_date": "2024-05-10",
                "status": "pending",
            }
        ],
        "decisions": [{"decision": "Extend beta by two weeks"}],
        "stats": {
            "duration_minutes": 45,
            "participants": {"Alex": 6, "Jordan": 5},
            "total_messages": 2,
        },
    }

    exported_files = export_manager.export_complete_package(meeting_data, "formal")

    expected_files = [
        export_manager.export_directory / "meeting_package_CONST_minutes.md",
        export_manager.export_directory / "meeting_package_CONST_transcript.txt",
        export_manager.export_directory / "meeting_package_CONST_formatted.md",
        export_manager.export_directory / "meeting_package_CONST_actions.md",
        export_manager.export_directory / "meeting_package_CONST_summary.md",
        export_manager.export_directory / "meeting_package_CONST_data.json",
    ]

    assert exported_files == [str(path) for path in expected_files]
    for path in expected_files:
        assert path.exists()


def test_export_complete_package_without_optional_sections(export_manager, monkeypatch):
    monkeypatch.setattr(
        export_manager,
        "_generate_filename",
        lambda prefix: f"{prefix}_BASE",
    )

    meeting_data = {
        "metadata": {
            "topic": "Weekly Check-in",
            "participants": ["Alex", "Jordan"],
            "start_time": datetime(2024, 4, 3, 10, 0),
        },
        "conversation_log": [],
        "action_items": [],
        "decisions": [],
        "stats": {},
    }

    exported_files = export_manager.export_complete_package(meeting_data, "casual")

    expected_files = [
        export_manager.export_directory / "meeting_package_BASE_minutes.md",
        export_manager.export_directory / "meeting_package_BASE_summary.md",
        export_manager.export_directory / "meeting_package_BASE_data.json",
    ]

    assert exported_files == [str(path) for path in expected_files]
    for path in expected_files:
        assert path.exists()


def test_export_raw_transcript_contains_metadata(export_manager):
    conversation_log = [
        {
            "timestamp": datetime(2024, 1, 15, 9, 0),
            "speaker": "Alex",
            "message": "Kickoff testing scope review.",
        },
        {
            "timestamp": datetime(2024, 1, 15, 9, 5),
            "speaker": "Jordan",
            "message": "Let's inventory what automation already covers.",
        },
    ]
    metadata = {
        "topic": "Testing Strategy",
        "participants": ["Alex", "Jordan"],
    }

    transcript_path = export_manager.export_raw_transcript(
        conversation_log, metadata, filename="raw_transcript_metadata"
    )

    content = read_text(transcript_path)
    assert "Topic: Testing Strategy" in content
    assert "Participants: Alex, Jordan" in content
    assert "End of transcript - 2 messages total" in content


def test_export_formatted_conversation_includes_mode_and_participants(export_manager):
    conversation_log = [
        {
            "timestamp": datetime(2024, 6, 1, 9, 0),
            "speaker": "Alex",
            "message": "We should review the release checklist to confirm dependencies are satisfied across the services.",
        },
        {
            "timestamp": datetime(2024, 6, 1, 9, 2),
            "speaker": "Alex",
            "message": "I'll compile feedback so we can flag any risky items early.",
        },
        {
            "timestamp": datetime(2024, 6, 1, 9, 5),
            "speaker": "Jordan",
            "message": "Once that summary is ready I'll notify stakeholders and update the comms plan.",
        },
    ]
    metadata = {
        "topic": "Release Sync",
        "participants": ["Alex", "Jordan"],
        "conversation_mode": "adaptive",
        "start_time": datetime(2024, 6, 1, 9, 0),
    }

    formatted_path = export_manager.export_formatted_conversation(
        conversation_log, metadata, filename="formatted_conversation_view"
    )

    content = read_text(formatted_path)
    assert "# 💬 Conversation: Release Sync" in content
    assert "**Mode**: Adaptive" in content
    assert "**Participants**: Alex, Jordan" in content
    assert content.count("## 🤖 Alex") == 1
    assert "I'll compile feedback so we can flag any risky items early." in content
    assert "## 🤖 Jordan" in content


def test_export_action_items_summary_counts(export_manager):
    action_items = [
        {
            "description": "Ship feature",
            "assignee": "Alex",
            "due_date": "2024-07-10",
            "status": "completed",
        },
        {
            "description": "Write docs",
            "assignee": "Jordan",
            "due_date": "2024-07-12",
            "status": "pending",
        },
    ]
    metadata = {"topic": "Launch Prep"}

    action_path = export_manager.export_action_items(
        action_items, metadata, filename="actions_with_summary"
    )

    content = read_text(action_path)
    assert "**Total Items**: 2" in content
    assert "☑️ **Ship feature**" in content
    assert "- ✅ Completed: 1" in content
    assert "- ⏳ Pending: 1" in content
    assert "- 📊 Progress: 50%" in content


def test_export_structured_data_serializes_datetime(export_manager):
    meeting_data = {
        "metadata": {"start_time": datetime(2024, 8, 1, 10, 0)},
        "conversation_log": [
            {
                "timestamp": datetime(2024, 8, 1, 10, 5),
                "speaker": "Alex",
                "message": "Check-in on migration status.",
            }
        ],
    }

    data_path = export_manager.export_structured_data(
        meeting_data, filename="structured_serialization"
    )

    with open(data_path, encoding="utf-8") as f:
        exported = json.load(f)

    assert exported["metadata"]["start_time"].startswith("2024-08-01T10:00:00")
    assert exported["conversation_log"][0]["timestamp"].startswith("2024-08-01T10:05:00")


def test_list_exports_returns_sorted_file_names(export_manager):
    metadata = {"topic": "Ordering"}
    meeting_data = {"metadata": metadata}

    summary = export_manager.export_executive_summary(
        meeting_data, filename="alpha_summary"
    )
    actions = export_manager.export_action_items(
        [], metadata, filename="beta_actions"
    )
    data = export_manager.export_structured_data(
        meeting_data, filename="gamma_data"
    )

    listed = export_manager.list_exports()
    expected = sorted([summary, actions, data])
    assert listed == expected


def test_export_action_items_handles_empty_list(export_manager):
    metadata = {"topic": "No Tasks"}

    action_path = export_manager.export_action_items(
        [], metadata, filename="actions_empty"
    )

    content = read_text(action_path)
    assert "No action items were recorded." in content
    assert "## Summary" not in content
