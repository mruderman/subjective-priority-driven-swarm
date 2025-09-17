"""
Unit tests for spds.tools module.
"""

import pytest
from pydantic import ValidationError

from spds.tools import SubjectiveAssessment, perform_subjective_assessment


class TestSubjectiveAssessment:
    """Test the SubjectiveAssessment Pydantic model."""

    def test_valid_assessment_creation(self):
        """Test creating a valid SubjectiveAssessment."""
        assessment = SubjectiveAssessment(
            importance_to_self=8,
            perceived_gap=6,
            unique_perspective=7,
            emotional_investment=5,
            expertise_relevance=9,
            urgency=7,
            importance_to_group=8,
        )

        assert assessment.importance_to_self == 8
        assert assessment.perceived_gap == 6
        assert assessment.unique_perspective == 7
        assert assessment.emotional_investment == 5
        assert assessment.expertise_relevance == 9
        assert assessment.urgency == 7
        assert assessment.importance_to_group == 8

    def test_assessment_with_boundary_values(self):
        """Test assessment with boundary values (0 and 10)."""
        assessment = SubjectiveAssessment(
            importance_to_self=0,
            perceived_gap=10,
            unique_perspective=0,
            emotional_investment=10,
            expertise_relevance=5,
            urgency=0,
            importance_to_group=10,
        )

        assert assessment.importance_to_self == 0
        assert assessment.perceived_gap == 10
        assert assessment.unique_perspective == 0
        assert assessment.emotional_investment == 10
        assert assessment.urgency == 0
        assert assessment.importance_to_group == 10

    def test_missing_required_fields(self):
        """Test that missing required fields raise ValidationError."""
        with pytest.raises(ValidationError):
            SubjectiveAssessment(
                importance_to_self=8,
                perceived_gap=6,
                # Missing other required fields
            )

    def test_invalid_field_types(self):
        """Test that invalid field types raise ValidationError."""
        with pytest.raises(ValidationError):
            SubjectiveAssessment(
                importance_to_self="eight",  # Should be int
                perceived_gap=6,
                unique_perspective=7,
                emotional_investment=5,
                expertise_relevance=9,
                urgency=7,
                importance_to_group=8,
            )

    def test_assessment_model_dump(self):
        """Test converting assessment to dict."""
        assessment = SubjectiveAssessment(
            importance_to_self=8,
            perceived_gap=6,
            unique_perspective=7,
            emotional_investment=5,
            expertise_relevance=9,
            urgency=7,
            importance_to_group=8,
        )

        data = assessment.model_dump()
        expected = {
            "importance_to_self": 8,
            "perceived_gap": 6,
            "unique_perspective": 7,
            "emotional_investment": 5,
            "expertise_relevance": 9,
            "urgency": 7,
            "importance_to_group": 8,
        }

        assert data == expected


