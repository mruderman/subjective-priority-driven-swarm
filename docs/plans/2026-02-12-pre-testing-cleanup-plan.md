# Pre-Testing Repo Cleanup Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Clean up repo structure and documentation before user testing - both dev hygiene and user-facing polish.

**Architecture:** Two independent workstreams running in parallel: (1) project-curator for structural cleanup (file removal, .gitignore, archive moves) and (2) documentation-maintainer for content updates (CLAUDE.md slimming, README, docs/ audit). Structural changes committed first to avoid conflicts.

**Tech Stack:** Git, Python (pytest for verification)

---

## Workstream 1: Structural Cleanup (project-curator subagent)

### Task 1: Update .gitignore with new exclusions

**Files:**
- Modify: `.gitignore`

**Step 1: Add legacy tool directories and stale artifact patterns to .gitignore**

Add these entries to `.gitignore` (in appropriate sections):

```gitignore
# Legacy AI tool configs (no longer used)
.roo/
.roomodes
.openhands/

# Coverage XML artifacts
coverage-*.xml
coverage-summary.md

# Firebase debug log
firebase-debug.log
```

Note: `.hive-mind/` and `.kilocode/` are already in `.gitignore`. Verify `*.log` already covers `server.log` (it does via the Django `*.log` pattern on line 60).

**Step 2: Verify .gitignore is correct**

Run: `git status` to confirm new patterns are recognized.

### Task 2: Remove legacy tool directories from git tracking

**Files:**
- Remove from git: `.roo/` (all files), `.roomodes`, `.hive-mind/` (all files), `.openhands/` (all files), `.github/copilot-instructions.md`

**Step 1: Remove tracked files**

```bash
git rm -r --cached .roo/ .roomodes .openhands/ .hive-mind/
git rm --cached .github/copilot-instructions.md
```

The `--cached` flag removes from git tracking only; local files remain for reference.

**Step 2: Verify removal**

Run: `git status` - should show deleted files staged for commit.

### Task 3: Remove stale coverage artifacts from git

**Files:**
- Remove from git: `coverage-all.xml`, `coverage-e2e.xml`, `coverage-integration.xml`, `coverage-unit.xml`, `coverage-summary.md`

**Step 1: Remove tracked coverage files**

```bash
git rm --cached coverage-all.xml coverage-e2e.xml coverage-integration.xml coverage-unit.xml coverage-summary.md
```

**Step 2: Verify removal**

Run: `git status` - coverage files should be staged for deletion.

### Task 4: Move historical docs to docs/archive/

**Files:**
- Move: `BUG_FIX_SECRETARY_PROPERTY.md` -> `docs/archive/BUG_FIX_SECRETARY_PROPERTY.md`
- Move: `CACHE_INVALIDATION_GUIDE.md` -> `docs/archive/CACHE_INVALIDATION_GUIDE.md`
- Move: `CONVERSATION_LOGIC_REFACTOR.md` -> `docs/archive/CONVERSATION_LOGIC_REFACTOR.md`
- Move: `EXTENDED_MODEL_TOKEN_LIMITS.md` -> `docs/archive/EXTENDED_MODEL_TOKEN_LIMITS.md`
- Move: `GIT_WORKFLOW.md` -> `docs/archive/GIT_WORKFLOW.md`
- Move: `TEST_FAILURE_ANALYSIS_REPORT.md` -> `docs/archive/TEST_FAILURE_ANALYSIS_REPORT.md`
- Move: `TEST_FAILURE_FIX_RECOMMENDATIONS.md` -> `docs/archive/TEST_FAILURE_FIX_RECOMMENDATIONS.md`
- Move: `TESTING_STRATEGY_REFACTOR.md` -> `docs/archive/TESTING_STRATEGY_REFACTOR.md`
- Move: `TODO.md` -> `docs/archive/TODO.md`

**Step 1: Create archive directory and move files**

```bash
mkdir -p docs/archive
git mv BUG_FIX_SECRETARY_PROPERTY.md docs/archive/
git mv CACHE_INVALIDATION_GUIDE.md docs/archive/
git mv CONVERSATION_LOGIC_REFACTOR.md docs/archive/
git mv EXTENDED_MODEL_TOKEN_LIMITS.md docs/archive/
git mv GIT_WORKFLOW.md docs/archive/
git mv TEST_FAILURE_ANALYSIS_REPORT.md docs/archive/
git mv TEST_FAILURE_FIX_RECOMMENDATIONS.md docs/archive/
git mv TESTING_STRATEGY_REFACTOR.md docs/archive/
git mv TODO.md docs/archive/
```

**Step 2: Verify moves**

Run: `git status` - should show renamed files. Run: `ls docs/archive/` - should show 9 files.

### Task 5: Delete untracked stale files

**Files:**
- Delete: `CLAUDE.md~`, `AGENTS.md~` (editor backup files, not tracked)
- Delete: `server.log`, `firebase-debug.log` (already gitignored via `*.log` pattern)
- Delete: `.coverage` (already gitignored)

**Step 1: Remove stale local files**

```bash
rm -f CLAUDE.md~ AGENTS.md~ server.log firebase-debug.log .coverage
```

These are untracked/gitignored files so no `git rm` needed.

**Step 2: Verify clean state**

Run: `ls *.md~ server.log firebase-debug.log .coverage 2>/dev/null` - should produce no output.

### Task 6: Commit structural cleanup

**Step 1: Stage and commit all structural changes**

```bash
git add .gitignore
git add -u  # stages all modifications and deletions
git add docs/archive/  # stage moved files
git commit -m "chore: clean up repo structure for user testing

- Remove legacy AI tool configs from tracking (.roo/, .roomodes, .hive-mind/, .openhands/)
- Remove stale coverage XML artifacts
- Move 9 historical docs to docs/archive/
- Update .gitignore with new exclusion patterns
- Delete .github/copilot-instructions.md (superseded by CLAUDE.md)"
```

