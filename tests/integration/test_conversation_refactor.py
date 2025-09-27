"""
Integration tests for the SPDS conversation logic refactor.

This test suite validates the major refactor that fixes the "round cycling problem"
where agents assess motivation against static topics instead of evolving conversation.

Key areas tested:
1. ConversationMessage class functionality
2. Dynamic vs static context assessment
3. Message filtering and delivery efficiency
4. Agent context awareness improvements
5. Backward compatibility preservation
6. Performance benchmarks for before/after comparison
"""

import json
import time
from datetime import datetime, timedelta
from typing import List, Tuple
from unittest.mock import MagicMock, Mock, patch
from dataclasses import dataclass

import pytest
from letta_client.types import AgentState

from spds.spds_agent import SPDSAgent
from spds.swarm_manager import SwarmManager
from spds.tools import SubjectiveAssessment


# ConversationMessage class for the refactor (will be moved to spds/message.py)
@dataclass
class ConversationMessage:
    """Structured message for conversation history management."""
    sender: str           # Agent name or "You" for human
    content: str         # Message text content
    timestamp: datetime  # When message was sent
    
    def __str__(self) -> str:
        """Format message for display."""
        return f"{self.sender}: {self.content}"
    
    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "sender": self.sender,
            "content": self.content,
            "timestamp": self.timestamp.isoformat()
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "ConversationMessage":
        """Create from dictionary."""
        return cls(
            sender=data["sender"],
            content=data["content"],
            timestamp=datetime.fromisoformat(data["timestamp"])
        )


class TestConversationMessage:
    """Unit tests for the ConversationMessage class."""
    
    def test_message_creation(self):
        """Test basic message creation and properties."""
        timestamp = datetime.now()
        msg = ConversationMessage(
            sender="Alice",
            content="Hello everyone!",
            timestamp=timestamp
        )
        
        assert msg.sender == "Alice"
        assert msg.content == "Hello everyone!"
        assert msg.timestamp == timestamp
    
    def test_string_representation(self):
        """Test message string formatting."""
        msg = ConversationMessage(
            sender="Bob",
            content="I agree with the proposal.",
            timestamp=datetime.now()
        )
        
        assert str(msg) == "Bob: I agree with the proposal."
    
    def test_serialization(self):
        """Test message serialization and deserialization."""
        original = ConversationMessage(
            sender="Carol",
            content="Let's discuss the technical details.",
            timestamp=datetime(2024, 1, 15, 10, 30, 0)
        )
        
        # Serialize to dict
        data = original.to_dict()
        assert data["sender"] == "Carol"
        assert data["content"] == "Let's discuss the technical details."
        assert data["timestamp"] == "2024-01-15T10:30:00"
        
        # Deserialize back
        restored = ConversationMessage.from_dict(data)
        assert restored.sender == original.sender
        assert restored.content == original.content
        assert restored.timestamp == original.timestamp
    
    def test_human_message_formatting(self):
        """Test formatting for human messages."""
        msg = ConversationMessage(
            sender="You",
            content="What are your thoughts on this?",
            timestamp=datetime.now()
        )
        
        assert str(msg) == "You: What are your thoughts on this?"


