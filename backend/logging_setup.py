"""Rotated operational logs with secret redaction; no request bodies are logged."""
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
import re


class RedactingFormatter(logging.Formatter):
    def __init__(self, secrets=()):
        super().__init__('%(asctime)sZ %(levelname)s %(name)s %(message)s')
        import time
        self.converter = time.gmtime
        self.secrets = [value for value in secrets if isinstance(value, str) and len(value) >= 4]

    def format(self, record):
        text = super().format(record)
        for value in self.secrets:
            text = text.replace(value, '[redacted]')
        text = re.sub(r'((?:https?|rtsps?)://)[^\s/@]+:[^\s/@]+@', r'\1[redacted]@', text)
        return re.sub(r'((?:https?|rtsps?)://[^\s?]+)\?[^\s]+', r'\1?[redacted]', text)


def configure_logging(config):
    path = Path(config.LOG_DIR)
    path.mkdir(parents=True, exist_ok=True)
    root = logging.getLogger()
    for existing in list(root.handlers):
        if getattr(existing, '_safeguard', False):
            root.removeHandler(existing)
            existing.close()
    handler = RotatingFileHandler(path / 'safeguard.log', maxBytes=2_000_000, backupCount=4, encoding='utf-8')
    handler._safeguard = True
    handler.setFormatter(RedactingFormatter([getattr(config, key, '') for key in (
        'SMTP_PASSWORD', 'TWILIO_AUTH_TOKEN', 'CREDENTIAL_KEY', 'ADMIN_PASSWORD')]))
    root.addHandler(handler)
    root.setLevel(logging.INFO)
    logging.getLogger('safeguard').info('Backend started; alert delivery mode=%s', config.ALERT_DELIVERY_MODE)
    return handler


def tail_logs(directory, limit=100):
    path = Path(directory) / 'safeguard.log'
    if not path.exists():
        return []
    with path.open('rb') as file:
        file.seek(0, 2)
        size = file.tell()
        file.seek(max(0, size - 200_000))
        content = file.read().decode('utf-8', errors='replace').splitlines()
    if size > 200_000:
        content = content[1:]
    return content[-max(1, min(250, limit)):]
