"""
Authoritative Server-Side Exam Timer.

Ensures that examination duration is strictly enforced on the server,
preventing client-side tampering or lag-based cheating.
"""

import time
import threading
from typing import Callable, Optional


class ExamTimer:
    """
    Monotonic clock-based timer for tracking and enforcing individual exam durations.
    """
    def __init__(self, duration_seconds: float, on_expiry: Optional[Callable[[], None]] = None):
        self.duration_seconds = float(duration_seconds)
        self.start_time: Optional[float] = None
        self.end_time: Optional[float] = None
        self.on_expiry = on_expiry
        self._lock = threading.RLock()
        self._timer_thread: Optional[threading.Timer] = None
        self._expired = False

    def start(self) -> None:
        """Start the countdown timer."""
        with self._lock:
            self.start_time = time.monotonic()
            self._expired = False

            if self.on_expiry and self.duration_seconds > 0:
                self._timer_thread = threading.Timer(self.duration_seconds, self._handle_expiry)
                self._timer_thread.daemon = True
                self._timer_thread.start()

    def _handle_expiry(self) -> None:
        with self._lock:
            self._expired = True
            if self.end_time is None:
                self.end_time = time.monotonic()
        if self.on_expiry:
            try:
                self.on_expiry()
            except Exception:
                pass

    def stop(self) -> float:
        """Stop the timer and return elapsed seconds."""
        with self._lock:
            if self.start_time is None:
                return 0.0
            if self.end_time is None:
                self.end_time = time.monotonic()
            if self._timer_thread:
                self._timer_thread.cancel()
            return max(0.0, self.end_time - self.start_time)

    def elapsed_seconds(self) -> float:
        """Return the number of seconds elapsed since timer start."""
        with self._lock:
            if self.start_time is None:
                return 0.0
            current = self.end_time if self.end_time is not None else time.monotonic()
            return max(0.0, current - self.start_time)

    def remaining_seconds(self) -> float:
        """Return remaining seconds until deadline (0.0 if expired)."""
        with self._lock:
            if self.start_time is None:
                return self.duration_seconds
            current = self.end_time if self.end_time is not None else time.monotonic()
            elapsed = current - self.start_time
            remaining = self.duration_seconds - elapsed
            return max(0.0, remaining)

    def is_expired(self) -> bool:
        """Authoritative check whether the deadline has passed."""
        with self._lock:
            if self._expired:
                return True
            if self.start_time is None:
                return False
            current = self.end_time if self.end_time is not None else time.monotonic()
            if (current - self.start_time) >= self.duration_seconds:
                self._expired = True
                return True
            return False
