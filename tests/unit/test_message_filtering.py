"""
Unit tests for message filtering and delivery logic.

This module tests the new message filtering system that delivers only
new messages to agents since their last turn, eliminating the current
inefficient full conversation history approach.
"""

import time
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

import pytest

# Import ConversationMessage from the actual message module
from spds.message import ConversationMessage


class MockAgent:
    """Mock agent for testing message filtering logic."""
    
    def __init__(self, name: str, last_message_index: int = -1):
        self.name = name
        self.last_message_index = last_message_index
        self.agent_id = f"ag-{name.lower()}-123"


class TestMessageFiltering:
    """Test core message filtering functionality."""
    
    def create_conversation_history(self, length: int = 10) -> list[ConversationMessage]:
        """Create a test conversation history."""
        messages = []
        base_time = datetime(2024, 1, 15, 10, 0, 0)
        
        speakers = ["You", "Agent1", "Agent2", "Agent3"]
        
        for i in range(length):
            speaker = speakers[i % len(speakers)]
            content = f"Message {i+1}: This is {speaker} speaking in the conversation."
            timestamp = base_time + timedelta(seconds=i * 30)  # 30 seconds apart
            
            messages.append(ConversationMessage(speaker, content, timestamp))
        
        return messages
    
    def test_get_new_messages_since_last_turn_basic(self):
        """Test basic message filtering functionality."""
        messages = self.create_conversation_history(8)
        agent = MockAgent("Agent1", last_message_index=3)  # Last spoke at index 3
        
        def get_new_messages_since_last_turn(agent, all_messages):
            if agent.last_message_index < 0:
                return all_messages
            return all_messages[agent.last_message_index + 1:]
        
        new_messages = get_new_messages_since_last_turn(agent, messages)
        
        # Should get messages from index 4 onwards
        assert len(new_messages) == 4  # Messages 4, 5, 6, 7
        assert new_messages[0].content == "Message 5: This is You speaking in the conversation."
        assert new_messages[-1].content == "Message 8: This is Agent3 speaking in the conversation."
    
    def test_first_time_speaker_gets_all_messages(self):
        """Test that agents speaking for the first time get full conversation history."""
        messages = self.create_conversation_history(5)
        new_agent = MockAgent("NewAgent", last_message_index=-1)  # Never spoke before
        
        def get_new_messages_since_last_turn(agent, all_messages):
            if agent.last_message_index < 0:
                return all_messages
            return all_messages[agent.last_message_index + 1:]
        
        new_messages = get_new_messages_since_last_turn(new_agent, messages)
        
        # Should get all messages since it's the first time
        assert len(new_messages) == 5
        assert new_messages[0].content == "Message 1: This is You speaking in the conversation."
        assert new_messages[-1].content == "Message 5: This is You speaking in the conversation."
    
    def test_agent_at_end_of_conversation(self):
        """Test agent that spoke last gets no new messages."""
        messages = self.create_conversation_history(6)
        last_speaker = MockAgent("Agent3", last_message_index=5)  # Last message index
        
        def get_new_messages_since_last_turn(agent, all_messages):
            if agent.last_message_index < 0:
                return all_messages
            return all_messages[agent.last_message_index + 1:]
        
        new_messages = get_new_messages_since_last_turn(last_speaker, messages)
        
        # Should get no new messages
        assert len(new_messages) == 0
    
    def test_agent_with_invalid_index(self):
        """Test handling of invalid last_message_index values."""
        messages = self.create_conversation_history(5)
        
        def get_new_messages_since_last_turn(agent, all_messages):
            if agent.last_message_index < 0:
                return all_messages
            # Handle invalid indices gracefully
            start_index = min(agent.last_message_index + 1, len(all_messages))
            return all_messages[start_index:]
        
        # Test with index beyond conversation length
        future_agent = MockAgent("FutureAgent", last_message_index=10)
        new_messages = get_new_messages_since_last_turn(future_agent, messages)
        assert len(new_messages) == 0
        
        # Test with negative index (other than -1)
        weird_agent = MockAgent("WeirdAgent", last_message_index=-5)
        new_messages = get_new_messages_since_last_turn(weird_agent, messages)
        assert len(new_messages) == 5  # Treats as first-time speaker


