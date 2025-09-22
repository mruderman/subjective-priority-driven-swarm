# spds/export_manager.py

import json
import logging
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from . import config
from .meeting_templates import BoardMinutesTemplate, CasualMinutesTemplate
from .session_store import SessionState, get_default_session_store

logger = logging.getLogger(__name__)


class ExportManager:
    """
    Manages the export of conversation data and meeting minutes in various formats.
    Supports markdown, text, and JSON exports with different styling options.
    """

    def __init__(self, export_directory: str = None):
        self.export_directory = Path(
            export_directory or config.DEFAULT_EXPORT_DIRECTORY
        )
        self.export_directory.mkdir(exist_ok=True)

        # Initialize templates
        self.board_template = BoardMinutesTemplate(config.ORGANIZATION_NAME)
        self.casual_template = CasualMinutesTemplate()

    def export_meeting_minutes(
        self,
        meeting_data: Dict[str, Any],
        format_type: str = "formal",
        filename: Optional[str] = None,
    ) -> str:
        """
        Export meeting minutes in the specified format.

        Args:
            meeting_data: Complete meeting data from SecretaryAgent
            format_type: "formal" for board minutes, "casual" for friendly notes
            filename: Optional custom filename

        Returns:
            Path to the exported file
        """
        if format_type == "formal":
            content = self.board_template.generate(meeting_data)
            default_name = self._generate_filename("board_minutes")
        else:
            content = self.casual_template.generate(meeting_data)
            default_name = self._generate_filename("meeting_notes")

        filename = filename or default_name
        filepath = self.export_directory / f"{filename}.md"

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)

        print(f"📄 Meeting minutes exported: {filepath}")
        return str(filepath)

    def export_raw_transcript(
        self,
        conversation_log: List[Dict[str, Any]],
        metadata: Dict[str, Any],
        filename: Optional[str] = None,
    ) -> str:
        """
        Export raw conversation transcript as plain text.

        Args:
            conversation_log: List of conversation entries
            metadata: Meeting metadata
            filename: Optional custom filename

        Returns:
            Path to the exported file
        """
        filename = filename or self._generate_filename("transcript")
        filepath = self.export_directory / f"{filename}.txt"

        content = f"Conversation Transcript\n"
        content += f"Topic: {metadata.get('topic', 'Unknown')}\n"
        content += f"Date: {datetime.now().strftime('%B %d, %Y %I:%M %p')}\n"
        content += f"Participants: {', '.join(metadata.get('participants', []))}\n"
        content += f"{'=' * 50}\n\n"

        for entry in conversation_log:
            timestamp = entry.get("timestamp", datetime.now())
            speaker = entry.get("speaker", "Unknown")
            message = entry.get("message", "")

            content += f"[{timestamp.strftime('%H:%M:%S')}] {speaker}: {message}\n"

        content += f"\n{'=' * 50}\n"
        content += f"End of transcript - {len(conversation_log)} messages total\n"

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)

        print(f"📝 Raw transcript exported: {filepath}")
        return str(filepath)

    def export_structured_data(
        self, meeting_data: Dict[str, Any], filename: Optional[str] = None
    ) -> str:
        """
        Export complete meeting data as structured JSON.

        Args:
            meeting_data: Complete meeting data from SecretaryAgent
            filename: Optional custom filename

        Returns:
            Path to the exported file
        """
        filename = filename or self._generate_filename("meeting_data")
        filepath = self.export_directory / f"{filename}.json"

        # Prepare data for JSON serialization
        exportable_data = self._prepare_for_json(meeting_data)

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(exportable_data, f, indent=2, ensure_ascii=False)

        print(f"📊 Structured data exported: {filepath}")
        return str(filepath)

    def export_action_items(
        self,
        action_items: List[Dict[str, Any]],
        metadata: Dict[str, Any],
        filename: Optional[str] = None,
    ) -> str:
        """
        Export action items as a formatted markdown checklist.

        Args:
            action_items: List of action items
            metadata: Meeting metadata
            filename: Optional custom filename

        Returns:
            Path to the exported file
        """
        filename = filename or self._generate_filename("action_items")
        filepath = self.export_directory / f"{filename}.md"

        content = f"# Action Items\n\n"
        content += f"**Meeting**: {metadata.get('topic', 'Unknown')}\n"
        content += f"**Date**: {datetime.now().strftime('%B %d, %Y')}\n"
        content += f"**Total Items**: {len(action_items)}\n\n"

        if not action_items:
            content += "No action items were recorded.\n"
        else:
            content += "## Outstanding Tasks\n\n"

            for i, item in enumerate(action_items, 1):
                description = item.get(
                    "description", item.get("content", f"Action item {i}")
                )
                assignee = item.get("assignee", "Unassigned")
                due_date = item.get("due_date", "No deadline")
                status = item.get("status", "pending")

                checkbox = "☑️" if status == "completed" else "⬜"

                content += f"{checkbox} **{description}**\n"
                content += f"   - **Assigned to**: {assignee}\n"
                content += f"   - **Due**: {due_date}\n"
                content += f"   - **Status**: {status}\n\n"

            # Add summary
            completed = sum(
                1 for item in action_items if item.get("status") == "completed"
            )
            pending = len(action_items) - completed

            content += f"## Summary\n"
            content += f"- ✅ Completed: {completed}\n"
            content += f"- ⏳ Pending: {pending}\n"
            content += f"- 📊 Progress: {(completed/len(action_items)*100):.0f}%\n"

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)

        print(f"✅ Action items exported: {filepath}")
        return str(filepath)

    def export_formatted_conversation(
        self,
        conversation_log: List[Dict[str, Any]],
        metadata: Dict[str, Any],
        filename: Optional[str] = None,
    ) -> str:
        """
        Export conversation in a formatted markdown style with agent styling.

        Args:
            conversation_log: List of conversation entries
            metadata: Meeting metadata
            filename: Optional custom filename

        Returns:
            Path to the exported file
        """
        filename = filename or self._generate_filename("formatted_conversation")
        filepath = self.export_directory / f"{filename}.md"

        content = f"# 💬 Conversation: {metadata.get('topic', 'Group Discussion')}\n\n"

        # Header info
        start_time = metadata.get("start_time", datetime.now())
        content += f"**Date**: {start_time.strftime('%B %d, %Y')}\n"
        content += f"**Time**: {start_time.strftime('%I:%M %p')}\n"
        content += f"**Mode**: {metadata.get('conversation_mode', 'Unknown').title()}\n"
        content += (
            f"**Participants**: {', '.join(metadata.get('participants', []))}\n\n"
        )

        content += "---\n\n"

        # Format conversation with agent styling
        current_speaker = None
        for entry in conversation_log:
            speaker = entry.get("speaker", "Unknown")
            message = entry.get("message", "")
            timestamp = entry.get("timestamp", datetime.now())

            # Add speaker header if it's a new speaker
            if speaker != current_speaker:
                if current_speaker is not None:
                    content += "\n"
                content += f"## 🤖 {speaker}\n"
                content += f"*{timestamp.strftime('%I:%M %p')}*\n\n"
                current_speaker = speaker

            # Format the message
            content += f"{message}\n\n"

        # Add footer with stats
        content += "---\n\n"
        content += f"**Conversation ended**: {datetime.now().strftime('%I:%M %p')}\n"
        content += f"**Total messages**: {len(conversation_log)}\n"

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)

        print(f"🎨 Formatted conversation exported: {filepath}")
        return str(filepath)

    def export_executive_summary(
        self, meeting_data: Dict[str, Any], filename: Optional[str] = None
    ) -> str:
        """
        Export a brief executive summary of the meeting.

        Args:
            meeting_data: Complete meeting data from SecretaryAgent
            filename: Optional custom filename

        Returns:
            Path to the exported file
        """
        filename = filename or self._generate_filename("executive_summary")
        filepath = self.export_directory / f"{filename}.md"

        metadata = meeting_data.get("metadata", {})
        decisions = meeting_data.get("decisions", [])
        action_items = meeting_data.get("action_items", [])
        stats = meeting_data.get("stats", {})

        content = f"# Executive Summary\n\n"
        content += f"**Meeting**: {metadata.get('topic', 'Group Discussion')}\n"
        content += f"**Date**: {datetime.now().strftime('%B %d, %Y')}\n"
        content += f"**Duration**: {stats.get('duration_minutes', 0)} minutes\n"
        content += f"**Participants**: {len(metadata.get('participants', []))}\n\n"

        # Key outcomes
        content += "## 🎯 Key Outcomes\n\n"

        if decisions:
            content += "### Decisions Made\n"
            for decision in decisions[:3]:  # Top 3 decisions
                decision_text = decision.get("decision", decision.get("content", ""))
                content += f"- {decision_text}\n"
            if len(decisions) > 3:
                content += f"- *...and {len(decisions) - 3} more decisions*\n"
            content += "\n"

        if action_items:
            content += "### Action Items\n"
            for item in action_items[:3]:  # Top 3 action items
                description = item.get("description", item.get("content", ""))
                assignee = item.get("assignee", "TBD")
                content += f"- {description} ({assignee})\n"
            if len(action_items) > 3:
                content += f"- *...and {len(action_items) - 3} more action items*\n"
            content += "\n"

        # Meeting effectiveness
        content += "## 📊 Meeting Metrics\n\n"
        content += f"- **Participation**: {len(stats.get('participants', {}))} active participants\n"
        content += (
            f"- **Engagement**: {stats.get('total_messages', 0)} total contributions\n"
        )
        content += f"- **Decisions**: {len(decisions)} decisions made\n"
        content += f"- **Action Items**: {len(action_items)} tasks created\n"

        # Determine meeting effectiveness
        effectiveness = (
            "High" if len(decisions) > 1 or len(action_items) > 2 else "Moderate"
        )
        content += f"- **Effectiveness**: {effectiveness}\n"

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)

        print(f"📋 Executive summary exported: {filepath}")
        return str(filepath)

    def export_complete_package(
        self, meeting_data: Dict[str, Any], format_type: str = "formal"
    ) -> List[str]:
        """
        Export a complete package of all available formats.

        Args:
            meeting_data: Complete meeting data from SecretaryAgent
            format_type: "formal" or "casual" for meeting minutes style

        Returns:
            List of exported file paths
        """
        base_filename = self._generate_filename("meeting_package")
        exported_files = []

        print(f"📦 Exporting complete meeting package...")

        # Meeting minutes
        minutes_file = self.export_meeting_minutes(
            meeting_data, format_type, f"{base_filename}_minutes"
        )
        exported_files.append(minutes_file)

        # Raw transcript
        conversation_log = meeting_data.get("conversation_log", [])
        metadata = meeting_data.get("metadata", {})

        if conversation_log:
            transcript_file = self.export_raw_transcript(
                conversation_log, metadata, f"{base_filename}_transcript"
            )
            exported_files.append(transcript_file)

            formatted_file = self.export_formatted_conversation(
                conversation_log, metadata, f"{base_filename}_formatted"
            )
            exported_files.append(formatted_file)

        # Action items
        action_items = meeting_data.get("action_items", [])
        if action_items:
            action_file = self.export_action_items(
                action_items, metadata, f"{base_filename}_actions"
            )
            exported_files.append(action_file)

        # Executive summary
        summary_file = self.export_executive_summary(
            meeting_data, f"{base_filename}_summary"
        )
        exported_files.append(summary_file)

        # Structured data
        data_file = self.export_structured_data(meeting_data, f"{base_filename}_data")
        exported_files.append(data_file)

        print(f"✅ Complete package exported: {len(exported_files)} files")
        return exported_files

    def _generate_filename(self, prefix: str) -> str:
        """Generate a timestamped filename."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"{prefix}_{timestamp}"

    def _prepare_for_json(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Prepare data for JSON serialization by converting datetime objects."""
        if isinstance(data, dict):
            return {k: self._prepare_for_json(v) for k, v in data.items()}
        elif isinstance(data, list):
            return [self._prepare_for_json(item) for item in data]
        elif isinstance(data, datetime):
            return data.isoformat()
        else:
            return data

    def list_exports(self) -> List[str]:
        """List all exported files in the export directory."""
        if not self.export_directory.exists():
            return []

        files = []
        for file_path in self.export_directory.iterdir():
            if file_path.is_file():
                files.append(str(file_path))

        return sorted(files)

    def cleanup_old_exports(self, days_old: int = 30):
        """Remove export files older than specified days."""
        if not self.export_directory.exists():
            return

        cutoff_time = datetime.now().timestamp() - (days_old * 24 * 60 * 60)
        removed_count = 0

        for file_path in self.export_directory.iterdir():
            if file_path.is_file() and file_path.stat().st_mtime < cutoff_time:
                file_path.unlink()
                removed_count += 1

        if removed_count > 0:
            print(f"🧹 Cleaned up {removed_count} old export files")

        return removed_count


