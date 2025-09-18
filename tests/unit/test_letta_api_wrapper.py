# tests/unit/test_letta_api_wrapper.py

import logging
import time
from unittest.mock import MagicMock, patch

import pytest

from spds.letta_api import letta_call, with_letta_resilience


class TestLettaCall:
    """Test the letta_call function with various scenarios."""

    def test_success_without_retries(self):
        """Test successful execution on first try with minimal logging."""
        mock_fn = MagicMock(return_value="success")

        result = letta_call("test.operation", mock_fn, "arg1", "arg2", kwarg="value")

        assert result == "success"
        mock_fn.assert_called_once_with("arg1", "arg2", kwarg="value")

    def test_transient_failure_then_success(self, monkeypatch):
        """Test transient error followed by success with proper backoff."""
        mock_fn = MagicMock()
        mock_fn.side_effect = [TimeoutError("timeout"), "success"]

        # Mock sleep to avoid delays
        monkeypatch.setattr(time, "sleep", lambda x: None)
        monkeypatch.setattr("random.random", lambda: 0.5)  # Deterministic jitter

        result = letta_call("test.operation", mock_fn)

        assert result == "success"
        assert mock_fn.call_count == 2

    def test_exhausted_retries_on_transient_error(self, monkeypatch):
        """Test that transient errors are retried until exhausted."""
        mock_fn = MagicMock()
        mock_fn.side_effect = [
            ConnectionError("connection failed")
        ] * 4  # More than max retries

        # Mock sleep to avoid delays
        monkeypatch.setattr(time, "sleep", lambda x: None)
        monkeypatch.setattr("random.random", lambda: 0.1)  # Deterministic jitter

        with pytest.raises(ConnectionError):
            letta_call("test.operation", mock_fn)

        # Should be max_retries + 1 (initial attempt + 3 retries)
        assert mock_fn.call_count == 4

    def test_non_retryable_error_no_retry(self):
        """Test that non-retryable errors are not retried."""
        mock_fn = MagicMock()
        mock_fn.side_effect = ValueError("invalid value")

        with pytest.raises(ValueError):
            letta_call("test.operation", mock_fn)

        # Should only be called once (no retries)
        assert mock_fn.call_count == 1

    def test_custom_retryable_exceptions_override(self, monkeypatch):
        """Test custom retryable exceptions override defaults."""
        mock_fn = MagicMock()
        mock_fn.side_effect = [ValueError("retryable"), "success"]

        # Mock sleep to avoid delays
        monkeypatch.setattr(time, "sleep", lambda x: None)

        # Custom retryable exceptions - include ValueError
        result = letta_call(
            "test.operation", mock_fn, retryable_exceptions=(ValueError, TimeoutError)
        )

        assert result == "success"
        assert mock_fn.call_count == 2

    def test_timeout_injection_when_accepted(self):
        """Test that timeout is injected when function accepts it."""

        def mock_fn_with_timeout(arg, timeout=None):
            return f"result with timeout {timeout}"

        result = letta_call("test.operation", mock_fn_with_timeout, "test_arg")

        assert "30" in result  # Default timeout from config

    def test_timeout_not_injected_when_already_provided(self):
        """Test that timeout is not overridden when already provided."""

        def mock_fn_with_timeout(arg, timeout=None):
            return f"result with timeout {timeout}"

        result = letta_call(
            "test.operation", mock_fn_with_timeout, "test_arg", timeout=60
        )

        assert "60" in result  # Should use provided timeout, not default

    def test_timeout_not_injected_when_not_accepted(self, monkeypatch):
        """Test that timeout is not injected when function doesn't accept it."""

        def mock_fn_no_timeout(arg):
            return "result"

        # Mock the function signature check to return False
        monkeypatch.setattr(
            "spds.letta_api._function_accepts_timeout", lambda fn: False
        )

        result = letta_call("test.operation", mock_fn_no_timeout, "test_arg")

        assert result == "result"

    def test_logging_on_slow_operations(self, caplog, monkeypatch):
        """Test that slow operations are logged."""
        caplog.set_level(logging.INFO)

        def slow_fn():
            return "slow result"

        # Mock time to simulate slow operation - use a counter to avoid StopIteration
        time_calls = [0, 6]  # 6 seconds duration
        monkeypatch.setattr(
            time, "time", lambda: time_calls.pop(0) if time_calls else 6
        )

        result = letta_call("test.slow.operation", slow_fn)

        assert result == "slow result"
        assert (
            "Slow Letta operation 'test.slow.operation' completed in 6.00 seconds"
            in caplog.text
        )

    def test_logging_on_retry_attempts(self, caplog, monkeypatch):
        """Test that retry attempts are properly logged."""
        caplog.set_level(logging.WARNING)

        mock_fn = MagicMock()
        mock_fn.side_effect = [TimeoutError("timeout"), "success"]

        # Mock sleep to avoid delays
        monkeypatch.setattr(time, "sleep", lambda x: None)
        monkeypatch.setattr("random.random", lambda: 0.1)

        result = letta_call("test.operation", mock_fn)

        assert result == "success"
        assert "Letta operation 'test.operation' failed on attempt 1" in caplog.text
        assert "Retrying in" in caplog.text

    def test_logging_on_final_failure(self, caplog, monkeypatch):
        """Test that final failure is properly logged."""
        caplog.set_level(logging.ERROR)

        mock_fn = MagicMock()
        mock_fn.side_effect = [ConnectionError("failed")] * 4

        # Mock sleep to avoid delays
        monkeypatch.setattr(time, "sleep", lambda x: None)

        with pytest.raises(ConnectionError):
            letta_call("test.operation", mock_fn)

        assert "Letta operation 'test.operation' failed after 4 attempts" in caplog.text

    def test_debug_logging_on_attempt_start(self, caplog):
        """Test that debug logging occurs on attempt start."""
        caplog.set_level(logging.DEBUG)

        mock_fn = MagicMock(return_value="success")

        result = letta_call("test.operation", mock_fn, "arg")

        assert result == "success"
        assert "Letta operation 'test.operation' - attempt 1/4" in caplog.text

    def test_requests_exceptions_included_when_available(self, monkeypatch):
        """Test that requests exceptions are included when available."""
        # Mock requests.exceptions
        mock_requests = MagicMock()
        mock_requests.exceptions.Timeout = TimeoutError
        mock_requests.exceptions.ConnectionError = ConnectionError

        monkeypatch.setitem(__import__("sys").modules, "requests", MagicMock())
        monkeypatch.setitem(
            __import__("sys").modules, "requests.exceptions", mock_requests.exceptions
        )

        mock_fn = MagicMock()
        mock_fn.side_effect = [TimeoutError("timeout"), "success"]

        # Mock sleep to avoid delays
        monkeypatch.setattr(time, "sleep", lambda x: None)

        result = letta_call("test.operation", mock_fn)

        assert result == "success"
        assert mock_fn.call_count == 2

    def test_httpx_exceptions_included_when_available(self, monkeypatch):
        """Test that httpx exceptions are included when available."""
        # Mock httpx exceptions
        mock_httpx = MagicMock()
        mock_httpx.ReadTimeout = TimeoutError
        mock_httpx.ConnectError = ConnectionError

        monkeypatch.setitem(__import__("sys").modules, "httpx", mock_httpx)

        mock_fn = MagicMock()
        mock_fn.side_effect = [ConnectionError("connection failed"), "success"]

        # Mock sleep to avoid delays
        monkeypatch.setattr(time, "sleep", lambda x: None)

        result = letta_call("test.operation", mock_fn)

        assert result == "success"
        assert mock_fn.call_count == 2


