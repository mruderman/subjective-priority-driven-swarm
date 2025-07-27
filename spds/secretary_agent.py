# spds/secretary_agent.py

from letta_client import Letta, CreateBlock, MessageCreate
from letta_client.types import AgentState
from datetime import datetime
from typing import List, Dict, Any, Optional
from . import config
import re
import json


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
        
        # Create the secretary agent
        self._create_secretary_agent()
    
    def _create_secretary_agent(self):
        """Creates or retrieves a specialized secretary agent using proper Letta patterns."""
        
        if self.mode == "formal":
            persona = (
                "I am the Recording Secretary for Cyan Society. I maintain professional "
                "board meeting minutes following nonprofit governance standards. I use "
                "formal language and ensure proper documentation of motions, decisions, "
                "and action items. I store meeting information in my memory and can generate "
                "comprehensive meeting minutes when requested."
            )
            name = "Cyan Secretary"
        elif self.mode == "casual":
            persona = (
                "I'm a friendly meeting facilitator who takes great notes! I capture "
                "the energy and key insights from group discussions in a conversational, "
                "approachable style. I help teams remember what they decided and what "
                "comes next. I store conversation highlights in my memory."
            )
            name = "Meeting Buddy"
        else:  # adaptive
            persona = (
                "I am an adaptive meeting secretary who adjusts my documentation style "
                "to match the conversation. I can switch between formal board meeting "
                "minutes and casual group discussion notes based on the context and tone. "
                "I actively listen to conversations, store key information in my memory, "
                "and generate appropriate meeting documentation when requested."
            )
            name = "Adaptive Secretary"
        
        # First, try to find an existing secretary agent
        try:
            existing_agents = self.client.agents.list()
            for agent in existing_agents:
                if agent.name == name:
                    self.agent = agent
                    print(f"♻️ Reusing existing secretary agent: {name}")
                    return
        except Exception as e:
            print(f"⚠️ Could not search for existing agents: {e}")
        
        # Create new agent using proper Letta memory blocks pattern
        try:
            self.agent = self.client.agents.create(
                name=name,
                memory_blocks=[
                    CreateBlock(
                        label="human",
                        value="I am working with a team of AI agents in group conversations and meetings."
                    ),
                    CreateBlock(
                        label="persona",
                        value=persona
                    ),
                    CreateBlock(
                        label="meeting_context",
                        value="No active meeting. Ready to take notes when a meeting begins.",
                        description="Stores current meeting information, participants, topic, and ongoing notes"
                    ),
                    CreateBlock(
                        label="notes_style",
                        value=f"Documentation style: {self.mode}",
                        description="Preferred style for meeting documentation (formal, casual, or adaptive)"
                    )
                ],
                model=config.DEFAULT_AGENT_MODEL,
                embedding=config.DEFAULT_EMBEDDING_MODEL,
                include_base_tools=True,
            )
            print(f"✅ Created new secretary agent: {name}")
        except Exception as e:
            print(f"❌ Failed to create secretary agent: {e}")
            raise
    
    def set_mode(self, mode: str):
        """Change the secretary's documentation mode."""
        if mode not in ["formal", "casual", "adaptive"]:
            raise ValueError("Mode must be 'formal', 'casual', or 'adaptive'")
        
        self.mode = mode
        print(f"📝 Secretary mode changed to: {mode}")
    
    def start_meeting(self, topic: str, participants: List[str], meeting_type: str = "discussion"):
        """Initialize meeting using agent communication."""
        self.meeting_metadata = {
            "topic": topic,
            "participants": participants,
            "meeting_type": meeting_type,
            "start_time": datetime.now(),
            "mode": self.mode,
            "conversation_mode": None,  # Will be set by SwarmManager
        }
        
        # Send meeting start message to the secretary agent
        meeting_start_message = (
            f"A new {meeting_type} meeting has started.\n"
            f"Topic: {topic}\n"
            f"Participants: {', '.join(participants)}\n"
            f"Please begin taking notes in {self.mode} style. "
            f"Store the meeting information in your memory and prepare to document the conversation."
        )
        
        try:
            response = self.client.agents.messages.create(
                agent_id=self.agent.id,
                messages=[
                    MessageCreate(
                        role="user",
                        content=meeting_start_message
                    )
                ]
            )
            print(f"📋 Meeting started: {topic}")
            print(f"👥 Participants: {', '.join(participants)}")
            print(f"🤖 Secretary: {self._extract_agent_response(response)}")
        except Exception as e:
            print(f"❌ Failed to notify secretary of meeting start: {e}")
            
    def _extract_agent_response(self, response) -> str:
        """Extract the main response from agent messages."""
        for msg in response.messages:
            if hasattr(msg, 'message_type') and msg.message_type == 'assistant_message':
                if hasattr(msg, 'content') and msg.content:
                    return msg.content
        # Fallback
        return "Secretary is ready to take notes."
    
    def observe_message(self, speaker: str, message: str, metadata: Optional[Dict] = None):
        """Send conversation message to the secretary agent for active processing."""
        if not self.agent:
            return
            
        # Format message for the secretary
        formatted_message = f"{speaker}: {message}"
        
        # Send to secretary agent for processing and note-taking
        try:
            self.client.agents.messages.create(
                agent_id=self.agent.id,
                messages=[
                    MessageCreate(
                        role="user",
                        content=f"Please note this in the meeting: {formatted_message}"
                    )
                ]
            )
        except Exception as e:
            print(f"⚠️ Secretary failed to process message from {speaker}: {e}")
    
    # Removed old static implementations - now using AI agent for everything
    
    def add_action_item(self, description: str, assignee: str = None, due_date: str = None):
        """Manually add an action item through the secretary agent."""
        if not self.agent:
            print(f"⚠️ Secretary agent not available")
            return
            
        action_message = f"Please record this action item: {description}"
        if assignee:
            action_message += f" (assigned to: {assignee})"
        if due_date:
            action_message += f" (due: {due_date})"
            
        try:
            self.client.agents.messages.create(
                agent_id=self.agent.id,
                messages=[
                    MessageCreate(
                        role="user",
                        content=action_message
                    )
                ]
            )
            print(f"✅ Action item recorded: {description}")
        except Exception as e:
            print(f"❌ Failed to record action item: {e}")
    
    def add_decision(self, decision: str, context: str = None):
        """Manually record a decision through the secretary agent."""
        if not self.agent:
            print(f"⚠️ Secretary agent not available")
            return
            
        decision_message = f"Please record this decision: {decision}"
        if context:
            decision_message += f" (context: {context})"
            
        try:
            self.client.agents.messages.create(
                agent_id=self.agent.id,
                messages=[
                    MessageCreate(
                        role="user",
                        content=decision_message
                    )
                ]
            )
            print(f"📋 Decision recorded: {decision}")
        except Exception as e:
            print(f"❌ Failed to record decision: {e}")
            
    def get_conversation_stats(self) -> Dict[str, Any]:
        """Get conversation statistics from the secretary agent."""
        if not self.agent:
            return {}
            
        try:
            response = self.client.agents.messages.create(
                agent_id=self.agent.id,
                messages=[
                    MessageCreate(
                        role="user",
                        content="Please provide a summary of the meeting statistics - how many messages, participants, decisions, action items, etc."
                    )
                ]
            )
            
            stats_text = self._extract_agent_response(response)
            
            # Parse basic stats from the meeting metadata
            if self.meeting_metadata:
                duration = (datetime.now() - self.meeting_metadata["start_time"]).seconds // 60
                return {
                    "duration_minutes": duration,
                    "participants": self.meeting_metadata.get("participants", []),
                    "topic": self.meeting_metadata.get("topic", "Unknown"),
                    "meeting_type": self.meeting_metadata.get("meeting_type", "discussion"),
                    "summary": stats_text
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
            f"Format the minutes appropriately for the meeting type."
        )
        
        try:
            response = self.client.agents.messages.create(
                agent_id=self.agent.id,
                messages=[
                    MessageCreate(
                        role="user",
                        content=minutes_request
                    )
                ]
            )
            
            # Extract the agent's response
            minutes = self._extract_agent_response(response)
            if minutes and len(minutes) > 50:  # Ensure we got substantial content
                return minutes
            else:
                return "Secretary is still processing the meeting notes. Please try again in a moment."
                
        except Exception as e:
            print(f"❌ Failed to generate minutes: {e}")
            return f"Error generating minutes: {str(e)}"
