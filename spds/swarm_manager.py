# spds/swarm_manager.py

import time
from .spds_agent import SPDSAgent
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
    ):
        self.client = client
        self.agents = []

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
            try:
                print(f"  - Retrieving agent by name: {name}")
                # The list method with a name filter returns a list. We'll take the first one.
                found_agents = self.client.agents.list(name=name, limit=1)
                if not found_agents:
                    raise NotFoundError
                self.agents.append(SPDSAgent(found_agents[0], self.client))
            except NotFoundError:
                print(f"  - WARNING: Agent with name '{name}' not found. Skipping.")

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

        self.conversation_history += f"System: The topic is '{topic}'.\n"

        while True:
            try:
                human_input = input("\nYou: ")
            except EOFError:
                print("\nExiting chat.")
                break

            if human_input.lower() == "quit":
                print("Exiting chat.")
                break
            self.conversation_history += f"You: {human_input}\n"

            self._agent_turn(topic)

    def start_chat_with_topic(self, topic: str):
        """Starts and manages the group chat with a pre-set topic."""
        print(f"\nSwarm chat started with topic: '{topic}' (Mode: {self.conversation_mode.upper()})")
        print("Type 'quit' or Ctrl+D to end the session.")
        
        self.conversation_history += f"System: The topic is '{topic}'.\n"

        while True:
            try:
                human_input = input("\nYou: ")
            except EOFError:
                print("\nExiting chat.")
                break

            if human_input.lower() == "quit":
                print("Exiting chat.")
                break
            self.conversation_history += f"You: {human_input}\n"

            self._agent_turn(topic)

    def _agent_turn(self, topic: str):
        """Manages a single turn of agent responses based on conversation mode."""
        print(f"\n--- Assessing agent motivations ({self.conversation_mode.upper()} mode) ---")
        for agent in self.agents:
            agent.assess_motivation_and_priority(self.conversation_history, topic)
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
        """Helper method to extract message text from agent response."""
        message_text = ""
        try:
            for msg in response.messages:
                # Check for tool calls first (send_message)
                if hasattr(msg, 'tool_calls') and msg.tool_calls:
                    for tool_call in msg.tool_calls:
                        if hasattr(tool_call, 'function') and tool_call.function.name == 'send_message':
                            try:
                                import json
                                args = json.loads(tool_call.function.arguments)
                                message_text = args.get('message', '')
                                break
                            except:
                                pass
                
                # If no tool call, try regular content extraction
                if not message_text and hasattr(msg, 'content'):
                    if isinstance(msg.content, str):
                        message_text = msg.content
                    elif isinstance(msg.content, list) and msg.content:
                        content_item = msg.content[0]
                        if hasattr(content_item, 'text'):
                            message_text = content_item.text
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
        original_history = self.conversation_history
        
        # Phase 1: Independent responses
        print("\n=== 🧠 INITIAL RESPONSES ===")
        initial_responses = []
        
        for i, agent in enumerate(motivated_agents, 1):
            print(f"\n({i}/{len(motivated_agents)}) {agent.name} (priority: {agent.priority_score:.2f}) - Initial thoughts...")
            try:
                response = agent.speak(original_history)
                message_text = self._extract_agent_response(response)
                initial_responses.append((agent, message_text))
                print(f"{agent.name}: {message_text}")
            except Exception as e:
                fallback = "I have some thoughts but I'm having trouble expressing them."
                initial_responses.append((agent, fallback))
                print(f"{agent.name}: {fallback}")
                print(f"[Debug: Error in initial response - {e}]")
        
        # Phase 2: Response round - agents react to each other's ideas
        print("\n=== 💬 RESPONSE ROUND ===")
        print("Agents now respond to each other's initial thoughts...")
        
        # Build history with all initial responses
        history_with_initials = original_history
        for agent, response in initial_responses:
            history_with_initials += f"{agent.name}: {response}\n"
        
        response_prompt_addition = "\n\nNow that you've heard everyone's initial thoughts, please respond to what others have said. You might:\n- Agree and build on someone's idea\n- Respectfully disagree and explain why\n- Share a new insight sparked by what you heard\n- Ask questions about others' perspectives\n- Connect ideas between different responses\n\nRespond naturally to what resonates with you from the discussion above."
        
        for i, agent in enumerate(motivated_agents, 1):
            print(f"\n({i}/{len(motivated_agents)}) {agent.name} - Responding to the discussion...")
            try:
                response = agent.speak(history_with_initials + response_prompt_addition)
                message_text = self._extract_agent_response(response)
                print(f"{agent.name}: {message_text}")
                # Add responses to conversation history
                self.conversation_history += f"{agent.name}: {message_text}\n"
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
                response = agent.speak(self.conversation_history)
                message_text = self._extract_agent_response(response)
                print(f"{agent.name}: {message_text}")
                # Add each response to history so subsequent agents can see it
                self.conversation_history += f"{agent.name}: {message_text}\n"
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
            response = speaker.speak(self.conversation_history)
            message_text = self._extract_agent_response(response)
            print(f"{speaker.name}: {message_text}")
            self.conversation_history += f"{speaker.name}: {message_text}\n"
        except Exception as e:
            fallback = "I have some thoughts but I'm having trouble phrasing them."
            print(f"{speaker.name}: {fallback}")
            self.conversation_history += f"{speaker.name}: {fallback}\n"
            print(f"[Debug: Error in sequential response - {e}]")

    def _pure_priority_turn(self, motivated_agents: list, topic: str):
        """Always highest priority motivated agent speaks."""
        speaker = motivated_agents[0]  # Already sorted by priority
        print(f"\n=== 🎯 PURE PRIORITY MODE ===")
        print(f"\n({speaker.name} is speaking - highest priority: {speaker.priority_score:.2f})")

        try:
            response = speaker.speak(self.conversation_history)
            message_text = self._extract_agent_response(response)
            print(f"{speaker.name}: {message_text}")
            self.conversation_history += f"{speaker.name}: {message_text}\n"
        except Exception as e:
            fallback = "I have thoughts on this topic but I'm having difficulty expressing them."
            print(f"{speaker.name}: {fallback}")
            self.conversation_history += f"{speaker.name}: {fallback}\n"
            print(f"[Debug: Error in pure priority response - {e}]")
