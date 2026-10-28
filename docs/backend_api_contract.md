# Backend API contract

Base URL through Vite: `/api`. Except login/session discovery, API/docs, `/screenshots/*` and WebSockets require the `safeguard_session` cookie. Mutations require `X-CSRF-Token` from login/session. CORS allows configured frontend origins only. Never put session tokens in URLs.

| Method/path | Behavior |
|---|---|
| GET `/api/auth/session` | `{authenticated, username?, csrf_token?}` |
| POST `/api/auth/login` | `{username,password}`; HttpOnly cookie + authenticated/session metadata; generic invalid-credential errors/rate limit |
| POST `/api/auth/logout` | Revokes session and clears cookie |
| GET `/api/health` | Real model/DB status, name/providers, toggles, effective preview/live mode, configuration-only SMTP status, optional demo label |
| GET `/api/cameras` / `/{id}` | Sanitized URL, has_credentials, metadata and active stream status; no username/password/query token |
| POST/PUT `/api/cameras[/{id}]` | Validated camera config. Credentials are write-only. Blank secrets/unchanged displayed URL preserve hidden values |
| POST `/api/cameras/{id}/test` | `{ok,message}`; HTTP 200 may still mean `ok:false` |
| DELETE `/api/cameras/{id}` | Configuration removal only |
| GET `/api/cameras/scan-local`, `/auto-detect` | Real device/LAN discovery; results depend on hardware/network |
| GET `/api/stats/dashboard` | DB incident counts/history and unavailable legacy worker totals |
| GET `/api/stats/analytics` | UTC daily/type/source/review counts and observation trend with explicit denominator |
| GET `/api/violations` | Paginated `{items,total,page,per_page,...}` with date_from/date_to, violation_type, camera_id, review_status, archived filters |
| GET `/api/violations/{id}` | Incident fields, review timestamps, source and evidence |
| PATCH `/api/violations/{id}` | `{action: acknowledge|escalate|archive}`; preserves record/evidence |
| GET `/api/violations/{id}/preview/email` | Exact MIME preview + attachment metadata; no send |
| POST `/api/violations/{id}/share/whatsapp` | Explicit share request; process preview gate still applies |
| GET `/api/uploads/limits` | Current extensions and byte limits |
| POST `/api/upload/image` | Multipart file; annotated_image_url, detections, workers, violations, created_violations and stats |
| POST `/api/upload/video` | Multipart file; total_frames, frames_processed, worker_observations, max_workers_in_frame, violations_detected/logged, suppressed_by_cooldown, key_frames, violation_frames, created_violations |
| GET/PUT `/api/settings/alerts` | Validated email/WhatsApp toggles/recipients/cooldowns, confidence_threshold, required_ppe, frame_skip; startup restores saved values |
| GET `/api/settings/alerts/delivery` | deployment_mode, effective_mode, can_go_live, explanation |
| POST `/api/settings/alerts/delivery` | `{mode,confirmation}`; preview process rejects live with 409; live needs exact confirmation and valid enabled configuration |
| GET `/api/settings/alerts/preview-email` | Manual test MIME preview without a worker/attachment |
| POST `/api/settings/alerts/test-email`, `/test-whatsapp` | One explicit channel attempt through the same process gate; UI disables in preview |
| GET `/api/system/logs?limit=100` | Authenticated tail (1–250 lines), UTC and rotation metadata |
| GET `/screenshots/{filename}` | Authenticated image file only; traversal/unsupported extensions/missing files rejected |

There is no DELETE violations route. CSV/PDF are generated in the frontend from filtered GET pages and authenticated evidence.

Workers include `person_bbox`, `has_ppe`, `missing_ppe`, `mask_assessment`, `status` and upload `ppe_status`/worker IDs. Status is `COMPLIANT`, `VIOLATION`, or `NOT_ASSESSABLE`. Missing-mask unknown does not create a violation. Video observations are per sampled frame, not unique identities. The server offers annotated key frames rather than an annotated video file.

WebSocket `/ws/stream/{camera_id}` authenticates the cookie/origin, then sends annotated base64 JPEG, frame_id, camera metadata, workers/violations/live stats and measured frame_age_ms. Client acknowledges `{type:'frame_ack',frame_id}` only after display. Reconnecting packets have status/message and clear stale frames; terminal failures contain error. Session revocation is rechecked during streaming.

Validation errors use 422 without echoing submitted secret values. Invalid uploads may return 400/413/415; busy uploads return 429. Unauthorized access returns 401, CSRF/origin failures 403, unavailable storage 503. Internal responses are generic; inspect redacted operational logs for details. Limits and live response schemas are authoritative; consult the route code for exact optional fields.
