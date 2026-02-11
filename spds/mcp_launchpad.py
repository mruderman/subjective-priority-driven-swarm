# spds/mcp_launchpad.py

"""MCP Launchpad — register, catalog, and execute MCP tools on behalf of agents.

The :class:`MCPLaunchpad` manages the full lifecycle:

1. **Register** MCP servers with the Letta backend (idempotent).
2. **Build** a catalog of available tools from those servers.
3. **Create / attach** a ``tool_ecosystem`` shared memory block so agents can
   read what tools are available.
4. **Attach** Tier 1 (always-on) tools to all agents at startup.
5. **Fulfill** on-demand Tier 2 tool requests: attach the tool, execute it via
   ``client.agents.tools.run()``, and return the result.
"""

import json
import logging
from typing import Any, Dict, List, Optional

from .letta_api import letta_call
from .mcp_config import MCPServerEntry, entry_to_letta_config

logger = logging.getLogger(__name__)

# Hard limit for the tool_ecosystem block content
_ECOSYSTEM_BLOCK_MAX_CHARS = 4500
_TOOL_DESC_MAX_CHARS = 80
_TOOLS_PER_SERVER_MAX = 10


class MCPLaunchpad:
    """Manages MCP server registration, tool cataloging, and on-demand execution."""

    def __init__(self, client, config_entries: List[MCPServerEntry]):
        self._client = client
        self._config_entries = config_entries
        self._catalog: Dict[str, List[Dict[str, Any]]] = {}  # server_name -> [tool_info]
        self._registered_servers: Dict[str, Any] = {}  # server_name -> server object
        self._ecosystem_block_id: Optional[str] = None
        self._attached_tools: Dict[str, str] = {}  # "server/tool" -> tool_id
        self._use_mcp_tool_id: Optional[str] = None

    # ------------------------------------------------------------------
    # Public orchestration
    # ------------------------------------------------------------------

    def setup(self, agent_ids: List[str]) -> None:
        """Run the full setup sequence: register, catalog, block, attach.

        This is safe to call multiple times (idempotent).
        """
        self.register_servers()
        self.build_catalog()
        self.create_ecosystem_block()
        self.attach_ecosystem_block(agent_ids)
        self.attach_tier1_tools(agent_ids)
        self.ensure_use_mcp_tool(agent_ids)
        logger.info("MCPLaunchpad setup complete for %d agents", len(agent_ids))

    # ------------------------------------------------------------------
    # Server registration
    # ------------------------------------------------------------------

    def register_servers(self) -> Dict[str, bool]:
        """Register configured MCP servers with the Letta backend.

        Skips servers that already exist (matched by name).  Returns a dict
        mapping server names to success booleans.
        """
        existing = self._list_existing_servers()
        results: Dict[str, bool] = {}

        for entry in self._config_entries:
            if entry.name in existing:
                logger.info("MCP server '%s' already registered; reusing", entry.name)
                self._registered_servers[entry.name] = existing[entry.name]
                results[entry.name] = True
                continue

            try:
                letta_config = entry_to_letta_config(entry)
                server = letta_call(
                    f"mcp_servers.create({entry.name})",
                    self._client.mcp_servers.create,
                    server_name=entry.name,
                    config=letta_config,
                )
                self._registered_servers[entry.name] = server
                results[entry.name] = True
                logger.info("Registered MCP server '%s'", entry.name)
            except Exception as exc:
                logger.warning("Failed to register MCP server '%s': %s", entry.name, exc)
                results[entry.name] = False

        return results

    def _list_existing_servers(self) -> Dict[str, Any]:
        """Query the Letta backend for already-registered MCP servers."""
        try:
            response = letta_call(
                "mcp_servers.list",
                self._client.mcp_servers.list,
            )
            # The response may be a list or an object with a .servers attribute
            servers = response
            if hasattr(response, "servers"):
                servers = response.servers
            return {
                getattr(s, "server_name", getattr(s, "name", "")): s
                for s in (servers or [])
            }
        except Exception as exc:
            logger.warning("Could not list existing MCP servers: %s", exc)
            return {}

    # ------------------------------------------------------------------
    # Catalog building
    # ------------------------------------------------------------------

    def build_catalog(self) -> Dict[str, List[Dict[str, Any]]]:
        """Query each registered server for its tool list and build the catalog."""
        self._catalog.clear()

        for server_name, server_obj in self._registered_servers.items():
            try:
                server_id = getattr(server_obj, "id", None)
                if server_id is None:
                    logger.warning("Server '%s' has no ID; skipping catalog", server_name)
                    continue

                # Refresh to get latest tools
                refreshed = letta_call(
                    f"mcp_servers.retrieve({server_name})",
                    self._client.mcp_servers.retrieve,
                    server_id,
                )

                tools_list = getattr(refreshed, "tools", []) or []
                tool_infos = []
                for tool in tools_list[:_TOOLS_PER_SERVER_MAX]:
                    tool_id = getattr(tool, "id", getattr(tool, "tool_id", ""))
                    tool_name = getattr(tool, "name", "")
                    tool_desc = getattr(tool, "description", "")[:_TOOL_DESC_MAX_CHARS]
                    tool_infos.append({
                        "id": tool_id,
                        "name": tool_name,
                        "description": tool_desc,
                    })
                    # Cache the tool_id for later attachment
                    self._attached_tools[f"{server_name}/{tool_name}"] = tool_id

                self._catalog[server_name] = tool_infos
                logger.info("Cataloged %d tools from server '%s'", len(tool_infos), server_name)

            except Exception as exc:
                logger.warning("Failed to catalog server '%s': %s", server_name, exc)
                self._catalog[server_name] = []

        return self._catalog

    # ------------------------------------------------------------------
    # Ecosystem block
    # ------------------------------------------------------------------

    def generate_ecosystem_content(self) -> str:
        """Generate agent-readable text describing available Tier 2 tools.

        Tier 1 tools are attached directly and don't need discovery text.
        """
        # Determine which entries are tier 2
        tier2_names = {e.name for e in self._config_entries if e.tier == 2}

        lines = ["Available MCP tools (use use_mcp_tool to invoke):"]

        for server_name, tools in self._catalog.items():
            if server_name not in tier2_names:
                continue
            if not tools:
                continue

            entry = next((e for e in self._config_entries if e.name == server_name), None)
            desc = entry.description if entry else ""
            lines.append(f"\n[{server_name}] {desc}")
            for t in tools:
                lines.append(f"  - {t['name']}: {t['description']}")

        content = "\n".join(lines)

        # Truncate if necessary
        if len(content) > _ECOSYSTEM_BLOCK_MAX_CHARS:
            content = content[: _ECOSYSTEM_BLOCK_MAX_CHARS - 20] + "\n... (truncated)"

        return content

    def create_ecosystem_block(self) -> Optional[str]:
        """Create or reuse the ``tool_ecosystem`` shared memory block.

        Returns the block ID, or None if no Tier 2 tools exist.
        """
        content = self.generate_ecosystem_content()

        # Check for existing block first
        try:
            existing_blocks = letta_call(
                "blocks.list(tool_ecosystem)",
                self._client.blocks.list,
                label="tool_ecosystem",
            )
            if existing_blocks:
                block = existing_blocks[0]
                self._ecosystem_block_id = block.id
                # Update content
                try:
                    letta_call(
                        "blocks.update(tool_ecosystem)",
                        self._client.blocks.update,
                        block.id,
                        value=content,
                    )
                except Exception as exc:
                    logger.warning("Could not update ecosystem block: %s", exc)
                logger.info("Reusing existing tool_ecosystem block %s", block.id)
                return self._ecosystem_block_id
        except Exception:
            pass  # blocks.list may not support label filter; fall through

        # Create new block
        try:
            block = letta_call(
                "blocks.create(tool_ecosystem)",
                self._client.blocks.create,
                label="tool_ecosystem",
                value=content,
                description="Catalog of available MCP tools agents can discover and use on demand",
            )
            self._ecosystem_block_id = block.id
            logger.info("Created tool_ecosystem block %s", block.id)
            return self._ecosystem_block_id
        except Exception as exc:
            logger.warning("Failed to create tool_ecosystem block: %s", exc)
            return None

    def attach_ecosystem_block(self, agent_ids: List[str]) -> None:
        """Attach the tool_ecosystem block to all agents."""
        if not self._ecosystem_block_id:
            return

        for agent_id in agent_ids:
            try:
                letta_call(
                    f"agents.blocks.attach({agent_id})",
                    self._client.agents.blocks.attach,
                    self._ecosystem_block_id,
                    agent_id=agent_id,
                )
            except Exception as exc:
                logger.warning("Failed to attach ecosystem block to agent %s: %s", agent_id, exc)

    # ------------------------------------------------------------------
    # Tier 1 tool attachment
    # ------------------------------------------------------------------

    def attach_tier1_tools(self, agent_ids: List[str]) -> None:
        """Attach all Tier 1 tools to all agents."""
        from . import config as spds_config

        if not spds_config.get_mcp_tier1_enabled():
            logger.info("Tier 1 MCP tools disabled; skipping attachment")
            return

        tier1_names = {e.name for e in self._config_entries if e.tier == 1}

        for server_name in tier1_names:
            tools = self._catalog.get(server_name, [])
            for tool_info in tools:
                tool_id = tool_info.get("id")
                if not tool_id:
                    continue
                for agent_id in agent_ids:
                    try:
                        letta_call(
                            f"agents.tools.attach({tool_info['name']}→{agent_id})",
                            self._client.agents.tools.attach,
                            tool_id,
                            agent_id=agent_id,
                        )
                    except Exception as exc:
                        logger.warning(
                            "Failed to attach tier-1 tool '%s' to agent %s: %s",
                            tool_info["name"], agent_id, exc,
                        )

    # ------------------------------------------------------------------
    # use_mcp_tool registration
    # ------------------------------------------------------------------

    def ensure_use_mcp_tool(self, agent_ids: List[str]) -> None:
        """Register the ``use_mcp_tool`` Letta tool and attach to all agents.

        Follows the idempotent pattern from ``SPDSAgent._ensure_assessment_tool``.
        """
        from . import config as spds_config

        if not spds_config.get_mcp_tier2_enabled():
            logger.info("Tier 2 MCP tools disabled; skipping use_mcp_tool registration")
            return

        # Only register if there are tier-2 entries
        tier2_entries = [e for e in self._config_entries if e.tier == 2]
        if not tier2_entries:
            logger.info("No Tier 2 servers configured; skipping use_mcp_tool")
            return

        from .tools import build_use_mcp_tool_kwargs

        tool_name = "use_mcp_tool"

        # Check if already registered
        try:
            existing = letta_call(
                "tools.list",
                self._client.tools.list,
            )
            for tool in (existing or []):
                if getattr(tool, "name", None) == tool_name:
                    self._use_mcp_tool_id = tool.id
                    logger.info("use_mcp_tool already registered (id=%s)", tool.id)
                    break
        except Exception:
            pass

        # Create if not found
        if not self._use_mcp_tool_id:
            try:
                create_fn = self._client.tools.create_from_function
                kwargs = build_use_mcp_tool_kwargs(create_fn)
                tool = letta_call(
                    "tools.create_from_function(use_mcp_tool)",
                    create_fn,
                    **kwargs,
                )
                self._use_mcp_tool_id = tool.id
                logger.info("Registered use_mcp_tool (id=%s)", tool.id)
            except Exception as exc:
                # May already exist (409 conflict)
                logger.warning("Failed to create use_mcp_tool: %s", exc)
                return

        # Attach to all agents
        if self._use_mcp_tool_id:
            for agent_id in agent_ids:
                try:
                    letta_call(
                        f"agents.tools.attach(use_mcp_tool→{agent_id})",
                        self._client.agents.tools.attach,
                        self._use_mcp_tool_id,
                        agent_id=agent_id,
                    )
                except Exception as exc:
                    logger.warning("Failed to attach use_mcp_tool to agent %s: %s", agent_id, exc)

    # ------------------------------------------------------------------
    # Tool fulfillment (on-demand execution)
    # ------------------------------------------------------------------

    def fulfill_and_execute(
        self, agent_id: str, server_name: str, tool_name: str, args: Dict[str, Any]
    ) -> str:
        """Attach an MCP tool to *agent_id* (if needed) and execute it.

        Returns the tool execution result as a string.
        """
        cache_key = f"{server_name}/{tool_name}"
        tool_id = self._attached_tools.get(cache_key)

        if not tool_id:
            logger.error("Unknown tool '%s' from server '%s'", tool_name, server_name)
            return f"Error: Unknown tool '{tool_name}' on server '{server_name}'"

        # Ensure tool is attached to agent
        try:
            letta_call(
                f"agents.tools.attach({tool_name}→{agent_id})",
                self._client.agents.tools.attach,
                tool_id,
                agent_id=agent_id,
            )
        except Exception as exc:
            # May already be attached — non-fatal
            logger.debug("Tool attach note for %s→%s: %s", tool_name, agent_id, exc)

        # Execute
        try:
            result = letta_call(
                f"agents.tools.run({tool_name})",
                self._client.agents.tools.run,
                tool_name,
                agent_id=agent_id,
                args=args,
            )
            # Extract string from result
            result_str = getattr(result, "tool_return", None)
            if result_str is None:
                result_str = str(result)
            logger.info("MCP tool %s/%s executed successfully", server_name, tool_name)
            return result_str
        except Exception as exc:
            logger.error("MCP tool execution failed for %s/%s: %s", server_name, tool_name, exc)
            return f"Error executing {server_name}/{tool_name}: {exc}"

    # ------------------------------------------------------------------
    # Utilities
    # ------------------------------------------------------------------

    def refresh_catalog(self) -> None:
        """Re-scan all registered servers and rebuild the catalog."""
        self.build_catalog()
        if self._ecosystem_block_id:
            content = self.generate_ecosystem_content()
            try:
                letta_call(
                    "blocks.update(tool_ecosystem)",
                    self._client.blocks.update,
                    self._ecosystem_block_id,
                    value=content,
                )
            except Exception as exc:
                logger.warning("Failed to refresh ecosystem block: %s", exc)

    def get_catalog_summary(self) -> str:
        """Return a human-readable summary of all registered MCP servers and tools."""
        if not self._catalog:
            return "No MCP servers registered."

        lines = ["MCP Tool Catalog:"]
        for server_name, tools in self._catalog.items():
            entry = next((e for e in self._config_entries if e.name == server_name), None)
            tier = f"Tier {entry.tier}" if entry else "Unknown"
            lines.append(f"\n  [{server_name}] ({tier})")
            if entry and entry.description:
                lines.append(f"    {entry.description}")
            if tools:
                for t in tools:
                    lines.append(f"    - {t['name']}: {t['description']}")
            else:
                lines.append("    (no tools discovered)")

        return "\n".join(lines)