class TestMessageIndexTracking:
    """Test agent message index tracking functionality."""
    
    def test_update_agent_last_message_index(self):
        """Test updating agent's last message index after they speak."""
        agent = MockAgent("TestAgent")
        messages = []
        
        def add_message_and_update_agent(speaker, content, messages, agent):
            # Add new message
            new_message = ConversationMessage(speaker, content, datetime.now())
            messages.append(new_message)
            
            # If this agent spoke, update their index
            if speaker == agent.name:
                agent.last_message_index = len(messages) - 1
            
            return len(messages) - 1
        
        # Initial state: agent hasn't spoken
        assert agent.last_message_index == -1
        
        # Add some messages
        add_message_and_update_agent("You", "Hello everyone", messages, agent)
        assert agent.last_message_index == -1  # Agent didn't speak
        
        add_message_and_update_agent("OtherAgent", "Hello back", messages, agent)
        assert agent.last_message_index == -1  # Agent still didn't speak
        
        add_message_and_update_agent("TestAgent", "Hi there!", messages, agent)
        assert agent.last_message_index == 2  # Agent spoke at index 2
        
        add_message_and_update_agent("You", "Great to hear from you", messages, agent)
        assert agent.last_message_index == 2  # Agent's index unchanged
        
        add_message_and_update_agent("TestAgent", "Thanks!", messages, agent)
        assert agent.last_message_index == 4  # Agent spoke again at index 4
    
    def test_multiple_agents_index_tracking(self):
        """Test tracking multiple agents' last message indices."""
        agents = [
            MockAgent("Agent1"),
            MockAgent("Agent2"), 
            MockAgent("Agent3")
        ]
        messages = []
        
        def simulate_conversation_turn(speaker, content, messages, agents):
            # Add message
            new_message = ConversationMessage(speaker, content, datetime.now())
            messages.append(new_message)
            
            # Update relevant agent's index
            for agent in agents:
                if speaker == agent.name:
                    agent.last_message_index = len(messages) - 1
        
        # Simulate conversation
        conversation_script = [
            ("You", "Let's start the discussion"),
            ("Agent1", "I'll go first"),
            ("Agent2", "I'll follow up"),
            ("You", "Good points"),
            ("Agent3", "Let me add something"),
            ("Agent1", "Building on that..."),
            ("You", "Excellent insights")
        ]
        
        for speaker, content in conversation_script:
            simulate_conversation_turn(speaker, content, messages, agents)
        
        # Verify each agent's last message index
        assert agents[0].last_message_index == 5  # Agent1 last spoke at index 5
        assert agents[1].last_message_index == 2  # Agent2 last spoke at index 2  
        assert agents[2].last_message_index == 4  # Agent3 last spoke at index 4
        
        # Test filtered messages for each agent
        def get_new_messages(agent, all_messages):
            if agent.last_message_index < 0:
                return all_messages
            return all_messages[agent.last_message_index + 1:]
        
        # Agent1 should see messages after index 5 (just the last "You" message)
        agent1_new = get_new_messages(agents[0], messages)
        assert len(agent1_new) == 1
        assert agent1_new[0].content == "Excellent insights"
        
        # Agent2 should see messages after index 2 (4 messages)
        agent2_new = get_new_messages(agents[1], messages)
        assert len(agent2_new) == 4
        assert agent2_new[0].content == "Good points"
        assert agent2_new[-1].content == "Excellent insights"


