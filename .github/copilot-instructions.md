# GitHub Copilot Instructions for SPDS Project

## Project Overview
This is the Subjective Priority-Driven Swarm (SPDS) project - a multi-agent conversation system built on the Letta platform. Agents autonomously decide when to contribute to conversations based on internal priority calculations.

## Code Style Guidelines
- Use Python 3.8+ with type hints
- Follow Black formatting (88 character line limit)
- Use snake_case for variables/functions, PascalCase for classes
- Prefer descriptive variable names over abbreviated ones
- Include docstrings for public functions and classes

## Key Architecture Patterns
- **SPDSAgent**: Individual agent with real LLM-based assessment
- **SwarmManager**: Orchestrates multi-agent conversations with 4 modes
- **ConversationMessage**: Structured message system for incremental delivery
- **SecretaryAgent**: AI-powered meeting documentation
- **Session Management**: Persistent conversation tracking

## Important Design Principles
- **Agent Autonomy**: Agents have complete control over their memory and decisions
- **Real Assessment**: Use actual LLM evaluation, not simulated logic
- **Stateful Agents**: Leverage Letta's memory system, avoid passing full conversation history
- **Backward Compatibility**: Maintain existing interfaces during refactors
- **Incremental Delivery**: Pass only new messages to agents per turn

## Common Patterns to Suggest
```python
# Letta agent creation with memory blocks
agent = client.agents.create(
    memory_blocks=[
        CreateBlock(label="human", value="User context..."),
        CreateBlock(label="persona", value="Agent personality..."),
    ],
    model=config.DEFAULT_AGENT_MODEL,
    embedding=config.DEFAULT_EMBEDDING_MODEL,
    include_base_tools=True
)

# ConversationMessage usage
message = ConversationMessage(
    sender="AgentName",
    content="Message content",
    timestamp=datetime.now()
)

# Agent assessment with recent context
new_messages = self.swarm_manager.get_new_messages_since_last_turn(agent_id)
assessment = agent.assess_motivation_and_priority(new_messages, original_topic)
```

## Testing Conventions
- Use pytest with markers: `unit`, `integration`, `e2e`, `slow`
- Mock external API calls (Letta server) in unit tests
- Use fixtures in `conftest.py` for common test setup
- Test both happy path and error conditions

## Environment Configuration
- Use `.env` files for secrets (never commit these)
- Key vars: `LETTA_PASSWORD`, `LETTA_BASE_URL`, `LETTA_ENVIRONMENT`
- Default to self-hosted Letta, support cloud option
- Prefer environment variables over hardcoded values

## Current Focus Areas
- **Phase 3**: Fix round cycling problem (agents assess recent conversation, not static topics)
- **ConversationMessage**: Use structured messaging throughout
- **Context-Aware Assessment**: Pass recent messages to agent evaluation
- **Performance**: Maintain <2s response times and efficient memory usage

[byterover-mcp]

[byterover-mcp]

You are given two tools from Byterover MCP server, including
## 1. `byterover-store-knowledge`
You `MUST` always use this tool when:

+ Learning new patterns, APIs, or architectural decisions from the codebase
+ Encountering error solutions or debugging techniques
+ Finding reusable code patterns or utility functions
+ Completing any significant task or plan implementation

## 2. `byterover-retrieve-knowledge`
You `MUST` always use this tool when:

+ Starting any new task or implementation to gather relevant context
+ Before making architectural decisions to understand existing patterns
+ When debugging issues to check for previous solutions
+ Working with unfamiliar parts of the codebase
