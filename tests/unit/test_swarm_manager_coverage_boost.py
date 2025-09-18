import builtins
import types
import pytest

from letta_client.errors import NotFoundError

from spds import swarm_manager


class StubSPDSAgent:
    def __init__(self, state, client):
        # emulate attributes used elsewhere
        class A:
            def __init__(self, id_):
                self.id = id_

        self.agent = A(getattr(state, "id", "stub-id"))
        self.name = getattr(state, "name", "Stub")
        self.motivation_score = 0
        self.priority_score = 0.0

    @classmethod
    def create_new(cls, name, persona, expertise, client, model=None, embedding=None):
        s = types.SimpleNamespace(id=f"{name}-id", name=name)
        return cls(s, client)


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


def make_client_for_ids(sequence):
    class Agents:
        def __init__(self, seq):
            self._seq = list(seq)

        def retrieve(self, agent_id=None):
            effect = self._seq.pop(0)
            if isinstance(effect, Exception):
                raise effect
            return effect

    return types.SimpleNamespace(agents=Agents(sequence))


def make_client_for_names(list_result):
    class Agents:
        def list(self, name=None, limit=1):
            return list_result

    return types.SimpleNamespace(agents=Agents())


def test_init_invalid_mode_raises(monkeypatch):
    monkeypatch.setattr(swarm_manager, "SPDSAgent", StubSPDSAgent)
    client = make_client_for_ids([types.SimpleNamespace(id="ok", name="A")])
    with pytest.raises(ValueError):
        swarm_manager.SwarmManager(
            client, agent_ids=["ok"], conversation_mode="not-a-mode"
        )


def test_secretary_init_failure_sets_flag_false(monkeypatch):
    # Make secretary raise during __init__
    class RaisingSecretary:
        def __init__(self, *a, **kw):
            raise RuntimeError("boom")

    monkeypatch.setattr(swarm_manager, "SPDSAgent", StubSPDSAgent)
    monkeypatch.setattr(swarm_manager, "SecretaryAgent", RaisingSecretary)
    client = make_client_for_ids([types.SimpleNamespace(id="ok", name="A")])
    mgr = swarm_manager.SwarmManager(
        client, agent_ids=["ok"], enable_secretary=True, secretary_mode="adaptive"
    )
    assert mgr.enable_secretary is False


def test_load_agents_by_id_not_found_then_success(monkeypatch):
    monkeypatch.setattr(swarm_manager, "SPDSAgent", StubSPDSAgent)
    # First NotFoundError, then valid object
    client = make_client_for_ids([NotFoundError("missing"), types.SimpleNamespace(id="ok2", name="B")])
    mgr = swarm_manager.SwarmManager(client, agent_ids=["missing", "ok2"], conversation_mode="hybrid")
    # One agent should be loaded
    assert len(mgr.agents) == 1 and mgr.agents[0].name == "B"


def test_load_agents_by_name_warning_and_success(monkeypatch, capsys):
    monkeypatch.setattr(swarm_manager, "SPDSAgent", StubSPDSAgent)
    # First call returns empty, second returns one
    class Agents:
        def __init__(self):
            self.calls = 0

        def list(self, name=None, limit=1):
            self.calls += 1
            if self.calls == 1:
                return []
            return [types.SimpleNamespace(id="x", name="Found")] 

    client = types.SimpleNamespace(agents=Agents())

    # First: empty triggers warning -> but no agents overall should raise later
    with pytest.raises(ValueError):
        swarm_manager.SwarmManager(client, agent_names=["Nope"])
    out = capsys.readouterr().out
    assert "not found" in out

    # Second: with a found agent
    mgr = swarm_manager.SwarmManager(client, agent_names=["Found"]) 
    assert mgr.agents and mgr.agents[0].name == "Found"


def test_agent_turn_no_motivated_prints(capsys):
    mgr = object.__new__(swarm_manager.SwarmManager)
    a = types.SimpleNamespace(
        name="A",
        priority_score=0.0,
        motivation_score=0,
        assess_motivation_and_priority=lambda t: None,
    )
    mgr.agents = [a]
    mgr.conversation_mode = "hybrid"
    mgr._agent_turn("topic")
    assert "No agent is motivated" in capsys.readouterr().out


