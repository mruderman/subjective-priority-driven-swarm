# spds/main.py

import argparse
import json
import logging
import sys
from typing import Optional

import questionary
from letta_client import Letta

from . import config
from .conversations import ConversationManager
from .session_context import set_current_session_id
from .swarm_manager import SwarmManager

logger = logging.getLogger(__name__)


def load_swarm_from_file(filepath: str):
    """Loads agent profiles from a JSON file."""
    try:
        with open(filepath, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"Error: Swarm configuration file not found at '{filepath}'")
        return None
    except json.JSONDecodeError:
        print(f"Error: Could not decode JSON from '{filepath}'")
        return None


def list_available_agents(client: Letta):
    """Fetches all available agents from the Letta server."""
    try:
        agents = list(client.agents.list())
        return agents
    except Exception as e:
        print(f"Error fetching agents from Letta server: {e}")
        return []


def interactive_agent_selection(client: Letta):
    """Presents an interactive checkbox interface for selecting agents."""
    print("🤖 Discovering available agents from Letta server...")

    agents = list_available_agents(client)

    if not agents:
        print("❌ No agents found on the Letta server.")
        print(
            "💡 Create some agents first using the Letta ADE (app.letta.com) or agent creation scripts."
        )
        return None, None

    print(f"✅ Found {len(agents)} available agents")

    # Format agent choices for the checkbox interface
    choices = []
    for agent in agents:
        # Extract model and creation info
        model_info = (
            f"({agent.model})" if hasattr(agent, "model") and agent.model else ""
        )
        created_info = (
            f"Created: {str(agent.created_at)[:10]}"
            if hasattr(agent, "created_at") and agent.created_at
            else ""
        )

        display_name = f"{agent.name} {model_info}"
        if created_info:
            display_name += f" - {created_info}"

        choices.append({"name": display_name, "value": agent.id, "checked": False})

    # Present checkbox selection
    selected_agent_ids = questionary.checkbox(
        "📋 Select agents for your swarm (use space to select, enter to confirm):",
        choices=choices,
    ).ask()

    if not selected_agent_ids:
        print("❌ No agents selected. Exiting.")
        return None, None

    # Get conversation mode selection
    conversation_mode = questionary.select(
        "🎭 Select conversation mode:",
        choices=[
            "🔄 Hybrid (independent thoughts + response round) [RECOMMENDED]",
            "👥 All-Speak (everyone responds in priority order)",
            "🔀 Sequential (one speaker per turn with fairness)",
            "🎯 Pure Priority (highest motivation always speaks)",
        ],
        default="🔄 Hybrid (independent thoughts + response round) [RECOMMENDED]",
    ).ask()

    # Map display names to internal values
    mode_mapping = {
        "🔄 Hybrid (independent thoughts + response round) [RECOMMENDED]": "hybrid",
        "👥 All-Speak (everyone responds in priority order)": "all_speak",
        "🔀 Sequential (one speaker per turn with fairness)": "sequential",
        "🎯 Pure Priority (highest motivation always speaks)": "pure_priority",
    }

    conversation_mode = mode_mapping.get(conversation_mode, "hybrid")

    if not conversation_mode:
        print("❌ No conversation mode selected. Exiting.")
        return None, None, None

    # Get secretary preferences
    enable_secretary = questionary.confirm(
        "📝 Enable meeting secretary? (Records minutes and allows export)", default=True
    ).ask()

    secretary_mode = "adaptive"
    meeting_type = "discussion"

    if enable_secretary:
        # Get meeting type
        meeting_type_choice = questionary.select(
            "📋 What type of meeting is this?",
            choices=[
                "💬 Casual Group Discussion",
                "📋 Formal Board Meeting (Cyan Society)",
                "🤖 Let Secretary Decide (Adaptive)",
            ],
            default="🤖 Let Secretary Decide (Adaptive)",
        ).ask()

        meeting_type_mapping = {
            "💬 Casual Group Discussion": ("casual", "discussion"),
            "📋 Formal Board Meeting (Cyan Society)": ("formal", "board_meeting"),
            "🤖 Let Secretary Decide (Adaptive)": ("adaptive", "discussion"),
        }

        secretary_mode, meeting_type = meeting_type_mapping.get(
            meeting_type_choice, ("adaptive", "discussion")
        )

    # Get topic from user
    topic = questionary.text("💬 Enter the conversation topic or meeting agenda:").ask()

    if not topic:
        print("❌ No topic provided. Exiting.")
        return None, None, None, None, None

    print(
        f"\n🎯 Selected {len(selected_agent_ids)} agents for discussion in {conversation_mode.upper()} mode: '{topic}'"
    )
    if enable_secretary:
        print(f"📝 Secretary: {secretary_mode} mode for {meeting_type}")

    return (
        selected_agent_ids,
        topic,
        conversation_mode,
        enable_secretary,
        secretary_mode,
        meeting_type,
    )