def build_session_summary(
    session_state_or_id: Union[SessionState, str],
) -> Dict[str, Any]:
    """
    Build a session summary from session events.

    Args:
        session_state_or_id: Either a SessionState object or a session ID string

    Returns:
        Dict containing:
            - minutes_markdown: Structured meeting minutes
            - actions: List of action events
            - decisions: List of decision events
            - messages: List of message excerpts
            - meta: Session metadata
    """
    # Load session if ID provided
    if isinstance(session_state_or_id, str):
        session_store = get_default_session_store()
        session_state = session_store.load(session_state_or_id)
    else:
        session_state = session_state_or_id

    # Extract events by type (chronologically)
    actions = []
    decisions = []
    messages = []

    # Ensure chronological order regardless of append order in store
    for event in sorted(session_state.events, key=lambda e: e.ts):
        if event.type == "action":
            actions.append(
                {"ts": event.ts.isoformat(), "actor": event.actor, **event.payload}
            )
        elif event.type == "decision":
            decisions.append(
                {"ts": event.ts.isoformat(), "actor": event.actor, **event.payload}
            )
        elif event.type == "message":
            content = event.payload.get("content", "")
            # Trim long content to 2000 chars max
            if len(content) > 2000:
                content = content[:2000] + "..."
            messages.append(
                {
                    "ts": event.ts.isoformat(),
                    "actor": event.actor,
                    "role": event.payload.get("message_type", "unknown"),
                    "content": content,
                }
            )

    # Build minutes markdown
    minutes_markdown = _build_minutes_markdown(
        session_state, messages, decisions, actions
    )

    return {
        "minutes_markdown": minutes_markdown,
        "actions": actions,
        "decisions": decisions,
        "messages": messages,
        "meta": {
            "session_id": session_state.meta.id,
            "title": session_state.meta.title,
            "created_at": session_state.meta.created_at.isoformat(),
            "last_updated": session_state.meta.last_updated.isoformat(),
            "total_events": len(session_state.events),
        },
    }


