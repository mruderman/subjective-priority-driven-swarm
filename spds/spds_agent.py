# spds/spds_agent.py

import re

from letta_client import Letta
from letta_client.types import AgentState
from pydantic import BaseModel

from . import config, tools


class SPDSAgent:
    def __init__(self, agent_state: AgentState, client: Letta):
        self.client = client
        self.agent = agent_state
        self.name = agent_state.name
        self.persona, self.expertise = self._parse_system_prompt()
        self.assessment_tool = None
        # Ensure the subjective assessment tool is available
        self._ensure_assessment_tool()

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
        """Ensures the subjective assessment tool is attached to the agent.

        Uses the local implementation in spds.tools and attaches it to the agent
        via the Letta Tools API if not already present. Matches tests expecting
        create_from_function + agents.tools.attach behavior.
        """
        tool_name = "perform_subjective_assessment"

        try:
            for tool in getattr(self.agent, "tools", []) or []:
                if getattr(tool, "name", None) == tool_name:
                    self.assessment_tool = tool
                    return
        except Exception:
            # If tools enumeration fails, proceed to attach
            pass

        # Create from our local function and Pydantic model
        self.assessment_tool = self.client.tools.create_from_function(
            function=tools.perform_subjective_assessment,
            return_model=tools.SubjectiveAssessment,
            name=tool_name,
            description="Perform a holistic subjective assessment of the conversation",
        )
        # Attach to agent
        try:
            attached = self.client.agents.tools.attach(
                agent_id=self.agent.id,
                tool_id=self.assessment_tool.id,
            )
            # Only replace if we received a proper AgentState back
            if isinstance(attached, AgentState):
                self.agent = attached
        except Exception:
            # If attach flow fails in a mocked environment, continue gracefully
            pass

    def _get_full_assessment(self, conversation_history: str = "", topic: str = ""):
        """Calls the agent's LLM to perform subjective assessment.
        If conversation_history is provided, include it in the prompt to reduce reliance on server-side memory.
        """

        # Check if agent has tools (need to use send_message for response)
        has_tools = hasattr(self.agent, "tools") and len(self.agent.tools) > 0

        if has_tools:
            assessment_context = (
                f"Conversation so far:\n{conversation_history}\n\n"
                if conversation_history
                else ""
            )
            assessment_prompt = f"""
{assessment_context}Based on our conversation about "{topic}", please assess your motivation to contribute using the send_message tool.

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
            assessment_context = (
                f"Conversation so far:\n{conversation_history}\n\n"
                if conversation_history
                else ""
            )
            assessment_prompt = f"""
{assessment_context}Based on our conversation about "{topic}", please assess your motivation to contribute. 

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
                messages=[
                    {
                        "role": "user",
                        "content": assessment_prompt,
                    }
                ],
            )

            # Extract response text or JSON (handle tool return or direct content)
            response_text = ""
            for msg in response.messages:
                # Tool call flow (send_message)
                if hasattr(msg, "tool_calls") and getattr(msg, "tool_calls"):
                    for tool_call in msg.tool_calls:
                        if (
                            hasattr(tool_call, "function")
                            and getattr(tool_call.function, "name", None)
                            == "send_message"
                        ):
                            try:
                                import json as _json

                                args = _json.loads(tool_call.function.arguments)
                                response_text = args.get("message", "")
                                break
                            except Exception:
                                pass
                # Tool return message payload
                if (
                    not response_text
                    and hasattr(msg, "tool_return")
                    and getattr(msg, "tool_return")
                ):
                    response_text = getattr(msg, "tool_return")
                # Generic content field
                if not response_text and hasattr(msg, "content"):
                    content_val = getattr(msg, "content")
                    if isinstance(content_val, str):
                        response_text = content_val
                    elif isinstance(content_val, list) and content_val:
                        item0 = content_val[0]
                        if hasattr(item0, "text"):
                            response_text = item0.text
                        elif isinstance(item0, dict) and "text" in item0:
                            response_text = item0["text"]
                        elif isinstance(item0, str):
                            response_text = item0
                if response_text:
                    break

            # Try JSON first (supports tests/e2e + unit JSON content), else parse lines
            parsed = None
            if isinstance(response_text, str) and response_text.strip().startswith("{"):
                try:
                    import json as _json

                    parsed = _json.loads(response_text)
                except Exception:
                    parsed = None
            if isinstance(parsed, dict):
                self.last_assessment = tools.SubjectiveAssessment(**parsed)
            else:
                # Try to parse labeled scores; if not present, fall back to local tool
                scores = self._parse_assessment_response(response_text or "")
                if not response_text or not any(
                    k in (response_text.upper())
                    for k in [
                        "IMPORTANCE_TO_SELF",
                        "PERCEIVED_GAP",
                        "UNIQUE_PERSPECTIVE",
                        "EMOTIONAL_INVESTMENT",
                        "EXPERTISE_RELEVANCE",
                        "URGENCY",
                        "IMPORTANCE_TO_GROUP",
                    ]
                ):
                    # Fallback to local subjective assessment
                    self.last_assessment = tools.perform_subjective_assessment(
                        topic, conversation_history, self.persona, self.expertise
                    )
                else:
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
            "importance_to_self": 5,
            "perceived_gap": 5,
            "unique_perspective": 5,
            "emotional_investment": 5,
            "expertise_relevance": 5,
            "urgency": 5,
            "importance_to_group": 5,
        }

        # Try to extract scores from the response
        lines = response_text.split("\n")
        for line in lines:
            line = line.strip()
            for key in default_scores.keys():
                key_upper = key.upper()
                if key_upper in line and ":" in line:
                    try:
                        score_part = line.split(":")[1].strip()
                        # Extract just the number (handle cases like "7/10" or "7 out of 10")
                        score_str = re.search(r"\d+", score_part)
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

    def speak(
        self, conversation_history: str = "", mode: str = "initial", topic: str = ""
    ):
        """Generates a response from the agent with conversation context."""
        # Check if agent has tools (Letta default agents require using send_message tool)
        has_tools = hasattr(self.agent, "tools") and len(self.agent.tools) > 0

        # Use conversation history if provided, otherwise use topic-based prompting
        if conversation_history:
            # Original working pattern with conversation history
            if has_tools:
                prompt = f"""{conversation_history}

Based on this conversation, I want to contribute. Please use the send_message tool to share your response. Remember to call the send_message function with your response as the message parameter."""
            else:
                prompt = f"{conversation_history}\nBased on my assessment, here is my contribution:"
        else:
            # Fallback to topic-based prompting
            if has_tools:
                if mode == "initial":
                    prompt = f"""Based on my assessment of the topic '{topic}', I want to share my initial thoughts and perspective. Please use the send_message tool to contribute your viewpoint to this discussion. Remember to call the send_message function with your response as the message parameter."""
                else:  # response mode
                    prompt = f"""Based on what everyone has shared about '{topic}', I'd like to respond to the discussion. Please use the send_message tool to share your response, building on or reacting to what others have said. Remember to call the send_message function with your response as the message parameter."""
            else:
                if mode == "initial":
                    prompt = f"Based on my assessment of '{topic}', here is my initial contribution:"
                else:
                    prompt = (
                        f"Based on the discussion about '{topic}', here is my response:"
                    )

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
                print(
                    f"[Debug: {self.name} didn't use tools, trying direct instruction]"
                )
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
