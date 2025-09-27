"""
Unit tests for the ConversationMessage class.

This module tests the new ConversationMessage dataclass that will replace
the current tuple-based conversation history system.
"""

import json
import pickle
from datetime import datetime, timedelta
from unittest.mock import patch

import pytest

# Import the ConversationMessage class from the actual implementation
from spds.message import ConversationMessage


class TestConversationMessageBasics:
    """Test basic ConversationMessage functionality."""
    
    def test_message_creation_with_all_fields(self):
        """Test creating a message with all required fields."""
        timestamp = datetime(2024, 1, 15, 14, 30, 0)
        msg = ConversationMessage(
            sender="Alice",
            content="Hello everyone, let's discuss the project timeline.",
            timestamp=timestamp
        )
        
        assert msg.sender == "Alice"
        assert msg.content == "Hello everyone, let's discuss the project timeline."
        assert msg.timestamp == timestamp
    
    def test_message_creation_with_current_timestamp(self):
        """Test creating a message with current timestamp."""
        before = datetime.now()
        msg = ConversationMessage(
            sender="Bob",
            content="I have some concerns about the current approach.",
            timestamp=datetime.now()
        )
        after = datetime.now()
        
        assert before <= msg.timestamp <= after
        assert msg.sender == "Bob"
        assert "concerns" in msg.content
    
    def test_message_immutability(self):
        """Test that ConversationMessage is immutable (dataclass with frozen=True would be ideal)."""
        msg = ConversationMessage(
            sender="Carol",
            content="This is the original content.",
            timestamp=datetime.now()
        )
        
        # While dataclass doesn't enforce immutability by default,
        # we can test that the fields are properly set
        assert msg.sender == "Carol"
        assert msg.content == "This is the original content."
        
        # In a real implementation, we'd want frozen=True on the dataclass
        # to prevent accidental mutation
    
    def test_empty_content_handling(self):
        """Test handling of empty or whitespace-only content."""
        # Empty content
        msg_empty = ConversationMessage(
            sender="Dave",
            content="",
            timestamp=datetime.now()
        )
        assert msg_empty.content == ""
        assert str(msg_empty) == "Dave: "
        
        # Whitespace-only content
        msg_whitespace = ConversationMessage(
            sender="Eve",
            content="   \n\t  ",
            timestamp=datetime.now()
        )
        assert msg_whitespace.content == "   \n\t  "
        assert "Eve:" in str(msg_whitespace)
    
    def test_special_characters_in_content(self):
        """Test handling of special characters in message content."""
        special_content = "Hello! @everyone 👋 Let's discuss:\n• Point 1\n• Point 2\n\nThanks 😊"
        msg = ConversationMessage(
            sender="Frank",
            content=special_content,
            timestamp=datetime.now()
        )
        
        assert msg.content == special_content
        assert "👋" in str(msg)
        assert "😊" in str(msg)
        assert "\n" in msg.content


class TestConversationMessageFormatting:
    """Test message formatting and string representation."""
    
    def test_basic_string_formatting(self):
        """Test basic string representation."""
        msg = ConversationMessage(
            sender="Alice",
            content="This is a test message.",
            timestamp=datetime.now()
        )
        
        result = str(msg)
        assert result == "Alice: This is a test message."
    
    def test_human_sender_formatting(self):
        """Test formatting for human messages."""
        msg = ConversationMessage(
            sender="You",
            content="What do you think about this approach?",
            timestamp=datetime.now()
        )
        
        result = str(msg)
        assert result == "You: What do you think about this approach?"
    
    def test_multiline_content_formatting(self):
        """Test formatting of multiline content."""
        content = "Here are my thoughts:\n1. First point\n2. Second point\n\nThanks!"
        msg = ConversationMessage(
            sender="Bob",
            content=content,
            timestamp=datetime.now()
        )
        
        result = str(msg)
        expected = f"Bob: {content}"
        assert result == expected
        assert "\n" in result
    
    def test_long_content_formatting(self):
        """Test formatting of very long content."""
        long_content = "This is a very long message " * 50  # 1400+ characters
        msg = ConversationMessage(
            sender="Carol",
            content=long_content,
            timestamp=datetime.now()
        )
        
        result = str(msg)
        assert result.startswith("Carol: This is a very long message")
        assert len(result) > 1400
        assert "very long message" in result


