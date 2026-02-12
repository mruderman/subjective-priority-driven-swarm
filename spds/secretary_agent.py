import json
import re
from datetime import datetime
from typing import Any, Dict, List, Optional

from letta_client import Letta
from letta_client.types import AgentState, CreateBlockParam, MessageCreateParam

from . import config
from .letta_api import letta_call
# spds/secretary_agent.py



class SecretaryAgent:
    """
    A specialized secretary agent that observes conversations and generates meeting minutes.
    Uses Letta agent AI to actively take notes and generate insights.
    """

    def __init__(self, client: Letta, mode: str = "adaptive"):
        self.client = client
        self.mode = mode  # "formal", "casual", or "adaptive"
        self.agent = None
        self.meeting_metadata = {}
        self.conversation_log: List[Any] = []
        self.action_items: List[Dict[str, Any]] = []
        self.decisions: List[Dict[str, Any]] = []

        # Conversations API routing (set by SwarmManager)
        self.conversation_id: str | None = None
        self._conversation_manager = None

        # Create the secretary agent
        self._create_secretary_agent()

    def _create_secretary_agent(self):
        """Creates or retrieves a specialized secretary agent using reuse-first policy."""

        # Generate unique name with timestamp to avoid conflicts
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        if self.mode == "formal":
            persona = (
                "I am the Recording Secretary for Cyan Society. I maintain professional "
                "board meeting minutes following nonprofit governance standards. I use "
                "formal language and ensure proper documentation of motions, decisions, "
                "and action items. I store meeting information in my memory and can generate "
                "comprehensive meeting minutes when requested."
            )
            name = f"Cyan Secretary {timestamp}"
        elif self.mode == "casual":
            persona = (
                "I'm a friendly meeting facilitator who takes great notes! I capture "
                "the energy and key insights from group discussions in a conversational, "
                "approachable style. I help teams remember what they decided and what "
                "comes next. I store conversation highlights in my memory."
            )
            name = f"Meeting Buddy {timestamp}"
        else:  # adaptive
            persona = (
                "I am an adaptive meeting secretary who adjusts my documentation style "
                "to match the conversation. I can switch between formal board meeting "
                "minutes and casual group discussion notes based on the context and tone. "
                "I actively listen to conversations, store key information in my memory, "
                "and generate appropriate meeting documentation when requested."
            )
            name = f"Adaptive Secretary {timestamp}"

        # Reuse-first policy: check configured ID or name before creating a new agent
        sec_id = config.get_secretary_agent_id()
        sec_name = config.get_secretary_agent_name()
        if sec_id:
            try:
                self.agent = letta_call(
                    "secretary.agent.retrieve",
                    self.client.agents.retrieve,
                    agent_id=sec_id,
                )
                print(f"✅ Reusing secretary agent by ID: {sec_id}")
                return
            except Exception as e:
                print(f"⚠️ Failed to retrieve secretary by ID {sec_id}: {e}")
        if sec_name:
            try:
                found = letta_call(
                    "secretary.agent.list",
                    self.client.agents.list,
                    name=sec_name,
                    limit=1,
                )
                if found:
                    self.agent = found[0]
                    print(f"✅ Reusing secretary agent by name: {sec_name}")
                    return
            except Exception as e:
                print(f"⚠️ Failed to find secretary by name {sec_name}: {e}")

        # If ephemeral creation is disabled by policy, do not create a new secretary
        if not config.get_allow_ephemeral_agents():
            raise RuntimeError(
                "Ephemeral creation disabled (SPDS_ALLOW_EPHEMERAL_AGENTS=false); set SECRETARY_AGENT_ID or SECRETARY_AGENT_NAME to reuse an existing secretary agent."
            )

        # Create new agent using proper Letta memory blocks pattern
        try:
            self.agent = letta_call(
                "secretary.agent.create",
                self.client.agents.create,
                name=name,
                memory_blocks=[
                    CreateBlockParam(
                        label="human",
                        value="I am working with a team of AI agents in group conversations and meetings.",
                    ),
                    CreateBlockParam(label="persona", value=persona),
                    CreateBlockParam(
                        label="meeting_context",
                        value="No active meeting. Ready to take notes when a meeting begins.",
                        description="Stores current meeting information, participants, topic, and ongoing notes",
                    ),
                    CreateBlockParam(
                        label="notes_style",
                        value=f"Documentation style: {self.mode}",
                        description="Preferred style for meeting documentation (formal, casual, or adaptive)",
                    ),
                ],
                model=config.DEFAULT_AGENT_MODEL,
                embedding=config.DEFAULT_EMBEDDING_MODEL,
                include_base_tools=True,
            )
            print(f"✅ Created new secretary agent: {name}")
        except Exception as e:
            print(f"❌ Failed to create secretary agent: {e}")
            raise

    def _send_to_agent(self, operation_name: str, messages):
        """Send messages to the secretary agent, routing through conversations when available.

        Args:
            operation_name: Descriptive name for letta_call logging.
            messages: List of MessageCreateParam (dicts) or message-like objects.

        Returns:
            The response (or response-like object from send_and_collect).
        """
        if self.conversation_id and self._conversation_manager:
            # MessageCreateParam is a TypedDict, so messages are dicts
            dict_msgs = []
            for m in messages:
                if isinstance(m, dict):
                    dict_msgs.append(m)
                else:
                    dict_msgs.append({"role": m.role, "content": m.content})
            return letta_call(
                operation_name,
                self._conversation_manager.send_and_collect,
                conversation_id=self.conversation_id,
                messages=dict_msgs,
            )
        return letta_call(
            operation_name,
            self.client.agents.messages.create,
            agent_id=self.agent.id,
            messages=messages,
        )

    def set_mode(self, mode: str):
        """Change the secretary's documentation mode."""
        if mode not in ["formal", "casual", "adaptive"]:
            raise ValueError("Mode must be 'formal', 'casual', or 'adaptive'")

        self.mode = mode
        print(f"📝 Secretary mode changed to: {mode}")

    def start_meeting(
        self, topic: str, participants: List[str], meeting_type: str = "discussion"
    ):
        """Initialize meeting using agent communication."""
        self.meeting_metadata = {
            "topic": topic,
            "participants": participants,
            "meeting_type": meeting_type,
            "start_time": datetime.now(),
            "mode": self.mode,
            "conversation_mode": None,  # Will be set by SwarmManager
        }

        # For backward compatibility, log meeting start
        self.conversation_log.append(("system", f"Meeting started: {topic}"))

        # Send meeting start message to the secretary agent
        meeting_start_message = (
            f"A new {meeting_type} meeting has started.\n"
            f"Topic: {topic}\n"
            f"Participants: {', '.join(participants)}\n"
            f"Please begin taking notes in {self.mode} style. "
            f"Store the meeting information in your memory and prepare to document the conversation. "
            f"Please use the send_message tool to acknowledge that you're ready to take notes."
        )

        try:
            response = self._send_to_agent(
                "secretary.meeting.start",
                [MessageCreateParam(role="user", content=meeting_start_message)],
            )
            if response:
                print(f"📋 Meeting started: {topic}")
                print(f"👥 Participants: {', '.join(participants)}")
                secretary_response = self._extract_agent_response(response)
                print(f"🤖 Secretary: {secretary_response}")

            else:
                print(f"⚠️ Secretary may not have received meeting start notification")
        except Exception as e:
            print(f"❌ Failed to notify secretary of meeting start: {e}")

    def _extract_agent_response(self, response) -> str:
        """Extract the main response from agent messages, handling tool calls properly."""
        message_text = ""
        try:
            for msg in response.messages:
                # Check for tool calls first (send_message)
                if hasattr(msg, "tool_calls") and msg.tool_calls:
                    for tool_call in msg.tool_calls:
                        if (
                            hasattr(tool_call, "function")
                            and tool_call.function.name == "send_message"
                        ):
                            try:
                                import json

                                args = json.loads(tool_call.function.arguments)
                                message_text = args.get("message", "")
                                break
                            except Exception:
                                pass

                # Check for tool return messages (when agent uses send_message)
                if not message_text and hasattr(msg, "tool_return") and msg.tool_return:
                    # Tool returns often contain status messages we can ignore
                    continue

                # Check assistant messages (direct responses without tools)
                if (
                    not message_text
                    and hasattr(msg, "message_type")
                    and msg.message_type == "assistant_message"
                ):
                    if hasattr(msg, "content") and msg.content:
                        message_text = msg.content

                # If no tool call, try regular content extraction
                if not message_text and hasattr(msg, "content"):
                    if isinstance(msg.content, str):
                        message_text = msg.content
                    elif isinstance(msg.content, list) and msg.content:
                        content_item = msg.content[0]
                        if hasattr(content_item, "text"):
                            message_text = content_item.text
                        elif isinstance(content_item, str):
                            message_text = content_item

                if message_text:
                    break

            if not message_text:
                message_text = "Secretary is ready to take notes."

        except Exception as e:
            message_text = "Secretary is ready to take notes."
            print(f"[Debug: Error extracting secretary response - {e}]")

        return message_text

    def observe_message(
        self, speaker: str, message: str, metadata: Optional[Dict] = None
    ):
        """Send conversation message to the secretary agent for active processing."""
        if not self.agent:
            return

        # For backward compatibility, log the message
        self.conversation_log.append((speaker, message))

        # Format message for the secretary
        formatted_message = f"{speaker}: {message}"

        # Send to secretary agent for processing and note-taking
        try:
            self._send_to_agent(
                "secretary.message.observe",
                [MessageCreateParam(
                    role="user",
                    content=f"Please note this in the meeting: {formatted_message}",
                )],
            )

        except Exception as e:
            # Don't print for every message - too noisy
            pass

    # Removed old static implementations - now using AI agent for everything

    def add_action_item(
        self, description: str, assignee: str = None, due_date: str = None
    ):
        """Manually add an action item through the secretary agent."""
        # For backward compatibility
        self.action_items.append(description)
        if not self.agent:
            print(f"⚠️ Secretary agent not available")
            return

        action_message = f"Please record this action item: {description}"
        if assignee:
            action_message += f" (assigned to: {assignee})"
        if due_date:
            action_message += f" (due: {due_date})"

        try:
            self._send_to_agent(
                "secretary.action_item.add",
                [MessageCreateParam(role="user", content=action_message)],
            )
            print(f"✅ Action item recorded: {description}")

        except Exception as e:
            print(f"❌ Failed to record action item: {e}")

    def add_decision(self, decision: str, context: str = None):
        """Manually record a decision through the secretary agent."""
        # For backward compatibility
        self.decisions.append({"decision": decision, "context": context})
        if not self.agent:
            print(f"⚠️ Secretary agent not available")
            return

        decision_message = f"Please record this decision: {decision}"
        if context:
            decision_message += f" (context: {context})"

        try:
            self._send_to_agent(
                "secretary.decision.record",
                [MessageCreateParam(role="user", content=decision_message)],
            )
            print(f"📋 Decision recorded: {decision}")

        except Exception as e:
            print(f"❌ Failed to record decision: {e}")

    def get_conversation_stats(self) -> Dict[str, Any]:
        """Get conversation statistics from the secretary agent."""
        if not self.agent:
            return {}

        try:
            response = self._send_to_agent(
                "secretary.stats.get",
                [MessageCreateParam(
                    role="user",
                    content="Please provide a summary of the meeting statistics - how many messages, participants, decisions, action items, etc. Please use the send_message tool to provide your response.",
                )],
            )

            stats_text = self._extract_agent_response(response)

            # Parse basic stats from the meeting metadata
            if self.meeting_metadata:
                duration = (
                    datetime.now() - self.meeting_metadata["start_time"]
                ).seconds // 60
                return {
                    "duration_minutes": duration,
                    "participants": self.meeting_metadata.get("participants", []),
                    "topic": self.meeting_metadata.get("topic", "Unknown"),
                    "meeting_type": self.meeting_metadata.get(
                        "meeting_type", "discussion"
                    ),
                    "summary": stats_text,
                }

            return {"summary": stats_text}

        except Exception as e:
            print(f"❌ Failed to get conversation stats: {e}")
            return {}

    def generate_minutes(self) -> str:
        """Generate meeting minutes using the secretary agent's AI capabilities."""
        if not self.agent:
            return "Secretary agent not available."

        if not self.meeting_metadata:
            return "No meeting in progress."

        # Ask the secretary agent to generate meeting minutes
        minutes_request = (
            f"Please generate meeting minutes for our {self.meeting_metadata.get('meeting_type', 'discussion')} "
            f"about '{self.meeting_metadata.get('topic', 'Unknown Topic')}'. "
            f"Use {self.mode} style documentation. "
            f"Include all the key points, decisions, and action items from the conversation you've been observing. "
            f"Format the minutes appropriately for the meeting type. "
            f"Please use the send_message tool to provide your response, with the formatted meeting minutes as the message parameter."
        )

        try:
            response = self._send_to_agent(
                "secretary.minutes.generate",
                [MessageCreateParam(role="user", content=minutes_request)],
            )
            if response:
                # Extract the agent's response
                minutes = self._extract_agent_response(response)
                if minutes and len(minutes) > 50:  # Ensure we got substantial content
                    return minutes
                else:
                    return "Secretary is still processing the meeting notes. Please try again in a moment."
            else:
                return "Secretary is temporarily unavailable. Please try again."

        except Exception as e:
            print(f"❌ Failed to generate minutes: {e}")
            return f"Error generating minutes: {str(e)[:100]}..."
