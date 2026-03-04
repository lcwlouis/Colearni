"""Unit tests for core.rate_limiter."""

from __future__ import annotations

import threading
import time
from unittest.mock import MagicMock, patch
from urllib.error import HTTPError

import pytest

from core.rate_limiter import (
    RateLimiter,
    _is_rate_limit_error,
    get_embedding_limiter,
    get_llm_limiter,
    reset_limiters,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class FakeRateLimitError(Exception):
    """Simulates a provider rate-limit error detected by class name."""


# Rename so _is_rate_limit_error matches on cls.__name__
FakeRateLimitError.__name__ = "RateLimitError"


class FakeHTTP429Error(HTTPError):
    """HTTPError with status 429."""

    def __init__(self) -> None:
        super().__init__(url="https://x", code=429, msg="Too Many Requests", hdrs=None, fp=None)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_execute_returns_result() -> None:
    limiter = RateLimiter(max_concurrent=1, max_retries=0, base_delay=0.1, name="test")
    assert limiter.execute(lambda x: x * 2, 5) == 10


def test_semaphore_limits_concurrency() -> None:
    limiter = RateLimiter(max_concurrent=2, max_retries=0, base_delay=0.1, name="test")
    peak = 0
    current = 0
    lock = threading.Lock()

    def slow_fn() -> None:
        nonlocal peak, current
        with lock:
            current += 1
            if current > peak:
                peak = current
        time.sleep(0.05)
        with lock:
            current -= 1

    threads = [threading.Thread(target=limiter.execute, args=(slow_fn,)) for _ in range(6)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert peak <= 2


def test_retry_on_rate_limit_error() -> None:
    limiter = RateLimiter(max_concurrent=1, max_retries=3, base_delay=0.01, name="test")
    call_count = 0

    def flaky() -> str:
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise FakeRateLimitError("rate limited")
        return "ok"

    with patch("core.rate_limiter.time.sleep"):
        result = limiter.execute(flaky)

    assert result == "ok"
    assert call_count == 3


def test_no_retry_on_non_rate_limit_error() -> None:
    limiter = RateLimiter(max_concurrent=1, max_retries=3, base_delay=0.01, name="test")
    call_count = 0

    def always_fail() -> None:
        nonlocal call_count
        call_count += 1
        raise ValueError("bad input")

    with pytest.raises(ValueError, match="bad input"):
        limiter.execute(always_fail)

    assert call_count == 1


def test_max_retries_exceeded() -> None:
    limiter = RateLimiter(max_concurrent=1, max_retries=2, base_delay=0.01, name="test")
    call_count = 0

    def always_rate_limited() -> None:
        nonlocal call_count
        call_count += 1
        raise FakeRateLimitError("rate limited")

    with patch("core.rate_limiter.time.sleep"):
        with pytest.raises(FakeRateLimitError):
            limiter.execute(always_rate_limited)

    # 1 initial + 2 retries = 3
    assert call_count == 3


def test_is_rate_limit_error_detection() -> None:
    # RateLimitError class name
    assert _is_rate_limit_error(FakeRateLimitError("boom")) is True

    # HTTPError with 429
    assert _is_rate_limit_error(FakeHTTP429Error()) is True

    # RuntimeError wrapping a 429
    inner = FakeRateLimitError("inner")
    outer = RuntimeError("wrapped")
    outer.__cause__ = inner
    assert _is_rate_limit_error(outer) is True

    # Message-based detection
    assert _is_rate_limit_error(Exception("rate limit exceeded")) is True
    assert _is_rate_limit_error(Exception("got 429 from server")) is True

    # Non-rate-limit errors
    assert _is_rate_limit_error(ValueError("bad input")) is False
    assert _is_rate_limit_error(RuntimeError("timeout")) is False


def test_wrap_decorator() -> None:
    limiter = RateLimiter(max_concurrent=1, max_retries=0, base_delay=0.1, name="test")

    @limiter.wrap
    def add(a: int, b: int) -> int:
        return a + b

    assert add(3, 4) == 7


def test_global_limiters_use_settings() -> None:
    reset_limiters()
    try:
        mock_settings = MagicMock()
        mock_settings.llm_max_concurrent_calls = 5
        mock_settings.embedding_max_concurrent_calls = 10
        mock_settings.api_retry_max_attempts = 7
        mock_settings.api_retry_base_delay = 2.0

        with patch("core.settings.get_settings", return_value=mock_settings):
            llm = get_llm_limiter()
            emb = get_embedding_limiter()

        assert llm._max_retries == 7
        assert llm._base_delay == 2.0
        assert llm._name == "llm"

        assert emb._max_retries == 7
        assert emb._base_delay == 2.0
        assert emb._name == "embedding"
    finally:
        reset_limiters()
