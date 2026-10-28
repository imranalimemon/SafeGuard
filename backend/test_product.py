"""Observation denominators, persistence and delivery gate; disposable SQLite only."""
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from pydantic import ValidationError
from fastapi import HTTPException
from backend import test_saved_settings as fixture_module
from backend.test_ppe_defaults import BACKEND, load_source, fresh_config
from backend.observations import record_observation
from backend import runtime_settings

class ProductTests(unittest.TestCase):
    def setUp(self):
        self.fixture=fixture_module.SavedSettingsTests('test_saved_settings_survive_fresh_runtime_and_session')
        self.fixture.setUp();self.addCleanup(self.fixture.doCleanups)
        self.db=self.fixture.db;self.models=self.fixture.models

    def test_real_counts_include_compliant_unknown_and_empty_frames(self):
        workers=[{'status':'COMPLIANT','mask_assessment':'detected'},{'status':'VIOLATION','mask_assessment':'not assessable'},{'status':'NOT_ASSESSABLE','mask_assessment':'not assessable'}]
        record_observation(self.db,workers,'camera:1',self.models.WorkerObservation)
        record_observation(self.db,[],'camera:1',self.models.WorkerObservation)
        self.db.commit()
        with patch.dict(sys.modules,{'config':self.fixture.config,'db.database':self.fixture.database,'db.models':self.models,'api.violations':SimpleNamespace(_serialize_violation=lambda row:{})}):
            api=load_source('isolated_analytics',BACKEND/'api/stats.py')
        result=api.analytics(db=self.db)
        row=result['compliance_trend'][0]
        self.assertEqual(row['worker_observations'],3)
        self.assertEqual(row['frames_analyzed'],2)
        self.assertEqual(row['assessed_denominator'],2)
        self.assertEqual(row['unknown'],1)
        self.assertEqual(row['compliance_rate'],50)
        self.assertEqual(self.db.query(self.models.Violation).count(),0)

    def test_empty_history_has_no_fabricated_denominator(self):
        with patch.dict(sys.modules,{'config':self.fixture.config,'db.database':self.fixture.database,'db.models':self.models,'api.violations':SimpleNamespace(_serialize_violation=lambda row:{})}):
            api=load_source('isolated_empty_analytics',BACKEND/'api/stats.py')
        result=api.analytics(db=self.db)
        self.assertEqual(result['compliance_trend'],[])
        self.assertEqual(result['violations_per_day'],[])

    def test_frame_skip_validation_and_restart(self):
        value=self.fixture.value(frame_skip=7)
        self.fixture.api.update_alert_settings(value,db=self.db)
        config=fresh_config().settings
        runtime_settings.restore_settings(self.fixture.database.SessionLocal,self.models.AlertSettings,config)
        self.assertEqual(config.STREAM_DETECTION_INTERVAL,7)
        self.assertEqual(self.db.query(self.models.AlertSettings).one().frame_skip,7)
        for invalid in (0,31,2.5,True):
            with self.assertRaises(ValidationError):self.fixture.value(frame_skip=invalid)

    def test_preview_cannot_be_overridden_by_confirmation(self):
        config=self.fixture.config.settings
        self.assertEqual(config.ALERT_DELIVERY_MODE,'preview')
        with self.assertRaises(HTTPException) as error:
            self.fixture.api.change_delivery(self.fixture.api.DeliveryUpdate(mode='live',confirmation='ENABLE LIVE ALERTS'))
        self.assertEqual(error.exception.status_code,409)
        self.assertFalse(config.ALERT_LIVE_CONFIRMED)

    def test_live_requires_confirmation_each_process_without_sending(self):
        config=self.fixture.config
        config.settings.ALERT_DELIVERY_MODE='live'
        config.settings.ENABLE_EMAIL_ALERTS=True
        with patch.dict(sys.modules,{'config':config}):
            content=load_source('isolated_delivery_content',BACKEND/'alerts/content.py')
        fake_email=SimpleNamespace(smtp_configuration=lambda:{'configured':True})
        with patch.dict(sys.modules,{'alerts.content':content,'alerts.email_service':fake_email}):
            self.assertTrue(content.preview_only())
            with self.assertRaises(HTTPException):self.fixture.api.change_delivery(self.fixture.api.DeliveryUpdate(mode='live'))
            result=self.fixture.api.change_delivery(self.fixture.api.DeliveryUpdate(mode='live',confirmation='ENABLE LIVE ALERTS'))
            self.assertEqual(result['effective_mode'],'live')
            self.assertFalse(content.preview_only())
            self.fixture.api.change_delivery(self.fixture.api.DeliveryUpdate(mode='preview'))
            self.assertTrue(content.preview_only())

if __name__=='__main__':unittest.main()
