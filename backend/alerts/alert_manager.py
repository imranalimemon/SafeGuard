"""Alert orchestration: transport workers, scoped cooldowns and atomic delivery logs."""
import asyncio
import logging
from datetime import datetime, timezone

from db.database import SessionLocal
from db.models import AlertLog, Violation
from alerts.throttle import throttle
from alerts.content import DeliveryResult
from alerts.email_service import send_email_alert
from alerts.whatsapp_service import send_whatsapp_alert
from config import settings

logger = logging.getLogger(__name__)


def _synthetic_violation():
    return {'id': None, 'is_test': True, 'source': 'settings:manual-test',
        'violation_type': 'Manual alert transport test', 'missing_ppe': [],
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'details': 'One manual Settings button click. No safety incident or screenshot is associated.'}


def _record_result(channel, result, data):
    try:
        with SessionLocal() as db:
            db.add(AlertLog(channel=channel, sent_to=result.recipient,
                sent_at=datetime.now(timezone.utc).replace(tzinfo=None), violation_id=data.get('id'),
                status='preview' if result.transport == 'preview' else 'success' if result.ok else 'failed',
                message=result.message, transport=result.transport))
            if channel == 'email' and result.transport == 'smtp' and result.sent and data.get('id') is not None:
                db.query(Violation).filter(Violation.id == data['id']).update({'alert_sent': True})
            db.commit()
        return True
    except Exception:
        logger.exception('[alerts] Could not persist alert result / email delivery flag')
        return False


async def _send_and_log(channel, data, screenshot_path=None, *, to_number=None, bypass_enabled_check=False):
    try:
        result = await (send_email_alert(data, screenshot_path) if channel == 'email' else
                        send_whatsapp_alert(data, to_number=to_number, bypass_enabled_check=bypass_enabled_check))
    except Exception as exc:
        result = DeliveryResult(False, f'{channel} delivery failed: {type(exc).__name__}: {exc}', channel)
        logger.exception('[alerts] %s', result.message)
    recorded = await asyncio.to_thread(_record_result, channel, result, data)
    response = result.to_dict()
    response['logged'] = recorded
    if not recorded:
        response['message'] += ' Alert database logging failed; check server logs.'
    return response


async def _automatic(channel, data, screenshot_path, cooldown):
    key = throttle.acquire(channel, data, cooldown)
    if key is None:
        return {'ok': False, 'sent': False, 'transport': 'none', 'message': 'Worker/source cooldown or send in progress.'}
    completed = False
    try:
        response = await _send_and_log(channel, data, screenshot_path)
        completed = response['sent'] or response['transport'] == 'preview'
        return response
    finally:
        throttle.finish(key, cooldown, completed)


async def trigger_alerts(violation_data, screenshot_path=None):
    calls, channels = [], []
    for channel, enabled, cooldown in (
        ('email', settings.ENABLE_EMAIL_ALERTS, settings.EMAIL_COOLDOWN_SECONDS),
        ('whatsapp', settings.ENABLE_WHATSAPP_ALERTS, settings.WHATSAPP_COOLDOWN_SECONDS),
    ):
        if enabled:
            channels.append(channel)
            calls.append(_automatic(channel, violation_data, screenshot_path, cooldown))
    return dict(zip(channels, await asyncio.gather(*calls)))


async def trigger_alerts_test(channel):
    if channel not in {'email', 'whatsapp'}:
        return {'ok': False, 'sent': False, 'transport': 'none', 'message': 'Unknown alert channel'}
    # One explicit request -> one channel -> one transport attempt, configured recipient only.
    return await _send_and_log(channel, _synthetic_violation())


async def share_whatsapp(data, to_number=None):
    return await _send_and_log('whatsapp', data, to_number=to_number, bypass_enabled_check=True)
