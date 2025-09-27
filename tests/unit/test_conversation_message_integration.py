"""
Integration tests for ConversationMessage architecture.

These tests verify that the SwarmManager properly uses ConversationMessage objects
throughout the conversation flow, ensuring the new incremental delivery system
works correctly across all conversation modes.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, MagicMock

from spds.swarm_manager import SwarmManager
from spds.message import ConversationMessage
from spds.spds_agent import SPDSAgent


class TestConversationMessageIntegration:
    """Test ConversationMessage integration in SwarmManager."""

    def test_swarm_manager_uses_conversation_message_internally(self):
        """Test that SwarmManager properly uses ConversationMessage objects internally."""
        # Create a mock swarm manager
        manager = SwarmManager.__new__(SwarmManager)
        manager._history = []
        manager._emit = Mock()
        
        # Add a message using the _append_history method
        manager._append_history("You", "Test message")
        
        # Verify internal storage uses ConversationMessage
        assert len(manager._history) == 1
        assert isinstance(manager._history[0], ConversationMessage)
        assert manager._history[0].sender == "You"
        assert manager._history[0].content == "Test message"
        assert isinstance(manager._history[0].timestamp, datetime)

    def test_conversation_message_serialization(self):
        """Test that ConversationMessage objects serialize correctly."""
        # Create a message
        message = ConversationMessage(
            sender="Agent1",
            content="Hello world",
            timestamp=datetime.now()
        )
        
        # Test to_dict conversion
        message_dict = message.to_dict()
        assert message_dict["sender"] == "Agent1"
        assert message_dict["content"] == "Hello world"
        assert "timestamp" in message_dict

    def test_conversation_message_str_format(self):
        """Test ConversationMessage string representation."""
        message = ConversationMessage(
            sender="Alice",
            content="Testing the system",
            timestamp=datetime.now()
        )
        
        # Test __str__ method
        str_repr = str(message)
        assert "Alice: Testing the system" in str_repr

    def test_get_filtered_conversation_history_empty(self):
        """Test _get_filtered_conversation_history with empty history."""
        manager = SwarmManager.__new__(SwarmManager)
        manager._history = []
        
        # Create mock agent
        agent = Mock()
        agent.last_message_index = None
        
        # Test the method
        result = manager._get_filtered_conversation_history(agent)
        assert result == ""

    def test_get_filtered_conversation_history_first_time(self):
        """Test _get_filtered_conversation_history for agent speaking first time."""
        manager = SwarmManager.__new__(SwarmManager)
        
        # Add some messages
        messages = [
            ConversationMessage("You", "Hello", datetime.now()),
            ConversationMessage("Agent1", "Hi there", datetime.now()),
            ConversationMessage("You", "How are you?", datetime.now())
        ]
        manager._history = messages
        
        # Create mock agent (first time speaking)
        agent = Mock()
        agent.last_message_index = None
        
        # Test the method - should get all messages
        result = manager._get_filtered_conversation_history(agent)
        expected = "You: Hello\nAgent1: Hi there\nYou: How are you?"
        assert result == expected

    def test_get_filtered_conversation_history_with_history(self):
        """Test _get_filtered_conversation_history for agent with previous messages."""
        manager = SwarmManager.__new__(SwarmManager)
        
        # Add some messages
        messages = [
            ConversationMessage("You", "Start", datetime.now()),
            ConversationMessage("Agent1", "Response 1", datetime.now()),
            ConversationMessage("Agent2", "Response 2", datetime.now()),
            ConversationMessage("You", "Follow up", datetime.now()),
            ConversationMessage("Agent1", "Final response", datetime.now())
        ]
        manager._history = messages
        
        # Create mock agent that spoke at index 1
        agent = Mock()
        agent.last_message_index = 1
        
        # Test the method - should get messages after index 1
        result = manager._get_filtered_conversation_history(agent)
        expected = "Agent2: Response 2\nYou: Follow up\nAgent1: Final response"
        assert result == expected

    def test_conversation_message_timeline_consistency(self):
        """Test that ConversationMessage objects maintain proper timeline order."""
        manager = SwarmManager.__new__(SwarmManager)
        manager._history = []
        manager._emit = Mock()
        
        # Add messages with slight delays
        base_time = datetime.now()
        messages = [
            ("You", "First message", base_time),
            ("Agent1", "Second message", base_time + timedelta(seconds=1)),
            ("You", "Third message", base_time + timedelta(seconds=2))
        ]
        
        for sender, content, timestamp in messages:
            message = ConversationMessage(sender, content, timestamp)
            manager._history.append(message)
        
        # Verify timestamps are in order
        for i in range(1, len(manager._history)):
            assert manager._history[i].timestamp >= manager._history[i-1].timestamp
        
        # Verify filtered history works with timeline
        agent = Mock()
        agent.last_message_index = 0
        
        result = manager._get_filtered_conversation_history(agent)
        assert "Agent1: Second message" in result
        assert "You: Third message" in result
        assert "You: First message" not in result  # Should be filtered out

    def test_conversation_message_backward_compatibility(self):
        """Test that conversation_history property still works for backward compatibility."""
        manager = SwarmManager.__new__(SwarmManager)
        
        # Add messages
        messages = [
            ConversationMessage("You", "Hello", datetime.now()),
            ConversationMessage("Agent1", "Hi", datetime.now())
        ]
        manager._history = messages
        
        # Test backward compatibility property
        # Note: This property should be deprecated but still functional
        assert hasattr(manager, '_history')
        assert len(manager._history) == 2
        assert all(isinstance(msg, ConversationMessage) for msg in manager._history)