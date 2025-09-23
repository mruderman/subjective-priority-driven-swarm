# tests/unit/test_session_store.py

import json
import tempfile
from pathlib import Path
from datetime import datetime

import pytest
from spds.session_store import JsonSessionStore, SessionMeta, SessionEvent, SessionState


class TestJsonSessionStore:
    """Test cases for JsonSessionStore."""
    
    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for testing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)
    
    @pytest.fixture
    def session_store(self, temp_dir):
        """Create a JsonSessionStore instance for testing."""
        sessions_dir = temp_dir / "sessions"
        return JsonSessionStore(sessions_dir)
    
    def test_create_session(self, session_store):
        """Test creating a new session."""
        session_state = session_store.create(title="Test Session", tags=["test", "demo"])
        
        assert session_state.meta.id is not None
        assert session_state.meta.title == "Test Session"
        assert session_state.meta.tags == ["test", "demo"]
        assert session_state.meta.created_at is not None
        assert session_state.meta.last_updated is not None
        # Should have one session_created event
        assert len(session_state.events) == 1
        assert session_state.events[0].type == "system"
        assert session_state.events[0].actor == "system"
        assert session_state.events[0].payload["event_type"] == "session_created"
        assert session_state.events[0].payload["title"] == "Test Session"
        assert session_state.events[0].payload["tags"] == ["test", "demo"]
        assert session_state.extras is None
    
    def test_create_session_with_custom_id(self, session_store):
        """Test creating a session with a custom ID."""
        custom_id = "custom-session-123"
        session_state = session_store.create(session_id=custom_id, title="Custom Session")
        
        assert session_state.meta.id == custom_id
        assert session_state.meta.title == "Custom Session"
    
    def test_save_event(self, session_store):
        """Test saving events to a session."""
        # Create a session first
        session_state = session_store.create(title="Event Test")
        session_id = session_state.meta.id
        
        # Create and save an event
        event = SessionEvent(
            event_id="test-event-1",
            session_id=session_id,
            ts=datetime.utcnow(),
            actor="test_agent",
            type="message",
            payload={"content": "Hello world", "message_type": "assistant"}
        )
        
        session_store.save_event(event)
        
        # Reload the session and verify the event was saved
        loaded_state = session_store.load(session_id)
        assert len(loaded_state.events) == 2  # session_created + the saved event
        # First event should be session_created
        assert loaded_state.events[0].type == "system"
        assert loaded_state.events[0].payload["event_type"] == "session_created"
        # Second event should be our saved event
        assert loaded_state.events[1].event_id == "test-event-1"
        assert loaded_state.events[1].actor == "test_agent"
        assert loaded_state.events[1].type == "message"
        assert loaded_state.events[1].payload["content"] == "Hello world"
    
    def test_load_session(self, session_store):
        """Test loading a session by ID."""
        # Create a session with events
        session_state = session_store.create(title="Load Test")
        session_id = session_state.meta.id
        
        # Add some events
        for i in range(3):
            event = SessionEvent(
                event_id=f"event-{i}",
                session_id=session_id,
                ts=datetime.utcnow(),
                actor=f"agent-{i}",
                type="message",
                payload={"content": f"Message {i}", "message_type": "assistant"}
            )
            session_store.save_event(event)
        
        # Load the session
        loaded_state = session_store.load(session_id)
        
        assert loaded_state.meta.id == session_id
        assert loaded_state.meta.title == "Load Test"
        assert len(loaded_state.events) == 4  # 1 session_created + 3 manual events
        # First event should be session_created
        assert loaded_state.events[0].type == "system"
        assert loaded_state.events[0].payload["event_type"] == "session_created"
        # Next events should be our manually added events
        assert loaded_state.events[1].payload["content"] == "Message 0"
    
    def test_list_sessions(self, session_store):
        """Test listing all sessions."""
        # Create multiple sessions
        session1 = session_store.create(title="Session 1", tags=["tag1"])
        session2 = session_store.create(title="Session 2", tags=["tag2"])
        session3 = session_store.create(title="Session 3", tags=["tag3"])
        
        # List sessions
        sessions = session_store.list_sessions()
        
        assert len(sessions) == 3
        session_ids = {s.id for s in sessions}
        expected_ids = {session1.meta.id, session2.meta.id, session3.meta.id}
        assert session_ids == expected_ids
        
        # Verify sessions are sorted by creation time (newest first)
        assert sessions[0].created_at >= sessions[1].created_at
        assert sessions[1].created_at >= sessions[2].created_at
    
    def test_delete_session(self, session_store):
        """Test deleting a session."""
        # Create a session
        session_state = session_store.create(title="Delete Test")
        session_id = session_state.meta.id
        
        # Verify session exists
        assert len(session_store.list_sessions()) == 1
        
        # Delete the session
        session_store.delete(session_id)
        
        # Verify session is deleted
        assert len(session_store.list_sessions()) == 0
        
        # Verify session files are deleted
        session_dir = session_store._get_session_dir(session_id)
        assert not session_dir.exists()
    
    def test_touch_session(self, session_store):
        """Test updating session timestamp."""
        # Create a session
        session_state = session_store.create(title="Touch Test")
        session_id = session_state.meta.id
        
        # Get original timestamp
        original_time = session_state.meta.last_updated
        
        # Wait a bit and touch the session
        import time
        time.sleep(0.1)
        session_store.touch(session_id)
        
        # Load and verify timestamp was updated
        loaded_state = session_store.load(session_id)
        assert loaded_state.meta.last_updated > original_time
    
    def test_atomic_writes(self, session_store):
        """Test that session recovery works when session.json is corrupted."""
        # Create a session
        session_state = session_store.create(title="Atomic Test")
        session_id = session_state.meta.id
        
        # Manually corrupt the session.json file
        session_file = session_store._get_session_file(session_id)
        session_file.write_text("invalid json{")
        
        # The load should succeed by rebuilding from events.jsonl (session_created event)
        recovered_state = session_store.load(session_id)
        assert recovered_state.meta.id == session_id
        assert recovered_state.meta.title == "Atomic Test"
        assert len(recovered_state.events) == 1  # session_created event
        assert recovered_state.events[0].payload["event_type"] == "session_created"
    
    def test_rebuild_from_events_jsonl(self, session_store):
        """Test that session can be rebuilt from events.jsonl if session.json is corrupted."""
        # Create a session
        session_state = session_store.create(title="Rebuild Test")
        session_id = session_state.meta.id
        
        # Add events
        for i in range(2):
            event = SessionEvent(
                event_id=f"event-{i}",
                session_id=session_id,
                ts=datetime.utcnow(),
                actor=f"agent-{i}",
                type="message",
                payload={"content": f"Message {i}", "message_type": "assistant"}
            )
            session_store.save_event(event)
        
        # Corrupt the session.json file
        session_file = session_store._get_session_file(session_id)
        session_file.write_text("invalid json{")
        
        # Load should succeed by rebuilding from events.jsonl
        loaded_state = session_store.load(session_id)
        
        assert loaded_state.meta.id == session_id
        assert len(loaded_state.events) == 3  # 1 session_created + 2 manual events
        # First event should be session_created
        assert loaded_state.events[0].type == "system"
        assert loaded_state.events[0].payload["event_type"] == "session_created"
        # Next events should be our manually added events
        assert loaded_state.events[1].payload["content"] == "Message 0"
        assert loaded_state.events[2].payload["content"] == "Message 1"
    
    def test_concurrent_access(self, session_store):
        """Test thread safety with concurrent access."""
        import threading
        
        # Create a session
        session_state = session_store.create(title="Concurrent Test")
        session_id = session_state.meta.id
        
        # Create multiple threads that save events
        threads = []
        event_count = 10
        
        def save_events(start_idx):
            for i in range(start_idx, start_idx + event_count):
                event = SessionEvent(
                    event_id=f"concurrent-event-{i}",
                    session_id=session_id,
                    ts=datetime.utcnow(),
                    actor=f"agent-{i}",
                    type="message",
                    payload={"content": f"Concurrent message {i}", "message_type": "assistant"}
                )
                session_store.save_event(event)
        
        # Start multiple threads
        for i in range(3):
            thread = threading.Thread(target=save_events, args=(i * event_count,))
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # Verify all events were saved
        loaded_state = session_store.load(session_id)
        assert len(loaded_state.events) == 1 + (3 * event_count)  # 1 session_created + 30 manual events


