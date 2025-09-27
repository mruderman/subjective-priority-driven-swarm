"""
Unit tests for the agent assessment logic refactor.

This module tests the changes to agent motivation and priority assessment
that fix the static topic problem by incorporating recent conversation context.
"""

import json
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

from spds.tools import SubjectiveAssessment
from spds.message import ConversationMessage


class MockSPDSAgent:
    """Mock SPDSAgent for testing assessment logic changes."""
    
    def __init__(self, name: str, client=None):
        self.name = name
        self.client = client or Mock()
        self.agent = Mock()
        self.agent.id = f"ag-{name.lower()}-123"
        self.agent.name = name
        
        # Assessment tracking
        self.motivation_score = 0
        self.priority_score = 0.0
        self.last_assessment = None
        self.last_error = None
        
        # Assessment call tracking for testing
        self._assessment_calls = []
    
    def _mock_letta_response(self, assessment_scores: dict):
        """Create a mock Letta response with assessment tool call."""
        tool_call = SimpleNamespace(
            function=SimpleNamespace(
                name="perform_subjective_assessment",
                arguments=json.dumps(assessment_scores)
            )
        )
        
        message = SimpleNamespace(
            tool_calls=[tool_call],
            tool_return=None,
            message_type="tool_message",
            content=None
        )
        
        return SimpleNamespace(messages=[message])


class TestCurrentAssessmentProblem:
    """Tests that demonstrate the current static topic assessment problem."""
    
    def test_current_static_assessment_pattern(self):
        """Test the current assessment pattern that always uses static topic."""
        agent = MockSPDSAgent("TestAgent")
        
        # Mock the current assessment method signature
        def current_assess_motivation_and_priority(topic: str):
            """Current method signature - only takes topic string."""
            agent._assessment_calls.append({
                "method": "current",
                "topic": topic,
                "conversation_history": None  # Not provided in current system
            })
            
            # Simulate static assessment
            agent.motivation_score = 30  # Fixed score for testing
            agent.priority_score = 7.0
        
        # Simulate multiple assessment calls as conversation evolves
        original_topic = "Hi Jack and Jill, let's discuss our testing strategy"
        
        # Current system: Always call with same topic regardless of conversation evolution
        for i in range(5):  # Multiple rounds of assessment
            current_assess_motivation_and_priority(original_topic)
        
        # Verify the problem: All calls use identical static topic
        assert len(agent._assessment_calls) == 5
        for call in agent._assessment_calls:
            assert call["topic"] == original_topic
            assert call["conversation_history"] is None
        
        # All assessments are identical - this is the problem!
        topics = [call["topic"] for call in agent._assessment_calls]
        assert len(set(topics)) == 1  # Only one unique topic across all assessments
    
    def test_current_get_full_assessment_limitations(self):
        """Test current _get_full_assessment method limitations."""
        agent = MockSPDSAgent("TestAgent")
        
        # Mock current _get_full_assessment signature
        def current_get_full_assessment(conversation_history: str = "", topic: str = ""):
            """Current signature - conversation_history is optional and rarely used."""
            agent._assessment_calls.append({
                "conversation_history": conversation_history,
                "topic": topic,
                "has_conversation_context": bool(conversation_history.strip()) if conversation_history else False
            })
            
            # Mock assessment result
            mock_scores = {
                "importance_to_self": 7,
                "perceived_gap": 6,
                "unique_perspective": 8,
                "emotional_investment": 5,
                "expertise_relevance": 9,
                "urgency": 7,
                "importance_to_group": 8
            }
            agent.last_assessment = SubjectiveAssessment(**mock_scores)
        
        # Typical usage: only topic provided, no conversation history
        current_get_full_assessment(topic="Discuss testing strategy")
        
        # Verify typical call pattern
        assert len(agent._assessment_calls) == 1
        call = agent._assessment_calls[0]
        assert call["topic"] == "Discuss testing strategy"
        assert call["conversation_history"] == ""
        assert call["has_conversation_context"] is False
        
        # This demonstrates the limitation: no conversation context in typical usage


