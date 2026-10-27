"""PPE configuration/API defaults; SQLite tests use fresh in-memory databases only."""
import importlib.util
import os
from pathlib import Path
import sys
from types import ModuleType
import unittest
from unittest.mock import patch


BACKEND = Path(__file__).parent


def load_source(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def fresh_config(environment=None):
    dotenv = ModuleType("dotenv")
    dotenv.load_dotenv = lambda **kwargs: None
    with patch.dict(os.environ, environment or {}, clear=True), \
            patch.dict(sys.modules, {"dotenv": dotenv}), patch("os.makedirs"):
        return load_source("isolated_ppe_default_config", BACKEND / "config.py")


class PPEDefaultTests(unittest.TestCase):
    def test_default_requires_all_three_ppe(self):
        self.assertEqual(fresh_config().settings.REQUIRED_PPE, ["Helmet", "Safety Vest", "Face Mask"])

    def test_legacy_two_item_environment_cannot_disable_mask_objective(self):
        config = fresh_config({"REQUIRED_PPE": "Helmet,Safety Vest"})
        self.assertEqual(config.settings.REQUIRED_PPE, ["Helmet", "Safety Vest", "Face Mask"])

    def test_default_confidence_stays_at_half(self):
        self.assertEqual(fresh_config().settings.CONFIDENCE_THRESHOLD, 0.5)

    def check_database_settings(self, legacy_policy=False, existing_row=False):
        config = fresh_config(
            {"REQUIRED_PPE": "Helmet,Safety Vest"} if legacy_policy else {}
        )
        config.settings.DATABASE_URL = "sqlite:///:memory:"
        db_package = ModuleType("db")
        db_package.__path__ = [str(BACKEND / "db")]
        with patch.dict(sys.modules, {"config": config, "db": db_package}):
            database = load_source("db.database", BACKEND / "db" / "database.py")
            sys.modules["db.database"] = database
            models = load_source("db.models", BACKEND / "db" / "models.py")
            sys.modules["db.models"] = models
            api = load_source("isolated_ppe_settings_api", BACKEND / "api" / "settings.py")
            database.Base.metadata.create_all(database.engine)
            try:
                with database.SessionLocal() as session:
                    if existing_row:
                        session.add(models.AlertSettings(email_recipients="unchanged@example.invalid"))
                        session.commit()
                    response = api.get_alert_settings(db=session)
                    self.assertEqual(
                        response["required_ppe"],
                        ["Helmet", "Safety Vest", "Face Mask"],
                    )
                    self.assertEqual(session.query(models.AlertSettings).count(), int(existing_row))
                    if existing_row:
                        self.assertEqual(response["email_recipients"], "unchanged@example.invalid")
            finally:
                database.engine.dispose()

    def test_fresh_database_starts_with_all_three_ppe(self):
        self.check_database_settings()

    def test_fresh_database_ignores_legacy_two_item_policy(self):
        self.check_database_settings(legacy_policy=True)

    def test_existing_settings_row_is_preserved(self):
        self.check_database_settings(existing_row=True)


if __name__ == "__main__":
    unittest.main()
