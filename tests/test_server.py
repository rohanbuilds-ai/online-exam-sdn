"""
Integration tests for concurrent TCP Examination Server and Clients.
"""

import os
import socket
import threading
import time
import unittest

from app.client import ExamClient
from app.server import ExamServer


class TestServerConcurrency(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Pick an ephemeral port
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.bind(("127.0.0.1", 0))
        cls.port = s.getsockname()[1]
        s.close()

        cls.db_path = "test_server_concurrency.db"
        if os.path.exists(cls.db_path):
            os.remove(cls.db_path)

        cls.server = ExamServer(
            host="127.0.0.1",
            port=cls.port,
            exam_duration_sec=10.0,
            questions_per_exam=3,
            db_path=cls.db_path
        )
        cls.server.start(blocking=False)
        time.sleep(0.3)  # Allow socket to bind

    @classmethod
    def tearDownClass(cls):
        cls.server.stop()
        if os.path.exists(cls.db_path):
            try:
                os.remove(cls.db_path)
            except Exception:
                pass

    def test_single_client_exam(self):
        client = ExamClient(
            server_host="127.0.0.1",
            server_port=self.port,
            student_id="TEST_SINGLE",
            student_name="Solo Student"
        )
        res = client.run_automated(think_delay_sec=0.05, pick_correct=True)
        self.assertEqual(res.get("student_id"), "TEST_SINGLE")
        self.assertEqual(res.get("total_questions"), 3)
        self.assertIn("score", res)

    def test_concurrent_multiple_students(self):
        # Launch 5 concurrent student clients simultaneously
        num_students = 5
        results = [None] * num_students
        threads = []

        def student_worker(index):
            client = ExamClient(
                server_host="127.0.0.1",
                server_port=self.port,
                student_id=f"CONCUR_{index}",
                student_name=f"Student {index}"
            )
            try:
                res = client.run_automated(think_delay_sec=0.02, pick_correct=(index % 2 == 0))
                results[index] = res
            except Exception as err:
                results[index] = {"error": str(err)}

        for i in range(num_students):
            t = threading.Thread(target=student_worker, args=(i,))
            threads.append(t)
            t.start()

        for t in threads:
            t.join(timeout=10.0)

        for i, res in enumerate(results):
            self.assertIsNotNone(res, f"Student {i} did not complete")
            self.assertNotIn("error", res, f"Student {i} failed: {res.get('error')}")
            self.assertEqual(res.get("student_id"), f"CONCUR_{i}")
            self.assertEqual(res.get("total_questions"), 3)


if __name__ == "__main__":
    unittest.main()
