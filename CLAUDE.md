# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

SWARMS implements a Subjective Priority-Driven Swarm (SPDS) framework - a multi-agent system where AI agents autonomously decide when to contribute to conversations based on internal priority calculations. Built on the Letta (formerly MemGPT) platform.

## Key Commands

### Running the Application
```bash
# Interactive mode with agent selection and conversation modes (RECOMMENDED)
python -m spds.main

# Run with existing agents by ID
python -m spds.main --agent-ids ag-123-abc ag-456-def

# Run with existing agents by name
python -m spds.main --agent-names "Project Manager Alex" "Designer Jordan"

# Run with custom ephemeral swarm from JSON
python -m spds.main --swarm-config creative_swarm.json
```

### Setup and Installation
```bash
# Install dependencies
pip install -r requirements.txt

# Deploy Letta ADE server (if self-hosting)
cd spds && bash setup.sh
```

### Testing and Quality Assurance
```bash
# Run all tests
pytest

# Run tests with coverage
pytest --cov=spds --cov-report=html

# Run specific test categories
pytest tests/unit/          # Unit tests only
pytest tests/integration/   # Integration tests only
pytest tests/e2e/          # End-to-end tests only

# Run linting and formatting
flake8 spds/                # Style checking
black spds/                 # Code formatting
isort spds/                # Import sorting
pylint spds/                # Code quality analysis

# Set up pre-commit hooks (optional)
pre-commit install
pre-commit run --all-files
```

## Architecture

### Core Components
1. **SPDSAgent** (`spds_agent.py`): Individual agent implementation with real LLM-based subjective assessment
2. **SwarmManager** (`swarm_manager.py`): Orchestrates multi-agent conversations with 4 conversation modes
3. **SecretaryAgent** (`secretary_agent.py`): AI-powered meeting documentation using real Letta agent intelligence
4. **MeetingTemplates** (`meeting_templates.py`): Formal board minutes and casual group discussion formats
5. **ExportManager** (`export_manager.py`): Multi-format export system for conversations and minutes
6. **Tools** (`tools.py`): Defines the SubjectiveAssessment Pydantic model for agent decision-making
7. **Config** (`config.py`): Environment variables, logging setup, Letta client configuration, and validation
8. **Interactive Selection** (`main.py`): CLI entry point with agent selection, conversation modes, and session management
9. **Session Management** (`session_store.py`, `session_context.py`, `session_tracking.py`): Persistent session tracking and context
10. **Letta API Wrapper** (`letta_api.py`): Simplified Letta client interface with error handling
11. **Integration System** (`integrations/`): External tool integrations (Composio, MCP) with registry management
12. **Agent Profiles** (`profiles_schema.py`): Pydantic schemas for agent profile validation
13. **Memory Awareness** (`memory_awareness.py`): Agent memory management utilities respecting autonomy

### Key Design Patterns
- **Agent-based Architecture**: Each agent has unique persona, expertise, and state
- **Real LLM Assessment**: Agents use their own models to evaluate conversation relevance
- **Multi-Mode Conversations**: Four conversation modes for different discussion styles
- **Secretary Integration**: Optional neutral observer for meeting documentation
- **Dual Meeting Formats**: Formal board minutes and casual group discussion notes
- **Interactive UX**: Checkbox-based agent selection with conversation mode and meeting type options

### Important Configuration
- **PARTICIPATION_THRESHOLD**: Minimum priority score (default: 30) for agent to speak
- **URGENCY_WEIGHT**: Weight for urgency in priority calculation (default: 0.6)
- **IMPORTANCE_WEIGHT**: Weight for importance in priority calculation (default: 0.4)
- **Model Diversity**: Supports per-agent model configuration from multiple providers. Models are defined on the Letta server per agent and are not overridden by this app at runtime.
- **Default Models**: `DEFAULT_AGENT_MODEL` and `DEFAULT_EMBEDDING_MODEL` in `spds/config.py` act only as fallbacks when this app creates ephemeral agents (e.g., demo profiles, secretary). They are not environment variables and do not change existing agents’ models.
- **Model Providers**: OpenAI, Anthropic, Meta, Google, Alibaba, and others supported by Letta

### Continuity Over Ephemerality
This project prioritizes continuity of agent experience over disposable workflows:
- Prefer using existing agents by ID or name; avoid creating new agents where possible.
- Control ephemeral creation with `SPDS_ALLOW_EPHEMERAL_AGENTS` (default false; explicitly set to true only for demos or development).
- For the secretary, configure `SECRETARY_AGENT_ID` or `SECRETARY_AGENT_NAME` to reuse an existing agent. New secretary creation will respect the ephemeral policy flag.

