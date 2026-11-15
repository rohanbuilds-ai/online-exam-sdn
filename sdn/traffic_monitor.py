"""
SDN Network Traffic and Port Statistics Monitor.

Periodically queries Open vSwitch ports using OpenFlow 1.3 Multipart Port Stats requests.
Calculates byte rates, packet rates, link utilization percentages, and packet loss.
"""

import time
import threading
from typing import Dict, List, Any, Optional, Tuple


class PortStatSnapshot:
    def __init__(self, port_no: int, rx_bytes: int, tx_bytes: int, rx_packets: int, tx_packets: int, rx_dropped: int, tx_dropped: int, timestamp: float):
        self.port_no = port_no
        self.rx_bytes = rx_bytes
        self.tx_bytes = tx_bytes
        self.rx_packets = rx_packets
        self.tx_packets = tx_packets
        self.rx_dropped = rx_dropped
        self.tx_dropped = tx_dropped
        self.timestamp = timestamp


class TrafficMonitor:
    def __init__(self, link_bandwidth_mbps: float = 10.0):
        self.link_bandwidth_mbps = link_bandwidth_mbps
        self.link_bandwidth_bps = link_bandwidth_mbps * 1_000_000.0
        self.port_history: Dict[int, List[PortStatSnapshot]] = {}
        self.current_metrics: Dict[int, Dict[str, Any]] = {}
        self._lock = threading.Lock()

    def update_port_stats(self, port_stats_list: List[Dict[str, Any]]) -> Dict[int, Dict[str, Any]]:
        """Process incoming OFPMP_PORT_STATS reply entries and compute rates."""
        now = time.time()
        updated = {}

        with self._lock:
            for entry in port_stats_list:
                port_no = entry["port_no"]
                rx_bytes = entry["rx_bytes"]
                tx_bytes = entry["tx_bytes"]
                rx_pkts = entry["rx_packets"]
                tx_pkts = entry["tx_packets"]
                rx_drops = entry["rx_dropped"]
                tx_drops = entry["tx_dropped"]

                snapshot = PortStatSnapshot(
                    port_no=port_no,
                    rx_bytes=rx_bytes,
                    tx_bytes=tx_bytes,
                    rx_packets=rx_pkts,
                    tx_packets=tx_pkts,
                    rx_dropped=rx_drops,
                    tx_dropped=tx_drops,
                    timestamp=now
                )

                if port_no not in self.port_history:
                    self.port_history[port_no] = []

                history = self.port_history[port_no]
                history.append(snapshot)
                if len(history) > 10:
                    history.pop(0)

                # Compute delta if at least 2 snapshots exist
                if len(history) >= 2:
                    prev = history[-2]
                    dt = max(0.001, snapshot.timestamp - prev.timestamp)

                    delta_tx_bytes = max(0, snapshot.tx_bytes - prev.tx_bytes)
                    delta_rx_bytes = max(0, snapshot.rx_bytes - prev.rx_bytes)
                    total_bytes = delta_tx_bytes + delta_rx_bytes

                    tx_rate_bps = (delta_tx_bytes * 8.0) / dt
                    rx_rate_bps = (delta_rx_bytes * 8.0) / dt
                    total_rate_bps = (total_bytes * 8.0) / dt
                    tx_rate_mbps = tx_rate_bps / 1_000_000.0

                    delta_tx_pkts = max(0, snapshot.tx_packets - prev.tx_packets)
                    delta_rx_pkts = max(0, snapshot.rx_packets - prev.rx_packets)
                    pkt_rate = (delta_tx_pkts + delta_rx_pkts) / dt

                    delta_drops = max(0, snapshot.tx_dropped - prev.tx_dropped) + max(0, snapshot.rx_dropped - prev.rx_dropped)
                    drop_rate = delta_drops / dt

                    # Link utilization based on capacity
                    utilization_percent = min(100.0, (tx_rate_bps / self.link_bandwidth_bps) * 100.0)

                    metrics = {
                        "port_no": port_no,
                        "timestamp": now,
                        "tx_rate_mbps": round(tx_rate_mbps, 3),
                        "total_rate_mbps": round(total_rate_bps / 1_000_000.0, 3),
                        "packet_rate_pps": round(pkt_rate, 1),
                        "drop_rate_pps": round(drop_rate, 2),
                        "utilization_percent": round(utilization_percent, 2),
                        "total_tx_bytes": snapshot.tx_bytes,
                        "total_rx_bytes": snapshot.rx_bytes,
                        "total_drops": snapshot.tx_dropped + snapshot.rx_dropped
                    }
                    self.current_metrics[port_no] = metrics
                    updated[port_no] = metrics

        return updated

    def get_port_metrics(self, port_no: int) -> Optional[Dict[str, Any]]:
        with self._lock:
            return self.current_metrics.get(port_no)

    def get_all_metrics(self) -> Dict[int, Dict[str, Any]]:
        with self._lock:
            return dict(self.current_metrics)
