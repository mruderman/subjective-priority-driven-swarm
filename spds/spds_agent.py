# spds/spds_agent.py

from letta_client import Letta
from letta_client.types import AgentState
from pydantic import BaseModel
from . import tools
from . import config
import re


class SPDSAgent:
    def __init__(self, agent_state: AgentState, client: Letta):
        self.client = client
        self.agent = agent_state
        self.name = agent_state.name
        self.persona, self.expertise = self._parse_system_prompt()
        self.assessment_tool = None
        # TODO: Re-enable tool attachment after fixing schema issue
        # self._ensure_assessment_tool()

        self.motivation_score = 0
        self.priority_score = 0
        self.last_assessment: tools.SubjectiveAssessment = None

    @classmethod
    def create_new(
        cls,
        name: str,
        persona: str,
        expertise: list,
        client: Letta,
        model: str = None,
        embedding: str = None,
    ):
        """Creates a new agent on the Letta server and returns an SPDSAgent instance."""
        system_prompt = (
            f"You are {name}. Your persona is: {persona}. "
            f"Your expertise is in: {', '.join(expertise)}. "
            "You are part of a swarm of agents having a conversation. "
            "You must use your tools to assess the conversation and decide if you should speak."
        )

        # Use provided models or fall back to defaults
        agent_model = model if model else config.DEFAULT_AGENT_MODEL
        agent_embedding = embedding if embedding else config.DEFAULT_EMBEDDING_MODEL

        agent_state = client.agents.create(
            name=name,
            system=system_prompt,
            model=agent_model,
            embedding=agent_embedding,
            include_base_tools=True,
        )
        return cls(agent_state, client)

    def _parse_system_prompt(self):
        """Parses persona and expertise from the agent's system prompt."""
        persona_match = re.search(r"Your persona is: (.*?)\.", self.agent.system)
        expertise_match = re.search(r"Your expertise is in: (.*?)\.", self.agent.system)

        persona = persona_match.group(1) if persona_match else "A helpful assistant."
        expertise_str = expertise_match.group(1) if expertise_match else ""
        expertise = [e.strip() for e in expertise_str.split(",")]

        return persona, expertise

    def _ensure_assessment_tool(self):
        """Ensures the subjective assessment tool is attached to the agent."""
        tool_name = "perform_subjective_assessment"

        # Check if tool is already attached
        for tool in self.agent.tools:
            if tool.name == tool_name:
                self.assessment_tool = tool
                return

        # If not, create the tool and attach it
        print(f"Attaching assessment tool to existing agent: {self.name}")
        
        # Create complete source code with imports and function
        tool_source = '''
from pydantic import BaseModel, Field
from typing import List

class SubjectiveAssessment(BaseModel):
    """A structured model for an agent's subjective assessment of a conversation."""
    importance_to_self: int = Field(..., description="How personally significant is this topic? (0-10)")
    perceived_gap: int = Field(..., description="Are there crucial points missing from the discussion? (0-10)")
    unique_perspective: int = Field(..., description="Do I have insights others haven't shared? (0-10)")
    emotional_investment: int = Field(..., description="How much do I care about the outcome? (0-10)")
    expertise_relevance: int = Field(..., description="How applicable is my domain knowledge? (0-10)")
    urgency: int = Field(..., description="How time-sensitive is the topic or risk of misunderstanding? (0-10)")
    importance_to_group: int = Field(..., description="What is the potential impact on group understanding and consensus? (0-10)")

def perform_subjective_assessment(
    topic: str, conversation_history: str, agent_persona: str, agent_expertise: List[str]
) -> SubjectiveAssessment:
    """
    Performs a holistic, subjective assessment of the conversation to determine motivation and priority for speaking.
    This single assessment evaluates all dimensions of the agent's internal state.
    """
    expertise_str = ", ".join(agent_expertise) if agent_expertise else "general knowledge"
    
    # Analyze conversation for keywords related to expertise
    expertise_keywords = sum(1 for exp in agent_expertise if exp.lower() in conversation_history.lower())
    expertise_score = min(10, expertise_keywords * 2)
    
    # Check if recent messages mention the agent or their expertise
    recent_history = conversation_history[-500:] if len(conversation_history) > 500 else conversation_history
    personal_relevance = 7 if any(exp.lower() in recent_history.lower() for exp in agent_expertise) else 3
    
    # Create assessment based on content analysis
    assessment = SubjectiveAssessment(
        importance_to_self=personal_relevance,
        perceived_gap=5 if "?" in recent_history else 3,
        unique_perspective=expertise_score,
        emotional_investment=4,
        expertise_relevance=expertise_score,
        urgency=7 if any(word in recent_history.lower() for word in ["urgent", "asap", "immediately", "critical"]) else 4,
        importance_to_group=6,
    )
    
    return assessment
'''
        
        self.assessment_tool = self.client.tools.create(
            source_code=tool_source,
        )
        self.agent = self.client.agents.tools.attach(
            agent_id=self.agent.id, tool_id=self.assessment_tool.id
        )

    def _get_full_assessment(self, topic: str):
        """Calls the agent's LLM to perform subjective assessment based on internal memory."""
        
        # Check if agent has tools (need to use send_message for response)
        has_tools = hasattr(self.agent, 'tools') and len(self.agent.tools) > 0
        
        if has_tools:
            assessment_prompt = f"""
Based on our conversation about "{topic}", please assess your motivation to contribute using the send_message tool.

You have access to our full conversation history in your memory. Please review what has been discussed and rate each dimension from 0-10, responding using send_message with this exact format:
IMPORTANCE_TO_SELF: X
PERCEIVED_GAP: X  
UNIQUE_PERSPECTIVE: X
EMOTIONAL_INVESTMENT: X
EXPERTISE_RELEVANCE: X
URGENCY: X
IMPORTANCE_TO_GROUP: X

Where:
1. IMPORTANCE_TO_SELF: How personally significant is this topic to you?
2. PERCEIVED_GAP: Are there crucial points missing from the discussion? 
3. UNIQUE_PERSPECTIVE: Do you have insights others haven't shared?
4. EMOTIONAL_INVESTMENT: How much do you care about the outcome?
5. EXPERTISE_RELEVANCE: How applicable is your domain knowledge?
6. URGENCY: How time-sensitive is this topic or risk of misunderstanding?
7. IMPORTANCE_TO_GROUP: What's the potential impact on group understanding?
"""
        else:
            assessment_prompt = f"""
Based on our conversation about "{topic}", please assess your motivation to contribute. 

You have access to our full conversation history in your memory. Please review what has been discussed and rate each dimension from 0-10:

1. IMPORTANCE_TO_SELF: How personally significant is this topic to you?
2. PERCEIVED_GAP: Are there crucial points missing from the discussion? 
3. UNIQUE_PERSPECTIVE: Do you have insights others haven't shared?
4. EMOTIONAL_INVESTMENT: How much do you care about the outcome?
5. EXPERTISE_RELEVANCE: How applicable is your domain knowledge?
6. URGENCY: How time-sensitive is this topic or risk of misunderstanding?
7. IMPORTANCE_TO_GROUP: What's the potential impact on group understanding?

Respond ONLY with numbers in this exact format:
IMPORTANCE_TO_SELF: X
PERCEIVED_GAP: X  
UNIQUE_PERSPECTIVE: X
EMOTIONAL_INVESTMENT: X
EXPERTISE_RELEVANCE: X
URGENCY: X
IMPORTANCE_TO_GROUP: X
"""
        
        try:
            print(f"  [Getting real assessment from {self.name}...]")
            response = self.client.agents.messages.create(
                agent_id=self.agent.id,
                messages=[{
                    "role": "user",
                    "content": assessment_prompt,
                }],
            )
            
            # Extract response text (handle both tool calls and regular responses)
            response_text = ""
            for msg in response.messages:
                # Check for tool calls first (send_message)
                if hasattr(msg, 'tool_calls') and msg.tool_calls:
                    for tool_call in msg.tool_calls:
                        if hasattr(tool_call, 'function') and tool_call.function.name == 'send_message':
                            try:
                                import json
                                args = json.loads(tool_call.function.arguments)
                                response_text = args.get('message', '')
                                break
                            except:
                                pass
                
                # If no tool call, try regular content extraction
                if not response_text and hasattr(msg, 'content'):
                    if isinstance(msg.content, str):
                        response_text = msg.content
                    elif isinstance(msg.content, list) and msg.content:
                        content_item = msg.content[0]
                        if hasattr(content_item, 'text'):
                            response_text = content_item.text
                        elif isinstance(content_item, str):
                            response_text = content_item
                
                if response_text:
                    break
            
            # Parse the assessment scores
            scores = self._parse_assessment_response(response_text)
            self.last_assessment = tools.SubjectiveAssessment(**scores)
            
        except Exception as e:
            print(f"  [Error getting assessment from {self.name}: {e}]")
            # Fallback to slightly randomized basic assessment
            import random
            base_score = random.randint(3, 7)
            self.last_assessment = tools.SubjectiveAssessment(
                importance_to_self=base_score + random.randint(-1, 2),
                perceived_gap=base_score + random.randint(-1, 2),
                unique_perspective=base_score + random.randint(-1, 2),
                emotional_investment=base_score + random.randint(-1, 2),
                expertise_relevance=base_score + random.randint(-1, 2),
                urgency=base_score + random.randint(-1, 2),
                importance_to_group=base_score + random.randint(-1, 2),
            )
    
    def _parse_assessment_response(self, response_text: str) -> dict:
        """Parses the agent's assessment response to extract numeric scores."""
        scores = {}
        default_scores = {
            'importance_to_self': 5,
            'perceived_gap': 5, 
            'unique_perspective': 5,
            'emotional_investment': 5,
            'expertise_relevance': 5,
            'urgency': 5,
            'importance_to_group': 5,
        }
        
        # Try to extract scores from the response
        lines = response_text.split('\n')
        for line in lines:
            line = line.strip()
            for key in default_scores.keys():
                key_upper = key.upper()
                if key_upper in line and ':' in line:
                    try:
                        score_part = line.split(':')[1].strip()
                        # Extract just the number (handle cases like "7/10" or "7 out of 10")
                        score_str = re.search(r'\d+', score_part)
                        if score_str:
                            score = int(score_str.group())
                            scores[key] = max(0, min(10, score))  # Clamp to 0-10
                    except (ValueError, IndexError):
                        continue
        
        # Fill in any missing scores with defaults
        for key, default_val in default_scores.items():
            if key not in scores:
                scores[key] = default_val
                
        return scores

    def assess_motivation_and_priority(self, topic: str):
        """Performs the full assessment and calculates motivation and priority scores."""
        self._get_full_assessment(topic)

        assessment = self.last_assessment
        self.motivation_score = (
            assessment.importance_to_self
            + assessment.perceived_gap
            + assessment.unique_perspective
            + assessment.emotional_investment
            + assessment.expertise_relevance
        )

        if self.motivation_score >= config.PARTICIPATION_THRESHOLD:
            self.priority_score = (assessment.urgency * config.URGENCY_WEIGHT) + (
                assessment.importance_to_group * config.IMPORTANCE_WEIGHT
            )
        else:
            self.priority_score = 0

    def speak(self, mode="initial", topic=None):
        """Generates a response from the agent based on internal memory."""
        # Check if agent has tools (Letta default agents require using send_message tool)
        has_tools = hasattr(self.agent, 'tools') and len(self.agent.tools) > 0
        
        # Get the last user message from conversation for context
        recent_context = ""
        if topic:
            recent_context = f" The current topic is: '{topic}'."
        if has_tools:
            # For agents with tools, be very explicit about using send_message
            if mode == "initial":
                # Initial independent thoughts
                prompt = f"""The user just asked a question or made a statement.{recent_context} Based on your assessment and the full conversation history in your memory, please share your initial thoughts on this. Use the send_message tool to respond. Your response should directly address what was just discussed."""
            else:
                # Response phase - reacting to others
                prompt = f"""Other agents have just shared their thoughts on the topic.{recent_context} Based on what everyone has shared in the conversation (which is in your memory), please share your response. You might agree, disagree, build on their ideas, or add new perspectives. Use the send_message tool to respond."""
        else:
            # For agents without tools, use simple prompt
            if mode == "initial":
                prompt = f"The user just asked a question or made a statement.{recent_context} Based on the conversation in your memory, here is my response:"
            else:
                prompt = f"Other agents have shared their thoughts.{recent_context} Based on what everyone has said, here is my response:"
        
        try:
            return self.client.agents.messages.create(
                agent_id=self.agent.id,
                messages=[
                    {
                        "role": "user",
                        "content": prompt,
                    }
                ],
            )
        except Exception as e:
            # If tool call fails, try a more direct approach
            if "No tool calls found" in str(e) and has_tools:
                print(f"[Debug: {self.name} didn't use tools, trying direct instruction]")
                direct_prompt = "Please use the send_message tool to share your thoughts on the topic we've been discussing."
                return self.client.agents.messages.create(
                    agent_id=self.agent.id,
                    messages=[
                        {
                            "role": "user", 
                            "content": direct_prompt,
                        }
                    ],
                )
            else:
                raise