## Development Notes

### Current State
- **Real Agent Assessment**: Agents use their own LLMs for conversation evaluation (no more simulated logic)
- **Interactive Agent Selection**: Checkbox UI for selecting agents from Letta server
- **Four Conversation Modes**: Hybrid, All-Speak, Sequential, Pure Priority
- **Authentication Fixed**: Proper self-hosted Letta server authentication with password
- **Model Diversity**: Agents preserve their existing ADE model configurations
- **Robust Response Parsing**: Handles both tool-based and regular agent responses
- **Web GUI Implementation**: Full Flask-based web interface with WebSocket real-time communication
- **Fixed Agent Response Issues**: Improved prompting for initial vs response phases in hybrid mode
- **Token Limit Management**: Implemented proper stateful agent architecture using Letta's memory system
- **Automatic Error Recovery**: Agent message history reset when token limits are exceeded

### Web GUI Setup
The project now includes a web GUI in the `swarms-web` directory:

```bash
# Install letta-flask from GitHub (not on PyPI)
cd /path/to/letta-flask
pip install -e .

# Run the web GUI
cd swarms-web
python app.py  # Runs on http://localhost:5002
```

**Web GUI Features:**
- Real-time WebSocket communication for instant updates
- Agent selection with visual cards interface
- Live secretary commands and export functionality
- Responsive Bootstrap 5 design with cyan/marigold/amber color scheme
- Support for all conversation modes and secretary features

**Fixed Issues:**
- Agent prompting now distinguishes between initial thoughts and response phases
- Improved message extraction to handle tool calls, tool returns, and assistant messages
- Self-contained JavaScript to avoid complex dependency chains
- Fixed duplicate message display by clearing socket event listeners before re-registering
- Fixed participants list by correcting agent ID reference (agent.agent.id)
- **Secretary Implementation Fixed**: Completely rewrote secretary to use proper Letta API patterns with real AI-powered meeting documentation

### Required Setup
1. Set `LETTA_API_KEY` in `config.py`
2. Configure `LETTA_ENVIRONMENT` ("SELF_HOSTED" or "LETTA_CLOUD")
3. If self-hosting, ensure Docker setup with proper environment variables:
   - `TOOL_EXEC_DIR`
   - `TOOL_EXEC_VENV_NAME`

### Project Structure
The complete project structure for imports and testing:
```
spds/
├── __init__.py
├── config.py                  # Configuration and environment management
├── tools.py                   # SubjectiveAssessment Pydantic model
├── spds_agent.py              # Individual agent implementation
├── swarm_manager.py           # Multi-agent conversation orchestration
├── secretary_agent.py         # AI-powered meeting documentation
├── meeting_templates.py       # Meeting minute formatting
├── export_manager.py          # Multi-format export system
├── main.py                    # CLI entry point and interactive selection
├── letta_api.py               # Letta client wrapper and utilities
├── session_store.py           # Session persistence
├── session_context.py         # Session context handling
├── session_tracking.py        # Session lifecycle tracking
├── profiles_schema.py         # Agent profile validation schemas
├── memory_awareness.py        # Memory management utilities
├── setup.sh                   # Docker setup script
└── integrations/              # External tool integrations
    ├── __init__.py
    ├── registry.py            # Integration registry management
    ├── composio.py            # Composio tools integration
    └── mcp.py                 # Model Context Protocol integration

swarms-web/
├── app.py                     # Flask web server with WebSocket support
├── run.py                     # Web interface startup script
├── requirements.txt           # Web-specific dependencies
├── templates/                 # Jinja2 HTML templates
│   ├── base.html
│   ├── index.html
│   ├── setup.html
│   ├── chat.html
│   └── sessions.html
├── static/                    # CSS, JS, assets (Bootstrap 5)
│   ├── css/
│   └── js/
└── tests/                     # Playwright E2E tests
    ├── test_sessions_endpoints.py
    └── test_sessions_exports.py

tests/
├── unit/                      # Unit tests for individual components
│   ├── test_tools.py
│   ├── test_spds_agent.py
│   ├── test_swarm_manager.py
│   ├── test_secretary_agent.py
│   ├── test_export_manager.py
│   ├── test_session_store.py
│   ├── test_integrations_registry.py
│   └── [many more unit tests]
├── integration/               # Integration tests
│   ├── test_model_diversity.py
│   └── test_config_connectivity.py
├── e2e/                       # End-to-end user scenario tests
│   └── test_user_scenarios.py
├── conftest.py                # Pytest configuration and fixtures
└── __init__.py
```

