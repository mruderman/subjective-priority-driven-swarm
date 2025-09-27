# spds/spds_agent.py

import logging
import re
from types import SimpleNamespace

from letta_client import Letta
from letta_client.types import AgentState
from pydantic import BaseModel

from . import config, tools
from .letta_api import letta_call
from .session_tracking import (
    track_action,
    track_decision,
    track_message,
    track_tool_call,
)
try:
    from letta_client.core.api_error import ApiError
except ImportError:  # pragma: no cover
    ApiError = None  # type: ignore


logger = logging.getLogger(__name__)


class SPDSAgent:
    def __init__(self, agent_state: AgentState, client: Letta):
        self.client = client
        self.agent = agent_state
        self.name = agent_state.name
        self.persona, self.expertise = self._parse_system_prompt()
        self.assessment_tool = None
        self._assessment_tool_disabled = False
        self._tools_supported = True
        # Ensure the subjective assessment tool is available
        self._ensure_assessment_tool()

        self.motivation_score = 0
        self.priority_score = 0
        self.last_assessment: tools.SubjectiveAssessment = None
        self.last_error: str | None = None
        self.last_message_index = -1  # Index in conversation history when this agent last spoke

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
        def _build_kwargs(target_fn):
            # Choose how to express schemas to the backend to avoid pulling in
            # Pydantic inside the tool sandbox unless explicitly enabled.
            use_pydantic = getattr(config, "get_tools_use_pydantic_schemas", lambda: False)()
            use_return_model = getattr(config, "get_tools_use_return_model", lambda: False)()

            args_schema = tools.SubjectiveAssessmentInput if use_pydantic else None
            json_schema = (
                None
                if use_pydantic
                else tools.SubjectiveAssessmentInput.model_json_schema()
            )
            return_model = tools.SubjectiveAssessment if use_return_model else None

            return tools.build_tool_create_kwargs(
                target_fn,
                tools.perform_subjective_assessment,
                name=tool_name,
                description="Perform a holistic subjective assessment of the conversation",
                return_model=return_model,
                args_schema=args_schema,
                json_schema=json_schema,
            )

        create_fn = self.client.tools.create_from_function
        create_kwargs = _build_kwargs(create_fn)

        try:
            self.assessment_tool = letta_call(
                "tools.create_from_function",
                create_fn,
                **create_kwargs,
            )
        except Exception as exc:  # noqa: BLE001
            if ApiError is None or not isinstance(exc, ApiError) or exc.status_code != 409:
                raise

            logger.info(
                "Tool '%s' already exists; reusing existing instance instead of recreating.",
                tool_name,
            )

            fallback_tool = None

            upsert_fn = getattr(self.client.tools, "upsert_from_function", None)
            if callable(upsert_fn):
                upsert_kwargs = _build_kwargs(upsert_fn)
                try:
                    fallback_tool = letta_call(
                        "tools.upsert_from_function",
                        upsert_fn,
                        **upsert_kwargs,
                    )
                except Exception:  # noqa: BLE001
                    fallback_tool = None

            if fallback_tool is None:
                fallback_tool = self._find_tool_by_name(tool_name)

            if fallback_tool is None:
                raise

            self.assessment_tool = fallback_tool
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

    def _disable_assessment_tool(self, reason: str) -> bool:
        """Detach the subjective assessment tool when the backend rejects it."""

        if self.assessment_tool is None or self._assessment_tool_disabled:
            return False

        tool_id = getattr(self.assessment_tool, "id", None)

        logger.info(
            "Disabling subjective assessment tool for %s due to backend incompatibility: %s",
            self.name,
            reason,
        )
        self.last_error = reason

        if tool_id:
            try:
                updated_state = letta_call(
                    "agents.tools.detach",
                    self.client.agents.tools.detach,
                    agent_id=self.agent.id,
                    tool_id=tool_id,
                )
                if isinstance(updated_state, AgentState):
                    self.agent = updated_state
            except Exception as detach_error:  # noqa: BLE001
                logger.warning(
                    "Failed to detach subjective assessment tool for %s: %s",
                    self.name,
                    detach_error,
                )

        self.assessment_tool = None
        self._assessment_tool_disabled = True
        self._tools_supported = False
        return True

    @staticmethod
    def _is_tool_incompatibility_error(exc: Exception) -> bool:
        """Detect backend responses indicating tool schema is not supported."""

        msg = str(exc).lower()
        return (
            "invalid tools" in msg
            or "missing message argument" in msg
            or "no module named" in msg
            or "pydantic" in msg
        )

    def _find_tool_by_name(self, tool_name: str):
        """Fetch an existing Letta tool by name."""

        try:
            tools_list = letta_call(
                "tools.list",
                self.client.tools.list,
                name=tool_name,
                limit=1,
            )
        except Exception:  # noqa: BLE001
            return None

        if not tools_list:
            return None
        return tools_list[0]

    def _get_full_assessment(self, conversation_history: str = "", topic: str = ""):
        """Calls the agent's LLM to perform subjective assessment.
        If conversation_history is provided, include it in the prompt to reduce reliance on server-side memory.
        """

        self.last_error = None
        max_attempts = 2
        attempt = 0
        
        while attempt < max_attempts:
            has_tools = (
                self._tools_supported
                and hasattr(self.agent, "tools")
                and len(self.agent.tools) > 0
            )

            if has_tools:
                assessment_context = (
                    f"Conversation so far:\n{conversation_history}\n\n"
                    if conversation_history
                    else ""
                )
                # Only claim the agent has access to "full conversation history in memory"
                # when we actually provided conversation_history in the prompt. Otherwise
                # avoid the confusing claim on first/initial calls.
                memory_claim = (
                    "You have access to our full conversation history in your memory. Please use the perform_subjective_assessment tool if available, or respond using send_message with this exact format:\n"
                    if conversation_history
                    else "Please use the perform_subjective_assessment tool if available, or respond using send_message with this exact format:\n"
                )
                # Adjust conversation reference based on whether there's actual history
                conversation_reference = (
                    f"Based on our conversation about \"{topic}\""
                    if conversation_history
                    else f"Regarding the topic \"{topic}\""
                )
                
                # Add retry instruction if this is a retry attempt
                retry_instruction = ""
                if attempt > 0:
                    retry_instruction = """
IMPORTANT: Please provide NUMERIC SCORES (0-10) for ALL dimensions listed below. 
Your previous response was incomplete. Please respond ONLY with the exact format shown:
IMPORTANCE_TO_SELF: [number]
PERCEIVED_GAP: [number]
UNIQUE_PERSPECTIVE: [number]
EMOTIONAL_INVESTMENT: [number]
EXPERTISE_RELEVANCE: [number]
URGENCY: [number]
IMPORTANCE_TO_GROUP: [number]

Do not include any other text or explanation - just the scores in the exact format above.
"""
                
                assessment_prompt = f"""
{assessment_context}{conversation_reference}, please assess your motivation to contribute using the send_message tool.
{retry_instruction}

{memory_claim}
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

Please respond with the exact format shown above, providing numeric scores (0-10) for each dimension. If you have access to the perform_subjective_assessment tool, you may use it instead for more accurate assessment.
"""
            else:
                assessment_context = (
                    f"Conversation so far:\n{conversation_history}\n\n"
                    if conversation_history
                    else ""
                )
                memory_claim = (
                    "You have access to our full conversation history in your memory. Please review what has been discussed and rate each dimension from 0-10:\n"
                    if conversation_history
                    else "Please review the topic below and rate each dimension from 0-10.\n"
                )
                # Adjust conversation reference based on whether there's actual history
                conversation_reference = (
                    f"Based on our conversation about \"{topic}\""
                    if conversation_history
                    else f"Regarding the topic \"{topic}\""
                )
                
                # Add retry instruction if this is a retry attempt
                retry_instruction = ""
                if attempt > 0:
                    retry_instruction = """
IMPORTANT: Please respond ONLY with numbers in the exact format shown below.
Your previous response was incomplete or unclear. Please provide numeric scores (0-10) for ALL dimensions:
"""
                
                assessment_prompt = f"""
{assessment_context}{conversation_reference}, please assess your motivation to contribute.

{memory_claim}
{retry_instruction}
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

                track_action(
                    actor=self.name,
                    action_type="assessment_request",
                    details={
                        "topic": topic,
                        "has_conversation_history": bool(conversation_history),
                        "has_tools": has_tools,
                    },
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
                    # Check for tool_call_message type with send_message tool (new format)
                    if hasattr(msg, "message_type") and msg.message_type == "tool_call_message":
                        if hasattr(msg, "tool_call") and msg.tool_call:
                            if hasattr(msg.tool_call, "function") and msg.tool_call.function.name == "send_message":
                                track_tool_call(
                                    actor=self.name,
                                    tool_name="send_message",
                                    arguments={"message": "assessment_response"},
                                    result="success",
                                )
                    # Also check legacy format for backward compatibility
                    elif hasattr(msg, "tool_calls") and getattr(msg, "tool_calls"):
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
                                    result="success",
                                )

                candidate_texts = []
                for msg in response.messages:
                    # Check for tool_call_message type with send_message tool (new format)
                    if hasattr(msg, "message_type") and msg.message_type == "tool_call_message":
                        if hasattr(msg, "tool_call") and msg.tool_call:
                            if hasattr(msg.tool_call, "function") and msg.tool_call.function.name == "send_message":
                                try:
                                    import json as _json
                                    args = _json.loads(msg.tool_call.function.arguments)
                                    candidate_texts.append(args.get("message", ""))
                                except Exception:
                                    candidate_texts.append("")
                    # Also check legacy format for backward compatibility
                    elif hasattr(msg, "tool_calls") and getattr(msg, "tool_calls"):
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
                    # Accept any parsed scores, even partial ones (defaults fill gaps)
                    if scores and any(key in candidate.upper() for key in assessment_keys):
                        parsed_scores = scores
                        break
                    # Also accept if we got any numeric scores at all
                    elif scores and any(value != 5 for value in scores.values()):
                        parsed_scores = scores
                        break

                if parsed_dict is not None:
                    self.last_assessment = tools.SubjectiveAssessment(**parsed_dict)
                elif parsed_scores is not None:
                    self.last_assessment = tools.SubjectiveAssessment(**parsed_scores)
                elif response_text:
                    # Try one more time with the full response text
                    scores = self._parse_assessment_response(response_text)
                    # Accept if we got any non-default scores
                    if scores and any(value != 5 for value in scores.values()):
                        self.last_assessment = tools.SubjectiveAssessment(**scores)
                    else:
                        self.last_error = (
                            self.last_error
                            or "Assessment response did not include sufficient structured scores."
                        )
                        # If this is the first attempt, try again with clearer instructions
                        if attempt == 0:
                            attempt += 1
                            print(f"  [Retrying assessment with clearer instructions for {self.name}...]")
                            continue
                        else:
                            self.last_assessment = tools.perform_subjective_assessment(
                                topic, conversation_history, self.persona, self.expertise
                            )
                else:
                    self.last_error = (
                        self.last_error
                        or "Assessment response did not include structured scores."
                    )
                    # If this is the first attempt, try again with clearer instructions
                    if attempt == 0:
                        attempt += 1
                        print(f"  [Retrying assessment with clearer instructions for {self.name}...]")
                        continue
                    else:
                        self.last_assessment = tools.perform_subjective_assessment(
                            topic, conversation_history, self.persona, self.expertise
                        )

                break
            except Exception as e:
                self.last_error = str(e)
                if has_tools and self._is_tool_incompatibility_error(e):
                    if self._disable_assessment_tool(str(e)):
                        continue
                    self._tools_supported = False
                    continue

                print(f"  [Error getting assessment from {self.name}: {e}]")
                self.last_assessment = tools.perform_subjective_assessment(
                    topic, conversation_history, self.persona, self.expertise
                )
                break

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

    @staticmethod
    def _response_contains_send_message(response) -> bool:
        messages = getattr(response, "messages", []) or []
        for msg in messages:
            # Check for tool_call_message type with send_message tool
            if hasattr(msg, "message_type") and msg.message_type == "tool_call_message":
                if hasattr(msg, "tool_call") and msg.tool_call:
                    function = getattr(msg.tool_call, "function", None)
                    if function and getattr(function, "name", None) == "send_message":
                        return True
            # Also check legacy format for backward compatibility
            elif hasattr(msg, "tool_calls") and msg.tool_calls:
                for tool_call in msg.tool_calls:
                    function = getattr(tool_call, "function", None)
                    if function and getattr(function, "name", None) == "send_message":
                        return True
        return False

    @staticmethod
    def _wrap_response_with_send_message(message_text: str) -> SimpleNamespace:
        """Wraps a plain text message in a send_message tool call format."""
        import json

        tool_call = SimpleNamespace(
            function=SimpleNamespace(
                name="send_message",
                arguments=json.dumps({"message": message_text}),
            )
        )
        message_entry = SimpleNamespace(
            tool_calls=[tool_call],
            tool_return=None,
            content=None,
            message_type="tool_call",
        )
        return SimpleNamespace(messages=[message_entry])

    def _create_error_response(self, error_message: str, fallback_message: str = None) -> SimpleNamespace:
        """Creates an error response with informative content that includes the error details."""
        if fallback_message:
            error_content = f"⚠️ **Error encountered**: {error_message}\n\nFallback response: {fallback_message}"
        else:
            error_content = f"⚠️ **Error encountered**: {error_message}\n\nThe agent was unable to respond due to a technical issue."
        
        return self._wrap_response_with_send_message(error_content)

    def _ensure_send_message_response(self, response, message_text: str):
        if not message_text:
            return response
        if self._response_contains_send_message(response):
            return response
        wrapped = self._wrap_response_with_send_message(message_text)
        setattr(wrapped, "original_response", response)
        return wrapped

    def _extract_response_text(self, response) -> str:
        """Extract response text from agent messages, handling tool calls properly."""
        response_text = ""
        try:
            for msg in response.messages:
                # Check for tool_call_message type with send_message tool (new format)
                if hasattr(msg, "message_type") and msg.message_type == "tool_call_message":
                    if hasattr(msg, "tool_call") and msg.tool_call:
                        if hasattr(msg.tool_call, "function") and msg.tool_call.function.name == "send_message":
                            try:
                                import json
                                args = json.loads(msg.tool_call.function.arguments)
                                response_text = args.get("message", "")
                                break
                            except:
                                pass
                
                # Check for tool calls (send_message) - legacy format
                if not response_text and hasattr(msg, "tool_calls") and msg.tool_calls:
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
                if (
                    not response_text
                    and hasattr(msg, "tool_return")
                    and msg.tool_return
                ):
                    continue

                # Check assistant messages (direct responses)
                if (
                    not response_text
                    and (
                        (hasattr(msg, "message_type") and msg.message_type == "assistant_message")
                        or (hasattr(msg, "role") and msg.role == "assistant")
                    )
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
        # Ensure the topic is passed as the 'topic' parameter and not accidentally
        # treated as conversation_history by positional args.
        self._get_full_assessment(topic=topic)

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
                "will_participate": self.motivation_score
                >= config.PARTICIPATION_THRESHOLD,
                "assessment": assessment.model_dump(),
            },
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
            attachment.get("kind") == "image" for attachment in attachments
        )

        # Check for document attachments
        has_documents = any(
            attachment.get("kind") == "document" for attachment in attachments
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
        self,
        conversation_history: str = "",
        mode: str = "initial",
        topic: str = "",
        attachments: list = None,
    ):
        """Generates a response from the agent with conversation context."""
        # Select processing mode based on attachments
        selected_mode = self._select_mode_for_message(conversation_history, attachments)

        # Log mode selection for scaffolding
        print(
            f"[DEBUG] Agent {self.name} selected mode: {selected_mode} for message with {len(attachments or [])} attachments"
        )

        # Track the mode selection in session events
        if attachments:
            track_decision(
                actor=self.name,
                decision_type="mode_selection",
                details={
                    "selected_mode": selected_mode,
                    "attachments_count": len(attachments),
                    "has_images": any(
                        att.get("kind") == "image" for att in attachments
                    ),
                    "has_documents": any(
                        att.get("kind") == "document" for att in attachments
                    ),
                    "message_preview": (
                        conversation_history[:100]
                        if conversation_history
                        else topic[:100]
                    ),
                },
            )

        while True:
            has_tools = (
                self._tools_supported
                and hasattr(self.agent, "tools")
                and len(self.agent.tools) > 0
            )

            if conversation_history:
                if has_tools:
                    prompt = f"""{conversation_history}

