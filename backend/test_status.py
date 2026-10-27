"""Health and statistics checks with a fake model and in-memory SQLite only."""
from datetime import datetime, timedelta
from types import ModuleType, SimpleNamespace
import sys
import unittest
from unittest.mock import Mock, patch

from backend.test_ppe_defaults import BACKEND, fresh_config, load_source


class BackendStatusTests(unittest.TestCase):
    def setUp(self):
        config = fresh_config()
        config.settings.DATABASE_URL = "sqlite:///:memory:"
        db = ModuleType("db")
        db.__path__ = [str(BACKEND / "db")]
        model = ModuleType("detection.model")
        session = Mock()
        session.get_providers.return_value = ["CPUExecutionProvider"]
        model.get_detector = Mock(return_value=SimpleNamespace(
            model_path="weights/custom_ppe.onnx", session=session,
        ))
        serializer = ModuleType("api.violations")
        serializer._serialize_violation = lambda row: {"id": row.id, "source": row.source}
        modules = patch.dict(sys.modules, {
            "config": config, "db": db, "detection.model": model, "api.violations": serializer,
        })
        modules.start()
        self.addCleanup(modules.stop)
        self.model = model
        self.database = load_source("db.database", BACKEND / "db" / "database.py")
        sys.modules["db.database"] = self.database
        self.models = load_source("db.models", BACKEND / "db" / "models.py")
        sys.modules["db.models"] = self.models
        self.database.Base.metadata.create_all(self.database.engine)
        self.addCleanup(self.database.engine.dispose)
        self.health = load_source("isolated_health_api", BACKEND / "api" / "health.py")
        self.stats = load_source("isolated_stats_api", BACKEND / "api" / "stats.py")

    def test_health_reports_checked_database_and_actual_session_identity(self):
        result = self.health.health()
        self.assertEqual(result["status"], "ok")
        self.assertTrue(result["model_loaded"])
        self.assertTrue(result["db_connected"])
        self.assertEqual(result["model_name"], "custom_ppe.onnx")
        self.assertEqual(result["execution_providers"], ["CPUExecutionProvider"])
        self.model.get_detector.assert_called_once()

    def test_health_reports_gpu_from_session_without_guessing(self):
        self.model.get_detector.return_value.session.get_providers.return_value = [
            "CUDAExecutionProvider", "CPUExecutionProvider",
        ]
        self.assertEqual(self.health.health()["execution_providers"], [
            "CUDAExecutionProvider", "CPUExecutionProvider",
        ])

    def test_model_load_failure_is_degraded(self):
        self.model.get_detector.side_effect = RuntimeError("Missing model")
        result = self.health.health()
        self.assertEqual(result["status"], "degraded")
        self.assertFalse(result["model_loaded"])
        self.assertTrue(result["db_connected"])
        self.assertIsNone(result["model_name"])
        self.assertEqual(result["execution_providers"], [])

    def test_database_failure_is_degraded(self):
        with patch.object(self.database.engine, "connect", side_effect=RuntimeError("Database unavailable")):
            result = self.health.health()
        self.assertEqual(result["status"], "degraded")
        self.assertTrue(result["model_loaded"])
        self.assertFalse(result["db_connected"])

    def test_empty_database_has_real_zero_counts_and_unavailable_compliance(self):
        with self.database.SessionLocal() as db:
            result = self.stats.get_dashboard_stats(db=db)
        self.assertEqual(result["total_violations"], 0)
        self.assertEqual(result["today_violations"], 0)
        self.assertEqual(result["recent_violations"], [])
        self.assertIsNone(result["total_persons_detected"])
        self.assertIsNone(result["compliance_rate"])
        self.assertIsNone(result["avg_confidence"])

    def test_statistics_use_stored_records_without_inventing_worker_totals(self):
        with self.database.SessionLocal() as db:
            db.add_all([
                self.models.Violation(timestamp=datetime.utcnow(), confidence=0.8, missing_ppe="Helmet", source="camera:8"),
                self.models.Violation(timestamp=datetime.utcnow() - timedelta(days=2), confidence=None, missing_ppe="Safety Vest", source="image_upload"),
            ])
            db.commit()
            result = self.stats.get_dashboard_stats(db=db)
            self.assertEqual(db.query(self.models.Violation).count(), 2)
        self.assertEqual(result["total_violations"], 2)
        self.assertEqual(result["today_violations"], 1)
        self.assertEqual(result["violations_by_type"], {"Helmet": 1, "Face Mask": 0, "Safety Vest": 1})
        self.assertEqual(result["avg_confidence"], 0.8)
        self.assertIsNone(result["compliance_rate"])
        self.assertIsNone(result["total_persons_detected"])


if __name__ == "__main__":
    unittest.main()
