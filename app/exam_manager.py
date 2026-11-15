"""
Examination Lifecycle and State Manager.

Coordinates sessions, student registration, question delivery,
server-authoritative timers, auto-submission on expiration,
and score calculation.
"""

import threading
import uuid
import time
from typing import Dict, List, Any, Optional, Tuple

from app.question_bank import QuestionBank, Question
from app.timer import ExamTimer
from app.storage import ExamStorage


class StudentSession:
    def __init__(
        self,
        session_id: str,
        student_id: str,
        student_name: str,
        questions: List[Question],
        duration_seconds: float,
        on_timeout_cb=None
    ):
        self.session_id = session_id
        self.student_id = student_id
        self.student_name = student_name
        self.questions = questions
        self.current_index = 0
        self.answers: Dict[int, int] = {}  # question_id -> selected_option
        self.score = 0
        self.total_points = sum(q.points for q in questions)
        self.is_completed = False
        self.completion_reason = "ACTIVE"
        self._lock = threading.Lock()

        # Attach server-authoritative timer
        self.timer = ExamTimer(
            duration_seconds=duration_seconds,
            on_expiry=lambda: on_timeout_cb(self.session_id) if on_timeout_cb else None
        )

    def start(self) -> None:
        self.timer.start()

    def get_current_question(self) -> Optional[Question]:
        with self._lock:
            if self.current_index < len(self.questions):
                return self.questions[self.current_index]
            return None

    def record_answer(self, question_id: int, selected_option: int) -> Tuple[bool, int, str]:
        with self._lock:
            # Check timer first
            if self.timer.is_expired():
                return False, 0, "Examination time expired. Answer rejected."

            # Find matching question
            target_q = None
            for q in self.questions:
                if q.id == question_id:
                    target_q = q
                    break

            if not target_q:
                return False, 0, f"Question ID {question_id} not part of this exam session."

            is_correct, pts, explanation = target_q.check_answer(selected_option)
            self.answers[question_id] = selected_option
            if is_correct:
                self.score += pts

            # Advance current question index
            self.current_index += 1
            return is_correct, pts, explanation

    def finish(self, reason: str = "COMPLETED") -> Dict[str, Any]:
        with self._lock:
            self.is_completed = True
            self.completion_reason = reason
            duration_taken = self.timer.stop()
            percentage = round((self.score / self.total_points * 100.0) if self.total_points > 0 else 0.0, 2)
            passed = percentage >= 50.0
            return {
                "session_id": self.session_id,
                "student_id": self.student_id,
                "student_name": self.student_name,
                "score": self.score,
                "total_points": self.total_points,
                "total_questions": len(self.questions),
                "questions_answered": len(self.answers),
                "percentage": percentage,
                "passed": passed,
                "duration_taken_sec": round(duration_taken, 2),
                "reason": self.completion_reason
            }


class ExamManager:
    """Central exam coordinator managing all concurrent student sessions."""
    def __init__(
        self,
        question_bank: QuestionBank,
        storage: Optional[ExamStorage] = None,
        default_duration_sec: float = 300.0,
        questions_per_exam: int = 5
    ):
        self.question_bank = question_bank
        self.storage = storage or ExamStorage()
        self.default_duration_sec = default_duration_sec
        self.questions_per_exam = questions_per_exam
        self.sessions: Dict[str, StudentSession] = {}
        self.student_to_session: Dict[str, str] = {}
        self._lock = threading.Lock()

    def start_exam(
        self,
        student_id: str,
        student_name: str,
        duration_sec: Optional[float] = None,
        question_count: Optional[int] = None
    ) -> StudentSession:
        """Initialize an exam session for a student."""
        with self._lock:
            # Register student in persistent database
            self.storage.register_student(student_id, student_name)

            dur = duration_sec if duration_sec is not None else self.default_duration_sec
            cnt = question_count if question_count is not None else self.questions_per_exam

            session_id = f"sess_{student_id}_{int(time.time())}_{uuid.uuid4().hex[:4]}"
            questions = self.question_bank.get_exam_questions(count=cnt, shuffle=False)

            session = StudentSession(
                session_id=session_id,
                student_id=student_id,
                student_name=student_name,
                questions=questions,
                duration_seconds=dur,
                on_timeout_cb=self._handle_session_timeout
            )

            self.sessions[session_id] = session
            self.student_to_session[student_id] = session_id

            # Save session to SQLite
            self.storage.create_session(session_id, student_id, dur)
            session.start()
            return session

    def get_session(self, session_id: str) -> Optional[StudentSession]:
        with self._lock:
            return self.sessions.get(session_id)

    def get_session_by_student(self, student_id: str) -> Optional[StudentSession]:
        with self._lock:
            sid = self.student_to_session.get(student_id)
            return self.sessions.get(sid) if sid else None

    def submit_answer(
        self,
        session_id: str,
        question_id: int,
        selected_option: int,
        latency_ms: float = 0.0
    ) -> Tuple[bool, int, str, float]:
        """Submit answer and update storage."""
        session = self.get_session(session_id)
        if not session:
            return False, 0, "Invalid session ID", 0.0

        is_correct, pts, explanation = session.record_answer(question_id, selected_option)
        remaining = session.timer.remaining_seconds()

        # Record into persistent DB
        self.storage.record_answer(
            session_id=session_id,
            question_id=question_id,
            selected_option=selected_option,
            is_correct=is_correct,
            points=pts,
            latency_ms=latency_ms
        )

        return is_correct, pts, explanation, remaining

    def finish_exam(self, session_id: str, reason: str = "COMPLETED") -> Dict[str, Any]:
        """Finalize the exam, persist result, and return summary."""
        session = self.get_session(session_id)
        if not session:
            return {}

        result = session.finish(reason=reason)

        # Update SQLite result record
        self.storage.finalize_session(
            session_id=session_id,
            student_id=session.student_id,
            score=result["score"],
            total_points=result["total_points"],
            status=reason
        )

        return result

    def _handle_session_timeout(self, session_id: str) -> None:
        """Triggered automatically by ExamTimer when student deadline expires."""
        session = self.get_session(session_id)
        if session and not session.is_completed:
            self.finish_exam(session_id, reason="TIME_EXPIRED")
