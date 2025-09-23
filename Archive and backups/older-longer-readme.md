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
- **💬 Human-in-the-Loop**: Seamless interaction between user and computational beings
- **⌨️ Live Commands**: Real-time meeting management with slash commands
- **🚀 WebSocket Communication**: Real-time updates and live agent responses in web interface

## Setup

1.  **Project Structure:** The repository is organized as follows:
    ```
    subjective-priority-driven-swarm/
    |-- spds/                          # Core CLI application
    |   |-- __init__.py
    |   |-- config.py                  # Configuration and environment variables
    |   |-- tools.py                   # SubjectiveAssessment model for agent decision-making
    |   |-- spds_agent.py              # Individual agent implementation
    |   |-- swarm_manager.py           # Multi-agent conversation orchestration
    |   |-- secretary_agent.py         # AI-powered meeting documentation
    |   |-- meeting_templates.py       # Formal and casual minute formatting
    |   |-- export_manager.py          # Multi-format export system
    |   |-- main.py                    # CLI entry point and interactive selection
    |   |-- letta_api.py               # Letta client wrapper and utilities
    |   |-- session_store.py           # Session persistence and management
    |   |-- session_context.py         # Session context handling
    |   |-- session_tracking.py        # Session lifecycle tracking
    |   |-- profiles_schema.py         # Agent profile validation schemas
    |   |-- memory_awareness.py        # Agent memory management utilities
    |   |-- setup.sh                   # Docker setup script for self-hosted Letta
    |   |-- integrations/              # External tool integrations
    |       |-- registry.py            # Integration registry and management
    |       |-- composio.py            # Composio tools integration
    |       |-- mcp.py                 # Model Context Protocol integration
    |-- swarms-web/                    # Web GUI application
    |   |-- app.py                     # Flask web server with WebSocket support
    |   |-- run.py                     # Quick start script with connectivity validation
    |   |-- templates/                 # HTML templates (Jinja2)
    |   |-- static/                    # CSS, JS, assets (Bootstrap 5)
    |   |-- tests/                     # Playwright E2E tests for web interface
    |   |-- requirements.txt           # Web-specific dependencies
    |-- tests/                         # Comprehensive test suite
    |   |-- unit/                      # Unit tests for individual components
    |   |-- integration/               # Integration tests for system interactions
    |   |-- e2e/                       # End-to-end user scenario tests
    |   |-- conftest.py                # Pytest configuration and fixtures
    |-- exports/                       # Generated meeting minutes and exports
    |   |-- sessions/                  # Session-specific exports
    |-- requirements.txt               # Core dependencies
    |-- creative_swarm.json            # Example agent configuration
    |-- openai_swarm.json              # OpenAI-focused agent configuration
    |-- tool_swarm.json                # Tool-enhanced agent configuration
    |-- vision_swarm.json              # Vision-capable agent configuration
    |-- Makefile                       # Build and development shortcuts
    ```

2.  **Install Dependencies:**
    ```bash
    # Core CLI dependencies
    pip install -r requirements.txt

    # Additional web interface dependencies
    pip install -r swarms-web/requirements.txt
    ```

3.  **Configure Environment Variables:**
    Create a `.env` file in the project root or set environment variables:
    ```bash
    # Core Letta Configuration
    LETTA_API_KEY=your-api-key-here                # For Letta Cloud
    LETTA_PASSWORD=your-server-password            # Primary variable for server authentication
    LETTA_BASE_URL=http://localhost:8283           # For self-hosted (fallback for local dev)
    LETTA_ENVIRONMENT=SELF_HOSTED                  # Or LETTA_CLOUD

    # Optional Configuration
    LOG_LEVEL=INFO                                 # Logging level (DEBUG, INFO, WARN, ERROR)
    SPDS_INIT_LOGGING=1                           # Enable automatic logging setup
    LETTA_VALIDATE_CONNECTIVITY=1                  # Validate server connectivity on startup
    ```

    **Environment Variable Precedence for Server Authentication:**
    - **LETTA_PASSWORD** (recommended): Primary variable for Letta server authentication
    - **LETTA_SERVER_PASSWORD** (deprecated): Supported for backward compatibility with deprecation warning
    - **Precedence**: If both are set, LETTA_PASSWORD is used and a preference message is logged

    **Configuration Notes:**
    - The application provides a non-sensitive fallback of `http://localhost:8283` for local development
    - For production, set `LETTA_BASE_URL` and `LETTA_ENVIRONMENT` explicitly and use a secrets manager for API keys
    - **Migration Guide**: If using LETTA_SERVER_PASSWORD, migrate to LETTA_PASSWORD for future compatibility
    - Use `spds.config.validate_letta_config(check_connectivity=True)` to validate configuration and connectivity

