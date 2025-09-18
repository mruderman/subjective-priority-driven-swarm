# TODO - SWARMS Project

This document tracks the progress and future direction of the SWARMS project.
Last updated: 2025-09-18

## Phase 1: Live Testing — COMPLETED

### Completed Tasks ✓
- [x] Create missing `__init__.py` in `spds/`
- [x] Environment variable support for API keys
- [x] Fix tool creation method (`create_from_function`)
- [x] Implement subjective assessment logic in `tools.py`
- [x] Clean up backup files (~)
- [x] Complete `README.md`
- [x] Provide example swarm configs (`creative_swarm.json`, etc.)
- [x] Connect to Letta server and validate
- [x] Test default agent creation with `AGENT_PROFILES`
- [x] Update model endpoints for supported providers
- [x] Create diverse model swarms
- [x] Live conversations with priority-based turn-taking
- [x] Validate assessment logic with real agents
- [x] Fix tool call use with default Letta tools
- [x] Verify across providers (Anthropic, OpenAI, Together models, etc.)

## Phase 2: Logging & Observability — COMPLETED

Implemented centralized, configurable logging in `spds/config.py` and added performance/timing instrumentation across `spds/swarm_manager.py`.

### Completed Tasks ✓
- [x] Python logging module with env-configurable level (`LOG_LEVEL`)
- [x] Console and rotating file handlers (`logs/spds.log`)
- [x] Structured formats with timestamps/module/line
- [x] Agent identification in log messages (names in messages)
- [x] Performance timing for agent creation, assessments, LLM responses
- [x] Slow-operation warnings (e.g., >5s)
- [x] `logs/` ignored via `.gitignore`

## Next Up (High Priority) — Optimized Order

1) Environment variable alignment (quick win, unblocks docs/UX)
   - [ ] Unify `LETTA_PASSWORD` and `LETTA_SERVER_PASSWORD` (support both; prefer `LETTA_PASSWORD`)
   - [ ] Update docs (`README.md`, `.env.example`) and add code shim

2) Agent profile schema validation (stability before features)
   - [ ] Define Pydantic model for `AGENT_PROFILES`
   - [ ] Validate on startup with clear error messages
   - [ ] Tests for invalid/missing fields

3) Error/timeout handling consolidation (foundation for reliability)
   - [ ] Central wrapper for Letta calls (timeouts, retry/backoff, logging)
   - [ ] Apply across agents/secretary paths
   - [ ] Unit tests for transient failures and timeouts

4) Conversation persistence and resume (build on #3)
   - [ ] Add session IDs; persist conversation state (JSON/DB)
   - [ ] CLI/Web: list sessions and resume
   - [ ] Export/restore secretary state (minutes, actions, decisions)

## Medium Priority — After High Priority

- [ ] Web UI enhancements (depends on persistence)
  - [ ] Session list/resume and exports from UI
  - [ ] Configure conversation modes and secretary options
  - [ ] Minor UX polish; loading/error states

- [ ] Multi‑modal support
  - [ ] Image/document inputs; display and routing

- [ ] Integrations
  - [ ] MCP servers / Composio-based tools

## Low Priority

- [ ] Documentation improvements
  - [ ] Public API reference and examples
  - [ ] Architecture diagrams and SPDS overview
  - [ ] Document logging/env vars (`LOG_LEVEL`, `SPDS_INIT_LOGGING`)

- [x] Lint/format tooling
  - [x] flake8, black, pylint, pre‑commit

## Future Enhancements

- [ ] Custom assessment dimensions
- [ ] Agent learning from outcomes
- [ ] Participation visualization/analytics
- [ ] Dynamic agent creation based on needs
- [ ] Collaborative subtasking workflows

## Known Issues / Gaps

- [ ] No validation for agent profile JSON schema
- [ ] No support for resuming interrupted conversations
- [ ] Minor env var naming mismatch in docs vs code (`LETTA_PASSWORD` vs `LETTA_SERVER_PASSWORD`)

Resolved from prior list:
- [x] Assessment via agent message API and tool usage (implemented in `spds/spds_agent.py`)
- [x] Handling for agent creation failures (logged and continued)
