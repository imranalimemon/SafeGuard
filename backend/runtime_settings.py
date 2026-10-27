"""Validated settings shared by save and startup; no application/DB imports."""
import json
import re
from typing import Literal
from pydantic import BaseModel, Field, StrictBool, field_validator, model_validator


class SavedSettings(BaseModel):
    email_enabled: StrictBool
    whatsapp_enabled: StrictBool
    email_recipients: str = Field(max_length=2000)
    whatsapp_recipient: str = Field(max_length=32)
    email_cooldown: int = Field(ge=0, le=86400, strict=True)
    whatsapp_cooldown: int = Field(ge=0, le=86400, strict=True)
    confidence_threshold: float = Field(ge=0, le=1, allow_inf_nan=False, strict=True)
    required_ppe: list[Literal['Helmet', 'Safety Vest', 'Face Mask']] = Field(
        default_factory=lambda: ['Helmet', 'Safety Vest', 'Face Mask'], min_length=1, max_length=3)

    @field_validator('required_ppe')
    @classmethod
    def distinct_ppe(cls, values):
        if len(set(values)) != len(values):
            raise ValueError('Required PPE must not contain duplicates')
        return values

    @model_validator(mode='after')
    def recipients(self):
        self.email_recipients = ', '.join(part.strip() for part in self.email_recipients.split(',') if part.strip())
        self.whatsapp_recipient = self.whatsapp_recipient.strip()
        if self.email_enabled and (not self.email_recipients or any(
            not re.fullmatch(r'[^@\s,]+@[^@\s,]+\.[^@\s,]+', address.strip())
            for address in self.email_recipients.split(','))):
            raise ValueError('Enabled email alerts require valid recipient email addresses')
        if self.whatsapp_enabled and not re.fullmatch(r'\+?[1-9][0-9]{7,14}', self.whatsapp_recipient):
            raise ValueError('Enabled WhatsApp alerts require an international recipient number')
        return self


def read_settings(row, config):
    values = {
        'email_enabled': config.ENABLE_EMAIL_ALERTS, 'whatsapp_enabled': config.ENABLE_WHATSAPP_ALERTS,
        'email_recipients': config.ALERT_EMAIL_TO, 'whatsapp_recipient': config.ALERT_WHATSAPP_TO,
        'email_cooldown': config.EMAIL_COOLDOWN_SECONDS, 'whatsapp_cooldown': config.WHATSAPP_COOLDOWN_SECONDS,
        'confidence_threshold': config.CONFIDENCE_THRESHOLD, 'required_ppe': list(config.REQUIRED_PPE),
    }
    if row is not None:
        for key in values:
            value = getattr(row, key, None)
            if key == 'required_ppe' and value is not None:
                try:
                    value = json.loads(value)
                except (ValueError, TypeError) as exc:
                    raise ValueError('Saved required PPE is invalid JSON; correct alert_settings.required_ppe') from exc
            if value is not None:
                values[key] = value
    return SavedSettings.model_validate(values)


def apply_settings(value, config):
    mapping = {
        'email_enabled': 'ENABLE_EMAIL_ALERTS', 'whatsapp_enabled': 'ENABLE_WHATSAPP_ALERTS',
        'email_recipients': 'ALERT_EMAIL_TO', 'whatsapp_recipient': 'ALERT_WHATSAPP_TO',
        'email_cooldown': 'EMAIL_COOLDOWN_SECONDS', 'whatsapp_cooldown': 'WHATSAPP_COOLDOWN_SECONDS',
        'confidence_threshold': 'CONFIDENCE_THRESHOLD', 'required_ppe': 'REQUIRED_PPE',
    }
    for name, setting in mapping.items():
        setattr(config, setting, getattr(value, name))


def restore_settings(session_factory, model, config):
    # Own and close this session in the startup worker thread.
    with session_factory() as db:
        value = read_settings(db.query(model).order_by(model.id).first(), config)
    apply_settings(value, config)
    return value
