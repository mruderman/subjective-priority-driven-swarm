# spds/message.py

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, Any, Optional


@dataclass
class ConversationMessage:
    """
    A structured representation of a single message in an SPDS conversation.
    
    This class replaces the flat tuple format (speaker, message) with a structured
    approach that enables efficient incremental delivery and better conversation context.
    
    Attributes:
        sender: Name of the message sender ("You" for human, agent name for agents)
        content: The actual message text content
        timestamp: When the message was sent (for ordering and context)
    """
    sender: str
    content: str  
    timestamp: datetime
    
    def __post_init__(self):
        """Validate message data after initialization."""
        if not self.sender:
            raise ValueError("Message sender cannot be empty")
        # Reject empty or whitespace-only content
        if not self.content or not str(self.content).strip():
            raise ValueError("Message content cannot be empty")
        if not isinstance(self.timestamp, datetime):
            raise TypeError("Message timestamp must be a datetime object")
    
    def to_flat_format(self) -> str:
        """
        Convert to the legacy flat string format for backward compatibility.
        
        Returns:
            String in format "sender: content" matching existing conversation_history
        """
        return f"{self.sender}: {self.content}"
    
    def is_from_agent(self) -> bool:
        """
        Check if this message is from an agent (not human user).
        
        Returns:
            True if sender is not "You" (human), False otherwise
        """
        return self.sender != "You"
    
    def is_from_human(self) -> bool:
        """
        Check if this message is from the human user.
        
        Returns:
            True if sender is "You" (human), False otherwise  
        """
        return self.sender == "You"
    
    def get_time_since(self, reference_time: datetime) -> float:
        """
        Get the time elapsed since this message relative to a reference time.
        
        Args:
            reference_time: Reference datetime to compare against
            
        Returns:
            Time difference in seconds (positive if this message is newer)
        """
        return (self.timestamp - reference_time).total_seconds()
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert message to dictionary format for serialization.
        
        Returns:
            Dictionary with sender, content, and ISO timestamp
        """
        return {
            "sender": self.sender,
            "content": self.content,
            "timestamp": self.timestamp.isoformat()
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ConversationMessage":
        """
        Create message from dictionary format (for deserialization).
        
        Args:
            data: Dictionary with sender, content, and timestamp keys
            
        Returns:
            ConversationMessage instance
            
        Raises:
            KeyError: If required keys are missing
            ValueError: If timestamp format is invalid
        """
        timestamp_str = data["timestamp"]
        if isinstance(timestamp_str, str):
            # Parse ISO format timestamp
            timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
        else:
            timestamp = timestamp_str
            
        return cls(
            sender=data["sender"],
            content=data["content"],
            timestamp=timestamp
        )
    
    @classmethod
    def from_tuple(cls, message_tuple: tuple, timestamp: Optional[datetime] = None) -> "ConversationMessage":
        """
        Create message from legacy (speaker, content) tuple format.
        
        Args:
            message_tuple: Tuple in format (speaker, content)
            timestamp: Optional timestamp (defaults to current time)
            
        Returns:
            ConversationMessage instance
            
        Raises:
            ValueError: If tuple format is invalid
        """
        if len(message_tuple) != 2:
            raise ValueError("Message tuple must have exactly 2 elements (speaker, content)")
        
        speaker, content = message_tuple
        if timestamp is None:
            timestamp = datetime.now()
            
        return cls(sender=speaker, content=content, timestamp=timestamp)
    
    def __str__(self) -> str:
        """String representation matching legacy format."""
        return self.to_flat_format()
    
    def __repr__(self) -> str:
        """Developer-friendly representation."""
        return f"ConversationMessage(sender='{self.sender}', content='{self.content[:50]}...', timestamp={self.timestamp})"
    
    def __eq__(self, other) -> bool:
        """Equality comparison based on sender, content, and timestamp."""
        if not isinstance(other, ConversationMessage):
            return False
        return (self.sender == other.sender and 
                self.content == other.content and 
                self.timestamp == other.timestamp)
    
    def __lt__(self, other) -> bool:
        """Less-than comparison for sorting by timestamp."""
        if not isinstance(other, ConversationMessage):
            return NotImplemented
        return self.timestamp < other.timestamp


def convert_history_to_messages(flat_history: list, base_timestamp: Optional[datetime] = None) -> list["ConversationMessage"]:
    """
    Convert legacy flat history format to ConversationMessage objects.
    
    Args:
        flat_history: List of (speaker, content) tuples
        base_timestamp: Starting timestamp (defaults to current time)
        
    Returns:
        List of ConversationMessage objects with incremental timestamps
    """
    if base_timestamp is None:
        base_timestamp = datetime.now()
    
    messages = []
    for i, (speaker, content) in enumerate(flat_history):
        # Create incremental timestamps (1 second apart for ordering)
        timestamp = base_timestamp.replace(microsecond=0) - timedelta(seconds=len(flat_history) - i - 1)
        messages.append(ConversationMessage(sender=speaker, content=content, timestamp=timestamp))
    
    return messages


def messages_to_flat_format(messages: list["ConversationMessage"]) -> str:
    """
    Convert ConversationMessage objects to legacy flat string format.
    
    Args:
        messages: List of ConversationMessage objects
        
    Returns:
        Newline-separated string in "sender: content" format
    """
    return "\n".join(msg.to_flat_format() for msg in messages)


def get_new_messages_since_index(messages: list["ConversationMessage"], last_index: int) -> list["ConversationMessage"]:
    """
    Get messages that are new since a given index position.
    
    This is the core function for incremental message delivery to agents.
    
    Args:
        messages: Full list of conversation messages
        last_index: Index of last message the agent processed (-1 if agent hasn't spoken)
        
    Returns:
        List of new messages since last_index (empty list if no new messages)
    """
    if last_index is None or last_index < 0:
        # Agent hasn't spoken yet, return all messages
        return messages.copy()
    
    # Return messages after the last index
    return messages[last_index + 1:].copy()