"""
Unit tests for SwarmManager utility functions.

This module consolidates tests for response extraction, memory management,
export functionality, secretary commands, meeting management, and other
SwarmManager utility methods.
"""

import builtins
import json
import sys
import time
import types
from io import StringIO
from types import SimpleNamespace
from unittest.mock import Mock, call, patch

import httpx
import pytest
from letta_client import NotFoundError
from letta_client.types import AgentState, EmbeddingConfig, LlmConfig
from letta_client.types.agent_state import Memory

from spds.spds_agent import SPDSAgent
from spds.swarm_manager import SwarmManager


# ============================================================================
# Helper Functions and Fixtures
# ============================================================================


def _make_not_found_error(message="Not found"):
    resp = httpx.Response(404, request=httpx.Request("GET", "http://test"))
    return NotFoundError(message, response=resp, body={"detail": message})


def mk_agent_state(
    id: str, name: str, system: str = "Test", model: str = "openai/gpt-4"
):
    """Build a minimally valid AgentState for current letta_client schema."""
    llm = LlmConfig(model=model, model_endpoint_type="openai", context_window=128000)
    emb = EmbeddingConfig(
        embedding_endpoint_type="openai",
        embedding_model="openai/text-embedding-ada-002",
        embedding_dim=1536,
    )
    mem = Memory(blocks=[])
    return AgentState(
        id=id,
        name=name,
        system=system,
        agent_type="react_agent",
        llm_config=llm,
        embedding_config=emb,
        memory=mem,
        blocks=[],
        tools=[],
        sources=[],
        tags=[],
        model=model,
        embedding="openai/text-embedding-ada-002",
    )


def make_tool_response(text: str):
    """
    Create a synthetic tool-message response object representing a single tool call to `send_message`.

    The returned object is a SimpleNamespace with a `messages` list containing one message SimpleNamespace that mimics a tool-generated message:
    - message_type is "tool_message"
    - the message contains a single `tool_call` whose `function.name` is "send_message" and whose `function.arguments` is a JSON string encoding {"message": text}

    Parameters:
        text (str): The message text to embed as the `message` argument of the simulated `send_message` tool call.

    Returns:
        SimpleNamespace: An object with shape compatible with tests that expect tool-based agent responses (i.e., has a `messages` attribute with the described message structure).
    """
    tool_call = SimpleNamespace(
        function=SimpleNamespace(
            name="send_message", arguments=json.dumps({"message": text})
        )
    )
    message = SimpleNamespace(
        tool_calls=[tool_call],
        tool_return=None,
        message_type="tool_message",
        content=None,
    )
    return SimpleNamespace(messages=[message])


def make_assistant_response(text: str, *, as_list: bool = False):
    """
    Create a synthetic assistant message object for tests.

    Useful in unit tests to simulate an assistant response. By default the message content is a plain string; set `as_list=True` to produce a list-style content payload (a list containing a single dict with keys `type` and `text`).

    Parameters:
        text (str): The assistant's text content.
        as_list (bool, optional): When True, wrap `text` in a list-style content object. Defaults to False.

    Returns:
        types.SimpleNamespace: A SimpleNamespace with a `messages` attribute containing a single assistant message. Each message includes `role`, `message_type`, `content`, and placeholders for `tool_calls` and `tool_return`.
    """
    if as_list:
        content = [{"type": "text", "text": text}]
    else:
        content = text

    message = SimpleNamespace(
        tool_calls=[],
        tool_return=None,
        role="assistant",
        message_type="assistant_message",
        content=content,
    )
    return SimpleNamespace(messages=[message])


def _make_msg(**kwargs):
    msg = SimpleNamespace()
    for k, v in kwargs.items():
        setattr(msg, k, v)
    return msg


class _ToolCall:
    def __init__(self, func_name: str, arguments: str):
        self.function = SimpleNamespace(name=func_name, arguments=arguments)


class _Resp:
    def __init__(self, messages):
        self.messages = messages


def _sample_profile(name="Agent X"):
    return {
        "name": name,
        "persona": "A short persona",
        "expertise": ["testing"],
        "model": "openai/gpt-4",
        "embedding": "openai/text-embedding-ada-002",
    }


# ============================================================================
# Tests from test_swarm_manager.py
# ============================================================================


def test_update_agent_memories_handles_token_reset(
    mock_letta_client, sample_agent_profiles
):
    """Token limit errors should trigger a reset and retry."""
    with patch("spds.swarm_manager.SPDSAgent.create_new") as mock_create:
        dummy_agent = SimpleNamespace(
            name="Agent 1", agent=SimpleNamespace(id="agent-1")
        )
        mock_create.return_value = dummy_agent
        manager = SwarmManager(
            client=mock_letta_client,
            agent_profiles=[sample_agent_profiles[0]],
        )

    manager._reset_agent_messages = Mock()
    mock_letta_client.agents.messages.create.side_effect = [
        Exception("token limit exceeded"),
        None,
    ]

    manager._update_agent_memories(
        "Important update", speaker="Facilitator", max_retries=2
    )

    manager._reset_agent_messages.assert_called_once_with("agent-1")
    assert mock_letta_client.agents.messages.create.call_count == 2