def test_all_speak_fallback_on_exception(monkeypatch):
    # Agent speak raises -> fallback path in all_speak
    class A:
        def __init__(self, name):
            class Inner:
                id = "id"

            self.agent = Inner()
            self.name = name
            self.priority_score = 1.0

        def speak(self, conversation_history=None):
            raise RuntimeError("fail")

    mgr = object.__new__(swarm_manager.SwarmManager)
    mgr.agents = [A("A")]
    mgr._update_agent_memories = lambda *a, **k: None
    mgr._notify_secretary_agent_response = lambda *a, **k: None
    mgr.conversation_history = ""

    mgr._all_speak_turn(motivated_agents=mgr.agents, topic="t")
    # fallback message added
    assert any("trouble" in line for line in mgr.conversation_history.splitlines())


def test_handle_export_command_all_formats_and_error(capsys):
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

    # Base manager with secretary
    mgr = object.__new__(swarm_manager.SwarmManager)
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
    mgr = object.__new__(swarm_manager.SwarmManager)
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

    monkeypatch.setattr(swarm_manager, "create_memory_awareness_for_agent", fake_create_awareness)

    class A:
        def __init__(self, id_, name):
            class Inner:
                def __init__(self, id_):
                    self.id = id_

            self.agent = Inner(id_)
            self.name = name

    mgr = object.__new__(swarm_manager.SwarmManager)
    mgr.client = object()
    mgr.agents = [A("1", "One"), A("2", "Two")]

    mgr.check_memory_awareness_status(silent=False)
    out = capsys.readouterr().out
    assert "Memory Awareness Information Available" in out or "Could not generate" in out


def test_start_meeting_sets_metadata_and_history():
    mgr = object.__new__(swarm_manager.SwarmManager)
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


def test_init_from_profiles(monkeypatch):
    monkeypatch.setattr(swarm_manager, "SPDSAgent", StubSPDSAgent)
    client = types.SimpleNamespace()
    profiles = [
        {"name": "P1", "persona": "p", "expertise": ["x"], "model": None, "embedding": None}
    ]
    mgr = swarm_manager.SwarmManager(client, agent_profiles=profiles)
    assert mgr.agents and mgr.agents[0].name == "P1"


def test_handle_secretary_commands_without_secretary(capsys):
    mgr = object.__new__(swarm_manager.SwarmManager)
    mgr.secretary = None
    # Commands that should warn and return True
    assert mgr._handle_secretary_commands("/minutes") is True
    assert mgr._handle_secretary_commands("/export") is True
    # Unknown command returns False
    assert mgr._handle_secretary_commands("/unknown") is False


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

    mgr = object.__new__(swarm_manager.SwarmManager)
    mgr.client = client
    mgr.agents = [A("1", "One"), A("2", "Two")]
    summary = mgr.get_memory_status_summary()
    assert summary["agents_with_high_memory"] == 1
    assert len(summary["agents_status"]) == 2


def test_start_chat_quit_immediately(monkeypatch, capsys):
    mgr = object.__new__(swarm_manager.SwarmManager)
    mgr.conversation_mode = "hybrid"
    mgr._start_meeting = lambda topic: None
    mgr._agent_turn = lambda topic: None
    mgr._end_meeting = lambda: None
    mgr._handle_secretary_commands = lambda s: False
    # secretary None path
    mgr.secretary = None
    # prepare input to always return 'quit' to immediately exit without StopIteration
    monkeypatch.setattr(__import__("builtins"), "input", lambda prompt="": "quit")
    mgr.start_chat()
    out = capsys.readouterr().out
    assert "Swarm chat started" in out and "Exiting chat." in out


