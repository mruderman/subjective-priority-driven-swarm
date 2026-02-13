# Pre-Testing Repo Cleanup Design

**Date:** 2026-02-12
**Goal:** Clean up repo structure and documentation before user testing. Both dev hygiene and user-facing polish.
**Approach:** Parallel sweep with project-curator (structural) and documentation-maintainer (content) subagents.

## Workstream 1: Structural Cleanup (project-curator)

### Delete from git tracking + add to .gitignore
- `.roo/` (352K) - Roo/Cline configs
- `.roomodes` (25K) - Roo mode definitions
- `.hive-mind/` (1.3M) - Hive-mind SQLite DBs
- `.kilocode/` - Kilocode rules
- `.openhands/` - OpenHands microagents
- `.github/copilot-instructions.md` - Copilot instructions (superseded by CLAUDE.md)

### Delete stale artifacts
- `coverage-all.xml`, `coverage-e2e.xml`, `coverage-integration.xml`, `coverage-unit.xml` (240KB total, from Sept 2023)
- `coverage-summary.md`
- `CLAUDE.md~`, `AGENTS.md~` (editor backup files)
- `server.log`, `firebase-debug.log`
- `.coverage` file

### Move historical root docs to docs/archive/
- `BUG_FIX_SECRETARY_PROPERTY.md`
- `CACHE_INVALIDATION_GUIDE.md`
- `CONVERSATION_LOGIC_REFACTOR.md`
- `EXTENDED_MODEL_TOKEN_LIMITS.md`
- `GIT_WORKFLOW.md`
- `TEST_FAILURE_ANALYSIS_REPORT.md`
- `TEST_FAILURE_FIX_RECOMMENDATIONS.md`
- `TESTING_STRATEGY_REFACTOR.md`
- `TODO.md`

### Keep in root
- `README.md`, `TESTING.md`, `AGENT_MEMORY_AUTONOMY.md`, `AGENTS.md`, `CLAUDE.md`
- Config: `pyproject.toml`, `pytest.ini`, `.flake8`, `Makefile`, `requirements.txt`, `.env.example`
- JSON swarm configs: `creative_swarm.json`, `tool_swarm.json`, `vision_swarm.json`, `openai_swarm.json`
- `run.py`, `setup_claude_env.sh`

### Update .gitignore
- Add: `.roo/`, `.roomodes`, `.hive-mind/`, `.kilocode/`, `.openhands/`
- Add: `coverage-*.xml`, `coverage-summary.md`
- Add: `firebase-debug.log`
- Verify `*.log` covers `server.log`

## Workstream 2: Documentation Cleanup (documentation-maintainer)

### CLAUDE.md slimming (498 -> ~250-300 lines)
- Remove completed-task history (secretary bug fixes, token limit fixes, static implementation removal)
- Replace "Current State (September 2025)" changelog with brief capabilities summary
- Condense secretary implementation details (keep API patterns, remove narrative)
- Keep: architecture, commands, conversation modes, config, project structure, setup, testing

### README.md update
- Verify quickstart instructions work with current codebase
- Update feature list (Conversations API, cross-agent messaging, MCP Launchpad)
- Ensure clear "Getting Started" flow for testers
- Remove references to deleted modules

### docs/ audit
- `docs/ARCHITECTURE.md` - verify against current module list
- `docs/INSTALL.md` - verify setup instructions
- `docs/CLI.md` - verify command documentation
- `docs/WEB_GUI.md` - verify web setup instructions
- `docs/TROUBLESHOOTING.md` - verify still relevant

### AGENTS.md update
- Verify agent descriptions match current capabilities

## Execution Strategy
- Both workstreams run in parallel as subagents
- Structural changes committed first (no content conflicts)
- Documentation changes committed second
- Final verification: run tests to confirm nothing broke
