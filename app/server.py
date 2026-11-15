"""
Concurrent TCP Examination Server.

Features:
- Handles multiple simultaneous student connections using worker threads.
- Robust length-prefixed framing over TCP with JSON messages.
- Server-authoritative timer with automatic timeout submission.
- Persistent SQLite storage for answers, sessions, and final scores.
- Graceful shutdown and clean thread cleanup.
"""

import argparse
import logging
import os
import signal
import socket
import sys
import threading
import time
from typing import Optional

from app.exam_manager import ExamManager
from app.metrics import MetricsCollector
from app.protocol import (
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
    ProtocolError,
    create_message,
    recv_framed_message,
    send_framed_message,
    validate_auth_request,
    validate_answer_submission
)
from app.question_bank import QuestionBank
from app.storage import ExamStorage

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] [SERVER] %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger("ExamServer")


class ExamServer:
    def __init__(
        self,
        host: str = "0.0.0.0",
        port: int = 5000,
        questions_file: Optional[str] = None,
        exam_duration_sec: float = 300.0,
        questions_per_exam: int = 5,
        db_path: str = "exam_records.db"
    ):
        self.host = host
        self.port = port
        self.exam_duration_sec = exam_duration_sec
        self.questions_per_exam = questions_per_exam

        # Load question bank
        if not questions_file:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            questions_file = os.path.join(base_dir, "data", "questions.json")

        self.question_bank = QuestionBank(questions_file)
        self.storage = ExamStorage(db_path)
        self.exam_manager = ExamManager(
            question_bank=self.question_bank,
            storage=self.storage,
            default_duration_sec=self.exam_duration_sec,
            questions_per_exam=self.questions_per_exam
        )

        self.metrics = MetricsCollector()
        self.server_socket: Optional[socket.socket] = None
        self.is_running = False
        self.client_threads = []
        self._shutdown_event = threading.Event()

    def start(self, blocking: bool = True) -> None:
        """Start the TCP server."""
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind((self.host, self.port))
        self.server_socket.listen(50)
        self.server_socket.settimeout(1.0)
        self.is_running = True

        logger.info(f"Server listening on {self.host}:{self.port} (Duration: {self.exam_duration_sec}s, Questions: {self.questions_per_exam})")

        if blocking:
            self._serve_loop()
        else:
            serve_thread = threading.Thread(target=self._serve_loop, daemon=True)
            serve_thread.start()

    def _serve_loop(self) -> None:
        while self.is_running and not self._shutdown_event.is_set():
            try:
                conn, address = self.server_socket.accept()
                t = threading.Thread(
                    target=self._handle_client,
                    args=(conn, address),
                    daemon=True
                )
                t.start()
                self.client_threads.append(t)
            except (socket.timeout, TimeoutError):
                continue
            except OSError:
                break

    def stop(self) -> None:
        """Stop the TCP server gracefully."""
        self.is_running = False
        self._shutdown_event.set()
        if self.server_socket:
            try:
                self.server_socket.close()
            except Exception:
                pass
        self.storage.close()
        self.metrics.finish()
        logger.info("Server stopped.")

    def _handle_client(self, conn: socket.socket, address) -> None:
        logger.info(f"Accepted TCP connection from {address[0]}:{address[1]}")
        conn.settimeout(30.0)  # 30-second socket timeout to prevent hung clients
        session_id = None
        student_id = "UNKNOWN"

        try:
            # 1. Expect AUTH_REQUEST
            auth_msg = recv_framed_message(conn)
            if auth_msg.get("type") != TYPE_AUTH_REQUEST:
                err_response = create_message(TYPE_ERROR, {"code": 401, "message": "Expected AUTH_REQUEST"})
                send_framed_message(conn, err_response)
                return

            student_id, student_name = validate_auth_request(auth_msg)
            session = self.exam_manager.start_exam(
                student_id=student_id,
                student_name=student_name,
                duration_sec=self.exam_duration_sec,
                question_count=self.questions_per_exam
            )
            session_id = session.session_id

            logger.info(f"Student authenticated: {student_name} ({student_id}), Session: {session_id}")

            # Send AUTH_RESPONSE
            auth_response = create_message(TYPE_AUTH_RESPONSE, {
                "status": "ACCEPTED",
                "session_id": session_id,
                "student_id": student_id,
                "student_name": student_name,
                "exam_duration_sec": self.exam_duration_sec,
                "total_questions": len(session.questions)
            })
            send_framed_message(conn, auth_response)

            # 2. Main Examination Interaction Loop
            while self.is_running and not self._shutdown_event.is_set():
                if session.timer.is_expired():
                    logger.warning(f"Session {session_id} expired on server timer.")
                    break

                try:
                    msg = recv_framed_message(conn)
                except (socket.timeout, TimeoutError):
                    if session.timer.is_expired():
                        break
                    continue

                msg_type = msg.get("type")
                t0 = time.time()

                if msg_type == TYPE_QUESTION_REQUEST:
                    q = session.get_current_question()
                    if not q:
                        # All questions delivered
                        logger.info(f"All questions delivered for {student_id}")
                        break

                    rem_time = session.timer.remaining_seconds()
                    q_payload = q.to_client_dict(
                        index=session.current_index + 1,
                        total=len(session.questions),
                        remaining_time=rem_time
                    )
                    send_framed_message(conn, create_message(TYPE_QUESTION_DELIVERY, q_payload))

                elif msg_type == TYPE_SUBMIT_ANSWER:
                    stu_id, q_id, selected_opt = validate_answer_submission(msg)
                    latency_ms = (time.time() - t0) * 1000.0

                    is_correct, pts, expl, rem = self.exam_manager.submit_answer(
                        session_id=session_id,
                        question_id=q_id,
                        selected_option=selected_opt,
                        latency_ms=latency_ms
                    )

                    self.metrics.record_latency(student_id, latency_ms)

                    ack_payload = {
                        "question_id": q_id,
                        "received": True,
                        "is_correct": is_correct,
                        "points_awarded": pts,
                        "explanation": expl,
                        "remaining_seconds": max(0.0, round(rem, 1))
                    }
                    send_framed_message(conn, create_message(TYPE_ANSWER_ACK, ack_payload))

                    if session.current_index >= len(session.questions):
                        # All answered
                        break

                elif msg_type == TYPE_EXAM_SUBMIT:
                    break

                elif msg_type == TYPE_PING:
                    send_framed_message(conn, create_message(TYPE_PONG, {"echo": msg.get("payload")}))

                else:
                    send_framed_message(conn, create_message(TYPE_ERROR, {
                        "code": 400,
                        "message": f"Unexpected message type: {msg_type}"
                    }))

            # 3. Finalize Exam & Send Result
            reason = "TIME_EXPIRED" if session.timer.is_expired() else "COMPLETED"
            result_data = self.exam_manager.finish_exam(session_id, reason=reason)
            result_msg = create_message(TYPE_RESULT_RESPONSE, result_data)
            try:
                send_framed_message(conn, result_msg)
            except Exception:
                pass

            self.metrics.record_completion(student_id, success=True)
            logger.info(f"Exam finished for {student_id} | Score: {result_data.get('score')}/{result_data.get('total_points')} ({result_data.get('percentage')}%) [{reason}]")

        except (ConnectionError, ProtocolError, OSError) as err:
            logger.warning(f"Connection issue with {student_id} ({address}): {err}")
            self.metrics.record_completion(student_id, success=False)
            if session_id:
                self.exam_manager.finish_exam(session_id, reason="DISCONNECTED")
        except Exception as err:
            logger.exception(f"Unhandled server error with {student_id} ({address}): {err}")
            self.metrics.record_completion(student_id, success=False)
            if session_id:
                self.exam_manager.finish_exam(session_id, reason="SERVER_ERROR")
        finally:
            try:
                conn.close()
            except Exception:
                pass


def main():
    parser = argparse.ArgumentParser(description="SDN Online Examination Server")
    parser.add_argument("--host", default="0.0.0.0", help="Host IP to bind (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=5000, help="Port to listen (default: 5000)")
    parser.add_argument("--duration", type=float, default=300.0, help="Exam duration in seconds (default: 300)")
    parser.add_argument("--questions", type=int, default=5, help="Questions per exam (default: 5)")
    parser.add_argument("--db", default="exam_records.db", help="SQLite database path")
    args = parser.parse_args()

    server = ExamServer(
        host=args.host,
        port=args.port,
        exam_duration_sec=args.duration,
        questions_per_exam=args.questions,
        db_path=args.db
    )

    def handle_sigint(signum, frame):
        logger.info("Termination signal received. Shutting down server...")
        server.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, handle_sigint)
    server.start(blocking=True)


if __name__ == "__main__":
    main()
