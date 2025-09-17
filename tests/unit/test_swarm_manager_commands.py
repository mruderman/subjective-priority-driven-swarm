import sys
from io import StringIO
from types import SimpleNamespace
from unittest.mock import Mock, patch

from spds.swarm_manager import SwarmManager


def _mgr_with_dummy_agents(n=2):
    client = Mock()
    with patch("spds.swarm_manager.SPDSAgent.create_new") as create_new:
        agents = []
        for i in range(n):
            name = f"A{i+1}"
            da = SimpleNamespace(name=name, priority_score=10, motivation_score=40)
            da.assess_motivation_and_priority = lambda topic: None
            da.speak = lambda conversation_history="": SimpleNamespace(
                messages=[
                    SimpleNamespace(
                        role="assistant", content=[{"type": "text", "text": "ok"}]
                    )
                ]
            )
            agents.append(da)
        create_new.side_effect = agents
        profiles = [
            {
                "name": a.name,
                "persona": "p",
                "expertise": ["x"],
                "model": "openai/gpt-4",
                "embedding": "openai/text-embedding-ada-002",
            }
            for a in agents
        ]
        mgr = SwarmManager(
            client=client, agent_profiles=profiles, conversation_mode="sequential"
        )
        return mgr, client


def test_memory_status_command_prints_summary():
    mgr, client = _mgr_with_dummy_agents(2)

    # prepare context retrieval
    def ctx_retrieve(agent_id):
        return {"num_recall_memory": 10, "num_archival_memory": 2}

    client.agents.context.retrieve = lambda agent_id: ctx_retrieve(agent_id)
    captured = StringIO()
    sys.stdout = captured
    handled = mgr._handle_secretary_commands("/memory-status")
    sys.stdout = sys.__stdout__
    out = captured.getvalue()
    assert handled is True
    assert "Agent Memory Status Summary" in out


def test_memory_awareness_command_prints_when_available():
    mgr, client = _mgr_with_dummy_agents(1)
    # Replace with agent carrying .agent for awareness
    mgr.agents = [SimpleNamespace(name="A1", agent=SimpleNamespace(id="id1"))]
    with patch(
        "spds.swarm_manager.create_memory_awareness_for_agent", return_value="info"
    ):
        captured = StringIO()
        sys.stdout = captured
        handled = mgr._handle_secretary_commands("/memory-awareness")
        sys.stdout = sys.__stdout__
        out = captured.getvalue()
        assert handled is True
        assert "Memory Awareness Information Available" in out


def test_help_command_prints():
    mgr, _ = _mgr_with_dummy_agents(1)
    captured = StringIO()
    sys.stdout = captured
    handled = mgr._handle_secretary_commands("/help")
    sys.stdout = sys.__stdout__
    out = captured.getvalue()
    assert handled is True
    assert "Available Commands" in out
