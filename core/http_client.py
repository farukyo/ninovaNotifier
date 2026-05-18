"""Thread-safe HTTP session pool using requests.

migrated from: common/session.py
Note: uses requests (synchronous), NOT aiohttp — the bot is thread-based.
"""

# migrated from: common/session.py
from __future__ import annotations

import logging
import threading
import time

import requests

logger = logging.getLogger("ninova")


class SessionManager:
    """
    Thread-safe manager for HTTP sessions with TTL-based cleanup.

    Features:
    - Automatic session creation per user (chat_id)
    - TTL-based cleanup for inactive sessions (default: 24 hours)
    - Thread-safe access with locking
    - Statistics tracking for monitoring
    """

    DEFAULT_TTL_SECONDS = 24 * 3600
    MAX_SESSIONS = 5000

    def __init__(self, ttl_seconds: int = DEFAULT_TTL_SECONDS, max_sessions: int = MAX_SESSIONS):
        self._sessions: dict[int, dict] = {}
        self._lock = threading.Lock()
        self._ttl_seconds = ttl_seconds
        self._max_sessions = max_sessions
        self._stats = {"created": 0, "cleaned": 0}
        logger.info(f"SessionManager initialized: TTL={ttl_seconds}s, MAX={max_sessions}")

    def get_session(self, chat_id: int, headers: dict | None = None) -> requests.Session:
        with self._lock:
            current_time = time.time()

            if chat_id in self._sessions:
                self._sessions[chat_id]["last_access"] = current_time
                return self._sessions[chat_id]["session"]

            if len(self._sessions) >= self._max_sessions:
                logger.warning(f"Session limit reached: {len(self._sessions)}/{self._max_sessions}")
                raise ValueError(f"Maximum {self._max_sessions} sessions reached")

            session = requests.Session()
            if headers:
                session.headers.update(headers)

            self._sessions[chat_id] = {
                "session": session,
                "last_access": current_time,
                "created_at": current_time,
            }
            self._stats["created"] += 1
            logger.debug(f"Created session for user {chat_id} (total: {len(self._sessions)})")
            return session

    def close_session(self, chat_id: int) -> bool:
        with self._lock:
            if chat_id not in self._sessions:
                return False
            try:
                self._sessions[chat_id]["session"].close()
            except Exception as e:
                logger.error(f"Error closing session for user {chat_id}: {e}")
            del self._sessions[chat_id]
            logger.info(f"Closed session for user {chat_id} (remaining: {len(self._sessions)})")
            return True

    def cleanup_inactive_sessions(self, force: bool = False) -> int:
        with self._lock:
            current_time = time.time()
            cutoff_time = current_time - self._ttl_seconds
            cleaned_count = 0

            for chat_id in list(self._sessions.keys()):
                last_access = self._sessions[chat_id]["last_access"]
                if force or last_access < cutoff_time:
                    try:
                        self._sessions[chat_id]["session"].close()
                    except Exception as e:
                        logger.error(f"Error closing session for user {chat_id}: {e}")
                    del self._sessions[chat_id]
                    cleaned_count += 1

            if cleaned_count > 0:
                self._stats["cleaned"] += cleaned_count
                logger.info(
                    f"Cleaned {cleaned_count} inactive sessions (remaining: {len(self._sessions)})"
                )
            return cleaned_count

    def close_all_sessions(self) -> int:
        return self.cleanup_inactive_sessions(force=True)

    def stats(self) -> dict:
        with self._lock:
            return {
                "created": self._stats["created"],
                "cleaned": self._stats["cleaned"],
                "current_count": len(self._sessions),
                "max_allowed": self._max_sessions,
                "ttl_seconds": self._ttl_seconds,
            }

    def session_count(self) -> int:
        with self._lock:
            return len(self._sessions)

    def has_session(self, chat_id: int) -> bool:
        with self._lock:
            return chat_id in self._sessions

    def get_active_sessions(self) -> list[int]:
        with self._lock:
            return list(self._sessions.keys())


_session_manager: SessionManager | None = None


def get_session_manager(ttl_seconds: int = SessionManager.DEFAULT_TTL_SECONDS) -> SessionManager:
    global _session_manager
    if _session_manager is None:
        _session_manager = SessionManager(ttl_seconds=ttl_seconds)
    return _session_manager
