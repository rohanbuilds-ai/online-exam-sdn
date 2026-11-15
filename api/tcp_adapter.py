"""
Per-student TCP bridge between FastAPI and the exam TCP server.

Each TcpExamAdapter holds one open TCP socket for the lifetime of a student
session.  All socket I/O is protected by a threading.Lock so that FastAPI's
default thread-pool can safely call the adapter from any worker thread.
"""

import logging
import select
import socket
import threading
import time
from typing import Any, Dict, Optional

from app.protocol import (
    TYPE_AUTH_REQUEST,
    TYPE_AUTH_RESPONSE,
    TYPE_QUESTION_REQUEST,
    TYPE_QUESTION_DELIVERY,
    TYPE_SUBMIT_ANSWER,
    TYPE_ANSWER_ACK,
    TYPE_EXAM_SUBMIT,
    TYPE_RESULT_RESPONSE,
    TYPE_ERROR,
    ProtocolError,
    create_message,
    send_framed_message,
    recv_framed_message,
)
from api.config import EXAM_SERVER_HOST, EXAM_SERVER_PORT

logger = logging.getLogger("api.tcp_adapter")

_DEFAULT_TIMEOUT: float = 30.0


def _strip_envelope(msg: Dict[str, Any]) -> Dict[str, Any]:
    """Return only the payload dict, dropping msg_id/timestamp wrappers."""
    return msg.get("payload", {})


class TcpAdapterError(Exception):
    """Raised for expected protocol-level errors (wrong message type, etc.)."""


class TcpExamAdapter:
    """
    Maintains a single open TCP connection to the exam server for one student.

    Thread-safety: a threading.Lock guards every socket operation so that
    FastAPI's default thread-pool can share the adapter safely.
    """

    def __init__(
        self,
        host: str = EXAM_SERVER_HOST,
        port: int = EXAM_SERVER_PORT,
        timeout: float = _DEFAULT_TIMEOUT,
    ) -> None:
        self.host = host
        self.port = port
        self.timeout = timeout
        self._sock: Optional[socket.socket] = None
        self._lock = threading.Lock()
        # Cached from the last ANSWER_ACK so /ping can answer without a round-trip
        self.last_remaining_seconds: Optional[float] = None
        self.cached_result: Optional[Dict[str, Any]] = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def connect(self, student_id: str, student_name: str) -> Dict[str, Any]:
        """
        Open the TCP connection to the exam server and authenticate.

        Returns the AUTH_RESPONSE payload dict on success.
        Raises ConnectionRefusedError / OSError if the server is unreachable.
        Raises TcpAdapterError if authentication fails.
        """
        with self._lock:
            if self._sock is not None:
                raise TcpAdapterError("Adapter already connected.")

            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(self.timeout)
            try:
                sock.connect((self.host, self.port))
            except (ConnectionRefusedError, OSError) as exc:
                sock.close()
                logger.error(
                    "TCP connect failed for student %s → %s:%d  error=%s",
                    student_id, self.host, self.port, exc,
                )
                raise

            logger.info(
                "TCP connected for student_id=%s name=%r → %s:%d",
                student_id, student_name, self.host, self.port,
            )

            # Send AUTH_REQUEST
            auth_msg = create_message(
                TYPE_AUTH_REQUEST,
                {"student_id": student_id, "name": student_name},
            )
            send_framed_message(sock, auth_msg)
            response = recv_framed_message(sock)

            if response.get("type") == TYPE_ERROR:
                sock.close()
                raise TcpAdapterError(
                    f"Auth rejected by server: {response.get('payload')}"
                )
            if response.get("type") != TYPE_AUTH_RESPONSE:
                sock.close()
                raise TcpAdapterError(
                    f"Unexpected response type after AUTH_REQUEST: {response.get('type')}"
                )

            self._sock = sock
            payload = _strip_envelope(response)
            logger.info(
                "AUTH_RESPONSE received for student_id=%s  total_questions=%s",
                student_id, payload.get("total_questions"),
            )
            return payload

    def get_question(self) -> Dict[str, Any]:
        """
        Request the next question from the server.

        Returns the QUESTION_DELIVERY payload dict.
        Raises TcpAdapterError with a 'exam_ended' hint when the server
        sends a RESULT_RESPONSE instead (exam finished server-side).
        """
        with self._lock:
            self._assert_connected()
            send_framed_message(self._sock, create_message(TYPE_QUESTION_REQUEST, {}))
            response = recv_framed_message(self._sock)

        rtype = response.get("type")
        if rtype == TYPE_RESULT_RESPONSE:
            raise TcpAdapterError("exam_ended")
        if rtype != TYPE_QUESTION_DELIVERY:
            raise TcpAdapterError(f"Expected QUESTION_DELIVERY, got {rtype}")

        return _strip_envelope(response)

    def submit_answer(
        self, question_id: int, selected_option: int, student_id: str
    ) -> Dict[str, Any]:
        """
        Submit an answer and return the ANSWER_ACK payload dict.
        Also caches remaining_seconds for use by /ping.
        """
        with self._lock:
            self._assert_connected()
            msg = create_message(
                TYPE_SUBMIT_ANSWER,
                {
                    "student_id": student_id,
                    "question_id": question_id,
                    "selected_option": selected_option,
                },
            )
            send_framed_message(self._sock, msg)
            response = recv_framed_message(self._sock)

        rtype = response.get("type")
        if rtype != TYPE_ANSWER_ACK:
            raise TcpAdapterError(f"Expected ANSWER_ACK, got {rtype}")

        payload = _strip_envelope(response)
        # Cache remaining time for the ping endpoint
        self.last_remaining_seconds = payload.get("remaining_seconds")

        # If server automatically sent RESULT_RESPONSE (e.g. final question answered), cache it
        with self._lock:
            try:
                rlist, _, _ = select.select([self._sock], [], [], 0.05)
                if rlist:
                    trailing = recv_framed_message(self._sock)
                    if trailing.get("type") == TYPE_RESULT_RESPONSE:
                        self.cached_result = _strip_envelope(trailing)
            except Exception:
                pass

        return payload

    def finish_exam(self) -> Dict[str, Any]:
        """
        Send EXAM_SUBMIT and read the RESULT_RESPONSE (or read buffered RESULT_RESPONSE).
        Returns the result payload dict.
        """
        if self.cached_result is not None:
            return self.cached_result

        with self._lock:
            self._assert_connected()
            try:
                send_framed_message(
                    self._sock, create_message(TYPE_EXAM_SUBMIT, {})
                )
            except Exception:
                # Server may have already finalized on last question and shut down write
                pass

            response = recv_framed_message(self._sock)

        rtype = response.get("type")
        if rtype != TYPE_RESULT_RESPONSE:
            raise TcpAdapterError(f"Expected RESULT_RESPONSE, got {rtype}")

        payload = _strip_envelope(response)
        self.cached_result = payload
        logger.info("RESULT_RESPONSE received; exam finished.")
        return payload

    def close(self) -> None:
        """Close the TCP socket. Safe to call multiple times."""
        with self._lock:
            if self._sock is not None:
                try:
                    self._sock.close()
                except Exception:
                    pass
                self._sock = None
                logger.info("TCP connection closed.")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _assert_connected(self) -> None:
        """Raise TcpAdapterError if the socket is not open (must be called under lock)."""
        if self._sock is None:
            raise TcpAdapterError("TCP connection is not open.")
