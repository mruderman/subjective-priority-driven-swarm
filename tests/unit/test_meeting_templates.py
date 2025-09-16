"""Unit tests for the board meeting minutes template."""

from datetime import datetime as real_datetime

import pytest

from spds.meeting_templates import BoardMinutesTemplate


@pytest.fixture
def fixed_datetime(monkeypatch):
    """Freeze datetime.now used inside the template for deterministic outputs."""

    class FixedDateTime(real_datetime):
        @classmethod
        def now(cls, tz=None):
            dt = cls(2024, 5, 20, 15, 30)
            return dt if tz is None else dt.replace(tzinfo=tz)

    monkeypatch.setattr("spds.meeting_templates.datetime", FixedDateTime)
    return FixedDateTime


@pytest.fixture
def sample_meeting_data(fixed_datetime):
    """Return a callable that builds representative meeting data."""

    def _create():
        start = fixed_datetime(2024, 5, 19, 9, 0)
        return {
            "metadata": {
                "start_time": start,
                "meeting_type": "strategy session",
                "topic": "Q3 Roadmap",
                "participants": [
                    {"name": "Alex Rivera", "model": "gpt-4", "expertise": "Chair"},
                    "Jordan Lee",
                ],
            },
            "conversation_log": [
                {
                    "speaker": "Alex Rivera",
                    "message": (
                        "Detailed strategy discussion message that easily exceeds twenty "
                        "characters."
                    ),
                },
                {
                    "speaker": "Jordan Lee",
                    "message": (
                        "Implementation considerations were raised in a message that is "
                        "also comfortably long enough."
                    ),
                },
            ],
            "action_items": [
                {
                    "description": "Prepare Q3 budget",
                    "assignee": "Jordan Lee",
                    "due_date": "2024-06-01",
                }
            ],
            "decisions": [
                {"decision": "Approve roadmap", "context": "Unanimous vote"}
            ],
            "topics_covered": ["Budget review", "Roadmap approval"],
            "stats": {
                "total_messages": 4,
                "participants": {"Alex Rivera": 2, "Jordan Lee": 2},
                "decisions": 1,
                "action_items": 1,
            },
        }

    return _create


def test_format_duration_under_hour_returns_minutes():
    template = BoardMinutesTemplate()
    start = real_datetime(2024, 5, 20, 9, 0)
    end = real_datetime(2024, 5, 20, 9, 45)

    assert template.format_duration(start, end) == "45 minutes"


def test_format_duration_exact_hour_uses_singular_label():
    template = BoardMinutesTemplate()
    start = real_datetime(2024, 5, 20, 9, 0)
    end = real_datetime(2024, 5, 20, 10, 0)

    assert template.format_duration(start, end) == "1 hour"


def test_format_duration_multiple_hours_and_minutes():
    template = BoardMinutesTemplate()
    start = real_datetime(2024, 5, 20, 9, 0)
    end = real_datetime(2024, 5, 20, 11, 15)

    assert template.format_duration(start, end) == "2 hours 15 minutes"


def test_generate_includes_custom_organization_and_title_case_meeting_type(
    sample_meeting_data,
):
    meeting_data = sample_meeting_data()
    meeting_data["metadata"]["meeting_type"] = "emergency session"
    template = BoardMinutesTemplate("Cyan Innovations")

    minutes = template.generate(meeting_data)

    assert "# Cyan Innovations" in minutes
    assert "**Meeting Type**: Emergency Session" in minutes


def test_generate_uses_default_metadata_values_when_missing(sample_meeting_data):
    meeting_data = sample_meeting_data()
    meeting_data["metadata"].pop("meeting_type")
    meeting_data["metadata"].pop("topic")

    minutes = BoardMinutesTemplate().generate(meeting_data)

    assert "**Meeting Type**: Regular Board Meeting" in minutes
    assert "**Topic**: General Discussion" in minutes


def test_generate_includes_meeting_number_from_start_date(sample_meeting_data):
    meeting_data = sample_meeting_data()

    minutes = BoardMinutesTemplate().generate(meeting_data)

    assert "**Meeting Number**: 2024-0519" in minutes


def test_generate_formats_participants_with_model_and_default_role(sample_meeting_data):
    meeting_data = sample_meeting_data()

    minutes = BoardMinutesTemplate().generate(meeting_data)

    assert "- Alex Rivera - Chair (Model: gpt-4)" in minutes
    assert "- Jordan Lee - Board Member" in minutes


def test_generate_includes_agenda_topics(sample_meeting_data):
    meeting_data = sample_meeting_data()

    minutes = BoardMinutesTemplate().generate(meeting_data)

    assert "1. Budget review" in minutes
    assert "2. Roadmap approval" in minutes


def test_generate_includes_decisions_and_context(sample_meeting_data):
    meeting_data = sample_meeting_data()

    minutes = BoardMinutesTemplate().generate(meeting_data)

    assert "**Motions and Decisions**" in minutes
    assert "1. **Motion**: Approve roadmap" in minutes
    assert "**Context**: Unanimous vote" in minutes


def test_generate_includes_action_items_with_assignment_details(sample_meeting_data):
    meeting_data = sample_meeting_data()

    minutes = BoardMinutesTemplate().generate(meeting_data)

    assert "- [ ] Prepare Q3 budget" in minutes
    assert "**Assigned to**: Jordan Lee" in minutes
    assert "**Due Date**: 2024-06-01" in minutes


def test_generate_discussion_summary_and_key_perspectives_sections(sample_meeting_data):
    meeting_data = sample_meeting_data()

    minutes = BoardMinutesTemplate().generate(meeting_data)

    assert (
        "**Discussion Summary**: The board engaged in comprehensive discussion on the topic."
        in minutes
    )
    assert "**Key Perspectives Shared**" in minutes
    assert (
        "- **Alex Rivera**: Detailed strategy discussion message that easily exceeds twenty"
        in minutes
    )


def test_generate_formal_summary_handles_empty_conversation_log():
    template = BoardMinutesTemplate()

    summary = template._generate_formal_discussion_summary([], [])

    assert summary == "No detailed discussion recorded."


def test_generate_formal_summary_highlights_substantive_keywords():
    template = BoardMinutesTemplate()
    conversation_log = [
        {
            "speaker": "A",
            "message": "This strategy document explores implementation details thoroughly.",
        },
        {
            "speaker": "B",
            "message": "Another substantive comment emphasizing the strategy considerations involved.",
        },
    ]

    summary = template._generate_formal_discussion_summary(conversation_log, [])

    assert "A total of 2 substantive contributions" in summary
    assert "Strategic considerations were emphasized" in summary
    assert "Implementation approaches were thoroughly examined" in summary


def test_extract_key_perspectives_skips_short_messages():
    template = BoardMinutesTemplate()
    conversation_log = [
        {"speaker": "A", "message": "Too short"},
        {
            "speaker": "A",
            "message": "This is the first sufficiently long perspective that should be kept.",
        },
        {
            "speaker": "A",
            "message": "A second message that should be ignored because a perspective already exists.",
        },
    ]

    perspectives = template._extract_key_perspectives(conversation_log)

    assert perspectives == {
        "A": "This is the first sufficiently long perspective that should be kept."
    }


def test_extract_key_perspectives_truncates_long_message():
    template = BoardMinutesTemplate()
    long_message = "Lorem ipsum " * 20  # 220 characters
    conversation_log = [
        {"speaker": "A", "message": long_message},
    ]

    perspectives = template._extract_key_perspectives(conversation_log)

    assert perspectives["A"].endswith("...")
    assert len(perspectives["A"]) == 150
