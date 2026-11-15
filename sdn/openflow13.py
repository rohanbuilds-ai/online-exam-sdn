"""
OpenFlow 1.3 Protocol Definition and Binary Serialization / Deserialization.

Implements OpenFlow 1.3 (wire version 4) message structures,
OXM match construction, instruction encoding, action building,
and multipart port/flow statistics parsing.
"""

import struct
from typing import Dict, List, Optional, Tuple, Any

OFP_VERSION = 4  # OpenFlow 1.3

# OpenFlow Message Types (OFPT_*)
OFPT_HELLO = 0
OFPT_ERROR = 1
OFPT_ECHO_REQUEST = 2
OFPT_ECHO_REPLY = 3
OFPT_EXPERIMENTER = 4
OFPT_FEATURES_REQUEST = 5
OFPT_FEATURES_REPLY = 6
OFPT_GET_CONFIG_REQUEST = 7
OFPT_GET_CONFIG_REPLY = 8
OFPT_SET_CONFIG = 9
OFPT_PACKET_IN = 10
OFPT_FLOW_REMOVED = 11
OFPT_PORT_STATUS = 12
OFPT_PACKET_OUT = 13
OFPT_FLOW_MOD = 14
OFPT_GROUP_MOD = 15
OFPT_PORT_MOD = 16
OFPT_TABLE_MOD = 17
OFPT_MULTIPART_REQUEST = 18
OFPT_MULTIPART_REPLY = 19
OFPT_BARRIER_REQUEST = 20
OFPT_BARRIER_REPLY = 21

# Special Port Numbers
OFPP_MAX = 0xffffff00
OFPP_IN_PORT = 0xfffffff8
OFPP_TABLE = 0xfffffff9
OFPP_NORMAL = 0xfffffffa
OFPP_FLOOD = 0xfffffffb
OFPP_ALL = 0xfffffffc
OFPP_CONTROLLER = 0xfffffffd
OFPP_LOCAL = 0xfffffffe
OFPP_ANY = 0xffffffff

# Special Buffer ID
OFP_NO_BUFFER = 0xffffffff

# Flow Mod Commands
OFPFC_ADD = 0
OFPFC_MODIFY = 1
OFPFC_MODIFY_STRICT = 2
OFPFC_DELETE = 3
OFPFC_DELETE_STRICT = 4

# Instruction Types
OFPIT_GOTO_TABLE = 1
OFPIT_WRITE_METADATA = 2
OFPIT_WRITE_ACTIONS = 3
OFPIT_APPLY_ACTIONS = 4
OFPIT_CLEAR_ACTIONS = 5
OFPIT_METER = 6

# Action Types
OFPAT_OUTPUT = 0
OFPAT_COPY_TTL_OUT = 11
OFPAT_COPY_TTL_IN = 12
OFPAT_SET_MPLS_TTL = 15
OFPAT_DEC_MPLS_TTL = 16
OFPAT_PUSH_VLAN = 17
OFPAT_POP_VLAN = 18
OFPAT_PUSH_MPLS = 19
OFPAT_POP_MPLS = 20
OFPAT_SET_QUEUE = 21
OFPAT_GROUP = 22
OFPAT_SET_NW_TTL = 23
OFPAT_DEC_NW_TTL = 24
OFPAT_SET_FIELD = 25

# Multipart Types (OFPMP_*)
OFPMP_DESC = 0
OFPMP_FLOW = 1
OFPMP_AGGREGATE = 2
OFPMP_TABLE = 3
OFPMP_PORT_STATS = 4
OFPMP_QUEUE = 5
OFPMP_GROUP = 6
OFPMP_GROUP_DESC = 7
OFPMP_GROUP_FEATURES = 8
OFPMP_METER = 9
OFPMP_METER_CONFIG = 10
OFPMP_METER_FEATURES = 11
OFPMP_TABLE_FEATURES = 12
OFPMP_PORT_DESC = 13

# OXM Match Field Classes and Fields (OpenFlow Basic 0x8000)
OXM_CLASS_OPENFLOW_BASIC = 0x8000
OFPXMT_OFB_IN_PORT = 0
OFPXMT_OFB_ETH_DST = 3
OFPXMT_OFB_ETH_SRC = 4
OFPXMT_OFB_ETH_TYPE = 5
OFPXMT_OFB_IP_PROTO = 10
OFPXMT_OFB_IPV4_SRC = 11
OFPXMT_OFB_IPV4_DST = 12
OFPXMT_OFB_TCP_SRC = 13
OFPXMT_OFB_TCP_DST = 14