def test_update_agent_memories_token_reset_retry_failure(
    mock_letta_client,
    sample_agent_profiles,
    capsys,
):
    """If the retry after a reset fails, we should log the failure."""
    with patch("spds.swarm_manager.SPDSAgent.create_new") as mock_create:
        dummy_agent = SimpleNamespace(
            name="Agent 1", agent=SimpleNamespace(id="agent-1")
        )
        mock_create.return_value = dummy_agent
        manager = SwarmManager(
            client=mock_letta_client,
            agent_profiles=[sample_agent_profiles[0]],
        )

    manager._reset_agent_messages = Mock()
    mock_letta_client.agents.messages.create.side_effect = [
        Exception("token limit exceeded"),
        Exception("still failing"),
    ]

    manager._update_agent_memories(
        "Critical update", speaker="Facilitator", max_retries=2
    )

    manager._reset_agent_messages.assert_called_once_with("agent-1")
    assert mock_letta_client.agents.messages.create.call_count == 2

    output = capsys.readouterr().out
    assert "Token limit reached for Agent 1" in output
    assert "Retry failed for Agent 1: still failing" in output
    assert "Failed to update Agent 1 after 2 attempts" in output


def test_update_agent_memories_reports_failure_after_retries(
    mock_letta_client,
    sample_agent_profiles,
    capsys,
):
    """A non-retryable error should report the failure without retry."""
    with patch("spds.swarm_manager.SPDSAgent.create_new") as mock_create:
        dummy_agent = SimpleNamespace(
            name="Agent 1", agent=SimpleNamespace(id="agent-1")
        )
        mock_create.return_value = dummy_agent
        manager = SwarmManager(
            client=mock_letta_client,
            agent_profiles=[sample_agent_profiles[0]],
        )

    mock_letta_client.agents.messages.create.side_effect = Exception("hard failure")

    manager._update_agent_memories("Another update", max_retries=2)

    output = capsys.readouterr().out
    assert "Failed to update Agent 1" in output


def test_get_agent_message_count_success_and_error(
    mock_letta_client,
    sample_agent_profiles,
):
    """_get_agent_message_count should handle success and exceptions."""
    with patch("spds.swarm_manager.SPDSAgent.create_new") as mock_create:
        dummy_agent = SimpleNamespace(
            name="Agent 1", agent=SimpleNamespace(id="agent-1")
        )
        mock_create.return_value = dummy_agent
        manager = SwarmManager(
            client=mock_letta_client,
            agent_profiles=[sample_agent_profiles[0]],
        )

    mock_letta_client.agents.messages.list.return_value = [1, 2, 3]
    assert manager._get_agent_message_count("agent-1") == 3

    mock_letta_client.agents.messages.list.side_effect = RuntimeError("boom")
    assert manager._get_agent_message_count("agent-1") == 0


def test_warm_up_agent_success_and_failure(
    mock_letta_client,
    sample_agent_profiles,
):
    """_warm_up_agent should return True on success and False on failure."""
    with patch("spds.swarm_manager.SPDSAgent.create_new") as mock_create:
        dummy_agent = SimpleNamespace(
            name="Agent 1", agent=SimpleNamespace(id="agent-1")
        )
        mock_create.return_value = dummy_agent
        manager = SwarmManager(
            client=mock_letta_client,
            agent_profiles=[sample_agent_profiles[0]],
        )

    test_agent = SimpleNamespace(
        name="Agent 1", agent=SimpleNamespace(id="agent-1")
    )

    mock_letta_client.agents.messages.create.return_value = None
    with patch("spds.swarm_manager.time.sleep") as sleep_mock:
        assert manager._warm_up_agent(test_agent, "Topic") is True
        sleep_mock.assert_called()

    mock_letta_client.agents.messages.create.side_effect = Exception("fail")
    assert manager._warm_up_agent(test_agent, "Topic") is False


def test_extract_agent_response_variants(
    mock_letta_client,
    sample_agent_profiles,
):
    """_extract_agent_response should handle tool calls, lists, and fallbacks."""
    with patch("spds.swarm_manager.SPDSAgent.create_new") as mock_create:
        dummy_agent = SimpleNamespace(
            name="Agent 1", agent=SimpleNamespace(id="agent-1")
        )
        mock_create.return_value = dummy_agent
        manager = SwarmManager(
            client=mock_letta_client,
            agent_profiles=[sample_agent_profiles[0]],
        )

    tool_response = make_tool_response("From tool call")
    assert manager._extract_agent_response(tool_response) == "From tool call"

    list_response = make_assistant_response("From list content", as_list=True)
    assert manager._extract_agent_response(list_response) == "From list content"

    empty_message = SimpleNamespace(
        tool_calls=[],
        tool_return=None,
        message_type=None,
        content=None,
    )
    empty_response = SimpleNamespace(messages=[empty_message])
    assert (
        manager._extract_agent_response(empty_response)
        == "I have some thoughts but I'm having trouble phrasing them."
    )


def test_start_meeting_with_secretary_sets_metadata(
    mock_letta_client,
    sample_agent_profiles,
):
    """_start_meeting should coordinate with the secretary and log the topic."""
    with patch("spds.swarm_manager.SPDSAgent.create_new") as mock_create:
        base_agent = SimpleNamespace(name="Base", agent=SimpleNamespace(id="base"))
        mock_create.return_value = base_agent
        manager = SwarmManager(
            client=mock_letta_client,
            agent_profiles=[sample_agent_profiles[0]],
        )

    secretary = SimpleNamespace(
        start_meeting=Mock(),
        meeting_metadata={},
    )
    manager.secretary = secretary
    manager.meeting_type = "planning"
    manager.conversation_history = ""
    manager.conversation_mode = "hybrid"
    manager.agents = [
        SimpleNamespace(name="Agent 1"),
        SimpleNamespace(name="Agent 2"),
    ]

    manager._start_meeting("Strategy")

    secretary.start_meeting.assert_called_once_with(
        topic="Strategy",
        participants=["Agent 1", "Agent 2"],
        meeting_type="planning",
    )
    assert secretary.meeting_metadata["conversation_mode"] == "hybrid"
    assert "System: The topic is 'Strategy'." in manager.conversation_history


