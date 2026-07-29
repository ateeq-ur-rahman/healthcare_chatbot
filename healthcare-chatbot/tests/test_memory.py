"""Unit tests for app.memory."""

from app.memory import MemoryStore
from app.models import Role


def test_add_and_get_history():
    store = MemoryStore(max_turns=10)
    store.add_message("s1", Role.USER, "I have a fever")
    store.add_message("s1", Role.ASSISTANT, "Sorry to hear that...")
    history = store.get_history("s1")
    assert len(history) == 2
    assert history[0].role == Role.USER
    assert history[0].content == "I have a fever"


def test_sessions_are_isolated():
    store = MemoryStore(max_turns=10)
    store.add_message("s1", Role.USER, "hello from s1")
    store.add_message("s2", Role.USER, "hello from s2")
    assert len(store.get_history("s1")) == 1
    assert len(store.get_history("s2")) == 1
    assert store.get_history("s1")[0].content != store.get_history("s2")[0].content


def test_sliding_window_trims_old_messages():
    store = MemoryStore(max_turns=2)  # keeps at most 4 messages (2 user + 2 assistant)
    for i in range(5):
        store.add_message("s1", Role.USER, f"msg-{i}")
        store.add_message("s1", Role.ASSISTANT, f"reply-{i}")
    history = store.get_history("s1")
    assert len(history) == 4
    assert history[0].content == "msg-3"  # oldest two turns dropped


def test_clear_removes_session():
    store = MemoryStore()
    store.add_message("s1", Role.USER, "hi")
    assert store.session_exists("s1") is True
    cleared = store.clear("s1")
    assert cleared is True
    assert store.session_exists("s1") is False


def test_clear_nonexistent_session_returns_false():
    store = MemoryStore()
    assert store.clear("does-not-exist") is False
