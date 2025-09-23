# spds/session_store.py

import json
import logging
import os
import tempfile
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional
from uuid import uuid4

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class SessionMeta(BaseModel):
    """Metadata for a session."""
    id: str
    created_at: datetime
    last_updated: datetime
    title: Optional[str] = None
    tags: List[str] = Field(default_factory=list)


class SessionEvent(BaseModel):
    """An event in a session."""
    event_id: str
    session_id: str
    ts: datetime
    actor: str
    type: Literal["message", "tool_call", "decision", "action", "system"]
    payload: Dict[str, Any] = Field(default_factory=dict)

    model_config = {"extra": "allow"}


class SessionState(BaseModel):
    """Complete state of a session."""
    meta: SessionMeta
    events: List[SessionEvent] = Field(default_factory=list)
    extras: Optional[Dict[str, Any]] = None


class SessionStore:
    """Abstract interface for session storage."""
    
    def create(self, session_id: Optional[str] = None, title: Optional[str] = None, tags: Optional[List[str]] = None) -> SessionState:
        """Create a new session."""
        raise NotImplementedError
    
    def save_event(self, event: SessionEvent) -> None:
        """Save an event to the session."""
        raise NotImplementedError
    
    def load(self, session_id: str) -> SessionState:
        """Load a session by ID."""
        raise NotImplementedError
    
    def list_sessions(self) -> List[SessionMeta]:
        """List all session metadata."""
        raise NotImplementedError
    
    def touch(self, session_id: str) -> None:
        """Update the last_updated timestamp for a session."""
        raise NotImplementedError
    
    def delete(self, session_id: str) -> None:
        """Delete a session."""
        raise NotImplementedError


