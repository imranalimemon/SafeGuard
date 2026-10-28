# Final QA, fixes and documentation

Date: 28 October 2026 (Asia/Karachi). Branch: `codex-fixes`. No commit.

## Safety and test environment

Actual Chrome was driven through Playwright installed in the Windows temporary directory, outside the repository, because the desktop browser connector failed to initialize. Backend: `127.0.0.1:8000`; frontend: Vite `127.0.0.1:5173`. The final code was launched with `start.bat` and its online state verified in Chrome.

SQLite's backup API opened `I:\AntiGRavity\db_backup\safeguard_before_webcam_test.db` read-only and produced `C:\Users\imran\AppData\Local\Temp\safeguard-final-qa-xcuia_9a\trial.db`. The backup evidence directory was copied into that temporary root's `screenshots/`. Every server used this disposable database/evidence directory, `ALERT_DELIVERY_MODE=preview`, dummy SMTP credentials, and empty Twilio credentials. Saved channel toggles were deliberately enabled during the restart test; preview still prevented transport delivery. No email or WhatsApp was sent.

The selected backup contained **114**, not 106, violation rows. Final copy: **136**, integrity **ok**, all original **114 rows byte-for-value identical** across their original columns. Two new records were archived; their evidence remains. The only new alert log is a Twilio **preview** result. Protected-file SHA-256 comparisons matched for `backend/.env`, both database files, the proposal PDF and presentation. Existing `test_images/` deletions were already present before this batch and were left untouched. No detector thresholds, NMS, PPE rules or weights were changed.

Full case details and browser telemetry: [qa-case-results.json](qa-case-results.json). Before-fix captures are retained alongside successful captures. Initial harness problems (wrong button names, treating a legacy flat-list response as pagination, disabled fields and a Unicode dash assertion) were corrected and rerun; they are not app defects. Only final passing functional cases are indexed as passes.

## Browser results

