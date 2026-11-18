"""
In-memory session store that maps a gateway_session_id (UUID4 string)
to a TcpExamAdapter (the live TCP connection for that student).

Thread-safety: all mutations are protected by an RLock.
Auto-cleanup removes sessions older than SESSION_MAX_AGE_SEC.
"""

import logging
import threading
import time
import uuid
from typing import Dict, List, Optional, Any

from api.tcp_adapter import TcpExamAdapter

logger = logging.getLogger("api.session_store")

SESSION_MAX_AGE_SEC: float = 2 * 60 * 60  # 2 hours


class _SessionEntry:
    __slots__ = ("gateway_session_id", "student_id", "student_name", "started_at", "adapter")

    def __init__(
        self,
        gateway_session_id: str,
        student_id: str,
        student_name: str,
        adapter: TcpExamAdapter,
    ) -> None:
        self.gateway_session_id = gateway_session_id
        self.student_id = student_id
        self.student_name = student_name
        self.started_at: float = time.time()
        self.adapter = adapter


class SessionStore:
    """
    Thread-safe in-memory session registry.

    Mapping: gateway_session_id (str) → _SessionEntry
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._sessions: Dict[str, _SessionEntry] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def create(
        self,
        student_id: str,
        student_name: str,
        adapter: TcpExamAdapter,
    ) -> str:
        """
        Register a new session.  Returns the new gateway_session_id (UUID4).
        """
        self._cleanup_stale()
        gid = str(uuid.uuid4())
        entry = _SessionEntry(gid, student_id, student_name, adapter)
        with self._lock:
            self._sessions[gid] = entry
        logger.info(
            "Session created: gateway_session_id=%s student_id=%s", gid, student_id
        )
        return gid

    def get(self, gateway_session_id: str) -> Optional[TcpExamAdapter]:
        """Return the TcpExamAdapter for the given session, or None."""
        with self._lock:
            entry = self._sessions.get(gateway_session_id)
            return entry.adapter if entry else None

    def get_entry(self, gateway_session_id: str) -> Optional[_SessionEntry]:
        """Return the full _SessionEntry, or None."""
        with self._lock:
            return self._sessions.get(gateway_session_id)

    def remove(self, gateway_session_id: str) -> None:
        """Remove a session from the store (does NOT close the adapter)."""
        with self._lock:
            removed = self._sessions.pop(gateway_session_id, None)
        if removed:
            logger.info(
                "Session removed: gateway_session_id=%s student_id=%s",
                gateway_session_id, removed.student_id,
            )

    def list_active(self) -> List[Dict[str, Any]]:
        """
        Return metadata for every active session.
        Each dict has: id, gateway_session_id, student_id, student_name, started_at.
        """
        self._cleanup_stale()
        with self._lock:
            return [
                {
                    "id": e.gateway_session_id,
                    "gateway_session_id": e.gateway_session_id,
                    "student_id": e.student_id,
                    "student_name": e.student_name,
                    "started_at": e.started_at,
                }
                for e in self._sessions.values()
            ]

    def count(self) -> int:
        """Return the number of active sessions."""
        with self._lock:
            return len(self._sessions)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _cleanup_stale(self) -> None:
        """Remove sessions older than SESSION_MAX_AGE_SEC."""
        cutoff = time.time() - SESSION_MAX_AGE_SEC
        stale_ids = []
        with self._lock:
            for gid, entry in list(self._sessions.items()):
                if entry.started_at < cutoff:
                    stale_ids.append(gid)
            for gid in stale_ids:
                entry = self._sessions.pop(gid)
                logger.info(
                    "Auto-evicted stale session: gateway_session_id=%s student_id=%s",
                    gid, entry.student_id,
                )
                # Best-effort close the orphaned TCP connection
                try:
                    entry.adapter.close()
                except Exception:
                    pass


# ---------------------------------------------------------------------------
# Module-level singleton shared by main.py
# ---------------------------------------------------------------------------
session_store = SessionStore()
