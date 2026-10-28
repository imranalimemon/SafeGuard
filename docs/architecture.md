# Architecture

```mermaid
flowchart LR
  Browser[React browser: login, dashboard, upload, review, settings]
  Auth[FastAPI access middleware: session, CSRF, origin, limits]
  Camera[Camera capture: latest frame slot]
  Sample[Sampled inference worker]
  Model[ONNX Runtime: installed accelerator or CPU]
  Decode[Letterbox RGB /255 + per-class NMS + coordinate reversal]
  Rules[Worker/PPE association + face visibility]
  Stream[Annotated JPEG + one-frame ACK window]
  DB[(SQLite: incidents, observations, reviews, settings, sessions)]
  Evidence[Annotated evidence files]
  Alerts[Channel/cooldown gate + preview/live confirmation]
  Worker[Off-loop MIME / SMTP / Twilio worker]
  Logs[Rotated redacted operational logs]
  Browser --> Auth
  Auth --> Camera --> Sample --> Model --> Decode --> Rules
  Auth --> Upload[Validated upload worker + temporary files]
  Upload --> Model
  Rules --> Stream --> Browser
  Rules --> DB
  Rules --> Evidence
  DB --> Alerts --> Worker
  Worker --> DB
  Auth --> DB
  Auth --> Evidence
  Auth --> Logs
```

Live and upload routes share the model and rules. Each live viewer has independent capture/error state. One latest-frame slot drops old inputs; frame acknowledgements bound delivery. Cached detection results may lag motion. Upload processing and transports run off the event loop. Observation storage has its own per-frame denominator, independent of violation cooldowns.

Camera secrets use a stable external Fernet key. Login protects HTTP, WebSockets and evidence. Settings restore at startup; secrets and live-delivery authorization do not come from the settings table. Demo databases carry explicit metadata/banner. This is a single-machine/single-admin architecture; it does not claim distributed capture, multi-user roles, identity tracking or unlimited camera capacity.
