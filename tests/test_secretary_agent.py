import json
from datetime import datetime as real_datetime
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

# Mark this module as unit tests so it is included when running `-m unit`
pytestmark = pytest.mark.unit

import pytest

import spds.secretary_agent as secretary_module
from spds.secretary_agent import SecretaryAgent


class DummyMessagesAPI:
    def __init__(self):
        self.calls = []
        self.responses = []

    def create(self, agent_id=None, messages=None, **kwargs):
        self.calls.append(
            {"agent_id": agent_id, "messages": messages, "kwargs": kwargs}
        )
        if self.responses:
            return self.responses.pop(0)
        return SimpleNamespace(messages=[])


class DummyAgentsAPI:
    def __init__(self):
        self.create_calls = []
        self.messages = DummyMessagesAPI()
        self._counter = 0

    def create(self, **kwargs):
        self.create_calls.append(kwargs)
        self._counter += 1
        return SimpleNamespace(id=f"agent-{self._counter}")


class DummyClient:
    def __init__(self):
        self.agents = DummyAgentsAPI()


def make_tool_message(text):
    tool_call = SimpleNamespace(
        function=SimpleNamespace(
            name="send_message", arguments=json.dumps({"message": text})
        )
    )
    return SimpleNamespace(
        tool_calls=[tool_call],
        tool_return=None,
        message_type="tool_message",
        content=None,
    )


def make_assistant_message(text):
    return SimpleNamespace(
        tool_calls=[],
        tool_return=None,
        message_type="assistant_message",
        content=text,
    )


@pytest.fixture
def fixed_datetime(monkeypatch):
    class FixedDateTime(real_datetime):
        @classmethod
        def now(cls, tz=None):
            dt = cls(2024, 1, 1, 9, 0, 0)
            return dt if tz is None else dt.replace(tzinfo=tz)

        @classmethod
        def utcnow(cls):
            return cls(2024, 1, 1, 9, 0, 0)

    monkeypatch.setattr(secretary_module, "datetime", FixedDateTime)
    return FixedDateTime


def test_secretary_agent_initialization_formal_builds_expected_blocks(fixed_datetime):
    client = DummyClient()

    secretary = SecretaryAgent(client, mode="formal")

    assert secretary.agent.id == "agent-1"
    call_kwargs = client.agents.create_calls[0]
    assert call_kwargs["name"].endswith("Secretary 20240101_090000")

    persona_block = next(
        block for block in call_kwargs["memory_blocks"] if block.label == "persona"
    )
    assert "formal language" in persona_block.value

    notes_style_block = next(
        block for block in call_kwargs["memory_blocks"] if block.label == "notes_style"
    )
    assert "formal" in notes_style_block.value


def test_secretary_agent_initialization_defaults_to_adaptive_mode(monkeypatch):
    class FixedDateTime(real_datetime):
        @classmethod
        def now(cls, tz=None):
            dt = cls(2024, 2, 2, 10, 30, 0)
            return dt if tz is None else dt.replace(tzinfo=tz)

        @classmethod
        def utcnow(cls):
            return cls(2024, 2, 2, 10, 30, 0)

    monkeypatch.setattr(secretary_module, "datetime", FixedDateTime)
    client = DummyClient()

    secretary = SecretaryAgent(client)

    assert secretary.mode == "adaptive"
    call_kwargs = client.agents.create_calls[0]
    assert call_kwargs["name"].startswith("Adaptive Secretary ")
    persona_block = next(
        block for block in call_kwargs["memory_blocks"] if block.label == "persona"
    )
    assert "adaptive meeting secretary" in persona_block.value


def test_set_mode_updates_mode_value(fixed_datetime):
    client = DummyClient()
    secretary = SecretaryAgent(client)

    secretary.set_mode("casual")

    assert secretary.mode == "casual"


def test_set_mode_rejects_invalid_mode(fixed_datetime):
    client = DummyClient()
    secretary = SecretaryAgent(client)

    with pytest.raises(ValueError):
        secretary.set_mode("improvised")


