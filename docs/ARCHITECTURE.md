# Architecture Overview

- SPDSAgent: individual agent using subjective assessment
- SwarmManager: orchestrates multi-agent discussions and modes
- SecretaryAgent: AI-powered meeting documentation
- ExportManager: exports minutes, transcripts, summaries
- Integrations: Composio, MCP via a registry

## Conversation Modes
- Hybrid: independent thoughts → response round
- All-Speak: priority-ordered responses with context
- Sequential: fair rotation
- Pure Priority: highest motivation leads

## Secretary & Minutes
Secretary uses Letta API patterns to generate live minutes and supports commands like `/minutes`, `/export`, `/formal`, `/casual`.

## Configuration
See `spds/config.py` and docs/INSTALL.md for environment variables. Model diversity per agent is supported via profiles.

## Session Management
Persistent sessions across CLI and web; see session commands in docs/CLI.md.
