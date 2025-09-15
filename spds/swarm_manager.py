# spds/swarm_manager.py

import time
from .spds_agent import SPDSAgent
from .secretary_agent import SecretaryAgent
from .export_manager import ExportManager
from .memory_awareness import create_memory_awareness_for_agent
from letta_client import Letta
from letta_client.errors import NotFoundError


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
        self.client = client
        self.agents = []
        self.enable_secretary = enable_secretary
        self.secretary = None
        self.export_manager = ExportManager()

        if agent_ids:
            self._load_agents_by_id(agent_ids)
        elif agent_names:
            self._load_agents_by_name(agent_names)
        elif agent_profiles:
            self._create_agents_from_profiles(agent_profiles)

        if not self.agents:
            raise ValueError(
                "Swarm manager initialized with no agents. Please provide profiles, IDs, or names."
            )

        self.conversation_history = ""
        self.last_speaker = None  # For fairness tracking
        self.conversation_mode = conversation_mode
        self.meeting_type = meeting_type
        
        # Initialize secretary if enabled
        if enable_secretary:
            try:
                self.secretary = SecretaryAgent(client, mode=secretary_mode)
                print(f"📝 Secretary enabled in {secretary_mode} mode")
            except Exception as e:
                print(f"⚠️  Failed to create secretary agent: {e}")
                self.enable_secretary = False
        
        # Validate conversation mode
        valid_modes = ["hybrid", "all_speak", "sequential", "pure_priority"]
        if conversation_mode not in valid_modes:
            raise ValueError(f"Invalid conversation mode: {conversation_mode}. Valid modes: {valid_modes}")

    def _load_agents_by_id(self, agent_ids: list):
        """Loads existing agents from the Letta server by their IDs."""
        print("Loading swarm from existing agent IDs...")
        for agent_id in agent_ids:
            try:
                print(f"  - Retrieving agent: {agent_id}")
                agent_state = self.client.agents.retrieve(agent_id=agent_id)
                self.agents.append(SPDSAgent(agent_state, self.client))
            except NotFoundError:
                print(f"  - WARNING: Agent with ID '{agent_id}' not found. Skipping.")

    def _load_agents_by_name(self, agent_names: list):
        """Loads existing agents from the Letta server by their names."""
        print("Loading swarm from existing agent names...")
        for name in agent_names:
            print(f"  - Retrieving agent by name: {name}")
            # The list method with a name filter returns a list. We'll take the first one.
            found_agents = self.client.agents.list(name=name, limit=1)
            if not found_agents:
                print(f"  - WARNING: Agent with name '{name}' not found. Skipping.")
                continue
            self.agents.append(SPDSAgent(found_agents[0], self.client))

    def _create_agents_from_profiles(self, agent_profiles: list):
        """Creates new, temporary agents from a list of profiles."""
        print("Creating swarm from temporary agent profiles...")
        for profile in agent_profiles:
            print(f"  - Creating agent: {profile['name']}")
            self.agents.append(
                SPDSAgent.create_new(
                    name=profile["name"],
                    persona=profile["persona"],
                    expertise=profile["expertise"],
                    client=self.client,
                    model=profile.get("model"),
                    embedding=profile.get("embedding"),
                )
            )

    def start_chat(self):
        """Starts and manages the group chat."""
        print("\nSwarm chat started. Type 'quit' or Ctrl+D to end the session.")
        try:
            topic = input("Enter the topic of conversation: ")
        except EOFError:
            print("\nExiting.")
            return

        print(f"\nSwarm chat started with topic: '{topic}' (Mode: {self.conversation_mode.upper()})")
        self._start_meeting(topic)

        while True:
            try:
                human_input = input("\nYou: ")
            except EOFError:
                print("\nExiting chat.")
                break

            if human_input.lower() == "quit":
                print("Exiting chat.")
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
        """Starts and manages the group chat with a pre-set topic."""
        print(f"\nSwarm chat started with topic: '{topic}' (Mode: {self.conversation_mode.upper()})")
        if self.secretary:
            print(f"📝 Secretary: {self.secretary.agent.name if self.secretary.agent else 'Recording'} ({self.secretary.mode} mode)")
        print("Type 'quit' or Ctrl+D to end the session.")
        print("Available commands: /minutes, /export, /formal, /casual, /action-item")
        
        self._start_meeting(topic)

        while True:
            try:
                human_input = input("\nYou: ")
            except EOFError:
                print("\nExiting chat.")
                break

            if human_input.lower() == "quit":
                print("Exiting chat.")
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

