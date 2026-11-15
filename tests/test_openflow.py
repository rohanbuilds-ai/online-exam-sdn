"""
Unit tests for OpenFlow 1.3 serialization, deserialization, and flow building.
"""

import struct
import unittest
from sdn.openflow13 import (
    OFP_VERSION,
    OFPT_HELLO,
    OFPT_FEATURES_REQUEST,
    OFPT_FLOW_MOD,
    OFPT_MULTIPART_REQUEST,
    OFPT_MULTIPART_REPLY,
    OFPMP_PORT_STATS,
    pack_header,
    unpack_header,
    pack_hello,
    pack_features_request,
    pack_port_stats_request,
    unpack_port_stats_reply,
    build_match,
    pack_action_output,
    pack_action_set_queue,
    pack_flow_mod
)
from sdn.flow_manager import FlowManager


class TestOpenFlow13(unittest.TestCase):
    def test_header_packing_and_unpacking(self):
        hdr = pack_header(OFPT_HELLO, xid=42, body_len=10)
        version, msg_type, length, xid = unpack_header(hdr)
        self.assertEqual(version, OFP_VERSION)
        self.assertEqual(msg_type, OFPT_HELLO)
        self.assertEqual(length, 18)
        self.assertEqual(xid, 42)

    def test_pack_hello(self):
        hello = pack_hello(xid=1)
        self.assertEqual(len(hello), 8)
        version, msg_type, length, xid = unpack_header(hello)
        self.assertEqual(version, 4)
        self.assertEqual(msg_type, 0)

    def test_flow_mod_table_miss(self):
        msg = FlowManager.create_table_miss_rule(xid=10)
        version, msg_type, length, xid = unpack_header(msg)
        self.assertEqual(version, 4)
        self.assertEqual(msg_type, OFPT_FLOW_MOD)
        self.assertGreater(length, 48)

    def test_flow_mod_exam_qos_rule(self):
        dst_mac = bytes.fromhex("000000000001")
        msg = FlowManager.create_exam_qos_rule(
            xid=20,
            dst_mac=dst_mac,
            out_port=1,
            queue_id=1,
            priority=1000,
            is_server_ingress=True
        )
        version, msg_type, length, xid = unpack_header(msg)
        self.assertEqual(version, 4)
        self.assertEqual(msg_type, OFPT_FLOW_MOD)

    def test_port_stats_request_and_reply_parsing(self):
        req = pack_port_stats_request(xid=99)
        version, msg_type, length, xid = unpack_header(req)
        self.assertEqual(msg_type, OFPT_MULTIPART_REQUEST)

        # Build synthetic OFPMP_PORT_STATS reply
        # 8-byte multipart header: mp_type=4, flags=0, pad=0
        mp_hdr = struct.pack("!HH4x", OFPMP_PORT_STATS, 0)
        # Entry (112 bytes):
        entry = struct.pack(
            "!I4xQQQQQQQQQQQQII",
            1,            # port_no
            100,          # rx_packets
            200,          # tx_packets
            15000,        # rx_bytes
            30000,        # tx_bytes
            0, 0, 0, 0, 0, 0, 0, 0, # drops & errors
            10, 500       # duration_sec, nsec
        )
        body = mp_hdr + entry
        parsed = unpack_port_stats_reply(body)
        self.assertEqual(len(parsed), 1)
        self.assertEqual(parsed[0]["port_no"], 1)
        self.assertEqual(parsed[0]["rx_packets"], 100)
        self.assertEqual(parsed[0]["tx_bytes"], 30000)


if __name__ == "__main__":
    unittest.main()