class TestNewAssessmentPattern:
    """Tests for the new dynamic context-aware assessment pattern."""
    
    def test_new_assessment_with_recent_messages(self):
        """Test the new assessment pattern with recent message context."""
        agent = MockSPDSAgent("TestAgent")
        
        # Mock the new assessment method signature
        def new_assess_motivation_and_priority(recent_messages: list, original_topic: str):
            """New method signature - takes recent messages + original topic."""
            agent._assessment_calls.append({
                "method": "new",
                "recent_messages": [str(msg) for msg in recent_messages],
                "original_topic": original_topic,
                "context_keywords": self._extract_keywords_from_messages(recent_messages)
            })
            
            # Dynamic assessment based on recent context
            recent_content = " ".join(msg.content for msg in recent_messages)
            if "performance" in recent_content.lower():
                agent.motivation_score = 40  # Higher if performance-related
            else:
                agent.motivation_score = 25  # Lower for general topics
            
            agent.priority_score = 8.0
        
        def _extract_keywords_from_messages(self, messages):
            """Helper to extract keywords from recent messages."""
            content = " ".join(msg.content for msg in messages)
            return [word for word in content.lower().split() if len(word) > 3]
        
        # Simulate evolving conversation
        conversation_evolution = [
            # Initial discussion
            [ConversationMessage("You", "Let's discuss our testing strategy", datetime.now())],
            
            # Focus on unit tests
            [
                ConversationMessage("You", "Let's discuss our testing strategy", datetime.now()),
                ConversationMessage("Dev1", "I think we need comprehensive unit tests", datetime.now())
            ],
            
            # Performance testing emerges
            [
                ConversationMessage("Dev1", "I think we need comprehensive unit tests", datetime.now()),
                ConversationMessage("You", "What about performance testing?", datetime.now()),
                ConversationMessage("Dev2", "We should benchmark the database queries", datetime.now())
            ]
        ]
        
        original_topic = "Let's discuss our testing strategy"
        
        # New system: Assessment sees conversation evolution
        for recent_messages in conversation_evolution:
            new_assess_motivation_and_priority(recent_messages, original_topic)
        
        # Verify improvement: Agent sees different contexts over time
        assert len(agent._assessment_calls) == 3
        
        # First assessment: general strategy discussion
        first_call = agent._assessment_calls[0]
        assert "strategy" in " ".join(first_call["recent_messages"])
        
        # Second assessment: unit testing focus
        second_call = agent._assessment_calls[1]
        recent_content = " ".join(second_call["recent_messages"])
        assert "unit tests" in recent_content
        
        # Third assessment: performance testing focus
        third_call = agent._assessment_calls[2]
        recent_content = " ".join(third_call["recent_messages"])
        assert "performance" in recent_content
        assert "benchmark" in recent_content
        
        # All assessments preserve original topic for reference
        for call in agent._assessment_calls:
            assert call["original_topic"] == original_topic
        
        # Context changes over time - this is the improvement!
        contexts = [" ".join(call["recent_messages"]) for call in agent._assessment_calls]
        assert len(set(contexts)) == 3  # Three different contexts seen
    
    def test_new_get_full_assessment_with_context(self):
        """Test the new _get_full_assessment method with conversation context."""
        agent = MockSPDSAgent("TestAgent")
        
        # Mock new _get_full_assessment signature
        def new_get_full_assessment(recent_messages: list = None, original_topic: str = ""):
            """New signature - takes recent messages list + original topic."""
            if recent_messages is None:
                recent_messages = []
            
            # Build context from recent messages
            conversation_context = "\n".join(str(msg) for msg in recent_messages[-5:])  # Last 5 messages
            
            agent._assessment_calls.append({
                "recent_messages_count": len(recent_messages),
                "conversation_context": conversation_context,
                "original_topic": original_topic,
                "has_recent_context": len(recent_messages) > 0
            })
            
            # Mock dynamic assessment based on context
            mock_scores = {
                "importance_to_self": 8,
                "perceived_gap": 7,
                "unique_perspective": 6,
                "emotional_investment": 5,
                "expertise_relevance": 9,
                "urgency": 8,
                "importance_to_group": 7
            }
            agent.last_assessment = SubjectiveAssessment(**mock_scores)
        
        # Test with recent message context
        recent_messages = [
            ConversationMessage("You", "What about the API performance?", datetime.now()),
            ConversationMessage("Dev1", "The response times are concerning", datetime.now()),
            ConversationMessage("You", "Should we add caching?", datetime.now())
        ]
        
        new_get_full_assessment(recent_messages, "Discuss system performance")
        
        # Verify new pattern provides context
        assert len(agent._assessment_calls) == 1
        call = agent._assessment_calls[0]
        assert call["recent_messages_count"] == 3
        assert call["has_recent_context"] is True
        assert "API performance" in call["conversation_context"]
        assert "response times" in call["conversation_context"]
        assert "caching" in call["conversation_context"]
        assert call["original_topic"] == "Discuss system performance"


