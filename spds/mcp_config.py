# spds/mcp_config.py

"""Configuration loader for MCP server definitions.

Reads ``mcp-servers.json`` and produces typed ``MCPServerEntry`` objects that
the :class:`MCPLaunchpad` uses to register servers with the Letta backend.
"""

import json
import logging
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Regex for ${ENV_VAR} or ${ENV_VAR:-default} patterns
_ENV_VAR_RE = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)(?::-(.*?))?\}")


@dataclass
class MCPServerEntry:
    """Parsed representation of a single MCP server from config."""

    name: str
    tier: int  # 1 or 2
    server_type: str  # "stdio", "sse", "streamable_http"
    command: str = ""
    args: List[str] = field(default_factory=list)
    env: Dict[str, str] = field(default_factory=dict)
    url: str = ""
    scope: str = "universal"
    description: str = ""
    categories: List[str] = field(default_factory=list)


def _resolve_env_vars(value: str) -> str:
    """Replace ``${ENV_VAR}`` and ``${ENV_VAR:-default}`` in *value*."""

    def _replacer(match: re.Match) -> str:
        var_name = match.group(1)
        default = match.group(2)  # None when no :- was present
        env_val = os.environ.get(var_name)
        if env_val is not None:
            return env_val
        if default is not None:
            return default
        logger.warning("Environment variable %s is not set and has no default", var_name)
        return match.group(0)  # leave placeholder intact

    return _ENV_VAR_RE.sub(_replacer, value)


def _resolve_env_dict(d: Dict[str, str]) -> Dict[str, str]:
    """Resolve env-var placeholders in all values of *d*."""
    return {k: _resolve_env_vars(v) for k, v in d.items()}


def load_mcp_config(path: Optional[str] = None) -> List[MCPServerEntry]:
    """Load MCP server definitions from a JSON configuration file.

    Args:
        path: Explicit path to the config file. When *None*, uses the value of
              ``SPDS_MCP_CONFIG_PATH`` or falls back to ``./mcp-servers.json``.

    Returns:
        List of :class:`MCPServerEntry` objects for both Tier 1 and Tier 2 servers.

    Raises:
        FileNotFoundError: If the resolved path does not exist.
        json.JSONDecodeError: If the file is not valid JSON.
    """
    if path is None:
        path = os.environ.get("SPDS_MCP_CONFIG_PATH", "./mcp-servers.json")

    config_path = Path(path)
    if not config_path.exists():
        raise FileNotFoundError(f"MCP config file not found: {config_path}")

    with open(config_path) as fh:
        raw: Dict[str, Any] = json.load(fh)

    entries: List[MCPServerEntry] = []

    for tier_key, tier_num in [("tier1", 1), ("tier2", 2)]:
        tier_data = raw.get(tier_key, {})
        if not isinstance(tier_data, dict):
            logger.warning("Expected dict for '%s' in MCP config, got %s", tier_key, type(tier_data).__name__)
            continue
        for name, server_def in tier_data.items():
            entry = _parse_server_entry(name, tier_num, server_def)
            if entry is not None:
                entries.append(entry)

    logger.info("Loaded %d MCP server entries (%d tier-1, %d tier-2)",
                len(entries),
                sum(1 for e in entries if e.tier == 1),
                sum(1 for e in entries if e.tier == 2))
    return entries


def _parse_server_entry(name: str, tier: int, data: Dict[str, Any]) -> Optional[MCPServerEntry]:
    """Parse a single server entry from the config dict."""
    server_type = data.get("type", "")
    if server_type not in ("stdio", "sse", "streamable_http"):
        logger.warning("Unknown MCP server type '%s' for server '%s'; skipping", server_type, name)
        return None

    env_raw = data.get("env", {})
    env_resolved = _resolve_env_dict(env_raw) if env_raw else {}

    return MCPServerEntry(
        name=name,
        tier=tier,
        server_type=server_type,
        command=data.get("command", ""),
        args=data.get("args", []),
        env=env_resolved,
        url=data.get("url", ""),
        scope=data.get("scope", "universal"),
        description=data.get("description", ""),
        categories=data.get("categories", []),
    )


def entry_to_letta_config(entry: MCPServerEntry) -> Any:
    """Convert an :class:`MCPServerEntry` to the appropriate Letta SDK config type.

    Returns one of ``CreateStdioMcpServerParam``, ``CreateSseMcpServerParam``,
    or ``CreateStreamableHTTPMcpServerParam``.

    Raises:
        ValueError: If the server type is unsupported.
        ImportError: If the required Letta SDK types are unavailable.
    """
    if entry.server_type == "stdio":
        from letta_client.types import CreateStdioMcpServerParam

        return CreateStdioMcpServerParam(
            command=entry.command,
            args=entry.args,
            env=entry.env if entry.env else None,
            mcp_server_type="stdio",
        )
    elif entry.server_type == "sse":
        from letta_client.types import CreateSseMcpServerParam

        return CreateSseMcpServerParam(
            sse_url=entry.url,
            mcp_server_type="sse",
        )
    elif entry.server_type == "streamable_http":
        from letta_client.types import CreateStreamableHTTPMcpServerParam

        return CreateStreamableHTTPMcpServerParam(
            streamable_http_url=entry.url,
            mcp_server_type="streamable_http",
        )
    else:
        raise ValueError(f"Unsupported MCP server type: {entry.server_type}")
