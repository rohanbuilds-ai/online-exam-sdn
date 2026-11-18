"""
Unit tests for the FastAPI Gateway and TCP Adapter layer.
"""

import os
import time
import unittest
from starlette.testclient import TestClient

from api.main import app
from api.session_store import SessionStore
from api.sdn_telemetry import SDNTelemetryStore, get_historical_results
from api.tcp_adapter import TcpExamAdapter, TcpAdapterError


class DummySocket:
    """Mock socket for testing TcpExamAdapter framing without a real network daemon."""
    def __init__(self, responses=None):
        self.sent_data = bytearray()
        self.responses = responses or []
        self.closed = False

    def sendall(self, data):
        self.sent_data.extend(data)

    def close(self):
        self.closed = True


class TestApiLayer(unittest.TestCase):
    def setUp(self):
        import api.main as main_mod
        if main_mod._exam_storage is None:
            from app.storage import ExamStorage
            main_mod._exam_storage = ExamStorage(db_path=":memory:")
        self.client = TestClient(app)

    def test_health_endpoint(self):
        response = self.client.get("/api/health")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data.get("status"), "ok")
        self.assertIn("exam_server_reachable", data)
        self.assertIn("timestamp", data)

    def test_sdn_history_endpoint(self):
        response = self.client.get("/api/sdn/history")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("baseline", data)
        self.assertIn("dynamic", data)
        self.assertIsInstance(data["baseline"], list)
        self.assertIsInstance(data["dynamic"], list)

    def test_sdn_telemetry_disconnected_state(self):
        response = self.client.get("/api/sdn/telemetry")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("available", data)
        self.assertIn("congestion_state", data)

    def test_session_store_lifecycle(self):
        store = SessionStore()
        dummy_adapter = object()
        gid = store.create("STU999", "Test Student", dummy_adapter)
        self.assertTrue(bool(gid))

        # Retrieve
        adapter = store.get(gid)
        self.assertIs(adapter, dummy_adapter)

        # Meta
        meta = store.get_entry(gid)
        self.assertIsNotNone(meta)
        self.assertEqual(meta.student_id, "STU999")

        # List active
        active = store.list_active()
        self.assertEqual(len(active), 1)
        self.assertEqual(active[0]["student_id"], "STU999")
        self.assertEqual(active[0]["id"], gid)
        self.assertEqual(active[0]["gateway_session_id"], gid)

        # Remove
        store.remove(gid)
        self.assertIsNone(store.get(gid))

    def test_sdn_telemetry_store_staleness(self):
        store = SDNTelemetryStore(snapshot_file=None)
        initial = store.get()
        self.assertFalse(initial["available"])

        # Update with recent timestamp
        now = time.time()
        store.update({
            "controller_connected": True,
            "switch_count": 1,
            "congestion_state": "NORMAL",
            "policy_active": False,
            "timestamp": now
        })
        snap = store.get()
        self.assertTrue(snap["available"])
        self.assertFalse(snap["stale"])
        self.assertEqual(snap["congestion_state"], "NORMAL")

        # Update with old timestamp
        store.update({
            "controller_connected": True,
            "switch_count": 1,
            "congestion_state": "CONGESTED",
            "policy_active": True,
            "timestamp": now - 30.0  # 30 seconds old
        })
        snap_old = store.get()
        self.assertTrue(snap_old["available"])
        self.assertTrue(snap_old["stale"])

    def test_admin_sessions_endpoint_requires_auth(self):
        """Accessing admin endpoints without an active session returns 401 Unauthorized."""
        unauth_resp = self.client.get("/api/admin/sessions")
        self.assertEqual(unauth_resp.status_code, 401)
        self.assertIn("error", unauth_resp.json().get("detail", {}))

    def test_admin_auth_flow(self):
        """Test complete admin lifecycle: login failure, success, cookie session, protected access, and logout."""
        import api.config as cfg
        orig_pw = cfg.ADMIN_PASSWORD
        cfg.ADMIN_PASSWORD = "test-strong-admin-pass-xyz"

        try:
            # 1. Unauthenticated request to /api/admin/stats returns 401
            unauth = self.client.get("/api/admin/stats")
            self.assertEqual(unauth.status_code, 401)

            # 2. Check session endpoint initially reports authenticated=False
            sess_check = self.client.get("/api/admin/session")
            self.assertEqual(sess_check.status_code, 200)
            self.assertFalse(sess_check.json().get("authenticated"))

            # 3. Login with wrong password returns 401
            bad_login = self.client.post("/api/admin/login", json={"password": "wrong-password"})
            self.assertEqual(bad_login.status_code, 401)

            # 4. Login with correct password returns 200 and issues cookie
            good_login = self.client.post("/api/admin/login", json={"password": "test-strong-admin-pass-xyz"})
            self.assertEqual(good_login.status_code, 200)
            self.assertEqual(good_login.json().get("status"), "authenticated")
            self.assertIn("admin_session", good_login.cookies)

            # 5. Access protected endpoint with cookie returns 200 OK
            stats_resp = self.client.get("/api/admin/stats")
            self.assertEqual(stats_resp.status_code, 200)
            self.assertIn("active_sessions", stats_resp.json())

            sessions_resp = self.client.get("/api/admin/sessions")
            self.assertEqual(sessions_resp.status_code, 200)
            self.assertIsInstance(sessions_resp.json(), list)

            # 6. Check session endpoint reports authenticated=True
            sess_check = self.client.get("/api/admin/session")
            self.assertEqual(sess_check.status_code, 200)
            self.assertTrue(sess_check.json().get("authenticated"))

            # 7. Logout clears session
            logout_resp = self.client.post("/api/admin/logout")
            self.assertEqual(logout_resp.status_code, 200)
            self.assertEqual(logout_resp.json().get("status"), "logged_out")

            # 8. Subsequent access returns 401 Unauthorized
            subsequent = self.client.get("/api/admin/sessions")
            self.assertEqual(subsequent.status_code, 401)

        finally:
            cfg.ADMIN_PASSWORD = orig_pw

    def test_admin_login_unconfigured_fails_safely(self):
        """When ADMIN_PASSWORD is unset, login fails safely with 503 Service Unavailable."""
        import api.config as cfg
        orig_pw = cfg.ADMIN_PASSWORD
        cfg.ADMIN_PASSWORD = None

        try:
            resp = self.client.post("/api/admin/login", json={"password": "any-password"})
            self.assertEqual(resp.status_code, 503)
            self.assertIn("not configured", resp.json().get("detail", {}).get("error", ""))
        finally:
            cfg.ADMIN_PASSWORD = orig_pw

    def test_missing_session_id_header(self):
        # Accessing /api/exam/question without X-Session-ID should return 400
        response = self.client.get("/api/exam/question")
        self.assertEqual(response.status_code, 400)

        # Accessing with invalid X-Session-ID should return 404
        response = self.client.get("/api/exam/question", headers={"X-Session-ID": "non-existent-uuid"})
        self.assertEqual(response.status_code, 404)

    def test_end_to_end_student_examination_via_fastapi(self):
        """Full end-to-end test: start real TCP ExamServer, connect via FastAPI, answer questions, submit, and verify results."""
        from app.server import ExamServer
        import socket

        # Find free ephemeral port
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.bind(("127.0.0.1", 0))
        test_port = s.getsockname()[1]
        s.close()

        server = ExamServer(
            host="127.0.0.1",
            port=test_port,
            exam_duration_sec=60.0,
            questions_per_exam=2,
            db_path=":memory:"
        )
        server.start(blocking=False)
        time.sleep(0.3)

        try:
            # Override adapter host/port in api.config temporarily
            import api.config as cfg
            orig_host, orig_port = cfg.EXAM_SERVER_HOST, cfg.EXAM_SERVER_PORT
            cfg.EXAM_SERVER_HOST, cfg.EXAM_SERVER_PORT = "127.0.0.1", test_port

            # 1. Auth via API
            auth_resp = self.client.post("/api/exam/auth", json={
                "student_id": "STU_E2E",
                "student_name": "End to End Student"
            })
            self.assertEqual(auth_resp.status_code, 200)
            auth_data = auth_resp.json()
            session_id = auth_data["gateway_session_id"]
            self.assertEqual(auth_data["student_id"], "STU_E2E")
            self.assertEqual(auth_data["total_questions"], 2)

            # 2. Get Question 1
            q1_resp = self.client.get("/api/exam/question", headers={"X-Session-ID": session_id})
            self.assertEqual(q1_resp.status_code, 200)
            q1 = q1_resp.json()
            self.assertEqual(q1["number"], 1)
            self.assertIn("question", q1)
            self.assertEqual(len(q1["options"]), 4)

            # 3. Submit Answer for Question 1
            ans1_resp = self.client.post("/api/exam/answer", headers={"X-Session-ID": session_id}, json={
                "question_id": q1["question_id"],
                "selected_option": 1
            })
            self.assertEqual(ans1_resp.status_code, 200)
            ack1 = ans1_resp.json()
            self.assertIn("is_correct", ack1)
            self.assertIn("points_awarded", ack1)

            # 4. Ping Exam Timer
            ping_resp = self.client.get("/api/exam/ping", headers={"X-Session-ID": session_id})
            self.assertEqual(ping_resp.status_code, 200)
            self.assertIsNotNone(ping_resp.json().get("remaining_seconds"))

            # 5. Get Question 2
            q2_resp = self.client.get("/api/exam/question", headers={"X-Session-ID": session_id})
            self.assertEqual(q2_resp.status_code, 200)
            q2 = q2_resp.json()
            self.assertEqual(q2["number"], 2)

            # 6. Submit Answer for Question 2
            ans2_resp = self.client.post("/api/exam/answer", headers={"X-Session-ID": session_id}, json={
                "question_id": q2["question_id"],
                "selected_option": 1
            })
            self.assertEqual(ans2_resp.status_code, 200)

            # 7. Finalize and Submit Exam
            submit_resp = self.client.post("/api/exam/submit", headers={"X-Session-ID": session_id})
            self.assertEqual(submit_resp.status_code, 200)
            result = submit_resp.json()
            self.assertEqual(result["student_id"], "STU_E2E")
            self.assertIn("score", result)
            self.assertIn("percentage", result)
            self.assertIn("passed", result)

            # Restore config
            cfg.EXAM_SERVER_HOST, cfg.EXAM_SERVER_PORT = orig_host, orig_port

        finally:
            server.stop()


if __name__ == "__main__":
    unittest.main()