def format_session_table(sessions: list) -> str:
    """Format conversation list as a human-readable table."""
    if not sessions:
        return "No sessions found."

    lines = [
        f"{'ID':<12} {'Created':<20} {'Updated':<20} {'Summary':<40}",
        "-" * 95,
    ]

    for conv in sessions:
        cid = getattr(conv, "id", str(conv)) if not isinstance(conv, dict) else conv.get("id", "")
        display_id = cid[:8] + "..." if len(cid) > 8 else cid

        created_at = getattr(conv, "created_at", None)
        updated_at = getattr(conv, "updated_at", None)
        created_str = created_at.strftime("%Y-%m-%d %H:%M") if created_at else ""
        updated_str = updated_at.strftime("%Y-%m-%d %H:%M") if updated_at else ""

        summary = getattr(conv, "summary", None) or ""
        display_summary = summary[:37] + "..." if len(summary) > 37 else summary

        lines.append(
            f"{display_id:<12} {created_str:<20} {updated_str:<20} {display_summary:<40}"
        )

    return "\n".join(lines)


def list_sessions_command(args, client=None):
    """Handle the 'sessions list' command.

    Requires ``--agent-id`` to specify which agent's conversations to list,
    since conversations are per-agent in the Letta Conversations API.
    """
    if client is None:
        print("Error: Letta client required for session listing", file=sys.stderr)
        return 1

    agent_id = getattr(args, "agent_id", None)
    if not agent_id:
        print("Error: --agent-id is required for listing sessions", file=sys.stderr)
        return 1

    cm = ConversationManager(client)
    sessions = cm.list_sessions(agent_id)

    if getattr(args, "json", False):
        import json as json_lib

        sessions_data = [
            cm.get_session_summary(conv.id) for conv in sessions
        ]
        print(json_lib.dumps(sessions_data, indent=2))
    else:
        print(format_session_table(sessions))

    return 0


def resume_session_command(args, client=None):
    """Handle the 'sessions resume' command."""
    if client is None:
        print("Error: Letta client required for session resume", file=sys.stderr)
        return 1

    conversation_id = args.session_id
    cm = ConversationManager(client)

    try:
        cm.get_session(conversation_id)
        set_current_session_id(conversation_id)
        print(f"Session resumed: {conversation_id}")
        return 0
    except Exception:
        print(f"Error: Conversation '{conversation_id}' not found", file=sys.stderr)
        return 2


def setup_session_context(args) -> Optional[str]:
    """Set up session context based on CLI arguments."""
    if getattr(args, "session_id", None):
        set_current_session_id(args.session_id)
        logger.info(f"Set conversation context: {args.session_id}")
        return args.session_id

    # No session management requested - return None
    return None