**Step 2: Verify commit**

Run: `git log --oneline -1` - should show the commit.
Run: `ls *.md` in root - should show only README.md, TESTING.md, AGENT_MEMORY_AUTONOMY.md, AGENTS.md, CLAUDE.md.

---

## Workstream 2: Documentation Cleanup (documentation-maintainer subagent)

> **Important:** Wait for Workstream 1 commit before committing documentation changes. This avoids merge conflicts. However, the documentation editing work itself can happen in parallel.

### Task 7: Slim CLAUDE.md

**Files:**
- Modify: `CLAUDE.md`

**Step 1: Read current CLAUDE.md and identify sections to remove or condense**

Sections to REMOVE entirely:
- "Current State (September 2025)" changelog block (lines ~160-180)
- "Secretary Implementation Details > Key Improvements" narrative
- "Secretary Implementation Details > Fixed Issues" narrative
- "Development Notes > Fixed Agent Response Issues" and similar completed-bug entries
- Duplicate secretary code examples that repeat what's in the Architecture section

Sections to CONDENSE:
- "Secretary Implementation Details" - keep the code patterns (CreateBlock, observe_message, generate_minutes), remove the narrative around them
- "Role-Based Secretary Assignment" - keep the API, remove the "Coming Soon" subsections
- "Web GUI Setup" - keep the commands, remove the "Fixed Issues" list

Sections to KEEP as-is:
- Project Overview
- Key Commands (Running, Setup, Testing)
- Architecture (core components list)
- Key Design Patterns
- Important Configuration
- Conversation Modes Details
- Live Secretary Commands
- Export Formats
- Project Structure
- Secrets and Environment Variables
- Context and Resources
- Letta Server Tool Dependencies (CRITICAL)

**Step 2: Edit CLAUDE.md**

Remove the identified sections and condense as described. Target: ~250-300 lines.

**Step 3: Verify CLAUDE.md is still valid**

Scan for broken internal references or orphaned section headers.

### Task 8: Update README.md

**Files:**
- Modify: `README.md`

**Step 1: Update feature list to reflect modernization**

Add to features section:
- Cross-agent messaging (agents can talk to each other autonomously)
- MCP Launchpad (on-demand tool discovery)
- Letta Conversations API (server-side session persistence)

Remove the "Major Update" banner (September 2025 is old news).

**Step 2: Verify quickstart instructions**

Check that `python3 -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt && python3 -m spds.main` is still the correct flow. Check web quickstart too.

**Step 3: Add session management to quickstart**

Add a brief note about `python -m spds.main sessions list` and `sessions resume` commands.

### Task 9: Update docs/ARCHITECTURE.md

**Files:**
- Modify: `docs/ARCHITECTURE.md`

**Step 1: Update component list**

Current list references "Integrations: Composio, MCP via a registry" which is outdated. Replace with:
- `conversations.py` - Letta Conversations API wrapper
- `cross_agent.py` - Cross-agent messaging (session tagging, multi-agent tools, shared memory blocks)
- `mcp_launchpad.py` + `mcp_config.py` - On-demand MCP tool discovery

Remove the "September 2025" update banner and "Key Architectural Improvements" dated section.

### Task 10: Update docs/INSTALL.md

**Files:**
- Modify: `docs/INSTALL.md`

**Step 1: Remove dated update banner**

Remove the "September 2025" update line.

**Step 2: Verify instructions are accurate**

Check that env vars listed match what `spds/config.py` actually reads. Verify the `python -m venv` and `pip install` commands work as documented.

### Task 11: Audit remaining docs/ files

**Files:**
- Read and verify: `docs/CLI.md`, `docs/WEB_GUI.md`, `docs/TROUBLESHOOTING.md`

**Step 1: Read each file and check for outdated references**

Look for:
- References to deleted modules (session_tracking, session_context, integrations/)
- Outdated command syntax
- Dated update banners

**Step 2: Fix any issues found**

Make minimal targeted edits for accuracy.

### Task 12: Update AGENTS.md

**Files:**
- Modify: `AGENTS.md`

**Step 1: Verify module descriptions are current**

Check that the module list matches the actual files in `spds/`. Ensure `conversations.py`, `cross_agent.py`, `mcp_launchpad.py`, `mcp_config.py` are properly described. Remove any references to deleted modules.

Remove the "September 2025" achievement banner if present.

### Task 13: Commit documentation cleanup

**Step 1: Stage and commit documentation changes**

```bash
git add CLAUDE.md AGENTS.md README.md docs/ARCHITECTURE.md docs/INSTALL.md docs/CLI.md docs/WEB_GUI.md docs/TROUBLESHOOTING.md
git commit -m "docs: slim CLAUDE.md, update README and docs for user testing

- Slim CLAUDE.md from ~500 to ~300 lines (remove historical sections)
- Update README.md feature list with modernization work
- Update docs/ARCHITECTURE.md with current module list
- Remove dated update banners across all docs
- Verify setup instructions accuracy"
```

---

## Verification

### Task 14: Run tests to confirm nothing broke

**Step 1: Run full test suite**

```bash
pytest --tb=short -q
```

Expected: All 595+ tests pass. No test should reference moved/deleted files.

**Step 2: Verify imports are clean**

```bash
grep -r "session_tracking\|session_context\|integrations\." spds/ --include="*.py" | grep -v __pycache__
```

Expected: No results (these modules were deleted in Phase 5).

**Step 3: Final root directory check**

```bash
ls *.md
```

Expected: `AGENT_MEMORY_AUTONOMY.md  AGENTS.md  CLAUDE.md  README.md  TESTING.md` (5 files, down from 14).
