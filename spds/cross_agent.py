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

# Built-in multi-agent tool name
MULTI_AGENT_TOOL = "send_message_to_agent_async"


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


def _find_multi_agent_tool(client: "Letta") -> Optional[str]:
    """Return the tool ID for ``send_message_to_agent_async`` if it exists.

    Letta registers multi-agent tools globally.  We search the tool list
    for the built-in async messaging tool.
    """
    try:
        all_tools = letta_call("tools.list", client.tools.list)
        for tool in all_tools:
            if getattr(tool, "name", None) == MULTI_AGENT_TOOL:
                return tool.id
    except Exception as e:
        logger.warning("Failed to search for multi-agent tool: %s", e)
    return None


def attach_multi_agent_tools(
    client: "Letta",
    agent_ids: List[str],
) -> bool:
    """Attach the async messaging tool to each agent.

    Returns True if the tool was successfully found and attached to at
    least one agent, False otherwise.
    """
    tool_id = _find_multi_agent_tool(client)
    if not tool_id:
        logger.info(
            "Multi-agent tool '%s' not found on server; "
            "agents will not have cross-agent messaging. "
            "Ensure include_multi_agent_tools=True when creating agents.",
            MULTI_AGENT_TOOL,
        )
        return False

    attached_count = 0
    for agent_id in agent_ids:
        try:
            # Check if tool is already attached
            agent_state = letta_call(
                "agents.retrieve",
                client.agents.retrieve,
                agent_id=agent_id,
            )
            agent_tool_names = [
                getattr(t, "name", None)
                for t in (getattr(agent_state, "tools", None) or [])
            ]
            if MULTI_AGENT_TOOL in agent_tool_names:
                logger.debug(
                    "Agent %s already has %s", agent_id, MULTI_AGENT_TOOL
                )
                attached_count += 1
                continue

            letta_call(
                "agents.tools.attach",
                client.agents.tools.attach,
                agent_id=agent_id,
                tool_id=tool_id,
            )
            attached_count += 1
            logger.debug("Attached %s to agent %s", MULTI_AGENT_TOOL, agent_id)
        except Exception as e:
            logger.warning(
                "Failed to attach multi-agent tool to agent %s: %s",
                agent_id,
                e,
            )

    logger.info(
        "Multi-agent tool attached to %d/%d agents", attached_count, len(agent_ids)
    )
    return attached_count > 0


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

    # 2. Attach multi-agent tool
    multi_agent_ok = attach_multi_agent_tools(client, agent_ids)

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
        "multi_agent_enabled": multi_agent_ok,
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