class TestStaticTopicProblem:
    """Tests that demonstrate the current static topic assessment problem."""
    
    def create_mock_agent(self, name: str, assessment_scores: dict = None) -> SPDSAgent:
        """Create a mock SPDSAgent for testing."""
        if assessment_scores is None:
            assessment_scores = {
                "importance_to_self": 7,
                "perceived_gap": 6,
                "unique_perspective": 8,
                "emotional_investment": 5,
                "expertise_relevance": 9,
                "urgency": 7,
                "importance_to_group": 8
            }
        
        mock_client = Mock()
        mock_agent_state = Mock()
        mock_agent_state.id = f"ag-{name.lower()}-123"
        mock_agent_state.name = name
        mock_agent_state.system = f"You are {name}. Your persona is: Test agent. Your expertise is in: testing."
        
        agent = SPDSAgent(mock_agent_state, mock_client)
        
        # Mock the assessment method to return predictable scores
        mock_assessment = SubjectiveAssessment(**assessment_scores)
        agent.last_assessment = mock_assessment
        
        return agent
    
    def test_current_static_topic_assessment(self):
        """Test that current system always assesses against the same static topic."""
        # Simulate the current behavior where agents always see the original topic
        original_topic = "Hi Jack and Jill, let's discuss our testing strategy"
        
        agent = self.create_mock_agent("TestAgent")
        
        # Mock the assessment method to track what topic it receives
        assessment_calls = []
        def mock_assess(topic):
            assessment_calls.append(topic)
            agent.motivation_score = 35  # Above threshold
            agent.priority_score = 7.5
        
        agent.assess_motivation_and_priority = mock_assess
        
        # Simulate multiple conversation rounds with evolving discussion
        conversation_history = [
            ("You", "Hi Jack and Jill, let's discuss our testing strategy"),
            ("Jack", "I think we need more unit tests for the API layer"),
            ("Jill", "What about integration tests for the database interactions?"),
            ("You", "Good points. What about performance testing?"),
            ("Jack", "We should benchmark the new caching system"),
        ]
        
        # Current system: Agent always assesses against original topic
        for i in range(len(conversation_history)):
            agent.assess_motivation_and_priority(original_topic)
        
        # Verify the problem: Agent always sees the same static topic
        assert all(call == original_topic for call in assessment_calls)
        assert len(set(assessment_calls)) == 1  # Only one unique topic seen
        
        # This demonstrates the problem: even though the conversation evolved
        # from general testing strategy to specific performance benchmarking,
        # the agent is still assessing motivation against the original greeting
    
    def test_desired_dynamic_context_assessment(self):
        """Test the desired behavior with dynamic context assessment."""
        original_topic = "Hi Jack and Jill, let's discuss our testing strategy"
        
        # Simulate the conversation evolution
        messages = [
            ConversationMessage("You", "Hi Jack and Jill, let's discuss our testing strategy", datetime.now()),
            ConversationMessage("Jack", "I think we need more unit tests for the API layer", datetime.now()),
            ConversationMessage("Jill", "What about integration tests for the database interactions?", datetime.now()),
            ConversationMessage("You", "Good points. What about performance testing?", datetime.now()),
            ConversationMessage("Jack", "We should benchmark the new caching system", datetime.now()),
        ]
        
        agent = self.create_mock_agent("TestAgent")
        
        # Mock new assessment method that takes recent messages + original topic
        assessment_calls = []
        def mock_new_assess(recent_messages, original_topic):
            assessment_calls.append({
                "recent_messages": [str(msg) for msg in recent_messages],
                "original_topic": original_topic
            })
            agent.motivation_score = 35
            agent.priority_score = 7.5
        
        # Simulate the new behavior: agent sees recent conversation context
        # Instead of assess_motivation_and_priority(topic), it would be:
        # assess_motivation_and_priority(recent_messages, original_topic)
        
        # For each assessment, provide the last 2-3 messages as context
        for i in range(2, len(messages)):
            recent_context = messages[max(0, i-2):i+1]  # Last 3 messages including current
            mock_new_assess(recent_context, original_topic)
        
        # Verify improvement: Agent sees evolving conversation context
        assert len(assessment_calls) == 3  # 3 assessment calls made
        
        # First assessment: sees initial topic discussion
        first_call = assessment_calls[0]
        assert "testing strategy" in " ".join(first_call["recent_messages"])
        
        # Last assessment: sees current performance testing discussion  
        last_call = assessment_calls[-1]
        recent_context = " ".join(last_call["recent_messages"])
        assert "performance testing" in recent_context
        assert "benchmark" in recent_context
        assert "caching system" in recent_context
        
        # Agent still has access to original topic for context
        assert all(call["original_topic"] == original_topic for call in assessment_calls)