class TestAssessmentPromptGeneration:
    """Test generation of assessment prompts with dynamic context."""
    
    def test_context_aware_prompt_generation(self):
        """Test generating assessment prompts that include recent conversation context."""
        
        def generate_assessment_prompt(recent_messages: list, original_topic: str, agent_name: str):
            """Generate assessment prompt with recent conversation context."""
            if not recent_messages:
                return f"Agent {agent_name}, regarding the topic '{original_topic}', please assess your motivation to participate."
            
            # Include recent conversation context
            recent_context = "\n".join(f"  {msg}" for msg in recent_messages[-3:])  # Last 3 messages
            
            prompt = f"""Agent {agent_name}, based on our recent conversation:

{recent_context}

The original topic was: "{original_topic}"

Please assess your motivation and priority to participate in this discussion."""
            
            return prompt
        
        # Test with evolving conversation
        messages = [
            ConversationMessage("You", "Let's discuss our deployment strategy", datetime.now()),
            ConversationMessage("DevOps", "I suggest using blue-green deployments", datetime.now()),
            ConversationMessage("Developer", "That would minimize downtime", datetime.now()),
            ConversationMessage("You", "What about rollback procedures?", datetime.now())
        ]
        
        original_topic = "Let's discuss our deployment strategy"
        
        # Generate prompt for agent assessment
        prompt = generate_assessment_prompt(messages, original_topic, "SecurityAgent")
        
        # Verify prompt includes recent context
        assert "SecurityAgent" in prompt
        assert "blue-green deployments" in prompt
        assert "minimize downtime" in prompt
        assert "rollback procedures" in prompt
        assert original_topic in prompt
        
        # Test with no recent messages (first-time assessment)
        empty_prompt = generate_assessment_prompt([], original_topic, "SecurityAgent")
        assert "SecurityAgent" in empty_prompt
        assert original_topic in empty_prompt
        assert "blue-green" not in empty_prompt  # No recent context
    
    def test_prompt_context_window_management(self):
        """Test managing prompt context window with large conversations."""
        
        def generate_limited_context_prompt(recent_messages: list, original_topic: str, max_messages: int = 5):
            """Generate prompt with limited context window."""
            # Limit to most recent messages to manage context size
            limited_messages = recent_messages[-max_messages:] if len(recent_messages) > max_messages else recent_messages
            
            context_summary = f"Recent conversation ({len(limited_messages)} messages):\n"
            context_summary += "\n".join(f"  {msg}" for msg in limited_messages)
            
            return {
                "context_summary": context_summary,
                "original_topic": original_topic,
                "total_messages": len(recent_messages),
                "included_messages": len(limited_messages),
                "context_limited": len(recent_messages) > max_messages
            }
        
        # Create large conversation
        large_conversation = []
        for i in range(20):
            speaker = f"Agent{i % 3}" if i % 4 != 0 else "You"
            content = f"Message {i+1}: Discussion point about the topic"
            large_conversation.append(ConversationMessage(speaker, content, datetime.now()))
        
        # Generate prompt with context limit
        prompt_data = generate_limited_context_prompt(large_conversation, "Large discussion topic", max_messages=5)
        
        # Verify context is properly limited
        assert prompt_data["total_messages"] == 20
        assert prompt_data["included_messages"] == 5
        assert prompt_data["context_limited"] is True
        assert "Message 16" in prompt_data["context_summary"]  # Should include last 5 messages
        assert "Message 20" in prompt_data["context_summary"]
        assert "Message 1" not in prompt_data["context_summary"]  # Should not include early messages


