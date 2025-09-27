# spds/tools.py

import inspect
import json
import logging
from typing import Any, Callable, Dict, Optional, Type

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


def build_tool_create_kwargs(
    create_fn: Callable,
    func_callable: Callable,
    *,
    name: str,
    description: Optional[str] = None,
    return_model: Optional[type] = None,
    args_schema: Optional[Type[BaseModel]] = None,
    json_schema: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Prepare kwargs for Letta's tools.create_from_function across SDK versions."""

    def _normalized_param_names(fn: Callable) -> set[str]:
        try:
            params = inspect.signature(fn).parameters
        except (TypeError, ValueError):
            return set()
        filtered = set()
        for param_name in params.keys():
            if param_name in {"self", "args", "kwargs"}:
                continue
            if param_name.startswith("*"):
                continue
            filtered.add(param_name)
        return filtered

    param_names = _normalized_param_names(create_fn)

    supports_name = "name" in param_names or not param_names
    supports_description = "description" in param_names or not param_names
    supports_args_schema = "args_schema" in param_names or not param_names
    supports_json_schema = "json_schema" in param_names or not param_names

    def _with_common_kwargs(target_kw: str) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            target_kw: func_callable,
        }
        if supports_name:
            payload["name"] = name
        if description is not None and supports_description:
            payload["description"] = description
        return payload

    def _attach_schema(payload: Dict[str, Any]) -> Dict[str, Any]:
        if args_schema is not None:
            schema = json_schema
            if schema is None and hasattr(args_schema, "model_json_schema"):
                schema = args_schema.model_json_schema()
            if supports_args_schema:
                payload["args_schema"] = args_schema
            if schema is not None and supports_json_schema:
                payload["json_schema"] = schema
        elif json_schema is not None and supports_json_schema:
            payload["json_schema"] = json_schema
        return payload

    # Prioritize 'function' parameter for legacy compatibility
    if "function" in param_names:
        payload = _with_common_kwargs("function")
        if return_model is not None and "return_model" in param_names:
            payload["return_model"] = return_model
        return _attach_schema(payload)

    if "func" in param_names:
        payload = _with_common_kwargs("func")
        if return_model is not None and "return_model" in param_names:
            payload["return_model"] = return_model
        return _attach_schema(payload)

    # Fallback when signature is not introspectable (e.g. mocks, builtins)
    # Default to legacy 'function=' parameter for compatibility
    fallback_payload = _with_common_kwargs("function")
    if return_model is not None:
        # Always include return_model in fallback for legacy compatibility
        fallback_payload["return_model"] = return_model
    return _attach_schema(fallback_payload)


class SubjectiveAssessment(BaseModel):
    """A structured model for an agent's subjective assessment of a conversation."""

    importance_to_self: int = Field(
        ..., description="How personally significant is this topic? (0-10)"
    )
    perceived_gap: int = Field(
        ..., description="Are there crucial points missing from the discussion? (0-10)"
    )
    unique_perspective: int = Field(
        ..., description="Do I have insights others haven't shared? (0-10)"
    )
    emotional_investment: int = Field(
        ..., description="How much do I care about the outcome? (0-10)"
    )
    expertise_relevance: int = Field(
        ..., description="How applicable is my domain knowledge? (0-10)"
    )
    urgency: int = Field(
        ...,
        description="How time-sensitive is the topic or risk of misunderstanding? (0-10)",
    )
    importance_to_group: int = Field(
        ...,
        description="What is the potential impact on group understanding and consensus? (0-10)",
    )


class SubjectiveAssessmentInput(BaseModel):
    """Input schema for perform_subjective_assessment tool calls."""

    topic: str = Field(..., description="Conversation topic or agenda focus")
    conversation_history: str = Field(
        ...,
        description="Recent transcript or summary the agent should consider",
    )
    agent_persona: str = Field(..., description="Agent persona description")
    agent_expertise: list[str] = Field(
        ...,
        description="List of expertise areas relevant to this agent",
    )


