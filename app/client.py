"""
Student Examination Client for Online Examination Network.

Supports:
1. Interactive CLI Mode: Displays questions, choices, countdown timer, prompts student.
2. Automated Headless Mode: For performance evaluation, load testing, and Mininet scripts.
3. Latency measurement: Tracks per-question RTT and prints summary.
"""

import argparse
import os
import socket
import sys
import time
from typing import Dict, Any, Optional

from app.protocol import (
    TYPE_AUTH_REQUEST,
    TYPE_AUTH_RESPONSE,
    TYPE_QUESTION_REQUEST,
    TYPE_QUESTION_DELIVERY,
    TYPE_SUBMIT_ANSWER,
    TYPE_ANSWER_ACK,
    TYPE_RESULT_RESPONSE,
    TYPE_ERROR,
    create_message,
    send_framed_message,
    recv_framed_message,
    ProtocolError
)


class ExamClient:
    def __init__(
        self,
        server_host: str = "127.0.0.1",
        server_port: int = 5000,
        student_id: str = "STU001",
        student_name: str = "Student 1",
        timeout: float = 15.0
    ):
        self.server_host = server_host
        self.server_port = server_port
        self.student_id = student_id
        self.student_name = student_name
        self.timeout = timeout
        self.sock: Optional[socket.socket] = None
        self.latencies_ms = []

    def connect(self) -> None:
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.settimeout(self.timeout)
        self.sock.connect((self.server_host, self.server_port))

    def close(self) -> None:
        if self.sock:
            try:
                self.sock.close()
            except Exception:
                pass
            self.sock = None

    def run_interactive(self) -> Dict[str, Any]:
        """Run interactive examination session in terminal."""
        self.connect()
        try:
            print("\n" + "=" * 60)
            print("        ONLINE EXAMINATION NETWORK - STUDENT PORTAL")
            print("=" * 60)

            # 1. Send AUTH_REQUEST
            auth_req = create_message(TYPE_AUTH_REQUEST, {
                "student_id": self.student_id,
                "name": self.student_name
            })
            send_framed_message(self.sock, auth_req)

            auth_resp = recv_framed_message(self.sock)
            if auth_resp.get("type") != TYPE_AUTH_RESPONSE:
                print(f"[ERROR] Authentication failed: {auth_resp.get('payload')}")
                return {}

            payload = auth_resp["payload"]
            print(f"Logged in as: {payload['student_name']} (ID: {payload['student_id']})")
            print(f"Exam Duration: {payload['exam_duration_sec']} seconds")
            print(f"Total Questions: {payload['total_questions']}")
            print("-" * 60)

            total_q = payload["total_questions"]
            for _ in range(total_q):
                # Request next question
                t0 = time.time()
                send_framed_message(self.sock, create_message(TYPE_QUESTION_REQUEST, {}))
                q_msg = recv_framed_message(self.sock)
                rtt = (time.time() - t0) * 1000.0
                self.latencies_ms.append(rtt)

                if q_msg.get("type") == TYPE_RESULT_RESPONSE:
                    return self._display_result(q_msg["payload"])

                if q_msg.get("type") != TYPE_QUESTION_DELIVERY:
                    print(f"[ERROR] Unexpected message: {q_msg}")
                    break

                q_data = q_msg["payload"]
                print(f"\n[Question {q_data['number']}/{q_data['total']}] (Points: {q_data['points']} | Time Left: {q_data['remaining_seconds']}s)")
                print(f"Topic: {q_data.get('category', 'General')}")
                print(f"{q_data['question']}\n")

                for idx, opt in enumerate(q_data["options"], start=1):
                    print(f"  {idx}. {opt}")

                # Prompt user
                choice = 0
                while True:
                    try:
                        inp = input("\nYour answer (1-4): ").strip()
                        choice = int(inp)
                        if 1 <= choice <= len(q_data["options"]):
                            break
                        print("Please enter a valid choice number.")
                    except ValueError:
                        print("Invalid input. Please enter a number.")
                    except (KeyboardInterrupt, EOFError):
                        print("\nExam interrupted by user.")
                        return {}

                # Submit answer
                t_sub = time.time()
                sub_msg = create_message(TYPE_SUBMIT_ANSWER, {
                    "student_id": self.student_id,
                    "question_id": q_data["question_id"],
                    "selected_option": choice
                })
                send_framed_message(self.sock, sub_msg)

                ack_msg = recv_framed_message(self.sock)
                sub_rtt = (time.time() - t_sub) * 1000.0
                self.latencies_ms.append(sub_rtt)

                if ack_msg.get("type") == TYPE_ANSWER_ACK:
                    ack = ack_msg["payload"]
                    status_str = "CORRECT" if ack.get("is_correct") else "INCORRECT"
                    print(f"-> Submitted! [{status_str}] (Latency: {sub_rtt:.1f}ms, Remaining: {ack.get('remaining_seconds')}s)")
                    if ack.get("explanation"):
                        print(f"   Explanation: {ack['explanation']}")

            # Receive final result
            final_msg = recv_framed_message(self.sock)
            if final_msg.get("type") == TYPE_RESULT_RESPONSE:
                return self._display_result(final_msg["payload"])

            return {}

        finally:
            self.close()

    def run_automated(self, think_delay_sec: float = 0.2, pick_correct: bool = True) -> Dict[str, Any]:
        """Run automated examination session without interactive prompts."""
        self.connect()
        try:
            # 1. Auth
            auth_req = create_message(TYPE_AUTH_REQUEST, {
                "student_id": self.student_id,
                "name": self.student_name
            })
            send_framed_message(self.sock, auth_req)
            auth_resp = recv_framed_message(self.sock)
            total_q = auth_resp.get("payload", {}).get("total_questions", 3)

            for _ in range(total_q):
                t0 = time.time()
                send_framed_message(self.sock, create_message(TYPE_QUESTION_REQUEST, {}))
                q_msg = recv_framed_message(self.sock)
                self.latencies_ms.append((time.time() - t0) * 1000.0)

                if q_msg.get("type") == TYPE_RESULT_RESPONSE:
                    return q_msg["payload"]
                if q_msg.get("type") != TYPE_QUESTION_DELIVERY:
                    break

                q_data = q_msg["payload"]
                if think_delay_sec > 0:
                    time.sleep(think_delay_sec)

                # Pick answer (1 or predetermined)
                selected = 2 if pick_correct else 1
                t_sub = time.time()
                sub_msg = create_message(TYPE_SUBMIT_ANSWER, {
                    "student_id": self.student_id,
                    "question_id": q_data["question_id"],
                    "selected_option": selected
                })
                send_framed_message(self.sock, sub_msg)
                ack = recv_framed_message(self.sock)
                self.latencies_ms.append((time.time() - t_sub) * 1000.0)

            # Receive final result
            final_msg = recv_framed_message(self.sock)
            if final_msg.get("type") == TYPE_RESULT_RESPONSE:
                return final_msg["payload"]
            return {}
        finally:
            self.close()

    def _display_result(self, result: Dict[str, Any]) -> Dict[str, Any]:
        print("\n" + "=" * 60)
        print("               EXAMINATION COMPLETED")
        print("=" * 60)
        print(f"Student: {result.get('student_name')} ({result.get('student_id')})")
        print(f"Score: {result.get('score')} / {result.get('total_points')} points")
        print(f"Percentage: {result.get('percentage')}%")
        print(f"Status: {'PASSED' if result.get('passed') else 'FAILED'} (Reason: {result.get('reason')})")
        print(f"Time Taken: {result.get('duration_taken_sec')} seconds")
        if self.latencies_ms:
            avg_rtt = sum(self.latencies_ms) / len(self.latencies_ms)
            print(f"Average Request Latency: {avg_rtt:.2f} ms")
        print("=" * 60 + "\n")
        return result


def main():
    parser = argparse.ArgumentParser(description="SDN Examination Student Client")
    parser.add_argument("--server", default=os.environ.get("EXAM_SERVER", "127.0.0.1"), help="Server host IP")
    parser.add_argument("--port", type=int, default=5000, help="Server port (default: 5000)")
    parser.add_argument("--id", default="STU101", help="Student ID (default: STU101)")
    parser.add_argument("--name", default="Student", help="Student Name")
    parser.add_argument("--auto", action="store_true", help="Run in automated test mode")
    parser.add_argument("--delay", type=float, default=0.2, help="Automated mode delay per answer")
    args = parser.parse_args()

    client = ExamClient(
        server_host=args.server,
        server_port=args.port,
        student_id=args.id,
        student_name=args.name
    )

    try:
        if args.auto:
            res = client.run_automated(think_delay_sec=args.delay)
            print(f"[AUTOMATED CLIENT] Completed: {res}")
        else:
            client.run_interactive()
    except (ConnectionError, OSError) as err:
        print(f"[CLIENT ERROR] Could not communicate with server: {err}")
        sys.exit(1)


if __name__ == "__main__":
    main()