def main(argv=None):
    """Initializes the Letta client and starts the swarm chat."""

    parser = argparse.ArgumentParser(
        description="Run a Subjective Priority-Driven Swarm chat. "
        "Specify agents by ID, name, or a config file.",
        formatter_class=argparse.RawTextHelpFormatter,
    )

    # Session management arguments
    session_group = parser.add_argument_group("Session Management")
    session_group.add_argument(
        "--session-id",
        type=str,
        metavar="SESSION_ID",
        help="Resume an existing session by ID. If provided, no new session is created.",
    )

    # Agent selection group (existing)
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--agent-ids",
        nargs="+",
        metavar="ID",
        help="A list of existing agent IDs to include in the swarm.",
    )
    group.add_argument(
        "--agent-names",
        nargs="+",
        metavar="NAME",
        help="A list of existing agent names to include in the swarm.",
    )
    group.add_argument(
        "--swarm-config",
        type=str,
        metavar="PATH",
        help="Path to a JSON file to create a new, temporary swarm.",
    )
    parser.add_argument(
        "--interactive",
        action="store_true",
        help="Use interactive agent selection and setup (overrides default ephemeral mode).",
    )
    parser.add_argument(
        "--secretary",
        "-s",
        type=str,
        metavar="AGENT_NAME",
        help="Name of the agent to assign as secretary. Must match one of the selected agents.",
    )

    # Subcommands for session management
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Sessions subcommand
    sessions_parser = subparsers.add_parser("sessions", help="Manage sessions")
    sessions_subparsers = sessions_parser.add_subparsers(dest="sessions_command")

    # sessions list
    list_parser = sessions_subparsers.add_parser("list", help="List all sessions")
    list_parser.add_argument(
        "--agent-id",
        type=str,
        metavar="AGENT_ID",
        required=True,
        help="Agent ID whose sessions to list",
    )
    list_parser.add_argument(
        "--json",
        action="store_true",
        help="Output sessions as JSON instead of table format",
    )

    # sessions resume
    resume_parser = sessions_subparsers.add_parser("resume", help="Resume a session")
    resume_parser.add_argument(
        "session_id",
        help="The ID of the session to resume",
    )

    # Allow passing argv for testing; default to sys.argv[1:]
    args = parser.parse_args(argv)

    agent_profiles = None
    agent_ids = None
    agent_names = None

    # --- Client Initialization ---
    # Use configuration from environment variables
    # For self-hosted servers with password protection, use the password as token
    letta_password = config.get_letta_password()
    if config.LETTA_ENVIRONMENT == "SELF_HOSTED" and letta_password:
        client = Letta(api_key=letta_password, base_url=config.LETTA_BASE_URL)
    elif config.LETTA_API_KEY:
        client = Letta(api_key=config.LETTA_API_KEY, base_url=config.LETTA_BASE_URL)
    else:
        # No authentication (local self-hosted without password protection)
        client = Letta(base_url=config.LETTA_BASE_URL)

    # Handle session management subcommands (require client)
    if args.command == "sessions":
        if args.sessions_command == "list":
            return list_sessions_command(args, client=client)
        elif args.sessions_command == "resume":
            return resume_session_command(args, client=client)
        else:
            sessions_parser.print_help()
            return 1

    # Set up session context for main commands (before any swarm operations)
    setup_session_context(args)

    if args.agent_ids:
        print("Mode: Loading existing agents by ID.")
        agent_ids = args.agent_ids
    elif args.agent_names:
        print("Mode: Loading existing agents by name.")
        agent_names = args.agent_names
    elif args.swarm_config:
        print(f"Mode: Creating temporary swarm from config: {args.swarm_config}")
        agent_profiles = load_swarm_from_file(args.swarm_config)
        if not agent_profiles:
            sys.exit(1)  # Exit if the config file is invalid or not found
    elif args.interactive:
        # Interactive setup explicitly requested
        print("Mode: Interactive agent selection")
        result = interactive_agent_selection(client)
        if not result or len(result) < 6:
            sys.exit(1)  # User cancelled or no agents selected
        (
            selected_agent_ids,
            topic,
            conversation_mode,
            enable_secretary,
            secretary_mode,
            meeting_type,
        ) = result
        agent_ids = selected_agent_ids
    else:
        # Default to ephemeral swarm from config.AGENT_PROFILES (test-friendly)
        print("Mode: Creating temporary swarm from default configuration")
        # Print header and attempt to get topic before contacting server
        print("\nSwarm chat started. Type 'quit' or Ctrl+D to end the session.")
        try:
            topic = input("Enter the topic of conversation: ")
        except EOFError:
            print("\nExiting.")
            sys.exit(0)
        print("Creating swarm from temporary agent profiles...")
        # Validate agent profiles before use
        try:
            validated_config = config.get_agent_profiles_validated()
            agent_profiles = [agent.dict() for agent in validated_config.agents]
            print(f"Validated {len(agent_profiles)} agent profiles successfully.")
        except Exception as e:
            print(f"Error: Invalid agent profiles configuration: {e}")
            print("Please check your agent profiles configuration and try again.")
            sys.exit(1)

    try:
        # Set conversation mode - default to sequential for non-interactive flows
        mode = conversation_mode if "conversation_mode" in locals() else "sequential"

        # Set secretary options - default to disabled for non-interactive mode
        secretary_enabled = (
            enable_secretary if "enable_secretary" in locals() else False
        )
        sec_mode = secretary_mode if "secretary_mode" in locals() else "adaptive"
        meet_type = meeting_type if "meeting_type" in locals() else "discussion"

        swarm = SwarmManager(
            client=client,
            agent_profiles=agent_profiles,
            agent_ids=agent_ids,
            agent_names=agent_names,
            conversation_mode=mode,
            enable_secretary=secretary_enabled,
            secretary_mode=sec_mode,
            meeting_type=meet_type,
        )

        # Assign secretary if specified via CLI flag
        if hasattr(args, 'secretary') and args.secretary:
            logger.info(f"Assigning secretary from CLI flag: {args.secretary}")
            swarm.assign_role_by_name(args.secretary, "secretary")
            print(f"✅ Assigned {args.secretary} as secretary")

        # If we already captured topic (default ephemeral), start with it
        if "topic" in locals() and topic:
            swarm.start_chat_with_topic(topic)
        else:
            swarm.start_chat()
    except ValueError as e:
        print(f"Error initializing swarm: {e}")
        sys.exit(1)

    return 0


if __name__ == "__main__":
    # Configure logging for CLI
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    sys.exit(main())
