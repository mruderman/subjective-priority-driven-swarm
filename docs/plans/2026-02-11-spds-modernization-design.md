# SPDS Modernization Design

**Date:** 2026-02-11
**Status:** Approved
**Approach:** Incremental migration (6 phases)

## Context

SPDS (Subjective Priority-Driven Swarm) is a multi-agent collaboration framework built on the Letta platform. After a period of dormancy, the project is being modernized to align with Letta's current architecture and expand agent capabilities beyond conversation into action.

### Key Research Findings

1. **Letta Groups API is deprecated** in the v1.0 SDK. Letta now recommends client-side orchestration with cross-agent messaging tools — which is exactly what SPDS's SwarmManager already does.

2. **Conversations API (January 2026)** enables agents to run multiple parallel conversation threads while sharing memory blocks. Replaces the need for local session persistence.

3. **Native multi-agent tools** exist for cross-agent communication:
   - `send_message_to_agent_async` (fire-and-forget)
   - `send_message_to_agent_and_wait_for_reply` (blocking)
   - `send_message_to_agents_matching_all_tags` (broadcast)

4. **Letta Code** is a TypeScript CLI coding agent, not a framework for building swarms. Rebuilding on Letta Code is not viable. The Python SDK (`letta-client`) remains the correct foundation.

5. **MCP tool bloat** is a real problem when attaching many servers to agents. The mcp-launchpad pattern (semantic search + on-demand execution) solves this.

### Design Principles

- **Modernize, don't rewrite.** The core architecture (client-side orchestration) is validated by Letta's own direction.
- **Agents should DO things, not just talk.** Tool access is a first-class concern.
- **Context window discipline.** Only always-needed tools stay loaded; everything else is discoverable on-demand.
- **Continuity over ephemerality.** Prefer persistent agents, persistent conversations, persistent memory.

---

## Architecture: What Changes vs What Stays

### Stays (Core SPDS Identity)

- **SwarmManager** as client-side orchestrator — this IS the Letta-recommended pattern
- **SPDSAgent** wrapper with subjective priority scoring via `perform_subjective_assessment` tool
- **Four conversation modes:** Hybrid, All-Speak, Sequential, Pure Priority
- **Secretary role concept** (implementation evolves)
- **Agent autonomy philosophy** and memory management principles
- **CLI entry point** (`main.py`) and **Web GUI** (`swarms-web/`)
- **Resilience layer** (`letta_api.py` with retry/backoff)

### Changes

- **Server connection:** New Oregon VPS Tailscale IP, pinned `letta-client` version
- **Session management:** Replaced by Letta's Conversations API. Each swarm session becomes a conversation with shared memory blocks. Local JSON persistence deleted.
- **Agent-to-agent comms:** Agents get `send_message_to_agent_async` for autonomous side conversations. Priority scoring still governs "taking the floor" in group discussion.
- **Tool ecosystem:** Tiered MCP strategy replaces placeholder integrations. Personal servers attached directly; everything else via launchpad-style discovery.
- **Integration placeholders:** `composio.py` and `mcp.py` deleted entirely.

### Net Effect

SwarmManager gets *thinner* (delegates session state to Letta, delegates tool discovery to launchpad). Agents get *richer* (can talk to each other, discover and use tools on-demand).

---

## Phase 1: Server Connection + Letta-Client Update ✅ COMPLETE

**Scope:** Small | **Risk:** Low | **Completed:** 2026-02-11

### Tasks

1. **Pin `letta-client` version** — Pinned `>=0.1.0,<0.2.0` in both `requirements.txt` and `swarms-web/requirements.txt` (installed version: 0.1.324).

2. **Update server connection config** — Default `LETTA_BASE_URL` changed to `http://100.65.223.46:8283` in `spds/config.py` and `.env.example`.

3. **Fix deprecated `datetime.utcnow()`** — 27 occurrences replaced with `datetime.now(timezone.utc)` across 8 files.

