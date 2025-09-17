from types import SimpleNamespace
from unittest.mock import Mock

from letta_client.types import Tool

from spds.spds_agent import SPDSAgent
from tests.unit.test_spds_agent import mk_agent_state


def test_speak_has_tools_initial_and_response():
    client = Mock()
    tool = Tool(id="t", name="perform_subjective_assessment", description="d")
    state = mk_agent_state(
        id="ag", name="N", system="S", model="openai/gpt-4", tools=[tool]
    )
    agent = SPDSAgent(state, client)
    # First call returns tool-call flow; second is arbitrary
    client.agents.messages.create.return_value = SimpleNamespace(
        messages=[
            SimpleNamespace(role="assistant", content=[{"type": "text", "text": "ok"}])
        ]
    )

    agent.speak("", mode="initial", topic="T")
    assert client.agents.messages.create.called

    client.agents.messages.create.reset_mock()
    agent.speak("", mode="response", topic="T")
    assert client.agents.messages.create.called


def test_speak_fallback_direct_instruction():
    client = Mock()
    tool = Tool(id="t", name="perform_subjective_assessment", description="d")
    state = mk_agent_state(
        id="ag", name="N", system="S", model="openai/gpt-4", tools=[tool]
    )
    agent = SPDSAgent(state, client)
    client.agents.messages.create.side_effect = [
        Exception("No tool calls found"),
        SimpleNamespace(
            messages=[
                SimpleNamespace(
                    role="assistant", content=[{"type": "text", "text": "ok"}]
                )
            ]
        ),
    ]
    agent.speak("", mode="initial", topic="T")
    assert client.agents.messages.create.call_count == 2
