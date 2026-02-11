# spds/session_tracking.py
#
# Logging stubs that preserve the original function signatures.
# Session persistence is now handled server-side by the Letta
# Conversations API (see spds/conversations.py).

import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class SessionTracker:
    """Logging-only session tracker (stub).

    All ``track_*`` calls are forwarded to ``logger.debug``.  The class
    exists purely to keep callers that instantiate ``SessionTracker``
    working without code changes.
    """

    def __init__(self, session_store=None):
        pass  # session_store no longer used

    def track_message(
        self, actor: str, content: str, message_type: str = "assistant"
    ) -> None:
        logger.debug("track_message actor=%s type=%s", actor, message_type)

    def track_tool_call(
        self,
        actor: str,
        tool_name: str,
        arguments: Dict[str, Any],
        result: Optional[Any] = None,
    ) -> None:
        logger.debug("track_tool_call actor=%s tool=%s", actor, tool_name)

    def track_decision(
        self, actor: str, decision_type: str, details: Dict[str, Any]
    ) -> None:
        logger.debug("track_decision actor=%s type=%s", actor, decision_type)

    def track_action(
        self, actor: str, action_type: str, details: Dict[str, Any]
    ) -> None:
        logger.debug("track_action actor=%s type=%s", actor, action_type)

    def track_system_event(self, event_type: str, details: Dict[str, Any]) -> None:
        logger.debug("track_system_event type=%s", event_type)


# Global tracker instance
_default_tracker: Optional[SessionTracker] = None


def get_default_session_tracker() -> SessionTracker:
    global _default_tracker
    if _default_tracker is None:
        _default_tracker = SessionTracker()
    return _default_tracker


def set_default_session_tracker(tracker: Optional[SessionTracker]) -> None:
    global _default_tracker
    _default_tracker = tracker


def reset_default_session_tracker() -> None:
    global _default_tracker
    _default_tracker = None


# ── Convenience functions (unchanged signatures) ──────────────────────

def track_message(actor: str, content: str, message_type: str = "assistant") -> None:
    get_default_session_tracker().track_message(actor, content, message_type)


def track_tool_call(
    actor: str, tool_name: str, arguments: Dict[str, Any], result: Optional[Any] = None
) -> None:
    get_default_session_tracker().track_tool_call(actor, tool_name, arguments, result)


def track_decision(actor: str, decision_type: str, details: Dict[str, Any]) -> None:
    get_default_session_tracker().track_decision(actor, decision_type, details)


def track_action(actor: str, action_type: str, details: Dict[str, Any]) -> None:
    get_default_session_tracker().track_action(actor, action_type, details)


def track_system_event(event_type: str, details: Dict[str, Any]) -> None:
    get_default_session_tracker().track_system_event(event_type, details)
