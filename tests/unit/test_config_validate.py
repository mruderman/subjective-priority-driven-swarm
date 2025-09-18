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


def test_validate_letta_config_requires_base_url(monkeypatch):
    monkeypatch.setenv("LETTA_BASE_URL", "")

    from spds import config

    with pytest.raises(ValueError):
        config.validate_letta_config(check_connectivity=False)


def test_validate_letta_config_skips_when_requests_missing(monkeypatch, caplog):
    monkeypatch.setenv("LETTA_BASE_URL", "http://localhost:8283")
    monkeypatch.setenv("LETTA_ENVIRONMENT", "SELF_HOSTED")

    import builtins

    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "requests":
            raise ImportError("no requests")
        return real_import(name, *args, **kwargs)

    from spds import config

    monkeypatch.setattr(builtins, "__import__", fake_import)

    caplog.clear()
    with caplog.at_level("WARNING"):
        assert config.validate_letta_config(check_connectivity=True) is True
    assert "skipping LETTA server connectivity check" in caplog.text


def test_validate_letta_config_raises_on_bad_status(monkeypatch):
    monkeypatch.setenv("LETTA_BASE_URL", "http://api.example")
    monkeypatch.setenv("LETTA_ENVIRONMENT", "SELF_HOSTED")

    class DummyResp:
        status_code = 503
        text = "unavailable"

    def fake_get(url, timeout):
        return DummyResp()

    import requests

    monkeypatch.setattr(requests, "get", fake_get)

    from spds import config

    with pytest.raises(RuntimeError):
        config.validate_letta_config(check_connectivity=True)


def test_get_letta_password_preference_letta_password_only(monkeypatch, caplog):
    """Test that LETTA_PASSWORD is used when only it is set."""
    monkeypatch.setenv("LETTA_PASSWORD", "new_password")
    monkeypatch.delenv("LETTA_SERVER_PASSWORD", raising=False)

    from spds import config

    caplog.clear()
    result = config.get_letta_password()

    assert result == "new_password"
    # Should not log any deprecation warning or preference message
    assert "Preferring LETTA_PASSWORD" not in caplog.text
    assert "deprecated" not in caplog.text


def test_get_letta_password_deprecation_server_password_only(monkeypatch, caplog):
    """Test that LETTA_SERVER_PASSWORD triggers deprecation warning."""
    monkeypatch.delenv("LETTA_PASSWORD", raising=False)
    monkeypatch.setenv("LETTA_SERVER_PASSWORD", "old_password")

    from spds import config

    caplog.clear()
    with caplog.at_level("WARNING"):
        result = config.get_letta_password()

    assert result == "old_password"
    assert "deprecated LETTA_SERVER_PASSWORD" in caplog.text
    assert "migrate to LETTA_PASSWORD" in caplog.text


def test_get_letta_password_preference_both_set(monkeypatch, caplog):
    """Test that LETTA_PASSWORD is preferred when both are set."""
    monkeypatch.setenv("LETTA_PASSWORD", "new_password")
    monkeypatch.setenv("LETTA_SERVER_PASSWORD", "old_password")

    from spds import config

    caplog.clear()
    with caplog.at_level("INFO"):
        result = config.get_letta_password()

    assert result == "new_password"
    assert "Preferring LETTA_PASSWORD over LETTA_SERVER_PASSWORD" in caplog.text


def test_get_letta_password_neither_set(monkeypatch, caplog):
    """Test that empty string is returned when neither is set."""
    monkeypatch.delenv("LETTA_PASSWORD", raising=False)
    monkeypatch.delenv("LETTA_SERVER_PASSWORD", raising=False)

    from spds import config

    caplog.clear()
    result = config.get_letta_password()

    assert result == ""
    # Should not log any messages
    assert caplog.text == ""