def test_handle_secretary_commands_without_secretary(
    mock_letta_client, sample_agent_profiles, capsys
):
    """Secretary-specific commands should warn when secretary is disabled."""
    with patch("spds.swarm_manager.SPDSAgent.create_new") as mock_create:
        base_agent = SimpleNamespace(name="Base", agent=SimpleNamespace(id="base"))
        mock_create.return_value = base_agent
        manager = SwarmManager(
            client=mock_letta_client,
            agent_profiles=[sample_agent_profiles[0]],
        )

    manager.secretary = None

    handled = manager._handle_secretary_commands("/minutes")
    output = capsys.readouterr().out

    assert handled is True
    assert "Secretary is not enabled" in output


def test_handle_secretary_commands_routes_to_secretary(
    mock_letta_client, sample_agent_profiles, capsys
):
    """Commands should call through to the secretary when available."""
    with patch("spds.swarm_manager.SPDSAgent.create_new") as mock_create:
        base_agent = SimpleNamespace(name="Base", agent=SimpleNamespace(id="base"))
        mock_create.return_value = base_agent
        manager = SwarmManager(
            client=mock_letta_client,
            agent_profiles=[sample_agent_profiles[0]],
        )

    secretary = SimpleNamespace(
        generate_minutes=Mock(return_value="minutes text"),
        set_mode=Mock(),
        add_action_item=Mock(),
        get_conversation_stats=Mock(return_value={"summary": "stats"}),
        meeting_metadata={"topic": "Strategy"},
        conversation_log="log",
        action_items=["Do something"],
        decisions=["Decide"],
        mode="adaptive",
        observe_message=Mock(),
    )
    manager.secretary = secretary
    manager._handle_export_command = Mock()

    assert manager._handle_secretary_commands("/minutes") is True
    assert secretary.generate_minutes.called
    assert "minutes text" in capsys.readouterr().out

    assert manager._handle_secretary_commands("/export summary") is True
    manager._handle_export_command.assert_called_with("summary")

    assert manager._handle_secretary_commands("/formal") is True
    secretary.set_mode.assert_any_call("formal")
    assert "Secretary mode changed to formal" in capsys.readouterr().out

    assert manager._handle_secretary_commands("/casual") is True
    secretary.set_mode.assert_any_call("casual")

    assert manager._handle_secretary_commands("/action-item Prepare report") is True
    secretary.add_action_item.assert_called_with("Prepare report")

    assert manager._handle_secretary_commands("/action-item") is True
    assert "Usage: /action-item" in capsys.readouterr().out

    assert manager._handle_secretary_commands("/stats") is True
    assert "summary" in capsys.readouterr().out


def test_handle_secretary_commands_memory_reports(
    mock_letta_client, sample_agent_profiles, capsys
):
    """Memory commands should run even without a secretary."""
    with patch("spds.swarm_manager.SPDSAgent.create_new") as mock_create:
        base_agent = SimpleNamespace(name="Base", agent=SimpleNamespace(id="base"))
        mock_create.return_value = base_agent
        manager = SwarmManager(
            client=mock_letta_client,
            agent_profiles=[sample_agent_profiles[0]],
        )

    summary = {
        "total_agents": 2,
        "agents_with_high_memory": 1,
        "total_messages_across_agents": 123,
        "agents_status": [
            {
                "name": "Agent 1",
                "recall_memory": 600,
                "archival_memory": 2,
                "high_memory": True,
            }
        ],
    }
    manager.get_memory_status_summary = Mock(return_value=summary)
    manager.check_memory_awareness_status = Mock()

    assert manager._handle_secretary_commands("/memory-status") is True
    status_output = capsys.readouterr().out
    assert "Total agents: 2" in status_output
    assert "Agents with >500 messages" in status_output

    assert manager._handle_secretary_commands("/memory-awareness") is True
    manager.check_memory_awareness_status.assert_called_with(silent=False)


def test_handle_export_command_variants(mock_letta_client, sample_agent_profiles):
    """_handle_export_command should dispatch to the correct exporter."""
    with patch("spds.swarm_manager.SPDSAgent.create_new") as mock_create:
        base_agent = SimpleNamespace(name="Base", agent=SimpleNamespace(id="base"))
        mock_create.return_value = base_agent
        manager = SwarmManager(
            client=mock_letta_client,
            agent_profiles=[sample_agent_profiles[0]],
            enable_secretary=True,
        )

    manager.secretary = SimpleNamespace(
        meeting_metadata={"topic": "Topic"},
        conversation_log="log",
        action_items=["Item"],
        decisions=["Decision"],
        get_conversation_stats=Mock(return_value={"summary": "stats"}),
        mode="adaptive",
    )
    manager.export_manager = Mock()
    manager.export_manager.export_meeting_minutes.return_value = "minutes.md"

    manager._handle_export_command("minutes")
    meeting_data = manager.export_manager.export_meeting_minutes.call_args[0][0]
    assert meeting_data["metadata"]["topic"] == "Topic"

    manager.export_manager.export_executive_summary.return_value = "summary.md"
    manager._handle_export_command("summary")
    manager.export_manager.export_executive_summary.assert_called()

    manager.export_manager.export_complete_package.return_value = ["one", "two"]
    manager._handle_export_command("all")
    manager.export_manager.export_complete_package.assert_called_with(
        meeting_data, "adaptive"
    )


def test_handle_export_command_unknown_format(
    mock_letta_client, sample_agent_profiles, capsys
):
    """Unknown export formats should notify the user."""
    with patch("spds.swarm_manager.SPDSAgent.create_new") as mock_create:
        base_agent = SimpleNamespace(name="Base", agent=SimpleNamespace(id="base"))
        mock_create.return_value = base_agent
        manager = SwarmManager(
            client=mock_letta_client,
            agent_profiles=[sample_agent_profiles[0]],
            enable_secretary=True,
        )

    manager.secretary = SimpleNamespace(
        meeting_metadata={},
        conversation_log="",
        action_items=[],
        decisions=[],
        get_conversation_stats=Mock(return_value={}),
        mode="adaptive",
    )
    manager.export_manager = Mock()

    manager._handle_export_command("unknown")
    output = capsys.readouterr().out
    assert "Unknown export format" in output


