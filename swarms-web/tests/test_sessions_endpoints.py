"""Tests for session management endpoints in swarms-web."""

import json
import tempfile
from pathlib import Path

import pytest

import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import app


@pytest.fixture
def client():
    """Create a test client for the Flask app."""
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client


@pytest.fixture
def temp_sessions_dir(monkeypatch):
    """Create a temporary sessions directory for testing."""
    from spds.session_store import reset_default_session_store

    with tempfile.TemporaryDirectory() as tmpdir:
        sessions_dir = Path(tmpdir) / "sessions"
        sessions_dir.mkdir(parents=True, exist_ok=True)
        
        # Mock the get_sessions_dir function
        def mock_get_sessions_dir():
            return sessions_dir
        
        monkeypatch.setattr("spds.config.get_sessions_dir", mock_get_sessions_dir)
        reset_default_session_store()
        yield sessions_dir


def test_get_sessions_empty(client, temp_sessions_dir):
    """Test GET /api/sessions returns empty array initially."""
    response = client.get('/api/sessions')
    
    assert response.status_code == 200
    data = json.loads(response.data)
    assert isinstance(data, list)
    assert len(data) == 0


def test_create_session_minimal(client, temp_sessions_dir):
    """Test POST /api/sessions creates session with minimal data."""
    response = client.post('/api/sessions', 
                          json={},
                          content_type='application/json')
    
    assert response.status_code == 201
    data = json.loads(response.data)
    
    assert 'id' in data
    assert 'created_at' in data
    assert 'last_updated' in data
    assert data['title'] is None
    assert data['tags'] == []


def test_create_session_with_title_and_tags(client, temp_sessions_dir):
    """Test POST /api/sessions creates session with title and tags."""
    payload = {
        'title': 'Test Session',
        'tags': ['test', 'demo']
    }
    
    response = client.post('/api/sessions', 
                          json=payload,
                          content_type='application/json')
    
    assert response.status_code == 201
    data = json.loads(response.data)
    
    assert 'id' in data
    assert data['title'] == 'Test Session'
    assert data['tags'] == ['test', 'demo']
    assert 'created_at' in data
    assert 'last_updated' in data


def test_create_session_invalid_json(client, temp_sessions_dir):
    """Test POST /api/sessions returns 400 for invalid JSON."""
    response = client.post('/api/sessions', 
                          data='invalid json',
                          content_type='application/json')
    
    assert response.status_code == 400
    data = json.loads(response.data)
    assert 'error' in data


def test_create_session_invalid_tags_type(client, temp_sessions_dir):
    """Test POST /api/sessions returns 400 for invalid tags type."""
    payload = {
        'title': 'Test Session',
        'tags': 'not an array'  # Invalid: should be array
    }
    
    response = client.post('/api/sessions', 
                          json=payload,
                          content_type='application/json')
    
    assert response.status_code == 400
    data = json.loads(response.data)
    assert 'error' in data
    assert 'tags must be an array' in data['error']


def test_resume_session_success(client, temp_sessions_dir):
    """Test POST /api/sessions/resume with valid session ID."""
    # First create a session
    create_response = client.post('/api/sessions', 
                                 json={'title': 'Test Session'},
                                 content_type='application/json')
    
    assert create_response.status_code == 201
    session_data = json.loads(create_response.data)
    session_id = session_data['id']
    
    # Now try to resume it
    response = client.post('/api/sessions/resume', 
                          json={'id': session_id},
                          content_type='application/json')
    
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data['ok'] is True
    assert data['id'] == session_id


def test_resume_session_not_found(client, temp_sessions_dir):
    """Test POST /api/sessions/resume with invalid session ID returns 404."""
    response = client.post('/api/sessions/resume', 
                          json={'id': 'non-existent-session-id'},
                          content_type='application/json')
    
    assert response.status_code == 404
    data = json.loads(response.data)
    assert data['ok'] is False
    assert data['error'] == 'not_found'


def test_resume_session_missing_id(client, temp_sessions_dir):
    """Test POST /api/sessions/resume returns 400 for missing ID."""
    response = client.post('/api/sessions/resume', 
                          json={},
                          content_type='application/json')
    
    assert response.status_code == 400
    data = json.loads(response.data)
    assert 'error' in data
    assert 'id is required' in data['error']


