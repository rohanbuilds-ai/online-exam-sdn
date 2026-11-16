"""
Server-side administrator authentication and signed session management.
Uses HMAC-SHA256 signed session tokens inside HTTP-only cookies.
Zero external dependencies required.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import secrets
import time
from typing import Any, Dict, Optional

import api.config as config

logger = logging.getLogger("api.auth")

COOKIE_NAME: str = "admin_session"


def _b64encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _b64decode(s: str) -> bytes:
    padding = "=" * ((4 - len(s) % 4) % 4)
    return base64.urlsafe_b64decode(s + padding)


def create_session_token(role: str = "admin") -> str:
    """
    Generate an HMAC-SHA256 signed session token containing role and expiration.
    """
    secret = config.SESSION_SECRET.encode("utf-8")
    payload = {
        "role": role,
        "exp": int(time.time()) + config.SESSION_MAX_AGE_SEC,
        "nonce": secrets.token_hex(8),
    }
    payload_bytes = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    payload_b64 = _b64encode(payload_bytes)

    sig = hmac.new(secret, payload_b64.encode("ascii"), hashlib.sha256).digest()
    sig_b64 = _b64encode(sig)

    return f"{payload_b64}.{sig_b64}"


def verify_session_token(token: str) -> Optional[Dict[str, Any]]:
    """
    Verify the signature and expiration of a session token.
    Returns the payload dictionary if valid, or None if invalid/expired.
    """
    if not token or "." not in token:
        return None

    parts = token.split(".", 1)
    if len(parts) != 2:
        return None

    payload_b64, sig_b64 = parts
    secret = config.SESSION_SECRET.encode("utf-8")

    try:
        expected_sig = hmac.new(secret, payload_b64.encode("ascii"), hashlib.sha256).digest()
        provided_sig = _b64decode(sig_b64)

        if not secrets.compare_digest(expected_sig, provided_sig):
            return None

        payload_bytes = _b64decode(payload_b64)
        payload = json.loads(payload_bytes.decode("utf-8"))

        # Verify expiration
        exp = payload.get("exp", 0)
        if time.time() > exp:
            return None

        return payload
    except Exception as exc:
        logger.debug("Token verification failed: %s", exc)
        return None
