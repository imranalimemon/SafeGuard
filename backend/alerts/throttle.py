import time

class AlertThrottle:
    def __init__(self):
        self.last_alerts = {}

    def can_send(self, channel: str, cooldown_seconds: int) -> bool:
        now = time.time()
        last_time = self.last_alerts.get(channel, 0)
        return (now - last_time) >= cooldown_seconds

    def record_sent(self, channel: str):
        self.last_alerts[channel] = time.time()

throttle = AlertThrottle()
