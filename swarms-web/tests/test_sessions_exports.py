"""
Test session export endpoints for the Flask web application.

Tests the following endpoints:
- GET /api/sessions/<session_id>/exports - List export files for a session
- POST /api/sessions/<session_id>/export - Trigger export for a session
- GET /api/sessions/<session_id>/exports/<filename> - Download a specific export file
"""

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

ROOT_DIR = Path(__file__).resolve().parents[2]
SWARMS_WEB_DIR = Path(__file__).resolve().parents[1]
if str(SWARMS_WEB_DIR) not in sys.path:
    sys.path.insert(0, str(SWARMS_WEB_DIR))
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from spds import config
from spds.session_store import (
    JsonSessionStore,
    SessionEvent,
    reset_default_session_store,
)


@pytest.fixture
def app(tmp_path, monkeypatch):
    """Create a test Flask app with temporary directories."""
    sessions_dir = tmp_path / "sessions"
    exports_dir = tmp_path / "exports"
    sessions_dir.mkdir()
    exports_dir.mkdir()

    monkeypatch.setattr(config, "get_sessions_dir", lambda: sessions_dir)
    monkeypatch.setattr(config, "DEFAULT_EXPORT_DIRECTORY", str(exports_dir))
    reset_default_session_store()

    swarms_web_dir = Path(__file__).resolve().parents[1]
    repo_root = swarms_web_dir.parent
    monkeypatch.syspath_prepend(str(swarms_web_dir))
    monkeypatch.syspath_prepend(str(repo_root))

    from app import app as flask_app

    return flask_app


@pytest.fixture
def client(app):
    """Create a test client for the Flask app."""
    return app.test_client()


@pytest.fixture
def test_session(tmp_path):
    """Create a test session with some events."""
    sessions_dir = tmp_path / "sessions"
    sessions_dir.mkdir(exist_ok=True)

    store = JsonSessionStore(sessions_dir)
    session_state = store.create(title="Test Session", tags=["test", "export"])
    session_id = session_state.meta.id

    # Add some events to the session
    events = [
        SessionEvent(
            event_id="test-event-1",
            session_id=session_id,
            ts=datetime.now(timezone.utc),
            actor="test_agent",
            type="message",
            payload={"content": "Hello world", "message_type": "assistant"},
        ),
        SessionEvent(
            event_id="test-event-2",
            session_id=session_id,
            ts=datetime.now(timezone.utc),
            actor="test_agent",
            type="action",
            payload={"action_type": "test_action", "details": {"key": "value"}},
        ),
        SessionEvent(
            event_id="test-event-3",
            session_id=session_id,
            ts=datetime.now(timezone.utc),
            actor="test_agent",
            type="decision",
            payload={
                "decision_type": "test_decision",
                "details": {"outcome": "approved"},
            },
        ),
    ]

    for event in events:
        store.save_event(event)

    return session_id


