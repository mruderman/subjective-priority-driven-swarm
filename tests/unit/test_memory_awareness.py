import pytest
from datetime import datetime, timedelta
from types import SimpleNamespace

from spds.memory_awareness import (
    MemoryAwarenessReporter,
    create_memory_awareness_for_agent,
)


class StubContextAPI:
    def __init__(self, response):
        self.response = response

    def retrieve(self, agent_id):
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


class StubCoreMemoryAPI:
    def __init__(self, response):
        self.response = response

    def retrieve(self, agent_id):
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


class StubAgentsAPI:
    def __init__(self, context_response, core_response):
        self.context = StubContextAPI(context_response)
        self.core_memory = StubCoreMemoryAPI(core_response)


class StubLettaClient:
    def __init__(self, context_response, core_response):
        self.agents = StubAgentsAPI(context_response, core_response)


@pytest.fixture
def agent():
    return SimpleNamespace(id="agent-123", name="Test Agent")


def make_reporter(context=None, core=None):
    if context is None:
        context = {"num_recall_memory": 0, "num_archival_memory": 0}
    if core is None:
        core = SimpleNamespace(memory={})
    return MemoryAwarenessReporter(StubLettaClient(context, core))


def test_get_objective_memory_metrics_includes_block_statistics(agent):
    long_block = "x" * 150
    core_memory = SimpleNamespace(memory={
        "persona": long_block,
        "facts": "short",
    })
    context_info = {"num_archival_memory": 3, "num_recall_memory": 550}
    reporter = make_reporter(context_info, core_memory)

    metrics = reporter.get_objective_memory_metrics(agent)

    memory_metrics = metrics["memory_metrics"]
    assert memory_metrics["recall_memory_count"] == 550
    assert memory_metrics["archival_memory_count"] == 3
    assert memory_metrics["core_memory_total_chars"] == 150 + len("short")

    blocks = memory_metrics["core_memory_blocks"]
    assert blocks["persona"]["size_chars"] == 150
    assert blocks["persona"]["content_preview"].endswith("...")
    expected_preview = "x" * 100 + "..."
    assert blocks["persona"]["content_preview"] == expected_preview
    assert blocks["facts"]["content_preview"] == "short"

def test_get_objective_memory_metrics_returns_error_when_client_fails(agent):
    context_info = {"num_archival_memory": 0, "num_recall_memory": 0}
    reporter = make_reporter(context_info, RuntimeError("core failure"))

    metrics = reporter.get_objective_memory_metrics(agent)

    assert metrics["agent_name"] == agent.name
    assert metrics["error"].endswith("core failure")


def test_generate_objective_observations_high_recall_and_large_core():
    reporter = make_reporter()

    observations = reporter._generate_objective_observations(600, 20, 3000)

    metrics = {obs["metric"] for obs in observations}
    assert "High Recall Memory Count" in metrics
    assert "Large Core Memory Size" in metrics


def test_generate_objective_observations_limited_archival_usage():
    reporter = make_reporter()

    observations = reporter._generate_objective_observations(200, 5, 1000)

    assert any(obs["metric"] == "Limited Archival Memory Usage" for obs in observations)


def test_generate_objective_observations_balanced_usage():
    reporter = make_reporter()

    observations = reporter._generate_objective_observations(20, 15, 100)

    assert len(observations) == 1
    obs = observations[0]
    assert obs["metric"] == "Balanced Memory Usage"
    assert "typical ranges" in obs["objective_fact"]
    assert "both approaches" in obs["note"]

def test_should_provide_memory_awareness_high_recall_threshold(agent):
    context_info = {"num_recall_memory": 501, "num_archival_memory": 0}
    reporter = make_reporter(context_info)

    assert reporter.should_provide_memory_awareness(agent) is True


def test_should_provide_memory_awareness_time_based_trigger(agent):
    context_info = {"num_recall_memory": 100, "num_archival_memory": 0}
    reporter = make_reporter(context_info)

    last_check = datetime.now() - timedelta(days=8)

    assert reporter.should_provide_memory_awareness(agent, last_check=last_check) is True


def test_should_provide_memory_awareness_handles_exception(agent):
    reporter = make_reporter(RuntimeError("context error"))

    assert reporter.should_provide_memory_awareness(agent) is False


def test_format_neutral_awareness_message_with_metrics():
    reporter = make_reporter()
    metrics = {
        "agent_name": "Test Agent",
        "memory_metrics": {
            "recall_memory_count": 123,
            "archival_memory_count": 5,
            "core_memory_total_chars": 456,
            "core_memory_blocks": {},
        },
        "objective_observations": [
            {
                "metric": "High Recall Memory Count",
                "objective_fact": "Agent has 123 messages in recall memory",
                "potential_considerations": {
                    "maintaining_current_approach": ["Preserves history"],
                    "memory_management_options": ["Archive older details"],
                    "neutral_note": "Agents decide what matters most",
                },
            }
        ],
    }

    message = reporter.format_neutral_awareness_message(metrics)

    assert "📊 **Memory Status Information for Test Agent**" in message
    assert "Recall Memory: 123 messages" in message
    assert "Alternative approaches available" in message
    assert "You may choose to take action" in message


def test_format_neutral_awareness_message_handles_error():
    reporter = make_reporter()

    message = reporter.format_neutral_awareness_message({"error": "metrics unavailable"})

    assert message == "Memory metrics unavailable: metrics unavailable"


def test_create_memory_awareness_for_agent_returns_message_when_triggered(agent):
    long_block = "x" * 50
    core_memory = SimpleNamespace(memory={"summary": long_block})
    context_info = {"num_archival_memory": 2, "num_recall_memory": 600}
    client = StubLettaClient(context_info, core_memory)

    message = create_memory_awareness_for_agent(client, agent)

    assert isinstance(message, str)
    assert "Memory Status Information" in message
    assert "High Recall Memory Count" in message


def test_create_memory_awareness_for_agent_returns_none_without_trigger(agent):
    core_memory = SimpleNamespace(memory={"summary": "short"})
    context_info = {"num_archival_memory": 1, "num_recall_memory": 50}
    client = StubLettaClient(context_info, core_memory)

    message = create_memory_awareness_for_agent(client, agent)

    assert message is None
