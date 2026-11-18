#!/usr/bin/env python3
"""A small, dependency-free OpenFlow 1.3 controller for the exam network.

Supports one or more OpenFlow switches, L2 MAC learning, periodic port-stat
polling, and congestion-triggered prioritization of TCP/5000 traffic to the
configured examination server.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import signal
import socket
import struct
import sys
import threading
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple

# Allow both `python -m sdn.controller` and `python sdn/controller.py`.
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from sdn.congestion_manager import (  # noqa: E402
    CongestionManager,
    STATE_CONGESTED,
    STATE_NORMAL,
)
from sdn.flow_manager import FlowManager  # noqa: E402
from sdn.openflow13 import (  # noqa: E402
    OFP_NO_BUFFER,
    OFP_VERSION,
    OFPP_FLOOD,
    OFPT_ECHO_REQUEST,
    OFPT_FEATURES_REPLY,
    OFPT_HELLO,
    OFPT_MULTIPART_REPLY,
    OFPT_PACKET_IN,
    OFPT_PORT_STATUS,
    OFPMP_PORT_STATS,
    pack_echo_reply,
    pack_features_request,
    pack_header,
    pack_hello,
    pack_packet_out,
    pack_port_stats_request,
    pack_set_config,
    unpack_header,
    unpack_port_stats_reply,
)
from sdn.traffic_monitor import TrafficMonitor  # noqa: E402

LOG = logging.getLogger("SDNController")
OFPMPF_REPLY_MORE = 1


def _recv_exact(sock: socket.socket, size: int) -> Optional[bytes]:
    """Read exactly size bytes; return None on a clean/partial disconnect."""
    chunks = bytearray()
    while len(chunks) < size:
        try:
            part = sock.recv(size - len(chunks))
        except InterruptedError:
            continue
        if not part:
            return None
        chunks.extend(part)
    return bytes(chunks)


def _parse_mac(value: str) -> bytes:
    try:
        result = bytes.fromhex(value.replace(":", "").replace("-", ""))
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"Invalid MAC address: {value}") from exc
    if len(result) != 6:
        raise argparse.ArgumentTypeError("MAC address must contain exactly 6 bytes")
    return result


@dataclass(eq=False)
class SwitchConnection:
    sock: socket.socket
    address: Tuple[str, int]
    send_lock: threading.Lock = field(default_factory=threading.Lock)
    xid_lock: threading.Lock = field(default_factory=threading.Lock)
    next_xid: int = 1
    dpid: Optional[int] = None
    n_buffers: int = 0
    n_tables: int = 0
    ready: bool = False
    hello_received: bool = False
    closed: bool = False
    mac_to_port: Dict[bytes, int] = field(default_factory=dict)
    multipart_port_stats: Dict[int, List[dict]] = field(default_factory=dict)
    thread: Optional[threading.Thread] = None

    def allocate_xid(self) -> int:
        with self.xid_lock:
            xid = self.next_xid
            self.next_xid = (self.next_xid + 1) & 0xFFFFFFFF
            if self.next_xid == 0:
                self.next_xid = 1
            return xid


class SDNController:
    """OpenFlow listener and policy coordinator for the examination network."""

    def __init__(
        self,
        host: str = "0.0.0.0",
        port: int = 6653,
        link_bandwidth_mbps: float = 10.0,
        congestion_threshold_percent: float = 70.0,
        recovery_threshold_percent: float = 35.0,
        cooldown_period_sec: float = 4.0,
        stats_interval_sec: float = 2.0,
        server_port: int = 1,
        server_mac: bytes = bytes.fromhex("000000000001"),
    ) -> None:
        if not (1 <= port <= 65535):
            raise ValueError("Controller TCP port must be between 1 and 65535")
        if link_bandwidth_mbps <= 0:
            raise ValueError("Link bandwidth must be positive")
        if stats_interval_sec <= 0:
            raise ValueError("Statistics interval must be positive")
        if len(server_mac) != 6:
            raise ValueError("Server MAC address must be exactly 6 bytes")

        self.host = host
        self.port = port
        self.server_port = server_port
        self.server_mac = server_mac
        self.stats_interval_sec = stats_interval_sec

        self.stop_event = threading.Event()
        self.listener: Optional[socket.socket] = None
        self.connections: Set[SwitchConnection] = set()
        self.connections_lock = threading.RLock()
        self.stats_thread: Optional[threading.Thread] = None

        self.traffic_monitor = TrafficMonitor(link_bandwidth_mbps=link_bandwidth_mbps)
        self.congestion_manager = CongestionManager(
            server_port=server_port,
            congestion_threshold_percent=congestion_threshold_percent,
            recovery_threshold_percent=recovery_threshold_percent,
            cooldown_period_sec=cooldown_period_sec,
            on_policy_change=self._on_policy_change,
        )

    def _send(self, conn: SwitchConnection, message: bytes) -> bool:
        if conn.closed:
            return False
        try:
            with conn.send_lock:
                if conn.closed:
                    return False
                conn.sock.sendall(message)
            return True
        except (OSError, ConnectionError) as exc:
            LOG.warning("Send to switch %s failed: %s", conn.address, exc)
            self._drop_connection(conn)
            return False

    def _send_features_request(self, conn: SwitchConnection) -> None:
        self._send(conn, pack_features_request(conn.allocate_xid()))

    def _send_port_stats_request(self, conn: SwitchConnection) -> None:
        if conn.ready and not conn.closed:
            self._send(conn, pack_port_stats_request(conn.allocate_xid()))

    def _drop_connection(self, conn: SwitchConnection) -> None:
        with self.connections_lock:
            if conn.closed:
                return
            conn.closed = True
            conn.ready = False
            self.connections.discard(conn)
        try:
            conn.sock.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        try:
            conn.sock.close()
        except OSError:
            pass
        LOG.info("Switch disconnected: %s (DPID=%s)", conn.address, conn.dpid)

    def serve_forever(self) -> None:
        """Bind the OpenFlow TCP port and serve switch connections."""
        listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        listener.bind((self.host, self.port))
        listener.listen(16)
        listener.settimeout(0.5)
        self.listener = listener

        LOG.info("OpenFlow 1.3 controller listening on %s:%d", self.host, self.port)
        self.stats_thread = threading.Thread(
            target=self._statistics_loop, name="port-statistics-poller", daemon=True
        )
        self.stats_thread.start()

        try:
            while not self.stop_event.is_set():
                try:
                    peer, address = listener.accept()
                except socket.timeout:
                    continue
                except OSError:
                    if self.stop_event.is_set():
                        break
                    raise

                peer.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                conn = SwitchConnection(sock=peer, address=address)
                with self.connections_lock:
                    self.connections.add(conn)

                LOG.info("Switch connected from %s:%d", *address)
                # Send our hello immediately; request features after the peer's hello.
                if self._send(conn, pack_hello(conn.allocate_xid())):
                    conn.thread = threading.Thread(
                        target=self._connection_loop,
                        args=(conn,),
                        name=f"openflow-{address[0]}-{address[1]}",
                        daemon=True,
                    )
                    conn.thread.start()
        finally:
            self.stop()

    def stop(self) -> None:
        self.stop_event.set()
        if self.listener is not None:
            try:
                self.listener.close()
            except OSError:
                pass
            self.listener = None

        with self.connections_lock:
            peers = list(self.connections)
        for conn in peers:
            self._drop_connection(conn)

        if self.stats_thread and self.stats_thread is not threading.current_thread():
            self.stats_thread.join(timeout=2.0)

    def _connection_loop(self, conn: SwitchConnection) -> None:
        try:
            while not self.stop_event.is_set() and not conn.closed:
                header = _recv_exact(conn.sock, 8)
                if header is None:
                    break
                try:
                    version, msg_type, length, xid = unpack_header(header)
                except struct.error:
                    LOG.warning("Malformed OpenFlow header from %s", conn.address)
                    break

                if version != OFP_VERSION:
                    LOG.warning(
                        "Rejecting %s: OpenFlow version %d received; expected 1.3 (wire version 4)",
                        conn.address,
                        version,
                    )
                    break
                if length < 8 or length > 65535:
                    LOG.warning("Invalid OpenFlow message length %d from %s", length, conn.address)
                    break

                body = _recv_exact(conn.sock, length - 8)
                if body is None:
                    break
                self._handle_message(conn, msg_type, xid, body)
        except (OSError, ConnectionError) as exc:
            if not conn.closed and not self.stop_event.is_set():
                LOG.info("Connection %s ended: %s", conn.address, exc)
        finally:
            self._drop_connection(conn)

    def _handle_message(self, conn: SwitchConnection, msg_type: int, xid: int, body: bytes) -> None:
        if msg_type == OFPT_HELLO:
            if not conn.hello_received:
                conn.hello_received = True
                LOG.info("OpenFlow 1.3 hello received from %s", conn.address)
                self._send_features_request(conn)
            return

        if msg_type == OFPT_ECHO_REQUEST:
            self._send(conn, pack_echo_reply(xid=xid, payload=body))
            return

        if msg_type == OFPT_FEATURES_REPLY:
            self._handle_features_reply(conn, body)
            return

        if msg_type == OFPT_PACKET_IN:
            self._handle_packet_in(conn, body)
            return

        if msg_type == OFPT_MULTIPART_REPLY:
            self._handle_multipart_reply(conn, xid, body)
            return

        if msg_type == OFPT_PORT_STATUS:
            LOG.info("Port status event from DPID=%s: %s", conn.dpid, body.hex())
            return

        # FLOW_REMOVED, BARRIER_REPLY and other asynchronous notifications are
        # intentionally harmless to ignore for this topology.
        if msg_type == 1:  # OFPT_ERROR
            LOG.error("OpenFlow error from DPID=%s (xid=%d): %s", conn.dpid, xid, body.hex())

    def _handle_features_reply(self, conn: SwitchConnection, body: bytes) -> None:
        # ofp_switch_features is 24 bytes in OpenFlow 1.3.
        if len(body) < 24:
            LOG.error("Short features reply from %s (%d bytes)", conn.address, len(body))
            return
        dpid, n_buffers, n_tables, _aux_id, capabilities, _reserved = struct.unpack(
            "!QIBB2xII", body[:24]
        )
        conn.dpid = dpid
        conn.n_buffers = n_buffers
        conn.n_tables = n_tables
        conn.ready = True

        LOG.info(
            "Switch ready: DPID=%016x buffers=%d tables=%d capabilities=0x%x",
            dpid,
            n_buffers,
            n_tables,
            capabilities,
        )
        # Ask the switch to send complete packet-in frames, then install table miss.
        self._send(conn, pack_set_config(conn.allocate_xid(), miss_send_len=65535))
        table_miss = FlowManager.create_table_miss_rule(conn.allocate_xid())
        self._send(conn, table_miss)
        self._send_port_stats_request(conn)
        LOG.info("Installed table-miss rule on DPID=%016x", dpid)

    def _handle_packet_in(self, conn: SwitchConnection, body: bytes) -> None:
        # parse_packet_in returns (buffer_id, in_port, src_mac, dst_mac, frame).
        from sdn.openflow13 import parse_packet_in

        parsed = parse_packet_in(body)
        if parsed is None:
            LOG.debug("Ignoring unparseable packet-in from DPID=%s", conn.dpid)
            return

        buffer_id, in_port, src_mac, dst_mac, frame = parsed
        if len(src_mac) != 6 or len(dst_mac) != 6:
            return

        # Learn source MAC -> ingress port. A host move updates the mapping.
        old_port = conn.mac_to_port.get(src_mac)
        conn.mac_to_port[src_mac] = in_port
        if old_port is not None and old_port != in_port:
            LOG.info(
                "MAC %s moved from port %d to port %d on DPID=%s",
                src_mac.hex(":"), old_port, in_port, conn.dpid
            )

        # Broadcast and multicast destinations must be flooded. Unknown unicast
        # is also flooded until its destination MAC has been learned.
        if (dst_mac[0] & 1) or dst_mac not in conn.mac_to_port:
            out_port = OFPP_FLOOD
        else:
            out_port = conn.mac_to_port[dst_mac]

        if out_port == in_port:
            LOG.debug("Dropping packet whose destination is on ingress port %d", in_port)
            return

        if out_port != OFPP_FLOOD:
            flow = FlowManager.create_l2_forwarding_rule(
                xid=conn.allocate_xid(), dst_mac=dst_mac, out_port=out_port
            )
            self._send(conn, flow)

        # If the switch retained the packet, refer to its buffer and omit packet
        # bytes; otherwise include the complete frame in PACKET_OUT.
        packet_data = b"" if buffer_id != OFP_NO_BUFFER else frame
        packet_out = pack_packet_out(
            xid=conn.allocate_xid(),
            packet=packet_data,
            out_port=out_port,
            in_port=in_port,
            buffer_id=buffer_id,
        )
        self._send(conn, packet_out)

    def _handle_multipart_reply(self, conn: SwitchConnection, xid: int, body: bytes) -> None:
        if len(body) < 8:
            return
        mp_type, flags = struct.unpack("!HH", body[:4])
        if mp_type != OFPMP_PORT_STATS:
            return

        entries = unpack_port_stats_reply(body)
        pending = conn.multipart_port_stats.setdefault(xid, [])
        pending.extend(entries)
        if flags & OFPMPF_REPLY_MORE:
            return

        complete_entries = conn.multipart_port_stats.pop(xid, pending)
        metrics = self.traffic_monitor.update_port_stats(complete_entries)
        if metrics:
            LOG.debug("Updated port telemetry: %s", metrics)
            self.congestion_manager.evaluate_network_conditions(metrics)
            self._export_telemetry_snapshot()

    def _statistics_loop(self) -> None:
        while not self.stop_event.wait(self.stats_interval_sec):
            with self.connections_lock:
                peers = list(self.connections)
            for conn in peers:
                if conn.ready and not conn.closed:
                    self._send_port_stats_request(conn)
            self._export_telemetry_snapshot()


    def _export_telemetry_snapshot(self) -> None:
        """Atomically publish real controller and OVS telemetry for the web API."""
        try:
            project_root = os.path.dirname(
                os.path.dirname(os.path.abspath(__file__))
            )
            snapshot_path = os.environ.get(
                "SDN_TELEMETRY_SNAPSHOT",
                os.path.join(
                    project_root, "results", "sdn_telemetry_snapshot.json"
                ),
            )

            controller_connected = (
                self.listener is not None and not self.stop_event.is_set()
            )

            with self.connections_lock:
                peers = list(self.connections)
                switches = [
                    {
                        "dpid": (
                            f"{conn.dpid:016x}"
                            if conn.dpid is not None else None
                        ),
                        "address": list(conn.address),
                        "ready": bool(conn.ready and not conn.closed),
                    }
                    for conn in peers
                ]

            state = self.congestion_manager.current_state
            metrics = self.traffic_monitor.get_all_metrics()

            snapshot = {
                "controller_connected": controller_connected,
                "switch_count": sum(1 for s in switches if s["ready"]),
                "switches": switches,
                "port_stats": sorted(
                    metrics.values(),
                    key=lambda item: item.get("port_no", 0),
                ),
                "congestion_state": (
                    state if controller_connected else "DISCONNECTED"
                ),
                "policy_active": (
                    controller_connected and state == STATE_CONGESTED
                ),
                "queue_assignment": (
                    (1 if state == STATE_CONGESTED else 0)
                    if controller_connected else None
                ),
                "policy_events": self.congestion_manager.get_decision_history()[
                    -20:
                ],
                "timestamp": time.time(),
            }

            directory = os.path.dirname(snapshot_path) or "."
            os.makedirs(directory, exist_ok=True)

            temporary_path = f"{snapshot_path}.{os.getpid()}.{threading.get_ident()}.tmp"
            with open(temporary_path, "w", encoding="utf-8") as handle:
                json.dump(snapshot, handle)
                handle.flush()
                os.fsync(handle.fileno())

            os.replace(temporary_path, snapshot_path)

        except Exception:
            LOG.exception("Failed to export SDN telemetry snapshot")

    def _on_policy_change(self, state: str, port_no: int) -> None:
        """Install the queue policy on the server-facing switch port."""
        if port_no != self.server_port:
            LOG.warning(
                "Congestion reported on port %d, but exam server is configured on port %d; "
                "no exam QoS rule installed",
                port_no,
                self.server_port,
            )
            return

        with self.connections_lock:
            peers = [c for c in self.connections if c.ready and not c.closed]

        queue_id = 1 if state == STATE_CONGESTED else 0
        installed = 0
        for conn in peers:
            xid = conn.allocate_xid()
            if state == STATE_CONGESTED:
                message = FlowManager.create_exam_qos_rule(
                    xid=xid,
                    dst_mac=self.server_mac,
                    out_port=self.server_port,
                    queue_id=queue_id,
                    priority=1000,
                    is_server_ingress=True,
                )
            elif state == STATE_NORMAL:
                message = FlowManager.modify_exam_queue(
                    xid=xid,
                    dst_mac=self.server_mac,
                    out_port=self.server_port,
                    new_queue_id=queue_id,
                    priority=1000,
                    is_server_ingress=True,
                )
            else:
                continue
            if self._send(conn, message):
                installed += 1

        action = "ENABLED" if state == STATE_CONGESTED else "RESTORED"
        LOG.warning(
            "[SDN QoS %s] TCP destination port 5000 -> server %s via switch port %d, queue %d (%d switch(es))",
            action,
            self.server_mac.hex(":"),
            self.server_port,
            queue_id,
            installed,
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Custom OpenFlow 1.3 examination-network controller")
    parser.add_argument("--host", default="0.0.0.0", help="Controller listen address")
    parser.add_argument("--port", type=int, default=6653, help="OpenFlow TCP listen port")
    parser.add_argument("--bw", type=float, default=10.0, help="Server-link capacity in Mbps")
    parser.add_argument("--threshold", type=float, default=70.0, help="Congestion trigger percentage")
    parser.add_argument("--recovery-threshold", type=float, default=35.0, help="Recovery percentage")
    parser.add_argument("--cooldown", type=float, default=4.0, help="Recovery cooldown in seconds")
    parser.add_argument("--stats-interval", type=float, default=2.0, help="Port stats polling interval")
    parser.add_argument("--server-port", type=int, default=1, help="Switch port connected to exam server")
    parser.add_argument(
        "--server-mac",
        type=_parse_mac,
        default=bytes.fromhex("000000000001"),
        help="Exam server MAC address (default: 00:00:00:00:00:01)",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    controller = SDNController(
        host=args.host,
        port=args.port,
        link_bandwidth_mbps=args.bw,
        congestion_threshold_percent=args.threshold,
        recovery_threshold_percent=args.recovery_threshold,
        cooldown_period_sec=args.cooldown,
        stats_interval_sec=args.stats_interval,
        server_port=args.server_port,
        server_mac=args.server_mac,
    )

    def request_shutdown(_signum, _frame) -> None:
        LOG.info("Shutdown signal received")
        controller.stop()

    signal.signal(signal.SIGINT, request_shutdown)
    signal.signal(signal.SIGTERM, request_shutdown)
    try:
        controller.serve_forever()
    except OSError as exc:
        LOG.error("Could not start controller on %s:%d: %s", args.host, args.port, exc)
        raise SystemExit(1) from exc
    finally:
        controller.stop()


if __name__ == "__main__":
    main()
