"""
Unit tests for Performance Metrics and Jain's Fairness Index.
"""

import unittest
from app.metrics import compute_percentile, calculate_jains_fairness_index, MetricsCollector


class TestMetrics(unittest.TestCase):
    def test_percentile_computation(self):
        vals = [10, 20, 30, 40, 50, 60, 70, 80, 90, 100]
        self.assertEqual(compute_percentile(vals, 50), 55.0)
        self.assertEqual(compute_percentile(vals, 0), 10.0)
        self.assertEqual(compute_percentile(vals, 100), 100.0)

    def test_jains_fairness_index_equal_distribution(self):
        # When all participants get identical share, Jain's index must be 1.0
        allocations = [10.0, 10.0, 10.0, 10.0]
        j = calculate_jains_fairness_index(allocations)
        self.assertEqual(j, 1.0)

    def test_jains_fairness_index_unequal_distribution(self):
        # 1 user gets 100, other 3 get 0 -> 1/4 = 0.25
        allocations = [100.0, 0.0, 0.0, 0.0]
        j = calculate_jains_fairness_index(allocations)
        self.assertEqual(j, 0.25)

    def test_metrics_collector(self):
        mc = MetricsCollector()
        mc.record_latency("S1", 15.0)
        mc.record_latency("S1", 25.0)
        mc.record_latency("S2", 20.0)
        mc.record_latency("S2", 20.0)
        mc.record_bytes(5000)
        mc.record_completion("S1", True)
        mc.record_completion("S2", True)
        mc.finish()

        summary = mc.summarize()
        self.assertEqual(summary["total_students"], 2)
        self.assertEqual(summary["completed_students"], 2)
        self.assertEqual(summary["completion_rate_percent"], 100.0)
        self.assertEqual(summary["latency_mean_ms"], 20.0)
        self.assertGreater(summary["jains_fairness_index"], 0.9)


if __name__ == "__main__":
    unittest.main()