4.  **Self-hosted Letta Server Setup (Optional):**
    If you're running your own Letta server instead of using Letta Cloud:

    ```bash
    # Quick setup using provided script
    cd spds && bash setup.sh

    # Or manual Docker setup
    docker run --name letta-ade-server -d \
      -v "$(pwd)":/app/spds_project \
      -e TOOL_EXEC_DIR="/app/spds_project" \
      -e TOOL_EXEC_VENV_NAME="spds-env" \
      -v ~/.letta/.persist/pgdata:/var/lib/postgresql/data \
      -p 8283:8283 \
      letta/letta:latest
    ```

## 🚀 Running the Application

Choose between the web interface (recommended for most users) or the command line interface:

### 🌐 Web Interface (Recommended)

Launch the modern web GUI with real-time features:

```bash
# Recommended in a separate virtualenv
python3 -m venv .venv-web && . .venv-web/bin/activate
pip install -r swarms-web/requirements.txt
pip install git+https://github.com/letta-ai/letta-flask.git

# Quick start
cd swarms-web && python run.py
```

Then open your browser to **http://localhost:5002**

**Web Interface Features:**
- 🖱️ **Point-and-click agent selection** with visual cards
- 🎨 **Modern Bootstrap 5 interface** with responsive design
- ⚡ **Real-time WebSocket communication** for live updates
- 📊 **Live agent scores and phase indicators** during conversations
- 📝 **Interactive secretary panel** with live minutes and commands
- 💾 **One-click export** with download buttons for all formats
- 📱 **Mobile-friendly design** that works on any device

### 🖥️ Command Line Interface

Launch the interactive terminal interface for agent selection and conversation mode choice:

```bash
# CLI in its own virtualenv
python -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
python -m spds.main
```

Notes:
- Default runs an ephemeral swarm using profiles from `spds/config.py`.
- Use `--interactive` to select agents, mode, and secretary via TUI.
- Examples:
  - `python -m spds.main --interactive`
  - `python -m spds.main --agent-ids <ID1> <ID2>`
  - `python -m spds.main --agent-names "Agent A" "Agent B"`
  - `python -m spds.main --swarm-config openai_swarm.json`

Makefile shortcuts:
- `make venv-cli` / `make run-cli`
- `make venv-web` / `make run-web`
- `make test` / `make coverage`

**What you'll see:**
1. **🤖 Agent Discovery**: Automatically finds all agents on your Letta server
2. **☑️ Agent Selection**: Checkbox interface to select computational beings
3. **🎭 Mode Selection**: Choose from 4 conversation modes with descriptions
4. **📝 Secretary Setup**: Enable optional meeting secretary
5. **📋 Meeting Type**: Choose formal board meeting or casual discussion
6. **💬 Topic Input**: Enter your discussion topic
7. **🔄 Rich Conversations**: Experience dynamic, multi-layered discussions
8. **💾 Export Options**: Save meeting minutes and transcripts at the end

### Command Line Options (Advanced)

**Run with specific agents by ID:**
```bash
python -m spds.main --agent-ids ag-123-abc ag-456-def
```

**Run with specific agents by name:**
```bash
python -m spds.main --agent-names "Project Manager Alex" "Designer Jordan"
```

**Run with custom ephemeral swarm:**
```bash
python -m spds.main --swarm-config creative_swarm.json
```

## 📖 Example Session