def test_offer_export_options_invokes_command(
    mock_letta_client, sample_agent_profiles
):
    """_offer_export_options should forward user input to command handler."""
    with patch("spds.swarm_manager.SPDSAgent.create_new") as mock_create:
        base_agent = SimpleNamespace(name="Base", agent=SimpleNamespace(id="base"))
        mock_create.return_value = base_agent
        manager = SwarmManager(
            client=mock_letta_client,
            agent_profiles=[sample_agent_profiles[0]],
            enable_secretary=True,
        )

    manager.secretary = SimpleNamespace(
        meeting_metadata={},
        conversation_log="",
        action_items=[],
        decisions=[],
        mode="adaptive",
        get_conversation_stats=Mock(return_value={}),
    )
    manager._handle_secretary_commands = Mock()

    with patch("builtins.input", return_value="/minutes"):
        manager._offer_export_options()

    manager._handle_secretary_commands.assert_called_once_with("/minutes")


def test_notify_secretary_agent_response(mock_letta_client, sample_agent_profiles):
    """_notify_secretary_agent_response should forward to secretary when present."""
    with patch("spds.swarm_manager.SPDSAgent.create_new") as mock_create:
        base_agent = SimpleNamespace(name="Base", agent=SimpleNamespace(id="base"))
        mock_create.return_value = base_agent
        manager = SwarmManager(
            client=mock_letta_client,
            agent_profiles=[sample_agent_profiles[0]],
        )

    observer = Mock()
    manager.secretary = SimpleNamespace(observe_message=observer)

    manager._notify_secretary_agent_response("Agent", "Message")

    observer.assert_called_once_with("Agent", "Message")


def test_check_memory_awareness_status_outputs_info(
    mock_letta_client, sample_agent_profiles, capsys
):
    """Memory awareness information should be printed when available."""
    with patch("spds.swarm_manager.SPDSAgent.create_new") as mock_create:
        base_agent = SimpleNamespace(name="Base", agent=SimpleNamespace(id="base"))
        mock_create.return_value = base_agent
        manager = SwarmManager(
            client=mock_letta_client,
            agent_profiles=[sample_agent_profiles[0]],
        )

    manager.agents = [
        SimpleNamespace(name="Agent 1", agent=SimpleNamespace(id="agent-1")),
        SimpleNamespace(name="Agent 2", agent=SimpleNamespace(id="agent-2")),
    ]

    with patch(
        "spds.swarm_manager.create_memory_awareness_for_agent"
    ) as awareness_patch:
        awareness_patch.side_effect = ["Awareness message", RuntimeError("fail")]

        manager.check_memory_awareness_status(silent=False)

    output = capsys.readouterr().out
    assert "Awareness message" in output
    assert "Could not generate memory awareness" in output


def test_check_memory_awareness_status_silent(
    mock_letta_client, sample_agent_profiles, capsys
):
    """Silent checks should not print anything."""
    with patch("spds.swarm_manager.SPDSAgent.create_new") as mock_create:
        base_agent = SimpleNamespace(name="Base", agent=SimpleNamespace(id="base"))
        mock_create.return_value = base_agent
        manager = SwarmManager(
            client=mock_letta_client,
            agent_profiles=[sample_agent_profiles[0]],
        )

    manager.agents = [
        SimpleNamespace(name="Agent 1", agent=SimpleNamespace(id="agent-1"))
    ]

    capsys.readouterr()

    with patch(
        "spds.swarm_manager.create_memory_awareness_for_agent",
        return_value="Message",
    ):
        manager.check_memory_awareness_status(silent=True)

    assert capsys.readouterr().out == ""


def test_get_memory_status_summary_with_errors(
    mock_letta_client, sample_agent_profiles
):
    """get_memory_status_summary should handle errors per agent."""
    with patch("spds.swarm_manager.SPDSAgent.create_new") as mock_create:
        base_agent = SimpleNamespace(name="Base", agent=SimpleNamespace(id="base"))
        mock_create.return_value = base_agent
        manager = SwarmManager(
            client=mock_letta_client,
            agent_profiles=[sample_agent_profiles[0]],
        )

    manager.agents = [
        SimpleNamespace(name="Agent 1", agent=SimpleNamespace(id="agent-1")),
        SimpleNamespace(name="Agent 2", agent=SimpleNamespace(id="agent-2")),
    ]

    mock_letta_client.agents.context = Mock()
    mock_letta_client.agents.context.retrieve.side_effect = [
        {"num_recall_memory": 600, "num_archival_memory": 2},
        RuntimeError("fail"),
    ]

    summary = manager.get_memory_status_summary()

    assert summary["total_agents"] == 2
    assert summary["agents_with_high_memory"] == 1
    assert summary["total_messages_across_agents"] == 600
    assert summary["agents_status"][0]["high_memory"] is True
    assert summary["agents_status"][1]["error"] == "fail"


# ============================================================================
# Tests from test_swarm_manager_additional.py
# ============================================================================


