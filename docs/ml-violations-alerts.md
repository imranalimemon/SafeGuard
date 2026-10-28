# Detection, PPE rules and alerts

## Model and preprocessing

The serving artifact is `backend/best.onnx`, an Ultralytics-trained, four-class YOLO-format export. `PPEDetector` uses ONNX Runtime with the explicitly selected `CPUExecutionProvider`. The serving code does not call a `.pt` model or the training library. Model/provider identity shown in the UI comes from the actual session.

| Class ID | Name |
|---|---|
| 0 | Face Mask |
| 1 | Helmet |
| 2 | Person |
| 3 | Safety Vest |

Input: 640x640. `model.py` letterboxes while preserving aspect ratio, centers padding with value 114 (an odd extra pixel goes right/bottom), converts BGR to RGB, scales float pixels by 1/255, and forms a contiguous NCHW batch.

The output tensor is `1x8x8400`: four box values plus four class scores, with no separate objectness channel or embedded NMS. Postprocessing selects the class score, applies the configured confidence cutoff (initial default 0.5), then **per-class NMS** (default IoU 0.45). An overlapping Person cannot suppress a Safety Vest just because their boxes overlap. Boxes map back by removing padding and dividing by the letterbox gain, then clip to original image bounds. Saved confidence settings apply at runtime; NMS is not a Settings slider.

## PPE association

`compute_violations(detections, required_ppe=None, frame=None)` is independent of API/database/alert paths. Default required PPE comes from runtime settings: Helmet + Safety Vest + Face Mask, unless a saved site policy changes it.

- Only real Person detections create worker assessments. Orphan PPE does not invent workers/incidents.
- Helmet association is restricted to a head zone extending to the upper 35% of the person, with small bounds extensions.
- Vest association requires the torso zone, approximately 15%-70% of person height.
- Mask association uses the upper 50% and horizontally centered 90% of the box to accommodate head/torso close-ups.
- At least half of a PPE box must overlap its anatomical zone and its vertical center must lie there. Scoring combines zone/body containment and horizontal alignment.
- Candidate matches are assigned greedily by score; a PPE item can belong to one worker and each worker gets at most one item of each type. This is geometric association, not pose estimation/tracking.

Legacy `VIOLATION_IOU_THRESHOLD(S)` configuration attributes do not supply the association decision in the current scoring implementation. Do not describe them as active per-class rule thresholds.

## Missing-mask visibility rule

A correctly associated mask counts as detected even if the frontal-face heuristic would not detect that masked face. If a required mask is not detected, the worker must have a person box at least **100 px wide and 160 px high**, and OpenCV's bundled `haarcascade_frontalface_default.xml` must detect a face in the clipped upper half. Faces need minimum 24x24 pixels, `scaleFactor=1.1`, `minNeighbors=5`, with their center in the central 20%-80% of the crop width.

This supplies conservative evidence of a plausibly frontal face, not a reliable head-orientation classifier. No frame pixels, a small worker, no centered frontal face, or an unavailable cascade means `mask_assessment="not assessable"`. It must not raise a missing-mask violation. Helmet/vest requirements are still checked.

Worker results include `person_bbox`, `has_ppe`, `missing_ppe`, `mask_assessment`, `not_assessable`, `status`, `violation_type`, person `confidence` and `compliance_score`:

- `VIOLATION`: one or more confirmed missing required items.
- `COMPLIANT`: no missing/unassessable required items.
- `NOT_ASSESSABLE`: mask uncertain, no other required PPE missing. This is not full compliance.

A mask-uncertain result has null `compliance_score`; an uncertainty can coexist with a helmet/vest violation. Live compliance excludes unknown-mask-only workers from the assessed denominator. Unknown-mask counts can also include workers who have another violation. No-person/no-assessed-worker compliance is null. The backend draws annotations; the frontend must not draw pixel boxes as CSS percentages.

## Record and alert deduplication

`ViolationDeduplicator` uses source, sorted missing PPE and similar worker boxes. Centers must be close relative to size and overlap high (IoU >=0.70) to absorb small jitter. Default record cooldown is 10 seconds. Sources distinguish camera IDs and upload contexts. A lock makes checks/reservations atomic.

`alerts/throttle.py` separately uses channel + source + missing PPE + worker box (event ID fallback if no position). It reserves in-flight sends so concurrent calls do not duplicate one worker. Other workers/cameras are not blocked by a global channel timer. Accepted deliveries and preview completions consume the channel cooldown; failed attempts release the reservation for retry. All cooldown state is process memory and resets on restart. Moving people/cameras can cross positional identities; this is not persistent tracking.

