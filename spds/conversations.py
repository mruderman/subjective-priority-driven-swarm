# spds/conversations.py

import logging
from types import SimpleNamespace
from typing import Any, Dict, List, Optional

from letta_client import Letta

logger = logging.getLogger(__name__)

# Message types to skip when consuming conversation streams.
# These are streaming-only control types that don't carry agent content.
_STREAM_SKIP_TYPES = frozenset({
    "ping",
    "usage_statistics",
    "stop_reason",
    "error_message",
})


class ConversationManager:
    """Wraps the Letta Conversations API for session management.

    Replaces the local JSON-based SessionStore with server-side persistence
    via Letta's Conversations API.
    """

    def __init__(self, client: Letta):
        self.client = client

    def create_session(
        self, agent_id: str, summary: str = ""
    ) -> str:
        """Create a new conversation (session) for an agent.

        Args:
            agent_id: The Letta agent ID to create the conversation for.
            summary: Optional summary/title for the conversation.

        Returns:
            The conversation ID.
        """
        conv = self.client.conversations.create(
            agent_id=agent_id,
            summary=summary or None,
        )
        logger.info(f"Created conversation {conv.id} for agent {agent_id}")
        return conv.id

    def send_message(
        self, conversation_id: str, content: str
    ) -> Any:
        """Send a message within a conversation.

        Args:
            conversation_id: The conversation ID.
            content: The message text to send.

        Returns:
            The streaming response from the Letta API.
        """
        response = self.client.conversations.messages.create(
            conversation_id=conversation_id,
            messages=[{"role": "user", "content": content}],
        )
        return response

    def list_messages(
        self,
        conversation_id: str,
        limit: Optional[int] = 100,
        order: str = "asc",
    ) -> List:
        """List messages in a conversation.

        Args:
            conversation_id: The conversation ID.
            limit: Max number of messages to return.
            order: Sort order ('asc' or 'desc').

        Returns:
            List of messages.
        """
        page = self.client.conversations.messages.list(
            conversation_id=conversation_id,
            limit=limit,
            order=order,
        )
        return list(page)

    def list_sessions(self, agent_id: str, limit: int = 50) -> List:
        """List conversations (sessions) for an agent.

        Args:
            agent_id: The Letta agent ID.
            limit: Max number of conversations to return.

        Returns:
            List of Conversation objects.
        """
        result = self.client.conversations.list(
            agent_id=agent_id,
            limit=limit,
        )
        # ConversationListResponse has a .conversations attribute
        if hasattr(result, "conversations"):
            return result.conversations
        # Fallback if the API returns a list-like object
        return list(result)

    def get_session(self, conversation_id: str) -> Any:
        """Retrieve a single conversation by ID.

        Args:
            conversation_id: The conversation ID.

        Returns:
            The Conversation object.
        """
        return self.client.conversations.retrieve(conversation_id)

    def update_summary(self, conversation_id: str, summary: str) -> Any:
        """Update the summary of a conversation.

        Args:
            conversation_id: The conversation ID.
            summary: New summary text.

        Returns:
            The updated Conversation object.
        """
        return self.client.conversations.update(
            conversation_id=conversation_id,
            summary=summary,
        )

    def get_session_summary(self, conversation_id: str) -> Dict:
        """Get a summary dict for a conversation.

        Args:
            conversation_id: The conversation ID.

        Returns:
            Dict with id, agent_id, summary, created_at, updated_at.
        """
        conv = self.get_session(conversation_id)
        return {
            "id": conv.id,
            "agent_id": conv.agent_id,
            "summary": conv.summary,
            "created_at": conv.created_at.isoformat() if conv.created_at else None,
            "updated_at": conv.updated_at.isoformat() if conv.updated_at else None,
        }

    # ------------------------------------------------------------------
    # Phase 2: Conversations-routed messaging
    # ------------------------------------------------------------------

    def send_and_collect(
        self, conversation_id: str, messages: List[Dict]
    ) -> Any:
        """Send messages to a conversation, consume the stream, return a response-like object.

        The Letta SDK's ``conversations.messages.create`` always returns a
        streaming iterator.  This helper consumes the stream, filters out
        control-only chunk types (ping, usage_statistics, etc.), and wraps
        the collected content messages in a ``SimpleNamespace(messages=...)``
        so callers can treat it identically to ``agents.messages.create``
        responses.

        Args:
            conversation_id: The conversation to send to.
            messages: List of message dicts (``{"role": ..., "content": ...}``).

        Returns:
            A ``SimpleNamespace`` with a ``.messages`` list of content chunks.
        """
        stream = self.client.conversations.messages.create(
            conversation_id=conversation_id,
            messages=messages,
        )
        collected = []
        for chunk in stream:
            if getattr(chunk, "message_type", None) in _STREAM_SKIP_TYPES:
                continue
            collected.append(chunk)
        return SimpleNamespace(messages=collected)

    def create_agent_conversation(
        self,
        agent_id: str,
        session_id: str,
        agent_name: str = "",
        topic: str = "",
    ) -> str:
        """Create a conversation tagged with SPDS session metadata.

        The summary is encoded as ``spds:<session_id>|<agent_name>|<topic>``
        so that ``find_sessions_by_spds_id`` can discover all conversations
        belonging to a particular SPDS session.

        Args:
            agent_id: The Letta agent ID.
            session_id: The SPDS session UUID.
            agent_name: Human-readable agent name (for display).
            topic: Meeting topic (for display).

        Returns:
            The conversation ID.
        """
        summary = f"spds:{session_id}|{agent_name}|{topic}"
        return self.create_session(agent_id=agent_id, summary=summary)

    def find_sessions_by_spds_id(
        self, agent_id: str, session_id: str
    ) -> List:
        """Find all conversations for an agent that belong to a given SPDS session.

        Filters the agent's conversations by summaries prefixed with
        ``spds:<session_id>``.

        Args:
            agent_id: The Letta agent ID.
            session_id: The SPDS session UUID to match.

        Returns:
            List of matching Conversation objects.
        """
        prefix = f"spds:{session_id}"
        all_convs = self.list_sessions(agent_id)
        return [
            c for c in all_convs
            if getattr(c, "summary", None) and c.summary.startswith(prefix)
        ]

    @staticmethod
    def parse_spds_summary(summary: str) -> Optional[Dict[str, str]]:
        """Parse an SPDS-encoded conversation summary.

        Args:
            summary: The raw summary string.

        Returns:
            Dict with ``session_id``, ``agent_name``, ``topic`` keys,
            or None if the summary is not SPDS-encoded.
        """
        if not summary or not summary.startswith("spds:"):
            return None
        payload = summary[5:]  # strip "spds:" prefix
        parts = payload.split("|", 2)
        return {
            "session_id": parts[0] if len(parts) > 0 else "",
            "agent_name": parts[1] if len(parts) > 1 else "",
            "topic": parts[2] if len(parts) > 2 else "",
        }