def test_start_meeting_records_metadata_and_notifies_agent(fixed_datetime):
    client = DummyClient()
    response = SimpleNamespace(messages=[make_tool_message("Ready to take notes")])
    client.agents.messages.responses.append(response)
    secretary = SecretaryAgent(client)

    secretary.start_meeting(
        "Quarterly Review", ["Alice", "Bob"], meeting_type="planning"
    )

    metadata = secretary.meeting_metadata
    assert metadata["topic"] == "Quarterly Review"
    assert metadata["participants"] == ["Alice", "Bob"]
    assert metadata["meeting_type"] == "planning"
    assert metadata["mode"] == "adaptive"

    message_call = client.agents.messages.calls[0]
    assert message_call["agent_id"] == secretary.agent.id
    sent_message = message_call["messages"][0].content
    assert "Topic: Quarterly Review" in sent_message
    assert "Please begin taking notes" in sent_message


def test_extract_agent_response_prefers_tool_call_text(fixed_datetime):
    client = DummyClient()
    secretary = SecretaryAgent(client)

    response = SimpleNamespace(messages=[make_tool_message("Acknowledged")])

    assert secretary._extract_agent_response(response) == "Acknowledged"


def test_extract_agent_response_falls_back_to_assistant_message(fixed_datetime):
    client = DummyClient()
    secretary = SecretaryAgent(client)

    response = SimpleNamespace(messages=[make_assistant_message("Direct response")])

    assert secretary._extract_agent_response(response) == "Direct response"


def test_observe_message_sends_formatted_prompt(fixed_datetime):
    client = DummyClient()
    secretary = SecretaryAgent(client)

    secretary.observe_message("Alice", "We should revisit the budget")

    message_call = client.agents.messages.calls[-1]
    sent_message = message_call["messages"][0].content
    assert (
        sent_message
        == "Please note this in the meeting: Alice: We should revisit the budget"
    )


def test_observe_message_handles_retry_failure(fixed_datetime, monkeypatch):
    client = DummyClient()
    secretary = SecretaryAgent(client)

    def raising_retry(func, max_retries=2, backoff_factor=0.5):
        func()
        raise RuntimeError("retry failed")

    monkeypatch.setattr(secretary_module, "retry_with_backoff", raising_retry)

    secretary.observe_message("Bob", "Status update", metadata={"importance": "high"})

    message_call = client.agents.messages.calls[-1]
    sent_message = message_call["messages"][0].content
    assert sent_message.endswith("Bob: Status update")


def test_add_action_item_includes_optional_fields(fixed_datetime):
    client = DummyClient()
    secretary = SecretaryAgent(client)

    secretary.add_action_item(
        "Prepare the project report", assignee="Bob", due_date="Friday"
    )

    message_call = client.agents.messages.calls[-1]
    sent_message = message_call["messages"][0].content
    assert "Prepare the project report" in sent_message
    assert "assigned to: Bob" in sent_message
    assert "due: Friday" in sent_message


def test_add_decision_records_context(fixed_datetime):
    client = DummyClient()
    secretary = SecretaryAgent(client)

    secretary.add_decision("Approve new roadmap", context="Sprint review")

    message_call = client.agents.messages.calls[-1]
    sent_message = message_call["messages"][0].content
    assert "Approve new roadmap" in sent_message
    assert "context: Sprint review" in sent_message


def test_get_conversation_stats_combines_agent_summary(fixed_datetime):
    client = DummyClient()
    start_response = SimpleNamespace(messages=[make_assistant_message("Ready")])
    stats_response = SimpleNamespace(messages=[make_tool_message("Meeting summary")])
    client.agents.messages.responses.extend([start_response, stats_response])
    secretary = SecretaryAgent(client)

    secretary.start_meeting("Product Sync", ["Ada", "Lin"], meeting_type="sync")
    secretary.meeting_metadata["start_time"] = (
        secretary_module.datetime.now() - timedelta(minutes=5)
    )

    stats = secretary.get_conversation_stats()

    assert stats["duration_minutes"] == 5
    assert stats["participants"] == ["Ada", "Lin"]
    assert stats["topic"] == "Product Sync"
    assert stats["meeting_type"] == "sync"
    assert stats["summary"] == "Meeting summary"