def perform_subjective_assessment(
    topic: str, conversation_history: str, agent_persona: str, agent_expertise: list
):
    """
    Performs a holistic, subjective assessment of the conversation to determine motivation and priority for speaking.
    This single assessment evaluates all dimensions of the agent's internal state.

    Note: This function is designed to be called by the Letta agent's LLM, not directly.
    The agent will use this tool to assess its motivation to speak.
    """
    import json
    
    # Create a fallback SubjectiveAssessment class for tool execution context
    # This is necessary because when executed as a tool, the module-level class may not be available
    class FallbackSubjectiveAssessment:
        def __init__(self, **kwargs):
            for key, value in kwargs.items():
                setattr(self, key, value)

    expertise_str = (
        ", ".join(agent_expertise) if agent_expertise else "general knowledge"
    )

    # Create a structured prompt for the LLM to analyze the conversation
    assessment_prompt = f"""
You are {agent_persona} with expertise in: {expertise_str}

Given the conversation history and topic, assess your motivation to speak next by scoring each dimension from 0-10.

Topic: {topic}

Recent Conversation:
{conversation_history[-1000:] if len(conversation_history) > 1000 else conversation_history}

Evaluate and return scores for:
1. importance_to_self (0-10): How personally significant is this topic to you?
2. perceived_gap (0-10): Are there crucial points missing from the discussion that you could address?
3. unique_perspective (0-10): Do you have insights others haven't shared?
4. emotional_investment (0-10): How much do you care about the outcome?
5. expertise_relevance (0-10): How applicable is your domain knowledge?
6. urgency (0-10): How time-sensitive is the topic or risk of misunderstanding?
7. importance_to_group (0-10): What is the potential impact on group understanding and consensus?

Return ONLY a JSON object with these exact keys and integer values 0-10.
"""

    # For the actual implementation, this prompt would be sent to the agent's LLM
    # Since this function is called BY the agent as a tool, we can access the agent's context
    # For now, we'll create a more intelligent placeholder that considers the actual content

    # Analyze conversation for keywords related to expertise
    expertise_keywords = sum(
        1 for exp in agent_expertise if exp.lower() in conversation_history.lower()
    )
    expertise_score = min(10, expertise_keywords * 2)

    # Check if recent messages mention the agent or their expertise
    recent_history = (
        conversation_history[-500:]
        if len(conversation_history) > 500
        else conversation_history
    )
    personal_relevance = (
        7
        if any(exp.lower() in recent_history.lower() for exp in agent_expertise)
        else 3
    )

    # More nuanced assessment based on topic and expertise
    topic_words = topic.lower().split()
    expertise_match = sum(
        2 for exp in agent_expertise if any(word in exp.lower() for word in topic_words)
    )

    # Check for questions and discussion gaps
    has_question = "?" in recent_history
    needs_perspective = any(
        phrase in recent_history.lower()
        for phrase in ["should we", "what if", "consider", "think about", "prioritize"]
    )

    # Boost personal relevance based on expertise and topic alignment
    personal_relevance = min(10, personal_relevance + expertise_match)

    # Check if the topic is in the agent's domain
    is_ethics_topic = any(
        word in topic.lower() for word in ["ethics", "moral", "responsible"]
    )
    is_tech_topic = any(
        word in topic.lower()
        for word in ["develop", "model", "capabilities", "improve"]
    )
    is_strategy_topic = any(
        word in topic.lower() for word in ["prioritize", "framework", "focus"]
    )

    # Create a somewhat intelligent assessment based on content analysis
    assessment = FallbackSubjectiveAssessment(
        importance_to_self=personal_relevance,
        perceived_gap=8 if has_question else (6 if needs_perspective else 4),
        unique_perspective=min(10, expertise_score + 3),
        emotional_investment=7 if is_ethics_topic else 5,
        expertise_relevance=min(10, expertise_score + 2),
        urgency=(
            8
            if any(
                word in recent_history.lower()
                for word in ["urgent", "asap", "immediately", "critical", "prioritize"]
            )
            else 5
        ),
        importance_to_group=8 if (is_strategy_topic or is_ethics_topic) else 6,
    )

    return assessment


