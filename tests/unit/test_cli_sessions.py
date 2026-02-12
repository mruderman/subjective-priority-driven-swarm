"""Unit tests for CLI session management functionality.

Tests the session-related commands in spds.main after the migration to the
Letta Conversations API.  All Letta client / ConversationManager interactions
are mocked.
"""

import json
from argparse import Namespace
from types import SimpleNamespace
from unittest.mock import MagicMock, Mock, patch

import pytest

from spds.conversations import ConversationManager as _RealCM
from spds.main import (
    format_session_table,
    list_sessions_command,
    main,
    resume_session_command,
)

# The real parse_spds_summary — used to wire into mocked ConversationManager
_real_parse_spds_summary = _RealCM.parse_spds_summary


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_client():
    """Return a MagicMock that mimics a Letta client."""
    client = MagicMock()
    return client


def _make_conversation(id, summary="", created_at=None, updated_at=None, agent_id="agent-1"):
    """Create a mock Conversation object."""
    conv = Mock()
    conv.id = id
    conv.summary = summary
    conv.agent_id = agent_id
    conv.created_at = created_at
    conv.updated_at = updated_at
    return conv


def _make_message(role="user", content="Hello"):
    """Create a mock message object."""
    msg = SimpleNamespace(role=role, content=content)
    return msg


# ---------------------------------------------------------------------------
# list_sessions_command
# ---------------------------------------------------------------------------

class TestListSessionsCommand:

    def test_requires_client(self, capsys):
        """Returns 1 when no client is provided."""
        args = Namespace(agent_id="agent-1", json=False, spds_session=None)
        result = list_sessions_command(args, client=None)

        assert result == 1
        assert "Letta client required" in capsys.readouterr().err

    def test_requires_agent_id(self, mock_client, capsys):
        """Returns 1 when --agent-id is not provided."""
        args = Namespace(agent_id=None, json=False, spds_session=None)
        result = list_sessions_command(args, client=mock_client)

        assert result == 1
        assert "agent-id is required" in capsys.readouterr().err

    def test_lists_sessions_table(self, mock_client, capsys):
        """Prints a table when sessions exist."""
        convs = [
            _make_conversation("conv-1", summary="spds:sess-1|Alice|Budget"),
            _make_conversation("conv-2", summary="spds:sess-1|Bob|Budget"),
        ]

        with patch("spds.main.ConversationManager") as MockCM:
            MockCM.parse_spds_summary = _real_parse_spds_summary
            cm_instance = MockCM.return_value
            cm_instance.list_sessions.return_value = convs

            args = Namespace(agent_id="agent-1", json=False, spds_session=None)
            result = list_sessions_command(args, client=mock_client)

        assert result == 0
        output = capsys.readouterr().out
        assert "conv-1" in output or "conv-1..."[:8] in output

    def test_lists_sessions_empty(self, mock_client, capsys):
        """Prints 'No sessions found' when no sessions exist."""
        with patch("spds.main.ConversationManager") as MockCM:
            cm_instance = MockCM.return_value
            cm_instance.list_sessions.return_value = []

            args = Namespace(agent_id="agent-1", json=False, spds_session=None)
            result = list_sessions_command(args, client=mock_client)

        assert result == 0
        output = capsys.readouterr().out
        assert "No sessions found" in output

    def test_lists_sessions_json(self, mock_client, capsys):
        """Outputs JSON when --json is set."""
        convs = [_make_conversation("conv-j1", summary="JSON test")]

        with patch("spds.main.ConversationManager") as MockCM:
            cm_instance = MockCM.return_value
            cm_instance.list_sessions.return_value = convs
            cm_instance.get_session_summary.return_value = {
                "id": "conv-j1",
                "summary": "JSON test",
                "agent_id": "agent-1",
                "created_at": None,
                "updated_at": None,
            }

            args = Namespace(agent_id="agent-1", json=True, spds_session=None)
            result = list_sessions_command(args, client=mock_client)

        assert result == 0
        output = capsys.readouterr().out
        data = json.loads(output)
        assert len(data) == 1
        assert data[0]["id"] == "conv-j1"

    def test_spds_session_filter(self, mock_client, capsys):
        """Uses find_sessions_by_spds_id when --spds-session is provided."""
        convs = [_make_conversation("conv-f1", summary="spds:sess-abc|Alice|Topic")]

        with patch("spds.main.ConversationManager") as MockCM:
            MockCM.parse_spds_summary = _real_parse_spds_summary
            cm_instance = MockCM.return_value
            cm_instance.find_sessions_by_spds_id.return_value = convs

            args = Namespace(agent_id="agent-1", json=False, spds_session="sess-abc")
            result = list_sessions_command(args, client=mock_client)

        assert result == 0
        cm_instance.find_sessions_by_spds_id.assert_called_once_with("agent-1", "sess-abc")
        cm_instance.list_sessions.assert_not_called()


