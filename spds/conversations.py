# spds/conversations.py

import logging
from typing import Any, Dict, List, Optional

from letta_client import Letta

logger = logging.getLogger(__name__)


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