```
🤖 Discovering available agents from Letta server...
✅ Found 8 available agents

📋 Select agents for your swarm:
☑️ Alice (Research Scientist) - openai/gpt-4.1
☑️ Bob (Creative Director) - anthropic/claude-3-5-sonnet
☐ Charlie (Data Analyst) - together/llama-3.3-70b
☑️ Diana (Product Manager) - google/gemini-pro

🎭 Select conversation mode:
❯ 🔄 Hybrid (independent thoughts + response round) [RECOMMENDED]

📝 Enable meeting secretary? (Records minutes and allows export) Yes

📋 What type of meeting is this?
❯ 🤖 Let Secretary Decide (Adaptive)

💬 Enter conversation topic: "The future of AI in creative industries"

🎯 Selected 3 agents for discussion in HYBRID mode: 'The future of AI in creative industries'
📝 Secretary: Adaptive mode for discussion

Available commands: /minutes, /export, /formal, /casual, /action-item

=== 🧠 INITIAL RESPONSES ===
Alice: [Independent research perspective]
Bob: [Creative industry insights]
Diana: [Product strategy viewpoint]

=== 💬 RESPONSE ROUND ===
Alice: "I agree with Bob's point about human creativity, but..."
Bob: "Diana raises an interesting product angle that makes me think..."
Diana: "Building on both perspectives, what if we considered..."
```

## 📝 Secretary Agent & Meeting Minutes

The secretary agent uses AI-powered note-taking to actively document conversations through real agent communication. Built with proper Letta API patterns using memory blocks and active message processing, it provides intelligent meeting documentation that goes beyond simple transcription:

### Meeting Types

**📋 Formal Board Minutes (Cyan Society)**
- Professional board of directors format
- Compliance with nonprofit governance standards
- Sequential meeting numbering
- Proper motions, decisions, and action items
- Ideal for official organizational records

**💬 Casual Group Discussion Notes**
- Friendly, conversational tone with emojis
- Captures the energy and vibe of discussions
- Highlights key insights and good ideas
- Perfect for team brainstorming sessions

### Live Commands During Conversation

- `/minutes` - Generate current meeting minutes
- `/export [format]` - Export meeting in various formats
- `/formal` - Switch to formal board secretary mode
- `/casual` - Switch to casual discussion mode
- `/action-item [description]` - Manually add an action item
- `/stats` - Show conversation participation statistics
- `/help` - Display all available commands

### Export Formats

When the conversation ends or using `/export`, you can save:

- **📋 Board Minutes** (.md) - Official Cyan Society board format
- **💬 Casual Notes** (.md) - Friendly group discussion summary
- **📝 Raw Transcript** (.txt) - Complete conversation log
- **✅ Action Items** (.md) - Formatted task checklist
- **📊 Executive Summary** (.md) - Brief meeting overview
- **📦 Complete Package** - All formats bundled together

Example export prompt at conversation end:
```
==================================================
🏁 Meeting ended! Export options available.

Would you like to export the meeting? Available options:
  📋 /export minutes - Formal board minutes
  💬 /export casual - Casual meeting notes
  📝 /export transcript - Raw conversation
  ✅ /export actions - Action items list
  📊 /export summary - Executive summary
  📦 /export all - Complete package

Export choice: /export all
✅ Complete package exported: 6 files
```

## 🔧 How It Works

### Real Agent Intelligence
Each computational being uses its own LLM to assess conversation relevance:

1. **🧠 Subjective Assessment**: Agents evaluate conversations across 7 dimensions using their own models:
   - **Importance to Self**: How personally significant is the topic? (0-10)
   - **Perceived Gap**: Are crucial points missing? (0-10)
   - **Unique Perspective**: Do I have insights others haven't shared? (0-10)
   - **Emotional Investment**: How much do I care about the outcome? (0-10)
   - **Expertise Relevance**: How applicable is my domain knowledge? (0-10)
   - **Urgency**: How time-sensitive is this topic? (0-10)
   - **Group Impact**: What's the potential impact on group understanding? (0-10)

2. **⚡ Priority Calculation**: Dynamic scoring determines speaking order:
   - **Motivation Score**: Sum of first 5 dimensions (must exceed threshold of 30)
   - **Priority Score**: (Urgency × 0.6) + (Group Impact × 0.4)
   - Higher priority agents speak first in their mode

3. **🎭 Mode-Based Conversations**: Different interaction patterns:
   - **Hybrid**: Independent → Responses (natural rebuttals/agreements)
   - **All-Speak**: Sequential priority order with context building
   - **Sequential**: Turn-taking with fairness rotation
   - **Pure Priority**: Highest motivation always leads

