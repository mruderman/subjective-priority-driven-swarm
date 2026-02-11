# swarms-web/app.py

import json
import logging
import mimetypes
import os
import random
import string
import sys
import time
import uuid
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path

from flask import (
    Flask,
    abort,
    jsonify,
    make_response,
    redirect,
    render_template,
    request,
    send_file,
    send_from_directory,
    session,
    url_for,
)
from flask_socketio import SocketIO, emit, join_room, leave_room
from werkzeug.exceptions import BadRequest
from werkzeug.utils import secure_filename

# Add parent directory to path to import existing SPDS modules
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from letta_client import Letta
from letta_flask import LettaFlask, LettaFlaskConfig
from playwright_fixtures import get_mock_agents
from spds import config
from spds.export_manager import (
    ExportManager,
    export_session_to_json,
    export_session_to_markdown,
)
from spds.message import get_new_messages_since_index
from spds.secretary_agent import SecretaryAgent
from spds.session_context import set_current_session_id
from spds.session_store import get_default_session_store
from spds.session_tracking import track_system_event, track_message, track_action
from spds.swarm_manager import SwarmManager

logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)
app.config["SECRET_KEY"] = os.urandom(24)

# Initialize SocketIO for real-time communication
try:
    # Prefer threading to avoid eventlet/gevent issues in CI
    socketio = SocketIO(app, cors_allowed_origins="*", logger=True, engineio_logger=True, async_mode="threading")
except Exception:
    # Fallback to default mode if threading not available
    socketio = SocketIO(app, cors_allowed_origins="*", logger=True, engineio_logger=True)

# Initialize letta-flask
letta_flask = LettaFlask(
    config=LettaFlaskConfig(
        base_url=config.LETTA_BASE_URL,
        api_key=config.LETTA_API_KEY if config.LETTA_API_KEY else None,
    )
)
letta_flask.init_app(app)

# Validate Letta configuration at startup. This does not perform a network
# connectivity check by default (to avoid blocking imports), but it will raise
# clear configuration errors (missing API key when required, etc.).
try:
    config.validate_letta_config(check_connectivity=False)
except Exception as e:
    # Raise here so app startup fails fast with a clear message
    raise RuntimeError(f"Letta configuration invalid: {e}")

# Validate agent profiles configuration at startup
try:
    validated_profiles = config.get_agent_profiles_validated()
    print(
        f"Web UI: Validated {len(validated_profiles.agents)} agent profiles successfully."
    )
except Exception as e:
    # Log error but don't prevent startup since web UI primarily uses agent IDs
    print(f"Warning: Agent profiles validation failed: {e}")
    print("Web UI will continue but may have issues if using default agent profiles.")

# Global storage for active swarm sessions
active_sessions = {}

PLAYWRIGHT_EXPORT_FIXTURES = {
    "board_minutes_formal.md",
    "meeting_notes_casual.md",
    "conversation_transcript.txt",
    "action_items.md",
    "executive_summary.md",
    "structured_data.json",
}


