from pathlib import Path
import json

import pytest
from spds.session_store import set_default_session_store


def test_export_session_atomic_write_cleanup(tmp_path, monkeypatch):
    from spds import export_manager as em

    # Create minimal session in store so build_session_summary can run
    from spds.session_store import JsonSessionStore

    store = JsonSessionStore(tmp_path / "sessions")
    set_default_session_store(store)
    sess = store.create(title="X")

    # Force tempfile.NamedTemporaryFile to throw on write to trigger cleanup only during export
    real_ntf = em.tempfile.NamedTemporaryFile

    class Boom(Exception):
        pass

    def bomb(*args, **kwargs):
        raise Boom("fail")

    monkeypatch.setattr(em.tempfile, "NamedTemporaryFile", bomb)
    try:
        with pytest.raises(Boom):
            em.export_session_to_json(sess.meta.id, dest_dir=tmp_path / "out")
    finally:
        # Restore real NTF to avoid side effects
        monkeypatch.setattr(em.tempfile, "NamedTemporaryFile", real_ntf)
        set_default_session_store(None)


def test_build_session_summary_no_events(tmp_path):
    from spds import export_manager as em
    from spds.session_store import JsonSessionStore

    store = JsonSessionStore(tmp_path / "sessions")
    set_default_session_store(store)
    sess = store.create(title="Empty")
    summary = em.build_session_summary(sess)
    assert "minutes_markdown" in summary and "Total Events" in summary["minutes_markdown"]
    set_default_session_store(None)