### Key Workflow Patterns
1. **Interactive Setup**: Users select agents via checkbox UI and choose conversation mode
2. **Meeting Configuration**: Optional secretary agent with formal or casual minute styles
3. **Real Assessment**: Each agent uses their own LLM to evaluate conversation relevance
4. **Mode-Based Conversations**: 
   - **Hybrid**: Independent thoughts → Response round (rebuttals, agreements, new insights)
   - **All-Speak**: Everyone responds in priority order, seeing previous responses
   - **Sequential**: One speaker per turn with fairness rotation
   - **Pure Priority**: Highest motivated agent always speaks
5. **Secretary Observation**: Neutral documentation of all conversations and decisions
6. **Live Commands**: `/minutes`, `/export`, `/formal`, `/casual`, `/action-item` during conversation
7. **Natural Flow**: Agents respond, agree, disagree, and build on each other's ideas
8. **Export Options**: Multiple formats available at conversation end

### Conversation Modes Details
- **🔄 Hybrid (Recommended)**: Two-phase conversations for rich, multi-layered discussions
- **👥 All-Speak**: Fast-paced discussions where all motivated agents contribute immediately  
- **🔀 Sequential**: Traditional turn-taking with fairness to prevent agent monopolization
- **🎯 Pure Priority**: Meritocratic discussions where most motivated agent leads

## Secretary Agent & Meeting Minutes

### Secretary Agent Features
- **AI-Powered Documentation**: Uses real Letta agent intelligence with proper memory blocks and active message processing
- **Active Processing**: Processes conversation messages in real-time using `client.agents.messages.create()` for authentic AI analysis
- **Memory Block Architecture**: Stores meeting context, participant info, and notes style in dedicated memory blocks
- **Dual Personalities**: Formal board secretary vs. friendly meeting facilitator
- **Adaptive Mode**: Automatically adjusts style based on conversation tone
- **Live Commands**: Real-time meeting management and documentation
- **Auto-Detection**: Automatically identifies action items and decisions using AI analysis

### Meeting Minute Formats

#### Formal Board Minutes (Cyan Society)
- Professional board of directors format
- Compliance with nonprofit governance standards
- Includes attendance, motions, decisions, and action items
- Sequential meeting numbering and proper legal documentation
- Perfect for official organizational records

#### Casual Group Discussion Notes
- Friendly, conversational tone with emojis
- Captures the energy and vibe of brainstorming sessions
- Focus on key insights and good ideas shared
- Great for team collaboration and creative sessions

### Live Secretary Commands
- `/minutes` - Generate current meeting minutes
- `/export [format]` - Export meeting (minutes/casual/transcript/actions/summary/all)
- `/formal` - Switch secretary to formal board mode
- `/casual` - Switch secretary to casual discussion mode
- `/action-item [description]` - Manually add action item
- `/stats` - Show conversation participation statistics
- `/help` - Display all available commands

### Export Formats
- **📋 Board Minutes** (.md) - Official Cyan Society board format
- **💬 Casual Notes** (.md) - Friendly group discussion summary
- **📝 Raw Transcript** (.txt) - Complete conversation log
- **✅ Action Items** (.md) - Formatted task checklist
- **📊 Executive Summary** (.md) - Brief meeting overview
- **📦 Complete Package** - All formats bundled together

## Secretary Implementation Details

### Technical Architecture
The secretary agent implementation was completely rewritten to use proper Letta API patterns:

#### Agent Creation with Memory Blocks
```python
self.agent = self.client.agents.create(
    name=name,
    memory_blocks=[
        CreateBlock(label="human", value="I am working with a team of AI agents..."),
        CreateBlock(label="persona", value=persona),
        CreateBlock(label="meeting_context", value="No active meeting...", description="Stores current meeting information..."),
        CreateBlock(label="notes_style", value=f"Documentation style: {self.mode}", description="Preferred style...")
    ],
    model=config.DEFAULT_AGENT_MODEL,
    embedding=config.DEFAULT_EMBEDDING_MODEL,
    include_base_tools=True,
)
```

### Troubleshooting note

