"""
Application Protocol Specification and Message Framing for Online Examination Network.

This module provides:
1. Reliable framing over TCP stream sockets (Length-Prefixed Framing with Newline fallback).
2. Standardized JSON message envelope (type, timestamp, msg_id, payload).
3. Protocol constants, message validators, and typed builder functions.
"""

import json
import struct
import time
import uuid
import socket
from typing import Dict, Any, Optional, Tuple

HEADER_FORMAT = "!I"
HEADER_SIZE = struct.calcsize(HEADER_FORMAT)
MAX_MESSAGE_SIZE = 10 * 1024 * 1024  # 10 MB sanity limit

# Supported Message Types
TYPE_AUTH_REQUEST = "AUTH_REQUEST"
TYPE_AUTH_RESPONSE = "AUTH_RESPONSE"
TYPE_QUESTION_REQUEST = "QUESTION_REQUEST"
TYPE_QUESTION_DELIVERY = "QUESTION_DELIVERY"
TYPE_SUBMIT_ANSWER = "SUBMIT_ANSWER"
TYPE_ANSWER_ACK = "ANSWER_ACK"
TYPE_EXAM_SUBMIT = "EXAM_SUBMIT"
TYPE_RESULT_RESPONSE = "RESULT_RESPONSE"
TYPE_PING = "PING"
TYPE_PONG = "PONG"
TYPE_ERROR = "ERROR"

ALL_TYPES = {
    TYPE_AUTH_REQUEST,
    TYPE_AUTH_RESPONSE,
    TYPE_QUESTION_REQUEST,
    TYPE_QUESTION_DELIVERY,
    TYPE_SUBMIT_ANSWER,
    TYPE_ANSWER_ACK,
    TYPE_EXAM_SUBMIT,
    TYPE_RESULT_RESPONSE,
    TYPE_PING,
    TYPE_PONG,
    TYPE_ERROR,
}


class ProtocolError(Exception):
    """Raised when a protocol framing or message validation error occurs."""
    pass


def create_message(msg_type: str, payload: Dict[str, Any], msg_id: Optional[str] = None) -> Dict[str, Any]:
    """Create a standardized message envelope."""
    if msg_type not in ALL_TYPES:
        raise ProtocolError(f"Unsupported message type: {msg_type}")
    return {
        "type": msg_type,
        "msg_id": msg_id or str(uuid.uuid4())[:8],
        "timestamp": time.time(),
        "payload": payload
    }


def send_framed_message(sock: socket.socket, message: Dict[str, Any]) -> None:
    """
    Send a length-prefixed JSON message over a TCP socket.
    Framing: [4 bytes Big-Endian Message Length][UTF-8 JSON Payload]
    """
    try:
        raw_json = json.dumps(message, ensure_ascii=False).encode("utf-8")
        header = struct.pack(HEADER_FORMAT, len(raw_json))
        sock.sendall(header + raw_json)
    except (OSError, TypeError, ValueError) as err:
        raise ProtocolError(f"Failed to encode and send message: {err}") from err


def recv_exact(sock: socket.socket, num_bytes: int) -> bytes:
    """Read exactly num_bytes from a socket, or raise ConnectionError if EOF."""
    data = bytearray()
    while len(data) < num_bytes:
        try:
            chunk = sock.recv(num_bytes - len(data))
        except (socket.timeout, TimeoutError):
            raise
        except (OSError, ConnectionResetError) as err:
            raise ConnectionError(f"Socket error while reading {num_bytes} bytes: {err}") from err

        if not chunk:
            raise ConnectionError("Connection closed by peer while awaiting data.")
        data.extend(chunk)
    return bytes(data)


def recv_framed_message(sock: socket.socket) -> Dict[str, Any]:
    """
    Receive a length-prefixed JSON message from a TCP socket.
    """
    raw_header = recv_exact(sock, HEADER_SIZE)
    (msg_length,) = struct.unpack(HEADER_FORMAT, raw_header)

    if msg_length > MAX_MESSAGE_SIZE:
        raise ProtocolError(f"Message length {msg_length} exceeds limit {MAX_MESSAGE_SIZE}")
    if msg_length == 0:
        raise ProtocolError("Received zero-length message payload.")

    raw_payload = recv_exact(sock, msg_length)
    try:
        data = json.loads(raw_payload.decode("utf-8"))
        if not isinstance(data, dict) or "type" not in data:
            raise ProtocolError("Invalid message structure: missing 'type' key.")
        return data
    except (json.JSONDecodeError, UnicodeDecodeError) as err:
        raise ProtocolError(f"Failed to decode JSON message payload: {err}") from err


# --- Message Validation Helpers ---

def validate_auth_request(msg: Dict[str, Any]) -> Tuple[str, str]:
    """Validate AUTH_REQUEST message. Returns (student_id, student_name)."""
    payload = msg.get("payload", {})
    student_id = str(payload.get("student_id", "")).strip()
    name = str(payload.get("name", "")).strip() or student_id
    if not student_id:
        raise ProtocolError("AUTH_REQUEST missing valid 'student_id'.")
    return student_id, name


def validate_answer_submission(msg: Dict[str, Any]) -> Tuple[str, int, int]:
    """Validate SUBMIT_ANSWER message. Returns (student_id, question_id, selected_option)."""
    payload = msg.get("payload", {})
    student_id = str(payload.get("student_id", "")).strip()
    try:
        question_id = int(payload.get("question_id"))
        selected_option = int(payload.get("selected_option"))
    except (TypeError, ValueError) as err:
        raise ProtocolError(f"Invalid question_id or selected_option: {err}") from err

    if not student_id:
        raise ProtocolError("SUBMIT_ANSWER missing valid 'student_id'.")
    return student_id, question_id, selected_option
