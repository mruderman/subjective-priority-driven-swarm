import types
from types import SimpleNamespace

import pytest


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


def test_init_no_agents_raises(monkeypatch):
    import spds.swarm_manager as sm

    dummy_client = SimpleNamespace()
    with pytest.raises(ValueError):
        sm.SwarmManager(client=dummy_client, conversation_mode="hybrid")


def test_init_with_agent_ids_uses_retrieve(monkeypatch):
    import spds.swarm_manager as sm

    # Stub SPDSAgent so we don't require real AgentState
    class StubAgent:
        def __init__(self, agent_state, client):
            self.agent = agent_state
            self.name = getattr(agent_state, "name", "A")

    monkeypatch.setattr(sm, "SPDSAgent", StubAgent)

    # Dummy client with agents.retrieve
    class DummyAgents:
        def retrieve(self, agent_id):
            return SimpleNamespace(id=agent_id, name=f"Agent-{agent_id}", system="")

    dummy_client = SimpleNamespace(agents=DummyAgents())

    mgr = sm.SwarmManager(client=dummy_client, agent_ids=["1"], conversation_mode="hybrid")
    assert len(mgr.agents) == 1
    assert mgr.agents[0].agent.id == "1"


def test_init_with_profiles_ephemeral_disabled_raises(monkeypatch):
    import spds.swarm_manager as sm
    from spds import config

    monkeypatch.setattr(config, "get_allow_ephemeral_agents", lambda: False)

    dummy_client = SimpleNamespace(agents=SimpleNamespace())
    with pytest.raises(ValueError):
        sm.SwarmManager(
            client=dummy_client,
            agent_profiles=[{"name": "X", "persona": "p", "expertise": ["e"]}],
        )


