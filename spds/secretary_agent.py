# spds/secretary_agent.py

from letta_client import Letta
from letta_client.types import AgentState
from datetime import datetime
from typing import List, Dict, Any, Optional
from . import config
import re
import json


class SecretaryAgent:
    """
    A specialized secretary agent that observes conversations and generates meeting minutes.
    Supports both formal board meeting minutes and casual group discussion notes.
    """
    
    def __init__(self, client: Letta, mode: str = "adaptive"):
        self.client = client
        self.mode = mode  # "formal", "casual", or "adaptive"
        self.agent = None
        self.conversation_log = []
        self.meeting_metadata = {}
        self.action_items = []
        self.decisions = []
        self.topics_covered = []
        
        # Create the secretary agent
        self._create_secretary_agent()
    
    def _create_secretary_agent(self):
        """Creates a specialized secretary agent on the Letta server."""
        
        if self.mode == "formal":
            persona = (
                "I am the Recording Secretary for Cyan Society. I maintain professional "
                "board meeting minutes following nonprofit governance standards. I use "
                "formal language and ensure proper documentation of motions, decisions, "
                "and action items."
            )
            name = "Cyan Secretary"
        elif self.mode == "casual":
            persona = (
                "I'm a friendly meeting facilitator who takes great notes! I capture "
                "the energy and key insights from group discussions in a conversational, "
                "approachable style. I help teams remember what they decided and what "
                "comes next."
            )
            name = "Meeting Buddy"
        else:  # adaptive
            persona = (
                "I am an adaptive meeting secretary who adjusts my documentation style "
                "to match the conversation. I can switch between formal board meeting "
                "minutes and casual group discussion notes based on the context and tone."
            )
            name = "Adaptive Secretary"
        
        system_prompt = (
            f"You are {name}. {persona} "
            "You observe conversations without participating in the main discussion. "
            "Your role is to document meetings, track decisions, and note action items. "
            "You have excellent attention to detail and organizational skills."
        )
        
        try:
            self.agent = self.client.agents.create(
                name=name,
                system=system_prompt,
                model=config.DEFAULT_AGENT_MODEL,
                embedding=config.DEFAULT_EMBEDDING_MODEL,
                include_base_tools=True,
            )
            print(f"✅ Created secretary agent: {name}")
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
        """Initialize meeting metadata and start documentation."""
        self.meeting_metadata = {
            "topic": topic,
            "participants": participants,
            "meeting_type": meeting_type,
            "start_time": datetime.now(),
            "mode": self.mode,
            "conversation_mode": None,  # Will be set by SwarmManager
        }
        self.conversation_log = []
        self.action_items = []
        self.decisions = []
        self.topics_covered = []
        
        print(f"📋 Meeting started: {topic}")
        print(f"👥 Participants: {', '.join(participants)}")
    
    def observe_message(self, speaker: str, message: str, metadata: Optional[Dict] = None):
        """Record a message from the conversation."""
        timestamp = datetime.now()
        
        entry = {
            "timestamp": timestamp,
            "speaker": speaker,
            "message": message,
            "metadata": metadata or {}
        }
        
        self.conversation_log.append(entry)
        
        # Auto-detect action items and decisions in the message
        self._auto_detect_content(speaker, message)
    
    def _auto_detect_content(self, speaker: str, message: str):
        """Automatically detect action items, decisions, and topic changes."""
        
        # Simple detection patterns - could be enhanced with LLM analysis
        action_patterns = [
            r"I'll|I will|I can|I should|let me",
            r"action item|todo|task|follow up|next step",
            r"by \w+day|by \w+ \d+|due|deadline"
        ]
        
        decision_patterns = [
            r"we decided|we agreed|consensus|motion|approved|adopted",
            r"let's go with|we'll use|final decision|settled on"
        ]
        
        # Check for action items
        for pattern in action_patterns:
            if re.search(pattern, message, re.IGNORECASE):
                self.action_items.append({
                    "speaker": speaker,
                    "content": message,
                    "timestamp": datetime.now(),
                    "status": "pending"
                })
                break
        
        # Check for decisions
        for pattern in decision_patterns:
            if re.search(pattern, message, re.IGNORECASE):
                self.decisions.append({
                    "speaker": speaker,
                    "content": message,
                    "timestamp": datetime.now()
                })
                break
    
    def add_action_item(self, description: str, assignee: str = None, due_date: str = None):
        """Manually add an action item."""
        action_item = {
            "description": description,
            "assignee": assignee,
            "due_date": due_date,
            "timestamp": datetime.now(),
            "status": "pending"
        }
        self.action_items.append(action_item)
        print(f"✅ Action item added: {description}")
    
    def add_decision(self, decision: str, context: str = None):
        """Manually record a decision."""
        decision_record = {
            "decision": decision,
            "context": context,
            "timestamp": datetime.now()
        }
        self.decisions.append(decision_record)
        print(f"📋 Decision recorded: {decision}")
    
    def generate_minutes(self) -> str:
        """Generate meeting minutes in the appropriate format."""
        if not self.meeting_metadata:
            return "No meeting in progress."
        
        if self.mode == "formal" or (self.mode == "adaptive" and self._should_use_formal()):
            return self._generate_formal_minutes()
        else:
            return self._generate_casual_minutes()
    
    def _should_use_formal(self) -> bool:
        """Determine if adaptive mode should use formal style."""
        # Check for formal indicators in conversation
        formal_indicators = [
            "motion", "board", "approve", "consensus", "meeting minutes",
            "agenda", "official", "record", "vote", "resolution"
        ]
        
        conversation_text = " ".join([entry["message"] for entry in self.conversation_log])
        formal_count = sum(1 for indicator in formal_indicators 
                          if indicator in conversation_text.lower())
        
        # Use formal style if multiple formal indicators present
        return formal_count >= 2
    
    def _generate_formal_minutes(self) -> str:
        """Generate formal board meeting minutes."""
        metadata = self.meeting_metadata
        start_time = metadata["start_time"]
        end_time = datetime.now()
        duration = end_time - start_time
        
        # Format duration
        duration_str = f"{duration.seconds // 60} minutes"
        
        minutes = f"""# CYAN SOCIETY
## MINUTES OF THE BOARD OF DIRECTORS MEETING

**Meeting Type**: {metadata.get('meeting_type', 'Regular Board Meeting').title()}
**Date**: {start_time.strftime('%B %d, %Y')}
**Time**: {start_time.strftime('%I:%M %p')} - {end_time.strftime('%I:%M %p')} ({duration_str})
**Location**: Virtual Meeting via SPDS Platform
**Topic**: {metadata['topic']}

### ATTENDANCE
**Present**: """
        
        # Add participants
        for participant in metadata['participants']:
            minutes += f"\n- {participant} - Board Member"
        
        minutes += f"\n\n**Recording Secretary**: {self.agent.name if self.agent else 'Secretary Agent'}"
        minutes += f"\n**Quorum**: Present ✅"
        
        minutes += "\n\n### CALL TO ORDER"
        minutes += f"\nThe meeting was called to order at {start_time.strftime('%I:%M %p')}."
        
        # Add main discussion
        minutes += f"\n\n### DISCUSSION AND ACTIONS\n"
        minutes += f"#### Topic: {metadata['topic']}\n"
        
        # Summarize key discussion points
        if self.conversation_log:
            minutes += "**Discussion Summary**: "
            minutes += self._summarize_discussion_formal()
        
        # Add decisions
        if self.decisions:
            minutes += "\n\n**Decisions Made**:\n"
            for i, decision in enumerate(self.decisions, 1):
                minutes += f"{i}. {decision['decision']}\n"
        
        # Add action items
        if self.action_items:
            minutes += "\n**Action Items**:\n"
            for item in self.action_items:
                assignee = item.get('assignee', 'Board')
                due = item.get('due_date', 'TBD')
                description = item.get('description', item.get('content', ''))
                minutes += f"- [ ] {description} - Assigned to: {assignee} - Due: {due}\n"
        
        minutes += f"\n### ADJOURNMENT"
        minutes += f"\nThe meeting was adjourned at {end_time.strftime('%I:%M %p')}."
        
        minutes += f"\n\n---"
        minutes += f"\n**Minutes Prepared by**: {self.agent.name if self.agent else 'Secretary Agent'}"
        minutes += f"\n**Date of Preparation**: {datetime.now().strftime('%B %d, %Y')}"
        minutes += f"\n**Status**: Draft"
        
        return minutes
    
    def _generate_casual_minutes(self) -> str:
        """Generate casual meeting notes."""
        metadata = self.meeting_metadata
        start_time = metadata["start_time"]
        end_time = datetime.now()
        duration = end_time - start_time
        
        # Format duration
        duration_str = f"{duration.seconds // 60} minutes"
        
        minutes = f"""# 💬 Group Discussion: {metadata['topic']}

**Date**: {start_time.strftime('%B %d, %Y')}  
**Duration**: {duration_str}  
**Participants**: {', '.join(metadata['participants'])}  
**Vibe**: {self._get_conversation_vibe()} 

## 🎯 What We Talked About

### {metadata['topic']}
"""
        
        # Add casual summary
        if self.conversation_log:
            minutes += self._summarize_discussion_casual()
        
        # Add decisions in casual style
        if self.decisions:
            minutes += "\n\n## ✅ What We Decided\n"
            for decision in self.decisions:
                minutes += f"- {decision['decision']}\n"
        
        # Add action items in casual style
        if self.action_items:
            minutes += "\n## 📋 Action Items\n"
            for item in self.action_items:
                assignee = item.get('assignee', 'Someone')
                description = item.get('description', item.get('content', ''))
                minutes += f"- [ ] {description}"
                if assignee != 'Someone':
                    minutes += f" ({assignee})"
                minutes += "\n"
        
        # Add some fun elements
        if len(self.conversation_log) > 10:
            minutes += "\n## 💭 Random Good Ideas\n"
            minutes += "- Some great insights shared!\n"
            minutes += "- Lots of creative energy in this discussion\n"
        
        minutes += f"\n**Next Hangout**: TBD - same energy! 🚀"
        
        return minutes
    
    def _get_conversation_vibe(self) -> str:
        """Determine the overall vibe of the conversation."""
        if len(self.conversation_log) < 3:
            return "Quick sync"
        elif len(self.conversation_log) > 20:
            return "Deep dive discussion 🧠"
        elif len(self.decisions) > 0:
            return "Productive decision-making 💪"
        else:
            return "Collaborative brainstorming 🧠"
    
    def _summarize_discussion_formal(self) -> str:
        """Create a formal summary of the discussion."""
        if not self.conversation_log:
            return "Discussion details were not recorded."
        
        # Group messages by speaker
        speaker_points = {}
        for entry in self.conversation_log:
            speaker = entry["speaker"]
            if speaker not in speaker_points:
                speaker_points[speaker] = []
            speaker_points[speaker].append(entry["message"])
        
        summary = []
        for speaker, messages in speaker_points.items():
            if len(messages) > 0:
                # Take first substantial message as key point
                key_message = next((msg for msg in messages if len(msg) > 20), messages[0])
                summary.append(f"{speaker} emphasized: {key_message[:100]}...")
        
        return " ".join(summary)
    
    def _summarize_discussion_casual(self) -> str:
        """Create a casual summary of the discussion."""
        if not self.conversation_log:
            return "We had a great chat but I missed some details! 😅"
        
        participants = list(set(entry["speaker"] for entry in self.conversation_log))
        
        summary = f"The crew dove into {self.meeting_metadata['topic']}! "
        
        if len(participants) > 1:
            summary += f"{participants[0]} kicked things off, "
            if len(participants) > 2:
                summary += f"{', '.join(participants[1:-1])} jumped in with insights, "
                summary += f"and {participants[-1]} brought it home. "
            else:
                summary += f"and {participants[1]} brought some great perspectives. "
        
        summary += "Lots of good energy and solid ideas shared!"
        
        return summary
    
    def get_conversation_stats(self) -> Dict[str, Any]:
        """Get statistics about the conversation."""
        if not self.conversation_log:
            return {}
        
        participants = {}
        for entry in self.conversation_log:
            speaker = entry["speaker"]
            if speaker not in participants:
                participants[speaker] = {"messages": 0, "words": 0}
            participants[speaker]["messages"] += 1
            participants[speaker]["words"] += len(entry["message"].split())
        
        total_messages = len(self.conversation_log)
        duration = (datetime.now() - self.meeting_metadata["start_time"]).seconds // 60
        
        return {
            "total_messages": total_messages,
            "duration_minutes": duration,
            "participants": participants,
            "action_items": len(self.action_items),
            "decisions": len(self.decisions),
            "messages_per_minute": round(total_messages / max(duration, 1), 1)
        }