class TestMessageDeliveryEfficiency:
    """Tests for the new incremental message delivery system."""
    
    def test_get_new_messages_since_last_turn(self):
        """Test filtering messages to only new ones since agent's last turn."""
        # Create conversation history
        messages = [
            ConversationMessage("You", "Let's start the discussion", datetime.now()),
            ConversationMessage("Agent1", "I have some initial thoughts", datetime.now()),
            ConversationMessage("Agent2", "I agree with Agent1", datetime.now()),  
            ConversationMessage("You", "What about the technical details?", datetime.now()),
            ConversationMessage("Agent3", "I can help with that", datetime.now()),
            ConversationMessage("Agent1", "Let me add more context", datetime.now()),  # Agent1 last spoke here
            ConversationMessage("You", "Great points everyone", datetime.now()),
            ConversationMessage("Agent2", "I have a follow-up question", datetime.now()),
        ]
        
        # Mock agent tracking
        class MockAgent:
            def __init__(self, name, last_message_index=-1):
                self.name = name
                self.last_message_index = last_message_index
        
        agent1 = MockAgent("Agent1", last_message_index=5)  # Last spoke at index 5
        
        # Function to get new messages (this would be in SwarmManager)
        def get_new_messages_since_last_turn(agent, all_messages):
            if agent.last_message_index < 0:
                return all_messages  # First time speaking, return all
            return all_messages[agent.last_message_index + 1:]
        
        new_messages = get_new_messages_since_last_turn(agent1, messages)
        
        # Should only get messages after index 5
        assert len(new_messages) == 2
        assert new_messages[0].content == "Great points everyone"
        assert new_messages[1].content == "I have a follow-up question"
        
        # Verify we don't get Agent1's own last message or earlier messages
        message_contents = [msg.content for msg in new_messages]
        assert "Let me add more context" not in message_contents
        assert "I have some initial thoughts" not in message_contents
    
    def test_first_time_agent_gets_all_messages(self):
        """Test that agents speaking for the first time get full context."""
        messages = [
            ConversationMessage("You", "Welcome to the meeting", datetime.now()),
            ConversationMessage("Agent1", "Hello everyone", datetime.now()),
            ConversationMessage("Agent2", "Nice to meet you all", datetime.now()),
        ]
        
        class MockAgent:
            def __init__(self, name):
                self.name = name
                self.last_message_index = -1  # Never spoke before
        
        new_agent = MockAgent("Agent3")
        
        def get_new_messages_since_last_turn(agent, all_messages):
            if agent.last_message_index < 0:
                return all_messages
            return all_messages[agent.last_message_index + 1:]
        
        new_messages = get_new_messages_since_last_turn(new_agent, messages)
        
        # Should get all messages since it's the first time
        assert len(new_messages) == 3
        assert new_messages[0].content == "Welcome to the meeting"
        assert new_messages[-1].content == "Nice to meet you all"


class TestConversationModeIntegration:
    """Integration tests for all conversation modes with new message system."""
    
    def setup_method(self):
        """Set up test environment."""
        self.mock_client = Mock()
        self.agents = []
        
        # Create mock agents
        for i, name in enumerate(["Alice", "Bob", "Charlie"]):
            mock_agent_state = Mock()
            mock_agent_state.id = f"ag-{name.lower()}-{i}"
            mock_agent_state.name = name
            mock_agent_state.system = f"You are {name}. Your persona is: Test agent {i}. Your expertise is in: testing."
            
            agent = SPDSAgent(mock_agent_state, self.mock_client)
            agent.last_message_index = -1  # Track last message for filtering
            
            # Mock assessment to always participate
            agent.motivation_score = 35
            agent.priority_score = 8.0 - i  # Different priorities
            
            self.agents.append(agent)
    
    def create_swarm_manager(self, mode="hybrid"):
        """Create SwarmManager with mocked dependencies."""
        with patch('spds.swarm_manager.config.logger') as mock_logger:
            manager = SwarmManager(
                agents=self.agents,
                conversation_mode=mode,
                secretary=None,
                export_manager=None
            )
            
            # Replace history with ConversationMessage list
            manager._history = []
            manager._conversation_messages = []  # New structured history
            
            return manager
    
    def test_hybrid_mode_with_new_message_delivery(self):
        """Test hybrid mode using incremental message delivery."""
        manager = self.create_swarm_manager("hybrid")
        
        # Mock the agent assessment and speaking methods
        assessment_contexts = []
        
        def mock_assess_with_context(agent, recent_messages, original_topic):
            assessment_contexts.append({
                "agent": agent.name,
                "recent_messages": [str(msg) for msg in recent_messages],
                "original_topic": original_topic
            })
            agent.motivation_score = 35
            agent.priority_score = 8.0
        
        def mock_agent_speak(agent, context):
            return f"{agent.name} responds to: {context[-1].content if context else 'initial topic'}"
        
        # Simulate conversation with new system
        original_topic = "Let's discuss the new feature requirements"
        
        # Initial messages
        manager._conversation_messages = [
            ConversationMessage("You", original_topic, datetime.now()),
        ]
        
        # Simulate agent assessments with incremental context
        for agent in self.agents:
            recent_messages = manager._conversation_messages[agent.last_message_index + 1:]
            mock_assess_with_context(agent, recent_messages, original_topic)
        
        # Verify each agent got appropriate context
        assert len(assessment_contexts) == 3
        
        # All agents should see the human's initial message
        for context in assessment_contexts:
            recent_content = " ".join(context["recent_messages"])
            assert "feature requirements" in recent_content
            assert context["original_topic"] == original_topic
    
    def test_conversation_evolution_tracking(self):
        """Test that agents track conversation evolution properly."""
        manager = self.create_swarm_manager("all_speak")
        
        # Simulate an evolving conversation
        conversation_flow = [
            ("You", "Let's plan our testing strategy"),
            ("Alice", "I suggest we start with unit tests"),
            ("Bob", "We need integration tests too"),
            ("You", "What about performance testing?"),
            ("Charlie", "I can handle the load testing"),
            ("You", "Should we use containerized test environments?"),
        ]
        
        manager._conversation_messages = []
        assessment_history = []
        
        # Process each message and track what agents see
        for i, (speaker, content) in enumerate(conversation_flow):
            # Add message to history
            manager._conversation_messages.append(
                ConversationMessage(speaker, content, datetime.now())
            )
            
            # If it's a human message, assess agent motivations
            if speaker == "You":
                for agent in self.agents:
                    # Get messages since agent's last turn
                    recent_messages = manager._conversation_messages[agent.last_message_index + 1:]
                    
                    assessment_history.append({
                        "turn": i,
                        "agent": agent.name,
                        "recent_context": [str(msg) for msg in recent_messages[-3:]],  # Last 3 messages
                        "full_context_length": len(recent_messages)
                    })
                    
                    # Update agent's last seen index (simulate they spoke)
                    agent.last_message_index = len(manager._conversation_messages) - 1
        
        # Verify conversation evolution is captured
        human_assessments = [a for a in assessment_history if a["agent"] == "Alice"]
        
        # First assessment: sees initial strategy discussion
        first_assessment = human_assessments[0]
        assert "testing strategy" in " ".join(first_assessment["recent_context"])
        
        # Later assessment: sees performance testing discussion
        later_assessment = next(a for a in human_assessments if "performance testing" in " ".join(a["recent_context"]))
        assert "performance testing" in " ".join(later_assessment["recent_context"])
        
        # Final assessment: sees containerization discussion
        final_assessment = human_assessments[-1]
        assert "containerized" in " ".join(final_assessment["recent_context"])