4. **🧬 Authentic Personalities**: Each agent maintains unique:
   - **Persona**: Distinct personality and communication style
   - **Expertise**: Domain knowledge and areas of interest
   - **Model**: Their own LLM provider and capabilities
   - **Memory**: Persistent conversation history and context

## Configuration

Edit `spds/config.py` or use environment variables to customize:

### Core Settings
- **API Keys**: `LETTA_API_KEY`, `LETTA_PASSWORD`
- **Server**: `LETTA_BASE_URL`, `LETTA_ENVIRONMENT`
- **Default Models**: `DEFAULT_AGENT_MODEL`, `DEFAULT_EMBEDDING_MODEL` (fallback values)
- **Thresholds**: `PARTICIPATION_THRESHOLD`, `URGENCY_WEIGHT`, `IMPORTANCE_WEIGHT`
- **Agent Profiles**: Modify the `AGENT_PROFILES` list

### Secretary & Export Settings
- **Organization**: `ORGANIZATION_NAME` (default: "CYAN SOCIETY")
- **Export Directory**: `EXPORT_DIRECTORY` (default: "./exports")
- **Secretary Mode**: `DEFAULT_SECRETARY_MODE` ("formal", "casual", or "adaptive")
- **Meeting Type**: `DEFAULT_MEETING_TYPE` ("discussion", "board_meeting")
- **Auto Export**: `AUTO_EXPORT_ON_END` (true/false)

### Model Diversity Support

SPDS supports diverse computational lineages through per-agent model configuration:

```python
# Agent profiles can specify different models
AGENT_PROFILES = [
    {
        "name": "OpenAI Agent",
        "persona": "A strategic analyst",
        "expertise": ["analysis", "planning"],
        "model": "openai/gpt-4",
        "embedding": "openai/text-embedding-ada-002"
    },
    {
        "name": "Anthropic Agent",
        "persona": "A creative problem solver",
        "expertise": ["creativity", "innovation"],
        "model": "anthropic/claude-3-5-sonnet-20241022",
        "embedding": "openai/text-embedding-ada-002"
    },
    {
        "name": "Meta Agent",
        "persona": "A technical implementer",
        "expertise": ["engineering", "implementation"],
        "model": "meta-llama/llama-3.1-70b-instruct",
        "embedding": "openai/text-embedding-ada-002"
    }
]
```

**Supported Model Providers:**
- OpenAI (GPT-4.1, GPT-4o-mini, GPT-3.5)
- Anthropic (Claude 3.5 Sonnet, Claude 3 Opus)
- Meta (Llama 3.3-70B, Llama 3.1)
- Google (Gemini Pro)
- Alibaba (Qwen models)
- Together AI (various models)
- Moonshot (Kimi models)
- Mistral AI (Mistral models)
- And others supported by Letta

**Model Configuration Options:**
- `model`: Optional field in agent profiles to specify the LLM model
- `embedding`: Optional field to specify the embedding model
- If not specified, agents use `DEFAULT_AGENT_MODEL` and `DEFAULT_EMBEDDING_MODEL`
- Existing agents preserve their original model configuration when loaded

**Pre-configured Agent Templates:**
- `creative_swarm.json`: Diverse creative and analytical agents with mixed model providers
- `openai_swarm.json`: OpenAI-focused agent configuration
- `tool_swarm.json`: Tool-enhanced agents with specialized capabilities
- `vision_swarm.json`: Vision-capable agents for multimodal interactions

## 🔌 Integration System

SPDS includes a flexible integration system for external tools and services:

### Available Integrations
- **Composio** (`integrations/composio.py`): Access to 150+ tools for productivity, development, and automation
- **Model Context Protocol (MCP)** (`integrations/mcp.py`): Integration with MCP servers for enhanced agent capabilities
- **Integration Registry** (`integrations/registry.py`): Centralized management and discovery of available integrations

### Using Integrations
Integrations can be enabled through agent configuration or dynamically during conversations. The integration registry automatically discovers and manages available tools, making them accessible to agents based on their capabilities and requirements.

## 📊 Session Management

SPDS includes comprehensive session management for persistent conversations:

### Session Features
- **Persistent Sessions**: Resume conversations across CLI and web interfaces
- **Session Context**: Maintain conversation state, participants, and settings
- **Session Exports**: Export session data in multiple formats
- **Session Tracking**: Monitor session lifecycle and participant activity