## Alert delivery flow

1. Fresh inference produces confirmed violations; upstream positional dedup decides which rows to persist.
2. Upload/live payloads carry source, worker box, event time, missing PPE and annotated screenshot reference. Only newly persisted events schedule automatic alerts.
3. Saved channel toggles select email/WhatsApp. Per-worker/source/channel cooldowns reserve eligible work.
4. The process-level gate permits transport clients only when `ALERT_DELIVERY_MODE=live` and `ALERT_DEBUG_MODE=false`. Default mode is `preview`. DB settings cannot change this mode. The legacy debug flag now forces preview and does not start a local SMTP receiver.
5. SMTP/Twilio operations run in worker threads. The default network-operation timeout is 10 seconds; SMTP can perform several individually bounded operations. There is no promise of a single ten-second end-to-end delivery deadline, and active transport threads are not abandoned merely by an outer timeout.
6. Result/log writes run in worker threads. Logs store recipient, channel, transport, result detail and success/failed/preview status. SMTP acceptance sets `violations.alert_sent=true` in the same DB transaction; preview and WhatsApp do not. An earlier true flag is never cleared by a later failure. DB logging failures are explicitly reported as `logged:false`.

Email uses `EmailMessage` with plain-text content, source/camera, event time with offset/zone (default Asia/Karachi), missing PPE and an annotated image attachment. Naive DB timestamps are interpreted as UTC. The sender refuses an evidence-free **violation** email; a manual Settings test is clearly marked as a test with no associated screenshot. Evidence must resolve inside `SCREENSHOT_DIR`.

SMTP uses STARTTLS, or implicit TLS on port 465. Missing configuration, authentication failures, timeouts and recipient refusals return actual errors. `alert_sent` means at least one configured recipient was accepted by SMTP, not guaranteed inbox delivery. A partial refusal logs failure details even when another recipient was accepted. Twilio uses its HTTP client's timeout; API queue acceptance is explicitly distinguished from final delivery.

## Preview and manual test

- `GET /api/settings/alerts/preview-email`: synthetic manual-test MIME, no associated screenshot.
- `GET /api/violations/{id}/preview/email`: the actual violation's content and annotated evidence, or a clear error if evidence is unavailable.
- Both use the same email builder as SMTP, return subject/body/recipient/attachment metadata plus `eml_base64`, and do not send, write alert logs or set `alert_sent`.
- `POST /api/settings/alerts/test-email`: one configured-recipient email attempt after an explicit UI click, only if saved email alerts are enabled. The UI also requires effective live mode. No request recipient override is accepted; normal cooldown is bypassed for this manual test.
- Manual WhatsApp shares can bypass the channel toggle, but never the process preview gate. Test/share attempts use result logging.

For non-delivering tests, explicitly set process `ALERT_DELIVERY_MODE=preview` even if a database contains enabled alert toggles. Do not use credentialed real transports in unit tests. `test_alerts.py` uses fake SMTP/Twilio, rejects outbound sockets and writes only disposable databases.

### Deliberately enabling live delivery

1. Use preview with a disposable database first. Inspect the violation preview `.eml`, recipient, timestamp/timezone, missing PPE and annotated attachment. Preview builds the same MIME content as delivery.
2. Stop all live feeds/uploads. Check the intended saved recipients and both saved channel toggles; those toggles override environment defaults. Leave automatic channels disabled while preparing the deployment.
3. Configure private SMTP/Twilio credentials and bounded `ALERT_NETWORK_TIMEOUT_SECONDS`. Set process `ALERT_DELIVERY_MODE=live` and `ALERT_DEBUG_MODE=false`, then restart the backend. Check `/api/health`; SMTP configured does not mean authenticated or delivered.
4. Only when a real message is intended, enable the desired saved channel, save, and click its manual test once. Enabling the channel also permits automatic alerts from subsequent detections. Verify the actual recipient/result/log before starting feeds.
5. To stop all external delivery independently of saved toggles, restart with `ALERT_DELIVERY_MODE=preview`. No live transport delivery was attempted in the final QA batch.

## Evaluation limits

CPU throughput and cached live boxes are described in [README](../README.md#limitations-and-evaluation-status). Small/occluded PPE, overlapping workers, pose/lighting/domain changes, and frontal-face false positives/negatives still need real-site validation. A mask-unassessable result does not demonstrate mask compliance. Final accuracy/mAP/per-class claims remain pending a leakage audit, leakage-free retraining and independent held-out evaluation. The direct 12-image sanity tool is a functional regression check, not that evaluation.