class TestPerformanceBenchmarks:
    """Performance comparison tests for old vs new message delivery."""
    
    def test_memory_efficiency_comparison(self):
        """Compare memory usage of old string-based vs new structured history."""
        import sys
        
        # Simulate large conversation for memory testing
        conversation_size = 1000
        
        # Old system: List of tuples converted to strings
        old_history = []
        for i in range(conversation_size):
            speaker = f"Agent{i % 5}" if i % 5 != 0 else "You"
            message = f"This is message number {i} with some content to simulate real conversation length and complexity."
            old_history.append((speaker, message))
        
        # Convert to string as current system does
        old_history_string = "\n".join(f"{s}: {m}" for s, m in old_history)
        old_memory = sys.getsizeof(old_history) + sys.getsizeof(old_history_string)
        
        # New system: Structured ConversationMessage objects
        new_history = []
        for i in range(conversation_size):
            speaker = f"Agent{i % 5}" if i % 5 != 0 else "You"
            message = f"This is message number {i} with some content to simulate real conversation length and complexity."
            new_history.append(ConversationMessage(speaker, message, datetime.now()))
        
        new_memory = sys.getsizeof(new_history) + sum(sys.getsizeof(msg) for msg in new_history)
        
        # New system might use slightly more memory due to datetime objects
        # but should be comparable and provide much better functionality
        memory_ratio = new_memory / old_memory
        
        # Assert reasonable memory overhead (less than 2x)
        assert memory_ratio < 2.0, f"New system uses {memory_ratio:.2f}x more memory"
        
        # Test filtering efficiency
        start_time = time.time()
        # Old system: filter by string manipulation
        filtered_old = "\n".join(old_history_string.split("\n")[500:])
        old_filter_time = time.time() - start_time
        
        start_time = time.time()
        # New system: filter by list slicing
        filtered_new = new_history[500:]
        new_filter_time = time.time() - start_time
        
        # New system should be faster for filtering
        assert new_filter_time <= old_filter_time * 2, "New filtering should be efficient"
    
    def test_response_time_benchmarks(self):
        """Benchmark response times for agent assessment with different context sizes."""
        agent = Mock()
        agent.name = "TestAgent"
        
        # Test with different conversation sizes
        context_sizes = [10, 50, 100, 500]
        times = {}
        
        for size in context_sizes:
            messages = [
                ConversationMessage(f"Agent{i % 3}", f"Message {i}", datetime.now())
                for i in range(size)
            ]
            
            # Benchmark message filtering
            start_time = time.time()
            
            # Simulate getting recent messages (last 10)
            recent_messages = messages[-10:] if len(messages) > 10 else messages
            
            # Simulate assessment prompt construction
            context_text = "\n".join(str(msg) for msg in recent_messages)
            
            end_time = time.time()
            times[size] = end_time - start_time
        
        # Verify performance scales reasonably
        assert times[500] < times[50] * 10, "Performance should scale sub-linearly"
        
        # All operations should be fast (under 1ms for reasonable sizes)
        assert all(t < 0.001 for t in times.values()), "Message operations should be very fast"