| Area | Tested | Result | Bug found | Fixed | Evidence (screenshot path) |
|---|---|---|---|---|---|
| Startup | Actual `start.bat` starts backend + Vite; real model/DB health | Pass | Existing preferred `.venv` could not import runtime | Yes: warning + original PATH fallback, clear failure if neither works | [screenshots/qa-63-final-start-bat.png](screenshots/qa-63-final-start-bat.png) |
| Health | Stop/restart backend, Offline then Online, actual CPU provider/DB status | Pass | None observed in health transition | N/A | [screenshots/qa-41-backend-offline.png](screenshots/qa-41-backend-offline.png), [online](screenshots/qa-41-backend-offline-online.png) |
| Live view | Local video over two HTTP camera fixtures; annotated frames; switch closes old WS; Stop/Start | Pass | Network open/read could wait about 30 seconds | Yes: shared 3-second FFmpeg operation limits | [screenshots/qa-23-live-camera-a.png](screenshots/qa-23-live-camera-a.png), [switch](screenshots/qa-24-live-camera-switch.png) |
| Failing camera | `rtsp://127.0.0.1:1/x`, failed Test and live error; stale image absent | Pass | Slow opening; test previously checked opening only | Yes: bounded open/read and one decoded frame required; test failure returned in 3226 ms | [screenshots/qa-21-failing-camera-test-bounded.png](screenshots/qa-21-failing-camera-test-bounded.png), [live failure](screenshots/qa-25-live-failing-camera.png) |
| Cameras | Add/edit, enabled toggle, successful test, cancel/confirm delete | Pass | Unsupported resolution/FPS controls silently reset; edit erased password | Yes: unsupported controls removed; blank password omitted from update | [screenshots/qa-20-unsupported-camera-controls-removed.png](screenshots/qa-20-unsupported-camera-controls-removed.png), [credential regression](screenshots/qa-58-camera-password-preserved.png) |
| Camera errors | Intercepted delete 500; actual overlong-name 422 | Pass | Delete error swallowed; validation array crashed React | Yes: actual errors rendered as messages | [screenshots/qa-59-camera-delete-error-visible.png](screenshots/qa-59-camera-delete-error-visible.png), [validation](screenshots/qa-60-camera-validation-does-not-crash.png) |
| Discovery | Empty/results modal, checkbox, Add Selected, real config create/delete with synthetic discovery data | UI pass; hardware untested | No UI bug after corrected harness | N/A | [screenshots/qa-61-discovery-selection-ui-fixture.png](screenshots/qa-61-discovery-selection-ui-fixture.png) |
| Violations | All PPE/review options, dates, numeric camera, Reset, Prev/Next and numbered pages, evidence | Pass | API `source` hidden; partial dates generated 422s | Yes: actual source in table/detail/share; native date inputs | [screenshots/qa-30-violation-source-fixed.png](screenshots/qa-30-violation-source-fixed.png), [all filters](screenshots/qa-68-all-ppe-filter-options.png), [pagination](screenshots/qa-70-pagination-number-and-reset.png) |
| CSV | Browser download, parsed CSV, all matching pages | Pass | None in export implementation | N/A | [screenshots/qa-32-type-filter-csv.png](screenshots/qa-32-type-filter-csv.png) |
| PDF | Browser download/open in Chrome; parsed text and embedded images | Pass | None in export implementation | N/A | [screenshots/qa-45-pdf-viewer.png](screenshots/qa-45-pdf-viewer.png) |
| Review/archive | Acknowledge, Escalate, timestamps, incident log, archive, archived-only view | Pass | None observed | N/A | [screenshots/qa-38-review-filter-archive.png](screenshots/qa-38-review-filter-archive.png), [incident log](screenshots/qa-44-incident-log-review-status.png) |
| Record preservation | Direct old DELETE request, counts unchanged; archive evidence retained | Pass | Legacy API could erase every violation | Yes: HTTP 405, no delete SQL | [screenshots/qa-39-no-violation-deletion.png](screenshots/qa-39-no-violation-deletion.png) |
| Alerts/preview | Exact MIME download; annotated attachment; Twilio preview guard; test-email disabled explanation | Pass in preview | Source absent from quick-share composition | Yes: actual source used; no live delivery attempted | [screenshots/qa-36-evidence-preview.png](screenshots/qa-36-evidence-preview.png), [preview guard](screenshots/qa-37-preview-twilio-no-delivery.png) |
| Images | JPG/PNG/WEBP; helmet+vest, missing PPE, multi-worker, close-up mask; worker table/download; queue reopen; picker/drag/drop | Functional pass | No upload application defect observed | N/A | [screenshots/qa-49-closeup-mask-jpg.png](screenshots/qa-49-closeup-mask-jpg.png), [drag/drop](screenshots/qa-66-drag-drop-image.png) |
| Model quality | Visual review of real model's multi-worker result | **Known failure** | Visible helmets missed on W3/W6/W7; partly occluded workers also not all detected | **No**: detector/rules/thresholds preserved; evaluate/retrain separately | [screenshots/qa-48-multi-worker-webp.png](screenshots/qa-48-multi-worker-webp.png) |
| Videos | Actual MP4 + AVI, busy state, correct summary/violations, annotated key-frame download | Pass | No application defect observed | N/A | [screenshots/qa-55-video-busy.png](screenshots/qa-55-video-busy.png), [AVI result](screenshots/qa-56-video-avi.png) |
| Bad uploads | `.txt`, empty PNG, 10 MiB+1 PNG, text renamed `.jpg` | Pass | No defect observed | N/A | [screenshots/qa-51-bad-txt.png](screenshots/qa-51-bad-txt.png), [empty](screenshots/qa-52-empty.png), [oversized](screenshots/qa-53-oversized.png), [renamed](screenshots/qa-54-renamed-text.png) |
| Responsiveness | Load Dashboard in second tab while real MP4 still processing; health succeeds | Pass: 3895 ms page load | No blocked-event-loop failure observed | N/A | [screenshots/qa-55-dashboard-during-video.png](screenshots/qa-55-dashboard-during-video.png) |
| Settings | Change/save confidence, both cooldowns, PPE, channel toggles; restart; reject empty PPE without changing saved policy | Pass | No settings persistence defect observed | N/A | [screenshots/qa-42-settings-persisted-preview.png](screenshots/qa-42-settings-persisted-preview.png), [validation](screenshots/qa-64-settings-validation.png) |
| UI/navigation | Every page, sidebar/header links, no forbidden placeholder/hardware/site text; real model/provider | Pass | Dead footer links and unsupported camera controls | Yes: removed | [screenshots/qa-19-footer-controls-fixed.png](screenshots/qa-19-footer-controls-fixed.png), [navigation](screenshots/qa-62-global-navigation.png) |
| Browser errors | Page errors, console and failed requests observed throughout | Final re-runs: zero uncaught JS errors | Camera validation caused uncaught render error before fix | Yes | [screenshots/qa-60-camera-validation-does-not-crash.png](screenshots/qa-60-camera-validation-does-not-crash.png); [telemetry](qa-case-results.json) |

Negative tests intentionally generate HTTP 405/415/422 and an intercepted 500. Deliberately stopping the backend generates health/proxy failures. Navigation/React StrictMode can abort a health request. These expected entries are retained in telemetry and were not misreported as clean network runs. The earlier partial-date 422s and camera render exception were real bugs; their final re-runs passed.

## Counts and real-model observations

Export-time Helmet filter: **113 records**, downloaded CSV parsed into **113 data rows**. The camera/date-filtered PDF matched **4 records**, opened in Chrome as **2 pages**, and included evidence thumbnails (two PDF image references). These are snapshots at export time, before later QA detections/review actions. They are not today's final copy totals. The preview's JPEG attachment was **87,683 bytes** and matched the stored annotated evidence byte-for-byte.

| Upload fixture | Dataset source prefix | Workers found | Observed result |
|---|---|---:|---|
| `helmet_vest.jpg` | `chv_test_00003` | 1 | Helmet/vest present; mask not assessable; no violation |
| `missing_ppe.png` | `chv_test_00094` | 1 | Helmet present; vest and mask missing; one violation |
| `multi_worker.webp` | `chv_test_00110` | 7 | Three missing-helmet violations despite visible helmets; all masks unassessable |
| `closeup_mask.jpg` | `fac_test_00005` | 1 | Mask present; helmet/vest missing; correct mask association |

