# Implemented HTTP and WebSocket contract

This describes the current code, not proposed fields. REST paths below include `/api`; the WebSocket is `/ws/stream/{camera_id}`. Swagger is `/docs`. There is no generic `/api/upload` or camera-less `/ws/stream` route. Examples are illustrative, not benchmark data.

## Conventions and shared objects

- Confidence is 0-1, not a percentage; live compliance is 0-100 or null.
- Boxes are original-image pixel `[x1,y1,x2,y2]`, never CSS percentages.
- SQLite timestamps are UTC; responses can contain naive ISO strings without `Z`. Treat those as UTC. Alert text explicitly includes offset/timezone.
- A source is `camera:<integer id>`, `image_upload`, `video_upload`, or null for older records.
- Many endpoints use FastAPI validation errors `{"detail":[...]}` (422). Operational errors generally use `{"detail":"..."}`. A 200 response containing `ok:false` is still a failed operation.
- No authentication/role boundary is currently enforced. Do not expose destructive/share/credential endpoints publicly.

A **Detection** contains `class_id`, `class_name`, numeric `confidence`, `bbox`. IDs/names are 0 Face Mask, 1 Helmet, 2 Person, 3 Safety Vest.

A **Worker** contains:

```json
{
  "person_bbox": [100, 100, 300, 500],
  "status": "NOT_ASSESSABLE",
  "has_ppe": ["Helmet", "Safety Vest"],
  "missing_ppe": [],
  "mask_assessment": "not assessable",
  "not_assessable": ["Face Mask"],
  "violation_type": "Mask not assessable",
  "confidence": 0.9,
  "compliance_score": null
}
```

Statuses are `COMPLIANT`, `VIOLATION`, `NOT_ASSESSABLE`. Mask assessment is `detected`, `missing`, `not assessable` or `not required`. A worker may have another PPE violation while its mask remains uncertain. Upload workers additionally have a per-frame `worker_id` and `ppe_status` object with keys Helmet/Safety Vest/Face Mask and values `present`, `missing`, `mask not assessable` or `not required`. These IDs are not tracking identities.

A persisted **Violation** serializes:

`id`, `timestamp`, `violation_type`, `person_count`, `violation_count`, `screenshot_path`, `confidence`, `alert_sent`, `missing_ppe`, `details`, `source`, `review_status`, `acknowledged_at`, `escalated_at`, `archived_at`, `mask_assessment`, `bbox`, `detections`.

`missing_ppe` here is a comma-separated string, while in a Worker it is an array. `bbox`/`detections` are parsed from stored JSON text; malformed/null values become null/empty list. Nullable legacy fields are legitimate. There is no `resolved`, `location_name`, `evidence_image_url` or `bounding_boxes` property in this serializer. Use `review_status`, `source`, `screenshot_path` and `bbox`/`detections`.

## Health and dashboard

### `GET /api/health`

Returns `status` (`ok` or `degraded` for model/DB), `model_loaded`, `db_connected`, `model_name` (actual filename or null), `execution_providers` (actual list), `email_enabled`, `whatsapp_enabled`, effective `alert_delivery_mode`, `smtp_configured`, `smtp_configuration_error`, `smtp_status_note`.

The model is loaded/checked; DB is checked with `SELECT 1`. `smtp_configured` is null when email is disabled, otherwise a configuration boolean. It does not establish a socket, authenticate or send. The debug flag makes effective delivery preview-only even if configured mode is live.

### `GET /api/stats/dashboard`

Returns `total_violations`, `today_violations` (UTC day), `avg_confidence` (0-1 or null), `violations_by_type` (Helmet/Face Mask/Safety Vest counts), `recent_violations` (up to five unarchived Violation objects). `total_persons_detected` and historical `compliance_rate` are null: stored violations do not provide a historical worker denominator. Recorded totals/type averages include archived rows.

## Violations and exports

### `GET /api/violations`

| Query | Default / meaning |
|---|---|
| `page` | Omitted means legacy flat-list response; present means 1-based pagination, clamped to at least 1 |
| `per_page` | 50 when paginated; clamped to 1-200; the UI uses 20 |
| `limit`, `offset` | 50 / 0 for the legacy flat-list shape; ignored when `page` is supplied |
| `date_from`, `date_to` | Optional `YYYY-MM-DD`, inclusive from start-of-day through end-of-day UTC |
| `start_date`, `end_date` | Aliases taking precedence over the corresponding shorter date names |
| `camera_id` | Integer; matches `source="camera:<id>"` |
| `violation_type` | Case-insensitive substring, e.g. `Helmet`, not an exact fixed label |
| `review_status` | Optional `open`, `acknowledged`, `escalated` |
| `archived` | false by default; true returns archived rows only, not a combined list |

Paginated response is `{"items":[...Violation],"total":N,"page":P,"per_page":K}`. Without `page`, response is a flat Violation array. Ordering is timestamp descending, then ID descending. There is no site-location filter.

### `GET /api/violations/{violation_id}`

