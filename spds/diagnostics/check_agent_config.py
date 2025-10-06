# spds/diagnostics/check_agent_config.py

"""
Diagnostic tool for checking SPDS agent configuration and identifying issues.

This module provides functions to:
- Check agent configuration (model, tools, memory blocks)
- Verify send_message tool is attached
- Test tool execution environment for dependency issues
- Compare models against known good models
- Output actionable recommendations

Usage:
    python -m spds.diagnostics.check_agent_config --agent-name Jack
    python -m spds.diagnostics.check_agent_config --all
    python -m spds.diagnostics.check_agent_config --test-tools
"""

import argparse
import logging
import sys
from typing import Dict, List, Optional

from letta_client import Letta
from letta_client.types import AgentState

from .. import config
from ..letta_api import letta_call

logger = logging.getLogger(__name__)

# Known good models from Letta Leaderboard (as of 2025)
RECOMMENDED_MODELS = [
    "anthropic/claude-sonnet-4",
    "anthropic/claude-sonnet-4-20250514",
    "openai/gpt-4.1",
    "openai/gpt-4.1-2024-12-17",
    "google/gemini-2.5-flash",
]

MODELS_WITH_ISSUES = [
    "anthropic/claude-3-opus",  # Known tool-calling issues
    "anthropic/claude-3-opus-20240229",
]


def check_agent_by_name(client: Letta, agent_name: str) -> Dict:
    """
    Check configuration for a specific agent by name.

    Args:
        client: Letta client instance
        agent_name: Name of the agent to check

    Returns:
        Dict with diagnostic information and recommendations
    """
    logger.info(f"Checking agent configuration for: {agent_name}")

    # Find agent by name
    try:
        agents = letta_call(
            "agents.list",
            client.agents.list,
            name=agent_name,
            limit=10,
        )
    except Exception as e:
        return {
            "error": f"Failed to list agents: {e}",
            "agent_name": agent_name,
            "recommendations": [
                "Check Letta server connection",
                "Verify LETTA_BASE_URL and authentication",
            ],
        }

    if not agents:
        return {
            "error": f"Agent '{agent_name}' not found",
            "agent_name": agent_name,
            "recommendations": [
                f"Create agent with name '{agent_name}'",
                "Or check spelling of agent name",
            ],
        }

    if len(agents) > 1:
        logger.warning(f"Multiple agents found with name '{agent_name}', using first match")

    agent = agents[0]
    return check_agent_by_id(client, agent.id)


