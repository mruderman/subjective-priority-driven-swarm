# spds/swarm_manager.py

import time
import uuid

from letta_client import Letta
from letta_client.errors import NotFoundError

from . import config
from .config import logger
from .export_manager import ExportManager
from .letta_api import letta_call
from .memory_awareness import create_memory_awareness_for_agent
from .secretary_agent import SecretaryAgent
from .session_tracking import track_action, track_message, track_system_event
from .spds_agent import SPDSAgent


class SwarmManager:
    def __init__(
        self,
        client: Letta,
        agent_profiles: list = None,
        agent_ids: list = None,
        agent_names: list = None,
        conversation_mode: str = "hybrid",
        enable_secretary: bool = False,
        secretary_mode: str = "adaptive",
        meeting_type: str = "discussion",
    ):
        """
        Initialize the SwarmManager, load or create agents, and configure meeting and secretary settings.

        This constructor prepares internal state and populates self.agents using one of three input paths:
        - agent_ids: load existing agents by their IDs
        - agent_names: load existing agents by name (first match per name)
        - agent_profiles: create temporary agents from supplied profile dicts

        It also initializes conversation state, an ExportManager, and—if enabled—creates a SecretaryAgent. The chosen conversation_mode is validated.

        Parameters described when helpful:
            agent_profiles (list, optional): Profiles used to create temporary agents when agent_ids and agent_names are not provided.
            agent_ids (list, optional): List of existing agent IDs to load from the Letta backend.
            agent_names (list, optional): List of agent names to look up and load (uses the first match per name).
            conversation_mode (str, optional): Turn-taking mode. Valid values: "hybrid", "all_speak", "sequential", "pure_priority".
            enable_secretary (bool, optional): If True, attempts to create a SecretaryAgent to observe and assist the meeting.
            secretary_mode (str, optional): Mode passed to the SecretaryAgent when enable_secretary is True.
            meeting_type (str, optional): Descriptive meeting type stored in meeting metadata (e.g., "discussion").

        Raises:
            ValueError: If no agents are loaded/created or if conversation_mode is not one of the valid modes.
        """
        self.client = client
        self.agents = []
        self.enable_secretary = enable_secretary
        self.secretary = None
        self.export_manager = ExportManager()
        # Track whether the Letta client supports the optional otid parameter; lazily detected.
        self._agent_messages_supports_otid = None

        logger.info(f"Initializing SwarmManager in {conversation_mode} mode.")

        if agent_ids:
            self._load_agents_by_id(agent_ids)
        elif agent_names:
            self._load_agents_by_name(agent_names)
        elif agent_profiles:
            if config.get_allow_ephemeral_agents():
                self._create_agents_from_profiles(agent_profiles)
            else:
                logger.error(
                    "Ephemeral agent creation is disabled (SPDS_ALLOW_EPHEMERAL_AGENTS=false). "
                    "Provide existing agent IDs or names instead of profiles."
                )

        if not self.agents:
            logger.error("Swarm manager initialized with no agents.")
            raise ValueError(
                "Swarm manager initialized with no agents. Please provide profiles, IDs, or names."
            )

        logger.info(f"Swarm initialized with {len(self.agents)} agents.")

        self.conversation_history = ""
        self.last_speaker = None  # For fairness tracking
        self.conversation_mode = conversation_mode
        self.meeting_type = meeting_type

        # Initialize secretary if enabled
        if enable_secretary:
            try:
                self.secretary = SecretaryAgent(client, mode=secretary_mode)
                logger.info(f"Secretary enabled in {secretary_mode} mode")
            except Exception as e:
                logger.error(f"Failed to create secretary agent: {e}")
                self.enable_secretary = False

        # Validate conversation mode
        valid_modes = ["hybrid", "all_speak", "sequential", "pure_priority"]
        if conversation_mode not in valid_modes:
            logger.error(f"Invalid conversation mode: {conversation_mode}")
            raise ValueError(
                f"Invalid conversation mode: {conversation_mode}. Valid modes: {valid_modes}"
            )

    def _emit(self, message: str, *, level: str = "info") -> None:
        """Print a user-facing message and log it at the requested level."""
        # Add historical prefixes for stdout to satisfy test assertions
        display_message = message
        if level == "warning" and not message.startswith("WARNING:"):
            display_message = f"WARNING: {message}"
        elif level == "error" and message.startswith("[Debug:"):
            # Keep debug messages as-is since they already have the expected format
            display_message = message

        print(display_message)
        # Log the original message without prefixes for structured logging
        log_fn = getattr(logger, level, logger.info)
        log_fn(message)

    def _call_agent_message_create(
        self,
        operation_name: str,
        *,
        agent_id: str,
        messages: list,
    ):
        """Invoke the Letta agent messages.create endpoint with optional otid support."""

        # Ensure attribute exists even for tests constructing via object.__new__
        if not hasattr(self, "_agent_messages_supports_otid"):
            self._agent_messages_supports_otid = None

        include_otid = self._agent_messages_supports_otid is not False
        call_kwargs = {
            "agent_id": agent_id,
            "messages": messages,
        }

        if include_otid:
            call_kwargs["otid"] = str(uuid.uuid4())

        try:
            result = letta_call(
                operation_name,
                self.client.agents.messages.create,
                **call_kwargs,
            )
            if self._agent_messages_supports_otid is None and include_otid:
                self._agent_messages_supports_otid = True
            return result
        except TypeError as exc:
            exc_message = str(exc).lower()
            if include_otid and "otid" in exc_message:
                # Retry without otid and remember the capability for subsequent calls.
                self._agent_messages_supports_otid = False
                call_kwargs.pop("otid", None)
                return letta_call(
                    operation_name,
                    self.client.agents.messages.create,
                    **call_kwargs,
                )
            raise

    def _load_agents_by_id(self, agent_ids: list):
        """Loads existing agents from the Letta server by their IDs."""
        self._emit("Loading swarm from existing agent IDs...")
        for agent_id in agent_ids:
            try:
                self._emit(f"Retrieving agent: {agent_id}")
                agent_state = letta_call(
                    "agents.retrieve", self.client.agents.retrieve, agent_id=agent_id
                )
                self.agents.append(SPDSAgent(agent_state, self.client))
            except NotFoundError:
                self._emit(
                    f"Agent with ID '{agent_id}' not found. Skipping.",
                    level="warning",
                )

    def _load_agents_by_name(self, agent_names: list):
        """
        Load existing agents from the Letta server by name and append them (wrapped as SPDSAgent) to self.agents.

        This searches each name with client.agents.list(name=<name>, limit=1) and uses the first match if present; missing names are skipped and a warning is logged. Mutates self.agents by appending SPDSAgent instances for found agents.

        Parameters:
            agent_names (list[str]): Iterable of agent display names to look up; each name is matched with a single result (the first match).
        """
        self._emit("Loading swarm from existing agent names...")
        for name in agent_names:
            self._emit(f"Retrieving agent by name: {name}")
            # The list method with a name filter returns a list. We'll take the first one.
            found_agents = letta_call(
                "agents.list", self.client.agents.list, name=name, limit=1
            )
            if not found_agents:
                self._emit(
                    f"Agent with name '{name}' not found. Skipping.",
                    level="warning",
                )
                continue
            self.agents.append(SPDSAgent(found_agents[0], self.client))

    def _create_agents_from_profiles(self, agent_profiles: list):
        """
        Create temporary SPDSAgent instances from profile dictionaries and add them to self.agents.

        Each profile in agent_profiles should be a dict with at least the keys:
        - "name": display name for the agent
        - "persona": short persona/system prompt text
        - "expertise": brief expertise description

        Optional keys:
        - "model": model identifier to use for the agent
        - "embedding": embedding model identifier or config

        Side effects:
        - Calls SPDSAgent.create_new(...) for each profile (may create transient agents on the backend).
        - Appends each successfully created SPDSAgent to self.agents.
        - Logs creation duration and errors for individual profiles.

        Parameters:
            agent_profiles (list): Iterable of profile dicts as described above.

        Returns:
            None
        """
        logger.info("Creating swarm from temporary agent profiles...")
        if not config.get_allow_ephemeral_agents():
            raise ValueError(
                "Ephemeral agent creation is disabled by policy. Supply agent_ids or agent_names instead."
            )
        for profile in agent_profiles:
            start_time = time.time()
            logger.info(f"Creating agent: {profile['name']}")
            try:
                agent = SPDSAgent.create_new(
                    name=profile["name"],
                    persona=profile["persona"],
                    expertise=profile["expertise"],
                    client=self.client,
                    model=profile.get("model"),
                    embedding=profile.get("embedding"),
                )
                self.agents.append(agent)
                duration = time.time() - start_time
                logger.info(
                    f"Agent {profile['name']} created in {duration:.2f} seconds."
                )
            except Exception as e:
                logger.error(f"Failed to create agent {profile['name']}: {e}")

    def start_chat(self):
        """
        Start an interactive group chat session with the swarm.

        Prompts the user for a topic, initializes the meeting, and enters a read-eval loop accepting user messages until the user types "quit" or sends EOF (Ctrl+D). Each user message is appended to the manager's conversation_history, optionally forwarded to the configured secretary for observation, and then triggers a coordinated agent turn via _agent_turn(topic). Lines beginning with "/" are interpreted as secretary commands and handled by _handle_secretary_commands.

        Side effects:
        - Reads from standard input.
        - Mutates self.conversation_history and meeting state.
        - Calls _start_meeting, _agent_turn, and _end_meeting.
        - May call secretary.observe_message when a secretary is enabled.

        Returns:
            None
        """
        self._emit("Swarm chat started. Type 'quit' or Ctrl+D to end the session.")
        try:
            topic = input("Enter the topic of conversation: ")
        except EOFError:
            self._emit("Exiting.")
            return

        self._emit(
            f"Swarm chat started with topic: '{topic}' (Mode: {self.conversation_mode.upper()})"
        )
        self._start_meeting(topic)

        while True:
            try:
                human_input = input("\nYou: ")
            except EOFError:
                self._emit("Exiting chat.")
                break

            if human_input.lower() == "quit":
                self._emit("Exiting chat.")
                break

            # Check for secretary commands
            if self._handle_secretary_commands(human_input):
                continue

            self.conversation_history += f"You: {human_input}\n"

            # Let secretary observe the human message
            if self.secretary:
                self.secretary.observe_message("You", human_input)

            self._agent_turn(topic)

        self._end_meeting()

    def start_chat_with_topic(self, topic: str):
        """
        Start and manage an interactive group chat session using a preset topic.

        This begins a meeting for the given topic, enters a read-eval loop that accepts human input,
        dispatches secretary commands (if enabled), appends user messages to the shared conversation
        history, notifies the secretary of human messages, and triggers agent turns until the user
        exits. The loop exits when the user types "quit" or sends EOF (Ctrl+D).

        Parameters:
            topic (str): The discussion topic used to initialize meeting context and inform agents.

        Side effects:
            - Calls self._start_meeting(topic) at start and self._end_meeting() on exit.
            - Appends user messages to self.conversation_history.
            - If a secretary is enabled, calls secretary.observe_message("You", message) for each user input.
            - Calls self._agent_turn(topic) after each user message to drive agent responses.

        Returns:
            None
        """
        self._emit(
            f"Swarm chat started with topic: '{topic}' (Mode: {self.conversation_mode.upper()})"
        )
        if self.secretary:
            self._emit(
                f"Secretary: {self.secretary.agent.name if self.secretary.agent else 'Recording'} ({self.secretary.mode} mode)"
            )
        self._emit("Type 'quit' or Ctrl+D to end the session.")
        self._emit(
            "Available commands: /minutes, /export, /formal, /casual, /action-item"
        )

        self._start_meeting(topic)

        while True:
            try:
                human_input = input("\nYou: ")
            except EOFError:
                self._emit("Exiting chat.")
                break

            if human_input.lower() == "quit":
                self._emit("Exiting chat.")
                break

            # Check for secretary commands
            if self._handle_secretary_commands(human_input):
                continue

            self.conversation_history += f"You: {human_input}\n"

            # Track user message
            track_message(actor="user", content=human_input, message_type="user")

            # Let secretary observe the human message
            if self.secretary:
                self.secretary.observe_message("You", human_input)

            self._agent_turn(topic)

        self._end_meeting()

    def _update_agent_memories(
        self, message: str, speaker: str = "User", max_retries=3
    ):
        """
        Broadcast a user message to every agent to update their memory, with retries and error handling.

        Sends a message of the form "<speaker>: <message>" to each agent's message store. Retries transient failures with exponential backoff (e.g., HTTP 500 or disconnection). If a token-related error is detected, attempts to reset the agent's messages and retries the update once. Logs failures; does not raise on per-agent errors.

        Parameters:
            message (str): The message text to record in each agent's memory.
            speaker (str): Label prepended to the message (defaults to "User").
            max_retries (int): Maximum number of attempts per agent for transient errors.
        """
        for agent in self.agents:
            success = False
            for attempt in range(max_retries):
                try:
                    self._call_agent_message_create(
                        "agents.messages.create.update_memory",
                        agent_id=agent.agent.id,
                        messages=[
                            {
                                "role": "user",
                                "content": f"{speaker}: {message}",
                            }
                        ],
                    )
                    success = True
                    break
                except Exception as e:
                    error_str = str(e)
                    if attempt < max_retries - 1 and (
                        "500" in error_str or "disconnected" in error_str.lower()
                    ):
                        wait_time = 0.5 * (2**attempt)
                        self._emit(
                            f"Retrying {agent.name} after {wait_time}s...",
                            level="warning",
                        )
                        time.sleep(wait_time)
                        continue
                    else:
                        self._emit(
                            f"Error updating {agent.name} memory: {e}",
                            level="error",
                        )
                        # For token limit errors, reset and retry once
                        if (
                            "max_tokens" in error_str.lower()
                            or "token" in error_str.lower()
                        ):
                            self._emit(
                                f"Token limit reached for {agent.name}, resetting messages...",
                                level="warning",
                            )
                            self._reset_agent_messages(agent.agent.id)
                            try:
                                self._call_agent_message_create(
                                    "agents.messages.create.retry_after_reset",
                                    agent_id=agent.agent.id,
                                    messages=[
                                        {
                                            "role": "user",
                                            "content": f"{speaker}: {message}",
                                        }
                                    ],
                                )
                                success = True
                            except Exception as retry_e:
                                self._emit(
                                    f"Retry failed for {agent.name}: {retry_e}",
                                    level="error",
                                )
                        break

            if not success:
                self._emit(
                    f"Failed to update {agent.name} after {max_retries} attempts",
                    level="error",
                )

    def _reset_agent_messages(self, agent_id: str):
        """
        Reset the stored message history for a specific agent.

        Calls the Letta client to clear the agent's message history (agent_id) so the agent can recover from token-limit or context-size issues. Exceptions are caught and logged; this method does not raise.

        Parameters:
            agent_id (str): Identifier of the agent whose message history should be reset.
        """
        try:
            letta_call(
                "agents.messages.reset",
                self.client.agents.messages.reset,
                agent_id=agent_id,
            )
            self._emit(f"Successfully reset messages for agent {agent_id}")
        except Exception as e:
            self._emit(
                f"Failed to reset messages for agent {agent_id}: {e}",
                level="error",
            )

    def _get_agent_message_count(self, agent_id: str) -> int:
        """
        Return the number of messages in an agent's history.

        Queries the Lettа client for up to 1000 messages for the given agent and returns the length of the returned collection. If the response is not a sized sequence or an error occurs while fetching messages, the function returns 0 and logs the failure.

        Parameters:
            agent_id (str): Identifier of the agent whose message history will be counted.

        Returns:
            int: Number of messages found (0 on error or when the result is not size-aware).
        """
        try:
            messages = letta_call(
                "agents.messages.list",
                self.client.agents.messages.list,
                agent_id=agent_id,
                limit=1000,
            )
            return len(messages) if hasattr(messages, "__len__") else 0
        except Exception as e:
            self._emit(
                f"Failed to get message count for agent {agent_id}: {e}",
                level="error",
            )
            return 0

    def _warm_up_agent(self, agent, topic: str) -> bool:
        """
        Prime an agent's context so it's prepared to participate in a discussion about the given topic.

        Sends a short user-role primer message to the agent's message stream asking it to review its memory and prepare to contribute, then pauses briefly to allow processing. Returns True on successful primer send; returns False if an error occurs while attempting to warm up the agent.

        Parameters:
            agent: The SPDSAgent wrapper representing the agent to prime.
            topic (str): The meeting/topic string used in the primer message.

        Returns:
            bool: True if the primer was sent successfully; False if warming up failed.
        """
        try:
            # Send context primer to ensure agent is ready
            self._call_agent_message_create(
                "agents.messages.create.warm_up",
                agent_id=agent.agent.id,
                messages=[
                    {
                        "role": "user",
                        "content": f"We are about to discuss: {topic}. Please review your memory and prepare to contribute meaningfully to this discussion.",
                    }
                ],
            )
            time.sleep(0.3)  # Small delay to allow processing
            return True
        except Exception as e:
            self._emit(
                f"Agent warm-up failed for {agent.name}: {e}",
                level="error",
            )
            return False

    def _agent_turn(self, topic: str):
        """
        Evaluate motivation and priority for each agent with respect to the provided topic, build an ordered list of motivated agents (priority_score > 0), and invoke the mode-specific turn handler (_hybrid_turn, _all_speak_turn, _sequential_turn, or _pure_priority_turn). If no agents are motivated the method returns without further action. The method updates agent internal scores and triggers side-effectful turn handlers which append to the shared conversation state and notify the secretary when present.

        Parameters:
            topic (str): The meeting topic or prompt used to assess agent motivation.

        Returns:
            None
        """
        self._emit(
            f"--- Assessing agent motivations ({self.conversation_mode.upper()} mode) ---"
        )
        start_time = time.time()
        for agent in self.agents:
            agent.assess_motivation_and_priority(topic)
            self._emit(
                f"  - {agent.name}: Motivation Score = {agent.motivation_score}, Priority Score = {agent.priority_score:.2f}"
            )
        duration = time.time() - start_time
        self._emit(
            f"Motivation assessment for {len(self.agents)} agents took {duration:.2f} seconds."
        )
        if duration > 5:
            self._emit(
                f"Slow motivation assessment: {duration:.2f} seconds.",
                level="warning",
            )

        motivated_agents = sorted(
            [agent for agent in self.agents if agent.priority_score > 0],
            key=lambda x: x.priority_score,
            reverse=True,
        )

        if not motivated_agents:
            self._emit("System: No agent is motivated to speak at this time.")
            return

        self._emit(
            f"🎭 {len(motivated_agents)} agent(s) motivated to speak in {self.conversation_mode.upper()} mode"
        )

        # Dispatch to appropriate conversation mode
        if self.conversation_mode == "hybrid":
            self._hybrid_turn(motivated_agents, topic)
        elif self.conversation_mode == "all_speak":
            self._all_speak_turn(motivated_agents, topic)
        elif self.conversation_mode == "sequential":
            self._sequential_turn(motivated_agents, topic)
        elif self.conversation_mode == "pure_priority":
            self._pure_priority_turn(motivated_agents, topic)
        else:
            # Fallback to sequential mode
            self._sequential_turn(motivated_agents, topic)

    def _extract_agent_response(self, response) -> str:
        """
        Extract a human-readable message string from an agent response object.

        This helper inspects the response.messages sequence and attempts multiple robust extraction strategies:
        - Prefer text passed via a tool call named "send_message" (JSON-decoded arguments -> "message").
        - Ignore tool_return entries (typically non-content/status).
        - Fall back to assistant/assistant_message content, handling content represented as a plain string, a list of content blocks, objects with a `.text` attribute, or dicts with a "text" key.
        If no usable text is found or an error occurs, returns a short fallback sentence.

        Parameters:
            response: An object with a `messages` iterable where each message may expose
                attributes like `tool_calls`, `tool_return`, `message_type`, `role`, and `content`.
                The function does not require a specific concrete type, but the object must match
                the above shape.

        Returns:
            str: The extracted message text, or a generic fallback string if extraction fails.
        """
        message_text = ""
        extraction_successful = False

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
                                candidate = args.get("message", "").strip()
                                # Accept any non-empty message from tool call
                                if candidate:
                                    message_text = candidate
                                    extraction_successful = True
                                    break
                            except json.JSONDecodeError as e:
                                logger.warning(f"JSON parse error in tool call: {e}")
                                continue
                            except Exception as e:
                                logger.warning(f"Tool call extraction error: {e}")
                                continue

                # Only proceed if we haven't successfully extracted a message yet
                if extraction_successful:
                    break

                # Check for tool return messages (when agent uses send_message)
                if not message_text and hasattr(msg, "tool_return") and msg.tool_return:
                    # Tool returns often contain status messages we can ignore in SwarmManager
                    continue

                # Accept either legacy message_type or modern role='assistant'
                if not message_text and (
                    (
                        hasattr(msg, "message_type")
                        and getattr(msg, "message_type") == "assistant_message"
                    )
                    or (hasattr(msg, "role") and getattr(msg, "role") == "assistant")
                ):
                    if hasattr(msg, "content") and getattr(msg, "content"):
                        content_val = getattr(msg, "content")
                        if isinstance(content_val, str):
                            message_text = content_val
                        elif isinstance(content_val, list) and content_val:
                            item0 = content_val[0]
                            if hasattr(item0, "text"):
                                message_text = item0.text
                            elif isinstance(item0, dict) and "text" in item0:
                                message_text = item0["text"]
                            elif isinstance(item0, str):
                                message_text = item0

                # If no tool call, try regular content extraction
                if not message_text and hasattr(msg, "content"):
                    content_val = getattr(msg, "content")
                    if isinstance(content_val, str):
                        message_text = content_val
                    elif isinstance(content_val, list) and content_val:
                        content_item = content_val[0]
                        if hasattr(content_item, "text"):
                            message_text = content_item.text
                        elif isinstance(content_item, dict) and "text" in content_item:
                            message_text = content_item["text"]
                        elif isinstance(content_item, str):
                            message_text = content_item

                if message_text:
                    break

            if not message_text:
                message_text = (
                    "I have some thoughts but I'm having trouble phrasing them."
                )

        except Exception as e:
            message_text = "I have some thoughts but I'm having trouble phrasing them."
            logger.error(f"Error extracting response - {e}")

        return message_text

    def _hybrid_turn(self, motivated_agents: list, topic: str):
        """
        Run a two-phase hybrid turn where motivated agents first give independent initial thoughts and then respond to each other's ideas.

        Phase 1 (initial responses): Each agent in `motivated_agents` is asked to produce an independent short response using the current conversation history. Responses are validated for basic quality; if an agent fails to produce usable text a fallback message based on the agent's expertise is used. Initial replies are appended to the manager's conversation_history and forwarded to the secretary (if present).

        Phase 2 (response round): All agents are given a brief instruction to react to the group's initial thoughts. Each motivated agent is then asked to produce a follow-up response that considers others' inputs; those replies are appended to conversation_history and sent to the secretary.

        Side effects:
        - Appends agent messages (or fallbacks) to self.conversation_history.
        - Sends prompt messages to agents via self.client.agents.messages.create.
        - Notifies the secretary of agent responses via self._notify_secretary_agent_response.
        - Logs timing, slow responses, and errors.

        Parameters:
            motivated_agents (list): Ordered list of agent wrappers (SPDSAgent-like) selected to participate in this turn; each agent is expected to expose `.name`, `.agent.id`, `.priority_score`, `.speak(...)`, and optionally `.expertise`.
            topic (str): The meeting topic used to steer fallback prompts and initial prompting.

        Returns:
            None
        """
        turn_start_time = time.time()

        # Phase 1: Independent responses
        self._emit("\n=== 🧠 INITIAL RESPONSES ===")
        initial_responses = []

        for i, agent in enumerate(motivated_agents, 1):
            self._emit(
                f"\n({i}/{len(motivated_agents)}) {agent.name} (priority: {agent.priority_score:.2f}) - Initial thoughts..."
            )

            # Try to get response with retry logic
            message_text = ""
            max_attempts = 1

            for attempt in range(max_attempts):
                try:
                    start_time = time.time()
                    # Use current conversation history to avoid API overhead and align with agent interface
                    response = agent.speak(
                        conversation_history=self.conversation_history
                    )
                    duration = time.time() - start_time
                    self._emit(
                        f"Agent {agent.name} LLM response generated in {duration:.2f} seconds"
                    )
                    if duration > 5:
                        self._emit(
                            f"Slow LLM response from {agent.name}: {duration:.2f} seconds",
                            level="warning",
                        )
                    message_text = self._extract_agent_response(response)

                    # Validate response quality
                    if (
                        message_text
                        and len(message_text.strip()) > 10
                        and "having trouble" not in message_text.lower()
                    ):
                        # Good response
                        break
                    elif attempt < max_attempts - 1:
                        # Poor response, retry once
                        self._emit(
                            "Weak response detected, retrying...", level="warning"
                        )
                        time.sleep(0.5)
                        # Send a more specific prompt
                        self._call_agent_message_create(
                            "agents.messages.create.retry_prompt",
                            agent_id=agent.agent.id,
                            messages=[
                                {
                                    "role": "user",
                                    "content": f"Please share your specific thoughts on {topic}. What is your perspective?",
                                }
                            ],
                        )

                except Exception as e:
                    self._emit(
                        f"Error in initial response attempt {attempt+1} - {e}",
                        level="error",
                    )
                    if attempt < max_attempts - 1:
                        time.sleep(0.5)

            # Use the response or a more specific fallback
            if message_text and len(message_text.strip()) > 10:
                initial_responses.append((agent, message_text))
                self._emit(f"{agent.name}: {message_text}")
                # Add to conversation history for secretary
                self.conversation_history += f"{agent.name}: {message_text}\n"
                # Notify secretary
                self._notify_secretary_agent_response(agent.name, message_text)
            else:
                # More specific fallback based on agent's expertise
                fallback = f"As someone with expertise in {getattr(agent, 'expertise', 'this area')}, I'm processing the topic of {topic} and will share my thoughts in the next round."
                initial_responses.append((agent, fallback))
                self._emit(f"{agent.name}: {fallback}")
                self.conversation_history += f"{agent.name}: {fallback}\n"

        # Phase 2: Response round - agents react to each other's ideas
        self._emit("\n=== 💬 RESPONSE ROUND ===")
        self._emit("Agents now respond to each other's initial thoughts...")

        # Send instruction to all agents about response phase
        for agent in self.agents:
            try:
                self._call_agent_message_create(
                    "agents.messages.create.response_instruction",
                    agent_id=agent.agent.id,
                    messages=[
                        {
                            "role": "user",
                            "content": "Now that you've heard everyone's initial thoughts, please consider how you might respond. You might agree and build on someone's idea, respectfully disagree and explain why, share a new insight sparked by what you heard, ask questions about others' perspectives, or connect ideas between different responses.",
                        }
                    ],
                )
            except Exception as e:
                self._emit(
                    f"Error sending response instruction to {agent.name}: {e}",
                    level="error",
                )

        # Build response prompt context from current conversation history
        history_with_initials = self.conversation_history
        response_prompt_addition = "\nNow that you've heard everyone's initial thoughts, please consider how you might respond."

        for i, agent in enumerate(motivated_agents, 1):
            self._emit(
                f"\n({i}/{len(motivated_agents)}) {agent.name} - Responding to the discussion..."
            )
            try:
                start_time = time.time()
                response = agent.speak(
                    conversation_history=history_with_initials
                    + response_prompt_addition
                )
                duration = time.time() - start_time
                self._emit(
                    f"Agent {agent.name} LLM response generated in {duration:.2f} seconds"
                )
                if duration > 5:
                    self._emit(
                        f"Slow LLM response from {agent.name}: {duration:.2f} seconds",
                        level="warning",
                    )
                message_text = self._extract_agent_response(response)
                self._emit(f"{agent.name}: {message_text}")
                # Add responses to conversation history
                self.conversation_history += f"{agent.name}: {message_text}\n"
                # Notify secretary
                self._notify_secretary_agent_response(agent.name, message_text)
            except Exception as e:
                fallback = "I find the different perspectives here really interesting and would like to engage more with these ideas."
                self._emit(f"{agent.name}: {fallback}")
                self.conversation_history += f"{agent.name}: {fallback}\n"
                self._emit(
                    f"[Debug: Error in response round - {e}]",
                    level="error",
                )

        # Log overall turn timing
        turn_duration = time.time() - turn_start_time
        self._emit(f"Hybrid turn completed in {turn_duration:.2f} seconds")
        if turn_duration > 30:
            self._emit(
                f"Slow hybrid turn: {turn_duration:.2f} seconds",
                level="warning",
            )

    def _all_speak_turn(self, motivated_agents: list, topic: str):
        """
        Have every motivated agent speak in descending priority order, appending each response to the shared conversation history.

        For each agent in motivated_agents (expected to be SPDSAgent-like objects with a .name and .priority_score):
        - Requests a response using the current conversation_history so later speakers can see earlier replies.
        - Extracts a text response, appends "AgentName: message" to self.conversation_history, and notifies the secretary (if present).
        - Propagates the response to all agents' memories via _update_agent_memories.
        - Logs timing and slow-response warnings.

        Side effects:
        - Mutates self.conversation_history.
        - Calls agent.speak, self._extract_agent_response, self._update_agent_memories, and self._notify_secretary_agent_response (external I/O/LLM calls).
        - Emits logs and may append a fallback message on exceptions; exceptions are caught and not re-raised.
        """
        self._emit(f"\n=== 👥 ALL SPEAK MODE ({len(motivated_agents)} agents) ===")

        for i, agent in enumerate(motivated_agents, 1):
            self._emit(
                f"\n({i}/{len(motivated_agents)}) {agent.name} (priority: {agent.priority_score:.2f}) is speaking..."
            )
            try:
                start_time = time.time()
                response = agent.speak(conversation_history=self.conversation_history)
                duration = time.time() - start_time
                self._emit(
                    f"Agent {agent.name} LLM response generated in {duration:.2f} seconds."
                )
                if duration > 5:
                    self._emit(
                        f"Slow LLM response from {agent.name}: {duration:.2f} seconds.",
                        level="warning",
                    )
                message_text = self._extract_agent_response(response)
                self._emit(f"{agent.name}: {message_text}")
                # Update all agents' memories with this response
                self._update_agent_memories(message_text, agent.name)
                # Add each response to history so subsequent agents can see it
                self.conversation_history += f"{agent.name}: {message_text}\n"
                # Notify secretary
                self._notify_secretary_agent_response(agent.name, message_text)
            except Exception as e:
                fallback = "I have some thoughts but I'm having trouble expressing them clearly."
                self._emit(f"{agent.name}: {fallback}")
                self.conversation_history += f"{agent.name}: {fallback}\n"
                self._emit(
                    f"Error in all-speak response - {e}",
                    level="error",
                )

    def _sequential_turn(self, motivated_agents: list, topic: str):
        """One agent speaks per turn with fairness rotation."""
        self._emit(f"\n=== 🔀 SEQUENTIAL MODE (fairness rotation) ===")

        # Implement fairness: if multiple agents are motivated, give others a chance
        if len(motivated_agents) > 1:
            # Check if the top agent has spoken recently (simple fairness)
            if (
                hasattr(self, "last_speaker")
                and self.last_speaker == motivated_agents[0].name
            ):
                # Give the second-highest priority agent a chance
                speaker = motivated_agents[1]
                self._emit(
                    f"\n[Fairness: Giving {speaker.name} a turn (priority: {speaker.priority_score:.2f})]"
                )
            else:
                speaker = motivated_agents[0]
        else:
            speaker = motivated_agents[0]

        # Track the last speaker for fairness
        self.last_speaker = speaker.name
        self._emit(f"\n({speaker.name} is speaking...)")

        try:
            start_time = time.time()
            response = speaker.speak(conversation_history=self.conversation_history)
            duration = time.time() - start_time
            self._emit(
                f"Agent {speaker.name} LLM response generated in {duration:.2f} seconds."
            )
            if duration > 5:
                self._emit(
                    f"Slow LLM response from {speaker.name}: {duration:.2f} seconds.",
                    level="warning",
                )
            message_text = self._extract_agent_response(response)
            self._emit(f"{speaker.name}: {message_text}")
            self.conversation_history += f"{speaker.name}: {message_text}\n"
            # Notify secretary
            self._notify_secretary_agent_response(speaker.name, message_text)
        except Exception as e:
            fallback = "I have some thoughts but I'm having trouble phrasing them."
            self._emit(f"{speaker.name}: {fallback}")
            self.conversation_history += f"{speaker.name}: {fallback}\n"
            # Notify secretary of fallback too
            self._notify_secretary_agent_response(speaker.name, fallback)
            self._emit(
                f"[Debug: Error in sequential response - {e}]",
                level="error",
            )

    def _pure_priority_turn(self, motivated_agents: list, topic: str):
        """
        Have the single highest-priority motivated agent speak once and record the result.

        This picks the first agent from `motivated_agents` (expected to be pre-sorted by priority),
        requests a response using the manager's current conversation_history, appends the agent's
        utterance to conversation_history, and notifies the secretary (if enabled). On error,
        a short fallback message is recorded and the secretary is notified.

        Parameters:
            motivated_agents (list): List of motivated agent wrappers, highest priority first.
            topic (str): Meeting topic (not directly used by this turn handler).

        Returns:
            None
        """
        speaker = motivated_agents[0]  # Already sorted by priority
        self._emit(f"\n=== 🎯 PURE PRIORITY MODE ===")
        self._emit(
            f"\n({speaker.name} is speaking - highest priority: {speaker.priority_score:.2f})"
        )

        try:
            start_time = time.time()
            response = speaker.speak(conversation_history=self.conversation_history)
            duration = time.time() - start_time
            self._emit(
                f"Agent {speaker.name} LLM response generated in {duration:.2f} seconds."
            )
            if duration > 5:
                self._emit(
                    f"Slow LLM response from {speaker.name}: {duration:.2f} seconds.",
                    level="warning",
                )
            message_text = self._extract_agent_response(response)
            self._emit(f"{speaker.name}: {message_text}")
            self.conversation_history += f"{speaker.name}: {message_text}\n"
            # Notify secretary
            self._notify_secretary_agent_response(speaker.name, message_text)
        except Exception as e:
            fallback = "I have thoughts on this topic but I'm having difficulty expressing them."
            self._emit(f"{speaker.name}: {fallback}")
            self.conversation_history += f"{speaker.name}: {fallback}\n"
            # Notify secretary of fallback too
            self._notify_secretary_agent_response(speaker.name, fallback)
            self._emit(
                f"Error in pure priority response - {e}",
                level="error",
            )

    def _start_meeting(self, topic: str):
        """
        Initialize meeting context for the swarm and notify the secretary if enabled.

        Adds a system-level line with the provided topic to the manager's conversation_history.
        If a SecretaryAgent is present, calls its start_meeting(...) with the topic, the current
        agent names as participants, and the manager's meeting_type, and records the current
        conversation_mode in the secretary's meeting_metadata.

        Parameters:
            topic (str): Human-readable meeting topic to add to conversation history and pass to the secretary.
        """
        self.conversation_history += f"System: The topic is '{topic}'.\n"

        # Track meeting start
        track_system_event(
            event_type="meeting_started",
            details={
                "topic": topic,
                "meeting_type": self.meeting_type,
                "conversation_mode": self.conversation_mode,
                "agent_count": len(self.agents),
                "secretary_enabled": getattr(self, "enable_secretary", False),
            },
        )

        # Topic is naturally included in conversation_history

        if self.secretary:
            # Get participant names
            participant_names = [agent.name for agent in self.agents]

            # Start the meeting in the secretary
            self.secretary.start_meeting(
                topic=topic,
                participants=participant_names,
                meeting_type=self.meeting_type,
            )

            # Set conversation mode in metadata
            self.secretary.meeting_metadata[
                "conversation_mode"
            ] = self.conversation_mode

    def _end_meeting(self):
        """
        Mark the meeting as finished and, if a secretary is present, present export options.

        If a SecretaryAgent is enabled, logs a meeting-end separator/message and invokes
        _self._offer_export_options()_ to present export/export-command choices to the user.
        If no secretary is configured, this method is a no-op.
        """
        # Track meeting end
        track_system_event(
            event_type="meeting_ended",
            details={
                "meeting_type": self.meeting_type,
                "conversation_mode": self.conversation_mode,
                "secretary_enabled": getattr(self, "enable_secretary", False),
                "conversation_history_length": len(self.conversation_history),
            },
        )

        if self.secretary:
            self._emit("\n" + "=" * 50)
            self._emit("🏁 Meeting ended! Export options available.")
            self._offer_export_options()

    def _handle_secretary_commands(self, user_input: str) -> bool:
        """
        Parse and execute in-chat secretary and memory-related slash commands.

        Accepts a user input string (expected to start with '/') and handles commands such as:
        - memory-status / memory-awareness: produce agent memory summaries and awareness checks (available even when secretary is not enabled).
        - minutes / export / formal / casual / action-item / stats / help: delegate to the SecretaryAgent when enabled.

        Side effects:
        - May print summaries to stdout and call methods on the secretary (generate_minutes, set_mode, add_action_item, get_conversation_stats, etc.).
        - Logs informational or warning messages via the module logger.
        - If the secretary is not enabled, certain commands (minutes, export, formal, casual, action-item) will be intercepted and a warning is logged instead.

        Parameters:
            user_input (str): Raw user input; must start with '/' to be treated as a command.

        Returns:
            bool: True if the input was recognized and handled as a command (including when it is recognized but the secretary is disabled), False otherwise.
        """
        if not user_input.startswith("/"):
            return False

        command_parts = user_input[1:].split(" ", 1)
        command = command_parts[0].lower()
        args = command_parts[1] if len(command_parts) > 1 else ""

        # Handle memory awareness commands (available with or without secretary)
        if command == "memory-status":
            summary = self.get_memory_status_summary()
            print("\n📊 **Agent Memory Status Summary**")
            print(f"Total agents: {summary['total_agents']}")
            print(f"Agents with >500 messages: {summary['agents_with_high_memory']}")
            print(
                f"Total messages across all agents: {summary['total_messages_across_agents']}"
            )
            print("\nPer-agent status:")
            for agent_status in summary["agents_status"]:
                if "error" in agent_status:
                    print(f"  - {agent_status['name']}: Error retrieving data")
                else:
                    print(
                        f"  - {agent_status['name']}: {agent_status['recall_memory']} messages, {agent_status['archival_memory']} archived items"
                    )
            print(
                "\nNote: This information is provided for awareness only. Agents have autonomy over memory decisions."
            )
            return True

        elif command == "memory-awareness":
            self._emit("\n📊 Checking memory awareness status for all agents...")
            self.check_memory_awareness_status(silent=False)
            return True

        # Secretary-specific commands
        if not self.secretary:
            if command in ["minutes", "export", "formal", "casual", "action-item"]:
                self._emit(
                    "❌ Secretary is not enabled. Please restart with secretary mode.",
                    level="warning",
                )
                return True
            elif command in ["memory-status", "memory-awareness", "help", "commands"]:
                # These commands are handled above or below
                pass
            else:
                return False

        if command == "minutes":
            self._emit("\n📋 Generating current meeting minutes...")
            minutes = self.secretary.generate_minutes()
            print(minutes)
            return True

        elif command == "export":
            self._handle_export_command(args)
            return True

        elif command == "formal":
            self.secretary.set_mode("formal")
            self._emit("📝 Secretary mode changed to formal")
            return True

        elif command == "casual":
            self.secretary.set_mode("casual")
            self._emit("📝 Secretary mode changed to casual")
            return True

        elif command == "action-item":
            if args:
                self.secretary.add_action_item(args)
            else:
                print("Usage: /action-item <description>")
            return True

        elif command == "stats":
            stats = self.secretary.get_conversation_stats()
            print("\n📊 Conversation Statistics:")
            for key, value in stats.items():
                print(f"  - {key}: {value}")
            return True

        elif command in ["help", "commands"]:
            self._show_secretary_help()
            return True

        return False

    def _handle_export_command(self, args: str):
        """
        Handle an export command by generating meeting artifacts in the requested format.

        Collects current meeting data from the secretary (metadata, conversation log, action items, decisions, stats) and delegates to ExportManager to produce one of the supported outputs. Supported format strings (case-insensitive) are:
        - "minutes" or "formal": export formal meeting minutes
        - "casual": export casual-style minutes
        - "transcript": export a raw transcript
        - "actions": export action items
        - "summary": export an executive summary
        - "all": export a complete package (multiple files)

        If no secretary is available the call is ignored and a warning is logged. Errors during export are caught and logged; the function does not raise.

        Parameters:
            args (str): Optional format specifier (e.g., "minutes", "transcript"); defaults to "minutes" when falsy.
        """
        if not self.secretary:
            self._emit("❌ Secretary not available", level="warning")
            return

        # Get current meeting data
        meeting_data = {
            "metadata": self.secretary.meeting_metadata,
            "conversation_log": self.secretary.conversation_log,
            "action_items": self.secretary.action_items,
            "decisions": self.secretary.decisions,
            "stats": self.secretary.get_conversation_stats(),
        }

        format_type = args.strip().lower() if args else "minutes"

        try:
            if format_type in ["minutes", "formal"]:
                file_path = self.export_manager.export_meeting_minutes(
                    meeting_data, "formal"
                )
            elif format_type == "casual":
                file_path = self.export_manager.export_meeting_minutes(
                    meeting_data, "casual"
                )
            elif format_type == "transcript":
                file_path = self.export_manager.export_raw_transcript(
                    self.secretary.conversation_log, self.secretary.meeting_metadata
                )
            elif format_type == "actions":
                file_path = self.export_manager.export_action_items(
                    self.secretary.action_items, self.secretary.meeting_metadata
                )
            elif format_type == "summary":
                file_path = self.export_manager.export_executive_summary(meeting_data)
            elif format_type == "all":
                files = self.export_manager.export_complete_package(
                    meeting_data, self.secretary.mode
                )
                self._emit(f"✅ Complete package exported: {len(files)} files")
                return
            else:
                self._emit(
                    f"❌ Unknown export format: {format_type}",
                    level="error",
                )
                print(
                    "Available formats: minutes, casual, transcript, actions, summary, all"
                )
                return

            self._emit(f"✅ Exported: {file_path}")

        except Exception as e:
            self._emit(f"❌ Export failed: {e}", level="error")

    def _offer_export_options(self):
        """
        Prompt the user to choose end-of-meeting export options and dispatch the chosen export command to the secretary.

        If a SecretaryAgent is present, this presents a list of available export commands (minutes, casual, transcript, actions, summary, all), reads a single user choice from stdin, and forwards any input that starts with "/" to _handle_secretary_commands. EOF or KeyboardInterrupt during input are ignored and the method returns. If no secretary is configured, the method returns immediately.

        No return value.
        """
        if not self.secretary:
            return

        print("\nWould you like to export the meeting? Available options:")
        print("  📋 /export minutes - Formal board minutes")
        print("  💬 /export casual - Casual meeting notes")
        print("  📝 /export transcript - Raw conversation")
        print("  ✅ /export actions - Action items list")
        print("  📊 /export summary - Executive summary")
        print("  📦 /export all - Complete package")
        print("\nOr type any command, or just press Enter to finish.")

        try:
            choice = input("\nExport choice: ").strip()
            if choice and choice.startswith("/"):
                self._handle_secretary_commands(choice)
        except (EOFError, KeyboardInterrupt):
            pass

        self._emit("👋 Meeting complete!")

    def _show_secretary_help(self):
        """
        Display interactive help text describing secretary and memory-related commands.

        Shows available commands for memory-awareness utilities (always available), secretary actions (minutes, export, mode switches, action items, stats — applicable when a secretary is enabled), and general help. The help text is user-facing guidance; it does not perform any command actions itself.
        """
        print(
            """
📝 Available Commands:

Memory Awareness (Available Always):
  /memory-status     - Show objective memory statistics for all agents
  /memory-awareness  - Display neutral memory awareness information if criteria are met

Secretary Commands (When Secretary Enabled):
  /minutes           - Generate current meeting minutes
  /export [type]     - Export meeting (minutes/casual/transcript/actions/summary/all)
  /formal            - Switch to formal board minutes mode
  /casual            - Switch to casual meeting notes mode
  /action-item       - Add an action item
  /stats             - Show conversation statistics

General:
  /help              - Show this help message

Note: Memory awareness information respects agent autonomy and provides neutral facts only.
        """
        )

    def _notify_secretary_agent_response(self, agent_name: str, message: str):
        """
        Notify the secretary agent about a single agent's message.

        Parameters:
            agent_name (str): Display name of the agent who produced the message.
            message (str): The textual content of the agent's response.
        """
        if self.secretary:
            self.secretary.observe_message(agent_name, message)

    def check_memory_awareness_status(self, silent: bool = False) -> None:
        """
        Check whether any agents have generated memory-awareness information and, when not silent, display it.

        For each agent this calls create_memory_awareness_for_agent(self.client, agent.agent). If that call returns a non-empty awareness message and silent is False, the message is presented with a short contextual header and disclaimer that agents retain autonomy over memory decisions.

        Parameters:
            silent (bool): If True, perform checks quietly (suppress any console output); useful for background or programmatic checks.
        """
        for agent in self.agents:
            try:
                awareness_message = create_memory_awareness_for_agent(
                    self.client, agent.agent
                )
                if awareness_message and not silent:
                    print(
                        f"\n📊 Memory Awareness Information Available for {agent.name}"
                    )
                    print(
                        "This information is provided for agent awareness only - agents may use or ignore as they choose."
                    )
                    print("-" * 80)
                    print(awareness_message)
                    print("-" * 80)
                    print(
                        "Note: Agents have complete autonomy over memory management decisions.\n"
                    )
            except Exception as e:
                if not silent:
                    self._emit(
                        f"⚠️ Could not generate memory awareness for {agent.name}: {e}",
                        level="warning",
                    )

    def get_memory_status_summary(self) -> dict:
        """
        Get a summary of memory status across all agents.
        Returns objective information only.
        """
        summary = {
            "total_agents": len(self.agents),
            "agents_with_high_memory": 0,
            "total_messages_across_agents": 0,
            "agents_status": [],
        }

        for agent in self.agents:
            try:
                context_info = letta_call(
                    "agents.context.retrieve",
                    self.client.agents.context.retrieve,
                    agent_id=agent.agent.id,
                )
                recall_count = context_info.get("num_recall_memory", 0)
                archival_count = context_info.get("num_archival_memory", 0)

                summary["total_messages_across_agents"] += recall_count

                agent_status = {
                    "name": agent.name,
                    "recall_memory": recall_count,
                    "archival_memory": archival_count,
                    "high_memory": recall_count > 500,
                }

                if recall_count > 500:
                    summary["agents_with_high_memory"] += 1

                summary["agents_status"].append(agent_status)

            except Exception as e:
                summary["agents_status"].append({"name": agent.name, "error": str(e)})

        return summary
