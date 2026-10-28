# Phase 4 — observations, reports, settings and responsive UI

## Changes

- Added `worker_observations`, one row per analyzed live/upload frame, including compliant, unknown and empty frames. It stores source, UTC time and worker/status counts. Violation deduplication does not suppress observation storage. The compliance denominator is compliant + violating observations; unknown-only workers are excluded. These are sampled observations, not unique workers. Old violations are never backfilled with invented denominators.
- Dashboard analytics show recorded violations per UTC day, source/camera, missing PPE and review status, plus observation-based compliance history. All archived records are included in historical totals; the UI explains this scope.
- PDF export now includes title/date range/filter details, summary bar charts from the filtered records, daily charts, the incident table and evidence thumbnails. Its data path remains GET-only. CSV filtering is unchanged.
- Frame interval is validated as an integer 1–30, added to saved settings with an additive nullable column, restored at startup, and applied to new streams/video analysis. Existing streams should be restarted after saving it. Recipient/cooldown/confidence/PPE controls have inline guidance and clearer loading/disabled/error states.
- Live delivery requires an environment gate plus typing `ENABLE LIVE ALERTS` in Settings. Every process starts unconfirmed; DB toggles cannot override preview. A preview-configured process returns 409 even with the exact confirmation string. The header shows a live banner only when delivery is actually live. The real process stayed preview throughout QA.
- Responsive sidebar/header/footer and Dashboard layouts were checked at desktop and tablet widths. Unavailable card values wrap rather than clip. Settings controls and camera selector gained accessible names; the incident dialog traps focus, closes with Escape and restores previous focus. Camera configuration becomes a drawer at narrower widths.

## Files

Backend: `observations.py`, `db/models.py`, `db/database.py`, `runtime_settings.py`, `config.py`, `api/stats.py`, `api/upload.py`, `api/settings.py`, `api/health.py`, `websocket/manager.py`, `alerts/content.py`, `test_product.py`, `test_alerts.py`, `test_live_stream.py`, `test_saved_settings.py`.
Frontend: `src/App.jsx`, `src/components/Analytics.jsx`, `src/components/DeliveryControl.jsx`, `src/components/layout/Navbar.jsx`, `src/hooks/useDialog.js`, `src/api/violationReports.js`, `src/index.css`, `src/pages/{DashboardPage,SettingsPage,CamerasPage,ViolationsPage}.jsx`, `test/ui_status.test.cjs`, `test/violation_reports.test.mjs`.
Verification: `tools/qa_product.cjs`, `tools/inspect_pdf.py`, this report and `docs/evidence/phase4/`.

## Tests and evidence

Command: `<fresh-venv-python> -B tools/verify_phase.py --phase 4 --extra backend.test_security backend.test_reliability backend.test_evaluation backend.test_product`. [Exact commands and successful exit codes](../evidence/phase4/tests.json), numbered logs alongside it. Passed: 130 core, 3 camera, 2 launcher, 9 security, 6 reliability, 9 evaluation and 5 product tests; frontend Node tests/rendering and production build. Product tests cover a real temporary SQLite denominator, unknown/empty frames, frame-interval validation/restart and preview/live confirmation gates. Fake-transport tests now explicitly confirm their fake live configuration. The third-party Starlette test-client package emits an httpx deprecation warning; application utcnow/on_event/class Config deprecations remain removed.

Browser command: `node tools/qa_product.cjs <Playwright-directory> <temporary-auth.json>`. [Results](../evidence/phase4/browser.json): every page at 1366x768, 1920x1080 and 820x1180 had no horizontal document overflow. Screenshots for each page/width are in the same folder. Dashboard and tablet Settings screenshots were opened for visual inspection.

The browser uploaded a real copied image and fetched [actual analytics output](../evidence/phase4/observed-analytics.json). It recorded one worker as mask-not-assessable and correctly returned a zero assessed denominator / null compliance rate. [Upload](../evidence/phase4/upload-observation.png), [analytics](../evidence/phase4/observed-analytics.png). Saving frame interval 4 succeeded in the disposable DB; it was restored to 3 after the check. Preview live-mode confirmation was rejected. No real alert transport was invoked.

The browser downloaded [the filtered PDF](../evidence/phase4/filtered-report.pdf). `python -B tools/inspect_pdf.py docs/evidence/phase4/filtered-report.pdf` opened it with PyMuPDF, rendered its title and summary pages, and verified table/evidence sections: [inspection output](../evidence/phase4/pdf-inspection.json). Five pages, 97656 bytes. The rendered summary chart was visually inspected and reflects the one filtered escalated record, including true zero counts for other PPE types.

## Needs Imran

- Real SMTP/WhatsApp and live confirmation on a live-configured deployment remain untested. The gate itself has fake-only unit coverage; do not infer real delivery success from it.
- Observation counts repeat workers across frames and across multiple viewers. They describe sampled compliance, not site headcount, unique-worker compliance or exposure-normalized risk. No historical compliance is inferred before observation storage began.
- The responsive check covers the specified three sizes, not every browser/device or a formal accessibility certification. Physical touch/webcam testing remains useful.
