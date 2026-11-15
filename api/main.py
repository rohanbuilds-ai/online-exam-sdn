"""
SDN Online Examination API — FastAPI Gateway

Bridges browser HTTP/WebSocket requests to the existing TCP examination server.
All exam logic and scoring remain authoritative on the TCP server side;
this gateway never trusts client-submitted scores or timing values.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import socket
import time
from contextlib import asynccontextmanager
from typing import Any, Dict, Optional

from fastapi import (
    FastAPI,
    Header,
    HTTPException,
    WebSocket,
    WebSocketDisconnect,
    status,
)
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import api.config as config
from api.config import (
    CORS_ORIGINS,
    DB_PATH,
    EXAM_SERVER_HOST,
    EXAM_SERVER_PORT,
    SDN_ENABLED,
    START_EXAM_SERVER,
)
from api.session_store import session_store
from api.sdn_telemetry import get_historical_results, get_live_telemetry, telemetry_store
from api.tcp_adapter import TcpAdapterError, TcpExamAdapter
from app.storage import ExamStorage

logger = logging.getLogger("api.main")
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s",
    datefmt="%H:%M:%S",
)

# ---------------------------------------------------------------------------
# Shared app-lifetime state
# ---------------------------------------------------------------------------
_exam_storage: Optional[ExamStorage] = None
_exam_server = None  # ExamServer instance when START_EXAM_SERVER=true


# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    global _exam_storage, _exam_server

    # Optionally boot the exam TCP server inside this process
    if START_EXAM_SERVER:
        try:
            from app.server import ExamServer  # type: ignore
            _exam_server = ExamServer(port=EXAM_SERVER_PORT)
            _exam_server.start(blocking=False)
            logger.info("ExamServer started in-process on port %d", EXAM_SERVER_PORT)
        except Exception as exc:
            logger.error("Failed to start in-process ExamServer: %s", exc)

    # Shared read-only storage for admin endpoints
    try:
        _exam_storage = ExamStorage(db_path=DB_PATH)
        logger.info("ExamStorage opened: %s", DB_PATH)
    except Exception as exc:
        logger.error("Failed to open ExamStorage: %s", exc)

    yield

    # Teardown
    if _exam_storage:
        try:
            _exam_storage.close()
        except Exception:
            pass
    logger.info("API gateway shutting down.")


# ---------------------------------------------------------------------------
# Application
# ---------------------------------------------------------------------------

app = FastAPI(
    title="SDN Online Examination API",
    description=(
        "FastAPI gateway that bridges browser clients to the stateful TCP "
        "examination server used in the SDN Online Examination Network prototype. "
        "Deploy with: uvicorn api.main:app --host 0.0.0.0 --port 8000"
    ),
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Pydantic request models
# ---------------------------------------------------------------------------

class AuthRequest(BaseModel):
    student_id: str
    student_name: str


class AnswerRequest(BaseModel):
    question_id: int
    selected_option: int


# ---------------------------------------------------------------------------
# Helper: resolve session or raise 404
# ---------------------------------------------------------------------------

def _require_adapter(x_session_id: Optional[str]) -> TcpExamAdapter:
    if not x_session_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "X-Session-ID header is required."},
        )
    adapter = session_store.get(x_session_id)
    if adapter is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "Session not found or expired."},
        )
    return adapter


# ===========================================================================
# Exam endpoints
# ===========================================================================

@app.post("/api/exam/auth", status_code=status.HTTP_200_OK)
def exam_auth(body: AuthRequest) -> Dict[str, Any]:
    """
    Authenticate a student and open a persistent TCP connection to the exam server.

    Returns a gateway_session_id that must be passed as X-Session-ID in every
    subsequent request.
    """
    adapter = TcpExamAdapter(host=config.EXAM_SERVER_HOST, port=config.EXAM_SERVER_PORT)
    try:
        auth_payload = adapter.connect(
            student_id=body.student_id.strip(),
            student_name=body.student_name.strip(),
        )
    except (ConnectionRefusedError, OSError, TimeoutError) as exc:
        logger.error("TCP server unreachable during auth: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"error": "Examination server is unreachable. Please try again later."},
        )
    except TcpAdapterError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": str(exc)},
        )

    gid = session_store.create(
        student_id=body.student_id,
        student_name=body.student_name,
        adapter=adapter,
    )

    return {
        "gateway_session_id": gid,
        "student_id": auth_payload.get("student_id", body.student_id),
        "student_name": auth_payload.get("student_name", body.student_name),
        "exam_duration_sec": auth_payload.get("exam_duration_sec"),
        "total_questions": auth_payload.get("total_questions"),
    }


@app.get("/api/exam/question", status_code=status.HTTP_200_OK)
def exam_question(
    x_session_id: Optional[str] = Header(default=None, alias="X-Session-ID"),
) -> Dict[str, Any]:
    """Retrieve the next question from the TCP server for the current session."""
    adapter = _require_adapter(x_session_id)
    try:
        return adapter.get_question()
    except TcpAdapterError as exc:
        if "exam_ended" in str(exc):
            raise HTTPException(
                status_code=status.HTTP_410_GONE,
                detail={"error": "Exam has ended."},
            )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"error": str(exc)},
        )
    except (ConnectionError, OSError) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"error": f"TCP connection error: {exc}"},
        )


@app.post("/api/exam/answer", status_code=status.HTTP_200_OK)
def exam_answer(
    body: AnswerRequest,
    x_session_id: Optional[str] = Header(default=None, alias="X-Session-ID"),
) -> Dict[str, Any]:
    """
    Submit an answer.  Scores, correctness, and remaining time are ALWAYS
    taken from the server response — never trusted from the client.
    """
    adapter = _require_adapter(x_session_id)
    entry = session_store.get_entry(x_session_id)
    student_id = entry.student_id if entry else ""

    try:
        ack = adapter.submit_answer(
            question_id=body.question_id,
            selected_option=body.selected_option,
            student_id=student_id,
        )
    except TcpAdapterError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"error": str(exc)},
        )
    except (ConnectionError, OSError) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"error": f"TCP connection error: {exc}"},
        )

    # Return only server-authoritative fields
    return {
        "is_correct": ack.get("is_correct"),
        "points_awarded": ack.get("points_awarded"),
        "explanation": ack.get("explanation"),
        "remaining_seconds": ack.get("remaining_seconds"),
    }


@app.post("/api/exam/submit", status_code=status.HTTP_200_OK)
def exam_submit(
    x_session_id: Optional[str] = Header(default=None, alias="X-Session-ID"),
) -> Dict[str, Any]:
    """Submit the exam and receive the final result."""
    adapter = _require_adapter(x_session_id)
    try:
        result = adapter.finish_exam()
    except TcpAdapterError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"error": str(exc)},
        )
    except (ConnectionError, OSError) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"error": f"TCP connection error: {exc}"},
        )
    finally:
        # Always remove and close, even on error
        session_store.remove(x_session_id)
        try:
            adapter.close()
        except Exception:
            pass

    return result


@app.get("/api/exam/ping", status_code=status.HTTP_200_OK)
def exam_ping(
    x_session_id: Optional[str] = Header(default=None, alias="X-Session-ID"),
) -> Dict[str, Any]:
    """
    Return the remaining exam time (seconds) cached from the last ANSWER_ACK.
    Used by the frontend timer to stay in sync without a full round-trip.
    """
    adapter = _require_adapter(x_session_id)
    return {"remaining_seconds": adapter.last_remaining_seconds}


# ===========================================================================
# Admin endpoints
# ===========================================================================

@app.get("/api/admin/results", status_code=status.HTTP_200_OK)
def admin_results() -> Any:
    """Return all completed exam results from the persistent SQLite store."""
    if _exam_storage is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"error": "Storage not available."},
        )
    return _exam_storage.get_all_results()


@app.get("/api/admin/stats", status_code=status.HTTP_200_OK)
def admin_stats() -> Dict[str, Any]:
    """Return summary statistics plus the current active session count."""
    if _exam_storage is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"error": "Storage not available."},
        )
    stats = _exam_storage.get_summary_statistics()
    stats["active_sessions"] = session_store.count()
    return stats


@app.get("/api/admin/sessions", status_code=status.HTTP_200_OK)
def admin_sessions() -> Any:
    """Return metadata for all currently active gateway sessions."""
    return session_store.list_active()


# ===========================================================================
# SDN endpoints
# ===========================================================================

@app.get("/api/sdn/telemetry", status_code=status.HTTP_200_OK)
def sdn_telemetry() -> Dict[str, Any]:
    """Return the latest SDN controller telemetry snapshot."""
    return get_live_telemetry()


@app.get("/api/sdn/history", status_code=status.HTTP_200_OK)
def sdn_history() -> Dict[str, Any]:
    """Return experiment result data from baseline and dynamic SDN result files."""
    return get_historical_results()


@app.get("/api/sdn/events", status_code=status.HTTP_200_OK)
def sdn_events() -> Any:
    """Return the last 20 SDN policy events from the telemetry store."""
    return telemetry_store.get_policy_events()


# ===========================================================================
# Health
# ===========================================================================

@app.get("/api/health", status_code=status.HTTP_200_OK)
def health() -> Dict[str, Any]:
    """
    Quick health check.  Probes TCP reachability of the exam server with a
    1-second timeout — does NOT authenticate.
    """
    reachable = False
    try:
        with socket.create_connection((config.EXAM_SERVER_HOST, config.EXAM_SERVER_PORT), timeout=1.0):
            reachable = True
    except (ConnectionRefusedError, OSError, TimeoutError):
        reachable = False

    return {
        "status": "ok",
        "exam_server_reachable": reachable,
        "timestamp": time.time(),
    }


# ===========================================================================
# WebSocket: per-student exam channel
# ===========================================================================

@app.websocket("/ws/exam/{gateway_session_id}")
async def ws_exam(websocket: WebSocket, gateway_session_id: str) -> None:
    """
    WebSocket channel for a single student session.

    Pushes:
      {"type": "timer_tick", "remaining_seconds": float}  — every 2 s
      {"type": "exam_expired"}                            — when time hits 0
      {"type": "question_ack", ...ack_payload}            — mirrored from ACK cache

    Receives:
      {"action": "ping"}  → reply {"type": "pong", "remaining_seconds": float|null}
    """
    adapter = session_store.get(gateway_session_id)
    if adapter is None:
        await websocket.close(code=4004)
        return

    await websocket.accept()

    async def _send_json(data: dict) -> None:
        try:
            await websocket.send_json(data)
        except Exception:
            pass

    async def _ticker() -> None:
        """Background task: push timer_tick every 2 seconds."""
        try:
            while True:
                await asyncio.sleep(2)
                remaining = adapter.last_remaining_seconds
                if remaining is not None:
                    if remaining <= 0:
                        await _send_json({"type": "exam_expired"})
                        break
                    await _send_json({"type": "timer_tick", "remaining_seconds": remaining})
        except asyncio.CancelledError:
            pass

    ticker_task = asyncio.create_task(_ticker())

    try:
        while True:
            try:
                raw = await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
            except asyncio.TimeoutError:
                # Keep-alive: send a noop and wait again
                continue
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                continue

            if msg.get("action") == "ping":
                await _send_json(
                    {
                        "type": "pong",
                        "remaining_seconds": adapter.last_remaining_seconds,
                    }
                )
    except WebSocketDisconnect:
        pass
    except Exception as exc:
        logger.warning("ws_exam error for %s: %s", gateway_session_id, exc)
    finally:
        ticker_task.cancel()
        try:
            await ticker_task
        except asyncio.CancelledError:
            pass


# ===========================================================================
# WebSocket: SDN monitor
# ===========================================================================

@app.websocket("/ws/sdn/monitor")
async def ws_sdn_monitor(websocket: WebSocket) -> None:
    """
    WebSocket channel for the SDN telemetry dashboard.

    Pushes a telemetry snapshot every 3 seconds:
      {"type": "telemetry", ...telemetry_fields}

    Sends {"type": "connected"} immediately on join.
    """
    await websocket.accept()

    async def _send_json(data: dict) -> None:
        try:
            await websocket.send_json(data)
        except Exception:
            pass

    await _send_json({"type": "connected"})

    try:
        while True:
            snapshot = get_live_telemetry()
            await _send_json({"type": "telemetry", **snapshot})
            await asyncio.sleep(3)
    except WebSocketDisconnect:
        pass
    except Exception as exc:
        logger.warning("ws_sdn_monitor error: %s", exc)


# ---------------------------------------------------------------------------
# Mount production frontend build if present
# ---------------------------------------------------------------------------
_FRONTEND_DIST = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "frontend", "dist"
)
if os.path.exists(_FRONTEND_DIST):
    import os as _os
    from fastapi.staticfiles import StaticFiles
    from starlette.responses import FileResponse

    # Serve static assets
    assets_dir = _os.path.join(_FRONTEND_DIST, "assets")
    if _os.path.exists(assets_dir):
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

    # SPA catch-all for React Router navigation
    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_spa(full_path: str):
        file_path = _os.path.join(_FRONTEND_DIST, full_path)
        if _os.path.isfile(file_path):
            return FileResponse(file_path)
        return FileResponse(_os.path.join(_FRONTEND_DIST, "index.html"))