Based on this conversation, I want to contribute. Please use the send_message tool to share your response. Remember to call the send_message function with your response as the message parameter."""
                else:
                    prompt = f"{conversation_history}\nBased on my assessment, here is my contribution:"
            else:
                if has_tools:
                    if mode == "initial":
                        prompt = f"""Based on my assessment of the topic '{topic}', I want to share my initial thoughts and perspective. Please use the send_message tool to contribute your viewpoint to this discussion. Remember to call the send_message function with your response as the message parameter."""
                    else:
                        prompt = f"""Based on what everyone has shared about '{topic}', I'd like to respond to the discussion. Please use the send_message tool to share your response, building on or reacting to what others have said. Remember to call the send_message function with your response as the message parameter."""
                else:
                    if mode == "initial":
                        prompt = f"Based on my assessment of '{topic}', here is my initial contribution:"
                    else:
                        prompt = f"Based on the discussion about '{topic}', here is my response:"

            try:
                self.last_error = None
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

                response_text = self._extract_response_text(response)
                
                # Check if we got a valid response with send_message OR a direct response with text
                if self._response_contains_send_message(response):
                    response = self._ensure_send_message_response(response, response_text)
                    if response_text:
                        track_message(
                            actor=self.name, content=response_text, message_type="assistant"
                        )
                    return response
                elif response_text and len(response_text.strip()) > 10:  # Accept direct responses with substantial content
                    # Agent responded directly without using send_message tool - this is acceptable
                    response = self._ensure_send_message_response(response, response_text)
                    track_message(
                        actor=self.name, content=response_text, message_type="assistant"
                    )
                    return response
                else:
                    # No valid response content found
                    error_msg = f"Agent {self.name} did not provide a valid response. Response format: {type(response).__name__}"
                    print(f"[Error: {error_msg}]")
                    
                    # If we got some minimal text, include it as fallback
                    if response_text:
                        return self._create_error_response(error_msg, response_text)
                    else:
                        return self._create_error_response(error_msg)
                        
            except Exception as e:
                self.last_error = str(e)
                if has_tools and self._is_tool_incompatibility_error(e):
                    if self._disable_assessment_tool(str(e)):
                        continue
                    self._tools_supported = False
                    continue

                if "No tool calls found" in str(e) and has_tools:
                    print(
                        f"[Debug: {self.name} didn't use tools, trying direct instruction]"
                    )
                    direct_prompt = (
                        "Please use the send_message tool to share your thoughts on the topic we've been discussing."
                    )
                    try:
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

                        direct_response_text = self._extract_response_text(response)
                        
                        # Check if the direct response uses send_message OR has valid content
                        if self._response_contains_send_message(response):
                            response = self._ensure_send_message_response(
                                response, direct_response_text
                            )
                            if direct_response_text:
                                track_message(
                                    actor=self.name,
                                    content=direct_response_text,
                                    message_type="assistant",
                                )
                            return response
                        elif direct_response_text and len(direct_response_text.strip()) > 10:  # Accept direct responses
                            response = self._ensure_send_message_response(
                                response, direct_response_text
                            )
                            track_message(
                                actor=self.name,
                                content=direct_response_text,
                                message_type="assistant",
                            )
                            return response
                        else:
                            # Still no valid response, create error response
                            error_msg = f"Agent {self.name} failed to provide a valid response even after direct instruction."
                            if direct_response_text:
                                return self._create_error_response(error_msg, direct_response_text)
                            else:
                                return self._create_error_response(error_msg)
                                
                    except Exception as direct_e:
                        # Direct instruction also failed
                        error_msg = f"Agent {self.name} failed to respond after direct instruction. Original error: {e}, Direct instruction error: {direct_e}"
                        return self._create_error_response(error_msg)
                
                # Other types of errors
                error_msg = f"Agent {self.name} encountered an error: {e}"
                return self._create_error_response(error_msg)
