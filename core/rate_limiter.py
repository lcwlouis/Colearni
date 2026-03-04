"""Concurrency limiter and retry logic for outbound API calls.

Provides a threading-based semaphore gate that limits the number of
simultaneous LLM / embedding API calls, plus exponential-backoff retry
on rate-limit (HTTP 429) errors.  All knobs are driven by ``core.settings``.
"""

from __future__ import annotations

import logging
import random
import threading
import time
from collections.abc import Callable
from functools import wraps
from typing import TypeVar
from urllib.error import HTTPError

log = logging.getLogger("core.rate_limiter")

T = TypeVar("T")

# ---------------------------------------------------------------------------
# Rate-limit error detection
# ---------------------------------------------------------------------------

def _is_rate_limit_error(exc: BaseException) -> bool:
    """Return True when *exc* signals a provider rate-limit (HTTP 429)."""
    # OpenAI SDK raises openai.RateLimitError (status 429)
    cls_name = type(exc).__name__
    if cls_name == "RateLimitError":
        return True

    # urllib.error.HTTPError with code 429
    if isinstance(exc, HTTPError) and exc.code == 429:
        return True

    # LiteLLM wraps rate limits in its own exception hierarchy
    if cls_name == "RateLimitError" or "rate" in cls_name.lower():
        return True

    # RuntimeError wrapping a 429 from our own adapters
    inner = exc.__cause__ or exc.__context__
    if inner is not None:
        return _is_rate_limit_error(inner)

    # Check message as last resort
    msg = str(exc).lower()
    if "429" in msg or "rate limit" in msg or "rate_limit" in msg:
        return True

    return False


# ---------------------------------------------------------------------------
# Core rate limiter
# ---------------------------------------------------------------------------

class RateLimiter:
    """Thread-safe concurrency gate with retry-on-429 behaviour.

    Parameters
    ----------
    max_concurrent:
        Maximum number of API calls that may execute simultaneously.
    max_retries:
        How many times to retry after a rate-limit error (0 = no retries).
    base_delay:
        Base delay in seconds for exponential backoff (with jitter).
    name:
        Human-readable label used in log messages.
    """

    def __init__(
        self,
        max_concurrent: int = 3,
        max_retries: int = 3,
        base_delay: float = 1.0,
        name: str = "api",
    ) -> None:
        if max_concurrent < 1:
            raise ValueError("max_concurrent must be >= 1")
        self._semaphore = threading.Semaphore(max_concurrent)
        self._max_retries = max(max_retries, 0)
        self._base_delay = max(base_delay, 0.1)
        self._name = name
        log.info(
            "%s rate-limiter initialised: max_concurrent=%d, max_retries=%d, base_delay=%.1fs",
            name,
            max_concurrent,
            max_retries,
            base_delay,
        )

    # -- public API ----------------------------------------------------------

    def execute(self, fn: Callable[..., T], *args: object, **kwargs: object) -> T:
        """Run *fn* under the concurrency gate with retry-on-429.

        Non-rate-limit exceptions propagate immediately.
        """
        attempt = 0
        while True:
            self._semaphore.acquire()
            try:
                return fn(*args, **kwargs)
            except Exception as exc:
                if not _is_rate_limit_error(exc) or attempt >= self._max_retries:
                    raise
                delay = self._backoff_delay(attempt)
                log.warning(
                    "%s rate-limited (attempt %d/%d), retrying in %.1fs: %s",
                    self._name,
                    attempt + 1,
                    self._max_retries,
                    delay,
                    exc,
                )
                time.sleep(delay)
                attempt += 1
            finally:
                self._semaphore.release()

    def wrap(self, fn: Callable[..., T]) -> Callable[..., T]:
        """Decorator form of :meth:`execute`."""

        @wraps(fn)
        def _wrapper(*args: object, **kwargs: object) -> T:
            return self.execute(fn, *args, **kwargs)

        return _wrapper

    # -- helpers -------------------------------------------------------------

    def _backoff_delay(self, attempt: int) -> float:
        """Exponential backoff with full jitter."""
        max_delay = self._base_delay * (2 ** attempt)
        return random.uniform(0, max_delay)  # noqa: S311


# ---------------------------------------------------------------------------
# Global singleton instances (lazily created from settings)
# ---------------------------------------------------------------------------

_llm_limiter: RateLimiter | None = None
_embedding_limiter: RateLimiter | None = None
_lock = threading.Lock()


def get_llm_limiter() -> RateLimiter:
    """Return the process-wide LLM rate limiter (created on first call)."""
    global _llm_limiter  # noqa: PLW0603
    if _llm_limiter is None:
        with _lock:
            if _llm_limiter is None:
                from core.settings import get_settings  # noqa: PLC0415

                s = get_settings()
                _llm_limiter = RateLimiter(
                    max_concurrent=s.llm_max_concurrent_calls,
                    max_retries=s.api_retry_max_attempts,
                    base_delay=s.api_retry_base_delay,
                    name="llm",
                )
    return _llm_limiter


def get_embedding_limiter() -> RateLimiter:
    """Return the process-wide embedding rate limiter (created on first call)."""
    global _embedding_limiter  # noqa: PLW0603
    if _embedding_limiter is None:
        with _lock:
            if _embedding_limiter is None:
                from core.settings import get_settings  # noqa: PLC0415

                s = get_settings()
                _embedding_limiter = RateLimiter(
                    max_concurrent=s.embedding_max_concurrent_calls,
                    max_retries=s.api_retry_max_attempts,
                    base_delay=s.api_retry_base_delay,
                    name="embedding",
                )
    return _embedding_limiter


def reset_limiters() -> None:
    """Reset global limiters (useful for testing)."""
    global _llm_limiter, _embedding_limiter  # noqa: PLW0603
    with _lock:
        _llm_limiter = None
        _embedding_limiter = None
