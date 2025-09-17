# spds/config.py

import logging
import os

from dotenv import load_dotenv

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)

# Letta ADE Server Configuration
# Read sensitive values from environment. For local development we provide a
# non-sensitive localhost fallback so the app works out of the box. Production
# deployments should set real environment variables or use a secrets manager.
LETTA_API_KEY = os.getenv("LETTA_API_KEY", "")
LETTA_SERVER_PASSWORD = os.getenv("LETTA_PASSWORD", "")
# Default to localhost for self-hosted development convenience
LETTA_BASE_URL = os.getenv("LETTA_BASE_URL", "http://localhost:8283")
# Environment: e.g. "SELF_HOSTED", "LETTA_CLOUD", "PRODUCTION" (fallback
# is SELF_HOSTED for local dev). Keep the value explicit in production.
LETTA_ENVIRONMENT = os.getenv("LETTA_ENVIRONMENT", "SELF_HOSTED")


def validate_letta_config(check_connectivity: bool = False, timeout: int = 5) -> bool:
    """Validate critical Letta configuration and optionally check connectivity.

    - Ensures `LETTA_BASE_URL` is set (there's a localhost fallback for dev).
    - If running against Letta Cloud (`LETTA_ENVIRONMENT == 'LETTA_CLOUD'`),
      ensures `LETTA_API_KEY` is provided.
    - If `check_connectivity` is True and the `requests` package is available,
      performs a simple GET against `LETTA_BASE_URL` and raises a RuntimeError on
      non-successful or unreachable responses.

    Returns True if validation passes. Raises `ValueError` or `RuntimeError` on
    configuration/connectivity problems.
    """

    # Read current environment values at call time (allows tests and runtime to
    # change env vars without re-importing the module).
    # Read from the live environment where possible. For API keys we intentionally
    # check `os.environ` directly so that tests (which manipulate env vars) and
    # runtime checks reflect the current environment rather than any module-level
    # values that were populated at import time (for example by python-dotenv).
    cur_base_url = os.environ.get("LETTA_BASE_URL", LETTA_BASE_URL)
    cur_env = os.environ.get("LETTA_ENVIRONMENT", LETTA_ENVIRONMENT)
    cur_api_key = os.environ.get("LETTA_API_KEY")

    # Basic configuration checks
    if not cur_base_url:
        raise ValueError(
            "LETTA_BASE_URL is not set. Set the LETTA_BASE_URL environment variable to your Letta server URL."
        )

    if cur_env.upper() == "LETTA_CLOUD" and not cur_api_key:
        raise ValueError(
            "LETTA_API_KEY is required when LETTA_ENVIRONMENT=LETTA_CLOUD. Please set LETTA_API_KEY in your environment or secrets manager."
        )

    # Optional connectivity check
    if check_connectivity:
        try:
            import requests
        except Exception:
            logger.warning(
                "requests package not available; skipping LETTA server connectivity check. Install 'requests' to enable connectivity checks."
            )
            return True

        try:
            resp = requests.get(cur_base_url, timeout=timeout)
        except Exception as exc:
            # Catch any exception from the requests call and surface a RuntimeError
            raise RuntimeError(f"Unable to reach LETTA server at {cur_base_url}: {exc}")

        if not (200 <= getattr(resp, "status_code", 0) < 400):
            raise RuntimeError(
                f"LETTA server at {cur_base_url} returned status {resp.status_code}. Response: {resp.text[:200]!r}"
            )

    return True


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
DEFAULT_EXPORT_FORMAT = (
    "minutes"  # "minutes", "casual", "transcript", "actions", "summary", "all"
)
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
