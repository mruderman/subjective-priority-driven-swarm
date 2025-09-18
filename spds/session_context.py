# spds/session_context.py

import logging
from contextvars import ContextVar
from typing import Optional
from uuid import uuid4

from .session_store import SessionStore, SessionState

logger = logging.getLogger(__name__)

# Context variable for current session ID
current_session_id: ContextVar[Optional[str]] = ContextVar("current_session_id", default=None)


def set_current_session_id(session_id: str) -> None:
    """
    Set the current session ID in the context.
    
    Args:
        session_id: The session ID to set
    """
    current_session_id.set(session_id)
    logger.debug(f"Set current session ID to {session_id}")


def get_current_session_id() -> Optional[str]:
    """
    Get the current session ID from the context.
    
    Returns:
        The current session ID, or None if not set
    """
    return current_session_id.get()


def ensure_session(session_store: SessionStore, title: Optional[str] = None) -> str:
    """
    Ensure a session is active. If none is set, creates a new session.
    
    Args:
        session_store: The session store to use
        title: Optional title for the new session
        
    Returns:
        The session ID (either existing or newly created)
    """
    current_id = get_current_session_id()
    if current_id is not None:
        return current_id
    
    # Create new session
    session_state = session_store.create(title=title)
    session_id = session_state.meta.id
    set_current_session_id(session_id)
    logger.info(f"Created new session {session_id}")
    return session_id


def new_session_id() -> str:
    """
    Generate a new session ID.
    
    Returns:
        A new UUID4-based session ID
    """
    return uuid4().hex


def clear_session_context() -> None:
    """
    Clear the current session context.
    """
    current_session_id.set(None)
    logger.debug("Cleared session context")