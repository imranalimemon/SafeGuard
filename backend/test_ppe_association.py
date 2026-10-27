"""Synthetic-box tests; config, database, model, and alert services are not loaded."""
import ast
from datetime import datetime, timedelta
import importlib.util
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import patch


BACKEND = Path(__file__).parent


def load_module(name, filename):
    config = ModuleType("config")
    config.settings = SimpleNamespace(
        PERSON_CLASS_ID=2,
        REQUIRED_PPE=["Helmet", "Safety Vest", "Face Mask"],
        VIOLATION_COOLDOWN_SECONDS=10,
    )
    spec = importlib.util.spec_from_file_location(name, BACKEND / "detection" / filename)
    module = importlib.util.module_from_spec(spec)
    with patch.dict(sys.modules, {"config": config}):
        spec.loader.exec_module(module)
    return module


logic = load_module("isolated_violation_logic", "violation_logic.py")
dedup_module = load_module("isolated_deduplicator", "deduplicator.py")


def detection(class_id, bbox):
    return {
        "class_id": class_id,
        "class_name": {0: "Face Mask", 1: "Helmet", 2: "Person", 3: "Safety Vest"}[class_id],
        "bbox": bbox,
        "confidence": 0.9,
    }


def dedup_call_sites():
    # Execute only the actual should_log expressions, never import route modules.
    # This checks that image/video/live callers really pass the worker's box.
    sites = []
    for filename in ("api/upload.py", "websocket/manager.py"):
        tree = ast.parse((BACKEND / filename).read_text(encoding="utf-8"))
        calls = sorted((
            node for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "deduplicator"
            and node.func.attr == "should_log"
        ), key=lambda node: node.lineno)
        for index, call in enumerate(calls):
            call.keywords.append(ast.keyword(arg="now", value=ast.Name(id="now", ctx=ast.Load())))
            expression = ast.fix_missing_locations(ast.Expression(body=call))
            sites.append((f"{filename}:{index + 1}", compile(expression, filename, "eval")))
    return sites


CALL_SITES = dedup_call_sites()


def should_log_at_site(site, deduplicator, bbox, now, missing=None, source="camera:1"):
    v = {"person_bbox": bbox, "missing_ppe": missing if missing is not None else ["Helmet"]}
    return eval(site, {"__builtins__": {}}, {
        "deduplicator": deduplicator, "v": v, "source": source, "now": now,
    })


class PPEAssociationTests(unittest.TestCase):
    def setUp(self):
        self.person = detection(2, [100, 100, 200, 400])

    def assert_missing(self, ppe, required):
        results = logic.compute_violations([self.person, ppe], [required], face_assessor=lambda frame, box: True)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["status"], "VIOLATION")
        self.assertEqual(results[0]["missing_ppe"], [required])

    def test_helmet_at_feet_does_not_count_as_worn(self):
        self.assert_missing(detection(1, [125, 350, 175, 380]), "Helmet")

    def test_vest_at_feet_does_not_count_as_worn(self):
        self.assert_missing(detection(3, [110, 350, 190, 390]), "Safety Vest")

    def test_vest_at_head_does_not_count_as_worn(self):
        self.assert_missing(detection(3, [110, 100, 190, 130]), "Safety Vest")

    def test_orphan_helmet_does_not_create_worker_or_violation(self):
        self.assertEqual(logic.compute_violations([detection(1, [100, 100, 140, 130])]), [])

    def test_orphan_vest_does_not_create_worker_or_violation(self):
        self.assertEqual(logic.compute_violations([detection(3, [100, 150, 180, 250])]), [])

    def test_orphan_mask_does_not_create_worker_or_violation(self):
        self.assertEqual(logic.compute_violations([detection(0, [100, 100, 130, 120])]), [])

    def test_unclaimed_ppe_does_not_add_worker_beside_real_person(self):
        results = logic.compute_violations([
            self.person, detection(1, [500, 100, 540, 130]),
        ], ["Helmet"])
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["person_bbox"], self.person["bbox"])
        self.assertEqual(results[0]["missing_ppe"], ["Helmet"])

    def test_person_with_helmet_and_vest_is_compliant_when_both_required(self):
        results = logic.compute_violations([
            self.person, detection(1, [125, 95, 175, 135]),
            detection(3, [110, 170, 190, 280]),
        ], ["Helmet", "Safety Vest"])
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["status"], "COMPLIANT")
        self.assertEqual(results[0]["missing_ppe"], [])

    def test_person_with_nothing_is_violation(self):
        result = logic.compute_violations([self.person], ["Helmet", "Safety Vest"])[0]
        self.assertEqual(result["status"], "VIOLATION")
        self.assertEqual(result["missing_ppe"], ["Helmet", "Safety Vest"])

    def test_mask_still_required_when_configured(self):
        result = logic.compute_violations([
            self.person, detection(1, [125, 95, 175, 135]),
            detection(3, [110, 170, 190, 280]),
        ], ["Helmet", "Safety Vest", "Face Mask"], face_assessor=lambda frame, box: True)[0]
        self.assertEqual(result["missing_ppe"], ["Face Mask"])

    def test_close_up_mask_from_fac_test_00005_is_associated(self):
        # Actual detector boxes from fac_test_00005, reproduced without the image/model.
        result = logic.compute_violations([
            detection(2, [18, 191, 336, 640]),
            detection(0, [83, 277, 256, 483]),
        ], ["Face Mask"])[0]
        self.assertEqual(result["has_ppe"], ["Face Mask"])
        self.assertEqual(result["status"], "COMPLIANT")

    def test_mask_at_feet_is_not_associated(self):
        self.assert_missing(detection(0, [125, 350, 175, 380]), "Face Mask")

    def test_default_mask_is_not_assessable_without_face_evidence(self):
        result = logic.compute_violations([
            self.person, detection(1, [125, 95, 175, 135]),
            detection(3, [110, 170, 190, 280]),
        ])[0]
        self.assertEqual(result["status"], "NOT_ASSESSABLE")
        self.assertEqual(result["mask_assessment"], "not assessable")

    def test_empty_requirements_use_all_three_with_mask_gate(self):
        result = logic.compute_violations([self.person], [], face_assessor=lambda frame, box: True)[0]
        self.assertEqual(result["missing_ppe"], ["Helmet", "Safety Vest", "Face Mask"])

    def test_overlapping_workers_each_keep_their_own_helmet(self):
        results = logic.compute_violations([
            detection(2, [100, 100, 220, 400]),
            detection(2, [140, 100, 260, 400]),
            detection(1, [130, 100, 170, 130]),
            detection(1, [190, 100, 230, 130]),
        ], ["Helmet"])
        self.assertEqual(len(results), 2)
        self.assertEqual([v["status"] for v in results], ["COMPLIANT", "COMPLIANT"])

    def test_one_helmet_cannot_satisfy_two_overlapping_workers(self):
        results = logic.compute_violations([
            detection(2, [100, 100, 220, 400]),
            detection(2, [140, 100, 260, 400]),
            detection(1, [130, 100, 170, 130]),
        ], ["Helmet"])
        self.assertEqual(len(results), 2)
        self.assertEqual(sorted(v["status"] for v in results), ["COMPLIANT", "VIOLATION"])


class WorkerDeduplicationTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 1, 1)

    def test_two_workers_missing_same_ppe_are_both_logged_at_every_call_site(self):
        self.assertEqual(len(CALL_SITES), 3)
        boxes = [[100, 100, 220, 400], [140, 100, 260, 400]]
        for name, site in CALL_SITES:
            with self.subTest(site=name):
                dedup = dedup_module.ViolationDeduplicator(10)
                results = logic.compute_violations([detection(2, box) for box in boxes], ["Helmet"])
                self.assertEqual([
                    should_log_at_site(site, dedup, v["person_bbox"], self.now, v["missing_ppe"])
                    for v in results
                ], [True, True])
                self.assertEqual([
                    should_log_at_site(site, dedup, box, self.now + timedelta(seconds=1))
                    for box in reversed(boxes)
                ], [False, False])

    def test_same_worker_box_jitter_is_suppressed_even_across_grid_boundary(self):
        for name, site in CALL_SITES:
            with self.subTest(site=name):
                dedup = dedup_module.ViolationDeduplicator(10)
                self.assertTrue(should_log_at_site(site, dedup, [77, 100, 177, 400], self.now))
                for shift in (1, -2, 3, -1):
                    self.assertFalse(should_log_at_site(
                        site, dedup, [77 + shift, 100, 177 + shift, 400],
                        self.now + timedelta(seconds=1),
                    ))

    def test_worker_can_log_again_after_cooldown(self):
        for name, site in CALL_SITES:
            with self.subTest(site=name):
                dedup = dedup_module.ViolationDeduplicator(10)
                box = [100, 100, 200, 400]
                self.assertTrue(should_log_at_site(site, dedup, box, self.now))
                self.assertFalse(should_log_at_site(site, dedup, box, self.now + timedelta(seconds=9)))
                self.assertTrue(should_log_at_site(site, dedup, box, self.now + timedelta(seconds=10)))

    def test_changed_missing_items_have_separate_cooldown(self):
        for name, site in CALL_SITES:
            with self.subTest(site=name):
                dedup = dedup_module.ViolationDeduplicator(10)
                box = [100, 100, 200, 400]
                self.assertTrue(should_log_at_site(site, dedup, box, self.now, ["Helmet"]))
                self.assertTrue(should_log_at_site(site, dedup, box, self.now, ["Safety Vest", "Helmet"]))
                self.assertFalse(should_log_at_site(site, dedup, box, self.now, ["Helmet", "Safety Vest"]))

    def test_compliant_worker_is_never_logged(self):
        for name, site in CALL_SITES:
            with self.subTest(site=name):
                dedup = dedup_module.ViolationDeduplicator(10)
                self.assertFalse(should_log_at_site(site, dedup, [100, 100, 200, 400], self.now, []))

    def test_cameras_have_separate_cooldowns(self):
        _, site = next(s for s in CALL_SITES if s[0].startswith("websocket/"))
        dedup = dedup_module.ViolationDeduplicator(10)
        box = [100, 100, 200, 400]
        self.assertTrue(should_log_at_site(site, dedup, box, self.now, source="camera:1"))
        self.assertTrue(should_log_at_site(site, dedup, box, self.now, source="camera:2"))


if __name__ == "__main__":
    unittest.main()
