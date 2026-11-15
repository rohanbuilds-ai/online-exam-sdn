"""
Persistent SQLite Storage for Examination Records and Student Results.
Thread-safe single-connection storage supporting both file databases and :memory: databases.
"""

import sqlite3
import threading
import time
from typing import Dict, List, Any, Optional


class ExamStorage:
    def __init__(self, db_path: str = "exam_records.db"):
        self.db_path = db_path
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(
            self.db_path,
            check_same_thread=False,
            timeout=30.0
        )
        self._conn.row_factory = sqlite3.Row
        if self.db_path != ":memory:":
            try:
                self._conn.execute("PRAGMA journal_mode = WAL;")
                self._conn.commit()
            except Exception:
                pass
        self._init_db()

    def _init_db(self) -> None:
        """Create tables if they do not exist."""
        with self._lock:
            cursor = self._conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS students (
                    student_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    first_seen REAL NOT NULL
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id TEXT PRIMARY KEY,
                    student_id TEXT NOT NULL,
                    start_time REAL NOT NULL,
                    end_time REAL,
                    duration_seconds REAL,
                    status TEXT NOT NULL,
                    FOREIGN KEY (student_id) REFERENCES students(student_id)
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS answers (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    question_id INTEGER NOT NULL,
                    selected_option INTEGER NOT NULL,
                    is_correct INTEGER NOT NULL,
                    points INTEGER NOT NULL,
                    latency_ms REAL,
                    timestamp REAL NOT NULL,
                    FOREIGN KEY (session_id) REFERENCES sessions(session_id)
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS results (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL UNIQUE,
                    student_id TEXT NOT NULL,
                    score INTEGER NOT NULL,
                    total_points INTEGER NOT NULL,
                    percentage REAL NOT NULL,
                    status TEXT NOT NULL,
                    completed_at REAL NOT NULL,
                    FOREIGN KEY (session_id) REFERENCES sessions(session_id),
                    FOREIGN KEY (student_id) REFERENCES students(student_id)
                )
            """)
            self._conn.commit()

    def register_student(self, student_id: str, name: str) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT OR IGNORE INTO students (student_id, name, first_seen) VALUES (?, ?, ?)",
                (student_id, name, time.time())
            )
            self._conn.commit()

    def create_session(self, session_id: str, student_id: str, duration_seconds: float) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT INTO sessions (session_id, student_id, start_time, duration_seconds, status) "
                "VALUES (?, ?, ?, ?, ?)",
                (session_id, student_id, time.time(), duration_seconds, "ACTIVE")
            )
            self._conn.commit()

    def record_answer(
        self,
        session_id: str,
        question_id: int,
        selected_option: int,
        is_correct: bool,
        points: int,
        latency_ms: float = 0.0
    ) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT INTO answers (session_id, question_id, selected_option, is_correct, points, latency_ms, timestamp) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (session_id, question_id, selected_option, 1 if is_correct else 0, points, latency_ms, time.time())
            )
            self._conn.commit()

    def finalize_session(
        self,
        session_id: str,
        student_id: str,
        score: int,
        total_points: int,
        status: str = "COMPLETED"
    ) -> Dict[str, Any]:
        percentage = round((score / total_points * 100.0) if total_points > 0 else 0.0, 2)
        now = time.time()
        with self._lock:
            self._conn.execute(
                "UPDATE sessions SET end_time = ?, status = ? WHERE session_id = ?",
                (now, status, session_id)
            )
            self._conn.execute(
                "INSERT OR REPLACE INTO results (session_id, student_id, score, total_points, percentage, status, completed_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (session_id, student_id, score, total_points, percentage, status, now)
            )
            self._conn.commit()

        return {
            "session_id": session_id,
            "student_id": student_id,
            "score": score,
            "total_points": total_points,
            "percentage": percentage,
            "status": status,
            "completed_at": now
        }

    def get_all_results(self) -> List[Dict[str, Any]]:
        with self._lock:
            cursor = self._conn.execute("""
                SELECT r.session_id, r.student_id, s.name, r.score, r.total_points,
                       r.percentage, r.status, r.completed_at
                FROM results r
                LEFT JOIN students s ON r.student_id = s.student_id
                ORDER BY r.completed_at DESC
            """)
            return [dict(row) for row in cursor.fetchall()]

    def get_summary_statistics(self) -> Dict[str, Any]:
        with self._lock:
            cursor = self._conn.execute("""
                SELECT 
                    COUNT(*) as total_exams,
                    AVG(percentage) as avg_score,
                    MAX(percentage) as max_score,
                    MIN(percentage) as min_score
                FROM results
            """)
            row = cursor.fetchone()
            return {
                "total_completed_exams": row["total_exams"] if row else 0,
                "average_percentage": round(row["avg_score"] or 0.0, 2) if row else 0.0,
                "highest_percentage": round(row["max_score"] or 0.0, 2) if row else 0.0,
                "lowest_percentage": round(row["min_score"] or 0.0, 2) if row else 0.0,
            }

    def close(self) -> None:
        with self._lock:
            try:
                self._conn.close()
            except Exception:
                pass