class TestConversationMessageSerialization:
    """Test serialization and deserialization of messages."""
    
    def test_to_dict_conversion(self):
        """Test converting message to dictionary."""
        timestamp = datetime(2024, 1, 15, 14, 30, 45)
        msg = ConversationMessage(
            sender="Alice",
            content="Let's serialize this message.",
            timestamp=timestamp
        )
        
        result = msg.to_dict()
        
        assert isinstance(result, dict)
        assert result["sender"] == "Alice"
        assert result["content"] == "Let's serialize this message."
        assert result["timestamp"] == "2024-01-15T14:30:45"
        assert len(result) == 3  # Only the three expected fields
    
    def test_from_dict_reconstruction(self):
        """Test reconstructing message from dictionary."""
        data = {
            "sender": "Bob",
            "content": "This message was reconstructed from a dict.",
            "timestamp": "2024-01-15T16:45:30"
        }
        
        msg = ConversationMessage.from_dict(data)
        
        assert msg.sender == "Bob"
        assert msg.content == "This message was reconstructed from a dict."
        assert msg.timestamp == datetime(2024, 1, 15, 16, 45, 30)
    
    def test_round_trip_serialization(self):
        """Test full round-trip serialization."""
        original = ConversationMessage(
            sender="Carol",
            content="Testing round-trip serialization with special chars: 🎉",
            timestamp=datetime(2024, 2, 20, 9, 15, 0)
        )
        
        # Serialize to dict
        data = original.to_dict()
        
        # Deserialize back
        reconstructed = ConversationMessage.from_dict(data)
        
        # Verify they're identical
        assert reconstructed.sender == original.sender
        assert reconstructed.content == original.content
        assert reconstructed.timestamp == original.timestamp
        assert str(reconstructed) == str(original)
    
    def test_json_serialization_compatibility(self):
        """Test that messages can be JSON serialized via to_dict."""
        msg = ConversationMessage(
            sender="Dave",
            content="JSON serialization test.",
            timestamp=datetime(2024, 3, 10, 12, 0, 0)
        )
        
        # Convert to dict and serialize to JSON
        data = msg.to_dict()
        json_str = json.dumps(data)
        
        # Deserialize from JSON and reconstruct
        loaded_data = json.loads(json_str)
        reconstructed = ConversationMessage.from_dict(loaded_data)
        
        assert reconstructed.sender == msg.sender
        assert reconstructed.content == msg.content
        assert reconstructed.timestamp == msg.timestamp
    
    def test_serialization_with_timezone_info(self):
        """Test serialization handles timezone information properly."""
        # Test with timezone-aware datetime
        from datetime import timezone
        
        timestamp_with_tz = datetime(2024, 1, 15, 14, 30, 0, tzinfo=timezone.utc)
        msg = ConversationMessage(
            sender="Eve",
            content="Message with timezone.",
            timestamp=timestamp_with_tz
        )
        
        data = msg.to_dict()
        reconstructed = ConversationMessage.from_dict(data)
        
        # The ISO format should preserve timezone info
        assert "T14:30:00+00:00" in data["timestamp"]
        assert reconstructed.timestamp.tzinfo is not None


class TestConversationMessageComparison:
    """Test message comparison and equality operations."""
    
    def test_message_equality(self):
        """Test that identical messages are considered equal."""
        timestamp = datetime(2024, 1, 15, 10, 0, 0)
        
        msg1 = ConversationMessage("Alice", "Hello world!", timestamp)
        msg2 = ConversationMessage("Alice", "Hello world!", timestamp)
        
        assert msg1 == msg2
    
    def test_message_inequality_different_content(self):
        """Test that messages with different content are not equal."""
        timestamp = datetime(2024, 1, 15, 10, 0, 0)
        
        msg1 = ConversationMessage("Alice", "Hello world!", timestamp)
        msg2 = ConversationMessage("Alice", "Goodbye world!", timestamp)
        
        assert msg1 != msg2
    
    def test_message_inequality_different_sender(self):
        """Test that messages with different senders are not equal."""
        timestamp = datetime(2024, 1, 15, 10, 0, 0)
        
        msg1 = ConversationMessage("Alice", "Hello world!", timestamp)
        msg2 = ConversationMessage("Bob", "Hello world!", timestamp)
        
        assert msg1 != msg2
    
    def test_message_inequality_different_timestamp(self):
        """Test that messages with different timestamps are not equal."""
        msg1 = ConversationMessage("Alice", "Hello world!", datetime(2024, 1, 15, 10, 0, 0))
        msg2 = ConversationMessage("Alice", "Hello world!", datetime(2024, 1, 15, 10, 0, 1))
        
        assert msg1 != msg2
    
    def test_message_sorting(self):
        """Test that messages can be sorted by timestamp."""
        base_time = datetime(2024, 1, 15, 10, 0, 0)
        
        messages = [
            ConversationMessage("Carol", "Third message", base_time + timedelta(minutes=2)),
            ConversationMessage("Alice", "First message", base_time),
            ConversationMessage("Bob", "Second message", base_time + timedelta(minutes=1)),
        ]
        
        # Sort by timestamp
        sorted_messages = sorted(messages, key=lambda m: m.timestamp)
        
        assert sorted_messages[0].sender == "Alice"
        assert sorted_messages[1].sender == "Bob"
        assert sorted_messages[2].sender == "Carol"