class WebSwarmManager:
    """Web-adapted version of SwarmManager with WebSocket support."""

    def __init__(self, session_id, socketio_instance, **kwargs):
        self.session_id = session_id
        self.socketio = socketio_instance

        # Initialize Letta client
        letta_password = config.get_letta_password()
        if config.LETTA_ENVIRONMENT == "SELF_HOSTED" and letta_password:
            self.client = Letta(api_key=letta_password, base_url=config.LETTA_BASE_URL)
        elif config.LETTA_API_KEY:
            self.client = Letta(
                api_key=config.LETTA_API_KEY, base_url=config.LETTA_BASE_URL
            )
        else:
            self.client = Letta(base_url=config.LETTA_BASE_URL)

        # Initialize the base SwarmManager
        self.swarm = SwarmManager(client=self.client, **kwargs)
        self.export_manager = ExportManager()
        self.current_topic = None

        # Set up the callback to link backend event to frontend notification
        self.swarm.on_role_change_callback = self._handle_role_change

    def _handle_role_change(self):
        """Callback function passed to SwarmManager."""
        logger.info("Role change detected from swarm, notifying GUI.")
        notify_secretary_change(self.session_id, self.swarm)

    def emit_message(self, event, data):
        """Emit WebSocket message to the session room."""
        self.socketio.emit(event, data, room=self.session_id)

    def start_web_chat(self, topic):
        """Start chat with WebSocket notifications."""
        self.current_topic = topic
        self.emit_message(
            "chat_started",
            {
                "topic": topic,
                "mode": self.swarm.conversation_mode,
                "agents": [
                    {"name": agent.name, "id": agent.agent.id}
                    for agent in self.swarm.agents
                ],
                "secretary_enabled": self.swarm.enable_secretary,
            },
        )

        # Start meeting if secretary is enabled
        if self.swarm.secretary:
            participant_names = [agent.name for agent in self.swarm.agents]
            self.swarm.secretary.start_meeting(
                topic=topic,
                participants=participant_names,
                meeting_type=self.swarm.meeting_type,
            )
            self.swarm.secretary.meeting_metadata[
                "conversation_mode"
            ] = self.swarm.conversation_mode

            # Notify about secretary initialization
            logger.info(
                f"Emitting secretary_status event: active, "
                f"agent={self.swarm.secretary.agent.name if self.swarm.secretary.agent else 'Secretary'}, "
                f"mode={self.swarm.secretary.mode}"
            )
            self.emit_message(
                "secretary_status",
                {
                    "status": "active",
                    "mode": self.swarm.secretary.mode,
                    "agent_name": (
                        self.swarm.secretary.agent.name
                        if self.swarm.secretary.agent
                        else "Secretary"
                    ),
                    "message": f"📝 {self.swarm.secretary.agent.name if self.swarm.secretary.agent else 'Secretary'} is now taking notes in {self.swarm.secretary.mode} mode",
                },
            )
        else:
            # Secretary not enabled - ensure UI shows this clearly
            logger.info("Secretary not enabled, emitting disabled status")
            self.emit_message(
                "secretary_status",
                {
                    "status": "disabled",
                    "message": "📝 Secretary is not enabled for this session"
                }
            )

    def process_user_message(self, message):
        """Process user message and trigger agent responses."""
        # Add to conversation history
        self.swarm._append_history("You", message)

        # Let secretary observe
        if self.swarm.secretary:
            self.swarm.secretary.observe_message("You", message)
            self.emit_message(
                "secretary_activity",
                {"activity": "observing", "message": f"📝 Recording your message..."},
            )

        # Emit user message
        self.emit_message(
            "user_message",
            {
                "speaker": "You",
                "message": message,
                "timestamp": datetime.now().isoformat(),
            },
        )

        # Check for secretary commands
        if message.startswith("/"):
            self._handle_secretary_command(message)
            return

        # Process agent turn (follow CLI pattern)
        self._web_agent_turn(self.current_topic)

    def _handle_secretary_command(self, command):
        """Handle secretary commands with WebSocket responses."""
        command_parts = command[1:].split(" ", 1)
        cmd = command_parts[0].lower()
        args = command_parts[1] if len(command_parts) > 1 else ""

        if not self.swarm.secretary:
            self.emit_message(
                "system_message",
                {"message": "Secretary is not enabled for this session."},
            )
            return

        if cmd == "minutes":
            self.emit_message(
                "secretary_activity",
                {
                    "activity": "generating",
                    "message": "📝 Generating meeting minutes...",
                },
            )
            minutes = self.swarm.secretary.generate_minutes()
            self.emit_message("secretary_minutes", {"minutes": minutes})
            self.emit_message(
                "secretary_activity",
                {"activity": "completed", "message": "✅ Meeting minutes generated!"},
            )

        elif cmd == "export":
            self._handle_export_command(args)

        elif cmd in ["formal", "casual"]:
            self.swarm.secretary.set_mode(cmd)
            self.emit_message(
                "system_message", {"message": f"Secretary mode changed to {cmd}"}
            )

        elif cmd == "action-item":
            if args:
                self.swarm.secretary.add_action_item(args)
                self.emit_message(
                    "system_message", {"message": f"Action item added: {args}"}
                )
            else:
                self.emit_message(
                    "system_message", {"message": "Usage: /action-item <description>"}
                )

        elif cmd == "stats":
            stats = self.swarm.secretary.get_conversation_stats()
            self.emit_message("secretary_stats", {"stats": stats})

    def _handle_export_command(self, args):
        """Handle export commands."""
        if not self.swarm.secretary:
            self.emit_message(
                "system_message",
                {"message": "Secretary is not enabled for this session. Enable secretary to export meeting data."},
            )
            return

        meeting_data = {
            "metadata": self.swarm.secretary.meeting_metadata,
            "conversation_log": self.swarm.secretary.conversation_log,
            "action_items": self.swarm.secretary.action_items,
            "decisions": self.swarm.secretary.decisions,
            "stats": self.swarm.secretary.get_conversation_stats(),
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
                    meeting_data["conversation_log"],
                    meeting_data["metadata"]
                )
            elif format_type == "actions":
                file_path = self.export_manager.export_action_items(
                    meeting_data["action_items"],
                    meeting_data["metadata"]
                )
            elif format_type == "summary":
                file_path = self.export_manager.export_executive_summary(
                    meeting_data
                )
            elif format_type == "all":
                files = self.export_manager.export_complete_package(
                    meeting_data, self.swarm.secretary.mode
                )
                self.emit_message(
                    "export_complete", {"files": files, "count": len(files)}
                )
                return
            else:
                self.emit_message(
                    "system_message",
                    {"message": f"Unknown export format: {format_type}"},
                )
                return

            self.emit_message(
                "export_complete", {"file": file_path, "format": format_type}
            )

        except Exception as e:
            self.emit_message("system_message", {"message": f"Export failed: {str(e)}"})

    def _web_agent_turn(self, topic: str):
        """Process agent turn with WebSocket notifications (follows CLI pattern)."""
        # Assess motivations
        self.emit_message("assessing_agents", {})

        try:
            for agent in self.swarm.agents:
                # Get messages since this agent's last turn
                recent_messages = self.swarm.get_new_messages_since_last_turn(agent)

                # Use the same backward-compatible approach as SwarmManager
                try:
                    import inspect
                    sig = inspect.signature(agent.assess_motivation_and_priority)
                    pos_params = [
                        p for p in sig.parameters.values()
                        if p.kind in (inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD)
                    ]
                    if len(pos_params) >= 2:
                        agent.assess_motivation_and_priority(recent_messages, topic)
                    else:
                        agent.assess_motivation_and_priority(topic)
                except Exception:
                    # Fallback: try two-arg call first, then single-arg
                    try:
                        agent.assess_motivation_and_priority(recent_messages, topic)
                    except TypeError:
                        agent.assess_motivation_and_priority(topic)
        except Exception as e:
            logger.error(f"Error during agent assessment: {e}", exc_info=True)
            self.emit_message("system_message", {
                "message": f"Error assessing agents: {str(e)}"
            })
            return

        motivated_agents = sorted(
            [agent for agent in self.swarm.agents if agent.priority_score > 0],
            key=lambda x: x.priority_score,
            reverse=True,
        )

        if not motivated_agents:
            self.emit_message(
                "system_message",
                {"message": "No agent is motivated to speak at this time."},
            )
            return

        # Emit motivation scores
        agent_scores = [
            {
                "name": agent.name,
                "motivation_score": agent.motivation_score,
                "priority_score": round(agent.priority_score, 2),
            }
            for agent in self.swarm.agents
        ]
        self.emit_message("agent_scores", {"scores": agent_scores})

        # Process based on conversation mode
        if self.swarm.conversation_mode == "hybrid":
            self._web_hybrid_turn(motivated_agents)
        elif self.swarm.conversation_mode == "all_speak":
            self._web_all_speak_turn(motivated_agents)
        elif self.swarm.conversation_mode == "sequential":
            self._web_sequential_turn(motivated_agents)
        else:  # pure_priority
            self._web_pure_priority_turn(motivated_agents)

    def _web_hybrid_turn(self, motivated_agents):
        """Hybrid mode with WebSocket updates."""
        self.emit_message("phase_change", {"phase": "initial_responses"})

        original_history = self.swarm.conversation_history
        initial_responses = []

        # Phase 1: Independent responses
        for i, agent in enumerate(motivated_agents):
            self.emit_message(
                "agent_thinking",
                {
                    "agent": agent.name,
                    "phase": "initial",
                    "progress": f"{i+1}/{len(motivated_agents)}",
                },
            )

            try:
                print(
                    f"[DEBUG] Agent {agent.name} speaking with history length: {len(original_history)}"
                )
                response = agent.speak(conversation_history=original_history)
                print(f"[DEBUG] Agent {agent.name} response type: {type(response)}")

                message_text = self.swarm._extract_agent_response(response)
                print(
                    f"[DEBUG] Agent {agent.name} extracted message: {message_text[:100]}..."
                )

                initial_responses.append((agent, message_text))

                self.emit_message(
                    "agent_message",
                    {
                        "speaker": agent.name,
                        "message": message_text,
                        "timestamp": datetime.now().isoformat(),
                        "phase": "initial",
                    },
                )

                # Track agent message to persistent store
                track_message(agent.name, message_text, "assistant")

                # Notify secretary
                if self.swarm.secretary:
                    self.swarm.secretary.observe_message(agent.name, message_text)
                    self.emit_message(
                        "secretary_activity",
                        {
                            "activity": "recording",
                            "message": f"📝 Recording {agent.name}'s initial thoughts...",
                        },
                    )

            except Exception as e:
                print(f"[ERROR] Agent {agent.name} failed in initial phase: {e}")
                print(f"[ERROR] Exception type: {type(e)}")
                import traceback

                traceback.print_exc()

                fallback = (
                    "I have some thoughts but I'm having trouble expressing them."
                )
                initial_responses.append((agent, fallback))

                self.emit_message(
                    "agent_message",
                    {
                        "speaker": agent.name,
                        "message": fallback,
                        "timestamp": datetime.now().isoformat(),
                        "phase": "initial",
                        "error": True,
                    },
                )

        # Phase 2: Response round
        self.emit_message("phase_change", {"phase": "response_round"})

        history_with_initials = original_history
        for agent, response in initial_responses:
            history_with_initials += f"{agent.name}: {response}\n"

        response_prompt = "\n\nNow that you've heard everyone's initial thoughts, please respond to what others have said..."

        for i, agent in enumerate(motivated_agents):
            self.emit_message(
                "agent_thinking",
                {
                    "agent": agent.name,
                    "phase": "response",
                    "progress": f"{i+1}/{len(motivated_agents)}",
                },
            )

            try:
                response = agent.speak(
                    conversation_history=history_with_initials + response_prompt
                )
                message_text = self.swarm._extract_agent_response(response)

                self.emit_message(
                    "agent_message",
                    {
                        "speaker": agent.name,
                        "message": message_text,
                        "timestamp": datetime.now().isoformat(),
                        "phase": "response",
                    },
                )

                # Track agent response to persistent store
                track_message(agent.name, message_text, "assistant")

                # Add to conversation history
                self.swarm._append_history(agent.name, message_text)

                # Update all agent memories with this response
                self.swarm._update_agent_memories(message_text, agent.name)

                # Notify secretary
                if self.swarm.secretary:
                    self.swarm.secretary.observe_message(agent.name, message_text)
                    self.emit_message(
                        "secretary_activity",
                        {
                            "activity": "recording",
                            "message": f"📝 Recording {agent.name}'s response...",
                        },
                    )

            except Exception as e:
                error_message = f"Error during response round for {agent.name}: {e}"
                self.emit_message("error", {"message": error_message})
                self.swarm._append_history(agent.name, f"Error: {e}")
                if hasattr(agent, "last_message_index"):
                    agent.last_message_index = len(self.swarm._history) - 1

    def _web_all_speak_turn(self, motivated_agents):
        """All-speak mode with WebSocket updates."""
        self.emit_message("phase_change", {"phase": "all_speak"})

        for i, agent in enumerate(motivated_agents):
            self.emit_message(
                "agent_thinking",
                {"agent": agent.name, "progress": f"{i+1}/{len(motivated_agents)}"},
            )

            try:
                response = agent.speak(conversation_history=original_history)
                message_text = self.swarm._extract_agent_response(response)

                self.emit_message(
                    "agent_message",
                    {
                        "speaker": agent.name,
                        "message": message_text,
                        "timestamp": datetime.now().isoformat(),
                    },
                )

                # Track agent message to persistent store
                track_message(agent.name, message_text, "assistant")

                self.swarm._append_history(agent.name, message_text)

                # Update all agent memories with this response
                self.swarm._update_agent_memories(message_text, agent.name)

                if self.swarm.secretary:
                    self.swarm.secretary.observe_message(agent.name, message_text)

            except Exception as e:
                fallback = "I have some thoughts but I'm having trouble expressing them clearly."

                self.emit_message(
                    "agent_message",
                    {
                        "speaker": agent.name,
                        "message": fallback,
                        "timestamp": datetime.now().isoformat(),
                        "error": True,
                    },
                )

                self.swarm._append_history(agent.name, fallback)

    def _web_sequential_turn(self, motivated_agents):
        """Sequential mode with WebSocket updates."""
        # Implement fairness rotation
        if len(motivated_agents) > 1 and hasattr(self.swarm, "last_speaker"):
            if self.swarm.last_speaker == motivated_agents[0].name:
                speaker = motivated_agents[1]
            else:
                speaker = motivated_agents[0]
        else:
            speaker = motivated_agents[0]

        self.swarm.last_speaker = speaker.name

        self.emit_message("agent_thinking", {"agent": speaker.name})

        try:
            filtered_history = self.swarm._get_filtered_conversation_history(speaker)
            response = speaker.speak(
                conversation_history=filtered_history
            )
            message_text = self.swarm._extract_agent_response(response)

            self.emit_message(
                "agent_message",
                {
                    "speaker": speaker.name,
                    "message": message_text,
                    "timestamp": datetime.now().isoformat(),
                },
            )

            # Track agent message to persistent store
            track_message(speaker.name, message_text, "assistant")

            self.swarm._append_history(speaker.name, message_text)

            # Update all agent memories with this response
            self.swarm._update_agent_memories(message_text, speaker.name)

            if self.swarm.secretary:
                self.swarm.secretary.observe_message(speaker.name, message_text)

        except Exception as e:
            fallback = "I have some thoughts but I'm having trouble phrasing them."

            self.emit_message(
                "agent_message",
                {
                    "speaker": speaker.name,
                    "message": fallback,
                    "timestamp": datetime.now().isoformat(),
                    "error": True,
                },
            )

            self.swarm._append_history(speaker.name, fallback)

    def _web_pure_priority_turn(self, motivated_agents):
        """Pure priority mode with WebSocket updates."""
        speaker = motivated_agents[0]

        self.emit_message("agent_thinking", {"agent": speaker.name})

        try:
            filtered_history = self.swarm._get_filtered_conversation_history(speaker)
            response = speaker.speak(
                conversation_history=filtered_history
            )
            message_text = self.swarm._extract_agent_response(response)

            self.emit_message(
                "agent_message",
                {
                    "speaker": speaker.name,
                    "message": message_text,
                    "timestamp": datetime.now().isoformat(),
                },
            )

            # Track agent message to persistent store
            track_message(speaker.name, message_text, "assistant")

            self.swarm._append_history(speaker.name, message_text)

            # Update all agent memories with this response
            self.swarm._update_agent_memories(message_text, speaker.name)

            if self.swarm.secretary:
                self.swarm.secretary.observe_message(speaker.name, message_text)

        except Exception as e:
            fallback = "I have thoughts on this topic but I'm having difficulty expressing them."

            self.emit_message(
                "agent_message",
                {
                    "speaker": speaker.name,
                    "message": fallback,
                    "timestamp": datetime.now().isoformat(),
                    "error": True,
                },
            )

            self.swarm._append_history(speaker.name, fallback)