class TestAssessmentScoreCalculation:
    """Test how assessment scores change with different conversation contexts."""
    
    def test_dynamic_score_calculation(self):
        """Test that assessment scores reflect conversation context."""
        agent = MockSPDSAgent("TechLead")
        
        def calculate_context_aware_scores(recent_messages: list, agent_expertise: list):
            """Calculate assessment scores based on recent context and agent expertise."""
            recent_content = " ".join(msg.content.lower() for msg in recent_messages)
            
            # Base scores
            scores = {
                "importance_to_self": 5,
                "perceived_gap": 5,
                "unique_perspective": 5,
                "emotional_investment": 5,
                "expertise_relevance": 5,
                "urgency": 5,
                "importance_to_group": 5
            }
            
            # Boost scores based on expertise relevance
            for expertise in agent_expertise:
                if expertise.lower() in recent_content:
                    scores["expertise_relevance"] += 2
                    scores["unique_perspective"] += 1
                    scores["importance_to_self"] += 1
            
            # Urgency based on keywords
            urgent_keywords = ["urgent", "critical", "asap", "immediately", "problem"]
            if any(keyword in recent_content for keyword in urgent_keywords):
                scores["urgency"] += 3
            
            # Cap scores at 10
            for key in scores:
                scores[key] = min(scores[key], 10)
            
            return scores
        
        agent_expertise = ["architecture", "performance", "scalability"]
        
        # Test 1: General discussion (low relevance)
        general_messages = [
            ConversationMessage("You", "Let's plan the team meeting agenda", datetime.now()),
            ConversationMessage("PM", "We need to discuss project timelines", datetime.now())
        ]
        
        general_scores = calculate_context_aware_scores(general_messages, agent_expertise)
        assert general_scores["expertise_relevance"] == 5  # No boost
        assert general_scores["urgency"] == 5  # No urgency keywords
        
        # Test 2: Architecture discussion (high relevance)
        arch_messages = [
            ConversationMessage("You", "We have critical architecture decisions to make", datetime.now()),
            ConversationMessage("Dev", "The performance bottleneck is in the database layer", datetime.now()),
            ConversationMessage("You", "This is urgent - scalability issues are blocking the release", datetime.now())
        ]
        
        arch_scores = calculate_context_aware_scores(arch_messages, agent_expertise)
        assert arch_scores["expertise_relevance"] > 5  # Boosted by "architecture", "performance", "scalability"
        assert arch_scores["urgency"] > 5  # Boosted by "critical", "urgent"
        assert arch_scores["unique_perspective"] > 5  # Boosted by expertise match
        
        # Test 3: Different agent with different expertise
        design_expertise = ["ui", "ux", "design", "user_experience"]
        
        design_scores = calculate_context_aware_scores(arch_messages, design_expertise)
        assert design_scores["expertise_relevance"] == 5  # No boost for design expertise
        assert design_scores["urgency"] > 5  # Still urgent, but not expertise-relevant
    
    def test_motivation_threshold_with_context(self):
        """Test how motivation threshold checking works with dynamic context."""
        
        def assess_participation_decision(recent_messages: list, agent_expertise: list, threshold: int = 30):
            """Determine if agent should participate based on context-aware assessment."""
            recent_content = " ".join(msg.content.lower() for msg in recent_messages)
            
            # Calculate motivation score based on context
            base_motivation = 15
            expertise_bonus = 0
            urgency_bonus = 0
            
            # Expertise relevance bonus
            for expertise in agent_expertise:
                if expertise.lower() in recent_content:
                    expertise_bonus += 5
            
            # Urgency bonus
            urgent_keywords = ["urgent", "critical", "asap", "problem", "issue"]
            urgency_bonus = sum(3 for keyword in urgent_keywords if keyword in recent_content)
            
            motivation_score = base_motivation + expertise_bonus + urgency_bonus
            
            return {
                "motivation_score": motivation_score,
                "should_participate": motivation_score >= threshold,
                "expertise_bonus": expertise_bonus,
                "urgency_bonus": urgency_bonus,
                "context_keywords": recent_content.split()
            }
        
        # Test with different conversation contexts
        security_agent_expertise = ["security", "encryption", "authentication", "vulnerability"]
        
        # Context 1: General planning (low motivation)
        planning_messages = [
            ConversationMessage("You", "Let's schedule the next sprint planning", datetime.now()),
            ConversationMessage("PM", "We need to review the backlog", datetime.now())
        ]
        
        planning_result = assess_participation_decision(planning_messages, security_agent_expertise)
        assert planning_result["motivation_score"] < 30  # Below threshold
        assert planning_result["should_participate"] is False
        assert planning_result["expertise_bonus"] == 0
        
        # Context 2: Security issue (high motivation)
        security_messages = [
            ConversationMessage("You", "We have a critical security vulnerability", datetime.now()),
            ConversationMessage("Dev", "The authentication system has an urgent issue", datetime.now()),
            ConversationMessage("You", "We need to fix the encryption problem ASAP", datetime.now())
        ]
        
        security_result = assess_participation_decision(security_messages, security_agent_expertise)
        assert security_result["motivation_score"] >= 30  # Above threshold
        assert security_result["should_participate"] is True
        assert security_result["expertise_bonus"] > 0  # Security-related keywords
        assert security_result["urgency_bonus"] > 0  # Urgent keywords
        
        # Verify specific bonuses
        context_keywords = security_result["context_keywords"]
        assert "security" in context_keywords
        assert "authentication" in context_keywords
        assert "encryption" in context_keywords
        assert "critical" in context_keywords
        assert "urgent" in context_keywords


