"""Thread-safe per-channel, camera/source and worker cooldown reservations."""
import json
import time
from threading import Lock
from detection.deduplicator import ViolationDeduplicator


class AlertThrottle:
    def __init__(self):
        self.last_alerts = {}
        self.inflight = set()
        self.lock = Lock()

    @staticmethod
    def key(channel, data):
        missing = data.get('missing_ppe') or []
        if isinstance(missing, str): missing = [x.strip() for x in missing.split(',') if x.strip()]
        box = data.get('person_bbox') or data.get('bbox')
        if isinstance(box, str): box = json.loads(box)
        worker = ('bbox', tuple(box)) if box and len(box) == 4 else ('event', data.get('id'))
        return channel, data.get('source') or 'unknown', tuple(sorted(missing)), worker

    @staticmethod
    def same(a, b):
        if a[:3] != b[:3] or a[3][0] != b[3][0]: return False
        if a[3][0] == 'bbox':
            return ViolationDeduplicator._same_worker_box(a[3][1], b[3][1])
        return a[3] == b[3]

    def acquire(self, channel, data, cooldown):
        key = self.key(channel, data)
        now = time.monotonic()
        with self.lock:
            self.last_alerts = {k: expiry for k, expiry in self.last_alerts.items() if expiry > now}
            if any(self.same(k, key) for k in self.inflight) or any(self.same(k, key) for k in self.last_alerts):
                return None
            self.inflight.add(key)
        return key

    def finish(self, key, cooldown, completed):
        with self.lock:
            self.inflight.discard(key)
            if completed: self.last_alerts[key] = time.monotonic() + cooldown

    def reset(self):
        with self.lock:
            self.last_alerts.clear(); self.inflight.clear()


throttle = AlertThrottle()
