"""Fake SMTP/Twilio + disposable SQLite only. Outbound socket calls are forbidden."""
import asyncio
import base64
from datetime import datetime
from email import policy
from email.parser import BytesParser
from pathlib import Path
import inspect
import smtplib
import sys
import tempfile
import threading
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session
from backend import runtime_settings
from backend.test_ppe_defaults import BACKEND, fresh_config, load_source
from backend.test_ppe_association import dedup_module


class AlertTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        # The asyncio loop is already initialized. These forbid transport sockets,
        # including accidental fall-through from fake clients to a real network.
        for target in ('socket.create_connection', 'socket.socket.connect'):
            guard = patch(target, side_effect=AssertionError('Real network is forbidden'))
            guard.start(); self.addCleanup(guard.stop)
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.config = fresh_config(); self.cfg = self.config.settings
        self.cfg.DATABASE_URL = 'sqlite:///' + (self.root / 'alerts-test.db').as_posix()
        self.cfg.SCREENSHOT_DIR = str(self.root / 'screenshots'); Path(self.cfg.SCREENSHOT_DIR).mkdir()
        self.screenshot = Path(self.cfg.SCREENSHOT_DIR) / 'annotated.jpg'
        self.screenshot.write_bytes(b'fake annotated JPEG content')
        self.cfg.ENABLE_EMAIL_ALERTS = True; self.cfg.ENABLE_WHATSAPP_ALERTS = False
        self.cfg.SMTP_HOST = 'smtp.example.invalid'; self.cfg.SMTP_PORT = 587
        self.cfg.SMTP_USER = 'sender@example.invalid'; self.cfg.SMTP_PASSWORD = 'FAKE-secret'
        self.cfg.ALERT_EMAIL_FROM = 'sender@example.invalid'; self.cfg.ALERT_EMAIL_TO = 'configured@example.invalid'
        self.cfg.TWILIO_ACCOUNT_SID = 'FAKE-SID'; self.cfg.TWILIO_AUTH_TOKEN = 'FAKE-token'
        self.cfg.TWILIO_WHATSAPP_FROM = '+15005550006'; self.cfg.ALERT_WHATSAPP_TO = '+15005550007'
        self.sent = []; self.smtp_mode = ''; self.twilio_mode = ''
        self.entered = threading.Event(); self.release = threading.Event(); self.addCleanup(self.release.set)
        owner = self

        class FakeSMTP:
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def starttls(self, **kwargs): pass
            def login(self, user, password):
                if owner.smtp_mode == 'auth': raise smtplib.SMTPAuthenticationError(535, b'fake authentication rejected')
            def send_message(self, msg, to_addrs=None):
                owner.entered.set()
                if owner.smtp_mode == 'slow': owner.release.wait(timeout=2)
                if owner.smtp_mode == 'timeout': raise TimeoutError('fake SMTP timeout')
                owner.sent.append((msg.as_bytes(policy=policy.SMTP), to_addrs, threading.get_ident()))
                return {'refused@example.invalid': (550, b'fake refusal')} if owner.smtp_mode == 'partial' else {}

        self.smtp = Mock(side_effect=lambda *a, **kw: FakeSMTP())
        for target in ('smtplib.SMTP', 'smtplib.SMTP_SSL'):
            fake = patch(target, self.smtp); fake.start(); self.addCleanup(fake.stop)
        def twilio_create(**kwargs):
            self.entered.set()
            if self.twilio_mode == 'slow': self.release.wait(timeout=2)
            if self.twilio_mode == 'timeout': raise TimeoutError('fake Twilio timeout')
            return SimpleNamespace(sid='FAKE-MESSAGE', status='queued')
        self.twilio_create = Mock(side_effect=twilio_create)
        self.twilio = Mock(return_value=SimpleNamespace(messages=SimpleNamespace(create=self.twilio_create)))
        self.http = Mock(return_value=object())
        alerts = ModuleType('alerts'); alerts.__path__ = [str(BACKEND / 'alerts')]
        db = ModuleType('db'); db.__path__ = [str(BACKEND / 'db')]
        modules = {'config': self.config, 'db': db, 'alerts': alerts,
            'detection.deduplicator': dedup_module, 'runtime_settings': runtime_settings,
            'twilio.rest': SimpleNamespace(Client=self.twilio),
            'twilio.http.http_client': SimpleNamespace(TwilioHttpClient=self.http)}
        self.modules = patch.dict(sys.modules, modules); self.modules.start(); self.addCleanup(self.modules.stop)
        self.database = load_source('db.database', BACKEND / 'db/database.py'); sys.modules['db.database'] = self.database
        self.models = load_source('db.models', BACKEND / 'db/models.py'); sys.modules['db.models'] = self.models
        self.database.Base.metadata.create_all(self.database.engine); self.addCleanup(self.database.engine.dispose)
        self.db = self.database.SessionLocal(); self.addCleanup(self.db.close)
        self.db.add(self.models.Violation(id=1, missing_ppe='Helmet, Safety Vest', source='camera:7',
            screenshot_path='/screenshots/annotated.jpg', bbox='[10,10,100,200]', timestamp=datetime(2026, 10, 27, 20)))
        self.db.commit()
        for name in ('content', 'email_service', 'whatsapp_service', 'throttle', 'alert_manager'):
            module = load_source('alerts.' + name, BACKEND / f'alerts/{name}.py')
            sys.modules['alerts.' + name] = module
            setattr(self, name, module)
        self.settings_api = load_source('isolated_alert_settings_api', BACKEND / 'api/settings.py')
        self.violations_api = load_source('isolated_alert_violation_api', BACKEND / 'api/violations.py')
        self.data = {'id': 1, 'source': 'camera:7', 'camera_name': 'Entrance', 'timestamp': '2026-10-27T20:00:00',
            'missing_ppe': ['Helmet', 'Safety Vest'], 'person_bbox': [10, 10, 100, 200],
            'screenshot_path': '/screenshots/annotated.jpg'}
        self.assertTrue(Path(self.database.engine.url.database).is_relative_to(self.root))

    def logs(self):
        self.db.expire_all()
        return self.db.query(self.models.AlertLog).order_by(self.models.AlertLog.id).all()

    def emailed(self):
        self.db.expire_all()
        return self.db.get(self.models.Violation, 1).alert_sent

    async def test_preview_builds_exact_mime_and_attachment_without_sending_or_db_writes(self):
        preview = self.violations_api.preview_violation_email(1, db=self.db)
        msg = BytesParser(policy=policy.default).parsebytes(base64.b64decode(preview['eml_base64']))
        self.assertIn('camera:7', preview['subject']); self.assertIn('+05:00', preview['subject'])
        self.assertIn('Asia/Karachi', preview['body']); self.assertIn('Helmet, Safety Vest', preview['body'])
        self.assertEqual(msg['Subject'], preview['subject'])
        self.assertEqual(list(msg.iter_attachments())[0].get_payload(decode=True), self.screenshot.read_bytes())
        self.assertFalse(preview['sent']); self.assertEqual(self.logs(), [])
        self.smtp.assert_not_called(); self.twilio.assert_not_called()

    async def test_missing_or_external_screenshot_fails_without_sending(self):
        self.data['screenshot_path'] = '/screenshots/missing.jpg'
        with self.assertRaisesRegex(ValueError, 'Annotated screenshot'):
            self.email_service.preview_email(self.data)
        outside = self.root / 'outside.jpg'; outside.write_bytes(b'not permitted')
        with self.assertRaises(ValueError): self.email_service.preview_email(self.data, str(outside))
        self.smtp.assert_not_called()

    async def test_default_preview_blocks_smtp_with_enabled_saved_toggle(self):
        self.assertEqual(self.cfg.ALERT_DELIVERY_MODE, 'preview')
        result = await self.alert_manager.trigger_alerts(self.data)
        self.assertFalse(result['email']['sent']); self.assertEqual(result['email']['transport'], 'preview')
        self.assertEqual(self.logs()[0].status, 'preview'); self.assertFalse(self.emailed())
        self.smtp.assert_not_called()

    async def test_db_enabled_toggles_cannot_override_process_preview_mode(self):
        saved = runtime_settings.SavedSettings(email_enabled=True, whatsapp_enabled=True,
            email_recipients=self.cfg.ALERT_EMAIL_TO, whatsapp_recipient=self.cfg.ALERT_WHATSAPP_TO,
            email_cooldown=30, whatsapp_cooldown=60, confidence_threshold=0.5,
            required_ppe=['Helmet', 'Safety Vest', 'Face Mask'])
        self.settings_api.update_alert_settings(saved, db=self.db)
        runtime_settings.restore_settings(self.database.SessionLocal, self.models.AlertSettings, self.cfg)
        self.assertTrue(self.cfg.ENABLE_EMAIL_ALERTS); self.assertTrue(self.cfg.ENABLE_WHATSAPP_ALERTS)
        self.assertEqual(self.cfg.ALERT_DELIVERY_MODE, 'preview')
        result = await self.alert_manager.trigger_alerts(self.data)
        self.assertEqual([result[c]['transport'] for c in ('email', 'whatsapp')], ['preview', 'preview'])
        self.smtp.assert_not_called(); self.twilio.assert_not_called()

    async def test_database_result_writes_also_run_off_event_loop(self):
        self.cfg.ALERT_DELIVERY_MODE = 'live'
        original = self.alert_manager._record_result
        threads = []
        def record(*args):
            threads.append(threading.get_ident())
            return original(*args)
        with patch.object(self.alert_manager, '_record_result', side_effect=record):
            await self.alert_manager.trigger_alerts(self.data)
        self.assertTrue(threads); self.assertNotIn(threading.get_ident(), threads)

    async def test_database_failure_after_send_is_reported_without_claiming_log_success(self):
        self.cfg.ALERT_DELIVERY_MODE = 'live'
        with patch.object(self.alert_manager, 'SessionLocal', side_effect=RuntimeError('fake log DB failure')), self.assertLogs('alerts.alert_manager', level='ERROR'):
            result = await self.alert_manager.trigger_alerts(self.data)
        self.assertTrue(result['email']['sent']); self.assertFalse(result['email']['logged'])
        self.assertIn('database logging failed', result['email']['message'])

    async def test_twilio_wait_does_not_block_event_loop(self):
        self.cfg.ALERT_DELIVERY_MODE = 'live'; self.cfg.ENABLE_WHATSAPP_ALERTS = True
        self.twilio_mode = 'slow'
        task = asyncio.create_task(self.whatsapp_service.send_whatsapp_alert(self.data))
        self.assertTrue(await asyncio.to_thread(self.entered.wait, 1))
        try:
            for _ in range(4): await asyncio.sleep(0.005)
            self.assertFalse(task.done())
        finally: self.release.set()
        self.assertTrue((await task).ok)

    async def test_debug_flag_also_blocks_network_even_if_live_mode_is_set(self):
        self.cfg.ALERT_DELIVERY_MODE = 'live'; self.cfg.ALERT_DEBUG_MODE = True
        result = await self.email_service.send_email_alert(self.data)
        self.assertEqual(result.transport, 'preview'); self.smtp.assert_not_called()

    async def test_smtp_success_logs_actual_recipient_and_sets_email_flag(self):
        self.cfg.ALERT_DELIVERY_MODE = 'live'
        result = await self.alert_manager.trigger_alerts(self.data)
        self.assertTrue(result['email']['ok']); self.assertTrue(result['email']['sent']); self.assertTrue(self.emailed())
        row = self.logs()[0]
        self.assertEqual((row.status, row.transport, row.sent_to), ('success', 'smtp', 'configured@example.invalid'))
        self.assertEqual(self.smtp.call_args.kwargs['timeout'], 10)
        self.assertEqual(self.sent[0][1], ['configured@example.invalid'])
        self.assertNotEqual(self.sent[0][2], threading.get_ident())

    async def test_authentication_error_is_returned_and_recorded(self):
        self.cfg.ALERT_DELIVERY_MODE = 'live'; self.smtp_mode = 'auth'
        with self.assertLogs('alerts.email_service', level='ERROR'):
            result = await self.settings_api.test_email_alert()
        self.assertFalse(result['ok']); self.assertIn('535', result['message']); self.assertIn('fake authentication rejected', result['message'])
        self.assertEqual(self.logs()[0].status, 'failed'); self.assertFalse(self.emailed())

    async def test_timeout_has_failure_log_and_does_not_consume_worker_cooldown(self):
        self.cfg.ALERT_DELIVERY_MODE = 'live'; self.smtp_mode = 'timeout'
        with self.assertLogs('alerts.email_service', level='ERROR') as captured:
            first = await self.alert_manager.trigger_alerts(self.data)
        self.assertIn('timeout', first['email']['message']); self.assertIn('network timeout', ' '.join(captured.output))
        self.smtp_mode = ''
        second = await self.alert_manager.trigger_alerts(self.data)
        self.assertTrue(second['email']['sent']); self.assertEqual([r.status for r in self.logs()], ['failed', 'success'])

    async def test_failure_after_success_never_clears_historical_email_flag(self):
        self.cfg.ALERT_DELIVERY_MODE = 'live'
        await self.alert_manager.trigger_alerts(self.data)
        self.throttle.throttle.reset(); self.smtp_mode = 'timeout'
        with self.assertLogs('alerts.email_service', level='ERROR'):
            await self.alert_manager.trigger_alerts(self.data)
        self.assertTrue(self.emailed())

    async def test_partial_smtp_acceptance_records_failure_detail_but_keeps_true_sent_flag(self):
        self.cfg.ALERT_DELIVERY_MODE = 'live'; self.smtp_mode = 'partial'
        self.cfg.ALERT_EMAIL_TO = 'configured@example.invalid, refused@example.invalid'
        with self.assertLogs('alerts.email_service', level='ERROR'):
            result = await self.alert_manager.trigger_alerts(self.data)
        self.assertFalse(result['email']['ok']); self.assertTrue(result['email']['sent']); self.assertTrue(self.emailed())
        self.assertIn('1/2', self.logs()[0].message)

    async def test_manual_test_sends_one_message_to_configured_recipient_only(self):
        self.cfg.ALERT_DELIVERY_MODE = 'live'
        self.assertEqual(len(inspect.signature(self.settings_api.test_email_alert).parameters), 0)
        result = await self.settings_api.test_email_alert()
        self.assertTrue(result['ok']); self.assertEqual(len(self.sent), 1)
        self.assertEqual(self.sent[0][1], ['configured@example.invalid'])
        self.assertEqual(self.twilio.call_count, 0)
        self.assertEqual(self.logs()[0].violation_id, None)

    async def test_manual_test_disabled_means_no_attempt(self):
        self.cfg.ENABLE_EMAIL_ALERTS = False
        result = await self.settings_api.test_email_alert()
        self.assertFalse(result['ok']); self.smtp.assert_not_called(); self.assertEqual(self.logs(), [])

    async def test_other_workers_and_cameras_do_not_suppress_each_other(self):
        self.cfg.ALERT_DELIVERY_MODE = 'live'
        await self.alert_manager.trigger_alerts(self.data)
        jitter = {**self.data, 'person_bbox': [11, 10, 101, 200]}
        duplicate = await self.alert_manager.trigger_alerts(jitter)
        self.assertIn('cooldown', duplicate['email']['message'])
        for id, box, source in [(2, [110, 10, 200, 200], 'camera:7'), (3, [10, 10, 100, 200], 'camera:8')]:
            self.db.add(self.models.Violation(id=id)); self.db.commit()
            await self.alert_manager.trigger_alerts({**self.data, 'id': id, 'person_bbox': box, 'source': source})
        self.assertEqual(len(self.sent), 3)

    async def test_inflight_same_worker_is_reserved_and_smtp_does_not_block_loop(self):
        self.cfg.ALERT_DELIVERY_MODE = 'live'; self.smtp_mode = 'slow'
        task = asyncio.create_task(self.alert_manager.trigger_alerts(self.data))
        self.assertTrue(await asyncio.to_thread(self.entered.wait, 1))
        try:
            second = await self.alert_manager.trigger_alerts(self.data)
            for _ in range(4): await asyncio.sleep(0.005)
            self.assertFalse(task.done()); self.assertIn('progress', second['email']['message'])
        finally: self.release.set()
        await task
        self.assertEqual(len(self.sent), 1)

    async def test_twilio_uses_timeout_worker_and_does_not_set_email_flag(self):
        self.cfg.ALERT_DELIVERY_MODE = 'live'; self.cfg.ENABLE_EMAIL_ALERTS = False; self.cfg.ENABLE_WHATSAPP_ALERTS = True
        result = await self.alert_manager.trigger_alerts(self.data)
        self.assertTrue(result['whatsapp']['ok']); self.http.assert_called_once_with(timeout=10)
        self.assertEqual(self.logs()[0].channel, 'whatsapp'); self.assertFalse(self.emailed())

    async def test_twilio_timeout_is_logged_and_returned(self):
        self.cfg.ALERT_DELIVERY_MODE = 'live'; self.cfg.ENABLE_EMAIL_ALERTS = False; self.cfg.ENABLE_WHATSAPP_ALERTS = True
        self.twilio_mode = 'timeout'
        with self.assertLogs('alerts.whatsapp_service', level='ERROR'):
            result = await self.alert_manager.trigger_alerts(self.data)
        self.assertFalse(result['whatsapp']['ok']); self.assertIn('fake Twilio timeout', result['whatsapp']['message'])
        self.assertEqual(self.logs()[0].status, 'failed')

    async def test_preview_blocks_manual_whatsapp_bypass(self):
        self.cfg.ENABLE_WHATSAPP_ALERTS = False
        result = await self.alert_manager.share_whatsapp(self.data, '+15005550008')
        self.assertEqual(result['transport'], 'preview'); self.twilio.assert_not_called(); self.assertFalse(self.emailed())

    async def test_health_checks_configuration_and_temp_db_without_network_or_send(self):
        fake_model = SimpleNamespace(get_detector=lambda: SimpleNamespace(model_path='best.onnx',
            session=SimpleNamespace(get_providers=lambda: ['CPUExecutionProvider'])))
        with patch.dict(sys.modules, {'detection.model': fake_model}):
            health = load_source('isolated_alert_health', BACKEND / 'api/health.py')
        result = health.health()
        self.assertTrue(result['db_connected']); self.assertTrue(result['model_loaded']); self.assertTrue(result['smtp_configured'])
        self.assertEqual(result['alert_delivery_mode'], 'preview')
        self.cfg.ALERT_DELIVERY_MODE = 'live'; self.cfg.ALERT_DEBUG_MODE = True
        self.assertEqual(health.health()['alert_delivery_mode'], 'preview')
        self.cfg.SMTP_PASSWORD = ''
        result = health.health(); self.assertFalse(result['smtp_configured']); self.assertIn('SMTP_PASSWORD', result['smtp_configuration_error'])
        self.smtp.assert_not_called(); self.twilio.assert_not_called(); self.assertEqual(self.logs(), [])

    async def test_settings_preview_endpoint_is_read_only_and_does_not_attempt_smtp(self):
        result = self.settings_api.preview_test_email()
        self.assertTrue(result['ok']); self.assertFalse(result['sent']); self.assertEqual(result['attachments'], [])
        self.assertIn('TEST EMAIL', result['subject'])
        self.assertEqual(self.logs(), []); self.smtp.assert_not_called()

    async def test_cooldown_zero_and_failed_reservations_are_reusable(self):
        limiter = self.throttle.AlertThrottle()
        key = limiter.acquire('email', self.data, 0)
        self.assertIsNotNone(key); self.assertIsNone(limiter.acquire('email', self.data, 0))
        limiter.finish(key, 0, True)
        retry = limiter.acquire('email', self.data, 0); self.assertIsNotNone(retry)
        limiter.finish(retry, 30, False)
        self.assertIsNotNone(limiter.acquire('email', self.data, 30))

    async def test_log_migration_preserves_legacy_entries_and_is_idempotent(self):
        with self.database.engine.begin() as conn:
            conn.execute(text('DROP TABLE alert_logs'))
            conn.execute(text('CREATE TABLE alert_logs (id INTEGER PRIMARY KEY, status VARCHAR)'))
            conn.execute(text("INSERT INTO alert_logs VALUES (1, 'success')"))
        self.database.ensure_alert_log_columns(self.database.engine); self.database.ensure_alert_log_columns(self.database.engine)
        with self.database.engine.connect() as conn:
            self.assertEqual(tuple(conn.execute(text('SELECT * FROM alert_logs')).one()), (1, 'success', None, None))


if __name__ == '__main__':
    unittest.main()