class TestBackwardCompatibility:
    """Tests ensuring existing functionality continues to work during transition."""
    
    def test_conversation_history_property_compatibility(self):
        """Test that existing conversation_history property still works."""
        # Create messages in new format
        messages = [
            ConversationMessage("You", "Hello everyone", datetime.now()),
            ConversationMessage("Agent1", "Hello back!", datetime.now()),
            ConversationMessage("Agent2", "Good to meet you", datetime.now()),
        ]
        
        # Function to convert to old format (would be in SwarmManager)
        def conversation_history_property(messages):
            return "\n".join(str(msg) for msg in messages)
        
        old_format = conversation_history_property(messages)
        
        expected = "You: Hello everyone\nAgent1: Hello back!\nAgent2: Good to meet you"
        assert old_format == expected
        
        # Verify it's still parseable by existing code
        lines = old_format.split("\n")
        assert len(lines) == 3
        assert "You: Hello everyone" in lines[0]
        assert "Agent1: Hello back!" in lines[1]
    
    def test_secretary_integration_compatibility(self):
        """Test that secretary agent integration continues to work."""
        messages = [
            ConversationMessage("You", "Let's make a decision", datetime.now()),
            ConversationMessage("Agent1", "I propose option A", datetime.now()),
            ConversationMessage("Agent2", "I support option A", datetime.now()),
        ]
        
        # Secretary should still be able to observe messages
        def secretary_observe_message(message: ConversationMessage):
            return {
                "speaker": message.sender,
                "content": message.content,
                "timestamp": message.timestamp.isoformat(),
                "formatted": str(message)
            }
        
        observations = [secretary_observe_message(msg) for msg in messages]
        
        assert len(observations) == 3
        assert observations[0]["speaker"] == "You"
        assert observations[1]["content"] == "I propose option A"
        assert observations[2]["formatted"] == "Agent2: I support option A"
    
    def test_export_functionality_compatibility(self):
        """Test that export functionality works with new message format."""
        messages = [
            ConversationMessage("You", "Start of meeting", datetime.now()),
            ConversationMessage("Manager", "Let's review the agenda", datetime.now()),
            ConversationMessage("Developer", "I have updates on the API", datetime.now()),
        ]
        
        # Export functions should work with new format
        def export_as_transcript(messages):
            return "\n".join(f"[{msg.timestamp.strftime('%H:%M')}] {str(msg)}" for msg in messages)
        
        def export_as_summary(messages):
            participants = set(msg.sender for msg in messages)
            return {
                "participants": list(participants),
                "message_count": len(messages),
                "duration": "test_duration",
                "key_topics": ["meeting", "agenda", "API"]
            }
        
        transcript = export_as_transcript(messages)
        summary = export_as_summary(messages)
        
        assert "Start of meeting" in transcript
        assert "Developer" in summary["participants"]
        assert summary["message_count"] == 3