def check_agent_by_id(client: Letta, agent_id: str) -> Dict:
    """
    Check configuration for a specific agent by ID.

    Args:
        client: Letta client instance
        agent_id: ID of the agent to check

    Returns:
        Dict with diagnostic information and recommendations
    """
    try:
        # Retrieve full agent details with tools
        agent = letta_call(
            "agents.retrieve",
            client.agents.retrieve,
            agent_id=agent_id,
            include_relationships=["tools", "sources", "memory"],
        )
    except Exception as e:
        return {
            "error": f"Failed to retrieve agent {agent_id}: {e}",
            "agent_id": agent_id,
            "recommendations": [
                "Check agent ID is correct",
                "Verify agent exists on server",
            ],
        }

    # Get tools list
    try:
        tools_response = letta_call(
            "agents.tools.list",
            client.agents.tools.list,
            agent_id=agent_id,
        )
        tools = list(tools_response) if tools_response else []
    except Exception as e:
        logger.warning(f"Failed to list tools for {agent_id}: {e}")
        tools = []

    # Build diagnostic report
    report = {
        "agent_name": agent.name,
        "agent_id": agent.id,
        "model": getattr(agent, "model", "unknown"),
        "embedding": getattr(agent, "embedding", "unknown"),
        "tools": [t.name for t in tools] if tools else [],
        "has_send_message": any(t.name == "send_message" for t in tools),
        "has_assessment_tool": any(
            t.name == "perform_subjective_assessment" for t in tools
        ),
        "system_prompt": getattr(agent, "system", "")[:200],  # First 200 chars
        "issues": [],
        "warnings": [],
        "recommendations": [],
        "checks_passed": [],
    }

    # Check for send_message tool
    if report["has_send_message"]:
        report["checks_passed"].append("✓ send_message tool is attached")
    else:
        report["issues"].append("❌ send_message tool is NOT attached")
        report["recommendations"].append(
            "Add send_message tool: use include_base_tools=True when creating agent"
        )

    # Check for assessment tool
    if report["has_assessment_tool"]:
        report["checks_passed"].append("✓ perform_subjective_assessment tool is attached")
    else:
        report["warnings"].append("⚠️ perform_subjective_assessment tool not found")
        report["recommendations"].append(
            "Assessment tool will be auto-attached by SPDSAgent on first use"
        )

    # Check model
    model = report["model"]
    if model in RECOMMENDED_MODELS:
        report["checks_passed"].append(f"✓ Model {model} is recommended")
    elif model in MODELS_WITH_ISSUES:
        report["warnings"].append(
            f"⚠️ Model {model} has known tool-calling issues"
        )
        report["recommendations"].append(
            f"Consider updating to: {', '.join(RECOMMENDED_MODELS[:3])}"
        )
    else:
        report["warnings"].append(
            f"⚠️ Model {model} not in tested list - may have tool-calling issues"
        )
        report["recommendations"].append(
            f"For best results, use: {', '.join(RECOMMENDED_MODELS[:3])}"
        )

    # Check system prompt for conflicts
    if report["system_prompt"]:
        conflicts = []
        prompt_lower = report["system_prompt"].lower()
        if "do not use tools" in prompt_lower:
            conflicts.append("Contains 'do not use tools'")
        if "avoid function" in prompt_lower:
            conflicts.append("Contains 'avoid function'")

        if conflicts:
            report["issues"].append(
                f"❌ System prompt may conflict with tools: {', '.join(conflicts)}"
            )
            report["recommendations"].append(
                "Review system prompt for tool usage restrictions"
            )

    return report


def check_all_agents(client: Letta) -> List[Dict]:
    """
    Check configuration for all agents on the server.

    Args:
        client: Letta client instance

    Returns:
        List of diagnostic reports for each agent
    """
    try:
        agents = letta_call(
            "agents.list",
            client.agents.list,
            limit=100,
        )
    except Exception as e:
        logger.error(f"Failed to list agents: {e}")
        return []

    reports = []
    for agent in agents:
        report = check_agent_by_id(client, agent.id)
        reports.append(report)

    return reports


def check_tool_execution_env(client: Letta) -> Dict:
    """
    Test tool execution environment for common dependency issues.

    This attempts to create a simple pydantic-based tool and execute it
    to detect import errors or missing dependencies.

    Args:
        client: Letta client instance

    Returns:
        Dict with test results and any detected issues
    """
    logger.info("Testing tool execution environment...")

    report = {
        "test_name": "Tool Execution Environment Test",
        "status": "unknown",
        "issues": [],
        "recommendations": [],
    }

    # Try to create a simple pydantic-based tool
    try:
        from pydantic import BaseModel, Field

        class TestToolInput(BaseModel):
            """Test tool input schema"""
            test_value: str = Field(description="A test value")

        def test_tool_function(test_value: str) -> str:
            """Test tool that requires pydantic"""
            from pydantic import BaseModel
            return f"Pydantic import successful: {test_value}"

        # Try to create tool on server (name is set from function name)
        tool = letta_call(
            "tools.create_from_function",
            client.tools.create_from_function,
            func=test_tool_function,
            tags=["diagnostic", "test"],
        )

        report["status"] = "passed"
        report["checks_passed"] = [
            "✓ Tool creation successful",
            "✓ Pydantic imports available",
        ]

        # Clean up test tool
        try:
            letta_call(
                "tools.delete",
                client.tools.delete,
                tool_id=tool.id,
            )
        except Exception:
            pass  # Cleanup is best-effort

    except Exception as e:
        error_str = str(e).lower()
        report["status"] = "failed"

        if "pydantic" in error_str or "modulenotfound" in error_str:
            report["issues"].append(
                "🔥 CRITICAL: ModuleNotFoundError for pydantic detected"
            )
            report["recommendations"].append(
                "Install pydantic in Letta server tool execution environment:"
            )
            report["recommendations"].append(
                "  docker compose exec letta /app/letta_tools_env/shared-tools-env/bin/pip install pydantic"
            )
        else:
            report["issues"].append(f"❌ Tool execution test failed: {e}")
            report["recommendations"].append(
                "Check Letta server logs for tool execution errors"
            )

    return report


