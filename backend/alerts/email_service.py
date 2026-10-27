"""Build/preview exactly the same MIME email used by off-loop SMTP delivery."""
import asyncio
import base64
import logging
import mimetypes
from pathlib import Path
import re
import smtplib
import ssl
from email.message import EmailMessage
from email.policy import SMTP
from email.utils import getaddresses, make_msgid, format_datetime
from datetime import datetime, timezone

from config import settings
from alerts.content import DeliveryResult, alert_body, alert_fields, preview_only

logger = logging.getLogger(__name__)


def smtp_configuration():
    required = {'SMTP_HOST': settings.SMTP_HOST, 'SMTP_USER': settings.SMTP_USER,
                'SMTP_PASSWORD': settings.SMTP_PASSWORD, 'ALERT_EMAIL_TO': settings.ALERT_EMAIL_TO,
                'sender address': settings.ALERT_EMAIL_FROM or settings.SMTP_USER}
    missing = [name for name, value in required.items() if not value]
    recipients = [address for _, address in getaddresses([settings.ALERT_EMAIL_TO or ''])]
    if not recipients or any(not re.fullmatch(r'[^@\s]+@[^@\s]+\.[^@\s]+', address) for address in recipients):
        missing.append('valid recipient email address')
    sender = getaddresses([settings.ALERT_EMAIL_FROM or settings.SMTP_USER or ''])
    if len(sender) != 1 or not re.fullmatch(r'[^@\s]+@[^@\s]+\.[^@\s]+', sender[0][1]):
        missing.append('valid sender email address')
    if not 1 <= settings.SMTP_PORT <= 65535:
        missing.append('valid SMTP_PORT')
    return {'configured': not missing, 'error': 'Missing/invalid: ' + ', '.join(missing) if missing else None}


def _resolve_screenshot_path(value):
    if not value:
        return None
    root = Path(settings.SCREENSHOT_DIR).resolve()
    path = root / Path(value).name if str(value).startswith('/screenshots/') else Path(value)
    path = path.resolve()
    if root not in path.parents or not path.is_file():
        return None
    return path


def build_email(data, screenshot_path=None):
    source, stamp, missing = alert_fields(data)
    prefix = 'TEST EMAIL' if data.get('is_test') else 'PPE VIOLATION'
    subject = f'SafeGuard {prefix} | {source} | {stamp} | Missing: {missing}'
    msg = EmailMessage()
    msg['Subject'] = subject.replace('\r', ' ').replace('\n', ' ')
    msg['From'] = settings.ALERT_EMAIL_FROM or settings.SMTP_USER
    msg['To'] = settings.ALERT_EMAIL_TO
    msg['Date'] = format_datetime(datetime.now(timezone.utc))
    msg['Message-ID'] = make_msgid(domain='safeguard.local')
    body = alert_body(data)
    path = _resolve_screenshot_path(screenshot_path or data.get('screenshot_path'))
    if not data.get('is_test') and path is None:
        raise ValueError('Annotated screenshot is unavailable; refusing to send evidence-free violation email')
    if path:
        mime = mimetypes.guess_type(path.name)[0] or ''
        if not mime.startswith('image/'):
            raise ValueError('Screenshot must be an annotated image')
        body += 'Annotated screenshot attached.\n'
    else:
        body += 'Manual settings test: no worker or screenshot is associated with this message.\n'
    msg.set_content(body)
    if path:
        maintype, subtype = mime.split('/', 1)
        msg.add_attachment(path.read_bytes(), maintype=maintype, subtype=subtype, filename=path.name)
    return msg


def preview_email(data, screenshot_path=None):
    msg = build_email(data, screenshot_path)
    encoded = msg.as_bytes(policy=SMTP)
    return {'ok': True, 'sent': False, 'transport': 'preview', 'subject': str(msg['Subject']),
        'from': str(msg['From']), 'to': str(msg['To']), 'body': msg.get_body(preferencelist=('plain',)).get_content(),
        'attachments': [{'filename': part.get_filename(), 'content_type': part.get_content_type(),
                         'bytes': len(part.get_payload(decode=True))} for part in msg.iter_attachments()],
        'eml_base64': base64.b64encode(encoded).decode('ascii'), 'message': 'Preview generated. Nothing was sent.'}


def _deliver_email(data, screenshot_path):
    recipient = settings.ALERT_EMAIL_TO
    if not settings.ENABLE_EMAIL_ALERTS:
        return DeliveryResult(False, 'Email alerts are disabled in saved settings.', 'none', recipient=recipient)
    try:
        msg = build_email(data, screenshot_path)
        recipient = str(msg['To'])
        if preview_only():
            return DeliveryResult(False, 'Preview mode: SMTP was not contacted. Nothing was sent.', 'preview', recipient=recipient)
        status = smtp_configuration()
        if not status['configured']:
            raise ValueError(status['error'])
        recipients = [address for _, address in getaddresses([str(msg['To'])])]
        context = ssl.create_default_context()
        kwargs = {'timeout': settings.ALERT_NETWORK_TIMEOUT_SECONDS}
        if settings.SMTP_PORT == 465:
            client = smtplib.SMTP_SSL(settings.SMTP_HOST, settings.SMTP_PORT, context=context, **kwargs)
        else:
            client = smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, **kwargs)
        with client as server:
            if settings.SMTP_PORT != 465:
                server.starttls(context=context)
            server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            refused = server.send_message(msg, to_addrs=recipients) or {}
        accepted = len(recipients) - len(refused)
        if refused:
            message = f'SMTP accepted {accepted}/{len(recipients)} configured recipients; refused: {refused}'
            logger.error('[email] %s', message)
            return DeliveryResult(False, message, 'smtp', sent=accepted > 0, recipient=str(msg['To']))
        return DeliveryResult(True, f"SMTP accepted one email for {msg['To']}.", 'smtp', sent=True, recipient=str(msg['To']))
    except Exception as exc:
        message = f'SMTP delivery failed: {type(exc).__name__}: {exc}'
        logger.error('[email] %s (network timeout: %ss)', message, settings.ALERT_NETWORK_TIMEOUT_SECONDS)
        return DeliveryResult(False, message, 'smtp', recipient=recipient)


async def send_email_alert(violation_data, screenshot_path=None):
    # Do not abandon a timed-out thread: its socket timeout supplies the actual
    # send result, avoiding a late send incorrectly marked as never delivered.
    return await asyncio.to_thread(_deliver_email, violation_data, screenshot_path)
