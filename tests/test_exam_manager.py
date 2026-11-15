"""
Unit tests for Question Bank, Server Timer, and Exam Manager.
"""

import time
import unittest
from app.question_bank import QuestionBank, Question
from app.timer import ExamTimer
from app.storage import ExamStorage
from app.exam_manager import ExamManager


class TestExamLogic(unittest.TestCase):
    def test_question_evaluation(self):
        q = Question(1, "Net", "Which protocol is reliable?", ["UDP", "TCP"], answer=2, explanation="TCP is reliable", points=2)
        is_correct, pts, exp = q.check_answer(2)
        self.assertTrue(is_correct)
        self.assertEqual(pts, 2)
        self.assertEqual(exp, "TCP is reliable")

        is_wrong, pts0, _ = q.check_answer(1)
        self.assertFalse(is_wrong)
        self.assertEqual(pts0, 0)

    def test_server_authoritative_timer(self):
        expired_flag = []
        timer = ExamTimer(duration_seconds=0.2, on_expiry=lambda: expired_flag.append(True))
        self.assertFalse(timer.is_expired())
        timer.start()
        self.assertGreater(timer.remaining_seconds(), 0.0)
        time.sleep(0.3)
        self.assertTrue(timer.is_expired())
        self.assertEqual(timer.remaining_seconds(), 0.0)
        self.assertTrue(len(expired_flag) > 0)

    def test_exam_manager_flow(self):
        storage = ExamStorage(":memory:")
        qb = QuestionBank()
        # Add 3 questions manually
        qb.questions[1] = Question(1, "Cat", "Q1?", ["A", "B"], 1, points=1)
        qb.questions[2] = Question(2, "Cat", "Q2?", ["A", "B"], 2, points=1)
        qb.ordered_ids = [1, 2]

        manager = ExamManager(question_bank=qb, storage=storage, default_duration_sec=5.0, questions_per_exam=2)
        session = manager.start_exam("STU_A", "Student Alpha")
        self.assertEqual(session.student_id, "STU_A")

        # Answer Q1 correctly
        is_corr, pts, _, rem = manager.submit_answer(session.session_id, 1, 1)
        self.assertTrue(is_corr)
        self.assertEqual(pts, 1)

        # Answer Q2 incorrectly
        is_corr2, pts2, _, _ = manager.submit_answer(session.session_id, 2, 1)
        self.assertFalse(is_corr2)
        self.assertEqual(pts2, 0)

        result = manager.finish_exam(session.session_id)
        self.assertEqual(result["score"], 1)
        self.assertEqual(result["total_points"], 2)
        self.assertEqual(result["percentage"], 50.0)
        self.assertTrue(result["passed"])

    def test_exam_manager_timeout_rejection(self):
        storage = ExamStorage(":memory:")
        qb = QuestionBank()
        qb.questions[1] = Question(1, "Cat", "Q1?", ["A", "B"], 1)
        qb.ordered_ids = [1]

        manager = ExamManager(question_bank=qb, storage=storage, default_duration_sec=0.1, questions_per_exam=1)
        session = manager.start_exam("STU_TIMEOUT", "Late Student")
        time.sleep(0.2)  # Wait for timer to expire

        is_corr, pts, expl, _ = manager.submit_answer(session.session_id, 1, 1)
        self.assertFalse(is_corr)
        self.assertIn("expired", expl.lower())


if __name__ == "__main__":
    unittest.main()