def get_external_tool_functions() -> Dict[str, Callable[[str], str]]:
    """Get external tool functions from integrations registry.

    This function initializes the integrations registry, attempts to register
    available providers (MCP, Composio), and returns a mapping of tool names
    to callable functions that can be registered with Letta's tool system.

    Returns:
        Dictionary mapping tool names to callable functions with signature
        def tool_func(input_str: str, **kwargs) -> str
    """
    from .config import get_integrations_enabled
    from .integrations.registry import get_registry

    # Check if integrations are enabled
    if not get_integrations_enabled():
        logger.debug("Integrations disabled, returning empty tool mapping")
        return {}

    # Initialize registry
    registry = get_registry()

    # Register available providers
    try:
        from .integrations import composio, mcp

        # Attempt to register MCP provider
        mcp.maybe_register_with(registry)

        # Attempt to register Composio provider
        composio.maybe_register_with(registry)

    except Exception as e:
        logger.warning(f"Failed to register some integration providers: {e}")

    # Get available tools
    tools = registry.list_tools()

    # Create callable functions for each tool
    tool_functions = {}
    for tool_fqname, descriptor in tools.items():

        def create_tool_function(fqname):
            def tool_func(input_str: str, **kwargs) -> str:
                """Wrapper function for external tool execution.

                Args:
                    input_str: Input string, potentially JSON
                    **kwargs: Additional keyword arguments

                Returns:
                    String result from tool execution
                """
                try:
                    # Parse input_str as JSON if it looks like JSON
                    if input_str.strip().startswith(("{", "[")):
                        try:
                            args = json.loads(input_str)
                        except json.JSONDecodeError:
                            # If JSON parsing fails, treat as plain text
                            args = {"input": input_str}
                    else:
                        # Treat as plain text input
                        args = {"input": input_str}

                    # Merge with any kwargs
                    if kwargs:
                        args.update(kwargs)

                    # Run the tool
                    result = registry.run(fqname, args)

                    # Convert result to string
                    if isinstance(result, (dict, list)):
                        return json.dumps(result)
                    else:
                        return str(result)

                except Exception as e:
                    logger.error(f"External tool '{fqname}' execution failed: {e}")
                    return f"Error executing tool: {e}"

            return tool_func

        tool_functions[tool_fqname] = create_tool_function(tool_fqname)

    logger.info(f"Loaded {len(tool_functions)} external tools from integrations")
    return tool_functions


def load_and_register_external_tools(client_or_agent, create_fn) -> None:
    """Load and register external tools with a Letta client or agent.

    This helper function fetches external tool functions and registers them
    with the provided create function (typically client.tools.create_from_function).
    Errors are caught and logged but do not fail the main flow.

    Args:
        client_or_agent: Letta client or agent instance
        create_fn: Function to create tools (e.g., client.tools.create_from_function)
    """
    try:
        # Get external tool functions
        external_tools = get_external_tool_functions()

        if not external_tools:
            logger.debug("No external tools available for registration")
            return

        # Register each tool
        registered_count = 0
        for tool_name, tool_func in external_tools.items():
            try:
                kwargs = build_tool_create_kwargs(
                    create_fn,
                    tool_func,
                    name=tool_name,
                    description=f"External tool from integration: {tool_name}",
                )
                create_fn(**kwargs)
                registered_count += 1
                logger.debug(f"Registered external tool: {tool_name}")

            except Exception as e:
                logger.warning(f"Failed to register external tool '{tool_name}': {e}")
                # Continue with other tools even if one fails

        logger.info(f"Successfully registered {registered_count} external tools")

    except Exception as e:
        logger.error(f"Failed to load external tools: {e}")
        # Don't fail the main flow - integrations are optional
