"""Unit tests for CLI session management functionality."""

import json
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import pytest

from spds.main import main
from spds.session_store import JsonSessionStore
from spds.session_context import get_current_session_id, set_current_session_id


@pytest.fixture
def temp_sessions_dir():
    """Create a temporary sessions directory for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        sessions_dir = Path(tmpdir) / "sessions"
        yield sessions_dir


@pytest.fixture
def mock_config(temp_sessions_dir):
    """Mock configuration to use temporary sessions directory."""
    with patch("spds.config.get_sessions_dir", return_value=temp_sessions_dir):
        yield temp_sessions_dir


def test_sessions_list_empty(mock_config, capsys):
    """Test sessions list command with no sessions."""
    with patch("spds.main.get_default_session_store") as mock_get_store:
        mock_get_store.return_value = JsonSessionStore(mock_config)

        with patch("sys.argv", ["spds", "sessions", "list"]):
            result = main(["sessions", "list"])

        assert result == 0
        captured = capsys.readouterr()
        assert "No sessions found" in captured.out


def test_sessions_list_with_sessions(mock_config, capsys):
    """Test sessions list command with multiple sessions."""
    # Create some test sessions
    store = JsonSessionStore(mock_config)
    store.create(title="Test Session 1", tags=["test", "demo"])
    store.create(title="Test Session 2", tags=["prod"])

    with patch("spds.main.get_default_session_store") as mock_get_store:
        mock_get_store.return_value = store

        with patch("sys.argv", ["spds", "sessions", "list"]):
            result = main(["sessions", "list"])

        assert result == 0
        captured = capsys.readouterr()
        assert "Test Session 1" in captured.out
        assert "Test Session 2" in captured.out
        assert "test, demo" in captured.out
        assert "prod" in captured.out


def test_sessions_list_json_format(mock_config, capsys):
    """Test sessions list command with JSON output."""
    # Create a test session
    store = JsonSessionStore(mock_config)
    session = store.create(title="JSON Test Session", tags=["json"])

    with patch("spds.main.get_default_session_store") as mock_get_store:
        mock_get_store.return_value = store

        with patch("sys.argv", ["spds", "sessions", "list", "--json"]):
            result = main(["sessions", "list", "--json"])

        assert result == 0
        captured = capsys.readouterr()

        # Parse JSON output
        sessions_data = json.loads(captured.out)
        assert len(sessions_data) == 1
        assert sessions_data[0]["title"] == "JSON Test Session"
        assert sessions_data[0]["tags"] == ["json"]
        assert sessions_data[0]["id"] == session.meta.id


def test_sessions_resume_existing_session(mock_config, capsys):
    """Test resuming an existing session."""
    # Create a test session
    store = JsonSessionStore(mock_config)
    session = store.create(title="Resume Test Session")

    # Clear any existing session context
    set_current_session_id(None)

    with patch("spds.main.get_default_session_store") as mock_get_store:
        mock_get_store.return_value = store

        with patch("sys.argv", ["spds", "sessions", "resume", session.meta.id]):
            result = main(["sessions", "resume", session.meta.id])

        assert result == 0
        captured = capsys.readouterr()
        assert f"Session resumed: {session.meta.id}" in captured.out

        # Verify session context is set
        assert get_current_session_id() == session.meta.id


def test_sessions_resume_nonexistent_session(mock_config, capsys):
    """Test resuming a non-existent session."""
    nonexistent_id = "nonexistent-session-id"

    with patch("spds.main.get_default_session_store") as mock_get_store:
        mock_get_store.return_value = JsonSessionStore(mock_config)

        with patch("sys.argv", ["spds", "sessions", "resume", nonexistent_id]):
            result = main(["sessions", "resume", nonexistent_id])

        assert result == 2
        captured = capsys.readouterr()
        assert f"Session '{nonexistent_id}' not found" in captured.err


def test_main_with_session_id(mock_config, monkeypatch):
    """Test running main with --session-id option."""
    # Create a test session
    store = JsonSessionStore(mock_config)
    session = store.create(title="CLI Test Session")

    # Mock the swarm manager to avoid network calls
    class MockSwarm:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

        def start_chat_with_topic(self, topic):
            pass

    # Clear session context
    set_current_session_id(None)

    with patch("spds.main.get_default_session_store") as mock_get_store, \
         patch("spds.main.SwarmManager", MockSwarm), \
         patch("spds.main.Letta"), \
         patch("builtins.input", return_value="Test Topic"):

        mock_get_store.return_value = store

        # Run main with session ID
        result = main(["--session-id", session.meta.id])

    assert result == 0
    # Verify session context is set
    assert get_current_session_id() == session.meta.id


def test_main_with_new_session_no_title(mock_config, monkeypatch, capsys):
    """Test running main with --new-session option (no title)."""
    # Clear any existing session context
    set_current_session_id(None)

    class MockSwarm:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

        def start_chat_with_topic(self, topic):
            pass

    with patch("spds.main.get_default_session_store") as mock_get_store, \
         patch("spds.main.SwarmManager", MockSwarm), \
         patch("spds.main.Letta"), \
         patch("builtins.input", return_value="Test Topic"):

        store = JsonSessionStore(mock_config)
        mock_get_store.return_value = store

        # Run main with --new-session (no title)
        result = main(["--new-session"])

    assert result == 0

    # Verify a new session was created and context is set
    current_session_id = get_current_session_id()
    assert current_session_id is not None

    # Verify the session exists in the store
    session_state = store.load(current_session_id)
    assert session_state.meta.title is None  # No title provided


def test_main_with_new_session_with_title(mock_config, monkeypatch, capsys):
    """Test running main with --new-session option with title."""
    # Clear any existing session context
    set_current_session_id(None)

    class MockSwarm:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

        def start_chat_with_topic(self, topic):
            pass

    with patch("spds.main.get_default_session_store") as mock_get_store, \
         patch("spds.main.SwarmManager", MockSwarm), \
         patch("spds.main.Letta"), \
         patch("builtins.input", return_value="Test Topic"):

        store = JsonSessionStore(mock_config)
        mock_get_store.return_value = store

        # Run main with --new-session and title
        result = main(["--new-session", "My Custom Session"])

    assert result == 0

    # Verify a new session was created with the title
    current_session_id = get_current_session_id()
    assert current_session_id is not None

    # Verify the session exists in the store with correct title
    session_state = store.load(current_session_id)
    assert session_state.meta.title == "My Custom Session"


def test_main_backward_compatibility_no_session(mock_config, monkeypatch):
    """Test that main works without session management (backward compatibility)."""
    # Clear any existing session context
    set_current_session_id(None)

    class MockSwarm:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

        def start_chat_with_topic(self, topic):
            pass

    with patch("spds.main.get_default_session_store") as mock_get_store, \
         patch("spds.main.SwarmManager", MockSwarm), \
         patch("spds.main.Letta"), \
         patch("builtins.input", return_value="Test Topic"):

        mock_get_store.return_value = JsonSessionStore(mock_config)

        # Run main without any session options
        result = main([])

    assert result == 0
    # No session should be set
    assert get_current_session_id() is None


def test_main_session_id_and_new_session_conflict(mock_config):
    """Test that --session-id and --new-session cannot be used together."""
    # This should be handled by argparse, but let's test the behavior
    with pytest.raises(SystemExit):
        main(["--session-id", "some-id", "--new-session"])


def test_sessions_help_command(capsys):
    """Test that sessions help works correctly."""
    with pytest.raises(SystemExit) as exc_info:
        main(["sessions", "--help"])

    # argparse exits with code 0 for help
    assert exc_info.value.code == 0

    captured = capsys.readouterr()
    assert "list" in captured.out
    assert "resume" in captured.out


def test_session_id_validation_in_main(mock_config):
    """Test that invalid session ID in main is handled correctly."""
    invalid_id = "invalid-session-id-that-does-not-exist"

    with patch("spds.main.get_default_session_store") as mock_get_store:
        store = JsonSessionStore(mock_config)
        mock_get_store.return_value = store

        with pytest.raises(SystemExit) as exc_info:
            main(["--session-id", invalid_id])

        assert exc_info.value.code == 2


def test_session_context_preserved_through_execution(mock_config, monkeypatch):
    """Test that session context is preserved through the execution flow."""
    # Create a test session
    store = JsonSessionStore(mock_config)
    session = store.create(title="Context Test Session")

    # Track whether session context was available during swarm operations
    context_captured = {}

    class MockSwarm:
        def __init__(self, **kwargs):
            # Capture session context during initialization
            context_captured['init'] = get_current_session_id()

        def start_chat_with_topic(self, topic):
            # Capture session context during chat start
            context_captured['chat'] = get_current_session_id()

    # Clear session context
    set_current_session_id(None)

    with patch("spds.main.get_default_session_store") as mock_get_store, \
         patch("spds.main.SwarmManager", MockSwarm), \
         patch("spds.main.Letta"), \
         patch("builtins.input", return_value="Test Topic"):

        mock_get_store.return_value = store

        # Run with session ID
        result = main(["--session-id", session.meta.id])

    assert result == 0
    # Verify session context was available at both points
    assert context_captured['init'] == session.meta.id
    assert context_captured['chat'] == session.meta.id


def test_multiple_sessions_created_separately(mock_config):
    """Test that multiple sessions can be created and managed separately."""
    store = JsonSessionStore(mock_config)

    # Create multiple sessions
    store.create(title="Session 1", tags=["first"])
    store.create(title="Session 2", tags=["second"])
    store.create(title="Session 3", tags=["third"])

    # List all sessions
    sessions = store.list_sessions()
    assert len(sessions) == 3

    # Verify all sessions are listed
    session_titles = {s.title for s in sessions}
    assert session_titles == {"Session 1", "Session 2", "Session 3"}


def test_session_list_ordering(mock_config):
    """Test that sessions are listed in reverse chronological order."""
    store = JsonSessionStore(mock_config)

    # Create sessions with different timestamps
    session1 = store.create(title="First Session")
    # Simulate older session by manually setting created_at
    session1.meta.created_at = datetime(2023, 1, 1)
    store._save_session_state(session1)

    session2 = store.create(title="Second Session")
    session2.meta.created_at = datetime(2023, 6, 15)
    store._save_session_state(session2)

    store.create(title="Third Session")
    # This one keeps current timestamp (most recent)

    # List sessions
    sessions = store.list_sessions()

    # Should be ordered by created_at descending
    assert len(sessions) == 3
    assert sessions[0].title == "Third Session"  # Most recent
    assert sessions[1].title == "Second Session"
    assert sessions[2].title == "First Session"  # Oldest