class TestSessionModels:
    """Test cases for Pydantic models."""
    
    def test_session_meta_creation(self):
        """Test SessionMeta model."""
        meta = SessionMeta(
            id="test-123",
            created_at=datetime.utcnow(),
            last_updated=datetime.utcnow(),
            title="Test Session",
            tags=["test", "demo"]
        )
        
        assert meta.id == "test-123"
        assert meta.title == "Test Session"
        assert meta.tags == ["test", "demo"]
    
    def test_session_event_creation(self):
        """Test SessionEvent model."""
        event = SessionEvent(
            event_id="event-123",
            session_id="session-123",
            ts=datetime.utcnow(),
            actor="test_agent",
            type="message",
            payload={"content": "Hello", "message_type": "assistant"}
        )
        
        assert event.event_id == "event-123"
        assert event.session_id == "session-123"
        assert event.actor == "test_agent"
        assert event.type == "message"
        assert event.payload["content"] == "Hello"
    
    def test_session_state_creation(self):
        """Test SessionState model."""
        meta = SessionMeta(
            id="session-123",
            created_at=datetime.utcnow(),
            last_updated=datetime.utcnow(),
            title="Test Session"
        )
        
        events = [
            SessionEvent(
                event_id="event-1",
                session_id="session-123",
                ts=datetime.utcnow(),
                actor="agent-1",
                type="message",
                payload={"content": "Message 1"}
            )
        ]
        
        state = SessionState(
            meta=meta,
            events=events,
            extras={"test": "extra data"}
        )
        
        assert state.meta.id == "session-123"
        assert len(state.events) == 1
        assert state.extras["test"] == "extra data"