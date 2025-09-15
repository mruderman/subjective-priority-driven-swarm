import pytest


def test_validate_letta_config_local_default(monkeypatch):
    """Local SELF_HOSTED with default localhost should pass validation."""
    # Ensure environment variables are controlled
    monkeypatch.delenv("LETTA_API_KEY", raising=False)
    monkeypatch.delenv("LETTA_PASSWORD", raising=False)
    monkeypatch.setenv("LETTA_BASE_URL", "http://localhost:8283")
    monkeypatch.setenv("LETTA_ENVIRONMENT", "SELF_HOSTED")

    from spds import config

    assert config.validate_letta_config(check_connectivity=False) is True


def test_validate_letta_config_cloud_requires_api_key(monkeypatch):
    """LETTA_CLOUD must require an API key."""
    monkeypatch.setenv("LETTA_ENVIRONMENT", "LETTA_CLOUD")
    monkeypatch.delenv("LETTA_API_KEY", raising=False)
    monkeypatch.setenv("LETTA_BASE_URL", "https://api.letta.example")

    from spds import config

    with pytest.raises(ValueError):
        config.validate_letta_config(check_connectivity=False)


def test_validate_letta_config_connectivity_failure(monkeypatch):
    """Simulate requests.get raising to ensure connectivity errors surface."""
    monkeypatch.setenv("LETTA_ENVIRONMENT", "SELF_HOSTED")
    monkeypatch.setenv("LETTA_BASE_URL", "http://localhost:8283")

    # Provide requests but simulate a connection problem
    class DummyResp:
        status_code = 500
        text = "Internal Error"


    def fake_get(url, timeout):
        raise Exception("connection refused")

    monkeypatch.setenv("LETTA_API_KEY", "")
    # Patch the top-level requests.get so the import inside the validator uses the mocked function
    import requests
    monkeypatch.setattr(requests, "get", fake_get)

    from spds import config

    with pytest.raises(RuntimeError):
        config.validate_letta_config(check_connectivity=True)