def test_generate_minutes_returns_full_minutes(fixed_datetime):
    client = DummyClient()
    minutes_response = SimpleNamespace(
        messages=[
            make_tool_message(
                """
    These are the detailed meeting minutes capturing every agenda item,
    discussion point, and the follow-up actions that we agreed to pursue as a team.
    """.strip()
            )
        ]
    )
    client.agents.messages.responses.append(minutes_response)
    secretary = SecretaryAgent(client)
    secretary.meeting_metadata = {
        "meeting_type": "planning",
        "topic": "Roadmap",
        "start_time": secretary_module.datetime.now(),
    }

    minutes = secretary.generate_minutes()

    assert "detailed meeting minutes" in minutes

    message_call = client.agents.messages.calls[-1]
    sent_message = message_call["messages"][0].content
    assert "Please generate meeting minutes" in sent_message
    assert "Roadmap" in sent_message


def test_generate_minutes_reports_processing_when_content_short(fixed_datetime):
    client = DummyClient()
    minutes_response = SimpleNamespace(messages=[make_tool_message("Working on it")])
    client.agents.messages.responses.append(minutes_response)
    secretary = SecretaryAgent(client)
    secretary.meeting_metadata = {
        "meeting_type": "retro",
        "topic": "Release review",
        "start_time": secretary_module.datetime.now(),
    }

    result = secretary.generate_minutes()

    assert (
        result
        == "Secretary is still processing the meeting notes. Please try again in a moment."
    )


def test_retry_with_backoff_retries_on_server_error():
    failing_then_success = Mock(
        side_effect=[Exception("500 Internal Server Error"), "success"]
    )

    with patch.object(secretary_module.time, "sleep") as sleep_mock:
        result = secretary_module.retry_with_backoff(
            failing_then_success,
            max_retries=3,
            backoff_factor=2,
        )

    assert result == "success"
    assert failing_then_success.call_count == 2
    sleep_mock.assert_called_once_with(2)


def test_retry_with_backoff_raises_non_retryable_error():
    always_fail = Mock(side_effect=ValueError("bad request"))

    with pytest.raises(ValueError):
        secretary_module.retry_with_backoff(always_fail, max_retries=2)

    assert always_fail.call_count == 1


def test_start_meeting_handles_missing_response(fixed_datetime, capsys, monkeypatch):
    client = DummyClient()
    secretary = SecretaryAgent(client)

    def fake_retry(func, max_retries=3, backoff_factor=1):
        """
        Test helper that invokes the provided callable exactly once and returns None.

        This fake replacement for a retry-with-backoff utility ignores retry semantics and backoff parameters. It calls `func()` a single time and always returns None. Useful in tests to simulate a retry helper that does not retry or return a value.

        Parameters:
            func (callable): Function to execute once.
            max_retries (int): Ignored. Present to match the real helper's signature.
            backoff_factor (int|float): Ignored. Present to match the real helper's signature.
        """
        func()
        return None

    monkeypatch.setattr(secretary_module, "retry_with_backoff", fake_retry)

    secretary.start_meeting("Weekly Sync", ["Ada", "Lin"], meeting_type="sync")

    captured = capsys.readouterr()
    assert "Secretary may not have received meeting start notification" in captured.out
    assert client.agents.messages.calls  # Inner function executed


def test_extract_agent_response_handles_invalid_tool_json(fixed_datetime):
    client = DummyClient()
    secretary = SecretaryAgent(client)

    broken_tool_message = SimpleNamespace(
        tool_calls=[
            SimpleNamespace(
                function=SimpleNamespace(name="send_message", arguments="{")
            )
        ],
        tool_return=None,
        message_type="tool_message",
        content=None,
    )
    assistant_message = make_assistant_message("Fallback after error")
    response = SimpleNamespace(messages=[broken_tool_message, assistant_message])

    assert secretary._extract_agent_response(response) == "Fallback after error"


def test_extract_agent_response_defaults_when_no_content(fixed_datetime):
    client = DummyClient()
    secretary = SecretaryAgent(client)

    empty_message = SimpleNamespace(
        tool_calls=[],
        tool_return=None,
        message_type=None,
        content=None,
    )
    response = SimpleNamespace(messages=[empty_message])

    assert (
        secretary._extract_agent_response(response)
        == "Secretary is ready to take notes."
    )