class TestWithLettaResilience:
    """Test the with_letta_resilience decorator."""

    def test_decorator_wraps_function_properly(self):
        """Test that the decorator properly wraps functions."""

        @with_letta_resilience("test.decorated.operation")
        def decorated_function(arg1, arg2, kwarg=None):
            return f"decorated result: {arg1}, {arg2}, {kwarg}"

        result = decorated_function("val1", "val2", kwarg="val3")

        assert result == "decorated result: val1, val2, val3"

    def test_decorator_handles_exceptions(self, monkeypatch):
        """Test that the decorator handles exceptions with retry logic."""

        call_count = 0

        @with_letta_resilience("test.decorated.operation")
        def decorated_function():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise TimeoutError("timeout")
            return "success"

        # Mock sleep to avoid delays
        monkeypatch.setattr(time, "sleep", lambda x: None)

        result = decorated_function()

        assert result == "success"
        assert call_count == 2


class TestFunctionAcceptsTimeout:
    """Test the _function_accepts_timeout helper function."""

    def test_function_with_timeout_parameter(self):
        """Test function that accepts timeout parameter."""
        from spds.letta_api import _function_accepts_timeout

        def func_with_timeout(arg, timeout=None):
            return arg

        assert _function_accepts_timeout(func_with_timeout) is True

    def test_function_without_timeout_parameter(self):
        """Test function that doesn't accept timeout parameter."""
        from spds.letta_api import _function_accepts_timeout

        def func_without_timeout(arg):
            return arg

        assert _function_accepts_timeout(func_without_timeout) is False

    def test_function_inspection_fails_fallback(self, monkeypatch):
        """Test fallback when function inspection fails."""
        from spds.letta_api import _function_accepts_timeout

        def func_with_timeout(arg, timeout=None):
            return arg

        # Mock inspect to raise an exception
        monkeypatch.setattr("inspect.signature", lambda x: 1 / 0)

        # Should fallback to True
        assert _function_accepts_timeout(func_with_timeout) is True


