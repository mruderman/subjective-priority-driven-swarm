import pytest

from spds.session_context import (
    clear_session_context,
    ensure_session,
    get_current_session_id,
    new_session_id,
    set_current_session_id,
)
from spds.session_store import JsonSessionStore


def test_get_set_clear_session_id(tmp_path):
    # Start with no session id
    clear_session_context()
    assert get_current_session_id() is None

    # Set and get
    set_current_session_id("abc-123")
    assert get_current_session_id() == "abc-123"

    # Clear resets
    clear_session_context()
    assert get_current_session_id() is None


def test_ensure_session_creates_when_none(tmp_path):
    clear_session_context()
    store = JsonSessionStore(tmp_path / "sessions")

    session_id = ensure_session(store, title="Edge Case")
    assert session_id is not None
    # ensure_session sets the context var
    assert get_current_session_id() == session_id

    # Calling again returns same id and does not create a new session
    again = ensure_session(store)
    assert again == session_id


def test_new_session_id_unique():
    a = new_session_id()
    b = new_session_id()
    assert a != b and isinstance(a, str) and isinstance(b, str)


def test_set_current_session_id_accepts_string_values():
    # Accepts arbitrary string identifiers (regression guard)
    clear_session_context()
    set_current_session_id("0")
    assert get_current_session_id() == "0"

    set_current_session_id("some-session-id")
    assert get_current_session_id() == "some-session-id"