def test_observe_message_skips_when_agent_missing(fixed_datetime):
    client = DummyClient()
    secretary = SecretaryAgent(client)
    secretary.agent = None

    secretary.observe_message("Ada", "Hello team")

    assert client.agents.messages.calls == []


def test_add_action_item_without_agent_does_not_send_message(fixed_datetime):
    client = DummyClient()
    secretary = SecretaryAgent(client)
    secretary.agent = None

    secretary.add_action_item("Prepare deck")

    assert client.agents.messages.calls == []


def test_get_conversation_stats_without_meeting_metadata_returns_summary_only(
    fixed_datetime,
):
    client = DummyClient()
    stats_response = SimpleNamespace(
        messages=[make_tool_message("Only summary provided")]
    )
    client.agents.messages.responses.append(stats_response)
    secretary = SecretaryAgent(client)
    secretary.meeting_metadata = {}

    stats = secretary.get_conversation_stats()

    assert stats == {"summary": "Only summary provided"}


def test_get_conversation_stats_requires_agent(fixed_datetime):
    client = DummyClient()
    secretary = SecretaryAgent(client)
    secretary.agent = None

    stats = secretary.get_conversation_stats()

    assert stats == {}
    assert client.agents.messages.calls == []


def test_get_conversation_stats_handles_exception(fixed_datetime):
    client = DummyClient()
    secretary = SecretaryAgent(client)
    secretary.client.agents.messages.create = Mock(side_effect=RuntimeError("fail"))

    assert secretary.get_conversation_stats() == {}


def test_generate_minutes_requires_agent(fixed_datetime):
    client = DummyClient()
    secretary = SecretaryAgent(client)
    secretary.agent = None

    assert secretary.generate_minutes() == "Secretary agent not available."


def test_generate_minutes_requires_meeting_metadata(fixed_datetime):
    client = DummyClient()
    secretary = SecretaryAgent(client)
    secretary.meeting_metadata = {}

    assert secretary.generate_minutes() == "No meeting in progress."


def test_generate_minutes_handles_missing_response(fixed_datetime, monkeypatch):
    client = DummyClient()
    secretary = SecretaryAgent(client)
    secretary.meeting_metadata = {
        "meeting_type": "sync",
        "topic": "Roadmap",
    }

    def fake_retry(func, max_retries=3, backoff_factor=1):
        """
        Test helper that invokes the provided callable exactly once and returns None.

        This fake replacement for a retry-with-backoff utility ignores retry semantics and backoff parameters. It calls `func()` a single time and always returns None. Useful in tests to simulate a retry helper that does not retry or return a value.

        Parameters:
            func (callable): Function to execute once.
            max_retries (int): Ignored. Present to match the real helper's signature.
            backoff_factor (int|float): Ignored. Present to match the real helper's signature.
        """
        func()
        return None

    monkeypatch.setattr(secretary_module, "retry_with_backoff", fake_retry)

    result = secretary.generate_minutes()

    assert result == "Secretary is temporarily unavailable. Please try again."


def test_generate_minutes_handles_exception(fixed_datetime, monkeypatch):
    client = DummyClient()
    secretary = SecretaryAgent(client)
    secretary.meeting_metadata = {
        "meeting_type": "sync",
        "topic": "Roadmap",
    }

    def fake_retry(func, max_retries=3, backoff_factor=1):
        """
        Test helper that simulates a failing retry function.

        This replacement for a retry helper always raises RuntimeError("boom"), regardless of the provided
        callable or retry parameters. Use in tests to simulate an unrecoverable error from retry logic.

        Parameters:
            func: Ignored. The callable that would be retried.
            max_retries (int): Ignored. Retry limit placeholder.
            backoff_factor (int|float): Ignored. Backoff multiplier placeholder.

        Raises:
            RuntimeError: Always raised with message "boom".
        """
        raise RuntimeError("boom")

    monkeypatch.setattr(secretary_module, "retry_with_backoff", fake_retry)

    result = secretary.generate_minutes()

    assert result.startswith("Error generating minutes: boom")