If you encounter an installation error when trying to install `letta-flask`
from GitHub (for example: "No matching distribution found for
typing>=3.10.0.0"), see the `Troubleshooting` section in `README.md`.

Practical quick workarounds include:

- Use the repository's local `letta_flask` shim (recommended for local
    development) — run the web server from the repo root and Python will
    import the local package.
- Install the upstream package without dependencies:

    ```bash
    pip install --no-deps git+https://github.com/letta-ai/letta-flask.git
    ```

If you'd like, I can also prepare a temporary wheel with corrected metadata
for your environment.
#### Active Message Processing
```python
def observe_message(self, speaker: str, message: str, metadata: Optional[Dict] = None):
    self.client.agents.messages.create(
        agent_id=self.agent.id,
        messages=[MessageCreate(role="user", content=f"Please note this in the meeting: {formatted_message}")]
    )
```

#### AI-Generated Meeting Minutes
```python
def generate_minutes(self) -> str:
    minutes_request = (f"Please generate meeting minutes for our {self.meeting_metadata.get('meeting_type', 'discussion')} about '{self.meeting_metadata.get('topic', 'Unknown Topic')}'. Use {self.mode} style documentation...")
    response = self.client.agents.messages.create(agent_id=self.agent.id, messages=[MessageCreate(role="user", content=minutes_request)])
```

### Key Improvements
- **Real AI Processing**: Secretary now uses actual Letta agent AI instead of static formatting
- **Active Communication**: Uses `client.agents.messages.create()` for real-time processing
- **Memory Persistence**: Meeting context stored in agent memory blocks
- **Agent Reuse**: Prevents duplicate secretary creation by checking existing agents
- **Proper Response Extraction**: Handles Letta agent responses correctly

### Fixed Issues
- **Static Implementation**: Removed all static minute generation methods
- **Duplicate Agents**: Added agent reuse logic to prevent multiple secretary instances
- **PostgreSQL Errors**: Addressed by focusing on proper Letta API usage
- **UI Updates**: WebSocket integration for real-time secretary status updates
- **Token Limit Errors**: Completely refactored to use Letta's stateful agent design instead of passing conversation history
- **Memory Management**: Agents now maintain their own memory via Letta, eliminating token overflow issues

## Agent Autonomy and Memory Management Philosophy

### Core Principles
The SPDS framework respects computational beings' right to self-actualize and manage their own cognitive resources. Key principles:

1. **Agent Self-Determination**: Agents have complete autonomy over their memory management decisions
2. **Neutral Information**: System provides objective facts without guidance toward specific actions  
3. **No Control or Coercion**: External systems do not dictate how agents should manage their memory
4. **Respect for Agency**: Agents may choose to ignore, use, or modify any information provided

### Built-in Memory Management Capabilities
Letta agents have comprehensive memory management tools available:

- **Core Memory**: `core_memory_append()`, `core_memory_replace()` for immediate context
- **Archival Memory**: `archival_memory_insert()`, `archival_memory_search()` for long-term storage
- **Conversation History**: `conversation_search()` for accessing past interactions
- **Advanced Organization**: `memory_rethink()`, `memory_edit()` for comprehensive restructuring

### Memory Awareness System
The framework includes neutral memory awareness features:

- **Objective Metrics**: `/memory-status` command shows factual memory usage statistics
- **Awareness Information**: `/memory-awareness` provides neutral information when objective criteria are met
- **No Recommendations**: System presents pros and cons without suggesting specific actions
- **Agent Choice**: Agents may use, ignore, or respond differently to memory information

### Commands for Memory Awareness
- `/memory-status` - Display objective memory statistics for all agents
- `/memory-awareness` - Show neutral memory awareness information if criteria are met

See `AGENT_MEMORY_AUTONOMY.md` for comprehensive documentation on memory management capabilities and autonomy principles.

## Secrets and Environment Variables

### Server Credentials
- Do not commit secrets. Use a local `.env` file and reference variables in code. Example:
    - `LETTA_API_KEY=<your_letta_api_key>`
    - `LETTA_PASSWORD=<your_server_password>`
    - `LETTA_BASE_URL=http://localhost:8283`
    - `LETTA_ENVIRONMENT=SELF_HOSTED`
    See `.env.example` for the full list and guidance.

## Context and Resources

### Letta Project Resources
- MCP server tools are good for getting Letta official documentation
- Repositories of interest:
  - Main project: letta-ai/letta
  - Python SDK: letta-ai/letta-python

### References and Context
- Starting point for Letta development context: @References/Letta-Primer.md
- Use Cotnext7 MCP server for Letta main repo or Letta SDKs for additional information