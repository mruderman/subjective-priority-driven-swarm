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
3. **Tools** (`tools.py`): Defines the SubjectiveAssessment model for agent decision-making
4. **Config** (`config.py`): Contains API keys, agent profiles, and conversation parameters
5. **Interactive Selection** (`main.py`): User-friendly agent and conversation mode selection

### Key Design Patterns
- **Agent-based Architecture**: Each agent has unique persona, expertise, and state
- **Real LLM Assessment**: Agents use their own models to evaluate conversation relevance
- **Multi-Mode Conversations**: Four conversation modes for different discussion styles
- **Interactive UX**: Checkbox-based agent selection with conversation mode options

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
2. **Real Assessment**: Each agent uses their own LLM to evaluate conversation relevance
3. **Mode-Based Conversations**: 
   - **Hybrid**: Independent thoughts → Response round (rebuttals, agreements, new insights)
   - **All-Speak**: Everyone responds in priority order, seeing previous responses
   - **Sequential**: One speaker per turn with fairness rotation
   - **Pure Priority**: Highest motivated agent always speaks
4. **Natural Flow**: Agents respond, agree, disagree, and build on each other's ideas
5. **Continuous Loop**: Conversation continues until user types 'quit'

### Conversation Modes Details
- **🔄 Hybrid (Recommended)**: Two-phase conversations for rich, multi-layered discussions
- **👥 All-Speak**: Fast-paced discussions where all motivated agents contribute immediately  
- **🔀 Sequential**: Traditional turn-taking with fairness to prevent agent monopolization
- **🎯 Pure Priority**: Meritocratic discussions where most motivated agent leads

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