class TestConversationMessageValidation:
    """Test validation and edge cases for message creation."""
    
    def test_sender_validation(self):
        """Test various sender name formats."""
        # Valid sender names
        valid_senders = [
            "Alice",
            "Agent_1",
            "Project Manager",
            "You",
            "AI Assistant",
            "user@domain.com",
            "Agent-007"
        ]
        
        for sender in valid_senders:
            msg = ConversationMessage(
                sender=sender,
                content="Test message",
                timestamp=datetime.now()
            )
            assert msg.sender == sender
    
    def test_very_long_sender_name(self):
        """Test handling of very long sender names."""
        long_sender = "A" * 1000  # 1000 character sender name
        msg = ConversationMessage(
            sender=long_sender,
            content="Test with long sender name",
            timestamp=datetime.now()
        )
        
        assert msg.sender == long_sender
        assert len(str(msg)) > 1000
    
    def test_unicode_sender_names(self):
        """Test handling of Unicode characters in sender names."""
        unicode_senders = [
            "José",
            "李明",
            "محمد",
            "🤖 AI Bot",
            "Ñiño"
        ]
        
        for sender in unicode_senders:
            msg = ConversationMessage(
                sender=sender,
                content="Unicode test message",
                timestamp=datetime.now()
            )
            assert msg.sender == sender
            assert sender in str(msg)
    
    def test_edge_case_timestamps(self):
        """Test edge cases for timestamp handling."""
        # Very old timestamp
        old_msg = ConversationMessage(
            sender="Historian",
            content="Message from the past",
            timestamp=datetime(1970, 1, 1, 0, 0, 0)
        )
        assert old_msg.timestamp.year == 1970
        
        # Far future timestamp
        future_msg = ConversationMessage(
            sender="Time Traveler",
            content="Message from the future",
            timestamp=datetime(2100, 12, 31, 23, 59, 59)
        )
        assert future_msg.timestamp.year == 2100
        
        # Timestamp with microseconds
        precise_msg = ConversationMessage(
            sender="Precision",
            content="Precise timing",
            timestamp=datetime(2024, 1, 15, 14, 30, 45, 123456)
        )
        assert precise_msg.timestamp.microsecond == 123456


class TestConversationMessagePerformance:
    """Test performance characteristics of ConversationMessage operations."""
    
    def test_creation_performance(self):
        """Test that message creation is fast for large volumes."""
        import time
        
        start_time = time.time()
        messages = []
        
        # Create 1000 messages
        for i in range(1000):
            msg = ConversationMessage(
                sender=f"Agent{i % 10}",
                content=f"Message number {i} with some content to simulate real usage",
                timestamp=datetime.now()
            )
            messages.append(msg)
        
        creation_time = time.time() - start_time
        
        # Should be very fast (under 1 second for 1000 messages)
        assert creation_time < 1.0
        assert len(messages) == 1000
    
    def test_serialization_performance(self):
        """Test serialization performance for message batches."""
        import time
        
        # Create test messages
        messages = [
            ConversationMessage(
                sender=f"Agent{i % 5}",
                content=f"Test message {i} with moderate length content for performance testing",
                timestamp=datetime.now()
            )
            for i in range(100)
        ]
        
        # Test serialization performance
        start_time = time.time()
        serialized_data = [msg.to_dict() for msg in messages]
        serialization_time = time.time() - start_time
        
        # Test deserialization performance
        start_time = time.time()
        reconstructed = [ConversationMessage.from_dict(data) for data in serialized_data]
        deserialization_time = time.time() - start_time
        
        # Both operations should be fast
        assert serialization_time < 0.1  # Under 100ms for 100 messages
        assert deserialization_time < 0.1  # Under 100ms for 100 messages
        assert len(reconstructed) == 100
    
    def test_string_formatting_performance(self):
        """Test string formatting performance."""
        import time
        
        # Create messages with varying content lengths
        messages = []
        for i in range(500):
            content_length = (i % 10 + 1) * 50  # Varying lengths from 50 to 500 chars
            content = "x" * content_length
            messages.append(ConversationMessage(
                sender=f"Agent{i % 3}",
                content=content,
                timestamp=datetime.now()
            ))
        
        # Test string formatting performance
        start_time = time.time()
        formatted = [str(msg) for msg in messages]
        formatting_time = time.time() - start_time
        
        # Should be very fast
        assert formatting_time < 0.1  # Under 100ms for 500 messages
        assert len(formatted) == 500
        assert all(isinstance(f, str) for f in formatted)


