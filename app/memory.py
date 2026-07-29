"""In-process conversation memory, keyed by session id.

An in-memory store is enough for this project's scope and keeps it
dependency-free (no Redis/DB needed to run locally). `MemoryStore` is a
small enough interface that swapping in a persistent backend later - the
obvious next step for running behind more than one worker process - only
means writing a new implementation of `get_history` / `add_message` /
`clear`, not touching any caller.
"""

from __future__ import annotations

import threading
from collections import OrderedDict

from app.config import settings
from app.models import ChatMessage, Role
from app.utils import get_logger

logger = get_logger(__name__)


class MemoryStore:
    """Thread-safe, per-session sliding-window conversation memory."""

    def __init__(self, max_turns: int | None = None):
        self._max_turns = max_turns or settings.max_memory_turns
        self._sessions: OrderedDict[str, list[ChatMessage]] = OrderedDict()
        self._lock = threading.Lock()

    def get_history(self, session_id: str) -> list[ChatMessage]:
        """Return a copy of the stored turns for a session (empty if unknown)."""
        with self._lock:
            return list(self._sessions.get(session_id, []))

    def add_message(self, session_id: str, role: Role, content: str) -> None:
        """Append a turn, trimming the oldest turns beyond the configured window."""
        with self._lock:
            history = self._sessions.setdefault(session_id, [])
            history.append(ChatMessage(role=role, content=content))

            max_messages = self._max_turns * 2  # user + assistant per turn
            if len(history) > max_messages:
                del history[: len(history) - max_messages]

    def clear(self, session_id: str) -> bool:
        """Drop a session's history. Returns True if the session existed."""
        with self._lock:
            existed = session_id in self._sessions
            self._sessions.pop(session_id, None)
            return existed

    def session_exists(self, session_id: str) -> bool:
        with self._lock:
            return session_id in self._sessions


_memory_store: MemoryStore | None = None


def get_memory_store() -> MemoryStore:
    """Process-wide singleton so every request shares the same session table."""
    global _memory_store
    if _memory_store is None:
        _memory_store = MemoryStore()
    return _memory_store