# ---------------------------------------------------------------------------
# resume_session_command
# ---------------------------------------------------------------------------

class TestResumeSessionCommand:

    def test_requires_client(self, capsys):
        """Returns 1 when no client is provided."""
        args = Namespace(session_id="conv-123")
        result = resume_session_command(args, client=None)

        assert result == 1
        assert "Letta client required" in capsys.readouterr().err

    def test_resumes_with_spds_metadata(self, mock_client, capsys):
        """Displays SPDS metadata and messages for a tagged conversation."""
        conv = _make_conversation("conv-resume", summary="spds:sess-x|Alice|Budget")
        msgs = [
            _make_message("user", "Hello Alice"),
            _make_message("assistant", "Hi, I'm Alice!"),
        ]

        with patch("spds.main.ConversationManager") as MockCM:
            MockCM.parse_spds_summary = _real_parse_spds_summary
            cm_instance = MockCM.return_value
            cm_instance.get_session.return_value = conv
            cm_instance.list_messages.return_value = msgs

            args = Namespace(session_id="conv-resume")
            result = resume_session_command(args, client=mock_client)

        assert result == 0
        output = capsys.readouterr().out
        assert "sess-x" in output
        assert "Alice" in output
        assert "Budget" in output
        assert "Recent messages" in output

    def test_resumes_with_plain_summary(self, mock_client, capsys):
        """Handles non-SPDS conversations gracefully."""
        conv = _make_conversation("conv-plain", summary="Just a chat")
        msgs = [_make_message("user", "Test message")]

        with patch("spds.main.ConversationManager") as MockCM:
            MockCM.parse_spds_summary = _real_parse_spds_summary
            cm_instance = MockCM.return_value
            cm_instance.get_session.return_value = conv
            cm_instance.list_messages.return_value = msgs

            args = Namespace(session_id="conv-plain")
            result = resume_session_command(args, client=mock_client)

        assert result == 0
        output = capsys.readouterr().out
        assert "conv-plain" in output
        assert "Just a chat" in output

    def test_resumes_with_no_messages(self, mock_client, capsys):
        """Handles conversations with no messages."""
        conv = _make_conversation("conv-empty", summary="spds:sess-e|Bob|Testing")

        with patch("spds.main.ConversationManager") as MockCM:
            MockCM.parse_spds_summary = _real_parse_spds_summary
            cm_instance = MockCM.return_value
            cm_instance.get_session.return_value = conv
            cm_instance.list_messages.return_value = []

            args = Namespace(session_id="conv-empty")
            result = resume_session_command(args, client=mock_client)

        assert result == 0
        output = capsys.readouterr().out
        assert "No messages" in output

    def test_resume_nonexistent_session(self, mock_client, capsys):
        """Returns 2 and prints error for non-existent conversation."""
        with patch("spds.main.ConversationManager") as MockCM:
            cm_instance = MockCM.return_value
            cm_instance.get_session.side_effect = Exception("Not found")

            args = Namespace(session_id="bad-id")
            result = resume_session_command(args, client=mock_client)

        assert result == 2
        assert "not found" in capsys.readouterr().err.lower()

    def test_resume_completed_shows_status(self, mock_client, capsys):
        """Shows completed status for finalized conversations."""
        conv = _make_conversation(
            "conv-done",
            summary="spds:sess-d|Alice|Budget|completed|msgs=5|mode=hybrid",
        )

        with patch("spds.main.ConversationManager") as MockCM:
            MockCM.parse_spds_summary = _real_parse_spds_summary
            cm_instance = MockCM.return_value
            cm_instance.get_session.return_value = conv
            cm_instance.list_messages.return_value = []

            args = Namespace(session_id="conv-done")
            result = resume_session_command(args, client=mock_client)

        assert result == 0
        output = capsys.readouterr().out
        assert "completed" in output