def _restore_web_swarm_from_session(session_id, socketio_instance):
    """Restore a WebSwarmManager from persistent session storage.

    Args:
        session_id: The session ID to restore
        socketio_instance: The SocketIO instance for WebSocket communication

    Returns:
        WebSwarmManager: Restored swarm manager instance

    Raises:
        ValueError: If session not found in persistent store
    """
    # Load session state from persistent store
    store = get_default_session_store()
    session_state = store.load(session_id)

    # Extract configuration from extras
    if not session_state.extras or "config" not in session_state.extras:
        raise ValueError(f"Session {session_id} has no configuration data")

    session_config = session_state.extras["config"]

    # Create WebSwarmManager with original configuration
    web_swarm = WebSwarmManager(
        session_id=session_id,
        socketio_instance=socketio_instance,
        agent_ids=session_config.get("agent_ids", []),
        conversation_mode=session_config.get("conversation_mode", "hybrid"),
        enable_secretary=session_config.get("enable_secretary", False),
        secretary_mode=session_config.get("secretary_mode", "adaptive"),
        meeting_type=session_config.get("meeting_type", "discussion"),
    )

    # Rebuild conversation history and state from events
    for event in session_state.events:
        if event.type == "message":
            speaker = event.actor
            content = event.payload.get("content", "")
            # Append to conversation history
            web_swarm.swarm._append_history(speaker, content)

        elif event.type == "system":
            event_type = event.payload.get("event_type")

            if event_type == "chat_started":
                # Restore current topic
                web_swarm.current_topic = event.payload.get("topic")

            elif event_type == "phase_change":
                # Phase changes are transient, no need to restore
                pass

        elif event.type == "action":
            action_type = event.payload.get("action_type")

            if action_type == "role_assignment":
                # Restore secretary role assignment
                agent_id = event.payload.get("agent_id")
                role = event.payload.get("role")
                if role == "secretary" and agent_id:
                    web_swarm.swarm.assign_role(agent_id, "secretary")

            elif action_type == "observe":
                # Secretary observations are already in conversation history
                pass

    # Set session context
    set_current_session_id(session_id)

    logger.info(f"Restored session {session_id} with {len(session_state.events)} events")

    return web_swarm