4. **Fix cascading `datetime.now()` naivety** — The `utcnow()` migration surfaced 5 additional bare `datetime.now()` calls in `meeting_templates.py` that produced naive datetimes mixed with the now-aware timestamps. Fixed these and updated 4 test files where fixtures created naive datetimes that conflicted with the aware timestamps:
   - `spds/meeting_templates.py` — 5 `datetime.now()` → `datetime.now(timezone.utc)`
   - `tests/unit/test_meeting_templates.py` — `FixedDateTime.now()` mock and fixture start time made tz-aware
   - `tests/unit/test_export_manager.py` — fixture start time made tz-aware
   - `tests/unit/test_cli_sessions.py` — fixture datetimes made tz-aware

5. **Clean up `session_store.py` self-import pattern** — Replaced try/except self-import with direct `globals().get()` check.

### Results

- 577 tests passing, 86% coverage (unchanged)
- Smoke test: connected to Oregon server, found 29 agents
- Zero `datetime.utcnow()` or naive/aware mixing issues remain

---

## Phase 2: Conversations API Integration

**Scope:** Large | **Risk:** Medium-high

This is the biggest architectural shift. Currently SPDS manages session state locally via JSON files. The Conversations API moves that state server-side.

### How Conversations API Works

- Each agent can participate in multiple conversations simultaneously
- Each conversation has its own message history / context window
- All conversations share the agent's memory blocks (persona, human, custom)
- This is exactly what a swarm session needs: agents remember across sessions, but each discussion has its own thread

### Tasks

1. **SwarmManager creates a conversation per session.** When a swarm session starts, create a new conversation on each participating agent. Messages go to that conversation.

2. **Delete local session persistence layer:**
   - `session_store.py` (JSON file management)
   - `session_context.py` (thread-local session ID)
   - `session_tracking.py` (event logging)

   These become unnecessary because Letta persists everything server-side.

3. **Session resume = conversation resume.** Instead of deserializing JSON from disk, resuming a session means continuing the existing conversation on each agent. Agents already have full history and memory.

4. **Shared memory block for group context.** Create a shared memory block (label `"swarm_context"`) that all agents in the session can read/write. Replaces passing topic/metadata through function arguments. Agents naturally know what the group is working on.

5. **Secretary gets its own conversation.** The secretary agent observes via a separate conversation that receives copies of messages, keeping its context clean.

### What We Preserve

The `ExportManager` stays — users still want to export transcripts/minutes locally. It reads from the Conversations API instead of local JSON.

### Risk Mitigation

~40% of existing tests will need rewrites since session management is deeply embedded. Plan for this. Run old and new tests in parallel during migration.

### Success Criteria

- Swarm sessions persist server-side and survive client restarts
- Session resume works by continuing existing conversations
- Shared `swarm_context` block is readable by all participants
- ExportManager produces identical output from Conversations API data

---

## Phase 3: Cross-Agent Messaging Tools

**Scope:** Medium | **Risk:** Low

Agents stop being passive participants and become autonomous collaborators.

### Current State

Agents only speak when SwarmManager explicitly prompts them. The manager controls all message routing. Agents never talk to each other directly.

### Design Decisions

1. **One messaging tool per agent.** Letta docs warn against attaching both async and sync tools. We use `send_message_to_agent_async` (non-blocking) since it fits the swarm's autonomous philosophy.

2. **Priority scoring still governs "taking the floor."** The async tool is for side conversations between agents. Addressing the whole swarm still requires passing the priority assessment. This prevents chaos.

3. **Tag-based agent discovery.** Agents in a swarm session get tagged (e.g., `swarm:session-123`). Enables broadcasts via `send_message_to_agents_matching_all_tags` without hardcoding agent IDs.

4. **SwarmManager awareness.** The manager monitors side conversations (via Conversations API) and can surface important exchanges to the group — a facilitator who notices relevant sidebars.

