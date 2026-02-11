# spds/config.py

import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

# Load environment variables
load_dotenv()


# --- Logging Configuration ---


def setup_logging():
    """
    Configure the root logger to emit to the console and to a rotating file.

    This function:
    - Reads LOG_LEVEL from the environment (default "INFO") and applies it to the root logger.
    - Ensures a "logs" directory exists and writes logs to "logs/spds.log".
    - Clears any existing handlers on the root logger to avoid duplicate outputs.
    - Attaches a console StreamHandler and a RotatingFileHandler (10 MB per file, 5 backups) with distinct formatters.

    Side effects:
    - Creates the "logs" directory if missing.
    - Mutates the global logging configuration (root logger and module logger).
    """
    log_level = os.getenv("LOG_LEVEL", "INFO").upper()
    log_dir = "logs"
    log_file = os.path.join(log_dir, "spds.log")

    # Create log directory if it doesn't exist
    os.makedirs(log_dir, exist_ok=True)

    # Get the root logger
    logger = logging.getLogger()

    # Prevent duplicate handlers if called multiple times
    if logger.hasHandlers():
        logger.handlers.clear()

    logger.setLevel(log_level)

    # Create console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(log_level)
    console_formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)

    # Create rotating file handler
    file_handler = RotatingFileHandler(
        log_file, maxBytes=10 * 1024 * 1024, backupCount=5  # 10MB per file, 5 backups
    )
    file_handler.setLevel(log_level)
    file_formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(module)s:%(lineno)d - %(message)s"
    )
    file_handler.setFormatter(file_formatter)
    logger.addHandler(file_handler)

    logging.getLogger(__name__).info(
        "Logging configured successfully with console and file output."
    )


# Initialize logging when the module is loaded (can be disabled for tests/embedding)
if os.getenv("SPDS_INIT_LOGGING", "1") == "1":
    setup_logging()
logger = logging.getLogger(__name__)


# Letta ADE Server Configuration
# Read sensitive values from environment. For local development we provide a
# non-sensitive localhost fallback so the app works out of the box. Production
# deployments should set real environment variables or use a secrets manager.
LETTA_API_KEY = os.getenv("LETTA_API_KEY", "")
LETTA_SERVER_PASSWORD = os.getenv("LETTA_SERVER_PASSWORD", "")
# Default to localhost for self-hosted development convenience
LETTA_BASE_URL = os.getenv("LETTA_BASE_URL", "http://localhost:8283")
# Environment: e.g. "SELF_HOSTED", "LETTA_CLOUD", "PRODUCTION" (fallback
# is SELF_HOSTED for local dev). Keep the value explicit in production.
LETTA_ENVIRONMENT = os.getenv("LETTA_ENVIRONMENT", "SELF_HOSTED")


def get_letta_password() -> str:
    """
    Get the Letta server password with proper precedence between LETTA_PASSWORD and LETTA_SERVER_PASSWORD.

    This function implements a centralized accessor for Letta server authentication that:
    - Prefers LETTA_PASSWORD if both variables are set
    - Falls back to LETTA_SERVER_PASSWORD if LETTA_PASSWORD is not set
    - Logs deprecation warning when using LETTA_SERVER_PASSWORD
    - Logs preference information when both are set

    Returns:
        str: The password to use for Letta server authentication, or empty string if neither is set
    """
    letta_password = os.getenv("LETTA_PASSWORD")
    letta_server_password = os.getenv("LETTA_SERVER_PASSWORD")

    if letta_password and letta_server_password:
        # Both are set, prefer LETTA_PASSWORD
        logger.info(
            "Preferring LETTA_PASSWORD over LETTA_SERVER_PASSWORD for authentication"
        )
        return letta_password
    elif letta_password:
        # Only LETTA_PASSWORD is set
        return letta_password
    elif letta_server_password:
        # Only LETTA_SERVER_PASSWORD is set, log deprecation warning
        logger.warning(
            "Using deprecated LETTA_SERVER_PASSWORD environment variable. "
            "Please migrate to LETTA_PASSWORD for future compatibility."
        )
        return letta_server_password
    else:
        # Neither is set
        return ""