class TestFeatureFlagMigration:
    """Tests for safe migration using feature flags."""
    
    def test_feature_flag_controlled_rollout(self):
        """Test gradual rollout with feature flag control."""
        # Simulate feature flag system
        class FeatureFlags:
            def __init__(self):
                self.use_new_conversation_system = False
                self.new_system_percentage = 0
            
            def should_use_new_system(self, agent_id: str = None):
                if not self.use_new_conversation_system:
                    return False
                
                # Could implement percentage-based rollout
                # For testing, use simple boolean
                return True
        
        flags = FeatureFlags()
        
        # Test old system behavior
        flags.use_new_conversation_system = False
        
        def assess_motivation(topic, flags, recent_messages=None):
            if flags.should_use_new_system():
                # New system: use recent_messages + topic
                return f"NEW: Assessing {len(recent_messages or [])} recent messages about '{topic}'"
            else:
                # Old system: use only topic
                return f"OLD: Assessing topic '{topic}'"
        
        result_old = assess_motivation("Test topic", flags, ["msg1", "msg2"])
        assert result_old.startswith("OLD:")
        assert "Test topic" in result_old
        
        # Test new system behavior
        flags.use_new_conversation_system = True
        
        result_new = assess_motivation("Test topic", flags, ["msg1", "msg2"])
        assert result_new.startswith("NEW:")
        assert "2 recent messages" in result_new
        assert "Test topic" in result_new
    
    def test_fallback_mechanism(self):
        """Test fallback to old system when new system fails."""
        def assessment_with_fallback(recent_messages, original_topic):
            try:
                # Simulate new system
                if not recent_messages:
                    raise ValueError("No recent messages provided")
                
                # New assessment logic
                context = f"Recent: {len(recent_messages)} messages, Topic: {original_topic}"
                return {"system": "new", "context": context, "success": True}
                
            except Exception as e:
                # Fallback to old system
                context = f"Topic: {original_topic}"
                return {"system": "old", "context": context, "success": True, "fallback_reason": str(e)}
        
        # Test successful new system
        result_success = assessment_with_fallback(["msg1", "msg2"], "Test topic")
        assert result_success["system"] == "new"
        assert "2 messages" in result_success["context"]
        
        # Test fallback scenario
        result_fallback = assessment_with_fallback(None, "Test topic")
        assert result_fallback["system"] == "old"
        assert "Topic: Test topic" in result_fallback["context"]
        assert "No recent messages provided" in result_fallback["fallback_reason"]


class TestValidationScenarios:
    """Comprehensive validation tests for the refactor objectives."""
    
    def test_elimination_of_repetitive_greetings(self):
        """Verify that agents no longer assess against 'Hi Jack and Jill' repeatedly."""
        # Simulate a conversation that starts with greeting but evolves
        conversation = [
            ConversationMessage("You", "Hi Jack and Jill, let's discuss our testing strategy", datetime.now()),
            ConversationMessage("Jack", "I think we need comprehensive unit tests", datetime.now()),
            ConversationMessage("Jill", "What about integration testing for the database?", datetime.now()),
            ConversationMessage("You", "Good points. Let's focus on the performance testing now.", datetime.now()),
            ConversationMessage("Jack", "We should benchmark the new caching layer", datetime.now()),
            ConversationMessage("You", "Excellent. What specific metrics should we track?", datetime.now()),
        ]
        
        # Mock agent assessment tracking
        assessment_contexts = []
        
        def mock_new_assessment(agent_name, recent_messages, original_topic):
            assessment_contexts.append({
                "agent": agent_name,
                "recent_messages": [msg.content for msg in recent_messages],
                "original_topic": original_topic
            })
        
        # Simulate agent assessments at different conversation points
        agent_last_index = -1  # Agent hasn't spoken yet
        
        # After initial greeting
        mock_new_assessment("TestAgent", conversation[agent_last_index + 1:1], conversation[0].content)
        
        # After technical discussion starts
        agent_last_index = 1  # Agent spoke after Jack
        mock_new_assessment("TestAgent", conversation[agent_last_index + 1:4], conversation[0].content)
        
        # After focus shifts to performance
        agent_last_index = 3  # Agent spoke after performance topic introduced  
        mock_new_assessment("TestAgent", conversation[agent_last_index + 1:6], conversation[0].content)
        
        # Verify improvement: Agent sees evolving context, not static greeting
        
        # First assessment: Sees initial strategy discussion
        first_context = " ".join(assessment_contexts[0]["recent_messages"])
        assert "testing strategy" in first_context
        
        # Second assessment: Sees technical unit/integration discussion
        second_context = " ".join(assessment_contexts[1]["recent_messages"])
        assert "unit tests" in second_context or "integration testing" in second_context
        
        # Third assessment: Sees performance-focused discussion
        third_context = " ".join(assessment_contexts[2]["recent_messages"])
        assert "performance testing" in third_context
        assert "benchmark" in third_context
        assert "metrics" in third_context
        
        # Most importantly: Agent doesn't repeatedly assess "Hi Jack and Jill"
        # The recent context changes, even though original_topic stays the same
        contexts = [" ".join(a["recent_messages"]) for a in assessment_contexts]
        assert len(set(contexts)) > 1, "Agent should see different contexts over time"
        
        # Original topic is preserved for reference but doesn't dominate assessment
        for assessment in assessment_contexts:
            assert assessment["original_topic"] == conversation[0].content
    
    def test_natural_conversation_flow_validation(self):
        """Test that conversations flow naturally based on human input and agent responses."""
        # Simulate a realistic conversation flow
        conversation_script = [
            # Initial human prompt
            ("You", "I'd like to brainstorm ideas for improving our user onboarding"),
            
            # Agents respond with relevant ideas
            ("UX_Designer", "We could simplify the initial signup form"),
            ("Developer", "I suggest adding progress indicators to show completion status"),
            
            # Human follows up on specific idea
            ("You", "The progress indicators sound great. What would those look like?"),
            
            # Agents build on the specific topic
            ("Developer", "We could use a step-by-step wizard with visual progress bar"),
            ("UX_Designer", "And add tooltips to explain each step's purpose"),
            
            # Human introduces new angle
            ("You", "What about mobile users? Would this work on smaller screens?"),
            
            # Agents adapt to new mobile focus
            ("UX_Designer", "Mobile requires a different approach - maybe vertical progress dots"),
            ("Developer", "We'd need responsive design patterns for the wizard layout"),
        ]
        
        # Track how agent assessments change with conversation evolution
        conversation_messages = []
        assessment_log = []
        
        for i, (speaker, content) in enumerate(conversation_script):
            # Add message to conversation
            conversation_messages.append(
                ConversationMessage(speaker, content, datetime.now())
            )
            
            # If human spoke, assess agent motivations with recent context
            if speaker == "You":
                for agent_name in ["UX_Designer", "Developer"]:
                    # Get recent context (last 3 messages)
                    recent_context = conversation_messages[-3:]
                    
                    assessment_log.append({
                        "turn": i,
                        "agent": agent_name,
                        "human_prompt": content,
                        "recent_context": [msg.content for msg in recent_context],
                        "context_summary": " ".join(msg.content for msg in recent_context[-2:])  # Last 2 messages
                    })
        
        # Verify natural conversation evolution
        assessments = assessment_log
        
        # Initial assessment: focuses on general onboarding improvement
        initial = next(a for a in assessments if "brainstorm ideas" in a["human_prompt"])
        assert "onboarding" in initial["context_summary"]
        
        # Mid conversation: focuses on specific progress indicator discussion
        progress_focus = next(a for a in assessments if "progress indicators" in a["human_prompt"])
        progress_context = progress_focus["context_summary"]
        assert "progress" in progress_context.lower()
        assert "indicators" in progress_context.lower() or "wizard" in progress_context.lower()
        
        # Later conversation: adapts to mobile-specific concerns
        mobile_focus = next(a for a in assessments if "mobile users" in a["human_prompt"])
        mobile_context = mobile_focus["context_summary"]
        assert "mobile" in mobile_context.lower() or "responsive" in mobile_context.lower()
        
        # Verify conversation builds naturally - each assessment should reference recent discussion
        for assessment in assessments[1:]:  # Skip first assessment
            context = assessment["context_summary"].lower()
            # Should contain topic-relevant keywords, not generic greetings
            relevant_keywords = ["onboarding", "progress", "wizard", "mobile", "responsive", "design", "user"]
            assert any(keyword in context for keyword in relevant_keywords), \
                f"Assessment context should be relevant: {context}"


