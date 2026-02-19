from __future__ import annotations

import os
import random
import time
from typing import Callable, TypeVar

import httpx
import psycopg2

T = TypeVar("T")


class DependencyError(RuntimeError):
    def __init__(self, message: str, *, retryable: bool):
        super().__init__(message)
        self.retryable = retryable


class RetryableDependencyError(DependencyError):
    def __init__(self, message: str):
        super().__init__(message, retryable=True)


class PermanentDependencyError(DependencyError):
    def __init__(self, message: str):
        super().__init__(message, retryable=False)


def _float_env(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        value = float(raw)
    except ValueError:
        return default
    return value if value > 0 else default


def _int_env(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    return value if value > 0 else default


def dependency_retry_attempts() -> int:
    return _int_env("DEPENDENCY_RETRY_ATTEMPTS", 2)


def dependency_retry_base_seconds() -> float:
    return _float_env("DEPENDENCY_RETRY_BASE_SECONDS", 0.2)


def dependency_retry_max_seconds() -> float:
    return _float_env("DEPENDENCY_RETRY_MAX_SECONDS", 2.0)


def dependency_timeout_seconds() -> float:
    return _float_env("DEPENDENCY_TIMEOUT_SECONDS", 30.0)


def is_retryable_exception(exc: Exception) -> bool:
    if isinstance(exc, httpx.HTTPStatusError) and exc.response is not None:
        return exc.response.status_code >= 500

    retryable_types = (
        TimeoutError,
        ConnectionError,
        httpx.TimeoutException,
        httpx.NetworkError,
        psycopg2.OperationalError,
        psycopg2.InterfaceError,
    )
    return isinstance(exc, retryable_types)


def retry_with_backoff(
    func: Callable[[], T],
    *,
    operation: str,
    attempts: int | None = None,
    base_delay_seconds: float | None = None,
    max_delay_seconds: float | None = None,
    retry_if: Callable[[Exception], bool] = is_retryable_exception,
) -> T:
    max_attempts = attempts or dependency_retry_attempts()
    base_delay = base_delay_seconds or dependency_retry_base_seconds()
    max_delay = max_delay_seconds or dependency_retry_max_seconds()

    last_exc: Exception | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            return func()
        except Exception as exc:
            if not retry_if(exc):
                raise
            last_exc = exc
            if attempt >= max_attempts:
                break

            delay = min(max_delay, base_delay * (2 ** (attempt - 1)))
            jitter = random.uniform(0, delay * 0.2)
            time.sleep(delay + jitter)

    raise RetryableDependencyError(
        f"{operation} failed after {max_attempts} attempts: {last_exc!r}"
    )


def enforce_timeout_budget(
    *,
    started_at: float,
    timeout_seconds: float,
    operation: str,
) -> None:
    elapsed = time.monotonic() - started_at
    if elapsed > timeout_seconds:
        raise TimeoutError(
            f"{operation} exceeded timeout budget ({elapsed:.2f}s > {timeout_seconds:.2f}s)"
        )
