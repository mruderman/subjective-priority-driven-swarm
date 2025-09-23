# tests/unit/test_persistence_hooks.py

import json
import os
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from spds.secretary_agent import SecretaryAgent
from spds.session_context import (
    ensure_session,
    get_current_session_id,
    new_session_id,
    set_current_session_id,
)
from spds.session_store import JsonSessionStore, SessionEvent
from spds.session_tracking import get_default_session_tracker
from spds.spds_agent import SPDSAgent
from spds.swarm_manager import SwarmManager


class TestPersistenceHooks:
    """Test cases for session persistence hooks in core runtime paths."""

    def setup_method(self):
        """Reset the default session tracker before each test."""
        import spds.session_tracking

        spds.session_tracking._default_tracker = None

        # Enable ephemeral agents for tests
        os.environ["SPDS_ALLOW_EPHEMERAL_AGENTS"] = "true"

    def teardown_method(self):
        """Clean up after each test."""
        # Restore default ephemeral agents setting
        if "SPDS_ALLOW_EPHEMERAL_AGENTS" in os.environ:
            del os.environ["SPDS_ALLOW_EPHEMERAL_AGENTS"]

    @pytest.fixture
    def temp_sessions_dir(self):
        """Create a temporary directory for session storage."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir) / "sessions"

    @pytest.fixture
    def mock_client(self):
        """Create a mock Letta client."""
        client = Mock()
        client.agents = Mock()
        client.agents.retrieve = Mock()
        client.agents.list = Mock()
        client.agents.create = Mock()
        client.agents.messages = Mock()
        client.agents.messages.create = Mock()
        client.agents.messages.reset = Mock()
        client.agents.messages.list = Mock()
        client.agents.tools = Mock()
        client.agents.tools.attach = Mock()
        return client

    @pytest.fixture
    def mock_agent_state(self):
        """Create a mock agent state."""
        agent_state = Mock()
        agent_state.id = "test-agent-123"
        agent_state.name = "TestAgent"
        agent_state.tools = []
        agent_state.system = "Your persona is: a helpful assistant."
        return agent_state

    def test_session_context_helpers(self):
        """Test session context helper functions."""
        # Test new_session_id
        session_id = new_session_id()
        assert len(session_id) == 36  # UUID4 string is 36 characters
        assert session_id != new_session_id()  # Should be unique

        # Test set/get current session ID
        set_current_session_id("test-session-123")
        assert get_current_session_id() == "test-session-123"

        # Test ensure_session with existing session
        set_current_session_id("test-session-123")
        mock_store = Mock()
        mock_store.create.return_value = Mock(meta=Mock(id="existing-session"))
        session_id = ensure_session(mock_store)
        assert get_current_session_id() == "test-session-123"

    def test_spds_agent_assessment_tracking(
        self, temp_sessions_dir, mock_client, mock_agent_state
    ):
        """Test that SPDSAgent assessment calls are tracked."""
        # Set up session context
        set_current_session_id("test-session-123")

        # Mock the session store
        with patch("spds.session_tracking.get_default_session_store") as mock_get_store:
            mock_store = Mock()
            mock_store.save_event = Mock()
            mock_get_store.return_value = mock_store

            # Create SPDSAgent
            agent = SPDSAgent(mock_agent_state, mock_client)

            # Mock the assessment method to avoid actual Letta calls
            with patch.object(agent, "_get_full_assessment") as mock_assess:
                mock_assess.return_value = None
                agent.last_assessment = Mock(
                    importance_to_self=8,
                    perceived_gap=7,
                    unique_perspective=6,
                    emotional_investment=5,
                    expertise_relevance=9,
                    urgency=4,
                    importance_to_group=3,
                    model_dump=lambda: {
                        "importance_to_self": 8,
                        "perceived_gap": 7,
                        "unique_perspective": 6,
                        "emotional_investment": 5,
                        "expertise_relevance": 9,
                        "urgency": 4,
                        "importance_to_group": 3,
                    },
                )

                # Call assess_motivation_and_priority
                agent.assess_motivation_and_priority("test topic")

                # Verify tracking was called
                assert mock_store.save_event.called
                call_args = mock_store.save_event.call_args[0][0]
                assert call_args.actor == "TestAgent"
                assert call_args.type == "decision"
                assert call_args.payload["decision_type"] == "motivation_assessment"
                assert call_args.payload["topic"] == "test topic"

    def test_secretary_meeting_start_tracking(self, temp_sessions_dir, mock_client):
        """Test that SecretaryAgent meeting start is tracked."""
        # Set up session context
        set_current_session_id("test-session-123")

        # Mock the session store
        with patch("spds.session_tracking.get_default_session_store") as mock_get_store:
            mock_store = Mock()
            mock_store.save_event = Mock()
            mock_get_store.return_value = mock_store

            # Mock the secretary agent creation
            with patch("spds.secretary_agent.letta_call") as mock_letta_call:
                mock_agent_state = Mock()
                mock_agent_state.id = "secretary-123"
                mock_agent_state.name = "Secretary"
                mock_letta_call.return_value = mock_agent_state

                # Create SecretaryAgent
                secretary = SecretaryAgent(mock_client, mode="formal")

                # Start meeting
                secretary.start_meeting(
                    topic="Test Meeting",
                    participants=["Agent1", "Agent2"],
                    meeting_type="discussion",
                )

                # Verify tracking was called
                assert mock_store.save_event.called
                call_args = mock_store.save_event.call_args[0][0]
                assert call_args.actor == "system"
                assert call_args.type == "system"
                assert call_args.payload["event_type"] == "meeting_started"
                assert call_args.payload["topic"] == "Test Meeting"
                assert call_args.payload["participants"] == ["Agent1", "Agent2"]

    def test_swarm_manager_session_tracking(self, temp_sessions_dir, mock_client):
        """Test that SwarmManager tracks session events."""
        # Set up session context
        set_current_session_id("test-session-123")

        # Mock the session store
        with patch("spds.session_tracking.get_default_session_store") as mock_get_store:
            mock_store = Mock()
            mock_store.save_event = Mock()
            mock_get_store.return_value = mock_store

            # Create SwarmManager
            with patch("spds.swarm_manager.SPDSAgent") as mock_spds_agent:
                mock_agent = Mock()
                mock_agent.name = "TestAgent"
                mock_agent.agent = Mock(id="agent-123")
                mock_spds_agent.return_value = mock_agent

                swarm_manager = SwarmManager(
                    client=mock_client,
                    agent_profiles=[
                        {
                            "name": "TestAgent",
                            "persona": "Test persona",
                            "expertise": ["testing"],
                        }
                    ],
                    enable_secretary=False,
                )

                # Test _start_meeting tracking
                swarm_manager._start_meeting("Test Topic")

                # Verify tracking was called
                assert mock_store.save_event.called
                call_args = mock_store.save_event.call_args[0][0]
                assert call_args.actor == "system"
                assert call_args.type == "system"
                assert call_args.payload["event_type"] == "meeting_started"
                assert call_args.payload["topic"] == "Test Topic"

    def test_user_message_tracking(self, temp_sessions_dir, mock_client):
        """Test that user messages are tracked."""
        # Set up session context
        set_current_session_id("test-session-123")

        # Mock the session store
        with patch("spds.session_tracking.get_default_session_store") as mock_get_store:
            mock_store = Mock()
            mock_store.save_event = Mock()
            mock_get_store.return_value = mock_store

            # Create SwarmManager
            with patch("spds.swarm_manager.SPDSAgent") as mock_spds_agent:
                mock_agent = Mock()
                mock_agent.name = "TestAgent"
                mock_agent.agent = Mock(id="agent-123")
                mock_spds_agent.return_value = mock_agent

                swarm_manager = SwarmManager(
                    client=mock_client,
                    agent_profiles=[
                        {
                            "name": "TestAgent",
                            "persona": "Test persona",
                            "expertise": ["testing"],
                        }
                    ],
                    enable_secretary=False,
                )

                # Simulate user input tracking
                from spds.session_tracking import track_message

                track_message(
                    actor="user",
                    content="Hello, this is a test message",
                    message_type="user",
                )

                # Verify tracking was called
                assert mock_store.save_event.called
                call_args = mock_store.save_event.call_args[0][0]
                assert call_args.actor == "user"
                assert call_args.type == "message"
                assert call_args.payload["content"] == "Hello, this is a test message"
                assert call_args.payload["message_type"] == "user"

    def test_no_session_context_no_tracking(self, temp_sessions_dir, mock_client):
        """Test that tracking is skipped when no session context is set."""
        # Ensure no session context
        from spds.session_context import clear_session_context

        clear_session_context()

        # Mock the session store
        with patch("spds.session_tracking.get_default_session_store") as mock_get_store:
            mock_store = Mock()
            mock_store.save_event = Mock()
            mock_get_store.return_value = mock_store

            # Try to track a message
            from spds.session_tracking import track_message

            track_message(
                actor="user", content="This should not be tracked", message_type="user"
            )

            # Verify tracking was NOT called
            assert not mock_store.save_event.called

    def test_secretary_action_item_tracking(self, temp_sessions_dir, mock_client):
        """Test that SecretaryAgent action item tracking works."""
        # Set up session context
        set_current_session_id("test-session-123")

        # Mock the session store
        with patch("spds.session_tracking.get_default_session_store") as mock_get_store:
            mock_store = Mock()
            mock_store.save_event = Mock()
            mock_get_store.return_value = mock_store

            # Mock the secretary agent
            with patch("spds.secretary_agent.letta_call") as mock_letta_call:
                mock_agent_state = Mock()
                mock_agent_state.id = "secretary-123"
                mock_agent_state.name = "Secretary"
                mock_letta_call.return_value = mock_agent_state

                secretary = SecretaryAgent(mock_client, mode="formal")

                # Add action item
                secretary.add_action_item(
                    description="Test action item",
                    assignee="TestUser",
                    due_date="2024-01-01",
                )

                # Verify tracking was called
                assert mock_store.save_event.called
                call_args = mock_store.save_event.call_args[0][0]
                assert (
                    call_args.actor == "secretary"
                )  # Secretary agent performs the action
                assert call_args.type == "action"
                assert call_args.payload["action_type"] == "add_action_item"
                assert call_args.payload["details"]["description"] == "Test action item"
                assert call_args.payload["details"]["assignee"] == "TestUser"
                assert call_args.payload["details"]["due_date"] == "2024-01-01"

    def test_session_context_helpers_with_ensure_session(self, temp_sessions_dir):
        """Test ensure_session creates new session when none exists."""
        # Clear session context
        from spds.session_context import clear_session_context

        clear_session_context()

        # Create a real session store
        sessions_dir = temp_sessions_dir
        store = JsonSessionStore(sessions_dir)

        # Ensure session
        session_id = ensure_session(store, title="Test Session")

        # Verify session was created
        assert session_id is not None
        assert len(session_id) == 36  # UUID4 string is 36 characters

        # Verify session exists in store
        sessions = store.list_sessions()
        assert len(sessions) == 1
        assert sessions[0].id == session_id
        assert sessions[0].title == "Test Session"

    def test_session_store_graceful_fallback_on_corruption(self, temp_sessions_dir):
        """Test that session store gracefully handles corrupted session.json."""
        # Create session store
        store = JsonSessionStore(temp_sessions_dir)

        # Create a session with events
        session_state = store.create(title="Corruption Test")
        session_id = session_state.meta.id

        # Add events
        for i in range(2):
            event = SessionEvent(
                event_id=f"event-{i}",
                session_id=session_id,
                ts=datetime.utcnow(),
                actor=f"agent-{i}",
                type="message",
                payload={"content": f"Message {i}", "message_type": "assistant"},
            )
            store.save_event(event)

        # Corrupt the session.json file
        session_file = store._get_session_file(session_id)
        session_file.write_text("invalid json{")

        # Load should succeed by rebuilding from events.jsonl
        loaded_state = store.load(session_id)

        assert loaded_state.meta.id == session_id
        assert len(loaded_state.events) == 3  # 1 session creation + 2 message events
        # Find the message events (skip the session creation event)
        message_events = [e for e in loaded_state.events if e.type == "message"]
        assert len(message_events) == 2
        assert message_events[0].payload["content"] == "Message 0"
        assert message_events[1].payload["content"] == "Message 1"
