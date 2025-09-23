import json
import time

import pytest
from letta_client.errors import NotFoundError

from spds import swarm_manager


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
    mgr = object.__new__(swarm_manager.SwarmManager)
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


def test_reset_agent_messages_handles_exception(capsys):
    msgs = DummyMessages(reset_side_effect=Exception("boom"))
    client = DummyClient(DummyAgentsClient(messages=msgs))
    mgr = object.__new__(swarm_manager.SwarmManager)
    mgr.client = client

    # Should not raise
    mgr._reset_agent_messages("agent-42")
    captured = capsys.readouterr()
    assert "Failed to reset messages" in captured.out


def test_get_agent_message_count_handles_exception(capsys):
    msgs = DummyMessages(list_side_effect=Exception("nope"))
    client = DummyClient(DummyAgentsClient(messages=msgs))
    mgr = object.__new__(swarm_manager.SwarmManager)
    mgr.client = client

    count = mgr._get_agent_message_count("agent-99")
    assert count == 0
    captured = capsys.readouterr()
    assert "Failed to get message count" in captured.out


def test_warm_up_agent_success_and_failure(monkeypatch):
    # Success case
    msgs = DummyMessages()
    client = DummyClient(DummyAgentsClient(messages=msgs))
    mgr = object.__new__(swarm_manager.SwarmManager)
    mgr.client = client

    class Agent:
        def __init__(self, id_, name):
            class A:
                def __init__(self, id_):
                    self.id = id_

            self.agent = A(id_)
            self.name = name

    agent = Agent("ag-1", "Bob")
    # Should return True on success
    assert mgr._warm_up_agent(agent, "topic") is True

    # Failure case: create raises
    msgs_fail = DummyMessages(create_side_effect=[Exception("network")])
    client_fail = DummyClient(DummyAgentsClient(messages=msgs_fail))
    mgr.client = client_fail
    assert mgr._warm_up_agent(agent, "topic") is False


def test_agent_turn_dispatches_modes(monkeypatch):
    # Create manager and inject two fake agents with different priorities
    mgr = object.__new__(swarm_manager.SwarmManager)
    mgr.client = None
    a1 = FakeAgentObj("id1", "A", priority=1.0)
    a2 = FakeAgentObj("id2", "B", priority=0.0)

    # a1 will report priority>0
    def assess(topic):
        a1.priority_score = 0.9
        a2.priority_score = 0.0

    a1.assess_motivation_and_priority = assess
    a2.assess_motivation_and_priority = assess
    mgr.agents = [a1, a2]

    called = {}

    def mark(name):
        def _fn(motivated_agents, topic):
            called[name] = True

        return _fn

    mgr._hybrid_turn = mark("hybrid")
    mgr._all_speak_turn = mark("all_speak")
    mgr._sequential_turn = mark("sequential")
    mgr._pure_priority_turn = mark("pure_priority")

    mgr.conversation_mode = "hybrid"
    mgr._agent_turn("t")
    assert called.get("hybrid")

    called.clear()
    mgr.conversation_mode = "all_speak"
    mgr._agent_turn("t")
    assert called.get("all_speak")

    called.clear()
    mgr.conversation_mode = "sequential"
    mgr._agent_turn("t")
    assert called.get("sequential")

    called.clear()
    mgr.conversation_mode = "pure_priority"
    mgr._agent_turn("t")
    assert called.get("pure_priority")

    # Unknown mode should fallback to sequential
    called.clear()
    mgr.conversation_mode = "unknown-mode"
    mgr._agent_turn("t")
    assert called.get("sequential")


def test_extract_agent_response_various_shapes():
    mgr = object.__new__(swarm_manager.SwarmManager)

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
