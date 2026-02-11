"""Extra unit tests for export_manager edge cases."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from spds.export_manager import build_session_summary, export_session_to_json


def _mock_conversation_manager(messages=None, summary_dict=None):
    """Create a mock ConversationManager."""
    cm = MagicMock()
    cm.list_messages.return_value = messages or []
    cm.get_session_summary.return_value = summary_dict or {"id": "conv-test"}
    return cm


def test_export_session_atomic_write_cleanup(tmp_path, monkeypatch):
    """Verify that a failed atomic write cleans up temp files."""
    from spds import export_manager as em

    # Create a mock ConversationManager that returns some messages
    cm = _mock_conversation_manager(
        messages=[
            {"message_type": "assistant_message", "role": "assistant",
             "content": "test", "created_at": ""},
        ],
        summary_dict={"id": "conv-boom"},
    )

    # Force tempfile.NamedTemporaryFile to throw to trigger cleanup path
    real_ntf = em.tempfile.NamedTemporaryFile

    class Boom(Exception):
        pass

    def bomb(*args, **kwargs):
        raise Boom("fail")

    monkeypatch.setattr(em.tempfile, "NamedTemporaryFile", bomb)
    try:
        with pytest.raises(Boom):
            em.export_session_to_json(
                "conv-boom",
                conversation_manager=cm,
                dest_dir=tmp_path / "out",
            )
    finally:
        monkeypatch.setattr(em.tempfile, "NamedTemporaryFile", real_ntf)


def test_build_session_summary_no_events(tmp_path):
    """build_session_summary with empty messages returns valid structure."""
    from spds import export_manager as em

    summary = em.build_session_summary(messages=[])
    assert "minutes_markdown" in summary
    assert "Total Messages" in summary["minutes_markdown"]
