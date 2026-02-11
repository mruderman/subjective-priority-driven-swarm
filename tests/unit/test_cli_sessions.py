"""Unit tests for CLI session management functionality.

Tests the session-related commands in spds.main after the migration to the
Letta Conversations API.  All Letta client / ConversationManager interactions
are mocked.
"""

import json
from argparse import Namespace
from unittest.mock import MagicMock, Mock, patch

import pytest

from spds.main import (
    format_session_table,
    list_sessions_command,
    main,
    resume_session_command,
    setup_session_context,
)
from spds.session_context import (
    clear_session_context,
    get_current_session_id,
    set_current_session_id,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _reset_session_context():
    """Clear conversation context before and after each test."""
    clear_session_context()
    yield
    clear_session_context()


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


# ---------------------------------------------------------------------------
# setup_session_context
# ---------------------------------------------------------------------------

class TestSetupSessionContext:

    def test_sets_context_from_session_id(self):
        """setup_session_context sets the ContextVar when session_id is present."""
        args = Namespace(session_id="conv-123")
        result = setup_session_context(args)

        assert result == "conv-123"
        assert get_current_session_id() == "conv-123"

    def test_returns_none_when_no_session_id(self):
        """Returns None and does not set context when no session_id."""
        args = Namespace(session_id=None)
        result = setup_session_context(args)

        assert result is None
        assert get_current_session_id() is None

    def test_returns_none_when_attr_missing(self):
        """Returns None when args has no session_id attribute."""
        args = Namespace()
        result = setup_session_context(args)

        assert result is None


# ---------------------------------------------------------------------------
# list_sessions_command
# ---------------------------------------------------------------------------

class TestListSessionsCommand:

    def test_requires_client(self, capsys):
        """Returns 1 when no client is provided."""
        args = Namespace(agent_id="agent-1", json=False)
        result = list_sessions_command(args, client=None)

        assert result == 1
        assert "Letta client required" in capsys.readouterr().err

    def test_requires_agent_id(self, mock_client, capsys):
        """Returns 1 when --agent-id is not provided."""
        args = Namespace(agent_id=None, json=False)
        result = list_sessions_command(args, client=mock_client)

        assert result == 1
        assert "agent-id is required" in capsys.readouterr().err

    def test_lists_sessions_table(self, mock_client, capsys):
        """Prints a table when sessions exist."""
        convs = [
            _make_conversation("conv-1", summary="First convo"),
            _make_conversation("conv-2", summary="Second convo"),
        ]

        with patch("spds.main.ConversationManager") as MockCM:
            cm_instance = MockCM.return_value
            cm_instance.list_sessions.return_value = convs

            args = Namespace(agent_id="agent-1", json=False)
            result = list_sessions_command(args, client=mock_client)

        assert result == 0
        output = capsys.readouterr().out
        assert "conv-1" in output or "conv-1..."[:8] in output

    def test_lists_sessions_empty(self, mock_client, capsys):
        """Prints 'No sessions found' when no sessions exist."""
        with patch("spds.main.ConversationManager") as MockCM:
            cm_instance = MockCM.return_value
            cm_instance.list_sessions.return_value = []

            args = Namespace(agent_id="agent-1", json=False)
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

            args = Namespace(agent_id="agent-1", json=True)
            result = list_sessions_command(args, client=mock_client)

        assert result == 0
        output = capsys.readouterr().out
        data = json.loads(output)
        assert len(data) == 1
        assert data[0]["id"] == "conv-j1"


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

    def test_resumes_existing_session(self, mock_client, capsys):
        """Sets context and prints confirmation for existing conversation."""
        with patch("spds.main.ConversationManager") as MockCM:
            cm_instance = MockCM.return_value
            cm_instance.get_session.return_value = _make_conversation("conv-resume")

            args = Namespace(session_id="conv-resume")
            result = resume_session_command(args, client=mock_client)

        assert result == 0
        assert get_current_session_id() == "conv-resume"
        assert "Session resumed: conv-resume" in capsys.readouterr().out

    def test_resume_nonexistent_session(self, mock_client, capsys):
        """Returns 2 and prints error for non-existent conversation."""
        with patch("spds.main.ConversationManager") as MockCM:
            cm_instance = MockCM.return_value
            cm_instance.get_session.side_effect = Exception("Not found")

            args = Namespace(session_id="bad-id")
            result = resume_session_command(args, client=mock_client)

        assert result == 2
        assert "not found" in capsys.readouterr().err.lower()


# ---------------------------------------------------------------------------
# format_session_table
# ---------------------------------------------------------------------------

class TestFormatSessionTable:

    def test_empty_list(self):
        """Returns 'No sessions found' for empty list."""
        assert format_session_table([]) == "No sessions found."

    def test_with_conversations(self):
        """Formats conversation objects into a table."""
        from datetime import datetime, timezone

        convs = [
            _make_conversation(
                "conv-abc123",
                summary="Test conversation",
                created_at=datetime(2026, 1, 15, 10, 30, tzinfo=timezone.utc),
                updated_at=datetime(2026, 1, 15, 11, 0, tzinfo=timezone.utc),
            ),
        ]
        table = format_session_table(convs)
        assert "conv-abc" in table
        assert "2026-01-15" in table


# ---------------------------------------------------------------------------
# main() integration (argument parsing and dispatch)
# ---------------------------------------------------------------------------

class TestMainSessionIntegration:

    def test_sessions_list_subcommand(self, mock_client, capsys):
        """'sessions list' dispatches to list_sessions_command."""
        with patch("spds.main.ConversationManager") as MockCM, \
             patch("spds.main.Letta", return_value=mock_client), \
             patch("spds.main.config") as mock_config:
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
            mock_config.get_letta_password.return_value = None
            mock_config.LETTA_ENVIRONMENT = "SELF_HOSTED"
            mock_config.LETTA_API_KEY = None
            mock_config.LETTA_BASE_URL = "http://localhost:8283"

            cm_instance = MockCM.return_value
            cm_instance.get_session.return_value = _make_conversation("conv-resume-main")

            result = main(["sessions", "resume", "conv-resume-main"])

        assert result == 0
        assert get_current_session_id() == "conv-resume-main"

    def test_session_id_sets_context(self, mock_client):
        """--session-id sets the conversation context before swarm starts."""
        context_captured = {}

        class MockSwarm:
            def __init__(self, **kwargs):
                context_captured["init"] = get_current_session_id()

            def start_chat_with_topic(self, topic):
                context_captured["chat"] = get_current_session_id()

        with patch("spds.main.SwarmManager", MockSwarm), \
             patch("spds.main.Letta", return_value=mock_client), \
             patch("spds.main.config") as mock_config, \
             patch("builtins.input", return_value="Test Topic"):
            mock_config.get_letta_password.return_value = None
            mock_config.LETTA_ENVIRONMENT = "SELF_HOSTED"
            mock_config.LETTA_API_KEY = None
            mock_config.LETTA_BASE_URL = "http://localhost:8283"
            mock_config.AGENT_PROFILES = []
            mock_config.get_agent_profiles_validated.return_value = Mock(
                agents=[Mock(dict=lambda: {"name": "A", "persona": "p", "expertise": []})]
            )

            result = main(["--session-id", "conv-ctx-test"])

        assert result == 0
        assert context_captured.get("init") == "conv-ctx-test"
        assert context_captured.get("chat") == "conv-ctx-test"

    def test_no_session_flag_leaves_context_empty(self, mock_client):
        """Running without --session-id leaves context as None."""
        class MockSwarm:
            def __init__(self, **kwargs):
                pass

            def start_chat_with_topic(self, topic):
                pass

        with patch("spds.main.SwarmManager", MockSwarm), \
             patch("spds.main.Letta", return_value=mock_client), \
             patch("spds.main.config") as mock_config, \
             patch("builtins.input", return_value="Test Topic"):
            mock_config.get_letta_password.return_value = None
            mock_config.LETTA_ENVIRONMENT = "SELF_HOSTED"
            mock_config.LETTA_API_KEY = None
            mock_config.LETTA_BASE_URL = "http://localhost:8283"
            mock_config.AGENT_PROFILES = []
            mock_config.get_agent_profiles_validated.return_value = Mock(
                agents=[Mock(dict=lambda: {"name": "A", "persona": "p", "expertise": []})]
            )

            result = main([])

        assert result == 0
        assert get_current_session_id() is None

    def test_sessions_help(self, capsys):
        """'sessions --help' exits cleanly with usage info."""
        with pytest.raises(SystemExit) as exc_info:
            main(["sessions", "--help"])

        assert exc_info.value.code == 0
        output = capsys.readouterr().out
        assert "list" in output
        assert "resume" in output