# Tool execution (Docker/self-hosted)
TOOL_EXEC_DIR = os.getenv("TOOL_EXEC_DIR", "/app/tools")
TOOL_EXEC_VENV_NAME = os.getenv("TOOL_EXEC_VENV_NAME", "venv")


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
DEFAULT_EMBEDDING_MODEL = "openai/text-embedding-3-small"

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
        "embedding": "openai/text-embedding-3-small",
    },
    {
        "name": "Jordan",
        "persona": "A creative and user-focused designer with a passion for intuitive interfaces.",
        "expertise": ["UX/UI design", "user research", "prototyping"],
        "model": "anthropic/claude-3-5-sonnet-20241022",
        "embedding": "openai/text-embedding-3-small",
    },
    {
        "name": "Casey",
        "persona": "A detail-oriented and meticulous engineer who prioritizes code quality and stability.",
        "expertise": ["backend systems", "database architecture", "API development"],
        "model": "openai/gpt-4",
        "embedding": "openai/text-embedding-3-small",
    },
    {
        "name": "Morgan",
        "persona": "A strategic and forward-thinking product owner focused on market fit and business goals.",
        "expertise": ["market analysis", "product strategy", "roadmapping"],
        "model": "together/nvidia/Llama-3.1-Nemotron-70B-Instruct-HF",
        "embedding": "openai/text-embedding-3-small",
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

# Import agent profile validation
from spds.profiles_schema import get_agent_profiles_validated

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

# Letta API Timeout and Retry Configuration
LETTA_TIMEOUT_SECONDS = int(os.getenv("LETTA_TIMEOUT_SECONDS", "30"))
LETTA_MAX_RETRIES = int(os.getenv("LETTA_MAX_RETRIES", "3"))
LETTA_RETRY_BASE_DELAY = float(os.getenv("LETTA_RETRY_BASE_DELAY", "0.5"))
LETTA_RETRY_FACTOR = float(os.getenv("LETTA_RETRY_FACTOR", "2.0"))
LETTA_RETRY_JITTER = float(os.getenv("LETTA_RETRY_JITTER", "0.1"))
LETTA_RETRY_MAX_BACKOFF = float(os.getenv("LETTA_RETRY_MAX_BACKOFF", "5.0"))


def get_letta_timeout_seconds() -> int:
    """
    Get the configured timeout for Letta API calls in seconds.

    Returns:
        int: Timeout value in seconds (default: 30)
    """
    return LETTA_TIMEOUT_SECONDS


def get_letta_max_retries() -> int:
    """
    Get the maximum number of retries for Letta API calls.

    Returns:
        int: Maximum retry count (default: 3)
    """
    return LETTA_MAX_RETRIES


def get_letta_retry_base_delay() -> float:
    """
    Get the base delay for exponential backoff in seconds.

    Returns:
        float: Base delay in seconds (default: 0.5)
    """
    return LETTA_RETRY_BASE_DELAY


def get_letta_retry_factor() -> float:
    """
    Get the exponential backoff factor.

    Returns:
        float: Backoff multiplier (default: 2.0)
    """
    return LETTA_RETRY_FACTOR


def get_letta_retry_jitter() -> float:
    """
    Get the jitter range for retry delays in seconds.

    Returns:
        float: Jitter range in seconds (default: 0.1)
    """
    return LETTA_RETRY_JITTER


def get_letta_retry_max_backoff() -> float:
    """
    Get the maximum backoff delay in seconds.

    Returns:
        float: Maximum backoff in seconds (default: 5.0)
    """
    return LETTA_RETRY_MAX_BACKOFF


def get_sessions_dir() -> Path:
    """
    Get the directory for storing session data.

    Returns:
        Path: Directory path for sessions (default: "exports/sessions")
    """
    return Path(os.getenv("SESSIONS_DIR", "exports/sessions"))


def get_session_autoflush_events() -> int:
    """
    Get the number of events to batch before flushing to disk.

    Returns:
        int: Number of events to batch (default: 1, flush every event)
    """
    return int(os.getenv("SESSION_AUTOFLUSH_EVENTS", "1"))


# Tool schema/export behavior
def get_tools_use_pydantic_schemas() -> bool:
    """
    Whether to pass Pydantic classes to Letta when creating tools.

    Default is False to avoid requiring Pydantic inside Letta's isolated
    tool execution environment. When False, only JSON schema will be sent.
    Enable by setting SPDS_TOOLS_USE_PYDANTIC_SCHEMAS=true if your backend
    supports it and the tool sandbox has Pydantic installed.
    """
    return os.getenv("SPDS_TOOLS_USE_PYDANTIC_SCHEMAS", "false").lower() in (
        "1",
        "true",
        "yes",
    )


def get_tools_use_return_model() -> bool:
    """
    Whether to pass return_model to Letta when creating tools.

    Default is False to avoid backend/sandbox dependencies on local models.
    Enable by setting SPDS_TOOLS_USE_RETURN_MODEL=true if supported.
    """
    return os.getenv("SPDS_TOOLS_USE_RETURN_MODEL", "false").lower() in (
        "1",
        "true",
        "yes",
    )


# Integrations Configuration
def get_integrations_enabled() -> bool:
    """
    Get whether integrations are enabled.

    Returns:
        bool: True if integrations are enabled (default: False)
    """
    return os.getenv("SPDS_ENABLE_INTEGRATIONS", "false").lower() == "true"


def get_integrations_allow_fake_providers() -> bool:
    """
    Get whether fake providers are allowed for testing.

    Returns:
        bool: True if fake providers are allowed (default: False)
    """
    allow_fake = os.getenv("SPDS_ALLOW_FAKE_PROVIDERS", "false").lower() == "true"
    if allow_fake:
        logger.warning(
            "Fake providers are enabled via SPDS_ALLOW_FAKE_PROVIDERS. "
            "This should only be used for testing and development."
        )
    return allow_fake


# Ephemeral agent policy and secretary reuse configuration
def get_allow_ephemeral_agents() -> bool:
    """
    Whether the app may create new (ephemeral) agents.

    Defaults to False to prioritize continuity and reuse of existing agents.
    Set SPDS_ALLOW_EPHEMERAL_AGENTS=true explicitly to allow creation from
    profiles or to create a new secretary when one is not provided.
    """
    env_value = os.getenv("SPDS_ALLOW_EPHEMERAL_AGENTS", "false").lower()
    return env_value in ("1", "true", "yes")


def get_secretary_agent_id() -> Optional[str]:
    """Optional fixed secretary agent ID to reuse instead of creating a new one."""
    return os.getenv("SECRETARY_AGENT_ID") or None


def get_secretary_agent_name() -> Optional[str]:
    """
    Optional secretary agent name to search for and reuse if present. If both
    ID and name are set, ID takes precedence.
    """
    return os.getenv("SECRETARY_AGENT_NAME") or None


# --- MCP Launchpad Configuration ---

def get_mcp_config_path() -> str:
    """Path to the MCP server configuration file.

    Defaults to ``./mcp-servers.json``, overridable via ``SPDS_MCP_CONFIG_PATH``.
    """
    return os.getenv("SPDS_MCP_CONFIG_PATH", "./mcp-servers.json")


def get_mcp_enabled() -> bool:
    """Whether MCP tool integration is enabled.

    Returns True if the config file exists (or ``SPDS_MCP_ENABLED`` is explicitly
    set to ``true``). Returns False if ``SPDS_MCP_ENABLED`` is ``false`` or the
    config file is missing.
    """
    explicit = os.getenv("SPDS_MCP_ENABLED")
    if explicit is not None:
        return explicit.lower() in ("1", "true", "yes")
    return Path(get_mcp_config_path()).exists()


def get_mcp_tier1_enabled() -> bool:
    """Whether Tier 1 (always-on) MCP tools are enabled. Default: True."""
    return os.getenv("SPDS_MCP_TIER1_ENABLED", "true").lower() in ("1", "true", "yes")


def get_mcp_tier2_enabled() -> bool:
    """Whether Tier 2 (on-demand) MCP tools are enabled. Default: True."""
    return os.getenv("SPDS_MCP_TIER2_ENABLED", "true").lower() in ("1", "true", "yes")
