"""
Environment-variable based configuration for the SDN Exam Gateway API.
All values can be overridden via environment variables or a .env file.
"""

import os


def _bool(val: str, default: bool = False) -> bool:
    if not val:
        return default
    return val.strip().lower() in ("1", "true", "yes", "on")


def _list(val: str, default: list) -> list:
    if not val:
        return default
    return [v.strip() for v in val.split(",") if v.strip()]


# ---------------------------------------------------------------------------
# TCP Examination Server
# ---------------------------------------------------------------------------
EXAM_SERVER_HOST: str = os.environ.get("EXAM_SERVER_HOST", "127.0.0.1")
EXAM_SERVER_PORT: int = int(os.environ.get("EXAM_SERVER_PORT", "5000"))

# ---------------------------------------------------------------------------
# FastAPI Gateway
# ---------------------------------------------------------------------------
GATEWAY_HOST: str = os.environ.get("GATEWAY_HOST", "0.0.0.0")
GATEWAY_PORT: int = int(os.environ.get("GATEWAY_PORT", "8000"))

# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------
DB_PATH: str = os.environ.get("DB_PATH", "exam_records.db")

# ---------------------------------------------------------------------------
# SDN Controller integration (live controller present in environment)
# ---------------------------------------------------------------------------
SDN_ENABLED: bool = _bool(os.environ.get("SDN_ENABLED", ""), default=False)

# ---------------------------------------------------------------------------
# Optionally boot the exam TCP server inside this process
# ---------------------------------------------------------------------------
START_EXAM_SERVER: bool = _bool(os.environ.get("START_EXAM_SERVER", ""), default=False)

# ---------------------------------------------------------------------------
# CORS
# ---------------------------------------------------------------------------
CORS_ORIGINS: list = _list(
    os.environ.get("CORS_ORIGINS", ""),
    default=["http://localhost:5173", "http://localhost:3000"],
)