def test_extract_agent_response_prefers_tool_call(mock_letta_client):
    """_swarm_manager._extract_agent_response should prefer a send_message tool call."""
    with patch("spds.swarm_manager.SPDSAgent.create_new") as mock_create:
        mock_agent = Mock()
        mock_agent.name = "A"
        mock_agent.agent = SimpleNamespace(id="a1")
        mock_create.return_value = mock_agent

        mgr = SwarmManager(client=mock_letta_client, agent_profiles=[_sample_profile()])

        # Build a synthetic response that mimics a tool call to send_message
        tool_call = SimpleNamespace(
            function=SimpleNamespace(
                name="send_message", arguments=json.dumps({"message": "hello tool"})
            )
        )
        message = SimpleNamespace(
            tool_calls=[tool_call],
            tool_return=None,
            message_type="tool_message",
            content=None,
        )
        response = SimpleNamespace(messages=[message])

        extracted = mgr._extract_agent_response(response)
        assert "hello tool" in extracted


def test_handle_secretary_commands_memory_status_prints_summary(
    mock_letta_client, capsys
):
    """/memory-status should call get_memory_status_summary and print objective info."""
    with patch("spds.swarm_manager.SPDSAgent.create_new") as mock_create:
        mock_agent = Mock()
        mock_agent.name = "A"
        mock_agent.agent = SimpleNamespace(id="a1")
        mock_create.return_value = mock_agent

        # make the client return simple context info
        mock_letta_client.agents.context.retrieve.return_value = {
            "num_recall_memory": 5,
            "num_archival_memory": 1,
        }

        mgr = SwarmManager(client=mock_letta_client, agent_profiles=[_sample_profile()])

        handled = mgr._handle_secretary_commands("/memory-status")
        captured = capsys.readouterr()

        assert handled is True
        assert "Total agents" in captured.out or "Agent Memory Status" in captured.out


def test_start_meeting_sets_secretary_metadata_when_enabled(mock_letta_client):
    """_enabling secretary should set secretary metadata when starting a meeting."""
    with patch("spds.swarm_manager.SPDSAgent.create_new") as mock_create, patch(
        "spds.swarm_manager.SecretaryAgent"
    ) as mock_secretary:
        mock_agent = Mock()
        mock_agent.name = "A"
        mock_agent.agent = SimpleNamespace(id="a1")
        mock_create.return_value = mock_agent

        mock_sec = Mock()
        mock_sec.meeting_metadata = {}
        mock_sec.agent = SimpleNamespace(name="Secretary")
        mock_sec.start_meeting = Mock()
        mock_secretary.return_value = mock_sec

        mgr = SwarmManager(
            client=mock_letta_client,
            agent_profiles=[_sample_profile()],
            enable_secretary=True,
        )

        mgr._start_meeting("Important Topic")

        mock_sec.start_meeting.assert_called_once()
        assert "conversation_mode" in mock_sec.meeting_metadata


# ============================================================================
# Tests from test_swarm_manager_commands.py
# ============================================================================


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


# ============================================================================
# Tests from test_swarm_manager_core.py
# ============================================================================


def test_extract_agent_response_tool_call_json(monkeypatch):
    import spds.swarm_manager as sm

    mgr = sm.SwarmManager.__new__(sm.SwarmManager)

    # Tool call with valid JSON yields that message
    tc = _ToolCall("send_message", '{"message": "Hello via tool"}')
    msg = _make_msg(tool_calls=[tc])
    resp = _Resp([msg])

    text = sm.SwarmManager._extract_agent_response(mgr, resp)
    assert text == "Hello via tool"


def test_extract_agent_response_tool_call_bad_json_falls_back(monkeypatch):
    import spds.swarm_manager as sm

    mgr = sm.SwarmManager.__new__(sm.SwarmManager)

    # Bad JSON in tool call; assistant message should be used
    tc = _ToolCall("send_message", '{bad json}')
    assistant = _make_msg(message_type="assistant_message", content="Assistant says hi")
    resp = _Resp([_make_msg(tool_calls=[tc]), assistant])

    text = sm.SwarmManager._extract_agent_response(mgr, resp)
    assert text == "Assistant says hi"


def test_extract_agent_response_tool_return(monkeypatch):
    import spds.swarm_manager as sm

    mgr = sm.SwarmManager.__new__(sm.SwarmManager)

    msg = _make_msg(tool_return="tool output")
    resp = _Resp([msg])
    text = sm.SwarmManager._extract_agent_response(mgr, resp)
    assert isinstance(text, str)


def test_extract_agent_response_list_content_variants(monkeypatch):
    import spds.swarm_manager as sm

    mgr = sm.SwarmManager.__new__(sm.SwarmManager)

    # Content list with .text
    item_with_text = SimpleNamespace(text="from .text")
    msg1 = _make_msg(content=[item_with_text])
    text1 = sm.SwarmManager._extract_agent_response(mgr, _Resp([msg1]))
    assert text1 == "from .text"

    # Content list with dict {'text': ...}
    msg2 = _make_msg(content=[{"text": "from dict"}])
    text2 = sm.SwarmManager._extract_agent_response(mgr, _Resp([msg2]))
    assert text2 == "from dict"


def test_extract_agent_response_fallback_when_empty(monkeypatch):
    import spds.swarm_manager as sm

    mgr = sm.SwarmManager.__new__(sm.SwarmManager)
    # No usable content
    msg = _make_msg()
    text = sm.SwarmManager._extract_agent_response(mgr, _Resp([msg]))
    assert isinstance(text, str) and len(text) > 0


# ============================================================================
# Tests from test_swarm_manager_coverage_boost.py
# ============================================================================


class StubSecretary:
    def __init__(self, client=None, mode="adaptive"):
        # Optionally raise to simulate failure in specific tests
        pass

    def observe_message(self, name, message):
        pass

    def start_meeting(self, topic, participants, meeting_type):
        pass

    def generate_minutes(self):
        return "MINUTES"

    def set_mode(self, mode):
        self.mode = mode

    def add_action_item(self, desc):
        pass

    def get_conversation_stats(self):
        return {"turns": 1}

    meeting_metadata = {}
    conversation_log = []
    action_items = []
    decisions = []
    mode = "formal"