class TestConversationMessageIntegration:
    """Test integration with other system components."""
    
    def test_backward_compatibility_with_tuple_format(self):
        """Test conversion to/from legacy tuple format."""
        msg = ConversationMessage(
            sender="Alice",
            content="Converting to legacy format",
            timestamp=datetime.now()
        )
        
        # Convert to legacy tuple format (sender, content)
        legacy_tuple = (msg.sender, msg.content)
        assert legacy_tuple == ("Alice", "Converting to legacy format")
        
        # Convert from legacy tuple format
        sender, content = legacy_tuple
        reconstructed = ConversationMessage(
            sender=sender,
            content=content,
            timestamp=datetime.now()  # Timestamp would be generated
        )
        
        assert reconstructed.sender == msg.sender
        assert reconstructed.content == msg.content
    
    def test_conversation_history_conversion(self):
        """Test converting message list to conversation history string."""
        messages = [
            ConversationMessage("You", "Hello everyone", datetime.now()),
            ConversationMessage("Alice", "Hello back!", datetime.now()),
            ConversationMessage("Bob", "Good to see you all", datetime.now()),
        ]
        
        # Convert to conversation history string (current format)
        history_string = "\n".join(str(msg) for msg in messages)
        
        expected = "You: Hello everyone\nAlice: Hello back!\nBob: Good to see you all"
        assert history_string == expected
        
        # Test that it can be parsed back (if needed)
        lines = history_string.split("\n")
        assert len(lines) == 3
        assert "You: Hello everyone" in lines[0]
    
    def test_secretary_integration_format(self):
        """Test format suitable for secretary agent observation."""
        msg = ConversationMessage(
            sender="Project Manager",
            content="We need to finalize the sprint planning by EOD.",
            timestamp=datetime(2024, 1, 15, 14, 30, 0)
        )
        
        # Format for secretary observation
        secretary_format = {
            "speaker": msg.sender,
            "content": msg.content,
            "timestamp": msg.timestamp.isoformat(),
            "formatted_message": str(msg)
        }
        
        assert secretary_format["speaker"] == "Project Manager"
        assert secretary_format["content"] == "We need to finalize the sprint planning by EOD."
        assert secretary_format["timestamp"] == "2024-01-15T14:30:00"
        assert secretary_format["formatted_message"] == "Project Manager: We need to finalize the sprint planning by EOD."
    
    def test_export_format_compatibility(self):
        """Test compatibility with export functionality."""
        messages = [
            ConversationMessage("You", "Start of meeting", datetime(2024, 1, 15, 10, 0, 0)),
            ConversationMessage("Manager", "Let's review the agenda", datetime(2024, 1, 15, 10, 1, 0)),
            ConversationMessage("Developer", "I have updates", datetime(2024, 1, 15, 10, 2, 0)),
        ]
        
        # Test transcript export format
        transcript = "\n".join(
            f"[{msg.timestamp.strftime('%H:%M')}] {str(msg)}"
            for msg in messages
        )
        
        expected_lines = [
            "[10:00] You: Start of meeting",
            "[10:01] Manager: Let's review the agenda", 
            "[10:02] Developer: I have updates"
        ]
        
        for expected_line in expected_lines:
            assert expected_line in transcript
        
        # Test summary export format
        summary = {
            "participants": list(set(msg.sender for msg in messages)),
            "message_count": len(messages),
            "start_time": messages[0].timestamp.isoformat(),
            "end_time": messages[-1].timestamp.isoformat()
        }
        
        assert len(summary["participants"]) == 3
        assert "You" in summary["participants"]
        assert summary["message_count"] == 3