# spds/letta_api.py

import logging
import random
import socket
import time
from typing import Any, Callable, Optional, Tuple, Type

from . import config

logger = logging.getLogger(__name__)


def letta_call(
    operation_name: str,
    fn: Callable,
    *args,
    retryable_exceptions: Optional[Tuple[Type[Exception], ...]] = None,
    **kwargs,
) -> Any:
    """
    Execute a Letta-related callable with standardized timeout, retries, and logging.

    This wrapper provides resilience for Letta API calls with:
    - Configurable timeout injection
    - Exponential backoff retry logic for transient errors
    - Comprehensive logging of attempts, failures, and slow operations
    - Customizable retryable exception types

    Args:
        operation_name: Descriptive name for the operation (used in logging)
        fn: The callable to execute (typically a Letta client method)
        retryable_exceptions: Optional tuple of exception types to retry.
                             Defaults to transient network/timeout errors.
        *args: Positional arguments to pass to fn
        **kwargs: Keyword arguments to pass to fn

    Returns:
        The result of the successful fn call

    Raises:
        The last exception encountered after all retries are exhausted
    """
    # Get configuration values
    timeout_seconds = config.get_letta_timeout_seconds()
    max_retries = config.get_letta_max_retries()
    base_delay = config.get_letta_retry_base_delay()
    factor = config.get_letta_retry_factor()
    jitter = config.get_letta_retry_jitter()
    max_backoff = config.get_letta_retry_max_backoff()

    # Default retryable exceptions (transient network/timeout errors)
    if retryable_exceptions is None:
        retryable_exceptions = (
            TimeoutError,
            ConnectionError,
            socket.timeout,
        )

        # Add requests exceptions if available
        try:
            import requests.exceptions

            retryable_exceptions += (
                requests.exceptions.Timeout,
                requests.exceptions.ConnectionError,
            )
        except ImportError:
            pass

        # Add httpx exceptions if available
        try:
            import httpx

            retryable_exceptions += (
                httpx.ReadTimeout,
                httpx.ConnectError,
            )
        except ImportError:
            pass

    # Inject timeout if not already provided and function accepts it
    if "timeout" not in kwargs and _function_accepts_timeout(fn):
        kwargs["timeout"] = timeout_seconds

    last_exception = None

    for attempt in range(max_retries + 1):
        try:
            # Log attempt start
            logger.debug(
                f"Letta operation '{operation_name}' - attempt {attempt + 1}/{max_retries + 1}, "
                f"timeout={kwargs.get('timeout', 'none')}"
            )

            # Record start time for performance monitoring
            start_time = time.time()

            # Execute the function
            result = fn(*args, **kwargs)

            # Check for slow operations
            duration = time.time() - start_time
            if duration > 5.0:  # 5 second threshold for slow operations
                logger.info(
                    f"Slow Letta operation '{operation_name}' completed in {duration:.2f} seconds"
                )

            return result

        except Exception as e:
            last_exception = e
            duration = time.time() - start_time

            # Check if this is a retryable exception
            is_retryable = isinstance(e, retryable_exceptions)

            if not is_retryable:
                # Non-retryable error - log and re-raise immediately
                logger.error(
                    f"Non-retryable error in Letta operation '{operation_name}': {type(e).__name__}: {e}"
                )
                raise

            if attempt < max_retries:
                # Calculate backoff delay with jitter
                delay = min(base_delay * (factor**attempt), max_backoff)
                jittered_delay = delay + random.uniform(0, jitter)

                logger.warning(
                    f"Letta operation '{operation_name}' failed on attempt {attempt + 1}: "
                    f"{type(e).__name__}: {str(e)[:100]}... "
                    f"Retrying in {jittered_delay:.2f} seconds"
                )

                time.sleep(jittered_delay)
            else:
                # Final attempt failed
                logger.error(
                    f"Letta operation '{operation_name}' failed after {max_retries + 1} attempts. "
                    f"Last error: {type(e).__name__}: {str(e)[:100]}..."
                )

    # All retries exhausted - re-raise the last exception
    if last_exception:
        raise last_exception


def with_letta_resilience(operation_name: str):
    """
    Decorator that wraps a function to use letta_call internally.

    This decorator provides a convenient way to add Letta resilience to existing functions
    without modifying their signatures. The decorated function will be executed with
    the same retry, timeout, and logging logic as letta_call.

    Args:
        operation_name: Descriptive name for the operation (used in logging)

    Returns:
        Decorator function that wraps the target function
    """

    def decorator(fn: Callable) -> Callable:
        def wrapper(*args, **kwargs):
            return letta_call(operation_name, fn, *args, **kwargs)

        return wrapper

    return decorator


def _function_accepts_timeout(fn: Callable) -> bool:
    """
    Check if a function accepts a 'timeout' parameter.

    This helper function inspects the function signature to determine if it accepts
    a 'timeout' keyword argument, which is used for timeout injection in letta_call.

    Args:
        fn: The function to inspect

    Returns:
        True if the function accepts a 'timeout' parameter, False otherwise
    """
    try:
        import inspect

        sig = inspect.signature(fn)
        return "timeout" in sig.parameters
    except Exception:
        # Fallback: assume it accepts timeout if we can't inspect
        return True
