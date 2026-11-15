"""
OpenFlow 1.3 Flow Table and Rule Management.

Constructs:
1. Table-Miss flow rules (priority 0 -> Controller)
2. Layer-2 MAC learning rules (priority 100)
3. Quality of Service (QoS) Examination Prioritization flows (priority 1000)
4. Dynamic queue modifications and flow evictions
"""

from typing import Optional
from sdn.openflow13 import (
    OFPP_CONTROLLER,
    OFPFC_ADD,
    OFPFC_MODIFY,
    OFPFC_DELETE_STRICT,
    build_match,
    build_apply_actions_instruction,
    pack_action_output,
    pack_action_set_queue,
    pack_flow_mod
)


class FlowManager:
    """Generates standard and dynamic OpenFlow 1.3 flow modification messages."""

    @staticmethod
    def create_table_miss_rule(xid: int) -> bytes:
        """Create default Table-Miss rule: sends unhandled packets to SDN controller."""
        action = pack_action_output(OFPP_CONTROLLER, max_len=65535)
        instruction = build_apply_actions_instruction(action)
        return pack_flow_mod(
            xid=xid,
            command=OFPFC_ADD,
            priority=0,
            idle_timeout=0,
            hard_timeout=0,
            match_bytes=b"",
            instructions_bytes=instruction
        )

    @staticmethod
    def create_l2_forwarding_rule(
        xid: int,
        dst_mac: bytes,
        out_port: int,
        priority: int = 100,
        idle_timeout: int = 60
    ) -> bytes:
        """Create destination MAC based L2 forwarding rule."""
        match_bytes = build_match(eth_dst=dst_mac)
        action = pack_action_output(out_port)
        instruction = build_apply_actions_instruction(action)
        return pack_flow_mod(
            xid=xid,
            command=OFPFC_ADD,
            priority=priority,
            idle_timeout=idle_timeout,
            hard_timeout=0,
            match_bytes=match_bytes,
            instructions_bytes=instruction
        )

    @staticmethod
    def create_exam_qos_rule(
        xid: int,
        dst_mac: bytes,
        out_port: int,
        queue_id: int = 1,
        priority: int = 1000,
        is_server_ingress: bool = True
    ) -> bytes:
        """
        Create High-Priority Examination Traffic Rule matching TCP port 5000.
        Attaches OFPAT_SET_QUEUE (queue_id) + OFPAT_OUTPUT (out_port).
        """
        if is_server_ingress:
            # Client -> Server traffic: TCP destination port 5000
            match_bytes = build_match(
                eth_dst=dst_mac,
                eth_type=0x0800,  # IPv4
                ip_proto=6,       # TCP
                tcp_dst=5000
            )
        else:
            # Server -> Client traffic: TCP source port 5000
            match_bytes = build_match(
                eth_dst=dst_mac,
                eth_type=0x0800,  # IPv4
                ip_proto=6,       # TCP
                tcp_src=5000
            )

        # Actions: 1) Assign QoS Queue, 2) Forward to destination port
        actions = pack_action_set_queue(queue_id) + pack_action_output(out_port)
        instruction = build_apply_actions_instruction(actions)

        return pack_flow_mod(
            xid=xid,
            command=OFPFC_ADD,
            priority=priority,
            idle_timeout=0,  # Permanent flow while congestion policy is active
            hard_timeout=0,
            match_bytes=match_bytes,
            instructions_bytes=instruction
        )

    @staticmethod
    def modify_exam_queue(
        xid: int,
        dst_mac: bytes,
        out_port: int,
        new_queue_id: int,
        priority: int = 1000,
        is_server_ingress: bool = True
    ) -> bytes:
        """Dynamically update queue assignment for examination traffic."""
        if is_server_ingress:
            match_bytes = build_match(
                eth_dst=dst_mac,
                eth_type=0x0800,
                ip_proto=6,
                tcp_dst=5000
            )
        else:
            match_bytes = build_match(
                eth_dst=dst_mac,
                eth_type=0x0800,
                ip_proto=6,
                tcp_src=5000
            )

        actions = pack_action_set_queue(new_queue_id) + pack_action_output(out_port)
        instruction = build_apply_actions_instruction(actions)

        return pack_flow_mod(
            xid=xid,
            command=OFPFC_MODIFY,
            priority=priority,
            idle_timeout=0,
            hard_timeout=0,
            match_bytes=match_bytes,
            instructions_bytes=instruction
        )
