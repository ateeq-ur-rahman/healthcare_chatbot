"""Unit tests for app.utils."""

import pytest

from app.utils import stopwatch, truncate, with_retries


def test_stopwatch_reports_nonnegative_elapsed_time():
    with stopwatch() as elapsed_ms:
        total = sum(range(1000))
    assert total == 499500
    assert elapsed_ms() >= 0


def test_truncate_short_text_unchanged():
    assert truncate("hello") == "hello"


def test_truncate_long_text_is_cut_with_ellipsis():
    text = "x" * 500
    result = truncate(text, max_len=50)
    assert len(result) == 50
    assert result.endswith("...")


def test_with_retries_succeeds_on_first_try():
    calls = []

    @with_retries(max_attempts=3, base_delay_seconds=0)
    def always_ok():
        calls.append(1)
        return "ok"

    assert always_ok() == "ok"
    assert len(calls) == 1


def test_with_retries_retries_then_succeeds():
    calls = []

    @with_retries(max_attempts=3, base_delay_seconds=0)
    def fails_twice_then_ok():
        calls.append(1)
        if len(calls) < 3:
            raise ValueError("transient")
        return "ok"

    assert fails_twice_then_ok() == "ok"
    assert len(calls) == 3


def test_with_retries_raises_after_exhausting_attempts():
    calls = []

    @with_retries(max_attempts=2, base_delay_seconds=0)
    def always_fails():
        calls.append(1)
        raise ValueError("persistent failure")

    with pytest.raises(ValueError, match="persistent failure"):
        always_fails()
    assert len(calls) == 2