class FakeExportManager:
    def export_meeting_minutes(self, meeting_data, mode):
        return "/tmp/minutes.md"

    def export_raw_transcript(self, log, meta):
        return "/tmp/t.txt"

    def export_action_items(self, items, meta):
        return "/tmp/a.json"

    def export_executive_summary(self, meeting_data):
        return "/tmp/s.txt"

    def export_complete_package(self, meeting_data, mode):
        return ["f1", "f2"]


def test_handle_export_command_all_formats_and_error(capsys):
    # Base manager with secretary
    mgr = object.__new__(SwarmManager)
    sec = StubSecretary()
    mgr.secretary = sec
    mgr.export_manager = FakeExportManager()
    sec.meeting_metadata = {}
    sec.conversation_log = []
    sec.action_items = []
    sec.decisions = []

    # casual
    mgr._handle_export_command("casual")
    # transcript
    mgr._handle_export_command("transcript")
    # actions
    mgr._handle_export_command("actions")
    # summary
    mgr._handle_export_command("summary")
    # all
    mgr._handle_export_command("all")

    # error path
    class RaisingExportManager(FakeExportManager):
        def export_meeting_minutes(self, *a, **k):
            raise RuntimeError("x")

    mgr.export_manager = RaisingExportManager()
    mgr._handle_export_command("minutes")
    out = capsys.readouterr().out
    assert "Export failed" in out or "❌ Export failed" in out


def test_offer_export_options_with_choice_and_eof(monkeypatch):
    mgr = object.__new__(SwarmManager)
    mgr.secretary = StubSecretary()
    called = {}
    mgr._handle_secretary_commands = lambda choice: called.setdefault("cmd", choice)

    # First time: provide a valid command
    monkeypatch.setattr(builtins, "input", lambda prompt="": "/export minutes")
    mgr._offer_export_options()
    assert called.get("cmd") == "/export minutes"

    # Second: simulate EOFError path
    def raise_eof(prompt=""):
        raise EOFError

    monkeypatch.setattr(builtins, "input", raise_eof)
    mgr._offer_export_options()  # Should not raise


def test_check_memory_awareness_status_prints(monkeypatch, capsys):
    # First agent returns a message, second raises
    msgs = ["INFO MESSAGE", Exception("nope")]

    def fake_create_awareness(client, agent):
        effect = msgs.pop(0)
        if isinstance(effect, Exception):
            raise effect
        return effect

    monkeypatch.setattr(
        "spds.swarm_manager.create_memory_awareness_for_agent", fake_create_awareness
    )

    class A:
        def __init__(self, id_, name):
            class Inner:
                def __init__(self, id_):
                    self.id = id_

            self.agent = Inner(id_)
            self.name = name

    mgr = object.__new__(SwarmManager)
    mgr.client = object()
    mgr.agents = [A("1", "One"), A("2", "Two")]

    mgr.check_memory_awareness_status(silent=False)
    out = capsys.readouterr().out
    assert (
        "Memory Awareness Information Available" in out or "Could not generate" in out
    )


def test_start_meeting_sets_metadata_and_history():
    mgr = object.__new__(SwarmManager)
    mgr.conversation_history = ""
    a = types.SimpleNamespace(name="A")
    b = types.SimpleNamespace(name="B")
    mgr.agents = [a, b]
    sec = StubSecretary()
    sec.meeting_metadata = {}
    mgr.secretary = sec
    mgr.meeting_type = "discussion"
    mgr.conversation_mode = "hybrid"

    mgr._start_meeting("Topic")
    assert "System: The topic is 'Topic'" in mgr.conversation_history
    assert sec.meeting_metadata.get("conversation_mode") == "hybrid"


def test_memory_status_summary_high_memory_and_error():
    class AgentsCtx:
        def retrieve(self, agent_id=None):
            # Return high memory once, then raise
            if not hasattr(self, "called"):
                self.called = 1
                return {"num_recall_memory": 600, "num_archival_memory": 5}
            raise Exception("nope")

    client = types.SimpleNamespace(agents=types.SimpleNamespace(context=AgentsCtx()))

    class A:
        def __init__(self, id_, name):
            class Inner:
                def __init__(self, id_):
                    self.id = id_

            self.agent = Inner(id_)
            self.name = name

    mgr = object.__new__(SwarmManager)
    mgr.client = client
    mgr.agents = [A("1", "One"), A("2", "Two")]
    summary = mgr.get_memory_status_summary()
    assert summary["agents_with_high_memory"] == 1
    assert len(summary["agents_status"]) == 2


def test_extract_agent_response_tool_return_and_break(monkeypatch):
    mgr = object.__new__(SwarmManager)

    class Msg:
        def __init__(self, **kw):
            for k, v in kw.items():
                setattr(self, k, v)

    class TF:
        def __init__(self, name, arguments):
            self.name = name
            self.arguments = arguments

    class TC:
        def __init__(self, f):
            self.function = f

    # tool_return present -> continue and default fallback
    resp1 = types.SimpleNamespace(messages=[Msg(tool_return=True)])
    fallback = mgr._extract_agent_response(resp1)
    assert "trouble phrasing" in fallback

    # extraction_successful -> break early on second message
    tf = TF("send_message", '{"message": "X"}')
    msg_tool = Msg(tool_calls=[TC(tf)])
    msg_other = Msg(role="assistant", content="Should not be seen")
    resp2 = types.SimpleNamespace(messages=[msg_tool, msg_other])
    assert mgr._extract_agent_response(resp2) == "X"


def test_handle_secretary_commands_help_without_secretary(capsys):
    mgr = object.__new__(SwarmManager)
    mgr._secretary = None
    mgr.secretary_agent_id = None
    assert mgr._handle_secretary_commands("/help") is True
    out = capsys.readouterr().out
    assert "Available Commands" in out


