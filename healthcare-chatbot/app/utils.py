"""Small, dependency-light helpers shared across the app.

Structured JSON logging, a stopwatch context manager, and a retry
decorator for outbound LLM calls. Kept deliberately free of app-specific
imports (besides config) so these can be reused anywhere without pulling
in the rest of the package.
"""

from __future__ import annotations

import functools
import json
import logging
import sys
import time
from contextlib import contextmanager
from typing import Any, Callable, Iterator, TypeVar

from app.config import settings

T = TypeVar("T")

# Standard LogRecord attributes we don't want echoed into the JSON output -
# only fields passed via `extra={...}` should show up as top-level keys.
_STANDARD_LOG_RECORD_FIELDS = frozenset(
    {
        "name", "msg", "args", "levelname", "levelno", "pathname", "filename",
        "module", "exc_info", "exc_text", "stack_info", "lineno", "funcName",
        "created", "msecs", "relativeCreated", "thread", "threadName",
        "processName", "process", "message", "taskName",
    }
)


class JSONFormatter(logging.Formatter):
    """Renders each log record as one JSON line, suitable for log aggregators."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for key, value in record.__dict__.items():
            if key not in _STANDARD_LOG_RECORD_FIELDS:
                payload[key] = value
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def get_logger(name: str) -> logging.Logger:
    """Return a logger configured for structured JSON output.

    Safe to call repeatedly with the same name (e.g. once per module) -
    handlers are only attached once per logger instance.
    """
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(JSONFormatter())
        logger.addHandler(handler)
        logger.setLevel(getattr(logging, settings.log_level.upper(), logging.INFO))
        logger.propagate = False
    return logger


@contextmanager
def stopwatch() -> Iterator[Callable[[], float]]:
    """Context manager yielding a callable that returns elapsed milliseconds.

    Usage::

        with stopwatch() as elapsed_ms:
            do_work()
        logger.info("done", extra={"latency_ms": elapsed_ms()})
    """
    start = time.perf_counter()
    yield lambda: (time.perf_counter() - start) * 1000


def with_retries(
    max_attempts: int = 3,
    base_delay_seconds: float = 0.5,
    retry_on: tuple[type[BaseException], ...] = (Exception,),
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """Exponential-backoff retry decorator.

    Used around outbound LLM API calls so a transient network blip or
    rate-limit response doesn't immediately surface as an error to the
    end user - see `app/llm.py`.
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            logger = get_logger(func.__module__)
            last_error: BaseException | None = None
            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except retry_on as exc:
                    last_error = exc
                    delay = base_delay_seconds * (2 ** (attempt - 1))
                    logger.warning(
                        "retry_attempt_failed",
                        extra={
                            "function": func.__name__,
                            "attempt": attempt,
                            "max_attempts": max_attempts,
                            "delay_seconds": delay,
                            "error": str(exc),
                        },
                    )
                    if attempt < max_attempts:
                        time.sleep(delay)
            # Loop only exits without returning if every attempt raised.
            assert last_error is not None
            raise last_error

        return wrapper

    return decorator


def truncate(text: str, max_len: int = 240) -> str:
    """Shorten text for safe/compact logging, appending '...' if cut."""
    return text if len(text) <= max_len else text[: max_len - 3] + "..."