class TestSessionExports:
    """Test session export functionality."""

    def test_list_exports_empty(self, client, test_session):
        """Test listing exports for a session with no exports."""
        response = client.get(f"/api/sessions/{test_session}/exports")

        assert response.status_code == 200
        data = json.loads(response.data)
        assert isinstance(data, list)
        assert len(data) == 0

    def test_list_exports_invalid_session(self, client):
        """Test listing exports for a non-existent session."""
        invalid_session_id = "non-existent-session-id"
        response = client.get(f"/api/sessions/{invalid_session_id}/exports")

        assert response.status_code == 404
        data = json.loads(response.data)
        assert "error" in data
        assert data["error"] == "Session not found"

    def test_trigger_export_success(self, client, test_session):
        """Test triggering export for a valid session."""
        response = client.post(
            f"/api/sessions/{test_session}/export", content_type="application/json"
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["ok"] is True
        assert "created" in data
        assert len(data["created"]) == 2  # JSON and Markdown files

        # Check that both files were created
        filenames = [item["filename"] for item in data["created"]]
        kinds = [item["kind"] for item in data["created"]]

        assert "json" in kinds
        assert "markdown" in kinds

        # Verify files exist
        json_file = next(item for item in data["created"] if item["kind"] == "json")
        md_file = next(item for item in data["created"] if item["kind"] == "markdown")

        assert json_file["filename"].startswith("summary_")
        assert json_file["filename"].endswith(".json")
        assert md_file["filename"].startswith("minutes_")
        assert md_file["filename"].endswith(".md")

    def test_trigger_export_invalid_session(self, client):
        """Test triggering export for a non-existent session."""
        invalid_session_id = "non-existent-session-id"
        response = client.post(
            f"/api/sessions/{invalid_session_id}/export",
            content_type="application/json",
        )

        assert response.status_code == 404
        data = json.loads(response.data)
        assert data["ok"] is False
        assert data["error"] == "Session not found"

    def test_list_exports_after_creation(self, client, test_session):
        """Test listing exports after creating some."""
        # First, create exports
        response = client.post(
            f"/api/sessions/{test_session}/export", content_type="application/json"
        )
        assert response.status_code == 200

        # Then list them
        response = client.get(f"/api/sessions/{test_session}/exports")

        assert response.status_code == 200
        data = json.loads(response.data)
        assert isinstance(data, list)
        assert len(data) == 2  # JSON and Markdown files

        # Verify export structure
        for export_item in data:
            assert "filename" in export_item
            assert "size_bytes" in export_item
            assert "created_at" in export_item
            assert "kind" in export_item
            assert export_item["kind"] in ["json", "markdown"]

    def test_list_exports_with_limit(self, client, test_session):
        """Test listing exports with limit parameter."""
        # Create multiple exports
        for _ in range(3):
            response = client.post(
                f"/api/sessions/{test_session}/export", content_type="application/json"
            )
            assert response.status_code == 200

        # List with limit
        response = client.get(f"/api/sessions/{test_session}/exports?limit=2")

        assert response.status_code == 200
        data = json.loads(response.data)
        assert len(data) == 2  # Should be limited to 2

        # Verify they are sorted by creation time (newest first)
        created_times = [datetime.fromisoformat(item["created_at"]) for item in data]
        assert created_times[0] >= created_times[1]

    def test_download_export_success(self, client, test_session):
        """Test downloading a valid export file."""
        # First, create an export
        response = client.post(
            f"/api/sessions/{test_session}/export", content_type="application/json"
        )
        assert response.status_code == 200
        data = json.loads(response.data)

        # Get the filename of the created export
        json_export = next(item for item in data["created"] if item["kind"] == "json")
        filename = json_export["filename"]

        # Download the file
        response = client.get(f"/api/sessions/{test_session}/exports/{filename}")

        assert response.status_code == 200
        assert response.content_type == "application/json"
        assert response.headers.get("Content-Disposition") is not None
        assert filename in response.headers.get("Content-Disposition")

    def test_download_export_markdown(self, client, test_session):
        """Test downloading a markdown export file."""
        # First, create an export
        response = client.post(
            f"/api/sessions/{test_session}/export", content_type="application/json"
        )
        assert response.status_code == 200
        data = json.loads(response.data)

        # Get the filename of the markdown export
        md_export = next(item for item in data["created"] if item["kind"] == "markdown")
        filename = md_export["filename"]

        # Download the file
        response = client.get(f"/api/sessions/{test_session}/exports/{filename}")

        assert response.status_code == 200
        assert response.content_type.startswith("text/markdown")
        assert response.headers.get("Content-Disposition") is not None
        assert filename in response.headers.get("Content-Disposition")

    def test_download_export_invalid_filename(self, client, test_session):
        """Test downloading with invalid filename pattern."""
        invalid_filename = "invalid_file.txt"
        response = client.get(
            f"/api/sessions/{test_session}/exports/{invalid_filename}"
        )

        assert response.status_code == 400
        data = json.loads(response.data)
        assert "error" in data
        assert "Invalid filename pattern" in data["error"]

    def test_download_export_path_traversal(self, client, test_session):
        """Test downloading with path traversal attempt."""
        malicious_filename = "../../../etc/passwd"
        response = client.get(
            f"/api/sessions/{test_session}/exports/{malicious_filename}"
        )

        assert response.status_code == 400
        data = json.loads(response.data)
        assert "error" in data
        assert "Invalid filename" in data["error"]

    def test_download_export_nonexistent_file(self, client, test_session):
        """Test downloading a non-existent export file."""
        nonexistent_filename = "summary_nonexistent_20240101_000000.json"
        response = client.get(
            f"/api/sessions/{test_session}/exports/{nonexistent_filename}"
        )

        assert response.status_code == 404
        data = json.loads(response.data)
        assert "error" in data
        assert data["error"] == "File not found"

    def test_download_export_invalid_session(self, client):
        """Test downloading export for a non-existent session."""
        invalid_session_id = "non-existent-session-id"
        filename = "summary_test_20240101_000000.json"
        response = client.get(f"/api/sessions/{invalid_session_id}/exports/{filename}")

        assert response.status_code == 404
        data = json.loads(response.data)
        assert "error" in data
        assert data["error"] == "Session not found"

    def test_export_file_content_validation(self, client, test_session):
        """Test that exported files contain valid content."""
        # Create an export
        response = client.post(
            f"/api/sessions/{test_session}/export", content_type="application/json"
        )
        assert response.status_code == 200
        data = json.loads(response.data)

        # Download the JSON export
        json_export = next(item for item in data["created"] if item["kind"] == "json")
        response = client.get(
            f'/api/sessions/{test_session}/exports/{json_export["filename"]}'
        )

        assert response.status_code == 200
        json_content = json.loads(response.data)

        # Validate JSON structure
        assert "minutes_markdown" in json_content
        assert "actions" in json_content
        assert "decisions" in json_content
        assert "messages" in json_content
        assert "meta" in json_content
        assert json_content["meta"]["session_id"] == test_session

        # Download the Markdown export
        md_export = next(item for item in data["created"] if item["kind"] == "markdown")
        response = client.get(
            f'/api/sessions/{test_session}/exports/{md_export["filename"]}'
        )

        assert response.status_code == 200
        md_content = response.data.decode("utf-8")

        # Validate Markdown content
        assert "# Session Minutes:" in md_content
        assert "**Session ID**:" in md_content
        assert test_session in md_content
        assert "## Transcript" in md_content
        assert "## Decisions" in md_content
        assert "## Action Items" in md_content
