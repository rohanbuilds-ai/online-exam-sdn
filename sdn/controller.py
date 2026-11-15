"""
Complete OpenFlow 1.3 SDN Controller for Online Examination Network.

Integrates:
- Reliable switch connection handling & handshake
- Table-miss rule installation (Priority 0)
- MAC address learning & dynamic L2 forwarding (Priority 100)
- Periodic Multipart Port Statistics collection & traffic rate computation
- Adaptive congestion detection & dynamic QoS flow prioritization (Priority 1000)
"""

import argparse
import json
import logging
import os
import socket
import struct
import sys
import threading
import time
from typing import Dict, Optional, Tuple, Any, Set

from sdn.openflow13 import (
    OFP_VERSION,
    OFPT_HELLO,
    OFPT_ERROR,
    OFPT_ECHO_REQUEST,
    OFPT_FEATURES_REPLY,
    OFPT_PACKET_IN,
    OFPT_MULTIPART_REPLY,
    OFPP_FLOOD,
    pack_hello,
    pack_echo_reply,
    pack_features_request,
    pack_set_config,
    pack_packet_out,
    pack_port_stats_request,
    unpack_port_stats_reply,
    parse_packet_in,
)
from sdn.flow_manager import FlowManager
from sdn.traffic_monitor import TrafficMonitor
from sdn.congestion_manager import CongestionManager, STATE_CONGESTED, STATE_NORMAL

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] [CONTROLLER] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("SDNController")


class SwitchConnection:
    """Represents an active OpenFlow switch connection."""

    def __init__(self, sock: Any, address: Tuple[str, int]):
        self.sock = sock
        self.address = address
        self.mac_to_port: Dict[bytes, int] = {}
        self.ready: bool = False
        self.dpid: Optional[int] = None

    def send(self, data: bytes) -> None:
        """Send raw bytes over the switch socket."""
        self.sock.sendall(data)

    def close(self) -> None:
        """Close the switch socket."""
        try:
            self.sock.close()
        except Exception:
            pass


