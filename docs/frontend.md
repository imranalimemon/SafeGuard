# Frontend implementation

## Stack and transport

React 18, React Router, Vite, Tailwind CSS, Axios, native browser WebSocket, jsPDF and jspdf-autotable. State is managed through React hooks and `context/SystemHealth.jsx`. The UI obtains real model/provider identity from backend health; unavailable values are shown as unavailable, not invented counts or hardware readings.

Run the root launcher after the [clean-machine setup](../README.md#clean-machine-setup), or start only the frontend:

```bash
npm --prefix frontend run dev -- --host 127.0.0.1 --port 5173 --strictPort
```

`vite.config.js` proxies `/api`, `/screenshots` and `/ws`. It reads `VITE_BACKEND_URL` from the Vite process environment (default `http://localhost:8000`). The combined launchers explicitly use `http://127.0.0.1:8000`. For a remote backend, start Vite separately with the matching `VITE_BACKEND_URL`; direct cross-origin clients also need the backend's appropriate `ALLOWED_ORIGINS`.

## Pages and states

| Route | Behaviour |
|---|---|
| `/` | Selected camera feed, real live worker/violation/compliance data, recorded counts and recent unarchived incidents |
| `/cameras` | Actual camera CRUD, enabled/disabled state, capture test and discovery; a camera being enabled is not proof it is online |
| `/violations` | Date/PPE/camera/review filters, pagination, archived-only view, evidence detail, review actions and CSV/PDF exports |
| `/upload` | Client validation using backend limits, sequential queue, upload percentage/busy analysis state, results and downloads |
| `/settings` | Saved confidence, required PPE, alert recipients/toggles/cooldowns, delivery-mode/SMTP configuration display, preview and manual test actions |

No emergency-stop or PTZ controls are implemented or displayed. Camera resolution/FPS are not measured by the current schema; do not treat metadata-selection controls as applied capture settings or unavailable badges as measurements.

## Live view

`api/liveStream.js` owns one socket. A selection change closes it, invalidates callbacks/timers and clears the frame/statistics before connecting to `/ws/stream/{id}`. A missing/disabled/unopenable camera or failed read shows a real error. Retry is explicit through Start; errors are not hidden by an endless reconnect loop.

The backend already draws boxes in original-image pixel coordinates. The frontend displays the JPEG with `object-contain` and adds no detection-box overlay. An image-load callback sends its `frame_ack` only for the current socket/frame key; distinct keys also handle repeated identical JPEGs. A five-second watchdog clears frozen results. PPE boxes are cached between inferences, so they may lag movement even while the video moves.

Health polls every five seconds. Reachable backend + loaded model + reachable DB determine the main online state; SMTP configuration is separate metadata. A down backend clears live data and shows Offline. Historical worker totals/compliance have no valid denominator and are not inferred from a violation-only database.

## Uploads

`api/uploadValidation.js` checks the selected extension and size against `GET /api/uploads/limits`; the backend also validates actual content. A selected batch runs sequentially, duplicate concurrent actions are guarded, and result/error state is stored per queued item. View result reopens a completed item's result. Switching upload tabs is disabled while processing.

`components/UploadResult.jsx` displays the backend annotation, each worker's Helmet/Safety Vest/Face Mask state and created record IDs. Missing masks can be `mask not assessable`; requirements disabled by site policy are `not required`. The image anchor downloads the annotated JPEG.

Video views use `total_frames`, `frames_processed`, `worker_observations`, `max_workers_in_frame`, `violation_frames`, `created_violations` and `key_frames`. Worker observations are not unique identities. Key frames have image downloads; there is no disabled/fake full-video export. Upload progress measures bytes transferred; analysis has a busy message, not a guessed percentage. Actual validation/server errors remain visible.

## Review and reports

`components/ViolationReview.jsx` shares Acknowledge, Escalate and Archive Evidence actions between history/detail and Dashboard incidents. The backend is authoritative for status/timestamps. Acknowledging an escalated record does not downgrade it. Archiving hides it from default history/recent incidents but retains evidence and the row; the archived-only filter exposes it.

`api/violationReports.js` imports no mutation API. It requests every matching page using the current date/type/camera/review/archive filters. CSV escapes quotes/newlines and neutralizes spreadsheet-formula prefixes. PDF contains a count/PPE summary, table and available unique evidence thumbnails; missing images are labelled unavailable rather than aborting the report. Neither export calls the legacy delete endpoint.

## Settings and alert previews

Settings reads the backend's required-PPE list and saves it with other validated values. Empty/duplicate/unknown PPE lists are rejected. All three PPE items are defaults; masks still use the face-visibility gate.

`components/EmailPreview.jsx` renders the exact built subject/body/recipient, attachment metadata and downloadable MIME `.eml`. Preview is available in Settings (synthetic manual test, no associated screenshot) and a violation detail (its annotated screenshot is required). A preview never sends a message or writes alert logs.

Send test email uses the saved recipient, makes one POST only after a click, guards duplicate clicks in progress, and keeps the actual outcome visible. It is disabled unless email is enabled and effective delivery mode is live. Preview mode and the legacy debug flag prevent external delivery independently of saved toggles. SMTP configuration readiness does not prove authentication or inbox delivery. Manual WhatsApp API sharing also remains subject to the preview gate.

## Checks and build

From the root:

```bash
node --test frontend/test/live_stream.test.mjs frontend/test/violation_reports.test.mjs frontend/test/uploads.test.mjs
node frontend/test/ui_status.test.cjs
npm --prefix frontend run build
```

The selected tests use fake sockets and static rendering without real alerts/cameras. A production bundle is not a deployed backend; route/proxy/TLS/service configuration is still required. See the [API contract](backend_api_contract.md) for wire formats and [README limitations](../README.md#limitations-and-evaluation-status).
