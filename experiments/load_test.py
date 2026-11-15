"""
Concurrent Client Load Generation and Stress Testing Tool.

Spawns multiple simultaneous student clients, measures individual and aggregate
application-level performance metrics, and computes Jain's Fairness Index.
"""

import argparse
import csv
import json
import os
import sys
import threading
import time
from typing import Dict, List, Any

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.client import ExamClient
from app.metrics import calculate_jains_fairness_index, compute_percentile


def run_load_test(
    server_host: str = "127.0.0.1",
    server_port: int = 5000,
    num_students: int = 10,
    think_delay: float = 0.1,
    questions_per_exam: int = 5,
    output_prefix: str = "load_test"
) -> Dict[str, Any]:
    print(f"\n[LOAD TEST] Starting load test with {num_students} concurrent students on {server_host}:{server_port}...")
    start_time = time.time()
    results = [None] * num_students
    client_latencies: Dict[str, List[float]] = {}
    threads = []

    def worker(student_idx: int):
        stu_id = f"STU_{student_idx + 1:03d}"
        client = ExamClient(
            server_host=server_host,
            server_port=server_port,
            student_id=stu_id,
            student_name=f"Student #{student_idx + 1}",
            timeout=20.0
        )
        try:
            res = client.run_automated(think_delay_sec=think_delay, pick_correct=(student_idx % 2 == 0))
            results[student_idx] = res
            client_latencies[stu_id] = client.latencies_ms
        except Exception as err:
            results[student_idx] = {"error": str(err), "student_id": stu_id}
            client_latencies[stu_id] = []

    for i in range(num_students):
        t = threading.Thread(target=worker, args=(i,))
        threads.append(t)
        t.start()

    for t in threads:
        t.join(timeout=45.0)

    total_duration = time.time() - start_time
    successful_exams = sum(1 for r in results if r and "error" not in r and r.get("passed") is not None)
    failed_exams = num_students - successful_exams

    all_latencies = []
    per_client_service_rates = []
    for stu_id, lats in client_latencies.items():
        all_latencies.extend(lats)
        if lats:
            avg_lat = sum(lats) / len(lats)
            per_client_service_rates.append(1000.0 / avg_lat if avg_lat > 0 else 1.0)
        else:
            per_client_service_rates.append(0.0)

    total_requests = len(all_latencies)
    avg_latency = round(sum(all_latencies) / total_requests, 2) if total_requests > 0 else 0.0
    p50_latency = compute_percentile(all_latencies, 50.0)
    p95_latency = compute_percentile(all_latencies, 95.0)
    p99_latency = compute_percentile(all_latencies, 99.0)
    min_latency = round(min(all_latencies), 2) if all_latencies else 0.0
    max_latency = round(max(all_latencies), 2) if all_latencies else 0.0

    throughput_rps = round(total_requests / total_duration, 2) if total_duration > 0 else 0.0
    completion_rate = round((successful_exams / num_students) * 100.0, 2)
    fairness = calculate_jains_fairness_index(per_client_service_rates)

    summary = {
        "num_students": num_students,
        "successful_exams": successful_exams,
        "failed_exams": failed_exams,
        "completion_rate_percent": completion_rate,
        "total_requests": total_requests,
        "duration_seconds": round(total_duration, 2),
        "throughput_req_per_sec": throughput_rps,
        "latency_avg_ms": avg_latency,
        "latency_p50_ms": p50_latency,
        "latency_p95_ms": p95_latency,
        "latency_p99_ms": p99_latency,
        "latency_min_ms": min_latency,
        "latency_max_ms": max_latency,
        "jains_fairness_index": fairness
    }

    print("-" * 50)
    print(f"Completed in: {total_duration:.2f}s | Success Rate: {completion_rate}% ({successful_exams}/{num_students})")
    print(f"Throughput: {throughput_rps} req/s | Avg Latency: {avg_latency} ms | P95 Latency: {p95_latency} ms")
    print(f"Jain's Fairness Index: {fairness:.4f}")
    print("-" * 50 + "\n")

    # Export
    os.makedirs("results", exist_ok=True)
    json_path = os.path.join("results", f"{output_prefix}_{num_students}clients.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    return summary


def main():
    parser = argparse.ArgumentParser(description="SDN Exam Network Concurrent Load Tester")
    parser.add_argument("--server", default="127.0.0.1", help="Server host IP")
    parser.add_argument("--port", type=int, default=5000, help="Server port")
    parser.add_argument("--students", type=int, default=10, help="Number of concurrent students")
    parser.add_argument("--delay", type=float, default=0.1, help="Simulated thinking delay per question")
    parser.add_argument("--prefix", default="load_test", help="Output file prefix")
    args = parser.parse_args()

    run_load_test(
        server_host=args.server,
        server_port=args.port,
        num_students=args.students,
        think_delay=args.delay,
        output_prefix=args.prefix
    )


if __name__ == "__main__":
    main()