def test_handle_secretary_commands_stats_and_action_item(capsys):
    class Sec:
        def get_conversation_stats(self):
            return {"turns": 2}

        def add_action_item(self, desc):
            self.added = desc

        def set_mode(self, m):
            self.m = m

        meeting_metadata = {}
        conversation_log = []
        action_items = []
        decisions = []

    mgr = object.__new__(SwarmManager)
    mgr.secretary = Sec()
    # stats
    assert mgr._handle_secretary_commands("/stats") is True
    # action-item with arg
    assert mgr._handle_secretary_commands("/action-item test it") is True
    # action-item without arg prints usage
    assert mgr._handle_secretary_commands("/action-item") is True


def test_update_agent_memories_all_fail_prints(capsys, monkeypatch):
    class Msgs:
        def __init__(self):
            self.calls = 0

        def create(self, agent_id=None, messages=None):
            self.calls += 1
            raise Exception("hard error")

    class Agents:
        def __init__(self):
            self.messages = Msgs()

    class C:
        def __init__(self):
            self.agents = Agents()

    class Agent:
        def __init__(self):
            class A:
                id = "id"

            self.agent = A()
            self.name = "N"

    mgr = object.__new__(SwarmManager)
    mgr.client = C()
    mgr.agents = [Agent()]
    # Patch sleep to avoid delay
    monkeypatch.setattr(__import__("time"), "sleep", lambda s: None)
    mgr._reset_agent_messages = lambda _: None
    mgr._update_agent_memories("m", max_retries=2)
    out = capsys.readouterr().out
    assert "Failed to update" in out


# ============================================================================
# Tests from test_swarm_manager_generated.py
# ============================================================================


class DummyMessages:
    def __init__(
        self, create_side_effect=None, list_side_effect=None, reset_side_effect=None
    ):
        self.create_calls = []
        self.create_side_effect = create_side_effect or []
        self.list_side_effect = list_side_effect
        self.reset_side_effect = reset_side_effect

    def create(self, agent_id, messages):
        self.create_calls.append((agent_id, messages))
        if self.create_side_effect:
            effect = self.create_side_effect.pop(0)
            if isinstance(effect, Exception):
                raise effect
            return effect
        return None

    def reset(self, agent_id):
        if self.reset_side_effect:
            if isinstance(self.reset_side_effect, Exception):
                raise self.reset_side_effect
        return None

    def list(self, agent_id, limit=1000):
        if callable(self.list_side_effect):
            return self.list_side_effect()
        if isinstance(self.list_side_effect, Exception):
            raise self.list_side_effect
        return self.list_side_effect or []


class DummyAgentsClient:
    def __init__(self, retrieve_side_effect=None, list_result=None, messages=None):
        self.retrieve_side_effect = retrieve_side_effect
        self._list_result = list_result or []
        self.messages = messages or DummyMessages()

    def retrieve(self, agent_id=None):
        if isinstance(self.retrieve_side_effect, Exception):
            raise self.retrieve_side_effect
        return self.retrieve_side_effect

    def list(self, name=None, limit=1):
        return self._list_result


class DummyClient:
    def __init__(self, agents_client):
        self.agents = agents_client


class FakeAgentObj:
    def __init__(self, id_, name, priority=1.0):
        class A:
            def __init__(self, id_):
                self.id = id_

        self.agent = A(id_)
        self.name = name
        self.motivation_score = 0
        self.priority_score = priority

    def assess_motivation_and_priority(self, topic):
        # For tests we toggle priority based on stored attribute
        return None


def make_manager_with_agent(fake_messages):
    client = DummyClient(DummyAgentsClient(messages=fake_messages))
    mgr = object.__new__(SwarmManager)
    mgr.client = client
    mgr.agents = [FakeAgentObj("agent-1", "Alice")]
    mgr.enable_secretary = False
    mgr.secretary = None
    mgr.export_manager = None
    mgr.conversation_mode = "hybrid"
    return mgr


def test_update_agent_memories_retries_and_token_reset(monkeypatch):
    # Simulate create raising 500, then max_tokens, then succeeding
    msgs = DummyMessages(
        create_side_effect=[
            Exception("500 error"),
            Exception("max_tokens exceeded"),
            None,
        ]
    )
    mgr = make_manager_with_agent(msgs)

    # Patch sleep to avoid delays
    monkeypatch.setattr(time, "sleep", lambda s: None)

    reset_calls = []

    def fake_reset(agent_id):
        reset_calls.append(agent_id)

    mgr._reset_agent_messages = fake_reset

    # Call the method; should ultimately succeed without raising
    mgr._update_agent_memories("hello", speaker="User", max_retries=3)

    # Verify messages.create was called at least twice and reset called once
    assert len(msgs.create_calls) >= 2
    assert reset_calls == [mgr.agents[0].agent.id]


def test_get_agent_message_count_handles_exception(capsys):
    msgs = DummyMessages(list_side_effect=Exception("nope"))
    client = DummyClient(DummyAgentsClient(messages=msgs))
    mgr = object.__new__(SwarmManager)
    mgr.client = client

    count = mgr._get_agent_message_count("agent-99")
    assert count == 0
    captured = capsys.readouterr()
    assert "Failed to get message count" in captured.out