def test_resume_session_invalid_json(client, temp_sessions_dir):
    """Test POST /api/sessions/resume returns 400 for invalid JSON."""
    response = client.post('/api/sessions/resume', 
                          data='invalid json',
                          content_type='application/json')
    
    assert response.status_code == 400
    data = json.loads(response.data)
    assert 'error' in data


def test_get_sessions_with_limit(client, temp_sessions_dir):
    """Test GET /api/sessions?limit=N returns limited results."""
    # Create exactly 3 new sessions
    for i in range(3):
        client.post('/api/sessions',
                   json={'title': f'Session {i}'},
                   content_type='application/json')
    
    # Get all sessions
    response_all = client.get('/api/sessions')
    assert response_all.status_code == 200
    all_sessions = json.loads(response_all.data)
    # Should have at least 3 sessions
    assert len(all_sessions) >= 3
    
    # Get limited sessions
    response_limited = client.get('/api/sessions?limit=2')
    assert response_limited.status_code == 200
    limited_sessions = json.loads(response_limited.data)
    assert len(limited_sessions) == 2
    
    # Verify sessions are sorted by last_updated desc (newest first)
    assert limited_sessions[0]['created_at'] >= limited_sessions[1]['created_at']


def test_get_sessions_sorted_by_last_updated(client, temp_sessions_dir):
    """Test GET /api/sessions returns sessions sorted by last_updated desc."""
    # Create exactly 3 new sessions
    session_ids = []
    for title in ['First', 'Second', 'Third']:
        response = client.post('/api/sessions',
                              json={'title': title},
                              content_type='application/json')
        assert response.status_code == 201
        session_data = json.loads(response.data)
        session_ids.append(session_data['id'])
    
    # Get sessions
    response = client.get('/api/sessions')
    assert response.status_code == 200
    sessions = json.loads(response.data)
    
    # Should have at least 3 sessions
    assert len(sessions) >= 3
    
    # Verify the sessions we just created are sorted by last_updated (newest first)
    our_sessions = [s for s in sessions if s['id'] in session_ids]
    assert len(our_sessions) == 3
    assert our_sessions[0]['last_updated'] >= our_sessions[1]['last_updated']
    assert our_sessions[1]['last_updated'] >= our_sessions[2]['last_updated']


def test_sessions_page_renders(client):
    """Test that the sessions page renders successfully."""
    response = client.get('/sessions')
    assert response.status_code == 200
    assert b'Session Management' in response.data
    assert b'Create New Session' in response.data


def test_sessions_page_contains_expected_elements(client):
    """Test that the sessions page contains expected placeholder elements."""
    response = client.get('/sessions')
    assert response.status_code == 200
    
    # Check for key elements that should be present
    assert b'sessions-container' in response.data
    assert b'new-session-form' in response.data
    assert b'sessions-table-body' in response.data
    assert b'empty-state' in response.data
    assert b'loading-spinner' in response.data


def test_session_data_format(client, temp_sessions_dir):
    """Test that session data has the expected format."""
    # Create a session
    response = client.post('/api/sessions', 
                          json={
                              'title': 'Test Session',
                              'tags': ['test', 'demo']
                          },
                          content_type='application/json')
    
    assert response.status_code == 201
    data = json.loads(response.data)
    
    # Verify all expected fields are present
    assert 'id' in data
    assert 'created_at' in data
    assert 'last_updated' in data
    assert 'title' in data
    assert 'tags' in data
    
    # Verify data types and values
    assert isinstance(data['id'], str)
    assert isinstance(data['created_at'], str)
    assert isinstance(data['last_updated'], str)
    assert data['title'] == 'Test Session'
    assert isinstance(data['tags'], list)
    assert data['tags'] == ['test', 'demo']


def test_session_id_format(client, temp_sessions_dir):
    """Test that session IDs are properly formatted."""
    # Create a session
    response = client.post('/api/sessions',
                          json={'title': 'Test Session'},
                          content_type='application/json')
    
    assert response.status_code == 201
    session_data = json.loads(response.data)
    session_id = session_data['id']
    
    # Verify the session ID is a valid UUID format (with dashes)
    assert len(session_id) == 36  # UUID with dashes
    # Basic UUID format validation
    parts = session_id.split('-')
    assert len(parts) == 5
    assert len(parts[0]) == 8
    assert len(parts[1]) == 4
    assert len(parts[2]) == 4
    assert len(parts[3]) == 4
    assert len(parts[4]) == 12
