# Backend implementation

## Runtime and startup

The backend is FastAPI + Uvicorn, SQLAlchemy/SQLite, OpenCV, NumPy and ONNX Runtime. `detection/model.py` lazily shares one `PPEDetector` session between health, uploads and live streaming. The current session explicitly selects `CPUExecutionProvider`. Ultralytics is the training/export origin, not the serving library.

Start with the root launchers described in [README](../README.md). They run from `backend/`, so relative database/evidence paths resolve there. For a manual local backend (activate the root virtual environment first):

```bash
cd backend
python -B -m uvicorn main:app --host 127.0.0.1 --port 8000
```

Set `ALERT_DELIVERY_MODE=preview` in the process environment before a non-delivering run. Use a disposable database/evidence directory for API tests; importing `main.py` itself initializes tables and runs additive migrations on the configured database. Do not import the application against a protected database merely to inspect routes.

Startup order:

1. Load environment/default configuration (`config.py`). This uses `python-dotenv` and class attributes, not a Pydantic configuration class.
2. Construct SQLite engine/session factory and SQLAlchemy models.
3. `create_all` missing tables; add missing violation, settings and alert-log columns. Migration errors are not silently ignored.
4. Mount `SCREENSHOT_DIR` at `/screenshots` and register routes.
5. Before serving requests, restore the earliest saved settings row in a worker thread through `runtime_settings.py`. Validate the full configuration before applying it. No row is inserted by a settings GET.

Saved confidence/PPE/recipient/toggle/cooldown values override initial environment defaults. Credentials, network timeout, timezone and delivery mode remain deployment settings. Invalid saved settings stop startup with a validation error.

## Modules

| Path | Responsibility |
|---|---|
| `api/health.py` | Load/check the actual session, `SELECT 1`, optional SMTP configuration check; no sends |
| `api/upload.py` | Validated sync upload handlers, FastAPI worker-pool processing, temp cleanup, result/record creation |
| `api/violations.py` | Filtered reads, review/archive updates, email preview and manual WhatsApp share |
| `api/settings.py`, `runtime_settings.py` | Validated save/read/restore, one-channel manual test and test-email preview |
| `api/cameras.py` | CRUD, open-plus-decoded-frame test, local webcam and ONVIF discovery |
| `detection/camera_capture.py` | Shared capture opening; three-second FFmpeg open/read timeouts for network/video sources |
| `api/stats.py` | Counts/aggregations from actual violation rows, recent unarchived incidents |
| `websocket/live.py` | Dedicated capture thread, latest-frame slot, sampled inference and display-ACK flow |
| `websocket/manager.py` | Camera lookup, annotation/encoding, persistence and alert scheduling |
| `detection/` | ONNX preprocessing/postprocessing, PPE association, face visibility, annotation, position dedup |
| `alerts/` | Shared content, MIME preview, off-loop SMTP/Twilio, scoped cooldowns and result logging |
| `db/` | SQLite engine, models and additive column migrations |

## Image and video requests

Uploads accept one multipart `file`. Processing functions are synchronous FastAPI routes, so file copying, decoding, inference, rules, annotation and SQL work run in the worker pool rather than the asyncio event loop. A process-local semaphore allows one upload to process at a time; another gets 429 rather than joining an unbounded processing queue.

Image formats: JPEG/PNG/WEBP; default limit 10 MiB plus 25 million decoded pixels. Video containers: MP4/AVI/MOV; default limit 100 MiB. Validation checks extension, MIME, actual image format/video signature and decoder success. Video codec support still depends on OpenCV. The file-size check is performed while copying the received multipart file; it is not an ingress/reverse-proxy body-size limit.

A temporary directory owns the input; `finally` closes it and the upload stream. Video captures are released on success/failure. Newly generated uncommitted images are removed on failure; evidence for already committed video-frame violations remains. Video commits are short per-frame transactions, so a late processing failure can leave valid earlier records/evidence.

Images return all worker assessments separately from confirmed violations and actual created record IDs. Videos analyze the first frame and then every third decoded frame, report observations/max workers, and save up to six representative annotated JPEG key frames. There is no full annotated video download or persistent job queue. Busy state describes analysis without fabricating a completion percentage.

## Live camera flow

`/ws/stream/{camera_id}` opens the selected enabled camera. Capture overwrites a single latest-frame slot. Inference takes the latest eligible frame at `STREAM_DETECTION_INTERVAL` spacing (default 3), dropping missed inputs when inference is slower. Annotation of newer frames reuses the last completed detections/rule results. Violation persistence/alerts run only for fresh inference results.

Each packet includes a capture `frame_id`. The browser sends `{"type":"frame_ack","frame_id":N}` after the image loads. Only one frame is in flight; the next packet uses newer input. No-person compliance is null; before initial inference `stats` is null. Socket close/camera switch clears old images/stats. Failed opening/reads, processing errors or missing delivery acknowledgements produce error states. Native driver reads can still stall; cleanup waits briefly for the capture owner to release the device rather than racing `read()` and `release()`.

## Persistence, alerts and deployment boundaries

Only confirmed violations are inserted into `violations`; unknown-mask-only worker assessments remain in result/live payloads rather than inventing incidents. Record deduplication is source + missing PPE + similar worker box. Alert throttling separately reserves per-channel/source/worker keys, including sends in progress.

SMTP/Twilio and log writes use worker threads. The process delivery-mode gate is checked before constructing clients. Preview attempts may be logged as `preview` by automatic alert flow; dedicated preview GETs are read-only. Live SMTP acceptance and its log/`alert_sent` flag are committed together; database failures are explicitly reported. See [ML and alerts](ml-violations-alerts.md).

The launchers are local development processes, not a production reverse proxy, service manager, authentication layer or TLS setup. WebSocket, HTTP and screenshot routes must be protected before exposing the app beyond a trusted machine/network. Camera tests require `isOpened()` and one decoded frame and always release the capture. A successful test is not proof of continuing frame delivery. Both camera tests and live streams use the shared bounded network capture helper; native webcam drivers can still stall.

Bulk `DELETE /api/violations` is retired and always returns HTTP 405 without issuing deletion SQL. Use review/archive actions instead. [Browser QA](qa-report.md) used only a disposable backup copy and preview delivery.