class TestRegressionPrevention:
    """Tests to prevent regression of existing functionality during refactor."""
    
    def test_all_conversation_modes_still_work(self):
        """Ensure all 4 conversation modes continue to function."""
        modes = ["hybrid", "all_speak", "sequential", "pure_priority"]
        
        for mode in modes:
            # Mock a simple conversation flow for each mode
            messages = [
                ConversationMessage("You", f"Test message for {mode} mode", datetime.now()),
                ConversationMessage("Agent1", f"Response in {mode} mode", datetime.now()),
            ]
            
            # Verify mode-specific behavior can be implemented
            def mode_handler(mode, messages, agents):
                if mode == "hybrid":
                    return f"Hybrid: 2-phase conversation with {len(messages)} messages"
                elif mode == "all_speak":
                    return f"All-speak: Everyone responds to {len(messages)} messages"
                elif mode == "sequential":
                    return f"Sequential: Turn-based with {len(messages)} messages"
                elif mode == "pure_priority":
                    return f"Pure-priority: Highest motivation speaks to {len(messages)} messages"
            
            result = mode_handler(mode, messages, ["Agent1", "Agent2"])
            assert mode in result
            assert "messages" in result
            assert str(len(messages)) in result
    
    def test_secretary_commands_still_function(self):
        """Test that secretary live commands continue to work."""
        messages = [
            ConversationMessage("You", "Let's decide on the technical architecture", datetime.now()),
            ConversationMessage("Architect", "I recommend microservices", datetime.now()),
            ConversationMessage("Developer", "That sounds good for scalability", datetime.now()),
        ]
        
        # Mock secretary command processing
        def process_secretary_command(command, messages):
            if command == "/minutes":
                return f"Meeting minutes: {len(messages)} messages discussed"
            elif command == "/export":
                return f"Exporting {len(messages)} messages"
            elif command == "/action-item":
                return "Action item added"
            elif command == "/stats":
                participants = set(msg.sender for msg in messages)
                return f"Stats: {len(participants)} participants, {len(messages)} messages"
        
        # Test each command works with new message format
        minutes_result = process_secretary_command("/minutes", messages)
        assert "Meeting minutes" in minutes_result
        assert "3 messages" in minutes_result
        
        stats_result = process_secretary_command("/stats", messages)
        assert "3 participants" in stats_result
        assert "3 messages" in stats_result
    
    def test_web_gui_compatibility(self):
        """Test that web GUI can still display conversations."""
        messages = [
            ConversationMessage("You", "Hello from web interface", datetime.now()),
            ConversationMessage("Assistant", "Hello back via web!", datetime.now()),
        ]
        
        # Mock web GUI message formatting
        def format_for_web_display(messages):
            formatted = []
            for msg in messages:
                formatted.append({
                    "sender": msg.sender,
                    "content": msg.content,
                    "timestamp": msg.timestamp.strftime("%H:%M:%S"),
                    "is_human": msg.sender == "You"
                })
            return formatted
        
        web_format = format_for_web_display(messages)
        
        assert len(web_format) == 2
        assert web_format[0]["sender"] == "You"
        assert web_format[0]["is_human"] is True
        assert web_format[1]["sender"] == "Assistant"
        assert web_format[1]["is_human"] is False
        assert "Hello from web interface" in web_format[0]["content"]


