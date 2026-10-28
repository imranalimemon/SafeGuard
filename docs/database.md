# Database

SQLite/SQLAlchemy storage is configured by `DATABASE_URL`. `sqlite:///./safeguard.db` is relative to the backend working directory. Evidence files live separately under `SCREENSHOT_DIR`; database backups alone do not preserve screenshots or the camera encryption key.

| Table | Purpose |
|---|---|
| `violations` | UTC event time, source, worker box, detections, missing PPE, confidence, screenshot URL, email success flag, review/archive timestamps, mask assessment |
| `worker_observations` | UTC analyzed-frame/source counts: workers, compliant, violating, unknown-only, mask-unknown; independent of incident cooldown |
| `alert_settings` | Validated recipients/toggles/cooldowns/confidence/required PPE/frame interval |
| `alert_logs` | Channel, recipient, violation reference, UTC time, success/failed/preview, message and transport |
| `cameras` | Real camera configuration; network URL and credentials encrypted; enabled flag is configuration, not proof of reachability |
| `admin_users` | Single admin username and salted password hash |
| `auth_sessions` | Hashed revocable session token, user reference and expiry |
| `demo_metadata` | Optional marker only in explicitly generated temporary demo DBs; exposes a demo banner |

Startup creates missing tables and adds missing legacy columns idempotently. Existing violation rows are preserved. New policy/frame-interval columns are nullable so old saved settings fall back to validated runtime defaults. UTC values retain the legacy naive-UTC database convention while acquisition uses timezone-aware UTC.

Acknowledge sets status/timestamp once. Escalate sets status/timestamp and cannot be downgraded by acknowledgement. Archive sets `archived_at`; default queries hide it, and the archived toggle selects it. Files/records are retained. No violation-delete endpoint exists. Camera deletion only removes configuration; historical source strings remain.

Compliance = compliant observations / (compliant + violating observations). Unknown-only workers are excluded. Repeated frames/viewers can count the same worker; this is not a unique-worker denominator. Historical incidents without observations cannot yield historical compliance.

`violations.alert_sent` means an email transport actually succeeded, not a preview/WhatsApp/failed attempt. Delivery log and that flag are updated together. Network success followed by DB logging failure is reported as such and cannot be made perfectly atomic across SMTP and SQLite.

All master-task migrations/tests ran on temporary databases. Before real deployment, use SQLite's backup API on a live DB, copy evidence separately, and retain the same encryption key. Legacy backups may contain plaintext camera credentials even after the current DB is encrypted.

`backend/tools/make_demo_data.py` accepts only temporary source copies, creates a new temporary DB, copies actual incident rows with existing evidence, preserves their values, and labels it DEMO. It generates no invented metrics and sends no alerts. [Example output](evidence/phase5/demo-output.json).
