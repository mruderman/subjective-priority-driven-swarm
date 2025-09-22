# spds/spds_agent.py

import re

from letta_client import Letta
from letta_client.types import AgentState
from pydantic import BaseModel

from . import config, tools
from .letta_api import letta_call
from .session_tracking import track_message, track_tool_call, track_decision, track_action


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

        agent_state = letta_call(
            "agent.create",
            client.agents.create,
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

        # Create from our local function, adapting to the installed letta-client signature.
        create_fn = self.client.tools.create_from_function
        create_kwargs = tools.build_tool_create_kwargs(
            create_fn,
            tools.perform_subjective_assessment,
            name=tool_name,
            description="Perform a holistic subjective assessment of the conversation",
            return_model=tools.SubjectiveAssessment,
        )
        self.assessment_tool = letta_call(
            "tools.create_from_function",
            create_fn,
            **create_kwargs,
        )
        # Attach to agent
        try:
            attached = letta_call(
                "agents.tools.attach",
                self.client.agents.tools.attach,
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
            
            # Track the assessment request
            track_action(
                actor=self.name,
                action_type="assessment_request",
                details={
                    "topic": topic,
                    "has_conversation_history": bool(conversation_history),
                    "has_tools": has_tools
                }
            )
            
            response = letta_call(
                "agents.messages.create.assessment",
                self.client.agents.messages.create,
                agent_id=self.agent.id,
                messages=[
                    {
                        "role": "user",
                        "content": assessment_prompt,
                    }
                ],
            )
            
            # Track tool calls in the response
            for msg in response.messages:
                if hasattr(msg, "tool_calls") and getattr(msg, "tool_calls"):
                    for tool_call in msg.tool_calls:
                        if (
                            hasattr(tool_call, "function")
                            and getattr(tool_call.function, "name", None)
                            == "send_message"
                        ):
                            track_tool_call(
                                actor=self.name,
                                tool_name="send_message",
                                arguments={"message": "assessment_response"},
                                result="success"
                            )

            # Extract candidate response texts (tool call payloads, tool returns, or assistant content)
            candidate_texts = []
            for msg in response.messages:
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
                                candidate_texts.append(args.get("message", ""))
                            except Exception:
                                candidate_texts.append("")
                if hasattr(msg, "tool_return") and getattr(msg, "tool_return"):
                    candidate_texts.append(getattr(msg, "tool_return"))
                if hasattr(msg, "content"):
                    content_val = getattr(msg, "content")
                    if isinstance(content_val, str):
                        candidate_texts.append(content_val)
                    elif isinstance(content_val, list) and content_val:
                        item0 = content_val[0]
                        if hasattr(item0, "text"):
                            candidate_texts.append(item0.text)
                        elif isinstance(item0, dict) and "text" in item0:
                            candidate_texts.append(item0["text"])
                        elif isinstance(item0, str):
                            candidate_texts.append(item0)

            response_text = ""
            assessment_keys = [
                "IMPORTANCE_TO_SELF",
                "PERCEIVED_GAP",
                "UNIQUE_PERSPECTIVE",
                "EMOTIONAL_INVESTMENT",
                "EXPERTISE_RELEVANCE",
                "URGENCY",
                "IMPORTANCE_TO_GROUP",
            ]
            parsed_dict = None
            parsed_scores = None

            for candidate in candidate_texts:
                if not isinstance(candidate, str):
                    continue
                candidate = candidate.strip()
                if not candidate:
                    continue
                response_text = candidate
                if candidate.startswith("{"):
                    try:
                        import json as _json

                        parsed = _json.loads(candidate)
                    except Exception:
                        continue
                    if isinstance(parsed, dict):
                        parsed_dict = parsed
                        break
                    continue

                scores = self._parse_assessment_response(candidate)
                if any(key in candidate.upper() for key in assessment_keys):
                    parsed_scores = scores
                    break

            if parsed_dict is not None:
                self.last_assessment = tools.SubjectiveAssessment(**parsed_dict)
            elif parsed_scores is not None:
                self.last_assessment = tools.SubjectiveAssessment(**parsed_scores)
            elif response_text and any(
                key in (response_text.upper()) for key in assessment_keys
            ):
                scores = self._parse_assessment_response(response_text)
                self.last_assessment = tools.SubjectiveAssessment(**scores)
            else:
                # Fallback to local subjective assessment
                self.last_assessment = tools.perform_subjective_assessment(
                    topic, conversation_history, self.persona, self.expertise
                )

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

    def _extract_response_text(self, response) -> str:
        """Extract response text from agent messages, handling tool calls properly."""
        response_text = ""
        try:
            for msg in response.messages:
                # Check for tool calls (send_message)
                if hasattr(msg, "tool_calls") and msg.tool_calls:
                    for tool_call in msg.tool_calls:
                        if (
                            hasattr(tool_call, "function")
                            and tool_call.function.name == "send_message"
                        ):
                            try:
                                import json
                                args = json.loads(tool_call.function.arguments)
                                response_text = args.get("message", "")
                                break
                            except:
                                pass
                
                # Check for tool return messages
                if not response_text and hasattr(msg, "tool_return") and msg.tool_return:
                    continue
                
                # Check assistant messages (direct responses)
                if (
                    not response_text
                    and hasattr(msg, "message_type")
                    and msg.message_type == "assistant_message"
                ):
                    if hasattr(msg, "content") and msg.content:
                        content_val = msg.content
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
        except Exception as e:
            logger = logging.getLogger(__name__)
            logger.warning(f"Failed to extract response text: {e}")
        
        return response_text

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
            
            # Track the assessment decision
            track_decision(
                actor=self.name,
                decision_type="motivation_assessment",
                details={
                    "topic": topic,
                    "motivation_score": self.motivation_score,
                    "priority_score": self.priority_score,
                    "participation_threshold": config.PARTICIPATION_THRESHOLD,
                    "will_participate": self.motivation_score >= config.PARTICIPATION_THRESHOLD,
                    "assessment": assessment.model_dump()
                }
            )
    
    def _select_mode_for_message(self, message: str, attachments: list = None) -> str:
        """Select processing mode based on message content and attachments.

        Returns:
            str: "vision" if any image attachments are present, "text" otherwise.
                 Returns "doc" for document-only attachments (future enhancement).
        """
        attachments = attachments or []

        # Check for image attachments
        has_images = any(
            attachment.get('kind') == 'image'
            for attachment in attachments
        )

        # Check for document attachments
        has_documents = any(
            attachment.get('kind') == 'document'
            for attachment in attachments
        )

        if has_images:
            return "vision"
        elif has_documents and not has_images:
            # For now, default to text mode for documents
            # Future enhancement: implement document processing mode
            return "text"
        else:
            return "text"

    def speak(
        self, conversation_history: str = "", mode: str = "initial", topic: str = "", attachments: list = None
    ):
        """Generates a response from the agent with conversation context."""
        # Select processing mode based on attachments
        selected_mode = self._select_mode_for_message(conversation_history, attachments)

        # Log mode selection for scaffolding
        print(f"[DEBUG] Agent {self.name} selected mode: {selected_mode} for message with {len(attachments or [])} attachments")

        # Track the mode selection in session events
        if attachments:
            track_decision(
                actor=self.name,
                decision_type="mode_selection",
                details={
                    "selected_mode": selected_mode,
                    "attachments_count": len(attachments),
                    "has_images": any(att.get('kind') == 'image' for att in attachments),
                    "has_documents": any(att.get('kind') == 'document' for att in attachments),
                    "message_preview": conversation_history[:100] if conversation_history else topic[:100]
                }
            )

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
            response = letta_call(
                "agents.messages.create.speak",
                self.client.agents.messages.create,
                agent_id=self.agent.id,
                messages=[
                    {
                        "role": "user",
                        "content": prompt,
                    }
                ],
            )
            
            # Track the agent's response
            response_text = self._extract_response_text(response)
            if response_text:
                track_message(
                    actor=self.name,
                    content=response_text,
                    message_type="assistant"
                )
            
            return response
        except Exception as e:
            # If tool call fails, try a more direct approach
            if "No tool calls found" in str(e) and has_tools:
                print(
                    f"[Debug: {self.name} didn't use tools, trying direct instruction]"
                )
                direct_prompt = "Please use the send_message tool to share your thoughts on the topic we've been discussing."
                response = letta_call(
                    "agents.messages.create.direct",
                    self.client.agents.messages.create,
                    agent_id=self.agent.id,
                    messages=[
                        {
                            "role": "user",
                            "content": direct_prompt,
                        }
                    ],
                )
                
                # Track the agent's response from direct prompt
                response_text = self._extract_response_text(response)
                if response_text:
                    track_message(
                        actor=self.name,
                        content=response_text,
                        message_type="assistant"
                    )
                
                return response
            else:
                raise
