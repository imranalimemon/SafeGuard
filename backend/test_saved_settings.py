"""Save/restart validation on a disposable SQLite file, never the real DB."""
import ast
import asyncio
import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile
from types import ModuleType
import unittest
from unittest.mock import patch

from pydantic import ValidationError
from fastapi import APIRouter
from sqlalchemy import text
from sqlalchemy.orm import Session
from backend import runtime_settings
from backend.test_ppe_defaults import BACKEND, fresh_config, load_source


class SavedSettingsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.config = fresh_config()
        self.config.settings.DATABASE_URL = 'sqlite:///' + (Path(self.temp.name) / 'settings.db').as_posix()
        package = ModuleType('db'); package.__path__ = [str(BACKEND / 'db')]
        with patch.dict(sys.modules, {'config': self.config, 'db': package, 'runtime_settings': runtime_settings}):
            self.database = load_source('db.database', BACKEND / 'db/database.py')
            sys.modules['db.database'] = self.database
            self.models = load_source('db.models', BACKEND / 'db/models.py')
            sys.modules['db.models'] = self.models
            self.api = load_source('isolated_saved_settings_api', BACKEND / 'api/settings.py')
        self.database.Base.metadata.create_all(self.database.engine)
        self.addCleanup(self.database.engine.dispose)
        self.db = self.database.SessionLocal(); self.addCleanup(self.db.close)

    def value(self, **changes):
        values = dict(email_enabled=False, whatsapp_enabled=False, email_recipients='owner@example.invalid',
            whatsapp_recipient='+923001234567', email_cooldown=17, whatsapp_cooldown=43,
            confidence_threshold=0.42, required_ppe=['Helmet', 'Face Mask'])
        values.update(changes)
        return runtime_settings.SavedSettings(**values)

    def test_saved_settings_survive_fresh_runtime_and_session(self):
        saved = self.value(email_enabled=True, whatsapp_enabled=True)
        self.api.update_alert_settings(saved, db=self.db)
        restart = fresh_config().settings
        restored = runtime_settings.restore_settings(self.database.SessionLocal, self.models.AlertSettings, restart)
        self.assertEqual(restored.model_dump(), saved.model_dump())
        self.assertEqual(restart.CONFIDENCE_THRESHOLD, 0.42)
        self.assertEqual(restart.REQUIRED_PPE, ['Helmet', 'Face Mask'])
        self.assertEqual(restart.EMAIL_COOLDOWN_SECONDS, 17)
        self.assertEqual(restart.WHATSAPP_COOLDOWN_SECONDS, 43)
        self.assertTrue(restart.ENABLE_EMAIL_ALERTS)
        self.assertTrue(restart.ENABLE_WHATSAPP_ALERTS)
        row = self.db.query(self.models.AlertSettings).one()
        self.assertEqual(json.loads(row.required_ppe), ['Helmet', 'Face Mask'])

    def test_get_and_save_return_same_required_ppe_and_runtime_values(self):
        saved = self.value()
        self.assertEqual(self.api.update_alert_settings(saved, db=self.db), saved.model_dump())
        self.assertEqual(self.api.get_alert_settings(db=self.db), saved.model_dump())
        self.assertEqual(self.config.settings.CONFIDENCE_THRESHOLD, 0.42)
        self.assertEqual(self.config.settings.REQUIRED_PPE, ['Helmet', 'Face Mask'])

    def test_invalid_values_are_rejected_before_database_write(self):
        for changes in [
            {'confidence_threshold': -0.1}, {'confidence_threshold': 1.1}, {'confidence_threshold': float('nan')},
            {'confidence_threshold': True}, {'email_cooldown': -1}, {'whatsapp_cooldown': 86401},
            {'email_cooldown': 2.5}, {'email_enabled': 'true'}, {'required_ppe': []},
            {'required_ppe': ['Helmet', 'Helmet']}, {'required_ppe': ['Boots']},
            {'email_enabled': True, 'email_recipients': 'invalid'},
            {'whatsapp_enabled': True, 'whatsapp_recipient': 'invalid'},
        ]:
            with self.subTest(changes=changes), self.assertRaises(ValidationError):
                self.value(**changes)
        self.assertEqual(self.db.query(self.models.AlertSettings).count(), 0)

    def test_invalid_stored_values_fail_before_partial_runtime_changes(self):
        self.api.update_alert_settings(self.value(), db=self.db)
        row = self.db.query(self.models.AlertSettings).one(); row.confidence_threshold = 9; self.db.commit()
        restart = fresh_config().settings
        with self.assertRaises(ValidationError):
            runtime_settings.restore_settings(self.database.SessionLocal, self.models.AlertSettings, restart)
        self.assertEqual(restart.CONFIDENCE_THRESHOLD, 0.5)
        self.assertEqual(restart.REQUIRED_PPE, ['Helmet', 'Safety Vest', 'Face Mask'])

    def test_legacy_null_policy_uses_all_three_default_without_updating_row(self):
        self.db.add(self.models.AlertSettings(email_recipients='', whatsapp_recipient='')); self.db.commit()
        result = runtime_settings.restore_settings(self.database.SessionLocal, self.models.AlertSettings, self.config.settings)
        self.assertEqual(result.required_ppe, ['Helmet', 'Safety Vest', 'Face Mask'])
        self.assertIsNone(self.db.query(self.models.AlertSettings).one().required_ppe)

    def test_invalid_stored_policy_json_has_clear_error_and_no_runtime_changes(self):
        self.api.update_alert_settings(self.value(), db=self.db)
        row = self.db.query(self.models.AlertSettings).one(); row.required_ppe = 'bad json'; self.db.commit()
        restart = fresh_config().settings
        with self.assertRaisesRegex(ValueError, 'Saved required PPE is invalid JSON'):
            runtime_settings.restore_settings(self.database.SessionLocal, self.models.AlertSettings, restart)
        self.assertEqual(restart.REQUIRED_PPE, ['Helmet', 'Safety Vest', 'Face Mask'])

    def test_legacy_settings_migration_adds_only_column_and_preserves_values(self):
        engine = self.database.engine
        # Only this disposable database is changed.
        with engine.begin() as conn:
            conn.execute(text('DROP TABLE alert_settings'))
            conn.execute(text('CREATE TABLE alert_settings (id INTEGER PRIMARY KEY, confidence_threshold FLOAT)'))
            conn.execute(text('INSERT INTO alert_settings VALUES (1, 0.73)'))
        self.database.ensure_alert_settings_columns(engine)
        self.database.ensure_alert_settings_columns(engine)
        with engine.connect() as conn:
            self.assertEqual(tuple(conn.execute(text('SELECT * FROM alert_settings')).one()), (1, 0.73, None, None))
            self.assertEqual(conn.execute(text('PRAGMA integrity_check')).scalar(), 'ok')

    def test_startup_restores_before_starting_debug_receiver_or_serving_requests(self):
        tree = ast.parse((BACKEND / 'main.py').read_text(encoding='utf-8'))
        startup = next(n for n in ast.walk(tree) if isinstance(n, ast.AsyncFunctionDef) and n.name == 'startup_event')
        first = startup.body[0]
        self.assertIsInstance(first.value, ast.Await)
        self.assertEqual(first.value.value.func.id, 'run_in_threadpool')
        self.assertEqual(first.value.value.args[0].id, 'restore_settings')

    def test_actual_startup_hook_restores_from_temporary_database(self):
        saved = self.value()
        self.api.update_alert_settings(saved, db=self.db)
        config = fresh_config()
        config.settings.DATABASE_URL = self.config.settings.DATABASE_URL
        config.settings.SCREENSHOT_DIR = str(Path(self.temp.name) / 'screenshots')
        api = ModuleType('api')
        for name in ('health', 'upload', 'violations', 'stats', 'settings', 'cameras'):
            setattr(api, name, type('RouteModule', (), {'router': APIRouter()})())
        db = ModuleType('db'); db.__path__ = []
        ws = ModuleType('websocket'); ws.__path__ = []
        modules = {'config': config, 'api': api, 'db': db, 'db.database': self.database,
                   'db.models': self.models, 'runtime_settings': runtime_settings,
                   'api.system': type('SystemModule', (), {'router': APIRouter()})(),
                   'websocket': ws, 'websocket.manager': type('WSModule', (), {'router': APIRouter()})()}
        with patch.dict(sys.modules, modules), patch.object(sys, 'path', sys.path.copy()), contextlib.redirect_stdout(io.StringIO()):
            main = load_source('isolated_startup_app', BACKEND / 'main.py')
            asyncio.run(main.startup_event())
        self.assertEqual(config.settings.CONFIDENCE_THRESHOLD, saved.confidence_threshold)
        self.assertEqual(config.settings.EMAIL_COOLDOWN_SECONDS, saved.email_cooldown)
        self.assertEqual(config.settings.REQUIRED_PPE, saved.required_ppe)
        self.assertFalse(config.settings.ENABLE_EMAIL_ALERTS)


if __name__ == '__main__':
    unittest.main()