def _build_minutes_markdown(
    session_state: SessionState,
    messages: List[Dict],
    decisions: List[Dict],
    actions: List[Dict],
) -> str:
    """Build formatted minutes markdown from session data."""
    content = f"# Session Minutes: {session_state.meta.title or 'Untitled Session'}\n\n"
    content += f"**Session ID**: {session_state.meta.id}\n"
    content += f"**Created**: {session_state.meta.created_at.strftime('%B %d, %Y at %I:%M %p')}\n"
    content += f"**Last Updated**: {session_state.meta.last_updated.strftime('%B %d, %Y at %I:%M %p')}\n"
    content += f"**Total Events**: {len(session_state.events)}\n\n"

    content += "## Transcript\n\n"

    if messages:
        # Sort chronologically
        sorted_messages = sorted(messages, key=lambda x: x["ts"])
        for msg in sorted_messages:
            timestamp = datetime.fromisoformat(msg["ts"]).strftime("%I:%M %p")
            content += f"**{msg['actor']}** ({msg['role']}) *{timestamp}*: {msg['content']}\n\n"
    else:
        content += "*No messages recorded.*\n\n"

    content += "## Decisions\n\n"
    if decisions:
        for decision in decisions:
            timestamp = datetime.fromisoformat(decision["ts"]).strftime("%I:%M %p")
            content += f"- **{decision['actor']}** *{timestamp}*: "
            if "decision_type" in decision:
                content += f"{decision['decision_type']}: "
            if "details" in decision:
                details = decision["details"]
                if isinstance(details, dict):
                    content += f"{details.get('content', str(details))}"
                else:
                    content += str(details)
            content += "\n"
    else:
        content += "*No decisions recorded.*\n"

    content += "\n## Action Items\n\n"
    if actions:
        for action in actions:
            timestamp = datetime.fromisoformat(action["ts"]).strftime("%I:%M %p")
            content += f"- **{action['actor']}** *{timestamp}*: "
            if "action_type" in action:
                content += f"{action['action_type']}: "
            if "details" in action:
                details = action["details"]
                if isinstance(details, dict):
                    content += f"{details.get('content', str(details))}"
                else:
                    content += str(details)
            content += "\n"
    else:
        content += "*No action items recorded.*\n"

    return content