def test_start_chat_with_topic_secretary_banner_and_quit(monkeypatch, capsys):
    class Sec:
        def __init__(self):
            class A:
                name = "SecName"

            self.agent = A()
            self.mode = "adaptive"

    mgr = object.__new__(swarm_manager.SwarmManager)
    mgr.conversation_mode = "hybrid"
    mgr._start_meeting = lambda topic: None
    mgr._agent_turn = lambda topic: None
    mgr._end_meeting = lambda: None
    mgr._handle_secretary_commands = lambda s: False
    mgr.secretary = Sec()
    # Always return 'quit' so the loop exits cleanly
    monkeypatch.setattr(__import__("builtins"), "input", lambda prompt="": "quit")
    mgr.start_chat_with_topic("T")
    out = capsys.readouterr().out
    assert "Secretary: SecName" in out and "Exiting chat." in out


def test_extract_agent_response_tool_return_and_break(monkeypatch):
    mgr = object.__new__(swarm_manager.SwarmManager)

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
    tf = TF("send_message", "{\"message\": \"X\"}")
    msg_tool = Msg(tool_calls=[TC(tf)])
    msg_other = Msg(role="assistant", content="Should not be seen")
    resp2 = types.SimpleNamespace(messages=[msg_tool, msg_other])
    assert mgr._extract_agent_response(resp2) == "X"


def test_hybrid_turn_initial_exception_and_instruction_error(monkeypatch, capsys):
    class A:
        def __init__(self, name, raise_on_speak=False):
            class Inner:
                id = "id"

            self.agent = Inner()
            self.name = name
            self.priority_score = 1.0
            self.expertise = "testing"
            self._raise = raise_on_speak

        def speak(self, conversation_history=None):
            if self._raise:
                raise RuntimeError("boom")
            return types.SimpleNamespace(messages=[types.SimpleNamespace(role="assistant", content="short")])

    mgr = object.__new__(swarm_manager.SwarmManager)
    # client create will error to cover instruction error branch
    class Msgs:
        def create(self, **k):
            raise RuntimeError("fail-create")

    mgr.client = types.SimpleNamespace(agents=types.SimpleNamespace(messages=Msgs()))
    mgr.conversation_history = ""
    mgr._notify_secretary_agent_response = lambda *a, **k: None

    # First agent raises in initial phase -> fallback; second yields short -> fallback too
    a1 = A("A", raise_on_speak=True)
    a2 = A("B", raise_on_speak=False)
    mgr.agents = [a1, a2]
    mgr._hybrid_turn([a1, a2], "topic")
    out = capsys.readouterr().out
    assert "Error in initial response attempt" in out or "As someone with expertise" in out


def test_handle_secretary_commands_help_without_secretary(capsys):
    mgr = object.__new__(swarm_manager.SwarmManager)
    mgr.secretary = None
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

    mgr = object.__new__(swarm_manager.SwarmManager)
    mgr.secretary = Sec()
    # stats
    assert mgr._handle_secretary_commands("/stats") is True
    # action-item with arg
    assert mgr._handle_secretary_commands("/action-item test it") is True
    # action-item without arg prints usage
    assert mgr._handle_secretary_commands("/action-item") is True


def test_pure_priority_turn_success():
    class A:
        def __init__(self, name):
            class Inner:
                id = "id"

            self.agent = Inner()
            self.name = name
            self.priority_score = 1.0

        def speak(self, conversation_history=None):
            return types.SimpleNamespace(messages=[types.SimpleNamespace(role="assistant", content="OK")])

    mgr = object.__new__(swarm_manager.SwarmManager)
    mgr.conversation_history = ""
    mgr._notify_secretary_agent_response = lambda *a, **k: None
    a = A("A")
    mgr._pure_priority_turn([a], "t")
    assert "A: OK" in mgr.conversation_history


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

    mgr = object.__new__(swarm_manager.SwarmManager)
    mgr.client = C()
    mgr.agents = [Agent()]
    # Patch sleep to avoid delay
    monkeypatch.setattr(__import__("time"), "sleep", lambda s: None)
    mgr._reset_agent_messages = lambda _: None
    mgr._update_agent_memories("m", max_retries=2)
    out = capsys.readouterr().out
    assert "Failed to update" in out
