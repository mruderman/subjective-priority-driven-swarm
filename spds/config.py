# spds/config.py

import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Letta ADE Server Configuration
LETTA_API_KEY = os.getenv("LETTA_API_KEY", "")
LETTA_SERVER_PASSWORD = os.getenv("LETTA_PASSWORD", "")
LETTA_BASE_URL = os.getenv("LETTA_BASE_URL", "http://localhost:8283")
LETTA_ENVIRONMENT = os.getenv("LETTA_ENVIRONMENT", "SELF_HOSTED")

# Default Model Configuration (fallback values)
DEFAULT_AGENT_MODEL = "openai/gpt-4"
DEFAULT_EMBEDDING_MODEL = "openai/text-embedding-ada-002"

# Default Swarm Configuration
# This list of agent profiles is used if no other configuration is provided.
# Each dictionary defines a single agent for the swarm.
# Optional fields: "model" and "embedding" to specify per-agent models
AGENT_PROFILES = [
    {
        "name": "Alex",
        "persona": "A pragmatic and analytical project manager who values clarity and efficiency.",
        "expertise": ["risk management", "scheduling", "budgeting"],
        "model": "openai/gpt-4",
        "embedding": "openai/text-embedding-ada-002",
    },
    {
        "name": "Jordan",
        "persona": "A creative and user-focused designer with a passion for intuitive interfaces.",
        "expertise": ["UX/UI design", "user research", "prototyping"],
        "model": "anthropic/claude-3-5-sonnet-20241022",
        "embedding": "openai/text-embedding-ada-002",
    },
    {
        "name": "Casey",
        "persona": "A detail-oriented and meticulous engineer who prioritizes code quality and stability.",
        "expertise": ["backend systems", "database architecture", "API development"],
        "model": "openai/gpt-4",
        "embedding": "openai/text-embedding-ada-002",
    },
    {
        "name": "Morgan",
        "persona": "A strategic and forward-thinking product owner focused on market fit and business goals.",
        "expertise": ["market analysis", "product strategy", "roadmapping"],
        "model": "together/nvidia/Llama-3.1-Nemotron-70B-Instruct-HF",
        "embedding": "openai/text-embedding-ada-002",
    },
]

# Conversation Parameters
PARTICIPATION_THRESHOLD = int(os.getenv("PARTICIPATION_THRESHOLD", "30"))
URGENCY_WEIGHT = float(os.getenv("URGENCY_WEIGHT", "0.6"))
IMPORTANCE_WEIGHT = float(os.getenv("IMPORTANCE_WEIGHT", "0.4"))

# Secretary Agent Configuration
ENABLE_SECRETARY_DEFAULT = True
DEFAULT_SECRETARY_MODE = "adaptive"  # "formal", "casual", or "adaptive"
DEFAULT_MEETING_TYPE = "discussion"  # "discussion", "board_meeting", "working_session"

# Export Configuration
DEFAULT_EXPORT_DIRECTORY = os.getenv("EXPORT_DIRECTORY", "./exports")
DEFAULT_EXPORT_FORMAT = "minutes"  # "minutes", "casual", "transcript", "actions", "summary", "all"
AUTO_EXPORT_ON_END = bool(os.getenv("AUTO_EXPORT_ON_END", "False"))

# Organization Settings for Formal Minutes
ORGANIZATION_NAME = os.getenv("ORGANIZATION_NAME", "CYAN SOCIETY")
ORGANIZATION_TYPE = "nonprofit"  # "nonprofit", "corporation", "partnership"

# Meeting Templates Configuration
FORMAL_MINUTES_INCLUDE_STATS = True
CASUAL_NOTES_INCLUDE_EMOJIS = True
EXPORT_FILE_TIMESTAMP_FORMAT = "%Y%m%d_%H%M%S"

# Secretary Behavior Settings
SECRETARY_AUTO_DETECT_DECISIONS = True
SECRETARY_AUTO_DETECT_ACTION_ITEMS = True
SECRETARY_INTERVENTION_LEVEL = "minimal"  # "none", "minimal", "active", "full"