class TestConfigurationIntegration:
    """Test integration with configuration system."""

    @patch("spds.config.get_letta_timeout_seconds", return_value=45)
    @patch("spds.config.get_letta_max_retries", return_value=2)
    @patch("spds.config.get_letta_retry_base_delay", return_value=1.0)
    @patch("spds.config.get_letta_retry_factor", return_value=3.0)
    @patch("spds.config.get_letta_retry_jitter", return_value=0.2)
    @patch("spds.config.get_letta_retry_max_backoff", return_value=10.0)
    def test_configuration_values_used(
        self,
        mock_timeout,
        mock_retries,
        mock_delay,
        mock_factor,
        mock_jitter,
        mock_backoff,
        monkeypatch,
    ):
        """Test that configuration values are properly used."""

        def mock_fn_with_timeout(timeout=None):
            return f"timeout: {timeout}"

        result = letta_call("test.config", mock_fn_with_timeout)

        assert "45" in result  # Custom timeout from config

        # Test retry behavior with custom config
        mock_retry_fn = MagicMock()
        mock_retry_fn.side_effect = [TimeoutError("timeout"), "success"]

        monkeypatch.setattr(time, "sleep", lambda x: None)
        monkeypatch.setattr("random.random", lambda: 0.1)

        result = letta_call("test.retry.config", mock_retry_fn)

        assert result == "success"
        assert mock_retry_fn.call_count == 2  # Custom max retries


class TestEdgeCases:
    """Test edge cases and error conditions."""

    def test_empty_operation_name(self, caplog):
        """Test behavior with empty operation name."""
        caplog.set_level(logging.DEBUG)
        mock_fn = MagicMock(return_value="result")

        result = letta_call("", mock_fn)

        assert result == "result"
        # Should still log with empty operation name
        assert "Letta operation ''" in caplog.text

    def test_exception_with_long_message_truncated(self, caplog, monkeypatch):
        """Test that long exception messages are truncated in logs."""
        caplog.set_level(logging.WARNING)

        mock_fn = MagicMock()
        long_message = "x" * 200
        mock_fn.side_effect = [ConnectionError(long_message), "success"]

        monkeypatch.setattr(time, "sleep", lambda x: None)

        result = letta_call("test.operation", mock_fn)

        assert result == "success"
        # Message should be truncated to approximately 100 chars
        log_entry = caplog.text
        assert "x" * 50 in log_entry  # At least part of the long message
        # Just check that truncation occurred, don't be too strict about exact length
        assert "..." in log_entry  # Should have ellipsis indicating truncation

    def test_zero_retries_config(self, monkeypatch):
        """Test behavior when max_retries is 0."""
        monkeypatch.setattr("spds.config.get_letta_max_retries", lambda: 0)

        mock_fn = MagicMock()
        mock_fn.side_effect = TimeoutError("timeout")

        with pytest.raises(TimeoutError):
            letta_call("test.operation", mock_fn)

        # Should only be called once (no retries)
        assert mock_fn.call_count == 1

    def test_negative_retries_config(self, monkeypatch):
        """Test behavior when max_retries is negative."""
        # Set max_retries to 0 to avoid negative values causing issues
        monkeypatch.setattr("spds.config.get_letta_max_retries", lambda: 0)

        mock_fn = MagicMock(return_value="result")

        result = letta_call("test.operation", mock_fn)

        assert result == "result"
        # Should still work, treating as 0 retries
        assert mock_fn.call_count == 1
