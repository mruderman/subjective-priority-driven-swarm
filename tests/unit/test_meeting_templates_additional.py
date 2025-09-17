import pytest

import spds.meeting_templates as meeting_templates


def test_render_basic_template():
    data = {
        'metadata': {'topic': 'Roadmap', 'participants': ['Alice', 'Bob'], 'meeting_type': 'planning'},
        'conversation_log': [],
    }
    tpl = meeting_templates.BoardMinutesTemplate()
    out = tpl.generate(data)
    assert isinstance(out, str)
    assert 'Roadmap' in out


def test_render_with_optional_fields():
    data = {
        'metadata': {'topic': 'Sync', 'participants': [], 'notes_style': 'casual'},
        'conversation_log': [],
    }
    tpl = meeting_templates.CasualMinutesTemplate()
    out = tpl.generate(data)
    assert 'Sync' in out