The original problematic filename is `chv_test_00110_jpg.rf.400439995d0c1be0487d4aaf9039cb1f.jpg` in the external dataset. This is a model false-negative example, not proof that the anatomical association code suppressed an existing helmet detection. It remains an open quality issue. No threshold/rule/NMS changes or retraining were made.

Both generated videos decoded **180 frames**, analyzed **61**, reported **151 worker observations**, **90 violating observations**, and created **6 records each**, with cooldown suppressing repeated observations. Counts are per-frame observations, not unique people. The videos are constructed from still images; they verify plumbing, formats and responsiveness, not motion tracking or deployment accuracy. The concurrent Dashboard load was measured at **3895 ms** while the video request was still pending; this is one measurement, not a latency guarantee. No leftover `safeguard-upload-*` temporary folders remained.

## Automated checks

Exact requested ten-module backend command: **130 tests passed**. Additional `backend.test_camera_capture backend.test_launchers`: **5 passed**. Frontend Node suites including the new camera-form suite: **19 passed**. All static-render assertions passed. Production Vite build: **488 modules, success**. `bash -n start.sh`: exit 0. Actual Windows `start.bat`: started both services and passed the browser smoke test, twice during this batch.

[Complete captured test output](qa-test-output.txt). Existing Python datetime/FastAPI/Pydantic deprecation warnings remain. Vite warns about its approximately 727 kB main chunk; build succeeded. The preferred root virtual environment is broken on this machine; the tested launcher fallback used the installed working Python. A fresh-machine installation was documented but not performed.

New regression coverage checks network capture timeout parameters and decoded-frame success/release, deletion preserving synthetic 106 legacy rows/evidence references, broken-environment launcher fallback/failure, actual violation source rendering, date/numeric inputs, absent dead/unsupported controls, camera password preservation and renderable server/network errors. Existing isolated rules, mask visibility, NMS, upload responsiveness/cleanup, persistence, alert MIME/cooldown/fake-transport tests also passed.

## Files changed

- `README.md`
- `backend/api/cameras.py`
- `backend/api/violations.py`
- `backend/detection/camera_capture.py`
- `backend/test_camera_capture.py`
- `backend/test_launchers.py`
- `backend/test_violation_workflow.py`
- `backend/websocket/manager.py`
- `docs/backend.md`
- `docs/backend_api_contract.md`
- `docs/database.md`
- `docs/frontend.md`
- `docs/ml-violations-alerts.md`
- `docs/qa-case-results.json`
- `docs/qa-report.md`
- `docs/qa-test-output.txt`
- `docs/suggestion.md`
- `docs/user-guide.md`
- `frontend/src/api/cameraForm.js`
- `frontend/src/api/client.js`
- `frontend/src/components/layout/Footer.jsx`
- `frontend/src/pages/CamerasPage.jsx`
- `frontend/src/pages/DashboardPage.jsx`
- `frontend/src/pages/ViolationsPage.jsx`
- `frontend/test/camera_form.test.mjs`
- `frontend/test/ui_status.test.cjs`
- `start.bat`
- `start.sh`
- `docs/screenshots/` (90 captured PNG files; includes before-fix and harness-diagnostic captures).

Generated `dist/` and installed dependency directories are ignored build/runtime artifacts, not source changes. Playwright, fixtures, disposable DB/screenshots, downloaded reports, scripts and server logs are outside the repo at the temporary root shown above. Pre-existing protected/untracked proposal files and pre-existing `test_images/` deletions are not changes made by this batch.

## Not verified and open risks

- No physical webcam, site RTSP device or actual LAN/ONVIF discovery was exercised. Camera video came from a local HTTP fixture; discovery UI used explicit synthetic responses. Native driver stalls remain a risk.
- No live SMTP authentication/inbox delivery, Twilio API delivery, handset receipt or external Quick Share sending was attempted. Preview MIME/attachment and transport-blocking behaviour were verified. Real services require a deliberate separate live test.
- No Linux/macOS runtime launch or fresh-machine dependency install was performed; Bash syntax passed. Windows one-command startup was exercised on this machine, including its broken preferred environment.
- No independent accuracy evaluation, leakage audit, retraining, physical motion/long-duration camera soak, GPU deployment or production concurrency/load test was performed. Visible-helmet false negatives remain on the named image; masks use a fallible frontal-face heuristic; position dedup is not tracking.
- The API still lacks authentication/roles/TLS and returns plaintext camera credentials. Keep the service local or protect it before deployment. Removing bulk deletion does not provide general access control.
- Video requests have a busy state and key-frame downloads, not persistent/cancellable jobs or encoded annotated-video output. CPU sharing, cached boxes, SQLite contention and restart-reset cooldowns remain limits.
- Deprecations and the large frontend chunk are maintenance work, not passing claims about future versions or network performance.

57 passing functional browser cases are indexed, with the separate model-quality failure retained explicitly. QA processes were stopped after evidence capture; temporary data was preserved for inspection. See the [user guide](user-guide.md), [setup/architecture](../README.md) and [current improvement priorities](suggestion.md).