def pack_header(msg_type: int, xid: int, body_len: int = 0) -> bytes:
    """Pack an 8-byte OpenFlow 1.3 header."""
    length = 8 + body_len
    return struct.pack("!BBHI", OFP_VERSION, msg_type, length, xid)


def unpack_header(data: bytes) -> Tuple[int, int, int, int]:
    """Unpack an 8-byte OpenFlow header. Returns (version, msg_type, length, xid)."""
    return struct.unpack("!BBHI", data[:8])


def pack_hello(xid: int) -> bytes:
    """Pack OFPT_HELLO message."""
    return pack_header(OFPT_HELLO, xid)


def pack_echo_reply(xid: int, payload: bytes = b"") -> bytes:
    """Pack OFPT_ECHO_REPLY message."""
    return pack_header(OFPT_ECHO_REPLY, xid, len(payload)) + payload


def pack_features_request(xid: int) -> bytes:
    """Pack OFPT_FEATURES_REQUEST message."""
    return pack_header(OFPT_FEATURES_REQUEST, xid)


def pack_set_config(xid: int, flags: int = 0, miss_send_len: int = 65535) -> bytes:
    """Pack OFPT_SET_CONFIG message."""
    body = struct.pack("!HH", flags, miss_send_len)
    return pack_header(OFPT_SET_CONFIG, xid, len(body)) + body


def pack_packet_out(
    xid: int,
    packet: bytes,
    out_port: int,
    in_port: int = OFPP_CONTROLLER,
    buffer_id: int = OFP_NO_BUFFER
) -> bytes:
    """Pack OFPT_PACKET_OUT message with OFPAT_OUTPUT action."""
    action = struct.pack("!HHIH6x", OFPAT_OUTPUT, 16, out_port, 0)
    body = struct.pack("!IIH6x", buffer_id, in_port, len(action)) + action + packet
    return pack_header(OFPT_PACKET_OUT, xid, len(body)) + body


def pack_oxm_field(field_num: int, has_mask: bool, value: bytes, mask: bytes = b"") -> bytes:
    """Pack an individual OXM (OpenFlow Extensible Match) TLV field."""
    field_and_mask = (field_num << 1) | (1 if has_mask else 0)
    length = len(value) + len(mask)
    header = struct.pack("!HBB", OXM_CLASS_OPENFLOW_BASIC, field_and_mask, length)
    return header + value + mask