def test_extract_agent_response_various_shapes():
    mgr = object.__new__(SwarmManager)

    class Msg:
        def __init__(self, **kwargs):
            for k, v in kwargs.items():
                setattr(self, k, v)

    class ToolFunction:
        def __init__(self, name, arguments):
            self.name = name
            self.arguments = arguments

    class ToolCall:
        def __init__(self, function):
            self.function = function

    # Case 1: tool_calls with valid JSON and message
    tf = ToolFunction("send_message", json.dumps({"message": "Hello from tool"}))
    msg1 = Msg(tool_calls=[ToolCall(tf)])
    resp = type("R", (), {"messages": [msg1]})
    assert mgr._extract_agent_response(resp) == "Hello from tool"

    # Case 2: tool_calls with invalid JSON -> fallthrough to default message
    tf2 = ToolFunction("send_message", "{bad json")
    msg2 = Msg(tool_calls=[ToolCall(tf2)])
    resp2 = type("R", (), {"messages": [msg2]})
    assert "trouble phrasing" in mgr._extract_agent_response(resp2)

    # Case 3: assistant message with content string
    msg3 = Msg(message_type="assistant_message", content="Assistant text")
    resp3 = type("R", (), {"messages": [msg3]})
    assert mgr._extract_agent_response(resp3) == "Assistant text"

    # Case 4: content list with dict
    msg4 = Msg(role="assistant", content=[{"text": "Dict text"}])
    resp4 = type("R", (), {"messages": [msg4]})
    assert mgr._extract_agent_response(resp4) == "Dict text"

    # Case 5: content list with object with text attribute
    class CI:
        def __init__(self, text):
            self.text = text

    msg5 = Msg(role="assistant", content=[CI("Object text")])
    resp5 = type("R", (), {"messages": [msg5]})
    assert mgr._extract_agent_response(resp5) == "Object text"

    # Case 6: empty messages -> default
    resp6 = type("R", (), {"messages": []})
    assert "trouble phrasing" in mgr._extract_agent_response(resp6)


# ============================================================================
# Tests from test_swarm_manager_modes.py
# ============================================================================


def test_secretary_commands_without_secretary():
    mgr = object.__new__(SwarmManager)
    mgr._secretary = None
    mgr.secretary_agent_id = None
    # Commands that should warn and return True
    assert mgr._handle_secretary_commands("/minutes") is True
    assert mgr._handle_secretary_commands("/export") is True
    # Unknown command returns False
    assert mgr._handle_secretary_commands("/unknown") is False


def test_export_command_without_secretary(capsys):
    mgr = object.__new__(SwarmManager)
    mgr._secretary = None
    mgr.secretary_agent_id = None
    mgr.pending_nomination = None
    mgr._handle_export_command("")
    out = capsys.readouterr().out
    assert "Secretary not available" in out


# ============================================================================
# Tests from test_swarm_manager_more.py
# ============================================================================


class FakeAgent2:
    def __init__(self, id_, name, text=None, raise_on_speak=False):
        class A:
            def __init__(self, id_):
                self.id = id_

        self.agent = A(id_)
        self.name = name
        self.motivation_score = 1
        self.priority_score = 1.0
        self.text = text
        self.raise_on_speak = raise_on_speak

    def assess_motivation_and_priority(self, topic):
        # leave priority_score as-is
        return None

    def speak(self, conversation_history=None):
        if self.raise_on_speak:
            raise Exception("speak failed")
        if isinstance(self.text, str):
            return types.SimpleNamespace(
                messages=[
                    SimpleNamespace(role="assistant", content=self.text)
                ]
            )
        return types.SimpleNamespace(
            messages=[SimpleNamespace(role="assistant", content=[{"text": self.text}])]
        )


def test_get_memory_status_summary_success_and_error():
    # client.agents.context.retrieve returns dict for first, raises for second
    def retrieve_good(agent_id):
        return {"num_recall_memory": 10, "num_archival_memory": 2}

    def retrieve_bad(agent_id):
        raise Exception("nope")

    class AgentsCtx:
        def __init__(self, funcs):
            self.funcs = funcs

        def retrieve(self, agent_id=None):
            # pop from funcs
            f = self.funcs.pop(0)
            return f(agent_id)

    client = types.SimpleNamespace(
        agents=types.SimpleNamespace(context=AgentsCtx([retrieve_good, retrieve_bad]))
    )
    mgr = object.__new__(SwarmManager)
    mgr.client = client
    mgr.agents = [FakeAgent2("id1", "A"), FakeAgent2("id2", "B")]

    summary = mgr.get_memory_status_summary()
    assert summary["total_agents"] == 2
    # first agent should have numeric recall_memory, second should have error entry
    assert any(
        "error" in s or isinstance(s.get("recall_memory"), int)
        for s in summary["agents_status"]
    )


def test_handle_export_command_various_formats(capsys):
    class FakeExportManager2:
        def export_meeting_minutes(self, meeting_data, mode):
            return f"/tmp/minutes-{mode}.md"

        def export_raw_transcript(self, conv_log, meta):
            return "/tmp/transcript.txt"

        def export_action_items(self, items, meta):
            return "/tmp/actions.json"

        def export_executive_summary(self, meeting_data):
            return "/tmp/summary.txt"

        def export_complete_package(self, meeting_data, mode):
            return ["a", "b"]

    class FakeSecretary2:
        def __init__(self):
            self.meeting_metadata = {}
            self.conversation_log = []
            self.action_items = []
            self.decisions = []
            self.mode = "formal"
            self._observed = []

        def observe_message(self, name, msg):
            self._observed.append((name, msg))

        def get_conversation_stats(self):
            return {"turns": 3}

    mgr = object.__new__(SwarmManager)
    sec = FakeSecretary2()
    mgr.secretary = sec
    mgr.export_manager = FakeExportManager2()

    # minutes
    mgr._handle_export_command("formal")
    out = capsys.readouterr().out
    assert "Exported" in out or "✅" in out

    # unknown format
    mgr._handle_export_command("unknown-format")
    out2 = capsys.readouterr().out
    assert "Unknown export format" in out2 or "❌ Unknown export format" in out2
