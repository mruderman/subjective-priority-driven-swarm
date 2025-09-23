import pytest

import spds.meeting_templates as meeting_templates


def test_render_basic_template():
    data = {
        "metadata": {
            "topic": "Roadmap",
            "participants": ["Alice", "Bob"],
            "meeting_type": "planning",
        },
        "conversation_log": [],
    }
    tpl = meeting_templates.BoardMinutesTemplate()
    out = tpl.generate(data)
    assert isinstance(out, str)
    assert "Roadmap" in out


def test_render_with_optional_fields():
    data = {
        "metadata": {"topic": "Sync", "participants": [], "notes_style": "casual"},
        "conversation_log": [],
    }
    tpl = meeting_templates.CasualMinutesTemplate()
    out = tpl.generate(data)
    assert "Sync" in out


def test_casual_template_long_conversation_features():
    tpl = meeting_templates.CasualMinutesTemplate()
    long_message = (
        "I think the strategy we discussed could evolve into a broader solution "
        "if we consider how the market might respond over the next quarter."
    )
    conversation = [
        {"speaker": "Alice", "message": long_message + " This idea could work."},
        {
            "speaker": "Bob",
            "message": "What if we pilot the idea with two teams first?",
        },
    ] * 6
    stats = {
        "total_messages": len(conversation),
        "messages_per_minute": 6,
        "participants": {
            "Alice": {"messages": 8},
            "Bob": {"messages": 4},
        },
    }
    decisions = [{"decision": "Launch pilot"}]
    action_items = [
        {"description": "Prepare pilot plan", "assignee": "Cara", "due_date": "Friday"}
    ]
    data = {
        "metadata": {
            "topic": "Roadmap",
            "participants": ["Alice", {"name": "Bob"}],
            "meeting_type": "planning",
        },
        "conversation_log": conversation,
        "stats": stats,
        "decisions": decisions,
        "action_items": action_items,
    }

    output = tpl.generate(data)

    assert "Random Good Ideas" in output
    assert "Quick Stats" in output
    assert "Energy level" in output
    assert "Most chatty" in output
    assert "Action Items" in output


def test_casual_template_defaults_when_sparse():
    tpl = meeting_templates.CasualMinutesTemplate()
    data = {
        "metadata": {"topic": "Retro", "participants": []},
        "conversation_log": [],
        "stats": {"total_messages": 0},
        "decisions": [],
        "action_items": [],
    }

    output = tpl.generate(data)

    assert "The usual suspects" in output
    assert "Next Hangout" in output


def test_format_participants_casual_variants():
    tpl = meeting_templates.CasualMinutesTemplate()
    assert tpl._format_participants_casual([]) == "The usual suspects"
    assert tpl._format_participants_casual(["Alex", "Blair"]) == "Alex and Blair"
    names = tpl._format_participants_casual(["Alex", "Blair", {"name": "Casey"}])
    assert names.endswith("and Casey")


def test_determine_conversation_vibe_branches():
    tpl = meeting_templates.CasualMinutesTemplate()
    assert tpl._determine_conversation_vibe([{}] * 3, [], []) == "Quick sync ⚡"
    assert (
        tpl._determine_conversation_vibe([{}] * 6, [{}, {}, {}], [])
        == "Productive decision-making 💪"
    )
    assert (
        tpl._determine_conversation_vibe([{}] * 6, [], [{}, {}, {}, {}])
        == "Action-packed planning 🎯"
    )
    assert (
        tpl._determine_conversation_vibe([{}] * 30, [], []) == "Deep dive discussion 🧠"
    )
    assert (
        tpl._determine_conversation_vibe([{}] * 20, [], [])
        == "Collaborative brainstorming 💡"
    )
    assert (
        tpl._determine_conversation_vibe([{}] * 10, [], []) == "Chill and productive 😊"
    )


def test_generate_casual_discussion_summary_branches():
    tpl = meeting_templates.CasualMinutesTemplate()
    assert (
        tpl._generate_casual_discussion_summary([], [])
        == "We had a great chat but the details got away from me! 😅"
    )
    single = tpl._generate_casual_discussion_summary(
        [{"speaker": "Alex", "message": "Lots to say about this topic."}], []
    )
    assert "Alex shared" in single

    mixed = tpl._generate_casual_discussion_summary(
        [
            {"speaker": "Alex", "message": "Detailed thoughts" * 5},
            {"speaker": "Blair", "message": "More contributions" * 5},
        ],
        ["Alex", "Blair"],
    )
    assert "Good back-and-forth" in mixed or "Solid discussion" in mixed


def test_extract_casual_insights_and_good_ideas():
    tpl = meeting_templates.CasualMinutesTemplate()
    conversation = [
        {
            "speaker": "Dana",
            "message": "I think the key is to prioritise onboarding because the data shows people churn quickly",
        },
        {
            "speaker": "Eli",
            "message": "Short note",
        },
    ]
    insights = tpl._extract_casual_insights(conversation)
    assert insights and any("Dana" in i for i in insights)

    ideas = tpl._extract_good_ideas(
        [
            {
                "speaker": "Dana",
                "message": "This idea might solve the onboarding problem if we adjust our approach",
            }
        ]
    )
    assert any("idea" in idea.lower() for idea in ideas)

    fallback = tpl._extract_good_ideas(
        [
            {"speaker": "Fay", "message": "Short"},
        ]
    )
    assert len(fallback) == 3


def test_get_most_active_participant_variants():
    tpl = meeting_templates.CasualMinutesTemplate()
    assert tpl._get_most_active_participant({}) == "Everyone equally!"
    stats = {"participants": {"Alex": {"messages": 3}, "Blair": {"messages": 5}}}
    assert "Blair" in tpl._get_most_active_participant(stats)
