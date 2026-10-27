"""Off-loop, bounded Twilio delivery; preview never constructs a network client."""
import asyncio
import logging
from config import settings
from alerts.content import DeliveryResult, alert_body, preview_only

logger = logging.getLogger(__name__)


def _build_message_body(violation_data):
    return 'SafeGuard AI\n' + alert_body(violation_data)


def _deliver_whatsapp(data, to_number, bypass_enabled_check):
    destination = to_number or settings.ALERT_WHATSAPP_TO
    if not bypass_enabled_check and not settings.ENABLE_WHATSAPP_ALERTS:
        return DeliveryResult(False, 'WhatsApp alerts are disabled in saved settings.', 'none')
    try:
        body = _build_message_body(data)
        if preview_only():
            return DeliveryResult(False, 'Preview mode: Twilio was not contacted. Nothing was sent.', 'preview', recipient=destination)
        if not (settings.TWILIO_ACCOUNT_SID and settings.TWILIO_AUTH_TOKEN and destination and settings.TWILIO_WHATSAPP_FROM):
            raise ValueError('Twilio SID, token, sender and destination must all be configured')
        from twilio.rest import Client
        from twilio.http.http_client import TwilioHttpClient
        http = TwilioHttpClient(timeout=settings.ALERT_NETWORK_TIMEOUT_SECONDS)
        client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN, http_client=http)
        message = client.messages.create(from_=f'whatsapp:{settings.TWILIO_WHATSAPP_FROM}',
            to=f'whatsapp:{destination}', body=body)
        if message.status in {'failed', 'undelivered'}:
            raise RuntimeError(f'Twilio rejected message: {message.error_message or message.error_code}')
        return DeliveryResult(True, f'Twilio accepted message {message.sid} ({message.status}); final delivery is not confirmed.', 'twilio', sent=True, recipient=destination)
    except Exception as exc:
        message = f'WhatsApp delivery failed: {type(exc).__name__}: {exc}'
        logger.error('[whatsapp] %s (network timeout: %ss)', message, settings.ALERT_NETWORK_TIMEOUT_SECONDS)
        return DeliveryResult(False, message, 'twilio', recipient=destination)


async def send_whatsapp_alert(violation_data, to_number=None, bypass_enabled_check=False):
    return await asyncio.to_thread(_deliver_whatsapp, violation_data, to_number, bypass_enabled_check)
