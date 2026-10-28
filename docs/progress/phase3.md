# Phase 3 — reproducible evaluation and model validation

## Changes and files

Added `backend/tools/evaluation.py` (pure metric/label helpers), `evaluate_onnx.py` (real-model detector evaluation), `validate_model.py` (shape/class metadata/five-image checks), `violation_eval.py` (full worker pipeline using hash-verified detector outputs), `backend/test_evaluation.py`, and `docs/model-swap.md`. Saved outputs are under `docs/evidence/phase3/`. No dataset, model, training artifact, database or detector setting was modified.

## Detector results

| Split | Images | Mask precision / recall | Helmet precision / recall | Person precision / recall | Vest precision / recall |
|---|---:|---|---|---|---|
| Test | 1224 | 0.9904 / 0.9786 | 0.9536 / 0.9137 | 0.9713 / 0.7596 | 0.9617 / 0.9464 |
| Validation | 1222 | 0.9850 / 0.9398 | 0.9547 / 0.9090 | 0.9426 / 0.8027 | 0.9521 / 0.9313 |

Source commands: `python -B backend/tools/evaluate_onnx.py --split I:/AntiGRavity/My_FYP_Dataset/test --output docs/evidence/phase3/test` and the same command with `valid`. Exact executable/commands, model hash, threshold, IoU, class map and timings are recorded in [test metrics](../evidence/phase3/test/metrics.json) and [validation metrics](../evidence/phase3/valid/metrics.json). Each output folder contains per-image predictions, image/label hashes, AP50/AP50-95, PR curves and a confusion matrix. The test confusion matrix was opened and inspected.

**Leakage warning:** these test/validation images were pooled into the augmentation workflow. Scores are likely optimistic and cannot demonstrate leakage-free generalization. No clean retrain was attempted.

**AP limitation:** the explicit instruction to retain detector thresholds was respected. These are 101-point interpolated AP values over detections retained at confidence 0.50, not full-score COCO/Ultralytics AP. PR curves stop at that cutoff. The reports label this limitation. Comparing them directly with training-tool AP would be misleading.

## Worker-level results and limits

Commands: `python -B backend/tools/violation_eval.py --predictions docs/evidence/phase3/test/predictions.json --output docs/evidence/phase3/test-workers` and the corresponding `valid` command. Model, image and label hashes are verified before cache reuse; association and the actual face-visibility rule run on each image.

[Exploratory test results](../evidence/phase3/test-workers/worker-metrics.json): violation precision 0.9675, recall 0.7241. [Validation results](../evidence/phase3/valid-workers/worker-metrics.json): 0.9340 / 0.7749. These are **geometric label-proxy scores**, not human-verified compliance accuracy. Broad anatomical annotation association is independent of the production association score; ambiguous assignments become unknown. Missing labels are treated as absence only under an exhaustive-annotation assumption.

The derived truth had **zero confirmed fully compliant workers** on both splits; compliant precision/recall are therefore `null`. Mask visibility was unknown for 4090 of 4414 test workers and 3383 of 3868 validation workers. The most frequent error was a missed worker (1061 test / 763 validation), followed by helmet mismatches and spurious workers. Eight annotated examples per split and per-image truth/prediction details are saved alongside the worker metrics. A `--visibility` JSON can supply independent human-visible-face labels; the model's own face heuristic is never used as ground truth.

## Model contract and rollback

Command: `python -B backend/tools/validate_model.py --images-dir I:/AntiGRavity/My_FYP_Dataset/test/images --output docs/evidence/phase3/model-validation.json`. [Saved output](../evidence/phase3/model-validation.json) confirms declared input `1x3x640x640`, output `1x8x8400`, ONNX metadata order Face Mask / Helmet / Person / Safety Vest, CPU provider and five finite real-image inferences. Model SHA-256: `8a402e16f3fbb966cd804dbc51f0bf94a582b4d1513041fea0874ae72db189d1`. Metadata checks declared order; learned semantics still need visual review for a replacement candidate. No swap was performed. [Reversible procedure](../model-swap.md) records both hashes and preserves an old model outside git.

## Tests

Command: `<fresh-venv-python> -B tools/verify_phase.py --phase 3 --extra backend.test_security backend.test_reliability backend.test_evaluation`. All exit codes zero: 130 core, 3 camera, 2 launcher, 9 security, 6 reliability, 9 evaluation tests; frontend tests/rendering and production build passed. [Commands/output](../evidence/phase3/tests.json). Synthetic cases cover perfect predictions, duplicates/high-confidence false positives, class confusion, unreachable recall, invalid YOLO labels, class-order/shape rejection, unknown face truth, association ambiguity, and worker misses/false positives.

## Needs Imran

- Approve a separate evaluation-only low confidence floor if full-score benchmark AP is required. Runtime threshold remains 0.50. Current outputs deliberately report threshold-truncated AP.
- Prepare a leakage-free held-out split and clean retrain before claiming final generalization metrics.
- Manually label a balanced worker subset with PPE relationships, annotation completeness and face visibility. Current box labels cannot validate full three-item compliance precision/recall or missing-mask recall. Do not paste the exploratory proxy numbers into the thesis as validated safety-system accuracy.
- Visually review any future candidate model on representative masks, helmets, vests, occlusions and distant workers before following the swap procedure.