class TestPerformSubjectiveAssessment:
    """Test the perform_subjective_assessment function."""

    def test_basic_assessment(self):
        """Test basic assessment functionality."""
        topic = "Testing Strategy"
        conversation_history = "We need to discuss our testing approach."
        agent_persona = "A testing expert"
        agent_expertise = ["testing", "validation", "QA"]

        assessment = perform_subjective_assessment(
            topic, conversation_history, agent_persona, agent_expertise
        )

        assert isinstance(assessment, SubjectiveAssessment)
        assert 0 <= assessment.importance_to_self <= 10
        assert 0 <= assessment.perceived_gap <= 10
        assert 0 <= assessment.unique_perspective <= 10
        assert 0 <= assessment.emotional_investment <= 10
        assert 0 <= assessment.expertise_relevance <= 10
        assert 0 <= assessment.urgency <= 10
        assert 0 <= assessment.importance_to_group <= 10

    def test_assessment_with_expertise_keywords(self):
        """Test that assessment recognizes expertise keywords in conversation."""
        topic = "Testing Strategy"
        conversation_history = (
            "We need comprehensive testing and validation of our system."
        )
        agent_persona = "A testing expert"
        agent_expertise = ["testing", "validation"]

        assessment = perform_subjective_assessment(
            topic, conversation_history, agent_persona, agent_expertise
        )

        # Should have higher expertise relevance due to keyword matches
        assert assessment.expertise_relevance >= 2  # At least some relevance
        assert assessment.unique_perspective >= 2

    def test_assessment_with_urgency_keywords(self):
        """Test that assessment recognizes urgency keywords."""
        topic = "Critical Bug"
        conversation_history = (
            "This is urgent! We need to fix this critical issue immediately."
        )
        agent_persona = "A developer"
        agent_expertise = ["debugging", "development"]

        assessment = perform_subjective_assessment(
            topic, conversation_history, agent_persona, agent_expertise
        )

        # Should have higher urgency due to urgency keywords
        assert assessment.urgency >= 6

    def test_assessment_with_questions(self):
        """Test that assessment recognizes questions in conversation."""
        topic = "Implementation Details"
        conversation_history = (
            "How should we implement this feature? What are the best practices?"
        )
        agent_persona = "An expert developer"
        agent_expertise = ["architecture", "best practices"]

        assessment = perform_subjective_assessment(
            topic, conversation_history, agent_persona, agent_expertise
        )

        # Should have higher perceived gap due to questions
        assert assessment.perceived_gap >= 4

    def test_assessment_without_expertise_match(self):
        """Test assessment when expertise doesn't match conversation topic."""
        topic = "Marketing Strategy"
        conversation_history = (
            "We need to plan our marketing campaign for next quarter."
        )
        agent_persona = "A technical developer"
        agent_expertise = ["programming", "debugging", "architecture"]

        assessment = perform_subjective_assessment(
            topic, conversation_history, agent_persona, agent_expertise
        )

        # Should have lower expertise relevance
        assert assessment.expertise_relevance <= 5
        assert assessment.unique_perspective <= 5

    def test_assessment_with_empty_expertise(self):
        """Test assessment with empty expertise list."""
        topic = "General Discussion"
        conversation_history = "Let's discuss our general approach."
        agent_persona = "A general helper"
        agent_expertise = []

        assessment = perform_subjective_assessment(
            topic, conversation_history, agent_persona, agent_expertise
        )

        assert isinstance(assessment, SubjectiveAssessment)
        # Should still produce valid scores
        assert assessment.expertise_relevance >= 0

    def test_assessment_with_long_conversation(self):
        """Test assessment with very long conversation history."""
        topic = "Long Discussion"
        # Create a long conversation history
        conversation_history = "This is a test conversation. " * 200  # ~4000+ chars
        agent_persona = "A patient listener"
        agent_expertise = ["listening", "analysis"]

        assessment = perform_subjective_assessment(
            topic, conversation_history, agent_persona, agent_expertise
        )

        assert isinstance(assessment, SubjectiveAssessment)
        # Function should handle long input gracefully
        assert all(
            0 <= score <= 10
            for score in [
                assessment.importance_to_self,
                assessment.perceived_gap,
                assessment.unique_perspective,
                assessment.emotional_investment,
                assessment.expertise_relevance,
                assessment.urgency,
                assessment.importance_to_group,
            ]
        )

    def test_assessment_persona_integration(self):
        """Test that different personas might yield different assessments."""
        topic = "Team Dynamics"
        conversation_history = "Our team communication needs improvement."

        # Test with HR persona
        hr_assessment = perform_subjective_assessment(
            topic,
            conversation_history,
            "An HR specialist focused on team dynamics",
            ["HR", "team building", "communication"],
        )

        # Test with technical persona
        tech_assessment = perform_subjective_assessment(
            topic,
            conversation_history,
            "A technical architect focused on systems",
            ["architecture", "systems", "technical design"],
        )

        # HR should be more relevant to team dynamics
        assert hr_assessment.expertise_relevance >= tech_assessment.expertise_relevance