def build_match(
    in_port: Optional[int] = None,
    eth_dst: Optional[bytes] = None,
    eth_src: Optional[bytes] = None,
    eth_type: Optional[int] = None,
    ip_proto: Optional[int] = None,
    tcp_dst: Optional[int] = None,
    tcp_src: Optional[int] = None
) -> bytes:
    """Build a complete ofp_match structure with 8-byte alignment padding."""
    oxm_fields = bytearray()
    if in_port is not None:
        oxm_fields.extend(pack_oxm_field(OFPXMT_OFB_IN_PORT, False, struct.pack("!I", in_port)))
    if eth_dst is not None:
        oxm_fields.extend(pack_oxm_field(OFPXMT_OFB_ETH_DST, False, eth_dst))
    if eth_src is not None:
        oxm_fields.extend(pack_oxm_field(OFPXMT_OFB_ETH_SRC, False, eth_src))
    if eth_type is not None:
        oxm_fields.extend(pack_oxm_field(OFPXMT_OFB_ETH_TYPE, False, struct.pack("!H", eth_type)))
    if ip_proto is not None:
        oxm_fields.extend(pack_oxm_field(OFPXMT_OFB_IP_PROTO, False, struct.pack("!B", ip_proto)))
    if tcp_dst is not None:
        oxm_fields.extend(pack_oxm_field(OFPXMT_OFB_TCP_DST, False, struct.pack("!H", tcp_dst)))
    if tcp_src is not None:
        oxm_fields.extend(pack_oxm_field(OFPXMT_OFB_TCP_SRC, False, struct.pack("!H", tcp_src)))

    match_len = 4 + len(oxm_fields)
    padded_len = ((match_len + 7) // 8) * 8
    pad_bytes = b"\x00" * (padded_len - match_len)
    return struct.pack("!HH", 1, match_len) + oxm_fields + pad_bytes


def build_apply_actions_instruction(actions: bytes) -> bytes:
    """Build OFPIT_APPLY_ACTIONS instruction containing the specified actions."""
    inst_len = 8 + len(actions)
    padded_len = ((inst_len + 7) // 8) * 8
    pad_bytes = b"\x00" * (padded_len - inst_len)
    return struct.pack("!HH4x", OFPIT_APPLY_ACTIONS, padded_len) + actions + pad_bytes


def pack_action_output(port: int, max_len: int = 0) -> bytes:
    """Pack OFPAT_OUTPUT action (16 bytes)."""
    return struct.pack("!HHIH6x", OFPAT_OUTPUT, 16, port, max_len)


def pack_action_set_queue(queue_id: int) -> bytes:
    """Pack OFPAT_SET_QUEUE action (8 bytes)."""
    return struct.pack("!HHI", OFPAT_SET_QUEUE, 8, queue_id)


def pack_flow_mod(
    xid: int,
    command: int = OFPFC_ADD,
    priority: int = 100,
    idle_timeout: int = 60,
    hard_timeout: int = 0,
    cookie: int = 0,
    cookie_mask: int = 0,
    table_id: int = 0,
    match_bytes: bytes = b"",
    instructions_bytes: bytes = b"",
    out_port: int = OFPP_ANY,
    out_group: int = OFPP_ANY
) -> bytes:
    """Pack OFPT_FLOW_MOD (type 14) message."""
    if not match_bytes:
        match_bytes = struct.pack("!HH4x", 1, 4)  # empty match

    fixed = struct.pack(
        "!QQBBHHHIIIH2x",
        cookie,
        cookie_mask,
        table_id,
        command,
        idle_timeout,
        hard_timeout,
        priority,
        OFP_NO_BUFFER,
        out_port,
        out_group,
        0  # flags
    )
    body = fixed + match_bytes + instructions_bytes
    return pack_header(OFPT_FLOW_MOD, xid, len(body)) + body


def pack_port_stats_request(xid: int, port_no: int = OFPP_ANY) -> bytes:
    """Pack OFPT_MULTIPART_REQUEST for OFPMP_PORT_STATS (type 4)."""
    body = struct.pack("!HH4xI4x", OFPMP_PORT_STATS, 0, port_no)
    return pack_header(OFPT_MULTIPART_REQUEST, xid, len(body)) + body


def unpack_port_stats_reply(body: bytes) -> List[Dict[str, Any]]:
    """Parse OFPT_MULTIPART_REPLY body for OFPMP_PORT_STATS."""
    if len(body) < 8:
        return []
    mp_type, flags = struct.unpack("!HH4x", body[:8])
    if mp_type != OFPMP_PORT_STATS:
        return []

    entries = []
    offset = 8
    ENTRY_SIZE = 112  # ofp_port_stats struct size in OpenFlow 1.3

    while offset + ENTRY_SIZE <= len(body):
        (
            port_no,
            rx_packets,
            tx_packets,
            rx_bytes,
            tx_bytes,
            rx_dropped,
            tx_dropped,
            rx_errors,
            tx_errors,
            rx_frame_err,
            rx_over_err,
            rx_crc_err,
            collisions,
            duration_sec,
            duration_nsec
        ) = struct.unpack("!I4xQQQQQQQQQQQQII", body[offset:offset + ENTRY_SIZE])

        entries.append({
            "port_no": port_no,
            "rx_packets": rx_packets,
            "tx_packets": tx_packets,
            "rx_bytes": rx_bytes,
            "tx_bytes": tx_bytes,
            "rx_dropped": rx_dropped,
            "tx_dropped": tx_dropped,
            "rx_errors": rx_errors,
            "tx_errors": tx_errors,
            "duration_sec": duration_sec,
            "duration_nsec": duration_nsec
        })
        offset += ENTRY_SIZE

    return entries


def parse_packet_in(body: bytes) -> Optional[Tuple[int, int, bytes, bytes, bytes]]:
    """
    Parse OFPT_PACKET_IN body.
    Returns: (buffer_id, in_port, src_mac, dst_mac, ethernet_payload) or None.
    """
    if len(body) < 20:
        return None

    buffer_id = struct.unpack("!I", body[:4])[0]
    match_length = struct.unpack("!H", body[18:20])[0]

    offset = 20
    in_port = None

    while offset + 4 <= 16 + match_length:
        oxm_class, field_mask, length = struct.unpack("!HBB", body[offset:offset + 4])
        val = body[offset + 4:offset + 4 + length]
        if oxm_class == 0x8000 and field_mask == 0 and length == 4:
            in_port = struct.unpack("!I", val)[0]
        offset += 4 + length

    data_offset = 16 + ((match_length + 7) // 8 * 8) + 2
    packet = body[data_offset:]

    if len(packet) < 14 or in_port is None:
        return None

    dst_mac = packet[0:6]
    src_mac = packet[6:12]
    return buffer_id, in_port, src_mac, dst_mac, packet