def notify_secretary_change(session_id, swarm_manager):
    """Fetches secretary status and emits a WebSocket update."""
    secretary_agent = swarm_manager.get_secretary()
    if secretary_agent:
        status_data = {
            "status": "active",
            "agent_name": secretary_agent.name,
            "mode": swarm_manager.secretary.mode if swarm_manager.secretary else "adaptive",
            "message": f"📝 {secretary_agent.name} is now the secretary"
        }
        config.logger.info(f"Emitting secretary_status update for session {session_id}: {secretary_agent.name}")
        socketio.emit("secretary_status", status_data, room=session_id)
    else:
        socketio.emit(
            "secretary_status",
            {
                "status": "disabled",
                "message": "📝 Secretary role is unassigned."
            },
            room=session_id
        )


# Routes
@app.route("/")
def index():
    """Landing page."""
    return render_template("index.html")


@app.route("/setup")
def setup():
    """Agent selection and configuration page."""
    return render_template("setup.html")


@app.route("/chat")
def chat():
    """Main chat interface with session restoration.

    This route allows loading the chat page even without a server-side Flask session,
    enabling session restoration after server restarts. The browser's sessionStorage
    maintains the session_id, and the WebSocket handlers will restore the session
    from persistent storage when the client connects.
    """
    from flask import request

    # In test environments we allow injecting a session_id via query param
    # to simplify E2E testing (Playwright). When PLAYWRIGHT_TEST=1 is set,
    # a test can navigate to /chat?session_id=<id> and the server will accept
    # it and proceed without requiring a prior POST /api/start_session that
    # performed Letta lookups.
    if os.getenv("PLAYWRIGHT_TEST") == "1":
        injected = request.args.get("session_id")
        if injected:
            session["session_id"] = injected

    # Check if we have a session_id in the Flask session (normal case)
    # If not, allow the page to load anyway - the JavaScript will check
    # sessionStorage and attempt to restore via WebSocket join_session event
    if "session_id" in session:
        session_id = session["session_id"]

        # Pre-restore session if it exists in persistent store but not in active memory
        # This provides a smoother experience when reloading the page
        if session_id not in active_sessions:
            try:
                logger.info(f"Session {session_id} not in active sessions, attempting pre-restoration...")
                active_sessions[session_id] = _restore_web_swarm_from_session(session_id, socketio)
                logger.info(f"Successfully pre-restored session {session_id} from persistent store")
            except ValueError as e:
                # Session not found in persistent store - redirect to setup
                logger.warning(f"Session {session_id} not found in persistent store: {e}")
                return redirect(url_for("setup"))
            except Exception as e:
                # Other restoration errors - redirect to setup
                logger.error(f"Error pre-restoring session {session_id}: {e}", exc_info=True)
                return redirect(url_for("setup"))

    # Allow page to load even without Flask session - client-side will handle restoration
    return render_template("chat.html")


