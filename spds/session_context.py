# spds/session_context.py
#
# Tracks the active conversation ID via a ContextVar.
# Previously tracked a local JSON session; now tracks a Letta
# Conversations API conversation_id.

import logging
from contextvars import ContextVar
from typing import Optional
from uuid import uuid4

logger = logging.getLogger(__name__)

# Context variable for active conversation ID
current_conversation_id: ContextVar[Optional[str]] = ContextVar(
    "current_conversation_id", default=None
)

# Backward-compatible alias
current_session_id = current_conversation_id


def set_current_session_id(session_id: str) -> None:
    """Set the active conversation/session ID."""
    current_conversation_id.set(session_id)
    logger.debug("Set current conversation ID to %s", session_id)


def get_current_session_id() -> Optional[str]:
    """Get the active conversation/session ID."""
    return current_conversation_id.get()


def clear_session_context() -> None:
    """Clear the active conversation context."""
    current_conversation_id.set(None)
    logger.debug("Cleared conversation context")


def new_session_id() -> str:
    """Generate a new session ID (UUID4)."""
    return str(uuid4())


def ensure_session(session_store=None, title: Optional[str] = None) -> str:
    """Ensure a conversation ID is set. Creates one if needed.

    The ``session_store`` parameter is accepted but ignored (kept for
    backward compatibility). A new UUID is generated if no conversation
    is active — callers should replace this with a real
    ``ConversationManager.create_session()`` call.
    """
    current_id = get_current_session_id()
    if current_id is not None:
        return current_id

    session_id = new_session_id()
    set_current_session_id(session_id)
    logger.info("Created new conversation context %s", session_id)
    return session_id
