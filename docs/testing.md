# Testing and reproducibility

Use a disposable SQLite/evidence copy, preview delivery and the configured temporary admin/key. Never import/start the application against the real database just to run QA.

## Required process split

```powershell
python -B -m unittest backend.test_detection_model backend.test_ppe_association backend.test_ppe_defaults backend.test_status backend.test_live_stream backend.test_mask_visibility backend.test_violation_workflow backend.test_uploads backend.test_saved_settings backend.test_alerts
python -B -m unittest backend.test_camera_capture
python -B -m unittest backend.test_launchers
python -B -m unittest backend.test_security
python -B -m unittest backend.test_reliability
python -B -m unittest backend.test_evaluation
python -B -m unittest backend.test_product
python -B -m unittest backend.test_demo
```

Do not combine the original twelve modules in one process: cv2 crashes on this Windows machine. The phase runner preserves the split and saves commands/output:

```powershell
python -B tools/verify_phase.py --phase 5 --extra backend.test_security backend.test_reliability backend.test_evaluation backend.test_product backend.test_demo
```

It also runs all `frontend/test/*.test.mjs`, rendering assertions in `ui_status.test.cjs`, and Vite production build. Isolated tests use temporary DBs/fake captures/fake transports. Live-mode transport tests explicitly confirm only fake configurations; no real SMTP/Twilio is contacted. A Starlette/httpx test-client deprecation warning remains third-party output.

## Real-model tools (read-only inputs)

```powershell
python -B backend/tools/evaluate_onnx.py --model backend/best.onnx --split I:/AntiGRavity/My_FYP_Dataset/test --output docs/evidence/phase3/test
python -B backend/tools/evaluate_onnx.py --model backend/best.onnx --split I:/AntiGRavity/My_FYP_Dataset/valid --output docs/evidence/phase3/valid
python -B backend/tools/validate_model.py --model backend/best.onnx --images-dir I:/AntiGRavity/My_FYP_Dataset/test/images --output docs/evidence/phase3/model-validation.json
python -B backend/tools/violation_eval.py --predictions docs/evidence/phase3/test/predictions.json --output docs/evidence/phase3/test-workers
python -B backend/tools/benchmark.py --video <temporary-video.mp4> --frames 120 --output <new-output-directory>
python -B backend/tools/sanity_check.py --output-dir <new-directory-outside-repo>
python -B tools/project_facts.py
```

Choose fresh output directories to preserve prior release evidence. `evaluate_onnx.py` uses the production detector/preprocessing/NMS, records image/label/model hashes and class map, and writes precision/recall/AP/confusion/PR outputs. It retains confidence 0.50: AP is explicitly truncated at this cutoff. Both real splits carry leakage warnings.

`violation_eval.py` verifies cached model/image/label hashes, reruns actual association/face checks, and reports exploratory worker metrics/error examples. Optional `--visibility <json>` expects `{filename: {zero-based-person-label-index: true/false}}` from independent human labels. Unknown face absence is not negative mask truth. [Limitations](limitations.md).

`benchmark.py` uses paced replay, real inference/annotation and the bounded frame-ACK loop. Its local sink excludes network/browser delay. Preview timing measures MIME construction/attachment, not SMTP/DB latency. It opens neither database nor transports.

## Browser QA

Final QA scripts under `tools/qa_final_*.cjs` take the installed Playwright module directory and temporary `auth.json` (never commit credentials). Chrome executable is configured for this Windows host. Start the disposable backend/Vite and loopback video fixture first. `qa_security.cjs`, `qa_reliability.cjs` and `qa_product.cjs` cover the phase-specific checks. [Final matrix/results](qa-report.md) distinguishes direct observation, UI fixtures and untested hardware.

## Demo and clean installation

```powershell
python -m venv <temporary-venv>
<temporary-venv>/Scripts/python -m pip install -r backend/requirements.txt
<temporary-venv>/Scripts/python -m pip check
python -B backend/tools/make_demo_data.py --source-copy <temporary-trial.db> --evidence-copy <temporary-screenshots> --limit 20
```

The demo tool creates a new system-temp directory with copied real incident values/evidence and a DEMO marker, without touching protected originals/backups. [Installation evidence](evidence/phase1/pip-install-report.json), [demo output](evidence/phase5/demo-output.json). Follow README for secrets/origins and real launcher commands; do not claim physical webcam, GPU, real delivery or native Linux success from a mocked/unit check.
