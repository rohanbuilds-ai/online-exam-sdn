"""
Unit tests for Traffic Monitor and Adaptive Congestion Manager.
"""

import time
import unittest
from sdn.traffic_monitor import TrafficMonitor
from sdn.congestion_manager import CongestionManager, STATE_NORMAL, STATE_CONGESTED


class TestCongestionControl(unittest.TestCase):
    def test_traffic_monitor_rate_computation(self):
        monitor = TrafficMonitor(link_bandwidth_mbps=10.0)

        # Snapshot 1 at t=0
        entry1 = [{
            "port_no": 1,
            "rx_packets": 100,
            "tx_packets": 200,
            "rx_bytes": 10000,
            "tx_bytes": 20000,
            "rx_dropped": 0,
            "tx_dropped": 0,
            "rx_errors": 0,
            "tx_errors": 0,
            "duration_sec": 1,
            "duration_nsec": 0
        }]
        res1 = monitor.update_port_stats(entry1)
        self.assertEqual(len(res1), 0)  # Need 2 snapshots for rate

        # Snapshot 2 after 1 second (transferred 1,000,000 bytes tx = 8 Mbps)
        time.sleep(0.1)  # small delay
        entry2 = [{
            "port_no": 1,
            "rx_packets": 200,
            "tx_packets": 1200,
            "rx_bytes": 10000,
            "tx_bytes": 120000,  # +100,000 bytes
            "rx_dropped": 0,
            "tx_dropped": 0,
            "rx_errors": 0,
            "tx_errors": 0,
            "duration_sec": 2,
            "duration_nsec": 0
        }]
        res2 = monitor.update_port_stats(entry2)
        self.assertIn(1, res2)
        m = res2[1]
        self.assertGreater(m["tx_rate_mbps"], 0.0)
        self.assertGreater(m["utilization_percent"], 0.0)

    def test_congestion_manager_state_transition(self):
        policy_triggers = []

        def on_policy(state, port):
            policy_triggers.append((state, port))

        cm = CongestionManager(
            server_port=1,
            congestion_threshold_percent=70.0,
            recovery_threshold_percent=30.0,
            cooldown_period_sec=0.1,
            on_policy_change=on_policy
        )

        self.assertEqual(cm.current_state, STATE_NORMAL)

        # 1. Low utilization (20%) -> stays NORMAL
        metrics_low = {1: {"port_no": 1, "utilization_percent": 20.0}}
        dec1 = cm.evaluate_network_conditions(metrics_low)
        self.assertIsNone(dec1)
        self.assertEqual(cm.current_state, STATE_NORMAL)

        # 2. High utilization (85%) -> triggers CONGESTED
        metrics_high = {1: {"port_no": 1, "utilization_percent": 85.0}}
        dec2 = cm.evaluate_network_conditions(metrics_high)
        self.assertIsNotNone(dec2)
        self.assertEqual(cm.current_state, STATE_CONGESTED)
        self.assertEqual(len(policy_triggers), 1)
        self.assertEqual(policy_triggers[0], (STATE_CONGESTED, 1))

        # 3. Drops to 25% after cooldown -> restores NORMAL
        time.sleep(0.15)
        metrics_recovered = {1: {"port_no": 1, "utilization_percent": 25.0}}
        dec3 = cm.evaluate_network_conditions(metrics_recovered)
        self.assertIsNotNone(dec3)
        self.assertEqual(cm.current_state, STATE_NORMAL)
        self.assertEqual(len(policy_triggers), 2)
        self.assertEqual(policy_triggers[1], (STATE_NORMAL, 1))


if __name__ == "__main__":
    unittest.main()
