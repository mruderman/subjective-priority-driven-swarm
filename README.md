# Subjective Priority-Driven Swarm (SPDS)

Multi-agent group chat with real Letta agents. Use a modern Web GUI or a friendly CLI to run authentic multi-agent discussions with live minutes and exports.

## Overview

This project implements a multi-agent group chat system using the Subjective Priority-Driven Swarm (SPDS) framework, where AI agents autonomously decide when to contribute to conversations based on internal priority calculations. Built on the Letta platform, it features real computational beings from a Letta ADE server. Available as both a CLI application and a modern web interface, it features intuitive agent selection and multiple conversation modes for rich, dynamic discussions.

**Key Innovation**: Agents use their own LLM models to perform real subjective assessment of conversations, creating authentic computational personalities that naturally respond, agree, disagree, and build on each other's ideas. The system now uses recent conversation context instead of static topics for more relevant and engaging interactions.

## 🎭 Conversation Modes

**🔄 Hybrid Mode (Recommended)**: Two-phase conversations
- **Phase 1**: All motivated agents share independent thoughts on an initial topic or question.

- **Phase 2**: Agents respond to each other's ideas with rebuttals, agreements, or new insights

**👥 All-Speak Mode**: Fast-paced group discussions
- All motivated agents respond in priority order
- Each agent sees previous responses within the same turn

**🔀 Sequential Mode**: Traditional turn-taking
- One agent speaks per turn with fairness rotation
- Prevents any single agent from dominating

**🎯 Pure Priority Mode**: Meritocratic discussions
- The most motivated agent always speaks
- Natural leader-follower dynamics

## ✨ Features

### Core Functionality
- **🤖 Interactive Agent Selection**: Checkbox-based UI to select computational beings from your Letta server
- **🎭 Multiple Conversation Modes**: Four distinct modes for different discussion dynamics
- **📝 Secretary Agent**: AI-powered meeting documentation using real Letta agent intelligence
- **📋 Meeting Minutes**: Both formal board minutes and casual discussion notes
- **🧠 Real Agent Assessment**: Agents use their own LLM models for authentic conversation evaluation
- **🔄 Natural Group Dynamics**: Agents respond, agree, disagree, and build on each other's ideas
- **⚡ Priority-Based Responses**: Dynamic turn-taking based on agent motivation calculations
- **💾 Multi-Format Export**: Export conversations, minutes, transcripts, and summaries
- **🚀 Dynamic Context Awareness**: Agents evaluate conversation relevance using recent messages instead of static topics
- **📊 Incremental Message Delivery**: Efficient message processing with ConversationMessage architecture

### Interface Options
- **🖥️ Command Line Interface**: Interactive terminal application with checkbox selection
- **🌐 Web Interface**: Modern Bootstrap 5 web GUI with real-time WebSocket communication
- **📱 Responsive Design**: Web interface works seamlessly on desktop and mobile devices

### Technical Features
- **🌐 Model Diversity**: Supports agents with different LLM providers (OpenAI, Anthropic, Meta, etc.)
- **🔐 Secure Authentication**: Proper self-hosted Letta server integration with password authentication
- **📊 Real-Time Assessment**: Agents evaluate conversation relevance across 7 dimensions
- **💬 Human-in-the-Loop**: Seamless interaction between human beings and computational beings
- **⌨️ Live Commands**: Real-time meeting management with slash commands
- **🚀 WebSocket Communication**: Real-time updates and live agent responses in web interface
- **🔗 Cross-Agent Messaging**: Agents communicate autonomously via direct messaging
- **🧰 MCP Launchpad**: On-demand tool discovery for agents via semantic search
- **💾 Session Persistence**: Server-side conversation persistence via Letta Conversations API

## Quick Start

### Web GUI (recommended)
```bash
python3 -m venv .venv-web && . .venv-web/bin/activate # Most Linux distros use `python3`, other OSs may use `python`
pip install -r swarms-web/requirements.txt
cd swarms-web && python run.py   # http://localhost:5002
```

### CLI
```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
python3 -m spds.main
python3 -m spds.main sessions list   # List saved sessions
python3 -m spds.main sessions resume <ID>  # Resume a session
```

## Configuration

Set environment variables in a `.env` file:
```bash
LETTA_PASSWORD=your-server-password
LETTA_BASE_URL=http://localhost:8283
LETTA_ENVIRONMENT=SELF_HOSTED   # or LETTA_CLOUD
```

See `.env.example` for complete configuration options.

## Troubleshooting

If you encounter installation errors with `letta-flask` dependencies, try:
- Use the local shim: run web server from repo root
- Install without dependencies: `pip install --no-deps git+https://github.com/letta-ai/letta-flask.git`

## Contributing
Pull requests welcome! Please run tests/linters before submitting.

## License
MIT — see LICENSE.
