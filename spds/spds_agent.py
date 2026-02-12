# spds/spds_agent.py

import logging
import re
from types import SimpleNamespace

from letta_client import Letta
from letta_client.types import AgentState
from pydantic import BaseModel

from . import config, tools
from .letta_api import letta_call
from .message import ConversationMessage, messages_to_flat_format
from .session_tracking import (
    track_action,
    track_decision,
    track_message,
    track_tool_call,
)
try:
    from letta_client import APIError as ApiError
except ImportError:  # pragma: no cover
    ApiError = None  # type: ignore


logger = logging.getLogger(__name__)


def format_group_message(conversation_history: str, current_speaker: str = None) -> str:
    """Format group conversation history for system messages with clear speaker indication.

    Args:
        conversation_history: The conversation text to format
        current_speaker: Optional current speaker name to highlight

    Returns:
        Formatted message with dividers and speaker emphasis
    """
    divider = "=" * 80

    if current_speaker:
        header = f"CURRENT SPEAKER: {current_speaker.upper()}"
        formatted = f"{divider}\n{header}\n{divider}\n\n{conversation_history}\n\n{divider}"
    else:
        formatted = f"{divider}\nGROUP CONVERSATION\n{divider}\n\n{conversation_history}\n\n{divider}"

    return formatted


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
        self.roles: list = []  # Roles assigned to this agent (e.g., "secretary")

        # Conversations API routing (set by SwarmManager when session conversations are active)
        self.conversation_id: str | None = None
        self._conversation_manager = None

    @classmethod
    def create_new(
        cls,
        name: str,
        persona: str,
        expertise: list,
        client: Letta,
        model: str = None,
        embedding: str = None,
        include_multi_agent_tools: bool = False,
        tags: list = None,
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

        create_kwargs = dict(
            name=name,
            system=system_prompt,
            model=agent_model,
            embedding=agent_embedding,
            include_base_tools=True,
        )
        if include_multi_agent_tools:
            create_kwargs["include_multi_agent_tools"] = True
        if tags:
            create_kwargs["tags"] = tags

        agent_state = letta_call(
            "agent.create",
            client.agents.create,
            **create_kwargs,
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
                    f"Recent messages since your last turn:\n{conversation_history}\n\n"
                    if conversation_history
                    else "This is the start of the conversation.\n\n"
                )
                # Adjust conversation reference to emphasize current conversation context
                conversation_reference = (
                    f"Based on these recent messages (current focus: \"{topic}\")"
                    if conversation_history
                    else f"Regarding the topic \"{topic}\""
                )

                # Add retry instruction if this is a retry attempt
                retry_instruction = ""
                if attempt > 0:
                    retry_instruction = """
IMPORTANT: Your previous response was incomplete. Please use the perform_subjective_assessment tool with the parameters shown below, or use send_message with numeric scores.
"""

                assessment_prompt = f"""
{assessment_context}{conversation_reference}, please assess your motivation to contribute to the CURRENT conversation state.
{retry_instruction}

**PRIMARY METHOD: Use the perform_subjective_assessment tool**

Call the perform_subjective_assessment tool with these parameters:
- topic: "{topic}"
- conversation_history: "{conversation_history[-500:] if conversation_history else topic}"
- agent_persona: "{self.persona}"
- agent_expertise: {self.expertise}

This tool will automatically evaluate all 7 assessment dimensions and return a structured result.

**FALLBACK METHOD (only if the tool is unavailable):**

If you cannot access the perform_subjective_assessment tool, use send_message with this exact format:

IMPORTANCE_TO_SELF: X
PERCEIVED_GAP: X
UNIQUE_PERSPECTIVE: X
EMOTIONAL_INVESTMENT: X
EXPERTISE_RELEVANCE: X
URGENCY: X
IMPORTANCE_TO_GROUP: X

Where each dimension is scored 0-10:
1. IMPORTANCE_TO_SELF: How personally significant is the CURRENT conversation direction to you?
2. PERCEIVED_GAP: Are there crucial points missing from the RECENT discussion?
3. UNIQUE_PERSPECTIVE: Do you have insights that haven't been shared in the CURRENT conversation?
4. EMOTIONAL_INVESTMENT: How much do you care about the current discussion outcome?
5. EXPERTISE_RELEVANCE: How applicable is your domain knowledge to what's being discussed NOW?
6. URGENCY: How time-sensitive are the current discussion points?
7. IMPORTANCE_TO_GROUP: What's the potential impact on the group's current understanding?

Focus on the EVOLVING conversation, not just the original topic. Consider what has actually been discussed recently and whether you can add value to the current direction.
"""
            else:
                assessment_context = (
                    f"Recent messages since your last turn:\n{conversation_history}\n\n"
                    if conversation_history
                    else "This is the start of the conversation.\n\n"
                )
                memory_claim = (
                    "You have access to the full conversation history in your recall memory. "
                    "The messages shown below are NEW since your last turn. "
                    "Please review these recent messages and assess each dimension (0-10):\n"
                    if conversation_history
                    else "This is the start of the conversation. Please review the topic below "
                    "and assess each dimension (0-10):\n"
                )
                # Adjust conversation reference to emphasize current conversation context
                conversation_reference = (
                    f"Based on these recent messages (current focus: \"{topic}\")"
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
{assessment_context}{conversation_reference}, please assess your motivation to contribute to the CURRENT conversation state.

{memory_claim}
{retry_instruction}
1. IMPORTANCE_TO_SELF: How personally significant is the CURRENT conversation direction to you?
2. PERCEIVED_GAP: Are there crucial points missing from the RECENT discussion?
3. UNIQUE_PERSPECTIVE: Do you have insights that haven't been shared in the CURRENT conversation?
4. EMOTIONAL_INVESTMENT: How much do you care about the current discussion outcome?
5. EXPERTISE_RELEVANCE: How applicable is your domain knowledge to what's being discussed NOW?
6. URGENCY: How time-sensitive are the current discussion points?
7. IMPORTANCE_TO_GROUP: What's the potential impact on the group's current understanding?

Focus on the EVOLVING conversation, not just the original topic. Consider what has actually been discussed recently and whether you can add value to the current direction.

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
                    # Check for tool_call_message type (new format)
                    if hasattr(msg, "message_type") and msg.message_type == "tool_call_message":
                        if hasattr(msg, "tool_call") and msg.tool_call:
                            tool_name = msg.tool_call.function.name if hasattr(msg.tool_call, "function") else None
                            if tool_name == "send_message":
                                track_tool_call(
                                    actor=self.name,
                                    tool_name="send_message",
                                    arguments={"message": "assessment_response"},
                                    result="success",
                                )
                            elif tool_name == "perform_subjective_assessment":
                                track_tool_call(
                                    actor=self.name,
                                    tool_name="perform_subjective_assessment",
                                    arguments={"assessment": "tool_based"},
                                    result="success",
                                )
                                print(f"  [{self.name} used perform_subjective_assessment tool ✓]")
                    # Also check legacy format for backward compatibility
                    elif hasattr(msg, "tool_calls") and getattr(msg, "tool_calls"):
                        for tool_call in msg.tool_calls:
                            if hasattr(tool_call, "function"):
                                tool_name = getattr(tool_call.function, "name", None)
                                if tool_name == "send_message":
                                    track_tool_call(
                                        actor=self.name,
                                        tool_name="send_message",
                                        arguments={"message": "assessment_response"},
                                        result="success",
                                    )
                                elif tool_name == "perform_subjective_assessment":
                                    track_tool_call(
                                        actor=self.name,
                                        tool_name="perform_subjective_assessment",
                                        arguments={"assessment": "tool_based"},
                                        result="success",
                                    )
                                    print(f"  [{self.name} used perform_subjective_assessment tool ✓]")

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
                self._assessment_tool_disabled = True
                self.assessment_tool = None
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

    def _get_diagnostic_context(self) -> dict:
        """
        Gather diagnostic context for error reporting and debugging.

        Returns a structured dict with agent configuration and state information
        that can be used to diagnose issues with agent responses.

        Returns:
            dict: Diagnostic information including agent ID, model, tools, state
        """
        return {
            "agent_id": self.agent.id,
            "agent_name": self.name,
            "model": getattr(self.agent, "model", "unknown"),
            "embedding": getattr(self.agent, "embedding", "unknown"),
            "tools": [t.name for t in getattr(self.agent, "tools", [])],
            "has_send_message": any(
                t.name == "send_message"
                for t in getattr(self.agent, "tools", [])
            ),
            "tools_supported": self._tools_supported,
            "assessment_tool_disabled": self._assessment_tool_disabled,
            "last_error": self.last_error,
            "motivation_score": self.motivation_score,
            "priority_score": self.priority_score,
        }

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

    def _create_error_response(
        self,
        error_message: str,
        fallback_message: str = None,
        diagnostic_context: dict = None
    ) -> SimpleNamespace:
        """
        Creates an error response with diagnostic information.

        Args:
            error_message: Primary error description
            fallback_message: Optional fallback text to include
            diagnostic_context: Optional diagnostic info (from _get_diagnostic_context())

        Returns:
            SimpleNamespace with error response message
        """
        diag = diagnostic_context or {}

        # Build detailed error message with diagnostics
        error_details = [
            f"⚠️ **Agent Error**: {self.name}",
            f"Model: {diag.get('model', 'unknown')}",
            f"Tools supported: {diag.get('tools_supported', 'unknown')}",
            f"Has send_message: {diag.get('has_send_message', 'unknown')}",
            f"Error: {error_message}",
        ]

        if diag.get('last_error'):
            error_details.append(f"Last tool error: {diag['last_error']}")

        error_content = "\n".join(error_details)

        if fallback_message:
            error_content += f"\n\nFallback: {fallback_message}"

        # Log full diagnostic context for debugging
        logger.error(
            f"Agent {self.name} error response created",
            extra={
                "agent_id": diag.get("agent_id"),
                "agent_name": self.name,
                "model": diag.get("model"),
                "error": error_message,
                "diagnostic_context": diag,
            }
        )

        return SimpleNamespace(
            messages=[
                {
                    "role": "assistant",
                    "content": error_content,
                }
            ]
        )

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
                # Skip user messages - these are the prompts we sent to the agent, not responses
                if (hasattr(msg, "message_type") and msg.message_type == "user_message") or \
                   (hasattr(msg, "role") and msg.role == "user"):
                    continue

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

    def assess_motivation_and_priority(self, recent_messages: list[ConversationMessage], original_topic: str):
        """Performs the full assessment and calculates motivation and priority scores.
        
        Args:
            recent_messages: List of ConversationMessage objects since agent's last turn
            original_topic: The original meeting topic for context
        """
        # Convert recent messages to conversation history format and pass with original topic
        conversation_history = messages_to_flat_format(recent_messages) if recent_messages else ""
        self._get_full_assessment(conversation_history=conversation_history, topic=original_topic)

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
                "topic": original_topic,
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
                # Format group conversation with proper dividers and speaker indication
                formatted_history = format_group_message(conversation_history, self.name)

                if has_tools:
                    # Simple, direct instruction without forcing
                    prompt = "Please share your response to the conversation using the send_message tool."
                else:
                    prompt = "Please share your response to the conversation."

                # Use system role for group conversation history, user role for instruction
                messages = [
                    {
                        "role": "system",
                        "content": formatted_history,
                    },
                    {
                        "role": "user",
                        "content": prompt,
                    }
                ]
            else:
                if has_tools:
                    if mode == "initial":
                        prompt = f"Please share your initial thoughts on '{topic}' using the send_message tool."
                    else:
                        prompt = f"Please respond to the discussion about '{topic}' using the send_message tool."
                else:
                    if mode == "initial":
                        prompt = f"Please share your initial thoughts on '{topic}'."
                    else:
                        prompt = f"Please respond to the discussion about '{topic}'."

                messages = [
                    {
                        "role": "user",
                        "content": prompt,
                    }
                ]

            try:
                self.last_error = None
                if self.conversation_id and self._conversation_manager:
                    response = letta_call(
                        "conversations.send_and_collect.speak",
                        self._conversation_manager.send_and_collect,
                        conversation_id=self.conversation_id,
                        messages=messages,
                    )
                else:
                    response = letta_call(
                        "agents.messages.create.speak",
                        self.client.agents.messages.create,
                        agent_id=self.agent.id,
                        messages=messages,
                    )

                response_text = self._extract_response_text(response)

                # Log response structure for debugging
                logger.debug(
                    f"[{self.name}] Response received",
                    extra={
                        "response_type": type(response).__name__,
                        "message_count": len(getattr(response, "messages", [])),
                        "message_types": [
                            getattr(m, "message_type", type(m).__name__)
                            for m in getattr(response, "messages", [])
                        ],
                    }
                )

                # Get diagnostic context for validation logging
                diagnostic_ctx = self._get_diagnostic_context()

                # Check if we got a valid response with send_message OR a direct response with text
                if self._response_contains_send_message(response):
                    logger.debug(f"[{self.name}] Response contains send_message tool call")
                    response = self._ensure_send_message_response(response, response_text)
                    if response_text:
                        track_message(
                            actor=self.name, content=response_text, message_type="assistant"
                        )
                    return response
                elif response_text and len(response_text.strip()) > 10:  # Accept direct responses with substantial content
                    # Agent responded directly without using send_message tool - this is acceptable
                    logger.debug(
                        f"[{self.name}] Direct response accepted",
                        extra={"response_length": len(response_text)}
                    )
                    response = self._ensure_send_message_response(response, response_text)
                    track_message(
                        actor=self.name, content=response_text, message_type="assistant"
                    )
                    return response
                else:
                    # No valid response content found - log detailed validation failure
                    logger.warning(
                        f"[{self.name}] Response validation failed",
                        extra={
                            "has_send_message": False,
                            "response_length": len(response_text) if response_text else 0,
                            "response_text_preview": response_text[:100] if response_text else "",
                            "diagnostic_context": diagnostic_ctx,
                        }
                    )

                    error_msg = (
                        f"Agent {self.name} validation failed: "
                        f"no send_message tool call, "
                        f"response_length={len(response_text) if response_text else 0}"
                    )

                    # Pass diagnostic context to error response
                    if response_text:
                        return self._create_error_response(error_msg, response_text, diagnostic_ctx)
                    else:
                        return self._create_error_response(error_msg, None, diagnostic_ctx)
                        
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
