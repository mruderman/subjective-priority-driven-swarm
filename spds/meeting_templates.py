# spds/meeting_templates.py

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Dict, List, Optional


class BaseTemplate(ABC):
    """Base class for meeting minute templates."""

    @abstractmethod
    def generate(self, meeting_data: Dict[str, Any]) -> str:
        pass

    def format_duration(self, start_time: datetime, end_time: datetime) -> str:
        """Format meeting duration in a human-readable way."""
        duration = end_time - start_time
        minutes = duration.seconds // 60
        if minutes < 60:
            return f"{minutes} minutes"
        else:
            hours = minutes // 60
            remaining_minutes = minutes % 60
            if remaining_minutes == 0:
                return f"{hours} hour{'s' if hours > 1 else ''}"
            else:
                return f"{hours} hour{'s' if hours > 1 else ''} {remaining_minutes} minutes"


class BoardMinutesTemplate(BaseTemplate):
    """Template for formal Cyan Society board meeting minutes."""

    def __init__(self, organization_name: str = "CYAN SOCIETY"):
        self.organization_name = organization_name

    def generate(self, meeting_data: Dict[str, Any]) -> str:
        """Generate formal board meeting minutes."""
        metadata = meeting_data.get("metadata", {})
        conversation_log = meeting_data.get("conversation_log", [])
        action_items = meeting_data.get("action_items", [])
        decisions = meeting_data.get("decisions", [])
        stats = meeting_data.get("stats", {})

        start_time = metadata.get("start_time", datetime.now())
        end_time = datetime.now()

        # Header
        minutes = f"""# {self.organization_name}
## MINUTES OF THE BOARD OF DIRECTORS MEETING

**Meeting Type**: {metadata.get('meeting_type', 'Regular Board Meeting').title()}
**Date**: {start_time.strftime('%B %d, %Y')}
**Time**: {start_time.strftime('%I:%M %p')} - {end_time.strftime('%I:%M %p')} ({self.format_duration(start_time, end_time)})
**Location**: Virtual Meeting via SPDS Platform
**Topic**: {metadata.get('topic', 'General Discussion')}
"""

        # Meeting number (simple sequential based on date)
        meeting_number = f"{start_time.year}-{start_time.month:02d}{start_time.day:02d}"
        minutes += f"**Meeting Number**: {meeting_number}\n"

        # Attendance
        minutes += "\n### ATTENDANCE\n**Present**: \n"
        participants = metadata.get("participants", [])
        for participant in participants:
            # Try to extract model info if available
            if isinstance(participant, dict):
                name = participant.get("name", "Unknown")
                model = participant.get("model", "")
                expertise = participant.get("expertise", "Board Member")
                minutes += f"- {name} - {expertise}"
                if model:
                    minutes += f" (Model: {model})"
                minutes += "\n"
            else:
                minutes += f"- {participant} - Board Member\n"

        minutes += f"\n**Recording Secretary**: Secretary Agent"
        minutes += f"\n**Quorum**: Present ✅\n"

        # Call to order
        minutes += "\n### CALL TO ORDER\n"
        minutes += (
            f"The meeting was called to order at {start_time.strftime('%I:%M %p')}.\n"
        )

        # Agenda (if topics were covered)
        topics_covered = meeting_data.get("topics_covered", [])
        if topics_covered:
            minutes += "\n### AGENDA\n"
            for i, topic in enumerate(topics_covered, 1):
                minutes += f"{i}. {topic}\n"

        # Main discussion
        minutes += f"\n### DISCUSSION AND ACTIONS\n"
        minutes += f"#### Topic: {metadata.get('topic', 'General Discussion')}\n"

        # Discussion summary
        if conversation_log:
            minutes += "**Discussion Summary**: "
            minutes += self._generate_formal_discussion_summary(
                conversation_log, participants
            )
            minutes += "\n"

        # Key perspectives
        if conversation_log:
            minutes += "\n**Key Perspectives Shared**:\n"
            speaker_summaries = self._extract_key_perspectives(conversation_log)
            for speaker, summary in speaker_summaries.items():
                minutes += f"- **{speaker}**: {summary}\n"

        # Decisions
        if decisions:
            minutes += "\n**Motions and Decisions**:\n"
            for i, decision in enumerate(decisions, 1):
                minutes += f"{i}. **Motion**: {decision.get('decision', decision.get('content', ''))}\n"
                minutes += f"   **Status**: Approved by consensus\n"
                if decision.get("context"):
                    minutes += f"   **Context**: {decision['context']}\n"

        # Action items
        if action_items:
            minutes += "\n**Action Items**:\n"
            for item in action_items:
                description = item.get("description", item.get("content", ""))
                assignee = item.get("assignee", "Board")
                due_date = item.get("due_date", "TBD")
                minutes += f"- [ ] {description}\n"
                minutes += f"  - **Assigned to**: {assignee}\n"
                minutes += f"  - **Due Date**: {due_date}\n"

        # Adjournment
        minutes += f"\n### ADJOURNMENT\n"
        minutes += f"The meeting was adjourned at {end_time.strftime('%I:%M %p')}.\n"

        # Next meeting
        minutes += f"\n**Next Meeting**: To be scheduled\n"

        # Footer
        minutes += f"\n---\n"
        minutes += f"**Minutes Prepared by**: Secretary Agent\n"
        minutes += f"**Date of Preparation**: {datetime.now().strftime('%B %d, %Y')}\n"
        minutes += f"**Status**: Draft\n"
        minutes += f"**Distribution**: Board Members\n"

        # Meeting statistics
        if stats:
            minutes += f"\n### MEETING STATISTICS\n"
            minutes += f"- **Total Messages**: {stats.get('total_messages', 0)}\n"
            minutes += (
                f"- **Active Participants**: {len(stats.get('participants', {}))}\n"
            )
            minutes += f"- **Decisions Made**: {stats.get('decisions', 0)}\n"
            minutes += f"- **Action Items Created**: {stats.get('action_items', 0)}\n"

        return minutes

    def _generate_formal_discussion_summary(
        self, conversation_log: List[Dict], participants: List
    ) -> str:
        """Generate a formal summary of the discussion."""
        if not conversation_log:
            return "No detailed discussion recorded."

        # Count substantive messages (longer than 20 characters)
        substantive_messages = [
            entry for entry in conversation_log if len(entry.get("message", "")) > 20
        ]

        if not substantive_messages:
            return "Brief discussion held among board members."

        summary = f"The board engaged in comprehensive discussion on the topic. "
        summary += f"A total of {len(substantive_messages)} substantive contributions were made "
        summary += f"by {len(set(entry['speaker'] for entry in substantive_messages))} participants. "

        # Identify key themes if possible
        all_text = " ".join([entry["message"] for entry in substantive_messages])
        if "strategy" in all_text.lower():
            summary += (
                "Strategic considerations were emphasized throughout the discussion. "
            )
        if "implementation" in all_text.lower():
            summary += "Implementation approaches were thoroughly examined. "

        return summary

    def _extract_key_perspectives(self, conversation_log: List[Dict]) -> Dict[str, str]:
        """Extract key perspectives from each speaker."""
        speaker_perspectives = {}

        for entry in conversation_log:
            speaker = entry.get("speaker", "Unknown")
            message = entry.get("message", "")

            # Skip very short messages
            if len(message) < 30:
                continue

            # Take the first substantial message from each speaker as their key perspective
            if speaker not in speaker_perspectives:
                # Truncate long messages for readability
                if len(message) > 150:
                    summary = message[:147] + "..."
                else:
                    summary = message
                speaker_perspectives[speaker] = summary

        return speaker_perspectives