### Session Commands
```bash
# List all sessions
python -m spds.main sessions list

# Show session details
python -m spds.main sessions show <session-id>

# Delete a session
python -m spds.main sessions delete <session-id>

# Resume a session
python -m spds.main --session-id <session-id>

# Create a new session with title
python -m spds.main --new-session "My Project Discussion"
```

## Example Output

```
Swarm chat started. Type 'quit' or Ctrl+D to end the session.
Enter the topic of conversation: Should we prioritize mobile or web development?

You: I think we need to decide our platform strategy for the next quarter.

--- Assessing agent motivations ---
  - Alex: Motivation Score = 45, Priority Score = 42.00
  - Jordan: Motivation Score = 72, Priority Score = 64.80
  - Casey: Motivation Score = 38, Priority Score = 34.80
  - Morgan: Motivation Score = 89, Priority Score = 80.60

Morgan: As the product owner, I believe we should prioritize mobile development...
```

## Architecture

### Core Components
- **SPDSAgent** (`spds_agent.py`): Individual agent with subjective assessment capabilities and real LLM-based evaluation
- **SwarmManager** (`swarm_manager.py`): Orchestrates multi-agent conversations with secretary integration and 4 conversation modes
- **SecretaryAgent** (`secretary_agent.py`): AI-powered meeting documentation using real Letta agent communication
- **MeetingTemplates** (`meeting_templates.py`): Formal board minutes and casual group discussion formatting engines
- **ExportManager** (`export_manager.py`): Multi-format export system for conversations, minutes, and summaries
- **SubjectiveAssessment** (`tools.py`): Pydantic model for agents to evaluate their motivation across 7 dimensions
- **Session Management** (`session_store.py`, `session_context.py`): Persistent session tracking and context management
- **Integration Registry** (`integrations/`): External tool integrations (Composio, MCP) with centralized management
- **Configuration** (`config.py`): Environment variable management, logging setup, and Letta client configuration
- **Letta API Wrapper** (`letta_api.py`): Simplified interface to Letta client with error handling and utilities

### Key Features
- **Real-time AI Processing**: Secretary actively processes conversations using Letta agent intelligence
- **Memory Block Architecture**: Uses proper Letta memory blocks for meeting context, notes style, and ongoing documentation
- **Active Agent Communication**: Secretary receives and processes messages through `client.agents.messages.create()` for real AI-powered analysis
- **AI-Generated Minutes**: Meeting minutes are generated by the secretary's AI model, not static templates
- **Dual Personality**: Formal board secretary vs. casual note-taker
- **Auto-detection**: Identifies decisions and action items automatically using AI analysis
- **Live Commands**: Manage meetings in real-time with slash commands
- **Flexible Export**: Multiple formats for different audiences

## Contributing

## Troubleshooting

If you encounter this error while installing web dependencies:

```
ERROR: Could not find a version that satisfies the requirement typing>=3.10.0.0 (from letta-flask)
ERROR: No matching distribution found for typing>=3.10.0.0
```

This is caused by an incorrect dependency specification in the upstream `letta-flask`
package. Here are practical workarounds so you can continue local development and
manual testing without blocking on upstream fixes:

- Use the included local shim (recommended for development)
  - This repo contains a minimal `letta_flask` package that provides the
    small API surface the web UI needs. If your Python path includes the repo
    root (running `python run.py` from the repo), Python will import the local
    package and you don't need to pip-install `letta-flask`.

- Install without dependencies (quick workaround)
  ```bash
  pip install --no-deps git+https://github.com/letta-ai/letta-flask.git
  ```
  This bypasses the broken dependency; make sure `letta-client` and other
  runtime deps are already installed in your venv.

- Edit the package metadata before installing (advanced)
  1. git clone https://github.com/letta-ai/letta-flask.git
  2. Remove or fix the `typing` constraint in `pyproject.toml` or `setup.cfg`
  3. pip install .

Notes:
- The local shim is safe for development and testing, but for production or
  CI you should use a correctly packaged `letta-flask` from upstream once
  they publish a fix.
- If you prefer, I can help prepare a temporary wheel with corrected
  metadata for your environment.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details.
