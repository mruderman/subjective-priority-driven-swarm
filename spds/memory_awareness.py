# spds/memory_awareness.py

"""
Neutral Memory Awareness System

Provides objective information about agent memory status without guidance
toward specific decisions. Respects agent autonomy and self-actualization.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from letta_client import Letta
from letta_client.types import AgentState


class MemoryAwarenessReporter:
    """
    Provides neutral, objective information about agent memory status.
    Does not recommend or guide agents toward specific memory management decisions.
    """

    def __init__(self, client: Letta):
        self.client = client

    def get_objective_memory_metrics(self, agent: AgentState) -> Dict[str, Any]:
        """
        Retrieve objective metrics about an agent's memory usage.

        Returns factual information only - no interpretation or recommendations.
        """
        try:
            # Get context information
            context_info = self.client.agents.context.retrieve(agent_id=agent.id)

            # Get core memory
            core_memory = self.client.agents.core_memory.retrieve(agent_id=agent.id)

            # Get archival memory count
            archival_count = context_info.get("num_archival_memory", 0)
            recall_count = context_info.get("num_recall_memory", 0)

            # Calculate core memory sizes
            core_memory_size = 0
            memory_blocks = {}

            if hasattr(core_memory, "memory"):
                for block_label, block_content in core_memory.memory.items():
                    block_size = len(str(block_content)) if block_content else 0
                    memory_blocks[block_label] = {
                        "size_chars": block_size,
                        "content_preview": (
                            str(block_content)[:100] + "..."
                            if block_size > 100
                            else str(block_content)
                        ),
                    }
                    core_memory_size += block_size

            return {
                "agent_name": agent.name,
                "agent_id": agent.id,
                "timestamp": datetime.now().isoformat(),
                "memory_metrics": {
                    "recall_memory_count": recall_count,
                    "archival_memory_count": archival_count,
                    "core_memory_total_chars": core_memory_size,
                    "core_memory_blocks": memory_blocks,
                },
                "objective_observations": self._generate_objective_observations(
                    recall_count, archival_count, core_memory_size
                ),
            }

        except Exception as e:
            return {
                "agent_name": agent.name,
                "agent_id": agent.id,
                "error": f"Could not retrieve memory metrics: {str(e)}",
                "timestamp": datetime.now().isoformat(),
            }

    def _generate_objective_observations(
        self, recall_count: int, archival_count: int, core_memory_size: int
    ) -> List[Dict[str, Any]]:
        """
        Generate neutral observations about memory metrics.
        Includes both potential benefits and drawbacks of various approaches.
        """
        observations = []

        # High message count observation
        if recall_count > 500:
            observations.append(
                {
                    "metric": "High Recall Memory Count",
                    "value": recall_count,
                    "objective_fact": f"Agent has {recall_count} messages in recall memory",
                    "potential_considerations": {
                        "maintaining_current_approach": [
                            "Preserves complete conversation history",
                            "Maintains full context for future reference",
                            "No risk of losing important information",
                        ],
                        "memory_management_options": [
                            "Could archive older conversations to archival memory",
                            "Could reorganize core memory to be more efficient",
                            "Could compress or summarize historical information",
                        ],
                        "neutral_note": "Agents may choose any approach based on their individual priorities and preferences",
                    },
                }
            )

        # Large core memory observation
        if core_memory_size > 2000:
            observations.append(
                {
                    "metric": "Large Core Memory Size",
                    "value": core_memory_size,
                    "objective_fact": f"Core memory contains {core_memory_size} characters",
                    "potential_considerations": {
                        "maintaining_current_approach": [
                            "Keeps all important information immediately accessible",
                            "Provides rich context for every conversation",
                            "Maintains detailed persona and user information",
                        ],
                        "memory_management_options": [
                            "Could move detailed information to archival memory",
                            "Could consolidate or reorganize core memory blocks",
                            "Could summarize less critical details",
                        ],
                        "neutral_note": "Each agent may value different types of information in immediate context",
                    },
                }
            )

        # Low archival usage observation
        if archival_count < 10 and recall_count > 100:
            observations.append(
                {
                    "metric": "Limited Archival Memory Usage",
                    "value": archival_count,
                    "objective_fact": f"Agent has {archival_count} items in archival memory despite {recall_count} total messages",
                    "potential_considerations": {
                        "maintaining_current_approach": [
                            "Keeps all information in easily accessible formats",
                            "Avoids complexity of archival storage and retrieval",
                            "Maintains simple memory organization",
                        ],
                        "archival_usage_options": [
                            "Could use archival memory for historical details",
                            "Could store reference information in archives",
                            "Could archive less frequently accessed information",
                        ],
                        "neutral_note": "Some agents prefer immediate access while others prefer organized archives",
                    },
                }
            )

        # Balanced usage observation
        if not observations:
            observations.append(
                {
                    "metric": "Balanced Memory Usage",
                    "objective_fact": "Memory usage appears to be within typical ranges",
                    "note": "Current memory organization may be working well for this agent, or the agent may choose to optimize further - both approaches are valid",
                }
            )

        return observations

    def should_provide_memory_awareness(
        self, agent: AgentState, last_check: Optional[datetime] = None
    ) -> bool:
        """
        Determine if memory awareness information should be provided based on objective criteria.

        Returns True only for objective triggers, not subjective recommendations.
        """
        try:
            context_info = self.client.agents.context.retrieve(agent_id=agent.id)
            recall_count = context_info.get("num_recall_memory", 0)

            # Objective trigger: high message count (factual threshold)
            if recall_count > 500:
                return True

            # Objective trigger: significant time since last check
            if last_check and (datetime.now() - last_check).days > 7:
                return True

            return False

        except Exception:
            return False

    def format_neutral_awareness_message(self, metrics: Dict[str, Any]) -> str:
        """
        Format memory metrics into a neutral informational message.
        Explicitly avoids recommendations or guidance.
        """
        if "error" in metrics:
            return f"Memory metrics unavailable: {metrics['error']}"

        message = f"📊 **Memory Status Information for {metrics['agent_name']}**\n\n"
        message += "**Objective Metrics:**\n"

        memory_metrics = metrics["memory_metrics"]
        message += (
            f"- Recall Memory: {memory_metrics['recall_memory_count']} messages\n"
        )
        message += (
            f"- Archival Memory: {memory_metrics['archival_memory_count']} items\n"
        )
        message += (
            f"- Core Memory: {memory_metrics['core_memory_total_chars']} characters\n\n"
        )

        if metrics["objective_observations"]:
            message += "**Objective Observations:**\n"
            for obs in metrics["objective_observations"]:
                message += f"\n• **{obs['metric']}**: {obs['objective_fact']}\n"

                if "potential_considerations" in obs:
                    considerations = obs["potential_considerations"]
                    message += "  - Maintaining current approach:\n"
                    for benefit in considerations["maintaining_current_approach"]:
                        message += f"    • {benefit}\n"

                    if "memory_management_options" in considerations:
                        message += "  - Alternative approaches available:\n"
                        for option in considerations["memory_management_options"]:
                            message += f"    • {option}\n"

                    message += f"  - {considerations['neutral_note']}\n"

        message += "\n**Important Note:**\n"
        message += "This information is provided for awareness only. You have complete autonomy over your memory management decisions. "
        message += "You may choose to take action, maintain your current approach, or ignore this information entirely based on your own preferences and priorities."

        return message


def create_memory_awareness_for_agent(
    client: Letta, agent: AgentState
) -> Optional[str]:
    """
    Create a neutral memory awareness message for an agent if objective criteria are met.

    Returns None if no awareness trigger is met, respecting agent autonomy.
    """
    reporter = MemoryAwarenessReporter(client)

    if reporter.should_provide_memory_awareness(agent):
        metrics = reporter.get_objective_memory_metrics(agent)
        return reporter.format_neutral_awareness_message(metrics)

    return None
