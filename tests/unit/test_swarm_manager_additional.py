import json
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

from spds.swarm_manager import SwarmManager


def _sample_profile(name="Agent X"):
    return {
        "name": name,
        "persona": "A short persona",
        "expertise": ["testing"],
        "model": "openai/gpt-4",
        "embedding": "openai/text-embedding-ada-002",
    }


def test_extract_agent_response_prefers_tool_call(mock_letta_client):
    """_swarm_manager._extract_agent_response should prefer a send_message tool call."""
    with patch("spds.swarm_manager.SPDSAgent.create_new") as mock_create:
        mock_agent = Mock()
        mock_agent.name = "A"
        mock_agent.agent = SimpleNamespace(id="a1")
        mock_create.return_value = mock_agent

        mgr = SwarmManager(client=mock_letta_client, agent_profiles=[_sample_profile()])

        # Build a synthetic response that mimics a tool call to send_message
        tool_call = SimpleNamespace(function=SimpleNamespace(name="send_message", arguments=json.dumps({"message": "hello tool"})))
        message = SimpleNamespace(tool_calls=[tool_call], tool_return=None, message_type="tool_message", content=None)
        response = SimpleNamespace(messages=[message])

        extracted = mgr._extract_agent_response(response)
        assert "hello tool" in extracted


def test_handle_secretary_commands_memory_status_prints_summary(mock_letta_client, capsys):
    """/memory-status should call get_memory_status_summary and print objective info."""
    with patch("spds.swarm_manager.SPDSAgent.create_new") as mock_create:
        mock_agent = Mock()
        mock_agent.name = "A"
        mock_agent.agent = SimpleNamespace(id="a1")
        mock_create.return_value = mock_agent

        # make the client return simple context info
        mock_letta_client.agents.context.retrieve.return_value = {"num_recall_memory": 5, "num_archival_memory": 1}

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

        mgr = SwarmManager(client=mock_letta_client, agent_profiles=[_sample_profile()], enable_secretary=True)

        mgr._start_meeting("Important Topic")

        mock_sec.start_meeting.assert_called_once()
        assert "conversation_mode" in mock_sec.meeting_metadata