class SDNController:
    def __init__(
        self,
        host: str = "0.0.0.0",
        port: int = 6653,
        monitor_interval_sec: float = 2.0,
        link_bw_mbps: float = 10.0,
        congestion_threshold: float = 70.0,
        server_mac_str: str = "00:00:00:00:00:01",
        server_port: int = 1,
        stats_interval_sec: Optional[float] = None,
    ):
        self.host = host
        self.port = port
        self.monitor_interval_sec = (
            stats_interval_sec if stats_interval_sec is not None else monitor_interval_sec
        )
        self.stats_interval_sec = self.monitor_interval_sec
        self.link_bw_mbps = link_bw_mbps
        self.congestion_threshold = congestion_threshold
        self.server_mac = bytes.fromhex(server_mac_str.replace(":", ""))
        self.server_port = server_port

        self.server_sock: Optional[socket.socket] = None
        self.is_running = False
        self.connections: Set[SwitchConnection] = set()
        self.switch_conns: Dict[Any, socket.socket] = {}
        self.mac_tables: Dict[Any, Dict[bytes, int]] = {}
        self.xid_counter = 1
        self._lock = threading.Lock()

        # Traffic Monitor & Adaptive Congestion Manager
        self.traffic_monitor = TrafficMonitor(link_bandwidth_mbps=self.link_bw_mbps)
        self.congestion_manager = CongestionManager(
            server_port=self.server_port,
            congestion_threshold_percent=self.congestion_threshold,
            on_policy_change=self._on_policy_change,
        )

        self._monitor_thread: Optional[threading.Thread] = None

    def _get_next_xid(self) -> int:
        with self._lock:
            self.xid_counter += 1
            return self.xid_counter

    def start(self, blocking: bool = True) -> None:
        """Start the OpenFlow controller socket listener."""
        self.server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_sock.bind((self.host, self.port))
        self.server_sock.listen(10)
        self.server_sock.settimeout(1.0)
        self.is_running = True

        logger.info(f"OpenFlow 1.3 SDN Controller listening on {self.host}:{self.port}")
        logger.info(
            f"Dynamic Congestion Threshold: {self.congestion_threshold}% link capacity ({self.link_bw_mbps} Mbps)"
        )

        # Start periodic traffic monitoring thread
        self._monitor_thread = threading.Thread(target=self._periodic_monitor_loop, daemon=True)
        self._monitor_thread.start()

        if blocking:
            self._listen_loop()
        else:
            t = threading.Thread(target=self._listen_loop, daemon=True)
            t.start()

    def stop(self) -> None:
        self.is_running = False
        if self.server_sock:
            try:
                self.server_sock.close()
            except Exception:
                pass
        with self._lock:
            for conn in list(self.connections):
                conn.close()
            self.connections.clear()
            self.switch_conns.clear()
            self.mac_tables.clear()
        logger.info("SDN Controller stopped.")

    def _listen_loop(self) -> None:
        while self.is_running:
            try:
                conn_sock, addr = self.server_sock.accept()
                t = threading.Thread(target=self._handle_switch, args=(conn_sock, addr), daemon=True)
                t.start()
            except (socket.timeout, TimeoutError):
                continue
            except OSError:
                break

    def _receive_exact(self, conn: socket.socket, num_bytes: int) -> Optional[bytes]:
        data = bytearray()
        while len(data) < num_bytes:
            try:
                chunk = conn.recv(num_bytes - len(data))
            except (socket.timeout, TimeoutError):
                continue
            except (OSError, ConnectionError):
                return None
            if not chunk:
                return None
            data.extend(chunk)
        return bytes(data)

    def _handle_switch(self, conn_sock: socket.socket, address: Tuple[str, int]) -> None:
        logger.info(f"Switch connected from {address}")
        conn_sock.settimeout(1.0)
        conn = SwitchConnection(conn_sock, address)
        with self._lock:
            self.connections.add(conn)
            self.switch_conns[address] = conn_sock
            self.mac_tables[address] = conn.mac_to_port

        # Controller sends initial OFPT_HELLO upon connection establishment
        try:
            conn.send(pack_hello(self._get_next_xid()))
        except Exception as err:
            logger.warning(f"Failed to send initial HELLO to {address}: {err}")

        try:
            while self.is_running:
                header = self._receive_exact(conn_sock, 8)
                if not header:
                    break

                version, msg_type, length, rx_xid = struct.unpack("!BBHI", header)
                if version != OFP_VERSION:
                    logger.error(f"Unsupported OpenFlow version {version} from {address}")
                    break

                body_len = length - 8
                body = self._receive_exact(conn_sock, body_len) if body_len > 0 else b""
                if body is None:
                    break

                self._handle_message(conn, msg_type, rx_xid, body)

        except Exception as err:
            logger.warning(f"Switch connection handler error ({address}): {err}")
        finally:
            with self._lock:
                self.connections.discard(conn)
                self.switch_conns.pop(address, None)
                self.mac_tables.pop(address, None)
            conn.close()
            logger.info(f"Switch disconnected from {address}")

    def _handle_message(
        self,
        conn: SwitchConnection,
        msg_type: int,
        rx_xid: int,
        body: bytes,
    ) -> None:
        """Dispatch received OpenFlow message to the appropriate handler."""
        # 1. OFPT_HELLO
        if msg_type == OFPT_HELLO:
            logger.info(f"Received OFPT_HELLO from switch {conn.address}")
            conn.send(pack_features_request(self._get_next_xid()))

        # 2. OFPT_ECHO_REQUEST
        elif msg_type == OFPT_ECHO_REQUEST:
            conn.send(pack_echo_reply(rx_xid, body))

        # 3. OFPT_FEATURES_REPLY
        elif msg_type == OFPT_FEATURES_REPLY:
            self._handle_features_reply(conn, body)

        # 4. OFPT_PACKET_IN
        elif msg_type == OFPT_PACKET_IN:
            self._handle_packet_in(conn, body)

        # 5. OFPT_MULTIPART_REPLY (Port Statistics)
        elif msg_type == OFPT_MULTIPART_REPLY:
            self._handle_multipart_reply(conn, body)

        # 6. OFPT_ERROR
        elif msg_type == OFPT_ERROR:
            logger.warning(f"Switch {conn.address} sent OpenFlow error: {body.hex()}")

    def _handle_features_reply(self, conn: SwitchConnection, body: bytes) -> None:
        """Handle OFPT_FEATURES_REPLY: configure switch, table miss rule, and start stats."""
        logger.info(f"Received OFPT_FEATURES_REPLY from switch {conn.address}")
        if len(body) >= 8:
            conn.dpid = struct.unpack("!Q", body[:8])[0]
        conn.ready = True

        # 1. Set Config (OFPT_SET_CONFIG, msg_type 9)
        conn.send(pack_set_config(self._get_next_xid()))

        # 2. Install Table-Miss Flow Rule (Priority 0 -> Controller)
        table_miss_msg = FlowManager.create_table_miss_rule(self._get_next_xid())
        conn.send(table_miss_msg)
        logger.info(f"Installed Table-Miss Rule (Priority 0) on switch {conn.address} (DPID={conn.dpid})")

        # 3. Request initial Port Statistics
        conn.send(pack_port_stats_request(self._get_next_xid()))

    def _handle_packet_in(self, conn: SwitchConnection, body: bytes) -> None:
        """Handle OFPT_PACKET_IN: learn source MAC, install flow rule if known, or flood."""
        pkt_info = parse_packet_in(body)
        if not pkt_info:
            return

        buffer_id, in_port, src_mac, dst_mac, packet = pkt_info
        conn.mac_to_port[src_mac] = in_port

        src_str = src_mac.hex(":")
        dst_str = dst_mac.hex(":")

        if dst_mac in conn.mac_to_port and conn.mac_to_port[dst_mac] != in_port:
            out_port = conn.mac_to_port[dst_mac]

            # If dynamic QoS is congested and this is exam traffic, install priority rule
            if self.congestion_manager.current_state == STATE_CONGESTED and (
                dst_mac == self.server_mac or src_mac == self.server_mac
            ):
                is_ingress = dst_mac == self.server_mac
                flow_msg = FlowManager.create_exam_qos_rule(
                    xid=self._get_next_xid(),
                    dst_mac=dst_mac,
                    out_port=out_port,
                    queue_id=1,  # Dedicated High Priority Queue
                    priority=1000,
                    is_server_ingress=is_ingress,
                )
                logger.info(
                    f"[DYNAMIC SDN FLOW] Installed High-Priority QoS Flow for Exam Traffic ({dst_str} -> Port {out_port}, Queue 1)"
                )
            else:
                flow_msg = FlowManager.create_l2_forwarding_rule(
                    xid=self._get_next_xid(),
                    dst_mac=dst_mac,
                    out_port=out_port,
                    priority=100,
                )
                logger.info(f"[L2 FORWARDING] Learned {dst_str} -> Port {out_port}")

            conn.send(flow_msg)
            conn.send(pack_packet_out(self._get_next_xid(), packet, out_port, in_port=in_port))
        else:
            # Flood unknown destination
            conn.send(pack_packet_out(self._get_next_xid(), packet, OFPP_FLOOD, in_port=in_port))

    def _handle_multipart_reply(self, conn: SwitchConnection, body: bytes) -> None:
        """Handle OFPT_MULTIPART_REPLY: extract port statistics and evaluate congestion."""
        entries = unpack_port_stats_reply(body)
        if entries:
            updated_metrics = self.traffic_monitor.update_port_stats(entries)
            self.congestion_manager.evaluate_network_conditions(updated_metrics)

    def _process_packet_in(self, conn: Any, address: Any, body: bytes) -> None:
        """Backward-compatibility wrapper for packet_in processing."""
        if isinstance(conn, SwitchConnection):
            self._handle_packet_in(conn, body)
        else:
            match_conn = next((c for c in self.connections if c.address == address), None)
            if not match_conn:
                match_conn = SwitchConnection(conn, address)
                if address in self.mac_tables:
                    match_conn.mac_to_port = self.mac_tables[address]
            self._handle_packet_in(match_conn, body)

    def _export_telemetry_snapshot(self) -> None:
        """Export telemetry snapshot to results/sdn_telemetry_snapshot.json for web gateway."""
        try:
            results_dir = os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "results"
            )
            os.makedirs(results_dir, exist_ok=True)
            snapshot_path = os.path.join(results_dir, "sdn_telemetry_snapshot.json")
            with self._lock:
                switches_data = [
                    {
                        "dpid": getattr(c, "dpid", None),
                        "address": list(getattr(c, "address", ())),
                        "ready": getattr(c, "ready", False),
                    }
                    for c in self.connections
                ]

            port_metrics = []
            if hasattr(self.traffic_monitor, "port_metrics"):
                port_metrics = list(self.traffic_monitor.port_metrics.values())

            data = {
                "controller_connected": True,
                "switch_count": len(self.connections),
                "switches": switches_data,
                "port_stats": port_metrics,
                "congestion_state": self.congestion_manager.current_state,
                "policy_active": self.congestion_manager.current_state == STATE_CONGESTED,
                "queue_assignment": (
                    1 if self.congestion_manager.current_state == STATE_CONGESTED else 0
                ),
                "policy_events": self.congestion_manager.get_decision_history(),
                "timestamp": time.time(),
            }
            tmp_path = snapshot_path + ".tmp"
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(data, f)
            os.replace(tmp_path, snapshot_path)
        except Exception:
            pass

    def _periodic_monitor_loop(self) -> None:
        """Poll switches for port statistics on every monitor interval."""
        while self.is_running:
            time.sleep(self.monitor_interval_sec)
            with self._lock:
                conns = [c for c in self.connections if getattr(c, "ready", True)]

            for conn in conns:
                try:
                    req = pack_port_stats_request(self._get_next_xid())
                    conn.send(req)
                except Exception:
                    pass
            self._export_telemetry_snapshot()

    def _on_policy_change(self, new_state: str, bottleneck_port: int) -> None:
        """Invoked when CongestionManager changes state."""
        with self._lock:
            conns = [c for c in self.connections if getattr(c, "ready", True)]

        if new_state == STATE_CONGESTED:
            logger.warning(
                f"*** TRIGGERING ADAPTIVE SDN POLICY: CONGESTION DETECTED ON PORT {bottleneck_port} ***"
            )
            for conn in conns:
                # Install high-priority rules for exam traffic to use Queue 1
                rule_in = FlowManager.create_exam_qos_rule(
                    xid=self._get_next_xid(),
                    dst_mac=self.server_mac,
                    out_port=self.server_port,
                    queue_id=1,
                    priority=1000,
                    is_server_ingress=True,
                )
                try:
                    conn.send(rule_in)
                    logger.info("Dynamically prioritized incoming Examination TCP Traffic to Queue 1.")
                except Exception:
                    pass

        elif new_state == STATE_NORMAL:
            logger.info(f"*** SDN POLICY RESTORED: TRAFFIC NORMALIZED ON PORT {bottleneck_port} ***")
            for conn in conns:
                # Revert exam traffic to standard Queue 0
                rule_normal = FlowManager.modify_exam_queue(
                    xid=self._get_next_xid(),
                    dst_mac=self.server_mac,
                    out_port=self.server_port,
                    new_queue_id=0,
                    priority=1000,
                    is_server_ingress=True,
                )
                try:
                    conn.send(rule_normal)
                    logger.info("Reverted Examination TCP Traffic to standard Best-Effort Queue 0.")
                except Exception:
                    pass

        self._export_telemetry_snapshot()

    _apply_sdn_policy = _on_policy_change


def main():
    parser = argparse.ArgumentParser(
        description="SDN OpenFlow 1.3 Controller with Dynamic Congestion Prioritization"
    )
    parser.add_argument("--host", default="0.0.0.0", help="Listen host (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=6653, help="Listen port (default: 6653)")
    parser.add_argument("--bw", type=float, default=10.0, help="Link bandwidth in Mbps (default: 10.0)")
    parser.add_argument("--threshold", type=float, default=70.0, help="Congestion threshold %% (default: 70.0)")
    parser.add_argument(
        "--interval", type=float, default=2.0, help="Monitoring polling interval in seconds"
    )
    args = parser.parse_args()

    controller = SDNController(
        host=args.host,
        port=args.port,
        link_bw_mbps=args.bw,
        congestion_threshold=args.threshold,
        monitor_interval_sec=args.interval,
    )

    try:
        controller.start(blocking=True)
    except KeyboardInterrupt:
        logger.info("Shutting down controller...")
        controller.stop()
        sys.exit(0)


if __name__ == "__main__":
    main()
