"""
Unit tests for protocol message framing, serialization, and validation.
"""

import socket
import threading
import unittest
from app.protocol import (
    create_message,
    send_framed_message,
    recv_framed_message,
    validate_auth_request,
    validate_answer_submission,
    TYPE_AUTH_REQUEST,
    TYPE_AUTH_RESPONSE,
    TYPE_SUBMIT_ANSWER,
    TYPE_QUESTION_DELIVERY,
    ProtocolError
)


class TestProtocol(unittest.TestCase):
    def test_create_message(self):
        msg = create_message(TYPE_AUTH_REQUEST, {"student_id": "S123", "name": "Bob"})
        self.assertEqual(msg["type"], TYPE_AUTH_REQUEST)
        self.assertEqual(msg["payload"]["student_id"], "S123")
        self.assertIn("timestamp", msg)
        self.assertIn("msg_id", msg)

    def test_invalid_message_type(self):
        with self.assertRaises(ProtocolError):
            create_message("NON_EXISTENT_TYPE", {})

    def test_framed_socket_transfer(self):
        # Create a loopback socket pair
        server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_sock.bind(("127.0.0.1", 0))
        server_sock.listen(1)
        port = server_sock.getsockname()[1]

        received_msgs = []

        def server_worker():
            conn, _ = server_sock.accept()
            try:
                m1 = recv_framed_message(conn)
                received_msgs.append(m1)
                m2 = recv_framed_message(conn)
                received_msgs.append(m2)
            finally:
                conn.close()
                server_sock.close()

        t = threading.Thread(target=server_worker)
        t.start()

        client_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client_sock.connect(("127.0.0.1", port))

        orig_m1 = create_message(TYPE_AUTH_REQUEST, {"student_id": "STU1", "name": "Alice"})
        orig_m2 = create_message(TYPE_SUBMIT_ANSWER, {"student_id": "STU1", "question_id": 1, "selected_option": 2})

        send_framed_message(client_sock, orig_m1)
        send_framed_message(client_sock, orig_m2)
        client_sock.close()
        t.join()

        self.assertEqual(len(received_msgs), 2)
        self.assertEqual(received_msgs[0]["payload"]["student_id"], "STU1")
        self.assertEqual(received_msgs[1]["payload"]["selected_option"], 2)

    def test_validate_auth_request(self):
        valid = create_message(TYPE_AUTH_REQUEST, {"student_id": "STU99", "name": "Charlie"})
        sid, name = validate_auth_request(valid)
        self.assertEqual(sid, "STU99")
        self.assertEqual(name, "Charlie")

        invalid = create_message(TYPE_AUTH_REQUEST, {"name": "NoID"})
        with self.assertRaises(ProtocolError):
            validate_auth_request(invalid)

    def test_validate_answer_submission(self):
        valid = create_message(TYPE_SUBMIT_ANSWER, {"student_id": "S1", "question_id": 3, "selected_option": 1})
        sid, qid, opt = validate_answer_submission(valid)
        self.assertEqual(sid, "S1")
        self.assertEqual(qid, 3)
        self.assertEqual(opt, 1)

        invalid = create_message(TYPE_SUBMIT_ANSWER, {"student_id": "S1", "question_id": "abc"})
        with self.assertRaises(ProtocolError):
            validate_answer_submission(invalid)


if __name__ == "__main__":
    unittest.main()