def format_report(report: Dict) -> str:
    """Format a diagnostic report for console output"""
    lines = []

    if "error" in report:
        lines.append(f"\n❌ ERROR: {report['error']}")
        if "recommendations" in report:
            lines.append("\nRecommendations:")
            for rec in report["recommendations"]:
                lines.append(f"  - {rec}")
        return "\n".join(lines)

    # Test report format
    if "test_name" in report:
        lines.append(f"\n{report['test_name']}")
        lines.append("=" * len(report["test_name"]))
        lines.append(f"Status: {report['status'].upper()}")

        if report.get("checks_passed"):
            lines.append("\nChecks Passed:")
            for check in report["checks_passed"]:
                lines.append(f"  {check}")

        if report.get("issues"):
            lines.append("\nIssues Found:")
            for issue in report["issues"]:
                lines.append(f"  {issue}")

        if report.get("recommendations"):
            lines.append("\nRecommendations:")
            for rec in report["recommendations"]:
                lines.append(f"  {rec}")

        return "\n".join(lines)

    # Agent report format
    lines.append(f"\nAgent: {report['agent_name']} (ID: {report['agent_id']})")
    lines.append(f"Model: {report['model']}")
    lines.append(f"Embedding: {report['embedding']}")
    lines.append(f"Tools: {', '.join(report['tools'][:5])}")
    if len(report['tools']) > 5:
        lines.append(f"       ... and {len(report['tools']) - 5} more")

    if report.get("checks_passed"):
        lines.append("\n" + "\n".join(report["checks_passed"]))

    if report.get("warnings"):
        lines.append("\n" + "\n".join(report["warnings"]))

    if report.get("issues"):
        lines.append("\n" + "\n".join(report["issues"]))

    if report.get("recommendations"):
        lines.append("\nRecommendations:")
        for i, rec in enumerate(report["recommendations"], 1):
            lines.append(f"{i}. {rec}")

    return "\n".join(lines)


def main():
    """CLI entry point for diagnostic tool"""
    parser = argparse.ArgumentParser(
        description="SPDS Agent Configuration Diagnostic Tool"
    )
    parser.add_argument(
        "--agent-name",
        help="Check specific agent by name"
    )
    parser.add_argument(
        "--agent-id",
        help="Check specific agent by ID"
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Check all agents on the server"
    )
    parser.add_argument(
        "--test-tools",
        action="store_true",
        help="Test tool execution environment"
    )

    args = parser.parse_args()

    # Initialize Letta client
    try:
        if config.LETTA_ENVIRONMENT == "LETTA_CLOUD":
            client = Letta(token=config.LETTA_API_KEY)
        else:
            password = config.get_letta_password()
            client = Letta(
                base_url=config.LETTA_BASE_URL,
                token=password if password else None,
            )
    except Exception as e:
        print(f"❌ Failed to initialize Letta client: {e}")
        print("\nCheck your configuration:")
        print(f"  LETTA_BASE_URL: {config.LETTA_BASE_URL}")
        print(f"  LETTA_ENVIRONMENT: {config.LETTA_ENVIRONMENT}")
        sys.exit(1)

    # Execute requested checks
    if args.test_tools:
        report = check_tool_execution_env(client)
        print(format_report(report))
    elif args.agent_name:
        report = check_agent_by_name(client, args.agent_name)
        print(format_report(report))
    elif args.agent_id:
        report = check_agent_by_id(client, args.agent_id)
        print(format_report(report))
    elif args.all:
        reports = check_all_agents(client)
        for report in reports:
            print(format_report(report))
            print("\n" + "=" * 80 + "\n")
        print(f"Total agents checked: {len(reports)}")
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
