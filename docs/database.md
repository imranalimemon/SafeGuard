# SQLite storage and migrations

## Which database is used

The implemented engine is SQLite through SQLAlchemy (`db/database.py`, `db/models.py`), with `check_same_thread=False`. Other SQL engines are not a supported drop-in configuration: engine arguments, schema inspection and migrations are SQLite-specific. There is no Alembic migration setup in this implementation.

`DATABASE_URL` defaults to `sqlite:///./safeguard.db`. Relative paths use the process working directory. The documented launchers start Python inside `backend/`, making the default file `backend/safeguard.db`, not the repository-root file with the same name. `SCREENSHOT_DIR=./screenshots` similarly means `backend/screenshots/`. Absolute process-level overrides allow dedicated data directories; see [setup](../README.md#clean-machine-setup).

Do not open an existing protected database through the app merely to inspect its schema: importing `main.py` runs initialization/migrations. Use read-only SQLite connections or a disposable copy. No dataset or model weights are stored in SQLite.

## Tables

### `violations`

One row represents a confirmed violating worker event after positional deduplication, not every frame/person seen.

| Column | Type / meaning |
|---|---|
| `id` | Integer primary key |
| `timestamp` | UTC DateTime; legacy storage/JSON may be naive UTC |
| `violation_type`, `missing_ppe` | Human-readable `Missing: ...` and comma-separated canonical PPE names |
| `person_count`, `violation_count` | Worker/violating-worker counts for that frame; not unique site totals |
| `confidence` | Person detection confidence, 0-1; not a calibrated probability of the rule being correct |
| `screenshot_path` | Relative HTTP URL `/screenshots/<file>.jpg`; file bytes remain on disk |
| `details` | Upload filename/frame or live-camera context |
| `source` | `image_upload`, `video_upload` or `camera:<integer id>`; nullable for older rows |
| `bbox` | JSON text containing this worker's original-pixel `[x1,y1,x2,y2]` |
| `detections` | JSON text for the frame's full detection list |
| `mask_assessment` | `detected`, `missing`, `not assessable`, `not required`, or null on legacy data |
| `alert_sent` | Default false; set true when SMTP accepts at least one recipient. Preview/WhatsApp do not set it; later failure does not erase an earlier success |
| `review_status` | `open` by default, `acknowledged` or `escalated` |
| `acknowledged_at`, `escalated_at` | UTC DateTime of the first respective action |
| `archived_at` | Nullable UTC DateTime; non-null hides a row from default history/recent incidents |

Unknown-mask-only workers are represented as `NOT_ASSESSABLE` in inference results and are not inserted as invented violations. If a worker also lacks helmet/vest, that genuine violation can be recorded with `mask_assessment=not assessable`.

Review actions are idempotent for their timestamps. Escalation persists even if acknowledgment is performed afterward. Archive changes metadata only: it never deletes a row or evidence file. Recorded-total statistics include archived records; the recent-incident list excludes them.

### `alert_settings`

The earliest row by `id` is the saved site configuration. Reading settings does not create a default row; saving creates one if absent.

| Column | Meaning |
|---|---|
| `id` | Integer primary key |
| `email_enabled`, `whatsapp_enabled` | Saved channel toggles |
| `email_recipients` | Comma-separated string, not a JSON array |
| `whatsapp_recipient` | String |
| `email_cooldown`, `whatsapp_cooldown` | Integer seconds, accepted range 0-86400 |
| `confidence_threshold` | Finite number in [0,1] |
| `required_ppe` | JSON text array of distinct canonical names: Helmet, Safety Vest, Face Mask; 1-3 entries |

At startup `runtime_settings.restore_settings` validates the full configuration before applying it. Saved values take precedence over the corresponding initial environment values. A null policy on a legacy row uses the default three-item policy without rewriting the row. Invalid stored values/JSON stop startup with an error rather than partially applying settings.

Credentials, `ALERT_DELIVERY_MODE`, timezone and network timeout are not in this table. A saved enabled toggle cannot override preview mode. Environment `REQUIRED_PPE` is ignored by current code; the default and saved policy are authoritative.

### `alert_logs`

| Column | Meaning |
|---|---|
| `id`, `violation_id` | Primary key and nullable reference to a violation; manual Settings tests have no incident ID |
| `channel` | `email` or `whatsapp` |
| `sent_to` | Recipient associated with the attempt |
| `sent_at` | UTC attempt/result logging time |
| `status` | `success`, `failed`, or `preview` |
| `message` | Actual transport/result/failure detail |
| `transport` | e.g. `smtp`, `twilio`, `preview`, `none` |

SMTP acceptance and the corresponding email flag update share one DB transaction. A partial SMTP refusal is logged as failed with details, while `alert_sent` can be true if another configured recipient was accepted. If recording fails after delivery, the failure is logged and the returned result has `logged:false`; the system cannot claim a DB update succeeded.

Automatic preview attempts can produce preview logs. Dedicated email-preview GETs do not send, add logs or mark a violation sent. Suppressed cooldown checks are not recorded as delivery successes. Twilio queue acceptance is not proof of final handset delivery.

### `cameras`

`id`, unique `name`, `source_type` (`webcam`, `ip`, `rtsp`), `url`, `username`, `password`, `location`, `enabled`, `created_at`. Webcam indices are strings such as `"0"`; omitted webcam URLs default to `"0"`. A source string in a violation is not a camera foreign key. Camera credentials are plaintext and currently included in camera API responses; this requires access control before non-local deployment.

There are no persisted resolution/FPS/PTZ fields in the current model.

## Initialization and migrations

`main.py` calls `Base.metadata.create_all`, then idempotent column checks:

- `ensure_violation_columns`: nullable bbox/detections/source/mask fields; `review_status` defaults to `open`; review/archive timestamps are nullable.
- `ensure_alert_settings_columns`: add nullable `required_ppe` text.
- `ensure_alert_log_columns`: add nullable `message` and `transport` text.

These migrations use `PRAGMA table_info` and `ALTER TABLE ... ADD COLUMN`; they do not remove existing rows, rewrite the database or delete screenshots. They do change the selected DB schema, so back up first and test a copy. Migration tests use disposable databases, including synthetic 106-row legacy fixtures; that fixture count is not a claim about the current real database.

## Backups and read-only inspection

Use SQLite's backup API rather than a plain file copy if the application may be writing or using WAL. Also copy `SCREENSHOT_DIR`; database rows contain file references, not image blobs. For a fully coordinated DB/evidence snapshot, stop writers while copying evidence. Never move/delete the original as part of a backup.

Example, run with absolute source/destination paths appropriate to your machine (the destination must be new):

```python
from pathlib import Path
import sqlite3

source = Path('backend/safeguard.db').resolve(strict=True)
backup = Path('safeguard-backup.db').resolve()
with backup.open('xb'):  # Refuse to overwrite an existing backup.
    pass
src = sqlite3.connect(source.as_uri() + '?mode=ro', uri=True)
dst = sqlite3.connect(str(backup))
try:
    src.backup(dst)
finally:
    dst.close()
    src.close()
check = sqlite3.connect(backup.as_uri() + '?mode=ro', uri=True)
try:
    print(check.execute('PRAGMA integrity_check').fetchall())
    print(check.execute('SELECT COUNT(*) FROM violations').fetchone()[0])
finally:
    check.close()
```

Run this from the repository root or replace the source path. If source configuration differs, use its actual path. A backup is only a recovery asset after integrity verification and evidence preservation.

## Destructive legacy endpoint

`DELETE /api/violations` still deletes all violation rows and is not protected by authentication. The current UI does not call it for exports/archive. Do not use it as a maintenance or export operation. Retention, recovery tooling and authentication remain deployment work, not implemented guarantees.
