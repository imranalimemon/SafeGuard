"""Additive migration and review API tests on synthetic in-memory SQLite only."""
from datetime import date
import sys
from types import ModuleType
import unittest
from unittest.mock import patch

from sqlalchemy import event, text
# Import ORM before patching sys.modules; unloading/reimporting its global
# registries between isolated modules otherwise creates duplicate registrations.
from sqlalchemy.orm import Session
from fastapi import HTTPException
from backend.test_ppe_defaults import BACKEND, fresh_config, load_source


class ViolationWorkflowTests(unittest.TestCase):
    def setUp(self):
        config = fresh_config()
        config.settings.DATABASE_URL = 'sqlite:///:memory:'
        package = ModuleType('db'); package.__path__ = [str(BACKEND / 'db')]
        with patch.dict(sys.modules, {'config': config, 'db': package}):
            self.database = load_source('db.database', BACKEND / 'db/database.py')
            sys.modules['db.database'] = self.database
            self.models = load_source('db.models', BACKEND / 'db/models.py')
            sys.modules['db.models'] = self.models
            self.api = load_source('isolated_workflow_api', BACKEND / 'api/violations.py')
        self.addCleanup(self.database.engine.dispose)
        with self.database.engine.begin() as conn:
            conn.execute(text('''CREATE TABLE violations (
                id INTEGER PRIMARY KEY, timestamp DATETIME, violation_type VARCHAR,
                person_count INTEGER, violation_count INTEGER, screenshot_path VARCHAR,
                confidence FLOAT, alert_sent BOOLEAN, missing_ppe VARCHAR, details VARCHAR
            )'''))
            conn.execute(text('''INSERT INTO violations VALUES
                (:id, :timestamp, :kind, 1, 1, :path, 0.9, 0, :missing, 'preserve me')'''), [
                {'id': i, 'timestamp': f'2026-10-{26 if i % 2 else 27} 12:00:00',
                 'kind': 'Missing: Helmet' if i % 2 else 'Missing: Face Mask',
                 'path': f'/screenshots/evidence-{i}.jpg',
                 'missing': 'Helmet' if i % 2 else 'Face Mask'} for i in range(1, 107)
            ])
        self.database.ensure_violation_columns(self.database.engine)
        self.db = self.database.SessionLocal()
        self.addCleanup(self.db.close)

    def action(self, action, id=1):
        return self.api.review_violation(id, self.api.ReviewUpdate(action=action), db=self.db)

    def test_migration_preserves_106_legacy_rows_and_is_idempotent(self):
        statements = []
        event.listen(self.database.engine, 'before_cursor_execute', lambda c, cu, s, p, ctx, many: statements.append(s))
        self.database.ensure_violation_columns(self.database.engine)
        self.assertFalse(any('ALTER TABLE' in s for s in statements))
        rows = self.db.query(self.models.Violation).order_by(self.models.Violation.id).all()
        self.assertEqual(len(rows), 106)
        self.assertEqual([r.id for r in rows], list(range(1, 107)))
        for row in rows:
            self.assertEqual(row.details, 'preserve me')
            self.assertEqual(row.screenshot_path, f'/screenshots/evidence-{row.id}.jpg')
            self.assertEqual(row.review_status, 'open')
            self.assertIsNone(row.archived_at)
        self.assertEqual(self.db.execute(text('PRAGMA integrity_check')).scalar(), 'ok')

    def test_acknowledge_persists_status_and_original_timestamp_on_retry(self):
        first = self.action('acknowledge')
        again = self.action('acknowledge')
        self.assertEqual(first['review_status'], 'acknowledged')
        self.assertIsNotNone(first['acknowledged_at'])
        self.assertEqual(first['acknowledged_at'], again['acknowledged_at'])
        self.assertEqual(self.db.query(self.models.Violation).count(), 106)

    def test_escalation_persists_and_acknowledging_does_not_downgrade_it(self):
        first = self.action('escalate')
        again = self.action('acknowledge')
        self.assertEqual(again['review_status'], 'escalated')
        self.assertEqual(first['escalated_at'], again['escalated_at'])
        self.assertIsNotNone(again['acknowledged_at'])

    def test_archive_hides_default_list_without_deleting_row_or_evidence_reference(self):
        archived = self.action('archive')
        self.assertEqual(self.action('archive')['archived_at'], archived['archived_at'])
        self.assertEqual(self.api.get_violations(page=1, db=self.db)['total'], 105)
        result = self.api.get_violations(page=1, archived=True, db=self.db)
        self.assertEqual(result['total'], 1)
        self.assertEqual(result['items'][0]['screenshot_path'], '/screenshots/evidence-1.jpg')
        self.assertEqual(self.db.query(self.models.Violation).count(), 106)

    def test_filters_dates_review_camera_and_pagination_share_same_query(self):
        row = self.db.get(self.models.Violation, 1); row.source = 'camera:7'; self.db.commit()
        self.action('acknowledge')
        result = self.api.get_violations(page=1, per_page=1, camera_id=7,
            date_from=date(2026, 10, 26), date_to=date(2026, 10, 26),
            violation_type='Helmet', review_status='acknowledged', db=self.db)
        self.assertEqual(result['total'], 1)
        self.assertEqual(result['items'][0]['id'], 1)
        before = self.db.query(self.models.Violation).count()
        self.api.get_violations(page=1, per_page=200, db=self.db)
        self.assertEqual(self.db.query(self.models.Violation).count(), before)

    def test_unknown_id_does_not_create_record(self):
        with self.assertRaises(HTTPException) as error:
            self.action('archive', 9999)
        self.assertEqual(error.exception.status_code, 404)
        self.assertEqual(self.db.query(self.models.Violation).count(), 106)


if __name__ == '__main__':
    unittest.main()
