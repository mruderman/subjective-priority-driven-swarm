import types

import pytest

from spds import swarm_manager


def test_start_chat_eof_inner_loop(monkeypatch, capsys):
    mgr = object.__new__(swarm_manager.SwarmManager)
    mgr.conversation_mode = "hybrid"
    mgr._start_meeting = lambda topic: None
    mgr._agent_turn = lambda topic: None
    mgr._end_meeting = lambda: None
    mgr._handle_secretary_commands = lambda s: False
    mgr._secretary = None
    mgr.secretary_agent_id = None

    # First call returns a topic, second call simulates Ctrl+D (EOF)
    seq = iter(["some topic"])

    def input_stub(prompt=""):
        try:
            return next(seq)
        except StopIteration:
            raise EOFError()

    monkeypatch.setattr(__import__("builtins"), "input", input_stub)
    mgr.start_chat()
    out = capsys.readouterr().out
    assert "Exiting chat." in out


def test_start_chat_with_topic_eof_inner_loop(monkeypatch, capsys):
    mgr = object.__new__(swarm_manager.SwarmManager)
    mgr.conversation_mode = "hybrid"
    mgr._start_meeting = lambda topic: None
    mgr._agent_turn = lambda topic: None
    mgr._end_meeting = lambda: None
    mgr._handle_secretary_commands = lambda s: False
    mgr._secretary = None
    mgr.secretary_agent_id = None
    mgr.pending_nomination = None

    # Simulate EOF immediately in the inner loop
    def input_stub(prompt=""):
        raise EOFError()

    monkeypatch.setattr(__import__("builtins"), "input", input_stub)
    mgr.start_chat_with_topic("T")
    out = capsys.readouterr().out
    assert "Exiting chat." in out


def test_start_chat_secretary_command_continue(monkeypatch, capsys):
    mgr = object.__new__(swarm_manager.SwarmManager)
    mgr.conversation_mode = "hybrid"
    mgr._start_meeting = lambda topic: None
    mgr._agent_turn = lambda topic: None
    mgr._end_meeting = lambda: None
    mgr._secretary = None
    mgr.secretary_agent_id = None

    # Inputs: topic, a secretary-command which should be handled and cause 'continue', then quit
    seq = iter(["topic", "/minutes", "quit"])

    def input_stub(prompt=""):
        try:
            return next(seq)
        except StopIteration:
            raise EOFError()

    monkeypatch.setattr(__import__("builtins"), "input", input_stub)
    mgr.start_chat()
    out = capsys.readouterr().out
    assert "Secretary is not enabled" in out or "❌ Secretary is not enabled" in out
    assert "Exiting chat." in out


def test_start_chat_observe_message_called(monkeypatch):
    mgr = object.__new__(swarm_manager.SwarmManager)
    mgr.conversation_mode = "hybrid"
    mgr._start_meeting = lambda topic: None
    mgr._agent_turn = lambda topic: None
    mgr._end_meeting = lambda: None
    mgr._handle_secretary_commands = lambda s: False
    # Initialize attributes used by start_chat
    mgr.conversation_history = ""
    mgr.last_speaker = None
    mgr.meeting_type = "discussion"
    mgr.conversation_mode = "hybrid"
    flag = types.SimpleNamespace(called=False)

    def observe(who, msg):
        flag.called = True

    mgr.secretary = types.SimpleNamespace(
        agent=types.SimpleNamespace(name="Sec"),
        mode="adaptive",
        observe_message=observe,
    )

    seq = iter(["topic", "hello", "quit"])

    def input_stub(prompt=""):
        try:
            return next(seq)
        except StopIteration:
            raise EOFError()

    monkeypatch.setattr(__import__("builtins"), "input", input_stub)
    mgr.start_chat()
    assert flag.called is True


def test_reset_agent_messages_success(capsys):
    class Msgs:
        def reset(self, agent_id=None):
            return None

    class Agents:
        def __init__(self):
            self.messages = Msgs()

    mgr = object.__new__(swarm_manager.SwarmManager)
    mgr.client = types.SimpleNamespace(agents=Agents())
    mgr._reset_agent_messages("xyz")
    out = capsys.readouterr().out
    assert "Successfully reset messages for agent xyz" in out
