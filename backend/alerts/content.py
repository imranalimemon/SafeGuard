"""Shared alert content and transport results; no database or network access."""
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from config import settings


@dataclass(frozen=True)
class DeliveryResult:
    ok: bool
    message: str
    transport: str
    sent: bool = False
    recipient: str = ''

    def __bool__(self):
        return self.ok

    def to_dict(self):
        return asdict(self)


def preview_only():
    return settings.ALERT_DELIVERY_MODE != 'live' or settings.ALERT_DEBUG_MODE


def alert_fields(data):
    missing = data.get('missing_ppe') or []
    if isinstance(missing, str):
        missing = [item.strip() for item in missing.split(',') if item.strip()]
    missing_text = ', '.join(missing) or 'None (test message)'
    source = data.get('source') or 'Source not available'
    if data.get('camera_name'):
        source = f"{data['camera_name']} ({source})"
    stamp = data.get('timestamp')
    if stamp:
        moment = stamp if isinstance(stamp, datetime) else datetime.fromisoformat(str(stamp).replace('Z', '+00:00'))
        if moment.tzinfo is None:
            moment = moment.replace(tzinfo=timezone.utc)  # DB timestamps are UTC.
        local = moment.astimezone(ZoneInfo(settings.ALERT_TIMEZONE))
        event_time = f'{local.isoformat(sep=" ", timespec="seconds")} ({settings.ALERT_TIMEZONE})'
    else:
        event_time = 'Event time not available'
    return source, event_time, missing_text


def alert_body(data):
    source, stamp, missing = alert_fields(data)
    label = 'TEST EMAIL — no safety incident' if data.get('is_test') else 'PPE VIOLATION DETECTED'
    return (f'{label}\nSource / camera: {source}\nTime: {stamp}\n'
            f'Missing PPE: {missing}\nViolation ID: {data.get("id") or "test"}\n'
            f'Details: {data.get("details") or "Not provided"}\n')