<<<<<<< HEAD
    def _update_agent_memories(self, message: str, speaker: str = "User", max_retries=3):
        """Send a message to all agents to update their internal memory with retry logic."""
        for agent in self.agents:
            success = False
            for attempt in range(max_retries):
                try:
                    self.client.agents.messages.create(
                        agent_id=agent.agent.id,
                        messages=[{"role": "user", "content": f"{speaker}: {message}"}]
                    )
                    success = True
                    break
                except Exception as e:
                    error_str = str(e)
                    if attempt < max_retries - 1 and ("500" in error_str or "disconnected" in error_str.lower()):
                        wait_time = 0.5 * (2 ** attempt)
                        print(f"[Debug: Retrying {agent.name} after {wait_time}s...]")
                        time.sleep(wait_time)
                        continue
                    else:
                        print(f"[Debug: Error updating {agent.name} memory: {e}]")
                        # For token limit errors, reset and retry once
                        if "max_tokens" in error_str.lower() or "token" in error_str.lower():
                            print(f"[Debug: Token limit reached for {agent.name}, resetting messages...]")
                            self._reset_agent_messages(agent.agent.id)
                            try:
                                self.client.agents.messages.create(
                                    agent_id=agent.agent.id,
                                    messages=[{"role": "user", "content": f"{speaker}: {message}"}]
                                )
                                success = True
                            except Exception as retry_e:
                                print(f"[Debug: Retry failed for {agent.name}: {retry_e}]")
                        break
            
            if not success:
                print(f"[Debug: Failed to update {agent.name} after {max_retries} attempts]")
    def _reset_agent_messages(self, agent_id: str):
        """Reset agent message history when token limits are reached."""
        try:
            self.client.agents.messages.reset(agent_id=agent_id)
            print(f"[Debug: Successfully reset messages for agent {agent_id}]")
        except Exception as e:
            print(f"[Debug: Failed to reset messages for agent {agent_id}: {e}]")

    def _get_agent_message_count(self, agent_id: str) -> int:
        """Get the number of messages in an agent's history for monitoring."""
        try:
            messages = self.client.agents.messages.list(agent_id=agent_id, limit=1000)
            return len(messages) if hasattr(messages, '__len__') else 0
        except Exception as e:
            print(f"[Debug: Failed to get message count for agent {agent_id}: {e}]")
            return 0

    def _warm_up_agent(self, agent, topic: str) -> bool:
        """Ensure agent is ready for conversation by priming their context."""
        try:
            # Send context primer to ensure agent is ready
            self.client.agents.messages.create(
                agent_id=agent.agent.id,
                messages=[{
                    "role": "user",
                    "content": f"We are about to discuss: {topic}. Please review your memory and prepare to contribute meaningfully to this discussion."
                }]
            )
            time.sleep(0.3)  # Small delay to allow processing
            return True
        except Exception as e:
            print(f"[Debug: Agent warm-up failed for {agent.name}: {e}]")
            return False

    def _agent_turn(self, topic: str):
        """Manages a single turn of agent responses based on conversation mode."""
        print(f"\n--- Assessing agent motivations ({self.conversation_mode.upper()} mode) ---")
        for agent in self.agents:
            agent.assess_motivation_and_priority(topic)
            print(
                f"  - {agent.name}: Motivation Score = {agent.motivation_score}, Priority Score = {agent.priority_score:.2f}"
            )

        motivated_agents = sorted(
            [agent for agent in self.agents if agent.priority_score > 0],
            key=lambda x: x.priority_score,
            reverse=True,
        )

        if not motivated_agents:
            print("\nSystem: No agent is motivated to speak at this time.")
            return

        print(f"\n🎭 {len(motivated_agents)} agent(s) motivated to speak in {self.conversation_mode.upper()} mode")

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
        """Helper method to extract message text from agent response with robust error handling."""
        message_text = ""
        extraction_successful = False
        
        try:
            for msg in response.messages:
                # Check for tool calls first (send_message)
                if hasattr(msg, 'tool_calls') and msg.tool_calls:
                    for tool_call in msg.tool_calls:
                        if hasattr(tool_call, 'function') and tool_call.function.name == 'send_message':
                            try:
                                import json
                                args = json.loads(tool_call.function.arguments)
                                candidate = args.get('message', '').strip()
                                # Validate the extracted message
                                if candidate and len(candidate) > 10:  # Minimum viable response
                                    message_text = candidate
                                    extraction_successful = True
                                    break
                            except json.JSONDecodeError as e:
                                print(f"[Debug: JSON parse error in tool call: {e}]")
                                continue
                            except Exception as e:
                                print(f"[Debug: Tool call extraction error: {e}]")
                                continue
                
                # Only proceed if we haven't successfully extracted a message yet
                if extraction_successful:
                    break
                
                # Check for tool return messages (when agent uses send_message)
                if not message_text and hasattr(msg, 'tool_return') and msg.tool_return:
                    # Tool returns often contain status messages we can ignore in SwarmManager
                    continue
                
                # Accept either legacy message_type or modern role='assistant'
                if not message_text and (
                    (hasattr(msg, 'message_type') and getattr(msg, 'message_type') == 'assistant_message')
                    or (hasattr(msg, 'role') and getattr(msg, 'role') == 'assistant')
                ):
                    if hasattr(msg, 'content') and getattr(msg, 'content'):
                        content_val = getattr(msg, 'content')
                        if isinstance(content_val, str):
                            message_text = content_val
                        elif isinstance(content_val, list) and content_val:
                            item0 = content_val[0]
                            if hasattr(item0, 'text'):
                                message_text = item0.text
                            elif isinstance(item0, dict) and 'text' in item0:
                                message_text = item0['text']
                            elif isinstance(item0, str):
                                message_text = item0
                
                # If no tool call, try regular content extraction
                if not message_text and hasattr(msg, 'content'):
                    content_val = getattr(msg, 'content')
                    if isinstance(content_val, str):
                        message_text = content_val
                    elif isinstance(content_val, list) and content_val:
                        content_item = content_val[0]
                        if hasattr(content_item, 'text'):
                            message_text = content_item.text
                        elif isinstance(content_item, dict) and 'text' in content_item:
                            message_text = content_item['text']
                        elif isinstance(content_item, str):
                            message_text = content_item
                
                if message_text:
                    break
            
            if not message_text:
                message_text = "I have some thoughts but I'm having trouble phrasing them."
                
        except Exception as e:
            message_text = "I have some thoughts but I'm having trouble phrasing them."
            print(f"[Debug: Error extracting response - {e}]")
            
        return message_text

    def _hybrid_turn(self, motivated_agents: list, topic: str):
        """Two-phase conversation: independent responses then synthesis."""
        
        # Phase 1: Independent responses
        print("\n=== 🧠 INITIAL RESPONSES ===")
        initial_responses = []
        
        for i, agent in enumerate(motivated_agents, 1):
            print(f"\n({i}/{len(motivated_agents)}) {agent.name} (priority: {agent.priority_score:.2f}) - Initial thoughts...")
            
            # Try to get response with retry logic
            message_text = ""
            max_attempts = 2
            
            for attempt in range(max_attempts):
                try:
                    response = agent.speak(mode="initial", topic=topic)
                    message_text = self._extract_agent_response(response)
                    
                    # Validate response quality
                    if message_text and len(message_text.strip()) > 10 and "having trouble" not in message_text.lower():
                        # Good response
                        break
                    elif attempt < max_attempts - 1:
                        # Poor response, retry once
                        print(f"[Debug: Weak response detected, retrying...")
                        time.sleep(0.5)
                        # Send a more specific prompt
                        self.client.agents.messages.create(
                            agent_id=agent.agent.id,
                            messages=[{"role": "user", "content": f"Please share your specific thoughts on {topic}. What is your perspective?"}]
                        )
                    
                except Exception as e:
                    print(f"[Debug: Error in initial response attempt {attempt+1} - {e}]")
                    if attempt < max_attempts - 1:
                        time.sleep(0.5)
            
            # Use the response or a more specific fallback
            if message_text and len(message_text.strip()) > 10:
                initial_responses.append((agent, message_text))
                print(f"{agent.name}: {message_text}")
                # Add to conversation history for secretary
                self.conversation_history += f"{agent.name}: {message_text}\n"
                # Notify secretary
                self._notify_secretary_agent_response(agent.name, message_text)
            else:
                # More specific fallback based on agent's expertise
                fallback = f"As someone with expertise in {getattr(agent, 'expertise', 'this area')}, I'm processing the topic of {topic} and will share my thoughts in the next round."
                initial_responses.append((agent, fallback))
                print(f"{agent.name}: {fallback}")
                self.conversation_history += f"{agent.name}: {fallback}\n"
        
        # Phase 2: Response round - agents react to each other's ideas
        print("\n=== 💬 RESPONSE ROUND ===")
        print("Agents now respond to each other's initial thoughts...")
        
        # Send instruction to all agents about response phase
        for agent in self.agents:
            try:
                self.client.agents.messages.create(
                    agent_id=agent.agent.id,
                    messages=[{"role": "user", "content": "Now that you've heard everyone's initial thoughts, please consider how you might respond. You might agree and build on someone's idea, respectfully disagree and explain why, share a new insight sparked by what you heard, ask questions about others' perspectives, or connect ideas between different responses."}]
                )
            except Exception as e:
                print(f"[Debug: Error sending response instruction to {agent.name}: {e}]")
        
        # Build response prompt context from current conversation history
        history_with_initials = self.conversation_history
        response_prompt_addition = "\nNow that you've heard everyone's initial thoughts, please consider how you might respond."
        
        for i, agent in enumerate(motivated_agents, 1):
            print(f"\n({i}/{len(motivated_agents)}) {agent.name} - Responding to the discussion...")
            try:
                response = agent.speak(conversation_history=history_with_initials + response_prompt_addition)
                message_text = self._extract_agent_response(response)
                print(f"{agent.name}: {message_text}")
                # Add responses to conversation history
                self.conversation_history += f"{agent.name}: {message_text}\n"
                # Notify secretary
                self._notify_secretary_agent_response(agent.name, message_text)
            except Exception as e:
                fallback = "I find the different perspectives here really interesting and would like to engage more with these ideas."
                print(f"{agent.name}: {fallback}")
                self.conversation_history += f"{agent.name}: {fallback}\n"
                print(f"[Debug: Error in response round - {e}]")

    def _all_speak_turn(self, motivated_agents: list, topic: str):
        """All motivated agents speak in priority order, seeing previous responses."""
        print(f"\n=== 👥 ALL SPEAK MODE ({len(motivated_agents)} agents) ===")
        
        for i, agent in enumerate(motivated_agents, 1):
            print(f"\n({i}/{len(motivated_agents)}) {agent.name} (priority: {agent.priority_score:.2f}) is speaking...")
            try:
                response = agent.speak(conversation_history=self.conversation_history)
                message_text = self._extract_agent_response(response)
                print(f"{agent.name}: {message_text}")
                # Update all agents' memories with this response
                self._update_agent_memories(message_text, agent.name)
                # Add each response to history so subsequent agents can see it
                self.conversation_history += f"{agent.name}: {message_text}\n"
                # Notify secretary
                self._notify_secretary_agent_response(agent.name, message_text)
            except Exception as e:
                fallback = "I have some thoughts but I'm having trouble expressing them clearly."
                print(f"{agent.name}: {fallback}")
                self.conversation_history += f"{agent.name}: {fallback}\n"
                print(f"[Debug: Error in all-speak response - {e}]")

    def _sequential_turn(self, motivated_agents: list, topic: str):
        """One agent speaks per turn with fairness rotation."""
        print(f"\n=== 🔀 SEQUENTIAL MODE (fairness rotation) ===")
        
        # Implement fairness: if multiple agents are motivated, give others a chance
        if len(motivated_agents) > 1:
            # Check if the top agent has spoken recently (simple fairness)
            if hasattr(self, 'last_speaker') and self.last_speaker == motivated_agents[0].name:
                # Give the second-highest priority agent a chance
                speaker = motivated_agents[1]
                print(f"\n[Fairness: Giving {speaker.name} a turn (priority: {speaker.priority_score:.2f})]")
            else:
                speaker = motivated_agents[0]
        else:
            speaker = motivated_agents[0]
        
        # Track the last speaker for fairness
        self.last_speaker = speaker.name
        print(f"\n({speaker.name} is speaking...)")

        try:
            response = speaker.speak(conversation_history=self.conversation_history)
            message_text = self._extract_agent_response(response)
            print(f"{speaker.name}: {message_text}")
            self.conversation_history += f"{speaker.name}: {message_text}\n"
            # Notify secretary
            self._notify_secretary_agent_response(speaker.name, message_text)
        except Exception as e:
            fallback = "I have some thoughts but I'm having trouble phrasing them."
            print(f"{speaker.name}: {fallback}")
            self.conversation_history += f"{speaker.name}: {fallback}\n"
            # Notify secretary of fallback too
            self._notify_secretary_agent_response(speaker.name, fallback)
            print(f"[Debug: Error in sequential response - {e}]")

    def _pure_priority_turn(self, motivated_agents: list, topic: str):
        """Always highest priority motivated agent speaks."""
        speaker = motivated_agents[0]  # Already sorted by priority
        print(f"\n=== 🎯 PURE PRIORITY MODE ===")
        print(f"\n({speaker.name} is speaking - highest priority: {speaker.priority_score:.2f})")

        try:
            response = speaker.speak(conversation_history=self.conversation_history)
            message_text = self._extract_agent_response(response)
            print(f"{speaker.name}: {message_text}")
            self.conversation_history += f"{speaker.name}: {message_text}\n"
            # Notify secretary
            self._notify_secretary_agent_response(speaker.name, message_text)
        except Exception as e:
            fallback = "I have thoughts on this topic but I'm having difficulty expressing them."
            print(f"{speaker.name}: {fallback}")
            self.conversation_history += f"{speaker.name}: {fallback}\n"
            # Notify secretary of fallback too
            self._notify_secretary_agent_response(speaker.name, fallback)
            print(f"[Debug: Error in pure priority response - {e}]")
    
    def _start_meeting(self, topic: str):
        """Initialize meeting with secretary if enabled."""
        self.conversation_history += f"System: The topic is '{topic}'.\n"
        
        # Topic is naturally included in conversation_history
        
        if self.secretary:
            # Get participant names
            participant_names = [agent.name for agent in self.agents]
            
            # Start the meeting in the secretary
            self.secretary.start_meeting(
                topic=topic,
                participants=participant_names,
                meeting_type=self.meeting_type
            )
            
            # Set conversation mode in metadata
            self.secretary.meeting_metadata["conversation_mode"] = self.conversation_mode
    
    def _end_meeting(self):
        """End meeting and offer export options."""
        if self.secretary:
            print("\n" + "="*50)
            print("🏁 Meeting ended! Export options available.")
            self._offer_export_options()
    
    def _handle_secretary_commands(self, user_input: str) -> bool:
        """Handle secretary-related commands. Returns True if command was handled."""
        if not user_input.startswith('/'):
            return False
        
        command_parts = user_input[1:].split(' ', 1)
        command = command_parts[0].lower()
        args = command_parts[1] if len(command_parts) > 1 else ""
        
        # Handle memory awareness commands (available with or without secretary)
        if command == "memory-status":
            summary = self.get_memory_status_summary()
            print("\n📊 **Agent Memory Status Summary**")
            print(f"Total agents: {summary['total_agents']}")
            print(f"Agents with >500 messages: {summary['agents_with_high_memory']}")
            print(f"Total messages across all agents: {summary['total_messages_across_agents']}")
            print("\nPer-agent status:")
            for agent_status in summary['agents_status']:
                if 'error' in agent_status:
                    print(f"  - {agent_status['name']}: Error retrieving data")
                else:
                    print(f"  - {agent_status['name']}: {agent_status['recall_memory']} messages, {agent_status['archival_memory']} archived items")
            print("\nNote: This information is provided for awareness only. Agents have autonomy over memory decisions.")
            return True
        
        elif command == "memory-awareness":
            print("\n📊 Checking memory awareness status for all agents...")
            self.check_memory_awareness_status(silent=False)
            return True
        
        # Secretary-specific commands
        if not self.secretary:
            if command in ['minutes', 'export', 'formal', 'casual', 'action-item']:
                print("❌ Secretary is not enabled. Please restart with secretary mode.")
                return True
            elif command in ['memory-status', 'memory-awareness', 'help', 'commands']:
                # These commands are handled above or below
                pass
            else:
                return False
        
        if command == "minutes":
            print("\n📋 Generating current meeting minutes...")
            minutes = self.secretary.generate_minutes()
            print(minutes)
            return True
        
        elif command == "export":
            self._handle_export_command(args)
            return True
        
        elif command == "formal":
            self.secretary.set_mode("formal")
            print("📝 Secretary mode changed to formal")
            return True
        
        elif command == "casual":
            self.secretary.set_mode("casual")
            print("📝 Secretary mode changed to casual")
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
        """Handle export command with optional format specification."""
        if not self.secretary:
            print("❌ Secretary not available")
            return
        
        # Get current meeting data
        meeting_data = {
            "metadata": self.secretary.meeting_metadata,
            "conversation_log": self.secretary.conversation_log,
            "action_items": self.secretary.action_items,
            "decisions": self.secretary.decisions,
            "stats": self.secretary.get_conversation_stats()
        }
        
        format_type = args.strip().lower() if args else "minutes"
        
        try:
            if format_type in ["minutes", "formal"]:
                file_path = self.export_manager.export_meeting_minutes(meeting_data, "formal")
            elif format_type == "casual":
                file_path = self.export_manager.export_meeting_minutes(meeting_data, "casual")
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
                files = self.export_manager.export_complete_package(meeting_data, self.secretary.mode)
                print(f"✅ Complete package exported: {len(files)} files")
                return
            else:
                print(f"❌ Unknown export format: {format_type}")
                print("Available formats: minutes, casual, transcript, actions, summary, all")
                return
            
            print(f"✅ Exported: {file_path}")
            
        except Exception as e:
            print(f"❌ Export failed: {e}")
    
    def _offer_export_options(self):
        """Offer export options at the end of meeting."""
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
            if choice and choice.startswith('/'):
                self._handle_secretary_commands(choice)
        except (EOFError, KeyboardInterrupt):
            pass
        
        print("👋 Meeting complete!")
    
    def _show_secretary_help(self):
        """Show available commands."""
        print("""
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
        """)
    
    def _notify_secretary_agent_response(self, agent_name: str, message: str):
        """Notify secretary of an agent response."""
        if self.secretary:
            self.secretary.observe_message(agent_name, message)
    
    def check_memory_awareness_status(self, silent: bool = False) -> None:
        """
        Check if any agents might benefit from memory awareness information.
        
        This method respects agent autonomy by:
        - Only providing information when objective criteria are met
        - Presenting neutral facts without recommendations
        - Allowing agents to make their own decisions
        
        Args:
            silent: If True, don't print messages (for background checks)
        """
        for agent in self.agents:
            try:
                awareness_message = create_memory_awareness_for_agent(self.client, agent.agent)
                if awareness_message and not silent:
                    print(f"\n📊 Memory Awareness Information Available for {agent.name}")
                    print("This information is provided for agent awareness only - agents may use or ignore as they choose.")
                    print("-" * 80)
                    print(awareness_message)
                    print("-" * 80)
                    print("Note: Agents have complete autonomy over memory management decisions.\n")
            except Exception as e:
                if not silent:
                    print(f"⚠️ Could not generate memory awareness for {agent.name}: {e}")
    
    def get_memory_status_summary(self) -> dict:
        """
        Get a summary of memory status across all agents.
        Returns objective information only.
        """
        summary = {
            'total_agents': len(self.agents),
            'agents_with_high_memory': 0,
            'total_messages_across_agents': 0,
            'agents_status': []
        }
        
        for agent in self.agents:
            try:
                context_info = self.client.agents.context.retrieve(agent_id=agent.agent.id)
                recall_count = context_info.get('num_recall_memory', 0)
                archival_count = context_info.get('num_archival_memory', 0)
                
                summary['total_messages_across_agents'] += recall_count
                
                agent_status = {
                    'name': agent.name,
                    'recall_memory': recall_count,
                    'archival_memory': archival_count,
                    'high_memory': recall_count > 500
                }
                
                if recall_count > 500:
                    summary['agents_with_high_memory'] += 1
                
                summary['agents_status'].append(agent_status)
                
            except Exception as e:
                summary['agents_status'].append({
                    'name': agent.name,
                    'error': str(e)
                })
        
        return summary