One Violation; unknown ID returns 404.

### `PATCH /api/violations/{violation_id}`

Body: `{"action":"acknowledge"}`, `{"action":"escalate"}` or `{"action":"archive"}`. Returns the updated Violation. Unknown ID is 404; invalid action is 422.

Acknowledgment/escalation set their first timestamps. Repeating an action preserves its timestamp. Acknowledgment does not downgrade an escalated status. Archive sets `archived_at`; it does not delete the row/image or change the review status.

### CSV/PDF export

There is **no CSV/PDF server endpoint**. The browser repeatedly GETs `/api/violations` with all current filters and `per_page=200`, then builds CSV or PDF. Export covers all matching pages, not just the visible page. PDF contains a summary/table plus available evidence thumbnails fetched by GET from `/screenshots/`. Neither export mutates records.

### `DELETE /api/violations` - disabled

Always returns HTTP **405** with `{"detail":"Violation deletion is disabled. Archive evidence instead."}`. It performs no mutation and cannot clear records. Archive Evidence uses PATCH; exports use GET only.

## Uploads

### `GET /api/uploads/limits`

```json
{
  "image": {"max_bytes": 10485760, "extensions": [".jpg", ".jpeg", ".png", ".webp"]},
  "video": {"max_bytes": 104857600, "extensions": [".mp4", ".avi", ".mov"]}
}
```

Values reflect process configuration, not hardcoded client limits. Image decoded pixel limit is additionally 25 million.

### `POST /api/upload/image`

Multipart `file` only. No per-request model/class/confidence selector is implemented; use saved site settings. The sync handler is executed in FastAPI's worker pool.

Example empty-detection result:

```json
{
  "media_type": "image",
  "filename": "empty-scene.jpg",
  "annotated_image_url": "/screenshots/example.jpg",
  "detections": [],
  "workers": [],
  "violations": [],
  "created_violations": [],
  "stats": {
    "total_persons": 0, "compliant": 0, "mask_not_assessable": 0,
    "violations": 0, "violations_created": 0, "suppressed_by_cooldown": 0
  }
}
```

`workers` includes every Upload Worker, `violations` only confirmed violating workers. Created records are separate from detections: cooldown can suppress database inserts. The annotated image remains downloadable even if no record is created.

An element of `created_violations` has `id`, `violation_type`, comma-separated `missing_ppe`, `person_count`, `confidence`, `details`, `source`, `timestamp`, `screenshot_path`, `frame_number` (null for images), and `person_bbox`.

### `POST /api/upload/video`

Multipart `file` only. The first frame and then every third decoded frame are analyzed. Response fields:

| Field | Meaning |
|---|---|
| `media_type`, `filename` | `video`, actual uploaded basename |
| `total_frames`, `frames_processed` | Successfully decoded frames / analyzed frames |
| `worker_observations`, `max_workers_in_frame` | Sum over analyzed frames / maximum in one analyzed frame; not unique workers |
| `violations_detected`, `violations_logged` | Violating worker observations / actual inserted rows |
| `suppressed_by_cooldown` | Confirmed events whose insert was suppressed |
| `mask_not_assessable_observations` | Mask-uncertain observations, including workers with another violation |
| `key_frames` | Up to six `{frame_number,screenshot_url,workers}` objects with downloadable annotated JPEGs |
| `violation_frames` | `{frame_number,violations,created_ids}` for analyzed frames containing confirmed violations |
| `created_violations` | Actual created-record objects described above |

There is no `result_video_url`, full annotated video file or job/progress-poll endpoint. UI shows real byte-upload progress, then a busy analysis state. Short per-frame DB commits mean an error later in a video can leave already committed incidents/evidence.

### Upload errors

400 empty file; 413 byte/pixel limit; 415 unsupported/mismatched/corrupt content, invalid container or no decodable frames; 429 another upload already processing; 500 processing/storage/inference failure. Framework-level missing-file validation returns 422. Temporary inputs/captures are cleaned up on failure; already committed evidence is preserved.

## Cameras

### `GET /api/cameras`, `GET /api/cameras/{camera_id}`

List / one camera object: `id`, `name`, `source_type`, `url`, `username`, **`password`**, `location`, `enabled`, `created_at`. There are no persisted resolution/FPS/PTZ/preset properties. Passwords are currently plaintext in storage/responses: restrict access.

### `POST /api/cameras` (201)

Required: `name` (1-120 characters), `source_type` (`webcam`, `ip`, `rtsp`). Optional: `url`, `username`, `password`, `location`, `enabled` (true default). `ip`/`rtsp` require URL; omitted webcam URL becomes `"0"`. Duplicate name is 409. Returns the created camera.

### `PUT /api/cameras/{camera_id}`

Partial update of those fields; returns updated camera. Unknown ID is 404. Unknown metadata extras do not implement capture controls; database constraints still apply.

### `DELETE /api/cameras/{camera_id}`

