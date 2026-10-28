# Detection, violations and alerts

ONNX Runtime executes the four-class model. Names: 0 Face Mask, 1 Helmet, 2 Person, 3 Safety Vest. Centered letterbox/RGB/float `/255` preprocessing and per-class NMS retain overlapping person/PPE boxes. Coordinates reverse padding/scaling and clip to original bounds. [Contract validation](evidence/phase3/model-validation.json), [model-swap procedure](model-swap.md).

PPE is associated only with detected persons. Helmets belong near the head, vests overlap the torso, and masks use a tolerant upper-person zone. One item belongs to one best-matching worker. Orphan equipment creates no invented worker. Position/source/missing-PPE cooldowns distinguish workers but are not tracking identities; movement, nearby workers and restarts can affect suppression.

Default required PPE is Helmet + Safety Vest + Face Mask. A detected mask establishes presence. An absent mask is assessed only on a sufficiently large worker when the frontal-face heuristic accepts the head region. Otherwise mask is unknown and creates no missing-mask alert. Known helmet/vest absence still creates a violation. A worker with all assessable requirements present but unknown mask is `NOT_ASSESSABLE`, not compliant.

## Alert flow

An accepted violation saves annotated screenshot evidence and a database row. Channel toggles and per-worker/source cooldowns decide whether to attempt automatic delivery. MIME content states source/camera, timezone-qualified event time, missing PPE and the screenshot attachment. A violation email without available annotated evidence is refused. Preview and live paths use the same message builder.

`ALERT_DELIVERY_MODE=preview` blocks SMTP and Twilio regardless of saved DB toggles. Debug mode also forces preview. Preview endpoints return the exact subject/body/attachment description and downloadable MIME without sending. Test-send buttons are disabled in preview. The preview transport records `preview`, never email success.

Live operation requires both:

1. Start a deployment configured with `ALERT_DELIVERY_MODE=live`, stable secrets, verified recipients and timeout settings. Review the message preview first. A configuration check does not prove SMTP reachability/authentication.
2. Save the desired channel settings, then type `ENABLE LIVE ALERTS` in Settings. This confirms real messages to saved recipients for that process. The header shows LIVE ALERTS ENABLED. Restarting clears confirmation. Return to preview immediately from the same panel if needed.

The current task never enabled live delivery or contacted real SMTP/Twilio. Real transport tests require Imran's deliberate deployment action.

SMTP/Twilio calls execute in worker threads with configured timeouts, keeping the event loop responsive. Results are logged with status/transport/message. Only actual SMTP success sets `alert_sent`. Failures remain visible; a database logging failure is reported separately. A network timeout cannot guarantee the remote provider did not accept a message, so absolute exactly-once delivery is not claimed.

## Evaluation

Read [testing](testing.md), [limitations](limitations.md) and [phase 3](progress/phase3.md). Test/validation images entered the augmentation pool. Saved AP/PR outputs are truncated at the retained production confidence cutoff and are not full-score benchmark AP. Box-derived worker truth is exploratory; independent face-visibility and worker-PPE labels are needed for validated compliance/missing-mask metrics.
