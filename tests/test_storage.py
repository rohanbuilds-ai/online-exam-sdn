"""
Unit tests for persistent SQLite storage.
"""

import os
import unittest
from app.storage import ExamStorage


class TestStorage(unittest.TestCase):
    def setUp(self):
        self.test_db = "test_exam.db"
        if os.path.exists(self.test_db):
            os.remove(self.test_db)
        self.storage = ExamStorage(self.test_db)

    def tearDown(self):
        if os.path.exists(self.test_db):
            try:
                os.remove(self.test_db)
            except Exception:
                pass

    def test_student_and_session_lifecycle(self):
        self.storage.register_student("STU01", "Alice Smith")
        self.storage.create_session("sess_01", "STU01", 300.0)

        self.storage.record_answer("sess_01", 1, 2, True, 1, 24.5)
        self.storage.record_answer("sess_01", 2, 3, True, 1, 18.2)
        self.storage.record_answer("sess_01", 3, 1, False, 0, 31.0)

        result = self.storage.finalize_session("sess_01", "STU01", score=2, total_points=3, status="COMPLETED")
        self.assertEqual(result["score"], 2)
        self.assertEqual(result["total_points"], 3)
        self.assertAlmostEqual(result["percentage"], 66.67, places=2)

        all_res = self.storage.get_all_results()
        self.assertEqual(len(all_res), 1)
        self.assertEqual(all_res[0]["student_id"], "STU01")
        self.assertEqual(all_res[0]["name"], "Alice Smith")

        summary = self.storage.get_summary_statistics()
        self.assertEqual(summary["total_completed_exams"], 1)
        self.assertEqual(summary["average_percentage"], 66.67)


if __name__ == "__main__":
    unittest.main()