Deletes the camera configuration and returns 200 `{"status":"ok","deleted_id":N}`; not 204. Existing violation sources/evidence are not deleted by this handler.

### `POST /api/cameras/{camera_id}/test`

Returns `{"ok":true|false,"message":"actual result"}`. A false `ok` is failure even with HTTP 200. Success requires opening and decoding one frame; capture is always released. Network sources use FFmpeg open/read timeouts of 3000 ms each. A successful test is not a continuous-read guarantee.

### `GET /api/cameras/scan-local`

`max_index` default 4, scanning indices 0 through max_index-1. Returns `{"cameras":[{"index":0,"width":640,"height":480,"backend":"DSHOW"}]}` when such a webcam is found; actual sizes/backends vary. Discovery confirms a decoded frame and releases each capture.

### `GET /api/cameras/auto-detect`

`max_index=4`, `onvif_timeout=3.0`. Returns `local` webcam entries, `onvif` entries (`ip`, `port`, `manufacturer`, `model`, `xaddr`, `types`) and `summary` with local/onvif counts. It probes local devices/LAN multicast and does not add records until the user submits selected cameras. Discovery operations are not part of no-network unit tests.

## Settings, manual tests and previews

### `GET /api/settings/alerts`, `PUT /api/settings/alerts`

GET returns validated effective/saved values without creating a row. PUT accepts and returns:

```json
{
  "email_enabled": false,
  "whatsapp_enabled": false,
  "email_recipients": "",
  "whatsapp_recipient": "",
  "email_cooldown": 30,
  "whatsapp_cooldown": 60,
  "confidence_threshold": 0.5,
  "required_ppe": ["Helmet", "Safety Vest", "Face Mask"]
}
```

Recipients are strings, not arrays/null. Toggles are strict booleans, cooldowns strict integers 0-86400, confidence finite 0-1, PPE a distinct 1-3-item canonical list. Enabled email/WhatsApp channels require valid recipient formats. Invalid PUT values return 422. Saved fields apply immediately after commit and restore at startup. Delivery mode/credentials cannot be changed through this schema. Legacy null PPE policy uses the three-item default.

### `POST /api/settings/alerts/test-email`, `POST /api/settings/alerts/test-whatsapp`

No recipient override body is accepted. Enabled channel required. One request makes one channel attempt to the configured recipient and bypasses normal cooldown. The process preview gate still prevents network delivery.

Delivery results contain `ok`, `message`, `transport`, `sent`; attempted/logged results also have `recipient` and `logged`. Disabled-channel early responses can omit the latter fields. Do not interpret `ok`/`sent` as final inbox/handset delivery. SMTP errors return their actual failure text; Twilio acceptance reports its queued/provider status. A failed result can still use HTTP 200.

### `GET /api/settings/alerts/preview-email`

Builds a clearly labelled manual Settings test with current recipient; no incident/screenshot is associated.

### `GET /api/violations/{violation_id}/preview/email`

Builds the violation email with annotated evidence. 404 missing row; 422 unavailable/disallowed evidence or invalid content. Evidence must resolve inside `SCREENSHOT_DIR`.

Both preview routes return `ok:true`, `sent:false`, `transport:"preview"`, `subject`, `from`, `to`, plain-text `body`, `attachments` (`filename`, `content_type`, `bytes`), `eml_base64`, and a message saying nothing was sent. They do not connect to transports, write logs or mark `alert_sent`.

### `POST /api/violations/{violation_id}/share/whatsapp`

Optional body `{"phone_number":"+15005550007"}` overrides only this manual share's destination. Missing number uses the configured recipient. This bypasses the channel toggle, not preview mode. Returns a logged delivery-result object. Unknown violation is 404. It does not set the email `alert_sent` flag.

## WebSocket: `/ws/stream/{camera_id}`

The selected enabled camera ID is mandatory. The backend sends an already annotated JPEG and a monotonically increasing capture `frame_id`. Packet fields are:

`camera_id`, `camera_name`, `frame` (base64 JPEG), `frame_id`, `detections` (Detection list), `workers` (Core Worker list), `violations` (only `{person_bbox,missing_ppe,status}` for confirmed violations), `stats`.

Stats are `persons`, `compliant`, `violations`, `mask_not_assessable`, `compliance_rate`. Before first inference `stats` is null. With no assessed workers, compliance is null. Fully compliant and confirmed violating workers form the compliance denominator; unknown-mask-only workers do not.

After **displaying** a frame, the client must send:

```json
{"type":"frame_ack","frame_id":123}
```

Only the matching pending frame ID advances delivery. There is at most one in-flight image; the next packet samples the latest capture with cached inference, not a queued old frame. A client that never acknowledges times out after about five seconds. Raw legacy frame-only clients are not sufficient for this protocol.

Errors arrive as `{"error":"actual reason"}` followed by close: 4404 missing camera, 4403 disabled camera, 4400 other capture/processing/delivery failure. Camera changes must close the old socket, clear its frame/stats and ignore late callbacks. Do not draw detection coordinates as frontend percentage overlays.