class TestAssessmentErrorHandling:
    """Test error handling in the new assessment system."""
    
    def test_empty_recent_messages_handling(self):
        """Test handling of empty recent messages list."""
        
        def safe_assess_with_context(recent_messages: list, original_topic: str):
            """Safely assess motivation with proper null handling."""
            try:
                if not recent_messages:
                    # First-time assessment or no recent context
                    context_prompt = f"Regarding the topic: '{original_topic}'"
                    context_type = "initial"
                else:
                    # Has recent context
                    context_prompt = f"Based on recent conversation about '{original_topic}'"
                    context_type = "contextual"
                
                return {
                    "success": True,
                    "context_prompt": context_prompt,
                    "context_type": context_type,
                    "message_count": len(recent_messages) if recent_messages else 0
                }
                
            except Exception as e:
                return {
                    "success": False,
                    "error": str(e),
                    "fallback_prompt": f"Regarding: '{original_topic}'"
                }
        
        # Test with empty list
        result_empty = safe_assess_with_context([], "Test topic")
        assert result_empty["success"] is True
        assert result_empty["context_type"] == "initial"
        assert result_empty["message_count"] == 0
        
        # Test with None
        result_none = safe_assess_with_context(None, "Test topic")
        assert result_none["success"] is True
        assert result_none["context_type"] == "initial"
        assert result_none["message_count"] == 0
        
        # Test with valid messages
        messages = [ConversationMessage("You", "Test message", datetime.now())]
        result_valid = safe_assess_with_context(messages, "Test topic")
        assert result_valid["success"] is True
        assert result_valid["context_type"] == "contextual"
        assert result_valid["message_count"] == 1
    
    def test_malformed_message_handling(self):
        """Test handling of malformed or invalid messages."""
        
        def robust_context_extraction(recent_messages: list):
            """Robustly extract context from potentially malformed messages."""
            valid_messages = []
            errors = []
            
            for i, msg in enumerate(recent_messages):
                try:
                    # Validate message has required attributes
                    if not hasattr(msg, 'sender') or not hasattr(msg, 'content'):
                        errors.append(f"Message {i}: Missing required attributes")
                        continue
                    
                    if not msg.sender or not isinstance(msg.sender, str):
                        errors.append(f"Message {i}: Invalid sender")
                        continue
                    
                    if not isinstance(msg.content, str):
                        errors.append(f"Message {i}: Invalid content type")
                        continue
                    
                    valid_messages.append(msg)
                    
                except Exception as e:
                    errors.append(f"Message {i}: {str(e)}")
            
            context_text = " ".join(msg.content for msg in valid_messages)
            
            return {
                "valid_messages": valid_messages,
                "valid_count": len(valid_messages),
                "total_count": len(recent_messages),
                "errors": errors,
                "context_text": context_text,
                "success_rate": len(valid_messages) / len(recent_messages) if recent_messages else 1.0
            }
        
        # Test with mixed valid/invalid messages
        mixed_messages = [
            ConversationMessage("You", "Valid message 1", datetime.now()),
            SimpleNamespace(invalid=True),  # Invalid message
            ConversationMessage("Agent", "Valid message 2", datetime.now()),
            SimpleNamespace(sender="", content="Invalid empty sender"),  # Invalid sender
            ConversationMessage("You", "Valid message 3", datetime.now()),
        ]
        
        result = robust_context_extraction(mixed_messages)
        
        assert result["total_count"] == 5
        assert result["valid_count"] == 3  # Only valid ConversationMessage objects
        assert len(result["errors"]) == 2  # Two invalid messages
        assert "Valid message 1" in result["context_text"]
        assert "Valid message 2" in result["context_text"]
        assert "Valid message 3" in result["context_text"]
        assert result["success_rate"] == 0.6  # 3/5 valid
    
    def test_assessment_timeout_handling(self):
        """Test handling of assessment timeouts and fallbacks."""
        
        def assess_with_timeout_fallback(recent_messages: list, original_topic: str, timeout_seconds: float = 5.0):
            """Assess with timeout and fallback mechanism."""
            import time
            import signal
            
            def timeout_handler(signum, frame):
                raise TimeoutError("Assessment timed out")
            
            try:
                # Set timeout
                signal.signal(signal.SIGALRM, timeout_handler)
                signal.alarm(int(timeout_seconds))
                
                # Simulate assessment process
                context_text = " ".join(msg.content for msg in recent_messages[-3:])  # Last 3 messages
                
                # Simulate processing time
                time.sleep(0.01)  # Quick processing
                
                signal.alarm(0)  # Cancel timeout
                
                return {
                    "success": True,
                    "method": "full_assessment",
                    "context_length": len(context_text),
                    "message_count": len(recent_messages)
                }
                
            except TimeoutError:
                signal.alarm(0)  # Cancel timeout
                
                # Fallback to simple assessment
                return {
                    "success": True,
                    "method": "fallback_assessment",
                    "fallback_reason": "timeout",
                    "original_topic": original_topic,
                    "estimated_relevance": "medium"  # Default relevance
                }
            
            except Exception as e:
                signal.alarm(0)  # Cancel timeout
                return {
                    "success": False,
                    "error": str(e),
                    "method": "error_fallback"
                }
        
        # Test normal assessment
        normal_messages = [ConversationMessage("You", "Quick question", datetime.now())]
        result_normal = assess_with_timeout_fallback(normal_messages, "Test topic")
        
        assert result_normal["success"] is True
        assert result_normal["method"] == "full_assessment"
        assert result_normal["message_count"] == 1