# ---------------------------------------------------------------------------
# format_session_table
# ---------------------------------------------------------------------------

class TestFormatSessionTable:

    def test_empty_list(self):
        """Returns 'No sessions found' for empty list."""
        assert format_session_table([]) == "No sessions found."

    def test_with_spds_conversations(self):
        """Formats SPDS-tagged conversations with parsed metadata."""
        convs = [
            _make_conversation(
                "conv-abc123",
                summary="spds:sess-1|Alice|Budget Discussion",
            ),
        ]
        table = format_session_table(convs)
        assert "conv-abc" in table
        assert "Alice" in table
        assert "Budget" in table
        assert "active" in table

    def test_with_completed_conversation(self):
        """Shows completed status for finalized conversations."""
        convs = [
            _make_conversation(
                "conv-def456",
                summary="spds:sess-2|Bob|Planning|completed|msgs=10|mode=hybrid",
            ),
        ]
        table = format_session_table(convs)
        assert "Bob" in table
        assert "Planning" in table
        assert "completed" in table

    def test_with_plain_conversations(self):
        """Handles non-SPDS conversations with raw summary."""
        from datetime import datetime, timezone

        convs = [
            _make_conversation(
                "conv-xyz789",
                summary="Test conversation",
                created_at=datetime(2026, 1, 15, 10, 30, tzinfo=timezone.utc),
            ),
        ]
        table = format_session_table(convs)
        assert "conv-xyz" in table
        assert "2026-01-15" in table

    def test_table_has_header(self):
        """Table includes column headers."""
        convs = [_make_conversation("conv-1", summary="spds:s|A|T")]
        table = format_session_table(convs)
        assert "ID" in table
        assert "Agent" in table
        assert "Topic" in table


# ---------------------------------------------------------------------------
# main() integration (argument parsing and dispatch)
# ---------------------------------------------------------------------------

class TestMainSessionIntegration:

    def test_sessions_list_subcommand(self, mock_client, capsys):
        """'sessions list' dispatches to list_sessions_command."""
        with patch("spds.main.ConversationManager") as MockCM, \
             patch("spds.main.Letta", return_value=mock_client), \
             patch("spds.main.config") as mock_config:
            MockCM.parse_spds_summary = _real_parse_spds_summary
            mock_config.get_letta_password.return_value = None
            mock_config.LETTA_ENVIRONMENT = "SELF_HOSTED"
            mock_config.LETTA_API_KEY = None
            mock_config.LETTA_BASE_URL = "http://localhost:8283"

            cm_instance = MockCM.return_value
            cm_instance.list_sessions.return_value = []

            result = main(["sessions", "list", "--agent-id", "agent-1"])

        assert result == 0

    def test_sessions_resume_subcommand(self, mock_client, capsys):
        """'sessions resume' dispatches to resume_session_command."""
        with patch("spds.main.ConversationManager") as MockCM, \
             patch("spds.main.Letta", return_value=mock_client), \
             patch("spds.main.config") as mock_config:
            MockCM.parse_spds_summary = _real_parse_spds_summary
            mock_config.get_letta_password.return_value = None
            mock_config.LETTA_ENVIRONMENT = "SELF_HOSTED"
            mock_config.LETTA_API_KEY = None
            mock_config.LETTA_BASE_URL = "http://localhost:8283"

            cm_instance = MockCM.return_value
            cm_instance.get_session.return_value = _make_conversation(
                "conv-resume-main", summary="spds:s1|Agent|Topic"
            )
            cm_instance.list_messages.return_value = []

            result = main(["sessions", "resume", "conv-resume-main"])

        assert result == 0

    def test_sessions_help(self, capsys):
        """'sessions --help' exits cleanly with usage info."""
        with pytest.raises(SystemExit) as exc_info:
            main(["sessions", "--help"])

        assert exc_info.value.code == 0
        output = capsys.readouterr().out
        assert "list" in output
        assert "resume" in output