### What This Enables

- An architect agent asks a developer to clarify a technical constraint mid-discussion
- A researcher shares a finding with the PM without interrupting group flow
- The swarm feels organic rather than turn-based

### Success Criteria

- Agents can send async messages to specific agents or broadcast by tag
- Side conversations are visible to SwarmManager
- Priority scoring is unaffected (still governs group-level contributions)

---

## Phase 4: MCP Launchpad Tool Discovery

**Scope:** Medium-large | **Risk:** Medium

This is where agents go from "can talk" to "can do."

### Tier 1 — Always-On (Attached Directly to Agents)

Permanently in each agent's tool list. Small footprint, high frequency.

| Server | Scope | Purpose |
|--------|-------|---------|
| Personal Gmail MCP | Per-agent | Agent's own email |
| Personal self-agency MCP | Per-agent | Agent self-management |
| Sequential thinking MCP | Universal | Reasoning aid |

### Tier 2 — On-Demand Discovery (Launchpad Pattern)

A custom Letta tool wrapping the mcp-launchpad pattern:

```
discover_and_use_tool(query: str, args: dict) -> str
```

When an agent needs a capability it doesn't have, it calls this tool with a natural language query. Under the hood:

1. Semantic search across all configured MCP servers' tool registries
2. Returns top matches with descriptions for the agent to choose from
3. Agent confirms and executes the chosen tool with arguments

### Shared Memory: Tool Ecosystem Awareness

A shared memory block (label `"tool_ecosystem"`) describes the available MCP server categories and discoverable capabilities. All agents can read this block so they know *what to ask for* — "I know there are GitHub tools available, let me search for one" rather than guessing blindly.

This block auto-updates when servers are added/removed from `mcp-servers.json`.

### Implementation Options

- Wrap `mcpl` CLI calls from within the server-side Letta tool, or
- Build a lightweight Python equivalent using the same index/search pattern

### Configuration

A `mcp-servers.json` at the project level defines all Tier 2 servers. Adding a new MCP server = adding one entry. No agent reconfiguration needed.

### Success Criteria

- Agents can discover tools by natural language query
- Tool execution works end-to-end (search -> inspect -> call -> result)
- Adding a new MCP server requires only a config file change
- `tool_ecosystem` shared memory block stays current

---

## Phase 5: Cleanup and Slimming ✅ Complete

**Scope:** Medium | **Risk:** Low | **Status:** Done (Feb 2026)

With Phases 1-4 complete, trimmed dead weight.

### Deleted Entirely ✅

| File/Directory | Reason | Status |
|---------------|--------|--------|
| `spds/integrations/` (composio.py, mcp.py, registry.py) | Replaced by launchpad | ✅ Deleted |
| `spds/session_store.py` | Replaced by Conversations API | ✅ Deleted |
| `spds/session_context.py` | Thread-local session ID no longer needed | ✅ Deleted |
| `spds/session_tracking.py` | No-op logging stubs, 23 call sites removed | ✅ Deleted |
| `spds/meeting_templates.py` | Static templates replaced by AI-generated minutes | ✅ Deleted |

### Web App Migration ✅

- Replaced `_StubSessionStore` in `swarms-web/app.py` with `_session_metadata` dict + `ConversationManager`
- Added `list_all_sessions`, `save_web_session_config`, `get_web_session_config` to `ConversationManager`

### Test Suite Consolidation ✅

- Consolidated 12 SwarmManager test files into 4 focused files (~4 duplicates removed)
  - `test_swarm_manager_init.py` (25 tests) — init, roles, config
  - `test_swarm_manager_modes.py` (24 tests) — conversation modes
  - `test_swarm_manager_utils.py` (44 tests) — extraction, memory, export
  - `test_swarm_manager_conversations.py` (15 tests) — Conversations API

### Net Result