class TestMessageFilteringPerformance:
    """Test performance characteristics of message filtering."""
    
    def create_conversation_history(self, length: int = 10) -> list[ConversationMessage]:
        """Create a test conversation history."""
        messages = []
        base_time = datetime(2024, 1, 15, 10, 0, 0)
        
        speakers = ["You", "Agent1", "Agent2", "Agent3"]
        
        for i in range(length):
            speaker = speakers[i % len(speakers)]
            content = f"Message {i+1}: This is {speaker} speaking in the conversation."
            timestamp = base_time + timedelta(seconds=i * 30)  # 30 seconds apart
            
            messages.append(ConversationMessage(speaker, content, timestamp))
        
        return messages
    
    def test_filtering_performance_large_conversations(self):
        """Test filtering performance with large conversation histories."""
        # Create large conversation
        large_conversation = []
        base_time = datetime.now()
        
        for i in range(10000):  # 10k messages
            speaker = f"Agent{i % 50}" if i % 10 != 0 else "You"
            content = f"Message {i}: Some content here to simulate real message length"
            timestamp = base_time + timedelta(seconds=i)
            large_conversation.append(ConversationMessage(speaker, content, timestamp))
        
        # Test filtering performance
        agent = MockAgent("TestAgent", last_message_index=5000)  # Midway through
        
        start_time = time.time()
        
        def get_new_messages_since_last_turn(agent, all_messages):
            if agent.last_message_index < 0:
                return all_messages
            return all_messages[agent.last_message_index + 1:]
        
        filtered_messages = get_new_messages_since_last_turn(agent, large_conversation)
        
        filtering_time = time.time() - start_time
        
        # Should be very fast (under 10ms for list slicing)
        assert filtering_time < 0.01
        assert len(filtered_messages) == 4999  # Messages from 5001 to 10000
    
    def test_memory_efficiency_of_filtering(self):
        """Test that filtering doesn't create unnecessary memory overhead."""
        import sys
        
        # Create test conversation
        messages = self.create_conversation_history(1000)
        agent = MockAgent("TestAgent", last_message_index=500)
        
        # Measure memory before filtering
        initial_memory = sys.getsizeof(messages)
        
        def get_new_messages_since_last_turn(agent, all_messages):
            if agent.last_message_index < 0:
                return all_messages
            return all_messages[agent.last_message_index + 1:]
        
        # Get filtered messages
        filtered = get_new_messages_since_last_turn(agent, messages)
        
        # Measure memory after filtering
        filtered_memory = sys.getsizeof(filtered)
        
        # Filtered list should be roughly half the size (proportional to content)
        expected_ratio = len(filtered) / len(messages)
        actual_ratio = filtered_memory / initial_memory
        
        # Allow some variance for list overhead
        assert 0.4 <= actual_ratio <= 0.6  # Should be around 50%
        assert len(filtered) == 499  # Messages 501-999


class TestMessageFilteringEdgeCases:
    """Test edge cases and error conditions in message filtering."""
    
    def test_empty_conversation_history(self):
        """Test filtering with empty conversation history."""
        empty_messages = []
        agent = MockAgent("TestAgent", last_message_index=-1)
        
        def get_new_messages_since_last_turn(agent, all_messages):
            if agent.last_message_index < 0:
                return all_messages
            return all_messages[agent.last_message_index + 1:]
        
        filtered = get_new_messages_since_last_turn(agent, empty_messages)
        assert len(filtered) == 0
        assert filtered == []
    
    def test_single_message_conversation(self):
        """Test filtering with single message conversation."""
        single_message = [ConversationMessage("You", "Hello", datetime.now())]
        
        # First-time agent should get the message
        new_agent = MockAgent("NewAgent", last_message_index=-1)
        
        def get_new_messages_since_last_turn(agent, all_messages):
            if agent.last_message_index < 0:
                return all_messages
            return all_messages[agent.last_message_index + 1:]
        
        filtered = get_new_messages_since_last_turn(new_agent, single_message)
        assert len(filtered) == 1
        assert filtered[0].content == "Hello"
        
        # Agent who spoke last should get no messages
        last_speaker = MockAgent("LastSpeaker", last_message_index=0)
        filtered = get_new_messages_since_last_turn(last_speaker, single_message)
        assert len(filtered) == 0
    
    def test_agent_index_consistency(self):
        """Test that agent indices remain consistent across conversation growth."""
        messages = []
        agent = MockAgent("TestAgent")
        
        # Helper to add message and track agent
        def add_message_and_track(speaker, content):
            new_msg = ConversationMessage(speaker, content, datetime.now())
            messages.append(new_msg)
            
            if speaker == agent.name:
                agent.last_message_index = len(messages) - 1
                
            return len(messages) - 1
        
        # Build conversation step by step
        add_message_and_track("You", "Start")  # Index 0
        add_message_and_track("OtherAgent", "Response 1")  # Index 1
        agent_first_msg_idx = add_message_and_track("TestAgent", "My first message")  # Index 2
        
        assert agent.last_message_index == 2
        
        # Add more messages
        add_message_and_track("You", "Follow up")  # Index 3
        add_message_and_track("OtherAgent", "Another response")  # Index 4
        
        # Agent index should be unchanged
        assert agent.last_message_index == 2
        
        # Agent speaks again
        agent_second_msg_idx = add_message_and_track("TestAgent", "My second message")  # Index 5
        assert agent.last_message_index == 5
        
        # Verify filtering works correctly
        def get_new_messages_since_last_turn(agent, all_messages):
            if agent.last_message_index < 0:
                return all_messages
            return all_messages[agent.last_message_index + 1:]
        
        filtered = get_new_messages_since_last_turn(agent, messages)
        assert len(filtered) == 0  # No messages after agent's last message
    
    def test_conversation_with_only_human_messages(self):
        """Test filtering in conversation with only human messages."""
        human_only_messages = [
            ConversationMessage("You", "First human message", datetime.now()),
            ConversationMessage("You", "Second human message", datetime.now()),
            ConversationMessage("You", "Third human message", datetime.now()),
        ]
        
        agent = MockAgent("TestAgent", last_message_index=-1)  # Never spoke
        
        def get_new_messages_since_last_turn(agent, all_messages):
            if agent.last_message_index < 0:
                return all_messages
            return all_messages[agent.last_message_index + 1:]
        
        filtered = get_new_messages_since_last_turn(agent, human_only_messages)
        
        # Should get all messages since agent never spoke
        assert len(filtered) == 3
        assert all(msg.sender == "You" for msg in filtered)
    
    def test_rapid_message_sequence(self):
        """Test filtering with rapid message sequences and quick updates."""
        messages = []
        agents = [MockAgent(f"Agent{i}") for i in range(3)]
        
        # Simulate rapid conversation
        rapid_sequence = [
            ("You", "Quick question"),
            ("Agent0", "Quick answer 1"),
            ("Agent1", "Quick answer 2"), 
            ("Agent2", "Quick answer 3"),
            ("You", "Follow up"),
            ("Agent0", "Response 1"),
            ("Agent1", "Response 2"),
        ]
        
        # Process each message
        for speaker, content in rapid_sequence:
            new_msg = ConversationMessage(speaker, content, datetime.now())
            messages.append(new_msg)
            
            # Update speaker's index
            for agent in agents:
                if speaker == agent.name:
                    agent.last_message_index = len(messages) - 1
        
        # Verify each agent's filtering
        def get_new_messages_since_last_turn(agent, all_messages):
            if agent.last_message_index < 0:
                return all_messages
            return all_messages[agent.last_message_index + 1:]
        
        # Agent0 last spoke at index 5 ("Response 1")
        agent0_filtered = get_new_messages_since_last_turn(agents[0], messages)
        assert len(agent0_filtered) == 1
        assert agent0_filtered[0].content == "Response 2"
        
        # Agent1 last spoke at index 6 ("Response 2")
        agent1_filtered = get_new_messages_since_last_turn(agents[1], messages)
        assert len(agent1_filtered) == 0  # No messages after
        
        # Agent2 last spoke at index 3 ("Quick answer 3")
        agent2_filtered = get_new_messages_since_last_turn(agents[2], messages)
        assert len(agent2_filtered) == 3  # Messages 4, 5, 6
        assert agent2_filtered[0].content == "Follow up"
        assert agent2_filtered[-1].content == "Response 2"


