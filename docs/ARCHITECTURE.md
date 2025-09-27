# Architecture Overview

**🎉 Recent Update**: Completed conversation logic refactor (September 2025) - now featuring dynamic, context-aware agent interactions with natural conversation flow.

## Core Components
- **SPDSAgent**: Individual agent using subjective assessment with recent conversation context
- **SwarmManager**: Orchestrates multi-agent discussions and modes with incremental message delivery
- **SecretaryAgent**: AI-powered meeting documentation using real Letta agent intelligence
- **ExportManager**: Exports minutes, transcripts, summaries
- **ConversationMessage**: Structured messaging system for incremental delivery
- **Integrations**: Composio, MCP via a registry

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

## Key Architectural Improvements (September 2025)
- **Dynamic Context Assessment**: Agents evaluate conversation relevance using recent messages
- **Incremental Message Delivery**: Efficient processing with ConversationMessage architecture
- **Natural Conversation Flow**: Eliminated repetitive assessment patterns
- **Full Backward Compatibility**: Maintained existing interfaces without breaking changes
