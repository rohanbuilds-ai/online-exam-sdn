"""Focused unit tests for the custom OpenFlow controller."""

import struct
import unittest

from sdn.congestion_manager import STATE_CONGESTED, STATE_NORMAL
from sdn.controller import SDNController, SwitchConnection
from sdn.openflow13 import (
    OFP_NO_BUFFER,
    OFPP_FLOOD,
    OFPT_FEATURES_REQUEST,
    OFPT_FLOW_MOD,
    OFPT_HELLO,
    OFPT_MULTIPART_REQUEST,
    OFPT_PACKET_OUT,
    OFPXMT_OFB_IN_PORT,
    pack_oxm_field,
    unpack_header,
)


class FakeSocket:
    def __init__(self):
        self.sent = []
        self.closed = False

    def sendall(self, data):
        self.sent.append(data)

    def shutdown(self, _how):
        self.closed = True

    def close(self):
        self.closed = True


class TestSDNController(unittest.TestCase):
    def setUp(self):
        self.controller = SDNController(
            host="127.0.0.1",
            port=6653,
            stats_interval_sec=60.0,
        )
        self.fake_socket = FakeSocket()
        self.conn = SwitchConnection(self.fake_socket, ("127.0.0.1", 40000))

    def message_types(self):
        return [unpack_header(message)[1] for message in self.fake_socket.sent]

    def make_packet_in(self, in_port=2, buffer_id=OFP_NO_BUFFER):
        dst_mac = bytes.fromhex("000000000001")
        src_mac = bytes.fromhex("000000000002")
        frame = dst_mac + src_mac + bytes.fromhex("0800") + b"exam-payload"

        oxm = pack_oxm_field(
            OFPXMT_OFB_IN_PORT,
            False,
            struct.pack("!I", in_port),
        )
        match_len = 4 + len(oxm)
        padded_match_len = (match_len + 7) // 8 * 8
        match = struct.pack("!HH", 1, match_len) + oxm
        match += b"\x00" * (padded_match_len - match_len)

        packet_in_prefix = struct.pack(
            "!IHBBQ", buffer_id, len(frame), 0, 0, 0
        )
        return packet_in_prefix + match + b"\x00\x00" + frame, dst_mac

    def test_hello_triggers_features_request(self):
        self.controller._handle_message(self.conn, OFPT_HELLO, 7, b"")
        self.assertEqual(self.message_types(), [OFPT_FEATURES_REQUEST])

    def test_features_reply_installs_table_miss_and_starts_stats(self):
        features = struct.pack("!QIBB2xII", 1, 256, 1, 0, 0, 0)
        self.controller._handle_features_reply(self.conn, features)

        self.assertTrue(self.conn.ready)
        self.assertEqual(self.conn.dpid, 1)
        self.assertEqual(
            self.message_types(),
            [9, OFPT_FLOW_MOD, OFPT_MULTIPART_REQUEST],
        )

    def test_unknown_destination_is_flooded(self):
        body, _dst = self.make_packet_in()
        self.controller._handle_packet_in(self.conn, body)

        self.assertEqual(self.message_types(), [OFPT_PACKET_OUT])
        # OFPT_PACKET_OUT body starts with buffer_id/in_port/actions_len/pad;
        # the output action's port is at message offset 8 + 16 + 4.
        out_port = struct.unpack("!I", self.fake_socket.sent[0][28:32])[0]
        self.assertEqual(out_port, OFPP_FLOOD)

    def test_known_destination_installs_flow_and_sends_packet(self):
        body, dst_mac = self.make_packet_in()
        self.conn.mac_to_port[dst_mac] = 3
        self.controller._handle_packet_in(self.conn, body)

        self.assertEqual(self.message_types(), [OFPT_FLOW_MOD, OFPT_PACKET_OUT])

    def test_congestion_policy_installs_queue_flow_and_recovery_modifies_it(self):
        self.conn.ready = True
        self.controller.connections.add(self.conn)

        self.controller._on_policy_change(STATE_CONGESTED, 1)
        self.assertEqual(self.message_types(), [OFPT_FLOW_MOD])

        self.controller._on_policy_change(STATE_NORMAL, 1)
        self.assertEqual(self.message_types(), [OFPT_FLOW_MOD, OFPT_FLOW_MOD])


if __name__ == "__main__":
    unittest.main()
