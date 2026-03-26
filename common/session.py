"""
SessionManager: Thread-safe HTTP session management with TTL support.

Manages user requests.Session objects with automatic cleanup for inactive sessions.
Prevents unbounded memory growth and provides lifecycle management.
"""

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

    # Class constants (configurable)
    DEFAULT_TTL_SECONDS = 24 * 3600  # 24 hours
    MAX_SESSIONS = 5000  # Max allowed concurrent sessions

    def __init__(self, ttl_seconds: int = DEFAULT_TTL_SECONDS, max_sessions: int = MAX_SESSIONS):
        """
        Initialize SessionManager.

        Args:
            ttl_seconds: Time-to-live for inactive sessions (seconds)
            max_sessions: Maximum number of concurrent sessions allowed
        """
        self._sessions: dict[
            int, dict
        ] = {}  # {chat_id: {"session": Session, "last_access": timestamp}}
        self._lock = threading.Lock()
        self._ttl_seconds = ttl_seconds
        self._max_sessions = max_sessions
        self._stats = {"created": 0, "cleaned": 0}
        logger.info(f"SessionManager initialized: TTL={ttl_seconds}s, MAX={max_sessions}")

    def get_session(self, chat_id: int, headers: dict | None = None) -> requests.Session:
        """
        Get or create session for a user.

        Args:
            chat_id: User's chat ID
            headers: Optional headers to set on new session

        Returns:
            requests.Session object

        Raises:
            ValueError: If max sessions limit exceeded
        """
        with self._lock:
            current_time = time.time()

            # Check if session already exists
            if chat_id in self._sessions:
                self._sessions[chat_id]["last_access"] = current_time
                return self._sessions[chat_id]["session"]

            # Check limit before creating new session
            if len(self._sessions) >= self._max_sessions:
                logger.warning(f"Session limit reached: {len(self._sessions)}/{self._max_sessions}")
                raise ValueError(f"Maximum {self._max_sessions} sessions reached")

            # Create new session
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
        """
        Close and remove session for a user.

        Args:
            chat_id: User's chat ID

        Returns:
            True if session was closed, False if not found
        """
        with self._lock:
            if chat_id not in self._sessions:
                logger.debug(f"Session not found for user {chat_id}")
                return False

            try:
                self._sessions[chat_id]["session"].close()
            except Exception as e:
                logger.error(f"Error closing session for user {chat_id}: {e}")

            del self._sessions[chat_id]
            logger.info(f"Closed session for user {chat_id} (remaining: {len(self._sessions)})")
            return True

    def cleanup_inactive_sessions(self, force: bool = False) -> int:
        """
        Close sessions that haven't been accessed within TTL period.

        Args:
            force: If True, close all sessions regardless of TTL

        Returns:
            Number of sessions cleaned up
        """
        with self._lock:
            current_time = time.time()
            cutoff_time = current_time - self._ttl_seconds
            cleaned_count = 0

            # Create list of keys to avoid dict size change during iteration
            chat_ids_to_check = list(self._sessions.keys())

            for chat_id in chat_ids_to_check:
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
        """
        Close all sessions (typically on shutdown).

        Returns:
            Number of sessions closed
        """
        return self.cleanup_inactive_sessions(force=True)

    def stats(self) -> dict:
        """
        Get session manager statistics.

        Returns:
            Dictionary with stats: created, cleaned, current_count
        """
        with self._lock:
            return {
                "created": self._stats["created"],
                "cleaned": self._stats["cleaned"],
                "current_count": len(self._sessions),
                "max_allowed": self._max_sessions,
                "ttl_seconds": self._ttl_seconds,
            }

    def session_count(self) -> int:
        """
        Get current number of active sessions.

        Returns:
            Number of sessions
        """
        with self._lock:
            return len(self._sessions)

    def has_session(self, chat_id: int) -> bool:
        """
        Check if a user has an active session.

        Args:
            chat_id: User's chat ID

        Returns:
            True if user has an active session, False otherwise
        """
        with self._lock:
            return chat_id in self._sessions

    def get_active_sessions(self) -> list[int]:
        """
        Get list of all active session user IDs.

        Returns:
            List of chat IDs with active sessions
        """
        with self._lock:
            return list(self._sessions.keys())


# Global singleton instance
_session_manager: SessionManager | None = None


def get_session_manager(ttl_seconds: int = SessionManager.DEFAULT_TTL_SECONDS) -> SessionManager:
    """
    Get or create global SessionManager instance.

    Args:
        ttl_seconds: TTL for sessions (only used if creating new instance)

    Returns:
        Global SessionManager instance
    """
    global _session_manager
    if _session_manager is None:
        _session_manager = SessionManager(ttl_seconds=ttl_seconds)
    return _session_manager