@app.route("/api/agents")
def get_agents():
    """
    Return a JSON list of available agents.
    
    When the environment variable PLAYWRIGHT_TEST == "1", returns a mocked agent list from get_mock_agents().
    Otherwise initializes a Letta client (using self-hosted password, API key, or base URL as available), fetches agents, and returns JSON with each agent's id, name, model (or "Unknown"), and created_at date (YYYY-MM-DD or "Unknown").
    
    Returns:
    	Flask Response: JSON payload {"agents": [...]} on success, or {"error": "<message>"} with HTTP 500 on failure.
    """
    if os.getenv("PLAYWRIGHT_TEST") == "1":
        return jsonify({"agents": get_mock_agents()})

    try:
        # Initialize Letta client
        letta_password = config.get_letta_password()
        if config.LETTA_ENVIRONMENT == "SELF_HOSTED" and letta_password:
            client = Letta(api_key=letta_password, base_url=config.LETTA_BASE_URL)
        elif config.LETTA_API_KEY:
            client = Letta(api_key=config.LETTA_API_KEY, base_url=config.LETTA_BASE_URL)
        else:
            client = Letta(base_url=config.LETTA_BASE_URL)

        agents = list(client.agents.list())
        agent_list = []

        for agent in agents:
            agent_list.append(
                {
                    "id": agent.id,
                    "name": agent.name,
                    "model": getattr(agent, "model", "Unknown"),
                    "created_at": (
                        str(agent.created_at)[:10]
                        if hasattr(agent, "created_at")
                        else "Unknown"
                    ),
                }
            )

        return jsonify({"agents": agent_list})

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/start_session", methods=["POST"])
def start_session():
    """Start a new swarm session with persistent storage."""
    try:
        data = request.get_json()
        session_id = str(uuid.uuid4())
        session["session_id"] = session_id

        if data.get("playwright_test") or os.getenv("PLAYWRIGHT_TEST") == "1":
            conversation_mode = data.get("conversation_mode", "hybrid")

            class DummySwarm:
                def __init__(self, mode):
                    self.conversation_mode = mode
                    self.conversation_history = ""

            class DummyWebSwarm:
                def __init__(self, mode):
                    self.session_id = session_id
                    self.swarm = DummySwarm(mode)

                def start_web_chat(self, topic):
                    return None

                def process_user_message(self, message):
                    return None

            active_sessions[session_id] = DummyWebSwarm(conversation_mode)

            return jsonify({"session_id": session_id, "status": "mock"})

        # Extract configuration
        agent_ids = data.get("agent_ids", [])
        conversation_mode = data.get("conversation_mode", "hybrid")
        enable_secretary = data.get("enable_secretary", False)
        secretary_mode = data.get("secretary_mode", "adaptive")
        meeting_type = data.get("meeting_type", "discussion")

        # Create persistent session with configuration in extras
        store = get_default_session_store()
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        session_state = store.create(
            session_id=session_id,
            title=f"Swarm Session {timestamp}",
            tags=["web", conversation_mode]
        )

        # Store configuration in session extras
        session_state.extras = {
            "config": {
                "agent_ids": agent_ids,
                "conversation_mode": conversation_mode,
                "enable_secretary": enable_secretary,
                "secretary_mode": secretary_mode,
                "meeting_type": meeting_type
            }
        }
        store._save_session_state(session_state)

        # Set session context for event tracking
        set_current_session_id(session_id)

        # Track session creation event
        track_system_event("session_created", {
            "agent_ids": agent_ids,
            "conversation_mode": conversation_mode,
            "enable_secretary": enable_secretary,
            "secretary_mode": secretary_mode,
            "meeting_type": meeting_type
        })

        # Create WebSwarmManager
        web_swarm = WebSwarmManager(
            session_id=session_id,
            socketio_instance=socketio,
            agent_ids=agent_ids,
            conversation_mode=conversation_mode,
            enable_secretary=enable_secretary,
            secretary_mode=secretary_mode,
            meeting_type=meeting_type,
        )

        active_sessions[session_id] = web_swarm

        logger.info(f"Created persistent session {session_id} with {len(agent_ids)} agents")

        return jsonify({"session_id": session_id, "status": "success"})

    except Exception as e:
        logger.error(f"Error creating session: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@app.route("/exports/<path:filename>")
def download_export(filename):
    """Download exported files."""
    export_dir = Path(__file__).resolve().parent.parent / "exports"
    export_path = export_dir / filename

    if export_path.exists():
        return send_from_directory(export_dir, filename, as_attachment=True)

    if os.getenv("PLAYWRIGHT_TEST") == "1" and filename in PLAYWRIGHT_EXPORT_FIXTURES:
        guessed_type, _ = mimetypes.guess_type(filename)
        response = make_response(f"Mock content for {filename}")
        response.headers["Content-Type"] = guessed_type or "application/octet-stream"
        response.headers["Content-Disposition"] = f'attachment; filename="{filename}"'
        return response

    abort(404)


# Session management endpoints
@app.route("/sessions")
def sessions_page():
    """Sessions management page."""
    return render_template("sessions.html")


@app.route("/api/sessions", methods=["GET"])
def get_sessions():
    """Get list of sessions with optional limit."""
    try:
        store = get_default_session_store()
        sessions = store.list_sessions()

        # Apply limit if provided
        limit = request.args.get("limit", type=int)
        if limit and limit > 0:
            sessions = sessions[:limit]

        # Convert to JSON-serializable format
        session_list = []
        for session_meta in sessions:
            session_list.append(
                {
                    "id": session_meta.id,
                    "created_at": session_meta.created_at.isoformat(),
                    "last_updated": session_meta.last_updated.isoformat(),
                    "title": session_meta.title,
                    "tags": session_meta.tags,
                }
            )

        logger.debug(f"Listed {len(session_list)} sessions")
        return jsonify(session_list)

    except Exception as e:
        logger.error(f"Error listing sessions: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/sessions", methods=["POST"])
def create_session():
    """Create a new session."""
    try:
        try:
            data = request.get_json()
        except BadRequest:
            return jsonify({"error": "Invalid JSON payload"}), 400
        if data is None:
            return jsonify({"error": "Invalid JSON payload"}), 400

        title = data.get("title")
        tags = data.get("tags", [])

        # Validate tags is a list if provided
        if tags is not None and not isinstance(tags, list):
            return jsonify({"error": "tags must be an array"}), 400

        store = get_default_session_store()
        session_state = store.create(title=title, tags=tags)

        logger.info(f"Created session {session_state.meta.id} with title: {title}")

        return (
            jsonify(
                {
                    "id": session_state.meta.id,
                    "created_at": session_state.meta.created_at.isoformat(),
                    "last_updated": session_state.meta.last_updated.isoformat(),
                    "title": session_state.meta.title,
                    "tags": session_state.meta.tags,
                }
            ),
            201,
        )

    except Exception as e:
        logger.error(f"Error creating session: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/sessions/resume", methods=["POST"])
def resume_session():
    """Resume an existing session."""
    try:
        try:
            data = request.get_json()
        except BadRequest:
            return jsonify({"error": "Invalid JSON payload"}), 400
        if data is None:
            return jsonify({"error": "Invalid JSON payload"}), 400

        session_id = data.get("id")
        if not session_id:
            return jsonify({"error": "id is required"}), 400

        store = get_default_session_store()

        # Check if session exists
        try:
            store.load(session_id)
        except ValueError:
            return jsonify({"ok": False, "error": "not_found"}), 404

        # Set current session context
        set_current_session_id(session_id)

        logger.info(f"Resumed session {session_id}")

        return jsonify({"ok": True, "id": session_id})

    except Exception as e:
        logger.error(f"Error resuming session: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500


# Session export endpoints
@app.route("/api/sessions/<session_id>/exports", methods=["GET"])
def get_session_exports(session_id):
    """Get list of export files for a session."""
    try:
        # Validate session exists
        store = get_default_session_store()
        try:
            store.load(session_id)
        except ValueError:
            return jsonify({"error": "Session not found"}), 404

        # Get exports directory for this session
        sessions_dir = config.get_sessions_dir()
        session_exports_dir = sessions_dir / session_id

        if not session_exports_dir.exists():
            return jsonify([])  # Return empty list if no exports

        # Get limit parameter
        limit = request.args.get("limit", type=int)

        # Find export files matching patterns
        export_files = []
        for file_path in session_exports_dir.iterdir():
            if file_path.is_file():
                filename = file_path.name
                # Check for allowed patterns
                if filename.startswith("summary_") and filename.endswith(".json"):
                    kind = "json"
                elif filename.startswith("minutes_") and filename.endswith(".md"):
                    kind = "markdown"
                else:
                    continue

                # Get file stats
                stat = file_path.stat()
                export_files.append(
                    {
                        "filename": filename,
                        "size_bytes": stat.st_size,
                        "created_at": datetime.fromtimestamp(stat.st_ctime).isoformat(),
                        "kind": kind,
                    }
                )

        # Sort by creation time (newest first)
        export_files.sort(key=lambda x: x["created_at"], reverse=True)

        # Apply limit if provided
        if limit and limit > 0:
            export_files = export_files[:limit]

        logger.debug(f"Listed {len(export_files)} exports for session {session_id}")
        return jsonify(export_files)

    except Exception as e:
        logger.error(f"Error listing session exports: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/sessions/<session_id>/export", methods=["POST"])
def trigger_session_export(session_id):
    """Trigger export for a session."""
    try:
        # Validate session exists
        store = get_default_session_store()
        try:
            store.load(session_id)
        except ValueError:
            return jsonify({"ok": False, "error": "Session not found"}), 404

        # Create exports directory for this session
        sessions_dir = config.get_sessions_dir()
        session_exports_dir = sessions_dir / session_id
        session_exports_dir.mkdir(parents=True, exist_ok=True)

        # Export to both JSON and Markdown
        created_files = []

        try:
            # Build messages from session events for export
            session_state = store.load(session_id)
            messages_for_export = []
            for event in sorted(session_state.events, key=lambda e: e.ts):
                if event.type == "message":
                    messages_for_export.append({
                        "message_type": event.payload.get("message_type", "message"),
                        "role": event.actor,
                        "content": event.payload.get("content", ""),
                        "created_at": event.ts.isoformat(),
                    })

            # Export to JSON
            json_path = export_session_to_json(
                session_id, dest_dir=session_exports_dir, messages=messages_for_export
            )
            json_filename = json_path.name
            created_files.append({"filename": json_filename, "kind": "json"})

            # Export to Markdown
            md_path = export_session_to_markdown(
                session_id, dest_dir=session_exports_dir, messages=messages_for_export
            )
            md_filename = md_path.name
            created_files.append({"filename": md_filename, "kind": "markdown"})

            logger.info(
                f"Exported session {session_id}: {json_filename}, {md_filename}"
            )
            return jsonify({"ok": True, "created": created_files})

        except Exception as export_error:
            logger.error(f"Export failed for session {session_id}: {export_error}")
            return (
                jsonify({"ok": False, "error": f"Export failed: {str(export_error)}"}),
                500,
            )

    except Exception as e:
        logger.error(f"Error triggering session export: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/sessions/<session_id>/exports/<path:filename>")
def download_session_export(session_id, filename):
    """Download a specific export file for a session."""
    try:
        # Validate session exists
        store = get_default_session_store()
        try:
            store.load(session_id)
        except ValueError:
            return jsonify({"error": "Session not found"}), 404

        # Security: Prevent path traversal
        if ".." in filename or "/" in filename or "\\" in filename:
            return jsonify({"error": "Invalid filename"}), 400

        # Security: Validate filename pattern
        if not (
            filename.startswith("summary_") and filename.endswith(".json")
        ) and not (filename.startswith("minutes_") and filename.endswith(".md")):
            return jsonify({"error": "Invalid filename pattern"}), 400

        # Get file path
        sessions_dir = config.get_sessions_dir()
        file_path = sessions_dir / session_id / filename

        if not file_path.exists() or not file_path.is_file():
            return jsonify({"error": "File not found"}), 404

        # Determine MIME type
        if filename.endswith(".json"):
            mime_type = "application/json"
        elif filename.endswith(".md"):
            mime_type = "text/markdown"
        else:
            mime_type = "application/octet-stream"

        logger.debug(f"Downloading export file: {file_path}")
        return send_from_directory(
            sessions_dir / session_id, filename, as_attachment=True, mimetype=mime_type
        )

    except Exception as e:
        logger.error(f"Error downloading session export: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/sessions/<session_id>/assign_secretary", methods=["POST"])
def assign_secretary_route(session_id):
    """Assign secretary role to an agent mid-session."""
    try:
        data = request.json
        agent_id = data.get("agent_id")

        if not agent_id:
            return jsonify({"status": "error", "message": "agent_id required"}), 400

        # Get the active session
        if session_id not in active_sessions:
            return jsonify({"status": "error", "message": "Session not found"}), 404

        session_handler = active_sessions[session_id]
        swarm = session_handler.swarm

        # Set session context for event tracking
        set_current_session_id(session_id)

        # Assign the role
        swarm.assign_role(agent_id, "secretary")

        # Get the assigned agent for confirmation
        secretary_agent = swarm.get_secretary()
        if not secretary_agent:
            return jsonify({
                "status": "error",
                "message": "Failed to assign secretary role"
            }), 500

        # Track role assignment to persistent store
        track_action("system", "role_assignment", {
            "agent_id": agent_id,
            "agent_name": secretary_agent.name,
            "role": "secretary"
        })

        # Use the centralized notification function
        notify_secretary_change(session_id, swarm)

        return jsonify({
            "status": "success",
            "message": f"{secretary_agent.name} is now the secretary",
            "agent_name": secretary_agent.name
        })

    except Exception as e:
        logger.error(f"Error assigning secretary: {e}", exc_info=True)
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500


# WebSocket events
@socketio.on("connect")
def on_connect():
    """Handle client connection."""
    print(f"Client connected: {request.sid}")


@socketio.on("disconnect")
def on_disconnect():
    """Handle client disconnection."""
    print(f"Client disconnected: {request.sid}")


@socketio.on("join_session")
def on_join_session(data):
    """Join a swarm session room with automatic session restoration."""
    session_id = data.get("session_id")
    if session_id:
        # Check if session needs to be restored from persistent storage
        if session_id not in active_sessions:
            try:
                logger.info(f"Session {session_id} not in active sessions, attempting restoration from WebSocket join...")
                active_sessions[session_id] = _restore_web_swarm_from_session(session_id, socketio)
                logger.info(f"Successfully restored session {session_id} from persistent store")
            except ValueError as e:
                logger.warning(f"Session {session_id} not found in persistent store: {e}")
                emit("error", {"message": f"Session not found: {session_id}"})
                return
            except Exception as e:
                logger.error(f"Error restoring session {session_id}: {e}", exc_info=True)
                emit("error", {"message": f"Failed to restore session: {str(e)}"})
                return

        join_room(session_id)
        emit("joined", {"session_id": session_id})


@socketio.on("start_chat")
def on_start_chat(data):
    """Start chat with topic and track event."""
    session_id = data.get("session_id")
    topic = data.get("topic")

    if session_id in active_sessions:
        # Set session context for event tracking
        set_current_session_id(session_id)

        web_swarm = active_sessions[session_id]
        web_swarm.start_web_chat(topic)

        # Track chat started event
        track_system_event("chat_started", {
            "topic": topic,
            "conversation_mode": web_swarm.swarm.conversation_mode,
            "enable_secretary": web_swarm.swarm.enable_secretary
        })


@socketio.on("user_message")
def on_user_message(data):
    """Handle user message and track event."""
    session_id = data.get("session_id")
    message = data.get("message")

    if session_id in active_sessions:
        # Set session context for event tracking
        set_current_session_id(session_id)

        # Track user message to persistent store
        track_message("user", message, "user")

        web_swarm = active_sessions[session_id]
        web_swarm.process_user_message(message)


# File upload utilities
ALLOWED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".pdf", ".docx", ".txt"}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB


def _generate_unique_filename(original_filename: str) -> str:
    """Generate a unique filename with timestamp and random suffix."""
    # Get file extension
    ext = Path(original_filename).suffix.lower()

    # Generate timestamp
    timestamp = int(time.time() * 1000)

    # Generate random suffix
    random_suffix = "".join(random.choices(string.ascii_lowercase + string.digits, k=8))

    # Sanitize original name (remove extension and special chars)
    base_name = secure_filename(Path(original_filename).stem)

    return f"{base_name}_{timestamp}_{random_suffix}{ext}"


def _validate_file_upload(file) -> tuple[bool, str]:
    """Validate file upload and return (is_valid, error_message)."""
    if not file:
        return False, "No file provided"

    if not file.filename:
        return False, "No filename provided"

    # Check file extension
    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        return (
            False,
            f"File type {ext} not allowed. Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}",
        )

    # Check file size by reading first chunk
    file.seek(0, 2)  # Seek to end
    file_size = file.tell()
    file.seek(0)  # Reset to beginning

    if file_size > MAX_FILE_SIZE:
        return (
            False,
            f"File too large. Maximum size: {MAX_FILE_SIZE // (1024 * 1024)}MB",
        )

    return True, ""


def _get_file_kind(mime_type: str, filename: str) -> str:
    """Determine file kind from MIME type or filename."""
    # Check MIME type first
    if mime_type:
        if mime_type.startswith("image/"):
            return "image"
        elif mime_type == "application/pdf":
            return "document"
        elif mime_type in [
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        ]:
            return "document"
        elif mime_type.startswith("text/"):
            return "document"

    # Fallback to file extension
    ext = Path(filename).suffix.lower()
    if ext in {".png", ".jpg", ".jpeg", ".gif"}:
        return "image"
    elif ext in {".pdf", ".docx", ".txt"}:
        return "document"

    return "document"  # Default fallback


# File upload endpoint
@app.route("/api/uploads", methods=["POST"])
def upload_file():
    """Handle file uploads with multipart/form-data."""
    try:
        # Check if file is present
        if "file" not in request.files:
            return jsonify({"error": "No file part in request"}), 400

        file = request.files["file"]

        # Validate file
        is_valid, error_msg = _validate_file_upload(file)
        if not is_valid:
            return jsonify({"error": error_msg}), 400

        # Get optional parameters
        session_id = request.form.get("session_id")
        kind = request.form.get("kind")

        # Determine storage directory
        sessions_dir = config.get_sessions_dir()
        if session_id:
            upload_dir = sessions_dir / session_id / "uploads"
        else:
            upload_dir = sessions_dir / "misc" / "uploads"

        # Ensure directory exists
        upload_dir.mkdir(parents=True, exist_ok=True)

        # Generate unique filename
        unique_filename = _generate_unique_filename(file.filename)
        file_path = upload_dir / unique_filename

        # Save file in chunks to avoid memory issues
        bytes_written = 0
        with file_path.open("wb") as f:
            while True:
                chunk = file.read(8192)  # 8KB chunks
                if not chunk:
                    break
                f.write(chunk)
                bytes_written += len(chunk)

        # Get MIME type
        mime_type, _ = mimetypes.guess_type(str(file_path))

        # Determine file kind
        if not kind:
            kind = _get_file_kind(mime_type or "", unique_filename)

        # Create relative path for storage
        path_rel = str(file_path.relative_to(sessions_dir))

        # Log upload
        logger.info(
            f"File upload saved: session_id={session_id}, filename={unique_filename}, mime={mime_type}, size={bytes_written}"
        )

        download_url = url_for("download_uploaded_file", path_rel=path_rel)

        return (
            jsonify(
                {
                    "ok": True,
                    "session_id": session_id,
                    "download_url": download_url,
                    "file": {
                        "filename": unique_filename,
                        "path_rel": path_rel,
                        "mime": mime_type or "application/octet-stream",
                        "size_bytes": bytes_written,
                        "kind": kind,
                        "download_url": download_url,
                    },
                }
            ),
            200,
        )

    except Exception as e:
        logger.error(f"File upload failed: {e}")
        return jsonify({"error": f"Upload failed: {str(e)}"}), 500


@app.route("/api/uploads/<path:path_rel>", methods=["GET"])
def download_uploaded_file(path_rel: str):
    """Stream a previously uploaded file with consistent metadata."""
    try:
        sessions_dir = config.get_sessions_dir().resolve()
        target_path = (sessions_dir / path_rel).resolve()

        try:
            target_path.relative_to(sessions_dir)
        except ValueError:
            abort(404)

        if not target_path.exists() or not target_path.is_file():
            abort(404)

        mime_type, _ = mimetypes.guess_type(str(target_path))
        mime_type = mime_type or "application/octet-stream"

        response = send_file(
            target_path,
            mimetype=mime_type,
            as_attachment=True,
            download_name=target_path.name,
            conditional=True,
        )
        response.headers["Content-Length"] = str(target_path.stat().st_size)
        return response

    except Exception as exc:
        logger.error(f"Error downloading uploaded file '{path_rel}': {exc}")
        abort(500)


# Message endpoint with attachments support
@app.route("/api/messages", methods=["POST"])
def create_message():
    """Create a new message with optional attachments."""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "Invalid JSON payload"}), 400

        # Required fields
        session_id = data.get("session_id")
        message = data.get("message")

        if not session_id:
            return jsonify({"error": "session_id is required"}), 400

        if not message:
            return jsonify({"error": "message is required"}), 400

        # Optional attachments
        attachments = data.get("attachments", [])

        # Set session context
        set_current_session_id(session_id)

        # Track message with attachments in payload
        from spds.session_tracking import track_message

        payload = {
            "content": message,
            "message_type": "user",
            "attachments": attachments,
        }

        # Create a session event directly
        from datetime import datetime

        from spds.session_store import SessionEvent

        event = SessionEvent(
            event_id=str(uuid.uuid4()),
            session_id=session_id,
            ts=datetime.now(timezone.utc),
            actor="user",
            type="message",
            payload=payload,
        )

        # Save event
        store = get_default_session_store()
        store.save_event(event)

        logger.info(
            f"Message created with {len(attachments)} attachments for session {session_id}"
        )

        return (
            jsonify(
                {
                    "ok": True,
                    "message_id": event.event_id,
                    "attachments_count": len(attachments),
                }
            ),
            201,
        )

    except Exception as e:
        logger.error(f"Message creation failed: {e}")
        return jsonify({"error": f"Message creation failed: {str(e)}"}), 500


if __name__ == "__main__":
    socketio.run(app, debug=True, host="0.0.0.0", port=5002, allow_unsafe_werkzeug=True)
