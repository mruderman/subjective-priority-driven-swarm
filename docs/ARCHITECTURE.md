# Architecture Overview

## Core Components
- **SPDSAgent**: Individual agent using subjective assessment with recent conversation context
- **SwarmManager**: Orchestrates multi-agent discussions and modes with incremental message delivery
- **SecretaryAgent**: AI-powered meeting documentation using real Letta agent intelligence
- **ExportManager**: Exports minutes, transcripts, summaries
- **ConversationMessage**: Structured messaging system for incremental delivery
- **ConversationManager** (conversations.py): Letta Conversations API wrapper for session persistence
- **CrossAgentSetup** (cross_agent.py): Session tagging, multi-agent tools, shared memory blocks
- **MCPLaunchpad** (mcp_launchpad.py + mcp_config.py): On-demand MCP tool discovery and execution

## Conversation Modes (All Updated with Dynamic Context)
- **Hybrid**: Independent thoughts → response round with contextual awareness
- **All-Speak**: Priority-ordered responses with recent message context
- **Sequential**: Fair rotation with conversation history awareness
- **Pure Priority**: Highest motivation leads with current topic relevance

## Secretary & Minutes
Secretary uses Letta API patterns to generate live minutes and supports commands like `/minutes`, `/export`, `/formal`, `/casual`.

## Configuration
See `spds/config.py` and docs/INSTALL.md for environment variables. Model diversity per agent is supported via profiles.

## Session Management
Persistent sessions across CLI and web; see session commands in docs/CLI.md.

