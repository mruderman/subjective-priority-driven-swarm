import json
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from spds.secretary_agent import SecretaryAgent


def _mk_profile():
    return {
        "name": "S",
        "persona": "sec",
        "expertise": [],
        "model": "openai/gpt-4",
        "embedding": "openai/text-embedding-ada-002",
    }


def make_tool_response(message: str):
    tool_call = SimpleNamespace(
        function=SimpleNamespace(
            name="send_message", arguments=json.dumps({"message": message})
        )
    )
    message_obj = SimpleNamespace(
        tool_calls=[tool_call],
        tool_return=None,
        message_type="tool_message",
        content=None,
    )
    return SimpleNamespace(messages=[message_obj])


def test_set_mode_accepts_valid_and_rejects_invalid(mock_letta_client):
    with patch("spds.secretary_agent.CreateBlockParam"):
        # create a secretary agent instance
        sec = SecretaryAgent(client=mock_letta_client, mode="adaptive")

    # valid
    sec.set_mode("formal")
    assert sec.mode == "formal"

    # invalid
    with pytest.raises(ValueError):
        sec.set_mode("improvised")


def test_start_meeting_notifies_and_extracts_response(mock_letta_client, capsys):
    # patch the underlying create to not actually call external
    with patch("spds.secretary_agent.CreateBlockParam"):
        sec = SecretaryAgent(client=mock_letta_client, mode="casual")

    # mock the client's messages.create to return a tool response
    mock_letta_client.agents.messages.create.return_value = make_tool_response(
        "ready to take notes"
    )

    sec.agent = SimpleNamespace(id="sec-1")
    sec.start_meeting("Budget", ["A", "B"], meeting_type="board")

    captured = capsys.readouterr()
    assert "Meeting started" in captured.out or "Participants" in captured.out
    assert "ready to take notes" in captured.out


def test_generate_minutes_returns_minutes_when_long_enough(mock_letta_client):
    with patch("spds.secretary_agent.CreateBlockParam"):
        sec = SecretaryAgent(client=mock_letta_client, mode="formal")

    # set meeting metadata so minutes() will proceed
    sec.meeting_metadata = {
        "meeting_type": "board",
        "topic": "Budget",
        "start_time": __import__("datetime").datetime.now(),
    }
    sec.agent = SimpleNamespace(id="sec-1")

    long_minutes = """This is a substantial meeting minutes output that is intentionally long to exceed the length threshold used by generate_minutes in the implementation. It contains details, decisions and action items."""

    mock_letta_client.agents.messages.create.return_value = make_tool_response(
        long_minutes
    )

    out = sec.generate_minutes()
    assert isinstance(out, str)
    assert "substantial meeting minutes" in out or len(out) > 50


def test_add_action_item_prints_success_and_handles_failure(mock_letta_client, capsys):
    with patch("spds.secretary_agent.CreateBlockParam"):
        sec = SecretaryAgent(client=mock_letta_client, mode="adaptive")

    sec.agent = SimpleNamespace(id="sec-1")

    # successful create
    mock_letta_client.agents.messages.create.return_value = make_tool_response("ok")
    sec.add_action_item("Do X", assignee="Alice")
    captured = capsys.readouterr()
    assert "Action item recorded" in captured.out or "Action item" in captured.out

    # simulate exception
    def raise_exc(*a, **k):
        raise RuntimeError("boom")

    mock_letta_client.agents.messages.create.side_effect = raise_exc
    sec.add_action_item("Do Y")
    captured = capsys.readouterr()
    assert "Failed to record action item" in captured.out or "Failed" in captured.out


def test_create_secretary_agent_failure_path(mock_letta_client, capsys):
    mock_letta_client.agents.create.side_effect = RuntimeError("boom")
    with patch("spds.secretary_agent.CreateBlockParam"):
        with pytest.raises(RuntimeError):
            SecretaryAgent(client=mock_letta_client, mode="formal")

    captured = capsys.readouterr()
    assert "Failed to create secretary agent" in captured.out


def test_extract_agent_response_prefers_tool_return_and_handles_list_content(
    mock_letta_client,
):
    with patch("spds.secretary_agent.CreateBlockParam"):
        sec = SecretaryAgent(client=mock_letta_client)

    response = SimpleNamespace(
        messages=[
            SimpleNamespace(
                tool_calls=[
                    SimpleNamespace(
                        function=SimpleNamespace(name="send_message", arguments="{")
                    )
                ],
                tool_return=None,
                message_type="tool_message",
                content=None,
            ),
            SimpleNamespace(
                tool_calls=[],
                tool_return="From tool return",
                message_type="tool_message",
                content=None,
            ),
            SimpleNamespace(
                tool_calls=[],
                tool_return=None,
                message_type="assistant_message",
                content=[SimpleNamespace(text="List content handled")],
            ),
        ]
    )

    result = sec._extract_agent_response(response)
    if isinstance(result, list):
        assert result and getattr(result[0], "text", "") == "List content handled"
    else:
        assert result == "List content handled"


def test_extract_agent_response_handles_unexpected_structure(mock_letta_client):
    with patch("spds.secretary_agent.CreateBlockParam"):
        sec = SecretaryAgent(client=mock_letta_client)

    # Force response.messages to raise when iterated
    class BrokenResponse:
        messages = None

    out = sec._extract_agent_response(BrokenResponse())

    assert out == "Secretary is ready to take notes."


def test_add_decision_handles_missing_agent_and_failure(mock_letta_client, capsys):
    with patch("spds.secretary_agent.CreateBlockParam"):
        sec = SecretaryAgent(client=mock_letta_client)

    # No agent present logs warning and returns early
    sec.agent = None
    sec.add_decision("Approve plan")
    captured = capsys.readouterr()
    assert "Secretary agent not available" in captured.out

    sec.agent = SimpleNamespace(id="sec-1")

    mock_letta_client.agents.messages.create.side_effect = RuntimeError("boom")
    sec.add_decision("Approve plan")
    captured = capsys.readouterr()
    assert "Failed to record decision" in captured.out


def test_extract_agent_response_handles_string_entries(mock_letta_client):
    with patch("spds.secretary_agent.CreateBlockParam"):
        sec = SecretaryAgent(client=mock_letta_client)

    response = SimpleNamespace(
        messages=[
            SimpleNamespace(
                tool_calls=[],
                tool_return=None,
                message_type="tool_message",
                content=["String list content"],
            )
        ]
    )

    out = sec._extract_agent_response(response)
    assert out == "String list content"


def test_extract_agent_response_handles_direct_string_content(mock_letta_client):
    with patch("spds.secretary_agent.CreateBlockParam"):
        sec = SecretaryAgent(client=mock_letta_client)

    response = SimpleNamespace(
        messages=[
            SimpleNamespace(
                tool_calls=[],
                tool_return=None,
                message_type="tool_message",
                content="Plain string content",
            )
        ]
    )

    out = sec._extract_agent_response(response)
    assert out == "Plain string content"


def test_extract_agent_response_handles_namespace_text(mock_letta_client):
    with patch("spds.secretary_agent.CreateBlockParam"):
        sec = SecretaryAgent(client=mock_letta_client)

    response = SimpleNamespace(
        messages=[
            SimpleNamespace(
                tool_calls=[],
                tool_return=None,
                message_type="tool_message",
                content=[SimpleNamespace(text="Namespace text content")],
            )
        ]
    )

    out = sec._extract_agent_response(response)
    assert out == "Namespace text content"
