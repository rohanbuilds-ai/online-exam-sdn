"""
Performance Metrics and Evaluation Module for Online Examination Network.

Computes:
1. Application Latency: Min, Max, Mean, Median, P95, P99
2. Throughput: Transactions per second, Bytes per second
3. Completion and Success Rates
4. Jain's Fairness Index:
      J = (sum(x_i))^2 / (n * sum(x_i^2))
"""

import math
import time
import json
import csv
from typing import List, Dict, Any, Optional


def compute_percentile(values: List[float], percentile: float) -> float:
    """Calculate the given percentile (0 to 100) using linear interpolation."""
    if not values:
        return 0.0
    sorted_vals = sorted(values)
    k = (len(sorted_vals) - 1) * (percentile / 100.0)
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return float(sorted_vals[int(k)])
    d0 = sorted_vals[int(f)] * (c - k)
    d1 = sorted_vals[int(c)] * (k - f)
    return round(float(d0 + d1), 3)


def calculate_jains_fairness_index(allocations: List[float]) -> float:
    """
    Compute Jain's Fairness Index for resource allocation across n participants.
    Formula:
        J(x_1, x_2, ..., x_n) = (sum_{i=1}^n x_i)^2 / (n * sum_{i=1}^n (x_i^2))
    
    Properties:
    - Bounded between 1/n (worst-case starvation) and 1.0 (perfect equality).
    - Dimensionless and independent of scale.
    """
    n = len(allocations)
    if n <= 1:
        return 1.0

    # Filter negative or NaN values
    clean = [max(0.0, float(x)) for x in allocations]
    total = sum(clean)
    sum_squares = sum(x * x for x in clean)

    if sum_squares == 0.0:
        return 1.0

    j = (total * total) / (n * sum_squares)
    return round(min(1.0, max(0.0, j)), 4)


class MetricsCollector:
    """Collects and aggregates latency, throughput, and completion metrics."""
    def __init__(self):
        self.latencies_ms: List[float] = []
        self.per_client_latencies: Dict[str, List[float]] = {}
        self.per_client_completed: Dict[str, bool] = {}
        self.bytes_transferred: int = 0
        self.start_time: float = time.time()
        self.end_time: Optional[float] = None

    def record_latency(self, student_id: str, latency_ms: float) -> None:
        self.latencies_ms.append(latency_ms)
        if student_id not in self.per_client_latencies:
            self.per_client_latencies[student_id] = []
        self.per_client_latencies[student_id].append(latency_ms)

    def record_bytes(self, num_bytes: int) -> None:
        self.bytes_transferred += num_bytes

    def record_completion(self, student_id: str, success: bool) -> None:
        self.per_client_completed[student_id] = success

    def finish(self) -> None:
        self.end_time = time.time()

    def summarize(self) -> Dict[str, Any]:
        duration = (self.end_time or time.time()) - self.start_time
        total_requests = len(self.latencies_ms)
        avg_latency = round(sum(self.latencies_ms) / total_requests, 3) if total_requests > 0 else 0.0
        p95_latency = compute_percentile(self.latencies_ms, 95.0)
        p99_latency = compute_percentile(self.latencies_ms, 99.0)
        median_latency = compute_percentile(self.latencies_ms, 50.0)
        min_latency = round(min(self.latencies_ms), 3) if total_requests > 0 else 0.0
        max_latency = round(max(self.latencies_ms), 3) if total_requests > 0 else 0.0

        throughput_req = round(total_requests / duration, 2) if duration > 0 else 0.0
        throughput_kbps = round((self.bytes_transferred * 8.0) / (duration * 1000.0), 2) if duration > 0 else 0.0

        total_students = len(self.per_client_completed)
        successful_students = sum(1 for v in self.per_client_completed.values() if v)
        completion_rate = round((successful_students / total_students * 100.0), 2) if total_students > 0 else 100.0

        # Calculate Fairness across per-student service rates (requests / second or inverse avg latency)
        per_client_service_rates = []
        for student_id, lats in self.per_client_latencies.items():
            if lats:
                avg_l = sum(lats) / len(lats)
                # Higher responsiveness = 1000 / avg_l (responses per sec)
                per_client_service_rates.append(1000.0 / avg_l if avg_l > 0 else 1.0)

        fairness = calculate_jains_fairness_index(per_client_service_rates)

        return {
            "total_students": total_students,
            "completed_students": successful_students,
            "completion_rate_percent": completion_rate,
            "total_requests": total_requests,
            "duration_seconds": round(duration, 3),
            "latency_mean_ms": avg_latency,
            "latency_median_ms": median_latency,
            "latency_p95_ms": p95_latency,
            "latency_p99_ms": p99_latency,
            "latency_min_ms": min_latency,
            "latency_max_ms": max_latency,
            "throughput_req_per_sec": throughput_req,
            "throughput_kbps": throughput_kbps,
            "jains_fairness_index": fairness
        }

    def export_csv(self, filepath: str) -> None:
        summary = self.summarize()
        with open(filepath, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["Metric", "Value"])
            for k, v in summary.items():
                writer.writerow([k, v])

    def export_json(self, filepath: str) -> None:
        summary = self.summarize()
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2)
