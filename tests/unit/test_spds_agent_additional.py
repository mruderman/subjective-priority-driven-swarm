import builtins
import json
import re
from types import SimpleNamespace
from unittest.mock import Mock, patch

import spds.spds_agent as spds_agent_module
from spds.spds_agent import SPDSAgent


def mk_agent_state(name="Alice", system=None):
    if system is None:
        system = "You are Alice. Your persona is: Thoughtful helper. Your expertise is in: testing, debugging."
    return SimpleNamespace(id="a1", name=name, system=system, tools=[])


def test_parse_system_prompt_extracts_persona_and_expertise():
    state = mk_agent_state(
        system="You are Test. Your persona is: Researcher. Your expertise is in: ml, ai."
    )
    agent = SPDSAgent(state, client=Mock())
    assert "Researcher" in agent.persona
    assert any("ml" in e for e in agent.expertise)


def test_parse_assessment_response_handles_partial_and_missing_scores():
    state = mk_agent_state()
    agent = SPDSAgent(state, client=Mock())

    # Provide only some labeled scores
    text = "IMPORTANCE_TO_SELF: 8\nUNIQUE_PERSPECTIVE: 6"
    scores = agent._parse_assessment_response(text)
    assert scores["importance_to_self"] == 8
    assert scores["unique_perspective"] == 6
    # Missing keys should be filled with defaults
    assert scores["perceived_gap"] == 5


def test_assess_motivation_and_priority_uses_last_assessment(monkeypatch):
    state = mk_agent_state()
    client = Mock()
    agent = SPDSAgent(state, client=client)

    # Inject a last_assessment object with known fields
    assessment_mock = Mock()
    assessment_mock.importance_to_self = 8
    assessment_mock.perceived_gap = 7
    assessment_mock.unique_perspective = 6
    assessment_mock.emotional_investment = 5
    assessment_mock.expertise_relevance = 4
    assessment_mock.urgency = 9
    assessment_mock.importance_to_group = 8
    assessment_mock.model_dump.return_value = {
        "importance_to_self": 8,
        "perceived_gap": 7,
        "unique_perspective": 6,
        "emotional_investment": 5,
        "expertise_relevance": 4,
        "urgency": 9,
        "importance_to_group": 8,
    }
    agent.last_assessment = assessment_mock

    # Monkeypatch _get_full_assessment so it doesn't call external
    monkeypatch.setattr(agent, "_get_full_assessment", lambda *a, **k: None)

    # Call assess with new signature
    recent_messages = []  # Empty list for this test
    original_topic = "T"
    agent.assess_motivation_and_priority(recent_messages, original_topic)

    assert agent.motivation_score == 8 + 7 + 6 + 5 + 4
    if agent.motivation_score >= 10:
        assert agent.priority_score >= 0


def test_speak_fallback_on_no_tool_calls(monkeypatch):
    state = mk_agent_state()
    # simulate agent with tools
    state.tools = [1]
    client = Mock()

    # configure client to raise the specific string error on first call then return a response
    def raise_no_tools(*a, **k):
        raise RuntimeError("No tool calls found")

    client.agents.messages.create.side_effect = [
        RuntimeError("No tool calls found"),
        SimpleNamespace(messages=[SimpleNamespace(content="ok")]),
    ]

    agent = SPDSAgent(state, client=client)
    # Should not raise
    res = agent.speak(conversation_history="", mode="initial", topic="X")
    assert res is not None


def test_ensure_assessment_tool_handles_iteration_error():
    state = mk_agent_state()

    class BadTools:
        def __iter__(self):
            raise RuntimeError("broken tools")

    state.tools = BadTools()
    client = Mock()
    created_tool = SimpleNamespace(id="tool-123")
    client.tools.create_from_function.return_value = created_tool
    client.agents.tools.attach.return_value = SimpleNamespace()

    agent = SPDSAgent(state, client=client)

    client.tools.create_from_function.assert_called_once()
    assert agent.assessment_tool == created_tool


