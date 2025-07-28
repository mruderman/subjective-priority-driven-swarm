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
3. **SecretaryAgent** (`secretary_agent.py`): Neutral observer for meeting minutes and export features
4. **MeetingTemplates** (`meeting_templates.py`): Formal board minutes and casual group discussion formats
5. **ExportManager** (`export_manager.py`): Multi-format export system for conversations and minutes
6. **Tools** (`tools.py`): Defines the SubjectiveAssessment model for agent decision-making
7. **Config** (`config.py`): Contains API keys, agent profiles, conversation parameters, and secretary settings
8. **Interactive Selection** (`main.py`): User-friendly agent selection, conversation modes, and meeting types

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
- **Model Diversity**: Supports per-agent model configuration from multiple providers
- **Default Models**: `DEFAULT_AGENT_MODEL` and `DEFAULT_EMBEDDING_MODEL` as fallback values
- **Model Providers**: OpenAI, Anthropic, Meta, Google, Alibaba, and others supported by Letta

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
The project structure for imports and testing:
```
spds/
├── __init__.py
├── config.py
├── tools.py
├── spds_agent.py
├── swarm_manager.py
├── secretary_agent.py
├── meeting_templates.py
├── export_manager.py
└── main.py

tests/
├── unit/
│   ├── test_tools.py
│   ├── test_spds_agent.py
│   └── test_swarm_manager.py
├── integration/
│   └── test_model_diversity.py
├── e2e/
│   └── test_user_scenarios.py
├── conftest.py
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

## Secrets and Environment Variables

### Server Credentials
- Our self-hosted Letta ADE server secure password env var is => LETTA_SERVER_PASSWORD=TWIJftq/ufbbxo8w51m/BQ1wBNrZb/JTlmnop

## Context and Resources

### Letta Project Resources
- MCP server tools are good for getting Letta official documentation
- Repositories of interest:
  - Main project: letta-ai/letta
  - Python SDK: letta-ai/letta-python

### References and Context
- Starting point for Letta development context: @References/Letta-Primer.md
- Use Cotnext7 MCP server for Letta main repo or Letta SDKs for additional information