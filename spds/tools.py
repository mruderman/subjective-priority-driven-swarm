# spds/tools.py

from pydantic import BaseModel, Field


class SubjectiveAssessment(BaseModel):
    """A structured model for an agent's subjective assessment of a conversation."""

    importance_to_self: int = Field(
        ..., description="How personally significant is this topic? (0-10)"
    )
    perceived_gap: int = Field(
        ..., description="Are there crucial points missing from the discussion? (0-10)"
    )
    unique_perspective: int = Field(
        ..., description="Do I have insights others haven't shared? (0-10)"
    )
    emotional_investment: int = Field(
        ..., description="How much do I care about the outcome? (0-10)"
    )
    expertise_relevance: int = Field(
        ..., description="How applicable is my domain knowledge? (0-10)"
    )
    urgency: int = Field(
        ...,
        description="How time-sensitive is the topic or risk of misunderstanding? (0-10)",
    )
    importance_to_group: int = Field(
        ...,
        description="What is the potential impact on group understanding and consensus? (0-10)",
    )


def perform_subjective_assessment(
    topic: str, conversation_history: str, agent_persona: str, agent_expertise: list
) -> SubjectiveAssessment:
    """
    Performs a holistic, subjective assessment of the conversation to determine motivation and priority for speaking.
    This single assessment evaluates all dimensions of the agent's internal state.

    Note: This function is designed to be called by the Letta agent's LLM, not directly.
    The agent will use this tool to assess its motivation to speak.
    """
    import json

    expertise_str = (
        ", ".join(agent_expertise) if agent_expertise else "general knowledge"
    )

    # Create a structured prompt for the LLM to analyze the conversation
    assessment_prompt = f"""
You are {agent_persona} with expertise in: {expertise_str}

Given the conversation history and topic, assess your motivation to speak next by scoring each dimension from 0-10.

Topic: {topic}

Recent Conversation:
{conversation_history[-1000:] if len(conversation_history) > 1000 else conversation_history}

Evaluate and return scores for:
1. importance_to_self (0-10): How personally significant is this topic to you?
2. perceived_gap (0-10): Are there crucial points missing from the discussion that you could address?
3. unique_perspective (0-10): Do you have insights others haven't shared?
4. emotional_investment (0-10): How much do you care about the outcome?
5. expertise_relevance (0-10): How applicable is your domain knowledge?
6. urgency (0-10): How time-sensitive is the topic or risk of misunderstanding?
7. importance_to_group (0-10): What is the potential impact on group understanding and consensus?

Return ONLY a JSON object with these exact keys and integer values 0-10.
"""

    # For the actual implementation, this prompt would be sent to the agent's LLM
    # Since this function is called BY the agent as a tool, we can access the agent's context
    # For now, we'll create a more intelligent placeholder that considers the actual content

    # Analyze conversation for keywords related to expertise
    expertise_keywords = sum(
        1 for exp in agent_expertise if exp.lower() in conversation_history.lower()
    )
    expertise_score = min(10, expertise_keywords * 2)

    # Check if recent messages mention the agent or their expertise
    recent_history = (
        conversation_history[-500:]
        if len(conversation_history) > 500
        else conversation_history
    )
    personal_relevance = (
        7
        if any(exp.lower() in recent_history.lower() for exp in agent_expertise)
        else 3
    )

    # More nuanced assessment based on topic and expertise
    topic_words = topic.lower().split()
    expertise_match = sum(
        2 for exp in agent_expertise if any(word in exp.lower() for word in topic_words)
    )

    # Check for questions and discussion gaps
    has_question = "?" in recent_history
    needs_perspective = any(
        phrase in recent_history.lower()
        for phrase in ["should we", "what if", "consider", "think about", "prioritize"]
    )

    # Boost personal relevance based on expertise and topic alignment
    personal_relevance = min(10, personal_relevance + expertise_match)

    # Check if the topic is in the agent's domain
    is_ethics_topic = any(
        word in topic.lower() for word in ["ethics", "moral", "responsible"]
    )
    is_tech_topic = any(
        word in topic.lower()
        for word in ["develop", "model", "capabilities", "improve"]
    )
    is_strategy_topic = any(
        word in topic.lower() for word in ["prioritize", "framework", "focus"]
    )

    # Create a somewhat intelligent assessment based on content analysis
    assessment = SubjectiveAssessment(
        importance_to_self=personal_relevance,
        perceived_gap=8 if has_question else (6 if needs_perspective else 4),
        unique_perspective=min(10, expertise_score + 3),
        emotional_investment=7 if is_ethics_topic else 5,
        expertise_relevance=min(10, expertise_score + 2),
        urgency=(
            8
            if any(
                word in recent_history.lower()
                for word in ["urgent", "asap", "immediately", "critical", "prioritize"]
            )
            else 5
        ),
        importance_to_group=8 if (is_strategy_topic or is_ethics_topic) else 6,
    )

    return assessment
