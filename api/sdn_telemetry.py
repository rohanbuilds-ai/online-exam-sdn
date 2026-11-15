"""
Lightweight in-process SDN telemetry snapshot store.

SDNTelemetryStore is a module-level singleton that:
 - accepts push-updates from the SDNController integration via update()
 - serves snapshots to the /api/sdn/telemetry endpoint via get()
 - marks snapshots as stale when they are older than STALE_THRESHOLD_SEC

get_live_telemetry() is the convenience wrapper used by API endpoints.
get_historical_results() loads the two JSON result files produced by the
experiment scripts.
"""

import json
import logging
import os
import threading
import time
from typing import Any, Dict, List, Optional

logger = logging.getLogger("api.sdn_telemetry")

STALE_THRESHOLD_SEC: float = 10.0
MAX_POLICY_EVENTS: int = 20

# Paths relative to the project root (cwd when uvicorn is launched from there)
_RESULTS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "results")
_BASELINE_PATH = os.path.join(_RESULTS_DIR, "baseline_results.json")
_DYNAMIC_PATH = os.path.join(_RESULTS_DIR, "dynamic_sdn_results.json")
_SNAPSHOT_FILE = os.path.join(_RESULTS_DIR, "sdn_telemetry_snapshot.json")


class SDNTelemetryStore:
    """
    Singleton snapshot store for SDN controller telemetry.

    Fields in a full snapshot:
      controller_connected, switch_count, port_stats, congestion_state,
      policy_active, queue_assignment, policy_events, timestamp
    """

    def __init__(self, snapshot_file: Optional[str] = _SNAPSHOT_FILE) -> None:
        self._lock = threading.Lock()
        self._snapshot: Optional[Dict[str, Any]] = None
        self._updated_at: Optional[float] = None
        self._snapshot_file = snapshot_file

    def update(self, snapshot: Dict[str, Any]) -> None:
        """
        Called by the SDNController integration to push fresh telemetry.
        policy_events list is capped to the last MAX_POLICY_EVENTS entries.
        """
        with self._lock:
            # Enforce policy_events cap
            events = snapshot.get("policy_events", [])
            if len(events) > MAX_POLICY_EVENTS:
                snapshot["policy_events"] = events[-MAX_POLICY_EVENTS:]
            snapshot.setdefault("timestamp", time.time())
            self._snapshot = snapshot
            self._updated_at = snapshot["timestamp"]
        logger.debug("SDN telemetry snapshot updated.")

    def get(self) -> Dict[str, Any]:
        """
        Return the latest snapshot augmented with 'available' and 'stale' flags.

        - available=False  → no snapshot has ever been received
        - stale=True       → last snapshot is older than STALE_THRESHOLD_SEC
        """
        with self._lock:
            # Check if file-based IPC snapshot exists and is newer
            if self._snapshot_file and os.path.exists(self._snapshot_file):
                try:
                    mtime = os.path.getmtime(self._snapshot_file)
                    if self._updated_at is None or mtime > self._updated_at:
                        with open(self._snapshot_file, "r", encoding="utf-8") as f:
                            file_snap = json.load(f)
                            if isinstance(file_snap, dict):
                                self._snapshot = file_snap
                                self._updated_at = file_snap.get("timestamp", mtime)
                except Exception as err:
                    logger.debug("Failed to read snapshot file: %s", err)

            if self._snapshot is None:
                return {
                    "available": False,
                    "stale": False,
                    "controller_connected": False,
                    "switch_count": 0,
                    "switches": [],
                    "port_stats": [],
                    "congestion_state": "DISCONNECTED",
                    "policy_active": False,
                    "queue_assignment": None,
                    "policy_events": [],
                    "timestamp": None,
                }
            age = time.time() - (self._updated_at or 0)
            return {
                "available": True,
                "stale": age > STALE_THRESHOLD_SEC,
                **self._snapshot,
            }

    def get_policy_events(self) -> List[Dict[str, Any]]:
        """Return the last MAX_POLICY_EVENTS policy events."""
        with self._lock:
            if self._snapshot is None:
                return []
            return list(self._snapshot.get("policy_events", []))


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------
telemetry_store = SDNTelemetryStore()


# ---------------------------------------------------------------------------
# Public helper functions
# ---------------------------------------------------------------------------

def get_live_telemetry() -> Dict[str, Any]:
    """Return the current SDN telemetry snapshot with availability/staleness flags."""
    return telemetry_store.get()


def get_historical_results() -> Dict[str, Any]:
    """
    Load and return the baseline and dynamic SDN result JSON files.
    Missing files are returned as empty lists rather than raising.
    """
    baseline: Any = []
    dynamic: Any = []

    for path, name in ((_BASELINE_PATH, "baseline"), (_DYNAMIC_PATH, "dynamic")):
        try:
            with open(path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            if name == "baseline":
                baseline = data
            else:
                dynamic = data
        except FileNotFoundError:
            logger.warning("Results file not found: %s", path)
        except (json.JSONDecodeError, OSError) as exc:
            logger.error("Failed to load results file %s: %s", path, exc)

    return {"baseline": baseline, "dynamic": dynamic}