def test_get_full_assessment_parses_tool_return_json(monkeypatch):
    state = mk_agent_state()
    client = Mock()
    agent = SPDSAgent(state, client=client)

    response = SimpleNamespace(
        messages=[
            SimpleNamespace(
                tool_calls=[
                    SimpleNamespace(
                        function=SimpleNamespace(name="send_message", arguments="{}")
                    )
                ],
                tool_return=None,
                message_type="tool_message",
                content=None,
            ),
            SimpleNamespace(
                tool_calls=[],
                tool_return=json.dumps(
                    {
                        "importance_to_self": 7,
                        "perceived_gap": 6,
                        "unique_perspective": 5,
                        "emotional_investment": 4,
                        "expertise_relevance": 8,
                        "urgency": 3,
                        "importance_to_group": 9,
                    }
                ),
                message_type="tool_message",
                content=None,
            ),
        ]
    )

    client.agents.messages.create.return_value = response

    agent._get_full_assessment(topic="Topic", conversation_history="History")

    assert agent.last_assessment.importance_to_self == 7
    client.agents.messages.create.assert_called_once()


def test_get_full_assessment_falls_back_to_local_tool(monkeypatch):
    state = mk_agent_state()
    client = Mock()
    agent = SPDSAgent(state, client=client)

    response = SimpleNamespace(
        messages=[
            SimpleNamespace(
                tool_calls=[],
                tool_return=None,
                message_type="assistant_message",
                content=[{"text": "Just checking in"}],
            )
        ]
    )
    client.agents.messages.create.return_value = response

    with patch.object(
        spds_agent_module.tools, "perform_subjective_assessment"
    ) as mock_local:
        mock_local.return_value = SimpleNamespace(
            importance_to_self=5,
            perceived_gap=5,
            unique_perspective=5,
            emotional_investment=5,
            expertise_relevance=5,
            urgency=5,
            importance_to_group=5,
        )
        agent._get_full_assessment(topic="Topic", conversation_history="")
        mock_local.assert_called_once()


def test_get_full_assessment_handles_invalid_json_and_content_dict(monkeypatch):
    state = mk_agent_state()
    state.tools = []
    client = Mock()
    agent = SPDSAgent(state, client=client)

    response = SimpleNamespace(
        messages=[
            SimpleNamespace(
                tool_calls=[],
                tool_return="{",
                message_type="tool_message",
                content=None,
            ),
            SimpleNamespace(
                tool_calls=[],
                tool_return=None,
                message_type="assistant_message",
                content=[{"text": "IMPORTANCE_TO_SELF: 9"}],
            ),
        ]
    )

    client.agents.messages.create.return_value = response

    with patch.object(
        spds_agent_module.tools, "SubjectiveAssessment"
    ) as mock_sa, patch.object(
        spds_agent_module.tools, "perform_subjective_assessment"
    ) as mock_local:
        sentinel = SimpleNamespace(marker="parsed")
        mock_sa.return_value = sentinel
        agent._get_full_assessment(topic="Topic", conversation_history="")
        mock_sa.assert_called_once()
        args, kwargs = mock_sa.call_args
        assert kwargs["importance_to_self"] == 9
        assert agent.last_assessment is sentinel
        mock_local.assert_not_called()


def test_get_full_assessment_parses_string_list_content(monkeypatch):
    state = mk_agent_state()
    state.tools = []
    client = Mock()
    agent = SPDSAgent(state, client=client)

    response = SimpleNamespace(
        messages=[
            SimpleNamespace(
                tool_calls=[],
                tool_return=None,
                message_type="assistant_message",
                content=["IMPORTANCE_TO_SELF: 4\nUNIQUE_PERSPECTIVE: 6"],
            )
        ]
    )

    client.agents.messages.create.return_value = response

    with patch.object(
        spds_agent_module.tools, "SubjectiveAssessment"
    ) as mock_sa, patch.object(
        spds_agent_module.tools, "perform_subjective_assessment"
    ) as mock_local:
        sentinel = SimpleNamespace(marker="list-str")
        mock_sa.return_value = sentinel
        agent._get_full_assessment(topic="Topic", conversation_history="")
        mock_sa.assert_called_once()
        assert agent.last_assessment is sentinel
        mock_local.assert_not_called()