class JsonSessionStore(SessionStore):
    """JSON-based session store with atomic writes and file locking."""
    
    def __init__(self, sessions_dir: Path):
        self.sessions_dir = sessions_dir
        self.sessions_dir.mkdir(parents=True, exist_ok=True)
        # Use reentrant locks for per-session locking to avoid deadlocks when
        # a method (e.g., save_event) calls another method (e.g., load) that
        # also attempts to acquire the same session lock within the same thread.
        self._locks: Dict[str, threading.RLock] = {}
        self._global_lock = threading.Lock()
        # If no default store has been initialized yet, set this instance as the default.
        # This makes helpers that call get_default_session_store() work seamlessly in tests
        # that construct their own JsonSessionStore pointing at a temp directory.
        try:
            from .session_store import _default_session_store  # type: ignore
            # Only assign if not yet set to avoid clobbering an explicitly configured store
            if _default_session_store is None:
                # Assigning via globals to avoid circular import issues
                globals().setdefault('_default_session_store', self)
                globals()['_default_session_store'] = self
        except Exception:
            # Best-effort; safe to ignore if globals are not yet available
            pass
    
    def _get_session_lock(self, session_id: str) -> threading.RLock:
        """Get or create a lock for a specific session."""
        with self._global_lock:
            if session_id not in self._locks:
                self._locks[session_id] = threading.RLock()
            return self._locks[session_id]
    
    def _get_session_dir(self, session_id: str) -> Path:
        """Get the directory for a session."""
        return self.sessions_dir / session_id
    
    def _get_session_file(self, session_id: str) -> Path:
        """Get the session state file path."""
        return self._get_session_dir(session_id) / "session.json"
    
    def _get_events_file(self, session_id: str) -> Path:
        """Get the events file path."""
        return self._get_session_dir(session_id) / "events.jsonl"
    
    def _get_lock_file(self, session_id: str) -> Path:
        """Get the lock file path."""
        return self._get_session_dir(session_id) / ".lock"
    
    def _atomic_write(self, file_path: Path, content: str) -> None:
        """Write content to a file atomically using a temporary file."""
        temp_file = None
        try:
            # Create temporary file in same directory
            with tempfile.NamedTemporaryFile(
                mode='w', 
                dir=file_path.parent, 
                delete=False,
                suffix='.tmp'
            ) as f:
                temp_file = Path(f.name)
                f.write(content)
            
            # Atomic replace
            temp_file.replace(file_path)
            logger.debug(f"Atomically wrote {file_path}")
        except Exception as e:
            # Clean up temp file on error
            if temp_file and temp_file.exists():
                temp_file.unlink(missing_ok=True)
            raise e
    
    def create(self, session_id: Optional[str] = None, title: Optional[str] = None, tags: Optional[List[str]] = None) -> SessionState:
        """Create a new session."""
        if session_id is None:
            session_id = str(uuid4())
        
        session_dir = self._get_session_dir(session_id)
        session_dir.mkdir(parents=True, exist_ok=True)
        
        now = datetime.utcnow()
        meta = SessionMeta(
            id=session_id,
            created_at=now,
            last_updated=now,
            title=title,
            tags=tags or []
        )
        
        session_state = SessionState(meta=meta)
        
        # Save initial state
        lock = self._get_session_lock(session_id)
        with lock:
            self._save_session_state(session_state)
            # Create empty events file
            events_file = self._get_events_file(session_id)
            self._atomic_write(events_file, "")
            
            # Add system event for session creation to preserve metadata
            creation_event = SessionEvent(
                event_id=str(uuid4()),
                session_id=session_id,
                ts=now,
                actor="system",
                type="system",
                payload={
                    "event_type": "session_created",
                    "title": title,
                    "tags": tags or []
                }
            )
            # Directly append to events file to avoid recursion
            event_json = creation_event.model_dump_json() + "\n"
            with events_file.open('a') as f:
                f.write(event_json)
            
            # Also add event to the session state in memory
            session_state.events.append(creation_event)
            session_state.meta.last_updated = creation_event.ts
            self._save_session_state(session_state)
        
        logger.info(f"Created session {session_id}")
        return session_state
    
    def _save_session_state(self, session_state: SessionState) -> None:
        """Save the complete session state."""
        session_file = self._get_session_file(session_state.meta.id)
        content = session_state.model_dump_json(indent=2)
        self._atomic_write(session_file, content)
    
    def save_event(self, event: SessionEvent) -> None:
        """Save an event to the session."""
        session_id = event.session_id
        lock = self._get_session_lock(session_id)
        
        with lock:
            # Ensure session directory exists
            session_dir = self._get_session_dir(session_id)
            session_dir.mkdir(parents=True, exist_ok=True)

            # Append to events file
            events_file = self._get_events_file(session_id)
            event_json = event.model_dump_json() + "\n"
            
            # Append to events.jsonl
            with events_file.open('a') as f:
                f.write(event_json)
            
            # Update session.json with new event
            try:
                # Try to load existing session.json directly without fallback to rebuild
                session_file = self._get_session_file(session_id)
                if session_file.exists():
                    try:
                        with session_file.open('r') as f:
                            content = f.read()
                            if content.strip():
                                session_state = SessionState.model_validate_json(content)
                                session_state.events.append(event)
                                session_state.meta.last_updated = event.ts
                                self._save_session_state(session_state)
                            else:
                                raise ValueError("Empty session file")
                    except Exception as e:
                        logger.debug(f"Cannot load session.json directly: {e}, skipping update")
                else:
                    logger.debug(f"Session file {session_file} does not exist, creating minimal session.json")
                    # Create minimal session from first event
                    meta = SessionMeta(
                        id=session_id,
                        created_at=event.ts,
                        last_updated=event.ts,
                    )
                    session_state = SessionState(meta=meta, events=[event])
                    self._save_session_state(session_state)
            except Exception as e:
                logger.warning(f"Failed to update session.json for {session_id}, but event saved to events.jsonl: {e}")
            
            logger.debug(f"Saved event {event.event_id} to session {session_id}")
    
    def load(self, session_id: str) -> SessionState:
        """Load a session by ID."""
        session_file = self._get_session_file(session_id)
        events_file = self._get_events_file(session_id)
        
        lock = self._get_session_lock(session_id)
        with lock:
            # Try to load from session.json first
            if session_file.exists():
                try:
                    with session_file.open('r') as f:
                        content = f.read()
                        if content.strip():
                            session_state = SessionState.model_validate_json(content)
                            logger.debug(f"Loaded session {session_id} from session.json")
                            return session_state
                except Exception as e:
                    logger.warning(f"Failed to load session.json for {session_id}: {e}")
            
            # Fallback: rebuild from events.jsonl
            if events_file.exists():
                try:
                    events = []
                    with events_file.open('r') as f:
                        for line in f:
                            line = line.strip()
                            if line:
                                try:
                                    event = SessionEvent.model_validate_json(line)
                                    events.append(event)
                                except Exception as e:
                                    logger.warning(f"Skipping malformed event line: {e}")
                    
                    if events:
                        # Create session meta from first event
                        first_event = events[0]
                        # Try to restore title from system events
                        title = None
                        tags = []
                        for event in events:
                            if event.type == "system" and event.payload.get("event_type") == "session_created":
                                title = event.payload.get("title")
                                tags = event.payload.get("tags", [])
                                break
                        
                        meta = SessionMeta(
                            id=session_id,
                            created_at=first_event.ts,
                            last_updated=events[-1].ts if events else first_event.ts,
                            title=title,
                            tags=tags
                        )
                        
                        session_state = SessionState(meta=meta, events=events)
                        # Try to save the rebuilt state
                        try:
                            self._save_session_state(session_state)
                        except Exception as e:
                            logger.warning(f"Failed to save rebuilt session state: {e}")
                        
                        logger.info(f"Rebuilt session {session_id} from events.jsonl")
                        return session_state
                except Exception as e:
                    logger.error(f"Failed to rebuild session from events.jsonl for {session_id}: {e}")
            
            raise ValueError(f"Session {session_id} not found")
    
    def list_sessions(self) -> List[SessionMeta]:
        """List all session metadata."""
        sessions = []
        
        if not self.sessions_dir.exists():
            return sessions
        
        for session_dir in self.sessions_dir.iterdir():
            if session_dir.is_dir():
                session_id = session_dir.name
                try:
                    session_state = self.load(session_id)
                    sessions.append(session_state.meta)
                except Exception as e:
                    logger.warning(f"Failed to load session {session_id}: {e}")
        
        return sorted(sessions, key=lambda x: x.created_at, reverse=True)
    
    def touch(self, session_id: str) -> None:
        """Update the last_updated timestamp for a session."""
        try:
            session_state = self.load(session_id)
            session_state.meta.last_updated = datetime.utcnow()
            self._save_session_state(session_state)
            logger.debug(f"Touched session {session_id}")
        except Exception as e:
            logger.warning(f"Failed to touch session {session_id}: {e}")
    
    def delete(self, session_id: str) -> None:
        """Delete a session."""
        session_dir = self._get_session_dir(session_id)
        
        lock = self._get_session_lock(session_id)
        with lock:
            if session_dir.exists():
                import shutil
                shutil.rmtree(session_dir)
                logger.info(f"Deleted session {session_id}")
            else:
                logger.warning(f"Session {session_id} not found for deletion")


# Singleton instance
_default_session_store: Optional[JsonSessionStore] = None
_default_store_lock = threading.Lock()


def get_default_session_store() -> JsonSessionStore:
    """Get the default session store instance."""
    global _default_session_store
    
    if _default_session_store is None:
        with _default_store_lock:
            if _default_session_store is None:
                from .config import get_sessions_dir
                sessions_dir = get_sessions_dir()
                _default_session_store = JsonSessionStore(sessions_dir)
    
    return _default_session_store


def set_default_session_store(store: Optional[JsonSessionStore]) -> None:
    """Override the default session store (useful for tests)."""
    global _default_session_store
    with _default_store_lock:
        _default_session_store = store


def reset_default_session_store() -> None:
    """Reset the default session store to None."""
    global _default_session_store
    with _default_store_lock:
        _default_session_store = None