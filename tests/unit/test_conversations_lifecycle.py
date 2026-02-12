"""Integration test for the full Conversations API lifecycle.

Exercises: SwarmManager init -> _start_meeting (creates conversations) ->
agent speak (routes through conversation) -> _end_meeting (finalizes) ->
verify all interactions.  All Letta client calls are mocked.
"""

from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_stream_response(*messages):
    """Create an iterable that simulates a Conversations API stream.

    Each positional arg is a message-like SimpleNamespace.  The returned
    iterator also yields control chunks (ping, usage_statistics) that
    ``send_and_collect`` should filter out.
    """
    control_chunks = [
        SimpleNamespace(message_type="ping"),
        SimpleNamespace(message_type="usage_statistics", data={}),
    ]
    for msg in messages:
        yield from control_chunks[:1]  # one ping before
        yield msg
    yield from control_chunks[1:]  # trailing usage_statistics


def _assistant_message(text="Hello"):
    """Create a mock assistant_message stream chunk."""
    return SimpleNamespace(
        message_type="assistant_message",
        content=text,
    )


def _tool_call_message(name="send_message", arguments='{"message": "Hi"}'):
    """Create a mock tool_call_message stream chunk."""
    return SimpleNamespace(
        message_type="tool_call_message",
        tool_call=SimpleNamespace(name=name, arguments=arguments),
    )


# ---------------------------------------------------------------------------
# Full lifecycle test
# ---------------------------------------------------------------------------

class TestConversationsLifecycle:
    """End-to-end mocked test: init -> start -> speak -> end."""

    def _build_manager(self, mock_client, monkeypatch):
        """Create a SwarmManager with mocked-out Letta calls.

        Returns (mgr, mock_cm_instance) so tests can inspect the
        ConversationManager mock.
        """
        from spds.swarm_manager import SwarmManager

        # Disable MCP during init
        monkeypatch.setenv("SPDS_MCP_ENABLED", "false")

        # --- Mock agents.create / agents.list ---
        agent_state = SimpleNamespace(
            id="ag-1",
            name="Alice",
            system="You are Alice. Your persona is: A test agent. Your expertise is in: testing.",
            agent_type="react_agent",
            llm_config=SimpleNamespace(
                model="openai/gpt-4", model_endpoint_type="openai", context_window=128000
            ),
            embedding_config=SimpleNamespace(
                embedding_endpoint_type="openai",
                embedding_model="openai/text-embedding-ada-002",
                embedding_dim=1536,
            ),
            memory=SimpleNamespace(blocks=[]),
            blocks=[],
            tools=["perform_subjective_assessment"],
            sources=[],
            tags=[],
            model="openai/gpt-4",
            embedding="openai/text-embedding-ada-002",
        )
        mock_client.agents.list.return_value = []
        mock_client.agents.create.return_value = agent_state
        mock_client.agents.update = Mock()

        # --- Mock tools ---
        mock_client.tools.list.return_value = [
            SimpleNamespace(id="tool-1", name="perform_subjective_assessment"),
        ]

        # --- Mock blocks (shared memory) ---
        mock_client.blocks = Mock()
        mock_client.blocks.create = Mock(return_value=SimpleNamespace(id="block-1"))
        mock_client.blocks.list = Mock(return_value=[])
        mock_client.agents.blocks = Mock()
        mock_client.agents.blocks.attach = Mock()

        # --- Mock conversations ---
        conv_counter = {"n": 0}

        def _create_conversation(**kwargs):
            conv_counter["n"] += 1
            return SimpleNamespace(id=f"conv-{conv_counter['n']}")

        mock_client.conversations = Mock()
        mock_client.conversations.create = Mock(side_effect=_create_conversation)
        mock_client.conversations.retrieve = Mock(
            side_effect=lambda conv_id: SimpleNamespace(
                id=conv_id, summary=f"spds:sess|Alice|Topic"
            )
        )
        mock_client.conversations.update = Mock()
        mock_client.conversations.messages = Mock()
        mock_client.conversations.messages.create = Mock(
            return_value=iter(list(_make_stream_response(_assistant_message("I think..."))))
        )
        mock_client.conversations.messages.list = Mock(return_value=[])
        mock_client.conversations.list = Mock(return_value=[])

        # --- Mock agents.messages for assessment (not routed through conversations) ---
        assess_response = SimpleNamespace(
            messages=[
                SimpleNamespace(
                    message_type="tool_call_message",
                    tool_calls=[
                        SimpleNamespace(
                            function=SimpleNamespace(
                                name="perform_subjective_assessment",
                                arguments='{"urgency": 80, "importance": 75, "emotional_state": "curious", "reasoning": "Interesting topic"}',
                            )
                        )
                    ],
                    tool_return=None,
                    content=None,
                )
            ]
        )
        mock_client.agents.messages.create = Mock(return_value=assess_response)

        # Agent profiles
        profiles = [
            {
                "name": "Alice",
                "persona": "A thoughtful researcher",
                "expertise": ["research", "analysis"],
                "model": "openai/gpt-4",
                "embedding": "openai/text-embedding-ada-002",
            }
        ]

        mgr = SwarmManager(mock_client, agent_profiles=profiles)
        return mgr

    def test_lifecycle_creates_and_finalizes_conversations(
        self, mock_letta_client, monkeypatch
    ):
        """Full lifecycle: init -> start_meeting -> end_meeting.

        Verifies that:
        1. ConversationManager is created during __init__
        2. _start_meeting creates per-agent conversations
        3. _end_meeting calls _finalize_conversations
        """
        mgr = self._build_manager(mock_letta_client, monkeypatch)

        # Verify ConversationManager was created
        assert mgr._conversation_manager is not None
        assert hasattr(mgr._conversation_manager, "send_and_collect")

        # Start meeting — should create conversations
        mgr._start_meeting("Test Topic")

        # Verify agent got a conversation ID
        assert len(mgr.agents) == 1
        agent = mgr.agents[0]
        assert agent.conversation_id is not None
        assert agent._conversation_manager is mgr._conversation_manager

        # End meeting — should finalize
        mgr._teardown_cross_agent = Mock()
        mgr._end_meeting()

        # Verify finalization went through the client's conversations.update
        update_mock = mock_letta_client.conversations.update
        assert update_mock.call_count >= 1

        # The updated summary should contain "completed"
        # conversations.update is called with conversation_id=..., summary=...
        update_kwargs = update_mock.call_args_list[0].kwargs
        assert "completed" in update_kwargs.get("summary", "")

    def test_lifecycle_agent_speak_routes_through_conversation(
        self, mock_letta_client, monkeypatch
    ):
        """After start_meeting, agent.speak() routes through conversations."""
        mgr = self._build_manager(mock_letta_client, monkeypatch)
        mgr._start_meeting("Routing Test")

        agent = mgr.agents[0]
        assert agent.conversation_id is not None

        # Reset the conversations.messages.create mock to track speak calls
        conv_msg_create = mock_letta_client.conversations.messages.create
        conv_msg_create.reset_mock()

        # Set up the stream response for the speak call
        speak_stream = list(_make_stream_response(
            _assistant_message("I have thoughts on this.")
        ))
        conv_msg_create.return_value = iter(speak_stream)

        response_text = agent.speak(
            conversation_history="Let's discuss AI.",
            topic="What do you think about AI?",
        )

        # Verify routing went through conversations.messages.create
        assert conv_msg_create.call_count >= 1
        call_kwargs = conv_msg_create.call_args.kwargs
        assert call_kwargs["conversation_id"] == agent.conversation_id

    def test_lifecycle_without_conversation_manager(
        self, mock_letta_client, monkeypatch
    ):
        """If _conversation_manager is None, lifecycle methods are no-ops."""
        mgr = self._build_manager(mock_letta_client, monkeypatch)

        # Forcibly remove conversation manager
        mgr._conversation_manager = None

        # These should all succeed without errors
        mgr._create_agent_conversations("Topic")
        mgr._finalize_conversations()

        # Agents should not have conversation IDs
        for agent in mgr.agents:
            assert agent.conversation_id is None

    def test_lifecycle_secretary_gets_conversation(
        self, mock_letta_client, monkeypatch
    ):
        """Secretary gets its own conversation during _start_meeting."""
        mgr = self._build_manager(mock_letta_client, monkeypatch)

        # Create a mock secretary
        sec = SimpleNamespace(
            agent=SimpleNamespace(id="sec-1"),
            conversation_id=None,
            _conversation_manager=None,
            meeting_metadata={},
        )
        sec.start_meeting = Mock()
        mgr._secretary = sec
        mgr.enable_secretary = True

        mgr._start_meeting("Secretary Test")

        # Secretary should have a conversation
        assert sec.conversation_id is not None
        assert sec._conversation_manager is mgr._conversation_manager

    def test_lifecycle_conversation_failure_nonfatal(
        self, mock_letta_client, monkeypatch
    ):
        """Conversation creation failures don't crash the lifecycle."""
        mgr = self._build_manager(mock_letta_client, monkeypatch)

        # Make create_agent_conversation fail
        cm = mgr._conversation_manager
        cm.create_agent_conversation = Mock(side_effect=RuntimeError("boom"))

        # Should not raise
        mgr._start_meeting("Failure Test")

        # Agent should fall back (no conversation_id)
        agent = mgr.agents[0]
        assert agent.conversation_id is None
        assert agent._conversation_manager is None


