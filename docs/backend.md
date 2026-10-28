# Backend

FastAPI serves authenticated HTTP/WebSocket routes. [Architecture](architecture.md) shows the data flow. `backend/main.py` uses lifespan: configure rotated logs, create missing tables/add legacy columns, restore validated DB settings, initialize admin/session storage and encrypt camera credentials. Shutdown signals active streams and disposes the engine.

## Access and storage

A single admin account uses salted PBKDF2-SHA256. Eight-hour revocable sessions store token hashes in SQLite; the browser receives HttpOnly/SameSite Strict cookies. Unsafe requests require `X-CSRF-Token`; origins are limited to `ALLOWED_ORIGINS`. API/docs, WebSockets and evidence downloads require login. Streams recheck session validity each second. Use HTTPS and `SAFEGUARD_COOKIE_SECURE=true` beyond a local loopback setup. There are no multi-user roles or password-reset UI.

Network camera URLs/usernames/passwords use Fernet encryption from `SAFEGUARD_CREDENTIAL_KEY`. API responses expose a credentialless/queryless URL and `has_credentials`, never passwords/usernames. Blank edit credentials preserve existing values. Legacy encrypted migration is transactional; old backups may retain plaintext. Lost keys are not recoverable.

## Detection and concurrency

`detection/model.py` loads ONNX Runtime, selecting available CUDA/DirectML with CPU fallback. Health/footer report actual session providers. Preprocessing is centered 640x640 letterbox, BGR-to-RGB and float pixels /255. Output `1x8x8400` is decoded with per-class NMS and padding/scale reversal. Thresholds were retained; current runtime default confidence is 0.50, NMS IoU 0.45.

Live capture owns one latest-frame slot. Sampled inference runs off the event loop; old inputs are dropped. One JPEG frame is in flight until the browser acknowledges display. Cached boxes may lag motion. Failed capture clears the frame and retries with bounded exponential backoff; default budget is three reconnect attempts. Each viewer owns independent capture state. Native webcam calls can still exceed shutdown deadlines.

Image/video endpoints are synchronous worker-pool handlers. A processing semaphore limits heavy upload work; SQLite sessions remain on their owning worker. Temp uploads are cleaned on failure. Images require matching extensions/MIME/signatures and successful decode; image bytes/dimensions and video bytes are limited. See API upload limits rather than assuming a browser-only restriction.

Per analyzed frame, `observations.py` stores worker/status counts even when no violation is logged. Violations use source + coarse worker position + missing items for cooldown. Logs/alerts happen only after actual records/evidence exist. Alert transports are off-loop and preview remains an independent process gate.

## Configuration and operation

Use [README setup](../README.md). Saved confidence, cooldowns, channel toggles, recipients, PPE policy and frame interval are validated/restored at startup. Secrets and delivery authorization are not DB settings. Restart an existing stream after changing the sampling interval. System Logs tails a bounded current file; rotation is 2 MB with four backups. Configured secrets and URL credentials/query strings are redacted.

Measured CPU stream benchmark and exact methodology: [saved output](evidence/phase2/benchmark/benchmark.json). Local ACK-sink measurements exclude network/browser latency. GPU behavior on real hardware, physical camera reconnect and SMTP delivery remain unverified.
