# Frontend

React 18 + Vite use a same-origin proxy for `/api`, `/ws` and `/screenshots`. `AuthGate` checks the session before mounting the app; login obtains the CSRF token, and logout revokes the session. Cancelled session checks cannot overwrite a newer login.

- **Dashboard:** real backend/model/DB health, actual model/provider, configured camera selection, annotated stream, current worker statuses, DB incident log and observation-based historical analytics. Unavailable values stay unavailable; there are no invented site/camera/hardware counts.
- **Cameras:** add/edit/test/delete camera configuration. Tests use the returned `ok` flag/message. Credential inputs are write-only; blank edits retain secrets. Active connection state is reported separately from the enabled configuration flag.
- **Violations:** date/PPE/source camera/review/archived filters, pagination, evidence/details, acknowledgement/escalation/archive, exact email preview, filtered CSV and PDF. There is no record-deletion control or violation DELETE route.
- **Upload:** real image/video schemas, workers and per-PPE statuses, created records/cooldown suppression, annotation downloads, sampled video summaries/key frames, clear busy/error states and extension/size checks backed by server validation.
- **Settings:** saved recipients/toggles/cooldowns/PPE/confidence/frame interval, email preview and gated live delivery. Test-send controls are disabled in preview with an explanation. The header marks actual live delivery.
- **Logs/Help:** genuine authenticated operational log lines and actual safety/operation guidance.

The browser draws no detection boxes over the backend JPEG; it acknowledges an image only after display. Camera switching closes the previous socket and rejects late callbacks. Reconnect messages clear stale frames and keep the watchdog informed.

PDF charts use the exported filtered records, not Dashboard totals. Evidence failures produce explicit unavailable messages. CSV escapes text/formulas. Exports use GET results only.

Responsive screenshots at 1366x768, 1920x1080 and 820x1180: [phase 4 evidence](evidence/phase4/browser.json). Dialogs support focus trapping/Escape/return focus, controls have basic labels, and focus outlines are visible. This is not formal accessibility certification. Previously external Google font requests caused QA load timeouts. Font assets and licenses are now bundled under `frontend/public/fonts/`; the app serves them locally with fallback fonts. A production deployment should serve its asset bundle over HTTPS, not expose Vite's development server.

Run frontend tests/build through [testing instructions](testing.md). The production build succeeds but warns about a large report/chart bundle; route/code splitting remains an optimization opportunity.