class CasualMinutesTemplate(BaseTemplate):
    """Template for casual group discussion notes."""

    def generate(self, meeting_data: Dict[str, Any]) -> str:
        """Generate casual meeting notes."""
        metadata = meeting_data.get("metadata", {})
        conversation_log = meeting_data.get("conversation_log", [])
        action_items = meeting_data.get("action_items", [])
        decisions = meeting_data.get("decisions", [])
        stats = meeting_data.get("stats", {})

        start_time = metadata.get("start_time", datetime.now())
        end_time = datetime.now()

        # Casual header with emoji
        minutes = f"""# 💬 Group Discussion: {metadata.get('topic', 'Team Chat')}

**Date**: {start_time.strftime('%B %d, %Y')}  
**Duration**: {self.format_duration(start_time, end_time)}  
**Participants**: {self._format_participants_casual(metadata.get('participants', []))}  
**Vibe**: {self._determine_conversation_vibe(conversation_log, decisions, action_items)}

## 🎯 What We Talked About

### {metadata.get('topic', 'Our Discussion')}
"""

        # Casual discussion summary
        if conversation_log:
            minutes += self._generate_casual_discussion_summary(
                conversation_log, metadata.get("participants", [])
            )
        else:
            minutes += "We had a great chat but I missed some of the details! 😅"

        # Key insights in casual style
        if conversation_log and len(conversation_log) > 5:
            minutes += "\n\n**Key Insights**:\n"
            insights = self._extract_casual_insights(conversation_log)
            for insight in insights:
                minutes += f"- {insight}\n"

        # Decisions in casual style
        if decisions:
            minutes += "\n\n## ✅ What We Decided\n"
            for decision in decisions:
                decision_text = decision.get("decision", decision.get("content", ""))
                minutes += f"- {decision_text}\n"

        # Action items in casual style
        if action_items:
            minutes += "\n## 📋 Action Items\n"
            for item in action_items:
                description = item.get("description", item.get("content", ""))
                assignee = item.get("assignee")
                due_date = item.get("due_date")

                minutes += f"- [ ] {description}"
                if assignee:
                    minutes += f" ({assignee})"
                if due_date:
                    minutes += f" - due {due_date}"
                minutes += "\n"

        # Fun elements for longer conversations
        if len(conversation_log) > 10:
            minutes += "\n## 💭 Random Good Ideas\n"
            good_ideas = self._extract_good_ideas(conversation_log)
            for idea in good_ideas:
                minutes += f"- {idea}\n"

        # Stats in a fun way
        if stats and stats.get("total_messages", 0) > 0:
            minutes += f"\n## 📊 Quick Stats\n"
            minutes += f"- **Total messages**: {stats.get('total_messages', 0)}\n"
            minutes += (
                f"- **Most chatty**: {self._get_most_active_participant(stats)}\n"
            )
            if stats.get("messages_per_minute", 0) > 5:
                minutes += f"- **Energy level**: High! 🔥 ({stats.get('messages_per_minute', 0)} messages/min)\n"
            else:
                minutes += f"- **Energy level**: Chill and thoughtful 🧘\n"

        # Casual closing
        minutes += f"\n**Next Hangout**: TBD - same energy! 🚀"

        return minutes

    def _format_participants_casual(self, participants: List) -> str:
        """Format participants list in a casual way."""
        if not participants:
            return "The usual suspects"

        names = []
        for participant in participants:
            if isinstance(participant, dict):
                names.append(participant.get("name", "Someone"))
            else:
                names.append(str(participant))

        if len(names) <= 2:
            return " and ".join(names)
        else:
            return ", ".join(names[:-1]) + f", and {names[-1]}"

    def _determine_conversation_vibe(
        self, conversation_log: List[Dict], decisions: List, action_items: List
    ) -> str:
        """Determine the overall vibe of the conversation."""
        message_count = len(conversation_log)

        if message_count < 5:
            return "Quick sync ⚡"
        elif len(decisions) > 2:
            return "Productive decision-making 💪"
        elif len(action_items) > 3:
            return "Action-packed planning 🎯"
        elif message_count > 25:
            return "Deep dive discussion 🧠"
        elif message_count > 15:
            return "Collaborative brainstorming 💡"
        else:
            return "Chill and productive 😊"

    def _generate_casual_discussion_summary(
        self, conversation_log: List[Dict], participants: List
    ) -> str:
        """Generate a casual summary of the discussion."""
        if not conversation_log:
            return "We had a great chat but the details got away from me! 😅"

        speakers = list(set(entry["speaker"] for entry in conversation_log))

        if len(speakers) == 1:
            return f"{speakers[0]} shared some great thoughts and insights!"

        summary = f"The crew really dove into this one! "

        # Mention the flow of conversation
        if len(speakers) > 1:
            if len(conversation_log) > 10:
                summary += f"{speakers[0]} kicked things off, and then everyone jumped in with their perspectives. "
            else:
                summary += f"Good back-and-forth between {self._format_participants_casual(speakers)}. "

        # Add some personality based on conversation length
        message_count = len(conversation_log)
        if message_count > 20:
            summary += "Lots of energy and great ideas flying around! "
        elif message_count > 10:
            summary += "Solid discussion with some really thoughtful points. "
        else:
            summary += "Concise but impactful conversation. "

        return summary

    def _extract_casual_insights(self, conversation_log: List[Dict]) -> List[str]:
        """Extract key insights in a casual way."""
        insights = []

        # Look for messages with key phrases that indicate insights
        insight_indicators = [
            "I think",
            "what if",
            "maybe we should",
            "the key is",
            "important point",
        ]

        for entry in conversation_log:
            message = entry.get("message", "")
            speaker = entry.get("speaker", "Someone")

            # Skip very short messages
            if len(message) < 40:
                continue

            # Check for insight indicators
            for indicator in insight_indicators:
                if indicator.lower() in message.lower():
                    # Create a casual summary
                    if len(message) > 100:
                        insight = f"{speaker}'s point about {message[:80]}..."
                    else:
                        insight = f'{speaker}: "{message}"'
                    insights.append(insight)
                    break

            # Limit to top 3 insights
            if len(insights) >= 3:
                break

        return insights

    def _extract_good_ideas(self, conversation_log: List[Dict]) -> List[str]:
        """Extract good ideas mentioned in conversation."""
        ideas = []

        # Look for creative or solution-oriented messages
        idea_indicators = [
            "idea",
            "solution",
            "approach",
            "strategy",
            "could",
            "might",
            "what about",
        ]

        for entry in conversation_log:
            message = entry.get("message", "")
            speaker = entry.get("speaker", "Someone")

            if len(message) < 30:
                continue

            for indicator in idea_indicators:
                if indicator.lower() in message.lower():
                    idea = f"{speaker}'s {indicator} was interesting"
                    ideas.append(idea)
                    break

            if len(ideas) >= 3:
                break

        # Add some default good vibes if no specific ideas found
        if not ideas:
            ideas = [
                "Great energy throughout the conversation",
                "Everyone brought unique perspectives",
                "Good collaborative spirit",
            ]

        return ideas

    def _get_most_active_participant(self, stats: Dict[str, Any]) -> str:
        """Get the most active participant in a fun way."""
        participants = stats.get("participants", {})
        if not participants:
            return "Everyone equally!"

        most_active = max(participants.items(), key=lambda x: x[1].get("messages", 0))
        return f"{most_active[0]} (they had a lot to say! 💬)"