def export_session_to_markdown(
    session_id: str, dest_dir: Optional[Union[Path, str]] = None
) -> Path:
    """
    Export session to markdown file.

    Args:
        session_id: Session ID to export
        dest_dir: Optional destination directory (defaults to exports/sessions/{session_id})

    Returns:
        Path to the exported markdown file
    """
    # Get destination directory
    if dest_dir is None:
        dest_dir = Path(config.DEFAULT_EXPORT_DIRECTORY) / "sessions" / session_id
    else:
        dest_dir = Path(dest_dir)

    dest_dir.mkdir(parents=True, exist_ok=True)

    # Build summary
    summary = build_session_summary(session_id)

    # Generate filename with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"minutes_{session_id}_{timestamp}.md"
    filepath = dest_dir / filename

    # Write markdown content
    content = summary["minutes_markdown"]

    # Use atomic write
    temp_file = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", dir=dest_dir, delete=False, suffix=".tmp"
        ) as f:
            temp_file = Path(f.name)
            f.write(content)

        # Atomic replace
        temp_file.replace(filepath)
        logger.info(f"Exported session {session_id} to markdown: {filepath}")

    except Exception as e:
        # Clean up temp file on error
        if temp_file and temp_file.exists():
            temp_file.unlink(missing_ok=True)
        raise e

    return filepath


