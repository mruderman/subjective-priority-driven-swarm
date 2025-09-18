# spds/session_tracking.py

import logging
import uuid
from datetime import datetime
from typing import Any, Dict, Optional
from uuid import uuid4

from .session_context import get_current_session_id
from .session_store import SessionEvent, SessionStore, get_default_session_store

logger = logging.getLogger(__name__)


class SessionTracker:
    """Tracks session events and persists them to storage."""
    
    def __init__(self, session_store: Optional[SessionStore] = None):
        self.session_store = session_store or get_default_session_store()
    
    def track_message(self, actor: str, content: str, message_type: str = "assistant") -> None:
        """Track a message event."""
        session_id = get_current_session_id()
        if not session_id:
            logger.debug("No active session, skipping message tracking")
            return
        
        event = SessionEvent(
            event_id=self._generate_event_id(),
            session_id=session_id,
            ts=datetime.utcnow(),
            actor=actor,
            type="message",
            payload={
                "content": content,
                "message_type": message_type
            }
        )
        
        self._save_event(event)
    
    def track_tool_call(self, actor: str, tool_name: str, arguments: Dict[str, Any], result: Optional[Any] = None) -> None:
        """Track a tool call event."""
        session_id = get_current_session_id()
        if not session_id:
            logger.debug("No active session, skipping tool call tracking")
            return
        
        event = SessionEvent(
            event_id=self._generate_event_id(),
            session_id=session_id,
            ts=datetime.utcnow(),
            actor=actor,
            type="tool_call",
            payload={
                "tool_name": tool_name,
                "arguments": arguments,
                "result": result
            }
        )
        
        self._save_event(event)
    
    def track_decision(self, actor: str, decision_type: str, details: Dict[str, Any]) -> None:
        """Track a decision event."""
        session_id = get_current_session_id()
        if not session_id:
            logger.debug("No active session, skipping decision tracking")
            return
        
        event = SessionEvent(
            event_id=self._generate_event_id(),
            session_id=session_id,
            ts=datetime.utcnow(),
            actor=actor,
            type="decision",
            payload={
                "decision_type": decision_type,
                "details": details
            }
        )
        
        self._save_event(event)
    
    def track_action(self, actor: str, action_type: str, details: Dict[str, Any]) -> None:
        """Track an action event."""
        session_id = get_current_session_id()
        if not session_id:
            logger.debug("No active session, skipping action tracking")
            return
        
        event = SessionEvent(
            event_id=self._generate_event_id(),
            session_id=session_id,
            ts=datetime.utcnow(),
            actor=actor,
            type="action",
            payload={
                "action_type": action_type,
                "details": details
            }
        )
        
        self._save_event(event)
    
    def track_system_event(self, event_type: str, details: Dict[str, Any]) -> None:
        """Track a system event."""
        session_id = get_current_session_id()
        if not session_id:
            logger.debug("No active session, skipping system event tracking")
            return
        
        event = SessionEvent(
            event_id=self._generate_event_id(),
            session_id=session_id,
            ts=datetime.utcnow(),
            actor="system",
            type="system",
            payload={
                "event_type": event_type,
                "details": details
            }
        )
        
        self._save_event(event)
    
    def _generate_event_id(self) -> str:
        """Generate a unique event ID."""
        import uuid
        return uuid4().hex
    
    def _save_event(self, event: SessionEvent) -> None:
        """Save an event to the session store."""
        try:
            self.session_store.save_event(event)
        except Exception as e:
            logger.warning(f"Failed to save event to session: {e}")


# Global tracker instance
_default_tracker: Optional[SessionTracker] = None


def get_default_session_tracker() -> SessionTracker:
    """Get the default session tracker instance."""
    global _default_tracker
    
    if _default_tracker is None:
        _default_tracker = SessionTracker()
    
    return _default_tracker


# Convenience functions for tracking
def track_message(actor: str, content: str, message_type: str = "assistant") -> None:
    """Track a message event using the default tracker."""
    tracker = get_default_session_tracker()
    tracker.track_message(actor, content, message_type)


def track_tool_call(actor: str, tool_name: str, arguments: Dict[str, Any], result: Optional[Any] = None) -> None:
    """Track a tool call event using the default tracker."""
    tracker = get_default_session_tracker()
    tracker.track_tool_call(actor, tool_name, arguments, result)


def track_decision(actor: str, decision_type: str, details: Dict[str, Any]) -> None:
    """Track a decision event using the default tracker."""
    tracker = get_default_session_tracker()
    tracker.track_decision(actor, decision_type, details)


def track_action(actor: str, action_type: str, details: Dict[str, Any]) -> None:
    """Track an action event using the default tracker."""
    tracker = get_default_session_tracker()
    tracker.track_action(actor, action_type, details)


def track_system_event(event_type: str, details: Dict[str, Any]) -> None:
    """Track a system event using the default tracker."""
    tracker = get_default_session_tracker()
    tracker.track_system_event(event_type, details)