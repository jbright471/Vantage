from __future__ import annotations

import os
import threading
import time
from collections import deque
from dataclasses import dataclass


LLM_RATE_ENV = "VANTAGE_LLM_REQUESTS_PER_MINUTE"
LLM_CONCURRENCY_ENV = "VANTAGE_LLM_MAX_CONCURRENCY"
DEFAULT_LLM_REQUESTS_PER_MINUTE = 12
DEFAULT_LLM_MAX_CONCURRENCY = 2

_state_lock = threading.Lock()
_request_windows: dict[str, deque[float]] = {}
_semaphore: threading.BoundedSemaphore | None = None
_semaphore_limit: int | None = None


def _bounded_env_int(name: str, default: int, *, minimum: int, maximum: int) -> int:
    try:
        value = int(os.getenv(name, str(default)))
    except ValueError:
        return default
    return max(minimum, min(value, maximum))


def is_costly_request(method: str, path: str) -> bool:
    if method.upper() != "POST":
        return False
    return (
        path == "/api/evals/assisted-summary"
        or path == "/api/models/capability-check"
        or (path.startswith("/api/evals/") and path.endswith("/execute"))
    )


class ResourceLease:
    def __init__(self, semaphore: threading.BoundedSemaphore) -> None:
        self._semaphore = semaphore
        self._released = False

    def release(self) -> None:
        if not self._released:
            self._semaphore.release()
            self._released = True


@dataclass(frozen=True)
class ResourceLimitResult:
    lease: ResourceLease | None
    reason: str | None = None


def acquire_costly_request(source: str, *, now: float | None = None) -> ResourceLimitResult:
    global _semaphore, _semaphore_limit

    current_time = time.monotonic() if now is None else now
    rate_limit = _bounded_env_int(
        LLM_RATE_ENV,
        DEFAULT_LLM_REQUESTS_PER_MINUTE,
        minimum=1,
        maximum=1000,
    )
    concurrency_limit = _bounded_env_int(
        LLM_CONCURRENCY_ENV,
        DEFAULT_LLM_MAX_CONCURRENCY,
        minimum=1,
        maximum=8,
    )

    with _state_lock:
        window = _request_windows.setdefault(source, deque())
        while window and current_time - window[0] >= 60:
            window.popleft()
        if len(window) >= rate_limit:
            return ResourceLimitResult(lease=None, reason="rate")
        window.append(current_time)

        if _semaphore is None or _semaphore_limit != concurrency_limit:
            _semaphore = threading.BoundedSemaphore(concurrency_limit)
            _semaphore_limit = concurrency_limit
        semaphore = _semaphore

    if not semaphore.acquire(blocking=False):
        return ResourceLimitResult(lease=None, reason="concurrency")
    return ResourceLimitResult(lease=ResourceLease(semaphore))


def clear_resource_limit_state() -> None:
    global _semaphore, _semaphore_limit
    with _state_lock:
        _request_windows.clear()
        _semaphore = None
        _semaphore_limit = None