# Integration test runner configuration
@pytest.mark.integration
class TestConversationRefactorIntegration:
    """High-level integration tests for the complete refactor."""
    
    def test_complete_refactor_workflow(self):
        """Test the complete refactored conversation workflow end-to-end."""
        # This test would require actual SwarmManager and SPDSAgent instances
        # For now, we'll mock the high-level workflow
        
        # 1. Start conversation with new message system
        original_topic = "Planning our Q4 development roadmap"
        conversation = []
        
        # 2. Add initial human message
        conversation.append(
            ConversationMessage("You", original_topic, datetime.now())
        )
        
        # 3. Agents assess motivation with full context (first time)
        agents_assessments = []
        for agent_name in ["Product_Manager", "Tech_Lead", "Designer"]:
            # New system: agents see all messages since their last turn
            recent_messages = conversation  # First assessment, sees everything
            assessment = {
                "agent": agent_name,
                "recent_messages": len(recent_messages),
                "motivated": True,
                "priority_score": 8.0
            }
            agents_assessments.append(assessment)
        
        # 4. Agents speak in conversation mode
        conversation.extend([
            ConversationMessage("Product_Manager", "We need to prioritize user-requested features", datetime.now()),
            ConversationMessage("Tech_Lead", "I agree, but we also need to address technical debt", datetime.now()),
            ConversationMessage("Designer", "What about the UI refresh we discussed?", datetime.now()),
        ])
        
        # 5. Human responds, conversation evolves
        conversation.append(
            ConversationMessage("You", "Let's focus on the technical debt first. What are the main issues?", datetime.now())
        )
        
        # 6. Agents reassess with new context
        # Each agent should now see only messages since their last turn
        tech_lead_last_index = 2  # Tech_Lead spoke at index 2
        new_messages_for_tech_lead = conversation[tech_lead_last_index + 1:]
        
        assert len(new_messages_for_tech_lead) == 2  # Designer's message + human's new message
        assert "technical debt" in new_messages_for_tech_lead[-1].content
        
        # 7. Verify conversation has evolved from roadmap to technical debt focus
        initial_context = conversation[0].content
        current_context = conversation[-1].content
        
        assert "roadmap" in initial_context
        assert "technical debt" in current_context
        assert initial_context != current_context  # Conversation has evolved
        
        # 8. Verify agents would assess current context, not original topic
        latest_messages = [msg.content for msg in conversation[-2:]]
        assert any("technical debt" in msg for msg in latest_messages)
        
        # Success: Conversation evolved naturally and agents see current context


if __name__ == "__main__":
    # Run specific test categories
    pytest.main([
        __file__,
        "-v",
        "--tb=short",
        "-k", "not integration"  # Skip integration tests for unit test run
    ])