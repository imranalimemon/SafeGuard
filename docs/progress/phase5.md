# Phase 5 — documentation, launchers and final delivery QA

## Delivered

Updated README and implementation docs; added architecture, honest limitations, testing/reproduction instructions and thesis notes generated from saved facts. Read training args/results and dataset scripts without executing them; extracted counts/configuration/logged metrics with source hashes. No original proposal/presentation, training/data/model files or real database was edited.

Both one-command launchers now align local origins and runtime dependency checks. The shell launcher selects an interpreter that actually imports the runtime instead of stopping at a nonworking python alias. Actual `start.bat` and `start.sh` under Git Bash started backend + Vite and passed authenticated Chrome health checks. Native Linux hardware remains unverified.

`make_demo_data.py` accepts temporary source copies only, creates a fresh temporary DB, copies actual incident values/evidence, and marks the application DEMO. The real run copied 20 records, integrity ok; Chrome saw the DEMO banner. A Windows handle-leak test caught that SQLite's transaction context did not close connections; explicit closing fixed it and the test now passes.

Final browser QA also exposed external Google-font load timeouts and duplicate Settings field IDs. Fonts/licenses are bundled locally; IDs are unique and covered by a rendering assertion. Added an application SVG favicon. No thresholds, NMS, model weights or PPE rules changed. Temporary settings tests restored confidence 0.50, all three PPE requirements and frame interval 3.

## Files

Documentation: `README.md`, `docs/backend.md`, `frontend.md`, `database.md`, `ml-violations-alerts.md`, `backend_api_contract.md`, `suggestion.md`, `user-guide.md`, `qa-report.md`; new `architecture.md`, `limitations.md`, `testing.md`, `final-year-report-notes.md`, this progress report, `docs/evidence/phase5/` and final browser screenshots under `docs/screenshots/`.

Runtime/test changes: `start.bat`, `start.sh`, `backend/main.py`, `backend/api/health.py`, `backend/tools/make_demo_data.py`, `backend/test_demo.py`, `frontend/src/components/layout/Navbar.jsx`, `frontend/src/pages/SettingsPage.jsx`, `frontend/src/index.css`, `frontend/test/ui_status.test.cjs`, `frontend/index.html`, `frontend/public/safeguard.svg`, `frontend/public/fonts/` (assets/licenses/source manifest).

Reproduction tools: `tools/vendor_fonts.py`, `project_facts.py`, `report_notes.py`, `final_audit.py`, `qa_report.py`, `qa_launcher.cjs`, `qa_final_live.cjs`, `qa_final_cameras.cjs` (incident/export cases), `qa_final_uploads.cjs`, `qa_final_errors.cjs`, `qa_final_violations.cjs` (settings/restart cases). The generated `files-changed.json` lists individual Phase 5 paths.

## Tests and observed evidence

Final command: `<fresh-venv-python> -B tools/verify_phase.py --phase 5 --extra backend.test_security backend.test_reliability backend.test_evaluation backend.test_product backend.test_demo`. [Commands and zero exit codes](../evidence/phase5/tests.json). Backend: **166 tests passed** across the required separate processes; frontend: **20 Node tests**, rendering checks and production build passed. Known third-party Starlette/httpx and Node util._extend deprecation messages and Vite's bundle-size warning remain; application deprecations requested in Phase 1 are removed.

[Final QA report](../qa-report.md) indexes **42 observed browser cases**, all passed in the final collection; additional settings/restart, launchers, demo, login and three-size layout checks are separately recorded. No page JavaScript errors or unexpected telemetry remained after identifying deliberate failure/validation tests and cancelled navigation/session requests. Raw telemetry is saved; not every request is claimed successful.

- [Batch launcher](../evidence/phase5/launcher-bat.json), [shell launcher](../evidence/phase5/launcher-sh.json), [actual demo](../evidence/phase5/launcher-demo.json).
- [Settings save/restart and actual Offline/Online](../evidence/phase5/settings-browser.json).
- [Read-only facts extraction](../evidence/phase5/project-facts.json), generated [thesis notes](../final-year-report-notes.md).
- [Protected-file/data audit](../evidence/phase5/final-audit.json): `.env`, both real DB files, original PDF/PPT hashes unchanged. All original 136 disposable-source IDs preserved; current trial 175 rows, integrity ok. Three new alert-log entries are preview-only; legacy success/failed rows were inherited, and new incidents have no email-success flags. No real SMTP/Twilio was contacted.
- Fresh Python 3.14 venv installation was performed in Phase 1 and used for subsequent gates. [Install report](../evidence/phase1/pip-install-report.json), [pip check/imports](../evidence/phase1/environment-check.log). A fresh npm download was not claimed; existing Node dependencies passed all tests/build.

Older QA harness assumptions and screenshot-write/restart-helper problems were corrected and rerun. Only final observed cases are marked pass. The original test_images deletions remain pre-existing and unstaged. No push/main action occurred.

## Needs Imran

1. Retain a strong admin password and stable camera-encryption key; review backups before the first real-database migration. Real DB startup/migration was intentionally not performed here.
2. Test physical webcam/LAN discovery/reconnect/shutdown, real GPU/DirectML hardware, native Linux deployment and sustained target load.
3. Validate real SMTP/WhatsApp/recipients/HTTPS deliberately before enabling live delivery. Preview and fake transports do not prove remote success.
4. Produce a leakage-free split/retrain and establish exact model export provenance. Current AP is truncated at the retained confidence cutoff; full-score evaluation needs an agreed evaluation-only low-score policy.
5. Independently label a balanced worker/PPE/face-visibility subset. Current label proxies cannot establish full compliance or missing-mask accuracy. Keep these caveats in the defense/report.

## Proposal objective status

| Objective (as listed in the master task) | Status | Evidence |
|---|---|---|
| YOLOv8-family PPE detection | Implemented, real model measured; final generalization claim pending | Detector tests, Phase 3 split metrics/validation |
| Live web monitoring | Observed with replay sources; physical webcam pending | Camera/live QA, real launchers, bounded stream tests |
| Image/video analysis | Observed working | JPG/PNG/WEBP, MP4/AVI, bad-file and responsiveness QA |
| Automatic email alerts with screenshot evidence | Implemented, preview/fake SMTP verified; real delivery pending | Alert tests, exact MIME/attachment preview, preview-only audit |
| Defensible evaluation/documentation | Tooling/docs delivered; clean retrain and independent compliance truth pending | Saved commands/outputs, thesis notes, limitations |