class TestSendAndCollectIntegration:
    """Test that send_and_collect properly consumes streams."""

    def test_filters_control_messages(self, mock_letta_client):
        """send_and_collect filters out ping/usage_statistics/etc."""
        from spds.conversations import ConversationManager

        cm = ConversationManager(mock_letta_client)

        # Create a stream with mixed content and control messages
        stream_data = list(_make_stream_response(
            _assistant_message("Real content"),
            _tool_call_message("send_message", '{"message": "Tool call"}'),
        ))
        mock_letta_client.conversations.messages.create.return_value = iter(stream_data)

        result = cm.send_and_collect("conv-test", [{"role": "user", "content": "Hi"}])

        # Should only contain real messages, not ping/usage_statistics
        assert hasattr(result, "messages")
        msg_types = [getattr(m, "message_type", None) for m in result.messages]
        assert "ping" not in msg_types
        assert "usage_statistics" not in msg_types
        assert "assistant_message" in msg_types
        assert "tool_call_message" in msg_types

    def test_empty_stream_returns_empty_messages(self, mock_letta_client):
        """Empty stream returns response with empty messages list."""
        from spds.conversations import ConversationManager

        cm = ConversationManager(mock_letta_client)
        mock_letta_client.conversations.messages.create.return_value = iter([])

        result = cm.send_and_collect("conv-test", [{"role": "user", "content": "Hi"}])

        assert result.messages == []

    def test_only_control_messages_returns_empty(self, mock_letta_client):
        """Stream with only control messages returns empty messages list."""
        from spds.conversations import ConversationManager

        cm = ConversationManager(mock_letta_client)
        control_only = [
            SimpleNamespace(message_type="ping"),
            SimpleNamespace(message_type="usage_statistics", data={}),
            SimpleNamespace(message_type="stop_reason", data="done"),
        ]
        mock_letta_client.conversations.messages.create.return_value = iter(control_only)

        result = cm.send_and_collect("conv-test", [{"role": "user", "content": "Hi"}])

        assert result.messages == []
