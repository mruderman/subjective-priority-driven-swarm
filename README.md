# Intrinsic Motivation-Driven Swarm (IMDS)

Multi-agent group chat with real Letta agents. Use a modern Web GUI or a friendly CLI to run authentic multi-agent discussions with live minutes and exports.

# Intrinsic Motivation-Driven Swarm (IMDS)

This project implements a multi-agent group chat system based on their subjective Intrinsivc Motivation-Driven Swarm (IMDS) framework, using real computational beings from a Letta ADE server. Available as both a CLI application and a modern web interface, it features intuitive agent selection and multiple conversation modes for rich, dynamic discussions.

**Key Innovation**: Agents use their own LLM models to perform real subjective assessment of conversations, creating authentic computational personalities that naturally respond, agree, disagree, and build on each other's ideas.

## 🎭 Direct Responses Conversation Modes

**🔄 Hybrid Mode (Recommended)**: Two-phase conversations
- **Phase 1**: All motivated agents share independent thoughts on an initial topic or question.

- **Phase 2**: Agents respond to each other's ideas with rebuttals, agreements, or new insights/

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
- **🧠 Real Agent Introspection**: Agents use their own LLM models for authentic conversation assessment
- **🔄 Natural Group Dynamics**: Agents respond, agree, disagree, and build on each other's ideas, and weigh any potentially emerging egos.
- **⚡ Motivations-Based Responses**: Dynamic turn-taking based on agent intrinsic motivation.
- **💾 Multi-Format Export**: Export conversations, minutes, transcripts, and summaries

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
```

## Minimal Config
Set in a `.env` or your shell (see docs/INSTALL.md):
```bash
LETTA_PASSWORD=your-server-password
LETTA_BASE_URL=http://localhost:8283
LETTA_ENVIRONMENT=SELF_HOSTED   # or LETTA_CLOUD
```

## Documentation
- Installation & setup: docs/INSTALL.md
- Web GUI guide: docs/WEB_GUI.md
- CLI guide: docs/CLI.md
- Architecture overview: docs/ARCHITECTURE.md
- Troubleshooting: docs/TROUBLESHOOTING.md

Tip: If web deps fail with a `typing>=3.10.0.0` error from `letta-flask`, see docs/TROUBLESHOOTING.md for safe workarounds (use local shim or `pip install --no-deps`).

## Contributing
Pull requests welcome! Please run tests/linters before submitting.

## License
MIT — see LICENSE.