def test_get_full_assessment_handles_direct_string_content(monkeypatch):
    state = mk_agent_state()
    state.tools = []
    client = Mock()
    agent = SPDSAgent(state, client=client)

    response = SimpleNamespace(
        messages=[
            SimpleNamespace(
                tool_calls=[],
                tool_return=None,
                message_type="assistant_message",
                content="IMPORTANCE_TO_SELF: 6\nUNIQUE_PERSPECTIVE: 4",
            )
        ]
    )

    client.agents.messages.create.return_value = response

    with patch.object(
        spds_agent_module.tools, "SubjectiveAssessment"
    ) as mock_sa, patch.object(
        spds_agent_module.tools, "perform_subjective_assessment"
    ) as mock_local:
        sentinel = SimpleNamespace(marker="direct-str")
        mock_sa.return_value = sentinel
        agent._get_full_assessment(topic="Topic", conversation_history="")
        mock_sa.assert_called_once()
        assert agent.last_assessment is sentinel
        mock_local.assert_not_called()


def test_get_full_assessment_handles_namespace_text_content(monkeypatch):
    state = mk_agent_state()
    state.tools = []
    client = Mock()
    agent = SPDSAgent(state, client=client)

    response = SimpleNamespace(
        messages=[
            SimpleNamespace(
                tool_calls=[],
                tool_return=None,
                message_type="assistant_message",
                content=[SimpleNamespace(text="IMPORTANCE_TO_SELF: 7")],
            )
        ]
    )

    client.agents.messages.create.return_value = response

    with patch.object(
        spds_agent_module.tools, "SubjectiveAssessment"
    ) as mock_sa, patch.object(
        spds_agent_module.tools, "perform_subjective_assessment"
    ) as mock_local:
        sentinel = SimpleNamespace(marker="ns-text")
        mock_sa.return_value = sentinel
        agent._get_full_assessment(topic="Topic", conversation_history="")
        mock_sa.assert_called_once()
        assert agent.last_assessment is sentinel
        mock_local.assert_not_called()


def test_get_full_assessment_skips_non_string_candidates(monkeypatch):
    state = mk_agent_state()
    state.tools = []
    client = Mock()
    agent = SPDSAgent(state, client=client)

    response = SimpleNamespace(
        messages=[
            SimpleNamespace(
                tool_calls=[],
                tool_return={"raw": "IMPORTANCE_TO_SELF: 5"},
                message_type="tool_message",
                content=None,
            )
        ]
    )

    client.agents.messages.create.return_value = response

    with patch.object(
        spds_agent_module.tools, "perform_subjective_assessment"
    ) as mock_local:
        sentinel = SimpleNamespace(marker="fallback")
        mock_local.return_value = sentinel
        agent._get_full_assessment(topic="Topic", conversation_history="History")
        mock_local.assert_called_once()
        assert agent.last_assessment is sentinel


def test_get_full_assessment_handles_non_dict_json_then_scores(monkeypatch):
    state = mk_agent_state()
    state.tools = []
    client = Mock()
    agent = SPDSAgent(state, client=client)

    response = SimpleNamespace(
        messages=[
            SimpleNamespace(
                tool_calls=[],
                tool_return="[1, 2, 3]",
                message_type="tool_message",
                content=None,
            ),
            SimpleNamespace(
                tool_calls=[],
                tool_return=None,
                message_type="assistant_message",
                content="IMPORTANCE_TO_SELF: 8",
            ),
        ]
    )

    client.agents.messages.create.return_value = response

    with patch.object(
        spds_agent_module.tools, "SubjectiveAssessment"
    ) as mock_sa, patch.object(
        spds_agent_module.tools, "perform_subjective_assessment"
    ) as mock_local:
        sentinel = SimpleNamespace(marker="after-json")
        mock_sa.return_value = sentinel
        agent._get_full_assessment(topic="Topic", conversation_history="")
        mock_sa.assert_called_once()
        assert agent.last_assessment is sentinel
        mock_local.assert_not_called()