class TestMessageFilteringIntegration:
    """Test integration of message filtering with other system components."""
    
    def test_swarm_manager_integration_pattern(self):
        """Test the expected integration pattern with SwarmManager."""
        # Simulate SwarmManager-like behavior
        class MockSwarmManager:
            def __init__(self):
                self.agents = [MockAgent(f"Agent{i}") for i in range(3)]
                self.conversation_messages = []  # New structured history
                self._history = []  # Legacy history for compatibility
            
            def add_message(self, speaker: str, content: str):
                """Add message to both new and legacy formats."""
                # New format
                new_msg = ConversationMessage(speaker, content, datetime.now())
                self.conversation_messages.append(new_msg)
                
                # Legacy format (for backward compatibility)
                self._history.append((speaker, content))
                
                # Update agent indices
                for agent in self.agents:
                    if speaker == agent.name:
                        agent.last_message_index = len(self.conversation_messages) - 1
            
            def get_new_messages_for_agent(self, agent):
                """Get new messages since agent's last turn."""
                if agent.last_message_index < 0:
                    return self.conversation_messages
                return self.conversation_messages[agent.last_message_index + 1:]
            
            def get_legacy_conversation_history(self):
                """Backward compatible conversation history."""
                return "\n".join(f"{s}: {c}" for s, c in self._history)
        
        # Test the integration
        manager = MockSwarmManager()
        
        # Simulate conversation
        manager.add_message("You", "Let's discuss the project")
        manager.add_message("Agent0", "I have some thoughts")
        manager.add_message("Agent1", "I agree with Agent0")
        manager.add_message("You", "What specific thoughts?")
        manager.add_message("Agent0", "Well, regarding the architecture...")
        
        # Test new message filtering
        agent0_new = manager.get_new_messages_for_agent(manager.agents[0])
        assert len(agent0_new) == 0  # Agent0 spoke last
        
        agent1_new = manager.get_new_messages_for_agent(manager.agents[1])
        assert len(agent1_new) == 2  # Should see last 2 messages
        assert agent1_new[0].content == "What specific thoughts?"
        assert agent1_new[1].content == "Well, regarding the architecture..."
        
        # Test backward compatibility
        legacy_history = manager.get_legacy_conversation_history()
        expected_legacy = (
            "You: Let's discuss the project\n"
            "Agent0: I have some thoughts\n"
            "Agent1: I agree with Agent0\n"
            "You: What specific thoughts?\n"
            "Agent0: Well, regarding the architecture..."
        )
        assert legacy_history == expected_legacy
    
    def test_agent_assessment_integration(self):
        """Test integration with agent assessment workflow."""
        messages = [
            ConversationMessage("You", "Let's plan our testing strategy", datetime.now()),
            ConversationMessage("QAAgent", "I suggest comprehensive unit tests", datetime.now()),
            ConversationMessage("DevAgent", "We also need integration tests", datetime.now()),
            ConversationMessage("You", "What about performance testing?", datetime.now()),
            ConversationMessage("QAAgent", "Load testing is crucial", datetime.now()),
        ]
        
        qa_agent = MockAgent("QAAgent", last_message_index=4)  # Last spoke at index 4
        dev_agent = MockAgent("DevAgent", last_message_index=2)  # Last spoke at index 2
        
        def assess_motivation_with_context(agent, all_messages, original_topic):
            """Mock assessment function using filtered messages."""
            if agent.last_message_index < 0:
                recent_messages = all_messages
            else:
                recent_messages = all_messages[agent.last_message_index + 1:]
            
            # Assessment based on recent context vs original topic
            recent_content = " ".join(msg.content for msg in recent_messages)
            
            return {
                "agent": agent.name,
                "recent_messages_count": len(recent_messages),
                "recent_content_keywords": recent_content.lower().split(),
                "sees_performance_topic": "performance" in recent_content.lower(),
                "original_topic": original_topic
            }
        
        original_topic = "Let's plan our testing strategy"
        
        # Assess both agents
        qa_assessment = assess_motivation_with_context(qa_agent, messages, original_topic)
        dev_assessment = assess_motivation_with_context(dev_agent, messages, original_topic)
        
        # QA Agent: Last spoke at index 4, should see no new messages
        assert qa_assessment["recent_messages_count"] == 0
        assert not qa_assessment["sees_performance_topic"]
        
        # Dev Agent: Last spoke at index 2, should see messages 3-4
        assert dev_assessment["recent_messages_count"] == 2
        assert dev_assessment["sees_performance_topic"]  # Should see "performance testing"
        
        # Both agents have access to original topic for context
        assert qa_assessment["original_topic"] == original_topic
        assert dev_assessment["original_topic"] == original_topic
    
    def test_secretary_observation_integration(self):
        """Test integration with secretary agent observation."""
        messages = [
            ConversationMessage("You", "Let's make a decision about the database", datetime.now()),
            ConversationMessage("Architect", "I recommend PostgreSQL", datetime.now()),
            ConversationMessage("Developer", "That works well with our stack", datetime.now()),
        ]
        
        def secretary_observe_conversation(messages, last_observed_index=-1):
            """Mock secretary observation of new messages."""
            if last_observed_index < 0:
                new_messages = messages
            else:
                new_messages = messages[last_observed_index + 1:]
            
            observations = []
            for msg in new_messages:
                observations.append({
                    "speaker": msg.sender,
                    "content": msg.content,
                    "timestamp": msg.timestamp.isoformat(),
                    "is_decision_related": "decision" in msg.content.lower() or "recommend" in msg.content.lower()
                })
            
            return observations
        
        # Secretary observes all messages initially
        initial_observations = secretary_observe_conversation(messages)
        assert len(initial_observations) == 3
        assert initial_observations[0]["is_decision_related"] is True  # "decision about database"
        assert initial_observations[1]["is_decision_related"] is True  # "recommend PostgreSQL"
        
        # Add more messages
        messages.extend([
            ConversationMessage("You", "Any concerns with PostgreSQL?", datetime.now()),
            ConversationMessage("Security", "We need to ensure proper encryption", datetime.now()),
        ])
        
        # Secretary observes only new messages
        new_observations = secretary_observe_conversation(messages, last_observed_index=2)
        assert len(new_observations) == 2
        assert new_observations[0]["content"] == "Any concerns with PostgreSQL?"
        assert new_observations[1]["speaker"] == "Security"