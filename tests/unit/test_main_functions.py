import json
from types import SimpleNamespace
from unittest.mock import Mock, patch

from spds.main import (
    interactive_agent_selection,
    list_available_agents,
    load_swarm_from_file,
)


def test_load_swarm_from_file_success(tmp_path):
    data = [{"name": "A"}]
    p = tmp_path / "swarm.json"
    p.write_text(json.dumps(data))
    assert load_swarm_from_file(str(p)) == data


def test_load_swarm_from_file_not_found(tmp_path):
    assert load_swarm_from_file(str(tmp_path / "missing.json")) is None


def test_load_swarm_from_file_invalid_json(tmp_path):
    p = tmp_path / "bad.json"
    p.write_text("{ invalid }")
    assert load_swarm_from_file(str(p)) is None


def test_list_available_agents_success():
    client = Mock()
    client.agents.list.return_value = [1, 2]
    assert list_available_agents(client) == [1, 2]


def test_list_available_agents_failure(capsys):
    client = Mock()
    client.agents.list.side_effect = RuntimeError("server down")

    agents = list_available_agents(client)

    captured = capsys.readouterr()
    assert agents == []
    assert "Error fetching agents" in captured.out


def test_interactive_agent_selection_flow(monkeypatch):
    # Build fake agents
    agents = [
        SimpleNamespace(
            id="a1", name="Alpha", model="openai/gpt-4", created_at="2025-01-01"
        ),
        SimpleNamespace(id="b2", name="Beta", model=None, created_at=None),
    ]
    client = Mock()
    with patch("spds.main.list_available_agents", return_value=agents):
        # Patch questionary interactions
        import spds.main as m

        monkeypatch.setattr(
            m.questionary,
            "checkbox",
            lambda *a, **k: SimpleNamespace(ask=lambda: ["a1"]),
        )
        monkeypatch.setattr(
            m.questionary,
            "select",
            lambda *a, **k: SimpleNamespace(
                ask=lambda: "🔄 Hybrid (independent thoughts + response round) [RECOMMENDED]"
            ),
        )
        monkeypatch.setattr(
            m.questionary, "confirm", lambda *a, **k: SimpleNamespace(ask=lambda: True)
        )
        monkeypatch.setattr(
            m.questionary,
            "text",
            lambda *a, **k: SimpleNamespace(ask=lambda: "My Topic"),
        )

        selected = interactive_agent_selection(client)
        assert selected[0] == ["a1"]
        assert selected[1] == "My Topic"
        assert selected[2] == "hybrid"
        assert selected[3] is True
        assert selected[4] in ("adaptive", "formal", "casual")
        assert selected[5] in ("discussion", "board_meeting")


def test_interactive_agent_selection_no_agents():
    client = Mock()
    with patch("spds.main.list_available_agents", return_value=[]):
        assert interactive_agent_selection(client) == (None, None)


def test_interactive_agent_selection_no_choice(monkeypatch):
    client = Mock()
    agents = [SimpleNamespace(id="a1", name="Agent", model=None, created_at=None)]
    with patch("spds.main.list_available_agents", return_value=agents):
        import spds.main as m

        monkeypatch.setattr(
            m.questionary,
            "checkbox",
            lambda *a, **k: SimpleNamespace(ask=lambda: []),
        )
        selected = interactive_agent_selection(client)
        assert selected == (None, None)


def test_interactive_agent_selection_missing_topic(monkeypatch):
    client = Mock()
    agents = [SimpleNamespace(id="a1", name="Agent", model=None, created_at=None)]
    with patch("spds.main.list_available_agents", return_value=agents):
        import spds.main as m

        monkeypatch.setattr(
            m.questionary,
            "checkbox",
            lambda *a, **k: SimpleNamespace(ask=lambda: ["a1"]),
        )
        monkeypatch.setattr(
            m.questionary,
            "select",
            lambda *a, **k: SimpleNamespace(ask=lambda: "🔀 Sequential (one speaker per turn with fairness)"),
        )
        monkeypatch.setattr(
            m.questionary,
            "confirm",
            lambda *a, **k: SimpleNamespace(ask=lambda: False),
        )
        monkeypatch.setattr(
            m.questionary,
            "text",
            lambda *a, **k: SimpleNamespace(ask=lambda: ""),
        )

        result = interactive_agent_selection(client)
        assert result == (None, None, None, None, None)
