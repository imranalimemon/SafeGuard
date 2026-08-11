"""
SafeGuard AI — Violation Deduplicator

Process-local cooldown that suppresses repeat DB writes and alert triggers for
the same (source, missing_ppe) combination. Resets on backend restart, which is
acceptable for the v1 single-process FastAPI deployment.

Design notes:
- State is keyed by `(source, sorted(missing_ppe_tuple))`. A "Helmet" violation
  is tracked independently from a "Helmet, Vest" violation; a worker who fixes
  their mask should still trigger a helmet alert.
- The "source" dimension isolates per-context cooldowns — an `image_upload` and
  a `live_stream` violation don't share a bucket.
- This is a separate layer from `alerts/throttle.py` (which is per-channel,
  not per-violation). Both serve different purposes and stack safely.
"""

from datetime import datetime
from typing import Dict, List, Optional, Tuple

from config import settings


class ViolationDeduplicator:
    """Suppresses repeat violation records within a cooldown window."""

    def __init__(self, cooldown_seconds: Optional[int] = None):
        # Mutable default via settings so the singleton stays in sync if the
        # env var reading changes at runtime.
        self._cooldown_seconds = cooldown_seconds
        self._last_seen: Dict[Tuple[str, tuple], datetime] = {}

    @property
    def cooldown_seconds(self) -> int:
        if self._cooldown_seconds is not None:
            return self._cooldown_seconds
        return settings.VIOLATION_COOLDOWN_SECONDS

    @cooldown_seconds.setter
    def cooldown_seconds(self, value: int) -> None:
        self._cooldown_seconds = value

    def should_log(self, source: str, missing_ppe: List[str], now: Optional[datetime] = None) -> bool:
        """Return True if this violation should be logged (and alerted), False
        if it falls within the cooldown window of an identical prior event."""
        if not missing_ppe:
            # A violation with no missing PPE is "COMPLIANT" — never logged.
            return False
        key = (source, tuple(sorted(missing_ppe)))
        last = self._last_seen.get(key)
        current = now or datetime.utcnow()
        if last is not None:
            elapsed = (current - last).total_seconds()
            if elapsed < self.cooldown_seconds:
                return False
        self._last_seen[key] = current
        return True

    def reset(self) -> None:
        """Clear all cooldown state (useful for tests)."""
        self._last_seen.clear()


# Module-level singleton — the upload endpoints import this directly.
deduplicator = ViolationDeduplicator()
