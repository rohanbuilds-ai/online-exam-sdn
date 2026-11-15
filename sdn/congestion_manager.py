"""
Adaptive SDN Congestion Management and Dynamic Traffic Prioritization.

Implements:
1. Dynamic threshold-based congestion detection on bottleneck switch links.
2. Hysteresis and cooldown periods to prevent rapid policy oscillation (flapping).
3. Dynamic QoS policy enforcement: Prioritizes examination traffic (TCP 5000)
   into guaranteed bandwidth queues (Queue 1) during periods of congestion.
4. Comprehensive decision auditing and logging for SDN evaluation.
"""

import time
import logging
from typing import Dict, List, Any, Optional, Callable

logger = logging.getLogger("SDNCongestionManager")

STATE_NORMAL = "NORMAL"
STATE_CONGESTED = "CONGESTED"
STATE_RECOVERY = "RECOVERY"


class CongestionDecision:
    def __init__(self, timestamp: float, port_no: int, utilization: float, previous_state: str, new_state: str, action: str):
        self.timestamp = timestamp
        self.port_no = port_no
        self.utilization = utilization
        self.previous_state = previous_state
        self.new_state = new_state
        self.action = action

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": round(self.timestamp, 3),
            "port_no": self.port_no,
            "utilization_percent": round(self.utilization, 2),
            "previous_state": self.previous_state,
            "new_state": self.new_state,
            "action": self.action
        }


class CongestionManager:
    def __init__(
        self,
        server_port: int = 1,
        congestion_threshold_percent: float = 70.0,
        recovery_threshold_percent: float = 35.0,
        cooldown_period_sec: float = 4.0,
        on_policy_change: Optional[Callable[[str, int], None]] = None
    ):
        self.server_port = server_port
        self.congestion_threshold_percent = congestion_threshold_percent
        self.recovery_threshold_percent = recovery_threshold_percent
        self.cooldown_period_sec = cooldown_period_sec
        self.on_policy_change = on_policy_change

        self.current_state = STATE_NORMAL
        self.last_state_change = time.time()
        self.decision_log: List[CongestionDecision] = []

    def evaluate_network_conditions(self, port_metrics: Dict[int, Dict[str, Any]]) -> Optional[CongestionDecision]:
        """
        Evaluate traffic metrics from switch ports and trigger SDN dynamic policies.
        """
        now = time.time()
        # Look at bottleneck port (typically server ingress/egress port 1)
        target_metric = port_metrics.get(self.server_port)
        if not target_metric:
            # Check maximum utilization across all ports
            if not port_metrics:
                return None
            target_metric = max(port_metrics.values(), key=lambda m: m.get("utilization_percent", 0.0))

        port_no = target_metric.get("port_no", self.server_port)
        utilization = target_metric.get("utilization_percent", 0.0)

        prev_state = self.current_state
        decision = None

        if self.current_state == STATE_NORMAL:
            if utilization >= self.congestion_threshold_percent:
                self.current_state = STATE_CONGESTED
                self.last_state_change = now
                action = f"CONGESTION_DETECTED: Utilization reached {utilization}%. Enforcing Priority Queue 1 for Exam Traffic."
                logger.warning(f"[SDN POLICY TRIGGER] Port {port_no} -> {action}")

                decision = CongestionDecision(
                    timestamp=now,
                    port_no=port_no,
                    utilization=utilization,
                    previous_state=prev_state,
                    new_state=STATE_CONGESTED,
                    action=action
                )
                self.decision_log.append(decision)

                if self.on_policy_change:
                    self.on_policy_change(STATE_CONGESTED, port_no)

        elif self.current_state == STATE_CONGESTED:
            if utilization < self.recovery_threshold_percent:
                if (now - self.last_state_change) >= self.cooldown_period_sec:
                    self.current_state = STATE_NORMAL
                    self.last_state_change = now
                    action = f"NETWORK_RECOVERED: Utilization dropped to {utilization}%. Reverting to Standard Best-Effort Queue 0."
                    logger.info(f"[SDN POLICY RESTORE] Port {port_no} -> {action}")

                    decision = CongestionDecision(
                        timestamp=now,
                        port_no=port_no,
                        utilization=utilization,
                        previous_state=prev_state,
                        new_state=STATE_NORMAL,
                        action=action
                    )
                    self.decision_log.append(decision)

                    if self.on_policy_change:
                        self.on_policy_change(STATE_NORMAL, port_no)

        return decision

    def get_decision_history(self) -> List[Dict[str, Any]]:
        return [d.to_dict() for d in self.decision_log]