def export_session_to_json(
    session_id: str, dest_dir: Optional[Union[Path, str]] = None
) -> Path:
    """
    Export session summary to JSON file.

    Args:
        session_id: Session ID to export
        dest_dir: Optional destination directory (defaults to exports/sessions/{session_id})

    Returns:
        Path to the exported JSON file
    """
    # Get destination directory
    if dest_dir is None:
        dest_dir = Path(config.DEFAULT_EXPORT_DIRECTORY) / "sessions" / session_id
    else:
        dest_dir = Path(dest_dir)

    dest_dir.mkdir(parents=True, exist_ok=True)

    # Build summary
    summary = build_session_summary(session_id)

    # Generate filename with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"summary_{session_id}_{timestamp}.json"
    filepath = dest_dir / filename

    # Use atomic write
    temp_file = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", dir=dest_dir, delete=False, suffix=".tmp"
        ) as f:
            temp_file = Path(f.name)
            json.dump(summary, f, indent=2, ensure_ascii=False, default=str)

        # Atomic replace
        temp_file.replace(filepath)
        logger.info(f"Exported session {session_id} to JSON: {filepath}")

    except Exception as e:
        # Clean up temp file on error
        if temp_file and temp_file.exists():
            temp_file.unlink(missing_ok=True)
        raise e

    return filepath


def restore_session_from_json(
    json_path: Union[Path, str], target_session_id: Optional[str] = None
) -> str:
    """
    Restore session from JSON summary file.

    Args:
        json_path: Path to the JSON summary file
        target_session_id: Optional target session ID. If provided and exists,
                          events are appended to existing session. Otherwise,
                          a new session is created.

    Returns:
        The session ID that was restored to
    """
    json_path = Path(json_path)

    if not json_path.exists():
        raise ValueError(f"JSON file not found: {json_path}")

    try:
        with json_path.open("r") as f:
            summary = json.load(f)
    except json.JSONDecodeError as e:
        raise ValueError(f"Malformed JSON file {json_path}: {e}")

    # Validate required structure
    required_keys = ["minutes_markdown", "actions", "decisions", "messages", "meta"]
    missing_keys = [key for key in required_keys if key not in summary]
    if missing_keys:
        raise ValueError(f"Missing required keys in JSON: {missing_keys}")

    required_meta_keys = ["session_id", "title", "created_at", "last_updated"]
    missing_meta_keys = [
        key for key in required_meta_keys if key not in summary["meta"]
    ]
    if missing_meta_keys:
        raise ValueError(f"Missing required meta keys: {missing_meta_keys}")

    # Get session store
    session_store = get_default_session_store()

    # Determine target session
    if target_session_id:
        try:
            session_state = session_store.load(target_session_id)
            session_id = target_session_id
            logger.info(f"Restoring to existing session {session_id}")
        except ValueError:
            # Session doesn't exist, create new one
            target_session_id = None

    if not target_session_id:
        # Create new session
        title = summary["meta"]["title"]
        if not title:
            title = "Restored Session"
        session_state = session_store.create(title=f"{title} (restored)")
        session_id = session_state.meta.id
        logger.info(f"Created new session {session_id} for restoration")

    # Add system event for minutes
    if summary["minutes_markdown"]:
        from .session_tracking import track_system_event

        track_system_event(
            "minutes_imported",
            {
                "content": summary["minutes_markdown"],
                "source_file": str(json_path),
                "original_session_id": summary["meta"]["session_id"],
            },
        )

    # Add decision events
    for decision in summary["decisions"]:
        from .session_tracking import track_decision

        track_decision(
            decision["actor"],
            decision.get("decision_type", "imported_decision"),
            {
                **{k: v for k, v in decision.items() if k not in ["ts", "actor"]},
                "original_ts": decision["ts"],
                "imported_from": summary["meta"]["session_id"],
            },
        )

    # Add action events
    for action in summary["actions"]:
        from .session_tracking import track_action

        track_action(
            action["actor"],
            action.get("action_type", "imported_action"),
            {
                **{k: v for k, v in action.items() if k not in ["ts", "actor"]},
                "original_ts": action["ts"],
                "imported_from": summary["meta"]["session_id"],
            },
        )

    # Add system event indicating transcript availability
    if summary["messages"]:
        track_system_event(
            "transcript_available_in_export",
            {"message_count": len(summary["messages"]), "source_file": str(json_path)},
        )

    logger.info(f"Successfully restored session from {json_path} to {session_id}")
    return session_id
