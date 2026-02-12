# spds/cross_agent.py

"""Cross-agent messaging setup for SPDS swarm sessions.

Manages:
- Session tagging: agents in a swarm session get tagged for discovery
- Multi-agent tools: attach ``send_message_to_agent_async`` to agents
- Shared memory blocks: ``swarm_context`` for group state awareness
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from .letta_api import letta_call

if TYPE_CHECKING:
    from letta_client import Letta

logger = logging.getLogger(__name__)

# Tag prefix used for swarm session membership
SESSION_TAG_PREFIX = "spds:session-"

# Built-in multi-agent tool names
MULTI_AGENT_TOOL = "send_message_to_agent_async"
BROADCAST_TOOL = "send_message_to_agents_matching_all_tags"
MULTI_AGENT_TOOLS = {MULTI_AGENT_TOOL, BROADCAST_TOOL}


def make_session_tag(session_id: str) -> str:
    """Return the tag string for a swarm session."""
    return f"{SESSION_TAG_PREFIX}{session_id}"


# ---------------------------------------------------------------------------
# Tagging
# ---------------------------------------------------------------------------


def tag_agents_for_session(
    client: "Letta",
    agent_ids: List[str],
    session_id: str,
) -> str:
    """Add a session tag to each agent so they can discover each other.

    Returns the session tag string.
    """
    tag = make_session_tag(session_id)
    for agent_id in agent_ids:
        try:
            current = letta_call(
                "agents.retrieve",
                client.agents.retrieve,
                agent_id=agent_id,
            )
            existing_tags = list(getattr(current, "tags", None) or [])
            if tag not in existing_tags:
                existing_tags.append(tag)
                letta_call(
                    "agents.update",
                    client.agents.update,
                    agent_id=agent_id,
                    tags=existing_tags,
                )
                logger.debug("Tagged agent %s with %s", agent_id, tag)
        except Exception as e:
            logger.warning("Failed to tag agent %s: %s", agent_id, e)
    return tag


def remove_session_tags(
    client: "Letta",
    agent_ids: List[str],
    session_id: str,
) -> None:
    """Remove the session tag from each agent after the session ends."""
    tag = make_session_tag(session_id)
    for agent_id in agent_ids:
        try:
            current = letta_call(
                "agents.retrieve",
                client.agents.retrieve,
                agent_id=agent_id,
            )
            existing_tags = list(getattr(current, "tags", None) or [])
            if tag in existing_tags:
                existing_tags.remove(tag)
                letta_call(
                    "agents.update",
                    client.agents.update,
                    agent_id=agent_id,
                    tags=existing_tags,
                )
                logger.debug("Removed tag %s from agent %s", tag, agent_id)
        except Exception as e:
            logger.warning("Failed to remove tag from agent %s: %s", agent_id, e)


# ---------------------------------------------------------------------------
# Multi-agent tool attachment
# ---------------------------------------------------------------------------


def _find_multi_agent_tools(client: "Letta") -> Dict[str, str]:
    """Return a mapping of tool name → tool ID for all known multi-agent tools.

    Scans ``client.tools.list()`` once and checks each tool name against
    :data:`MULTI_AGENT_TOOLS`.  Only tools that exist on the server are
    included in the result.
    """
    found: Dict[str, str] = {}
    try:
        all_tools = letta_call("tools.list", client.tools.list)
        for tool in all_tools:
            name = getattr(tool, "name", None)
            if name in MULTI_AGENT_TOOLS:
                found[name] = tool.id
    except Exception as e:
        logger.warning("Failed to search for multi-agent tools: %s", e)
    return found


def _find_multi_agent_tool(client: "Letta") -> Optional[str]:
    """Return the tool ID for ``send_message_to_agent_async`` if it exists.

    Thin wrapper around :func:`_find_multi_agent_tools` for backward
    compatibility.
    """
    return _find_multi_agent_tools(client).get(MULTI_AGENT_TOOL)


def attach_multi_agent_tools(
    client: "Letta",
    agent_ids: List[str],
) -> Dict[str, bool]:
    """Attach available multi-agent messaging tools to each agent.

    Discovers both ``send_message_to_agent_async`` and
    ``send_message_to_agents_matching_all_tags`` and attaches whichever
    are available on the server.

    Returns a dict::

        {"async_enabled": bool, "broadcast_enabled": bool}

    Each flag is True when the corresponding tool was found and attached
    to at least one agent.
    """
    tool_map = _find_multi_agent_tools(client)
    result = {"async_enabled": False, "broadcast_enabled": False}

    if not tool_map:
        logger.info(
            "No multi-agent tools found on server; "
            "agents will not have cross-agent messaging. "
            "Ensure include_multi_agent_tools=True when creating agents.",
        )
        return result

    async_count = 0
    broadcast_count = 0

    for agent_id in agent_ids:
        try:
            agent_state = letta_call(
                "agents.retrieve",
                client.agents.retrieve,
                agent_id=agent_id,
            )
            agent_tool_names = [
                getattr(t, "name", None)
                for t in (getattr(agent_state, "tools", None) or [])
            ]

            for tool_name, tool_id in tool_map.items():
                if tool_name in agent_tool_names:
                    logger.debug(
                        "Agent %s already has %s", agent_id, tool_name
                    )
                    if tool_name == MULTI_AGENT_TOOL:
                        async_count += 1
                    else:
                        broadcast_count += 1
                    continue

                letta_call(
                    "agents.tools.attach",
                    client.agents.tools.attach,
                    agent_id=agent_id,
                    tool_id=tool_id,
                )
                if tool_name == MULTI_AGENT_TOOL:
                    async_count += 1
                else:
                    broadcast_count += 1
                logger.debug("Attached %s to agent %s", tool_name, agent_id)

        except Exception as e:
            logger.warning(
                "Failed to attach multi-agent tools to agent %s: %s",
                agent_id,
                e,
            )

    logger.info(
        "Multi-agent tools attached — async: %d/%d, broadcast: %d/%d agents",
        async_count, len(agent_ids), broadcast_count, len(agent_ids),
    )
    result["async_enabled"] = async_count > 0
    result["broadcast_enabled"] = broadcast_count > 0
    return result


# ---------------------------------------------------------------------------
# Shared memory blocks
# ---------------------------------------------------------------------------


def create_swarm_context_block(
    client: "Letta",
    topic: str,
    participant_names: List[str],
    session_id: str,
    extra: Optional[Dict[str, Any]] = None,
) -> Optional[str]:
    """Create a shared ``swarm_context`` memory block and return its ID.

    The block provides all participants with awareness of:
    - Current discussion topic
    - Session ID for cross-agent messaging
    - Who is in the swarm
    - Any extra metadata (e.g. conversation mode)
    """
    participants_str = ", ".join(participant_names)
    session_tag = make_session_tag(session_id)

    value = (
        f"Swarm session: {session_id}\n"
        f"Session tag: {session_tag}\n"
        f"Topic: {topic}\n"
        f"Participants: {participants_str}\n"
    )
    if extra:
        for k, v in extra.items():
            value += f"{k}: {v}\n"

    try:
        block = letta_call(
            "blocks.create",
            client.blocks.create,
            label="swarm_context",
            value=value,
            description=(
                "Shared group context for this swarm session. "
                "Contains the discussion topic, participant list, "
                "and session tag for cross-agent messaging."
            ),
        )
        logger.info("Created swarm_context block: %s", block.id)
        return block.id
    except Exception as e:
        logger.warning("Failed to create swarm_context block: %s", e)
        return None


def attach_block_to_agents(
    client: "Letta",
    block_id: str,
    agent_ids: List[str],
) -> int:
    """Attach a shared memory block to multiple agents.

    Returns the number of agents that were successfully updated.
    """
    attached = 0
    for agent_id in agent_ids:
        try:
            current = letta_call(
                "agents.retrieve",
                client.agents.retrieve,
                agent_id=agent_id,
            )
            existing_block_ids = [
                b.id for b in (getattr(current, "memory", None) or {}).get("blocks", [])
                if hasattr(b, "id")
            ]
            # The blocks API uses agent-level block attachment
            if block_id not in existing_block_ids:
                letta_call(
                    "agents.blocks.attach",
                    client.agents.blocks.attach,
                    agent_id=agent_id,
                    block_id=block_id,
                )
            attached += 1
            logger.debug("Attached block %s to agent %s", block_id, agent_id)
        except Exception as e:
            logger.warning(
                "Failed to attach block %s to agent %s: %s", block_id, agent_id, e
            )
    return attached


def update_swarm_context(
    client: "Letta",
    block_id: str,
    updates: Dict[str, str],
) -> bool:
    """Update the swarm_context block with new key-value pairs.

    Reads the current block value, appends or replaces lines matching
    the update keys, and writes back.
    """
    try:
        block = letta_call(
            "blocks.retrieve",
            client.blocks.retrieve,
            block_id=block_id,
        )
        lines = (block.value or "").splitlines()

        # Build a dict of existing key: line_index
        existing = {}
        for i, line in enumerate(lines):
            if ": " in line:
                key = line.split(": ", 1)[0]
                existing[key] = i

        for key, value in updates.items():
            new_line = f"{key}: {value}"
            if key in existing:
                lines[existing[key]] = new_line
            else:
                lines.append(new_line)

        new_value = "\n".join(lines)
        letta_call(
            "blocks.update",
            client.blocks.update,
            block_id=block_id,
            value=new_value,
        )
        return True
    except Exception as e:
        logger.warning("Failed to update swarm_context block: %s", e)
        return False


# ---------------------------------------------------------------------------
# Side-conversation detection
# ---------------------------------------------------------------------------


def detect_side_conversations(
    response: Any,
    sender_name: str,
) -> List[Dict[str, Any]]:
    """Scan a Letta response for cross-agent messaging tool calls.

    Returns a list of dicts describing each detected side conversation::

        {
            "type": "async" | "broadcast",
            "sender": sender_name,
            "tool_name": str,
            "recipient_id": str | None,   # async only
            "tags": list | None,          # broadcast only
            "message_content": str,
        }

    Returns ``[]`` if *response* is None or contains no side-conversation
    tool calls.
    """
    if response is None:
        return []

    import json

    detected: List[Dict[str, Any]] = []
    messages = getattr(response, "messages", None) or []

    for msg in messages:
        if getattr(msg, "message_type", None) != "tool_call_message":
            continue

        tool_call = getattr(msg, "tool_call", None)
        if tool_call is None:
            continue

        tool_name = getattr(tool_call, "name", None)
        if tool_name not in MULTI_AGENT_TOOLS:
            continue

        # Parse arguments defensively
        raw_args = getattr(tool_call, "arguments", None) or "{}"
        try:
            args = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
        except (json.JSONDecodeError, TypeError):
            logger.warning(
                "Malformed tool call arguments from %s for %s: %s",
                sender_name,
                tool_name,
                raw_args,
            )
            continue

        entry: Dict[str, Any] = {
            "sender": sender_name,
            "tool_name": tool_name,
        }

        if tool_name == MULTI_AGENT_TOOL:
            entry["type"] = "async"
            entry["recipient_id"] = args.get("agent_id") or args.get("recipient_agent_id")
            entry["tags"] = None
        else:
            entry["type"] = "broadcast"
            entry["recipient_id"] = None
            entry["tags"] = args.get("tags")

        entry["message_content"] = args.get("message", "")
        detected.append(entry)

    return detected


# ---------------------------------------------------------------------------
# High-level setup / teardown
# ---------------------------------------------------------------------------


def setup_cross_agent_messaging(
    client: "Letta",
    agent_ids: List[str],
    session_id: str,
    topic: str = "",
    participant_names: Optional[List[str]] = None,
    conversation_mode: str = "hybrid",
) -> Dict[str, Any]:
    """One-call setup for cross-agent messaging in a swarm session.

    Performs:
    1. Tags agents with the session tag
    2. Attaches ``send_message_to_agent_async`` to each agent
    3. Creates a shared ``swarm_context`` memory block

    Returns a dict with setup results::

        {
            "session_tag": "spds:session-...",
            "multi_agent_enabled": True/False,
            "swarm_context_block_id": "block-..." or None,
        }
    """
    names = participant_names or [f"agent-{i}" for i in range(len(agent_ids))]

    # 1. Tag agents
    session_tag = tag_agents_for_session(client, agent_ids, session_id)

    # 2. Attach multi-agent tools
    tool_status = attach_multi_agent_tools(client, agent_ids)

    # 3. Create shared context block
    block_id = create_swarm_context_block(
        client,
        topic=topic,
        participant_names=names,
        session_id=session_id,
        extra={"Conversation mode": conversation_mode},
    )

    # 4. Attach shared block to all agents
    if block_id:
        attach_block_to_agents(client, block_id, agent_ids)

    return {
        "session_tag": session_tag,
        "multi_agent_enabled": tool_status.get("async_enabled", False),
        "broadcast_enabled": tool_status.get("broadcast_enabled", False),
        "swarm_context_block_id": block_id,
    }


def teardown_cross_agent_messaging(
    client: "Letta",
    agent_ids: List[str],
    session_id: str,
) -> None:
    """Clean up after a swarm session ends.

    Removes session tags from agents. Shared memory blocks are left
    in place for historical reference.
    """
    remove_session_tags(client, agent_ids, session_id)
