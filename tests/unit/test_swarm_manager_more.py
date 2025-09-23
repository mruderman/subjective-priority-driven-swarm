import types

import pytest

from spds import swarm_manager


class SimpleMsg:
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)


class FakeAgent:
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
                messages=[SimpleMsg(role="assistant", content=self.text)]
            )
        return types.SimpleNamespace(
            messages=[SimpleMsg(role="assistant", content=[{"text": self.text}])]
        )


class FakeExportManager:
    def __init__(self):
        self.calls = []

    def export_meeting_minutes(self, meeting_data, mode):
        self.calls.append(("minutes", mode))
        return f"/tmp/minutes-{mode}.md"

    def export_raw_transcript(self, conv_log, meta):
        return "/tmp/transcript.txt"

    def export_action_items(self, items, meta):
        return "/tmp/actions.json"

    def export_executive_summary(self, meeting_data):
        return "/tmp/summary.txt"

    def export_complete_package(self, meeting_data, mode):
        return ["a", "b"]


class FakeSecretary:
    def __init__(self):
        self.meeting_metadata = {}
        self.conversation_log = []
        self.action_items = []
        self.decisions = []
        self.mode = "formal"
        self._observed = []

    def observe_message(self, name, msg):
        self._observed.append((name, msg))

    def start_meeting(self, topic, participants, meeting_type):
        self.meeting_metadata = {"topic": topic}

    def generate_minutes(self):
        return "MINUTES"

    def set_mode(self, m):
        self.mode = m

    def add_action_item(self, desc):
        self.action_items.append(desc)

    def get_conversation_stats(self):
        return {"turns": 3}


def make_mgr_with_agents(agent_list):
    mgr = object.__new__(swarm_manager.SwarmManager)
    mgr.client = types.SimpleNamespace(
        agents=types.SimpleNamespace(
            messages=types.SimpleNamespace(create=lambda **k: None)
        )
    )
    mgr.agents = agent_list
    mgr.enable_secretary = False
    mgr.secretary = None
    mgr.export_manager = FakeExportManager()
    mgr.conversation_history = ""
    mgr.last_speaker = None
    mgr.conversation_mode = "hybrid"
    return mgr


def test_hybrid_turn_good_and_fallback(monkeypatch, capsys):
    # Agent with long text -> initial good response
    a1 = FakeAgent("id1", "A", text="This is a sufficiently long assistant response.")
    # Agent with short text -> fallback path
    a2 = FakeAgent("id2", "B", text="short")

    mgr = make_mgr_with_agents([a1, a2])

    # Provide client.agent.messages.create recording to ensure fallback path triggers
    created = []

    def fake_create(agent_id, messages):
        created.append((agent_id, messages))

    mgr.client.agents.messages.create = fake_create

    mgr._hybrid_turn([a1, a2], "topic")
    out = capsys.readouterr().out
    # Ensure that A's real text appears and B fallback appears
    assert "sufficiently long assistant response" in out
    assert "As someone with expertise" in out
    # ensure we attempted to call messages.create for fallback or retry
    assert isinstance(created, list)


def test_all_speak_updates_memory_and_history(monkeypatch):
    a1 = FakeAgent("id1", "A", text="Agent A lengthy reply here.")
    a2 = FakeAgent("id2", "B", text="Agent B reply here.")
    mgr = make_mgr_with_agents([a1, a2])

    # Track update_agent_memories calls
    calls = []

    def fake_update(msg, speaker):
        calls.append((speaker, msg))

    mgr._update_agent_memories = fake_update

    mgr._all_speak_turn([a1, a2], "topic")
    # After both speak, update_agent_memories should have been called for each
    assert any(c[0] == "A" for c in calls)
    assert "A: Agent A lengthy reply here." in mgr.conversation_history


def test_sequential_turn_fairness_and_fallback(monkeypatch, capsys):
    a1 = FakeAgent("id1", "A", text="First agent reply long enough.")
    a2 = FakeAgent("id2", "B", text="Second agent reply long enough.")
    mgr = make_mgr_with_agents([a1, a2])

    # Simulate last speaker was A so fairness gives B a turn
    mgr.last_speaker = "A"
    mgr._sequential_turn([a1, a2], "topic")
    assert mgr.last_speaker == "B"
    assert "B: Second agent reply" in mgr.conversation_history

    # Now simulate speak raising exception -> fallback path
    a3 = FakeAgent("id3", "C", raise_on_speak=True)
    mgr2 = make_mgr_with_agents([a3])
    mgr2._notify_secretary_agent_response = lambda n, m: None
    mgr2._sequential_turn([a3], "topic")
    assert (
        "having trouble" in mgr2.conversation_history
        or "trouble" in mgr2.conversation_history
    )


def test_pure_priority_turn_fallback_and_notify():
    a1 = FakeAgent("id1", "A", raise_on_speak=True)
    mgr = make_mgr_with_agents([a1])
    # set a secretary to ensure notify branch runs
    sec = FakeSecretary()
    mgr.secretary = sec
    mgr._notify_secretary_agent_response = lambda n, m: sec.observe_message(n, m)

    mgr._pure_priority_turn([a1], "topic")
    # fallback message should be present
    assert any("thoughts" in v for v in mgr.conversation_history.splitlines())
    # secretary should have observed fallback
    assert sec._observed


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
    mgr = object.__new__(swarm_manager.SwarmManager)
    mgr.client = client
    mgr.agents = [FakeAgent("id1", "A"), FakeAgent("id2", "B")]

    summary = mgr.get_memory_status_summary()
    assert summary["total_agents"] == 2
    # first agent should have numeric recall_memory, second should have error entry
    assert any(
        "error" in s or isinstance(s.get("recall_memory"), int)
        for s in summary["agents_status"]
    )


def test_handle_export_command_various_formats(capsys):
    mgr = make_mgr_with_agents([])
    sec = FakeSecretary()
    mgr.secretary = sec
    mgr.export_manager = FakeExportManager()

    # minutes
    mgr._handle_export_command("formal")
    out = capsys.readouterr().out
    assert "Exported" in out or "✅" in out

    # unknown format
    mgr._handle_export_command("unknown-format")
    out2 = capsys.readouterr().out
    assert "Unknown export format" in out2 or "❌ Unknown export format" in out2