595 tests passing, 85% coverage. Removed ~200 lines of dead code stubs and 10 redundant test files.

---

## Testing Strategy

### Unit Tests (Fast, No Server)

- Priority scoring logic (pure Python, fully mockable)
- Conversation mode selection and turn logic
- Export formatting (markdown, transcript, action items)
- MCP launchpad query/result parsing
- Shared memory block serialization/deserialization

### Integration Tests (`@pytest.mark.integration`, Require Letta Server)

- Conversations API: create, send, retrieve, resume
- Cross-agent messaging: async delivery and receipt
- Shared memory blocks: read/write across agents
- MCP launchpad: semantic search, inspection, execution
- Secretary observation: conversation thread receives copies

### End-to-End Tests (Full Swarm Scenario)

- 2-3 agents in Hybrid mode, priority scoring determines speaker order
- Agent autonomously discovers and uses a tool via launchpad
- Session start -> stop -> resume -> verify continuity
- Export completed session in all formats

### Infrastructure

- `conftest.py` fixture connecting to Oregon VPS (or local test server)
- Default `pytest` = unit tests only (fast CI)
- `pytest --integration` includes server tests
- **Coverage target:** 85%+ on the slimmed codebase

---

## Phase Summary

| Phase | Focus | Scope | Risk | Dependencies | Status |
|-------|-------|-------|------|-------------|--------|
| 1 | Server connection + letta-client | Small | Low | None | ✅ Complete |
| 2 | Conversations API | Large | Medium-high | Phase 1 ✅ | ✅ Complete |
| 3 | Cross-agent messaging | Medium | Low | Phase 2 ✅ | ✅ Complete |
| 4 | MCP Launchpad integration | Medium-large | Medium | Phase 1 ✅ | ✅ Complete |
| 5 | Cleanup and slimming | Medium | Low | Phases 2-4 ✅ | ✅ Complete |

### Parallel Execution Plan

With Phase 1 complete, the dependency graph allows two independent work streams:

```
Phase 1 ✅
├── Phase 2 (Conversations API)  ──→  Phase 3 (Cross-Agent Messaging)  ──┐
│                                                                         ├──→ Phase 5 (Cleanup)
└── Phase 4 (MCP Launchpad)  ─────────────────────────────────────────────┘
```

**Terminal Team A:** Phase 2 → Phase 3
- Heavy SwarmManager/session refactoring, ~40% test rewrites
- Touches: `swarm_manager.py`, `session_store.py`, `session_context.py`, `session_tracking.py`, `secretary_agent.py`, `export_manager.py`, and many test files
- Phase 3 depends on Phase 2's Conversations API for monitoring side conversations

**Terminal Team B:** Phase 4
- New code, largely additive — builds the `discover_and_use_tool` Letta tool and `mcp-servers.json` config
- Touches: new files for launchpad tool, `tool_ecosystem` shared memory block, agent tool attachment
- No overlap with Team A's files

**Conflict zones to watch:**
- `swarm_manager.py` — Team A rewrites session management; Team B may need to attach launchpad tools during swarm setup. Coordinate the agent initialization path.
- `spds_agent.py` — Team A removes history passing; Team B adds tool attachment. Merges should be straightforward if each team works in distinct methods.
- Shared memory blocks — Team A introduces `swarm_context`; Team B introduces `tool_ecosystem`. Both are additive, no conflict.

**Phase 5** waits for both teams to finish, then sweeps.

---

## References

- [Letta Conversations API](https://docs.letta.com/guides/agents/conversations/)
- [Letta Multi-Agent Systems](https://docs.letta.com/guides/agents/multi-agent/)
- [Letta Python SDK Reference](https://github.com/letta-ai/letta-python/blob/main/reference.md)
- [MCP Launchpad](https://github.com/kenneth-liao/mcp-launchpad)
- [Letta Groups (deprecated)](https://docs.letta.com/guides/agents/groups/)
