"""
SafeGuard AI — Violation Deduplicator

Process-local cooldown that suppresses repeat DB writes and alert triggers for
the same worker box, source, and missing PPE. Resets on backend restart, which is
acceptable for the v1 single-process FastAPI deployment.

Design notes:
- State is keyed by `(source, sorted(missing_ppe_tuple), person_bbox)`. A "Helmet" violation
  is tracked independently from a "Helmet, Vest" violation; a worker who fixes
  their mask should still trigger a helmet alert.
- The "source" dimension isolates per-context cooldowns — an `image_upload` and
  a `live_stream` violation don't share a bucket.
- Nearby, strongly overlapping boxes count as the same position despite small
  detection jitter. This is a spatial heuristic, not persistent worker tracking.
- This is a separate layer from `alerts/throttle.py` (which is per-channel,
  not per-violation). Both serve different purposes and stack safely.
"""

from datetime import datetime, timezone
from threading import Lock
from typing import Dict, List, Optional, Tuple

from config import settings


class ViolationDeduplicator:
    """Suppresses repeat violation records within a cooldown window."""

    def __init__(self, cooldown_seconds: Optional[int] = None):
        # Mutable default via settings so the singleton stays in sync if the
        # env var reading changes at runtime.
        self._cooldown_seconds = cooldown_seconds
        self._last_seen: Dict[Tuple[str, tuple, tuple], datetime] = {}
        self._lock = Lock()

    @property
    def cooldown_seconds(self) -> int:
        if self._cooldown_seconds is not None:
            return self._cooldown_seconds
        return settings.VIOLATION_COOLDOWN_SECONDS

    @cooldown_seconds.setter
    def cooldown_seconds(self, value: int) -> None:
        self._cooldown_seconds = value

    @staticmethod
    def _same_worker_box(box_a: tuple, box_b: tuple) -> bool:
        """Allow small box jitter without merging neighboring worker positions."""
        aw, ah = box_a[2] - box_a[0], box_a[3] - box_a[1]
        bw, bh = box_b[2] - box_b[0], box_b[3] - box_b[1]
        if min(aw, ah, bw, bh) <= 0:
            return False
        dx = abs((box_a[0] + box_a[2] - box_b[0] - box_b[2]) / 2)
        dy = abs((box_a[1] + box_a[3] - box_b[1] - box_b[3]) / 2)
        if dx > 0.10 * min(aw, bw) or dy > 0.10 * min(ah, bh):
            return False
        overlap_w = max(0, min(box_a[2], box_b[2]) - max(box_a[0], box_b[0]))
        overlap_h = max(0, min(box_a[3], box_b[3]) - max(box_a[1], box_b[1]))
        intersection = overlap_w * overlap_h
        return intersection / (aw * ah + bw * bh - intersection) >= 0.70

    def should_log(
        self, source: str, missing_ppe: List[str], now: Optional[datetime] = None,
        *, person_bbox: List[int],
    ) -> bool:
        """Return True if this violation should be logged (and alerted), False
        if it falls within the cooldown window of an identical prior event."""
        if not missing_ppe:
            # A violation with no missing PPE is "COMPLIANT" — never logged.
            return False
        key = (source, tuple(sorted(missing_ppe)), tuple(person_bbox))
        current = now or datetime.now(timezone.utc).replace(tzinfo=None)
        # Camera writers run in threads; check and record atomically. Expire
        # old positions so the in-memory cache does not grow indefinitely.
        with self._lock:
            self._last_seen = {
                previous: last for previous, last in self._last_seen.items()
                if (current - last).total_seconds() < self.cooldown_seconds
            }
            for previous in self._last_seen:
                if previous[:2] == key[:2] and self._same_worker_box(previous[2], key[2]):
                    return False
            self._last_seen[key] = current
            return True

    def reset(self) -> None:
        """Clear all cooldown state (useful for tests)."""
        with self._lock:
            self._last_seen.clear()


# Module-level singleton — the upload endpoints import this directly.
deduplicator = ViolationDeduplicator()