def test_get_full_assessment_handles_weird_json_module(monkeypatch):
    state = mk_agent_state()
    state.tools = []
    client = Mock()
    agent = SPDSAgent(state, client=client)

    response = SimpleNamespace(
        messages=[
            SimpleNamespace(
                tool_calls=[],
                tool_return='{"unexpected": true}',
                message_type="tool_message",
                content=None,
            ),
            SimpleNamespace(
                tool_calls=[],
                tool_return=None,
                message_type="assistant_message",
                content="IMPORTANCE_TO_SELF: 7",
            ),
        ]
    )

    original_json_loads = json.loads

    def fake_json_loads(payload):
        if payload == '{"unexpected": true}':
            return ["not", "a", "dict"]
        return original_json_loads(payload)

    monkeypatch.setattr(json, "loads", fake_json_loads)

    client.agents.messages.create.return_value = response

    with patch.object(
        spds_agent_module.tools, "SubjectiveAssessment"
    ) as mock_sa, patch.object(
        spds_agent_module.tools, "perform_subjective_assessment"
    ) as mock_local:
        sentinel = SimpleNamespace(marker="json-non-dict")
        mock_sa.return_value = sentinel
        agent._get_full_assessment(topic="Topic", conversation_history="")
        mock_sa.assert_called_once()
        assert agent.last_assessment is sentinel
        mock_local.assert_not_called()


def test_get_full_assessment_uses_fallback_scores_when_any_skipped(monkeypatch):
    state = mk_agent_state()
    state.tools = []
    client = Mock()
    agent = SPDSAgent(state, client=client)

    response = SimpleNamespace(
        messages=[
            SimpleNamespace(
                tool_calls=[],
                tool_return=None,
                message_type="assistant_message",
                content="IMPORTANCE_TO_SELF: 5",
            )
        ]
    )

    client.agents.messages.create.return_value = response

    original_any = builtins.any
    call_count = {"count": 0}

    def fake_any(iterable):
        call_count["count"] += 1
        if call_count["count"] == 1:
            return False
        return original_any(iterable)

    monkeypatch.setattr(builtins, "any", fake_any)

    with patch.object(
        spds_agent_module.tools, "SubjectiveAssessment"
    ) as mock_sa, patch.object(
        spds_agent_module.tools, "perform_subjective_assessment"
    ) as mock_local:
        sentinel = SimpleNamespace(marker="fallback-scores")
        mock_sa.return_value = sentinel
        agent._get_full_assessment(topic="Topic", conversation_history="")
        assert call_count["count"] >= 2
        mock_sa.assert_called_once()
        assert agent.last_assessment is sentinel
        mock_local.assert_not_called()


def test_get_full_assessment_handles_exception(monkeypatch):
    state = mk_agent_state()
    client = Mock()
    agent = SPDSAgent(state, client=client)

    client.agents.messages.create.side_effect = RuntimeError("unavailable")

    def fake_randint(a, b):
        return a

    monkeypatch.setattr("random.randint", fake_randint)

    agent._get_full_assessment(topic="Topic", conversation_history="")

    assert agent.last_assessment is not None
    assert agent.last_assessment.importance_to_self >= 2


def test_parse_assessment_response_handles_regex_error(monkeypatch):
    state = mk_agent_state()
    agent = SPDSAgent(state, client=Mock())

    original_search = spds_agent_module.re.search

    def fake_search(pattern, string, *args, **kwargs):
        if pattern == r"\d+":
            raise ValueError("regex fail")
        return original_search(pattern, string, *args, **kwargs)

    monkeypatch.setattr(spds_agent_module.re, "search", fake_search)

    scores = agent._parse_assessment_response("IMPORTANCE_TO_SELF: value")

    assert scores["importance_to_self"] == 5
