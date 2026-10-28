# Remaining engineering and evaluation work

This list reflects the current React/FastAPI/ONNX Runtime implementation. It is future work, not a list of implemented features. See [final QA](qa-report.md) for observed results.

## Submission priorities

1. Audit dataset leakage and duplicate images, split by source/video/session, then retrain only with explicit approval. Report independent per-class precision, recall, mAP, confusion matrices and failure cases. Existing metrics and the small sanity set are not final evaluation.
2. Review real-model false negatives. In the final browser QA, `chv_test_00110` (uploaded as `multi_worker.webp`) showed visible helmets that the detector did not return at the unchanged 0.50 threshold. Geometry cannot associate a detection that is absent. Keep such examples in the defense/demo discussion.
3. Gather consented real-site test videos across distance, occlusion, lighting and worker overlap. Measure detection latency, delivered frame age and end-to-end FPS on the target machine. Approximate CPU inference throughput is 2.7 FPS; frame skipping improves display continuity without creating extra detections.
4. Preserve reproducible setup, screenshot-based user guidance, exact model identity and honest limitations. Rebuild a corrupt virtual environment instead of depending indefinitely on PATH fallback.

## Engineering after the verified core

- Add authentication, role checks, TLS and protected evidence access before exposing the app. Camera credentials are currently plaintext in storage/responses.
- Replace position-based deduplication with evaluated persistent tracking if moving/overlapping workers require it. The existing cooldown already suppresses similar worker boxes; it does not create an incident on every frame.
- Evaluate a better face-visibility/orientation method. The current conservative frontal-face gate can fail; an unassessable mask is not compliance.
- Add bounded persistent upload jobs, cancellation and durable progress if long videos require restart recovery. Current uploads run off the event loop, accept one active upload per process, and provide key frames rather than an encoded annotated video.
- Consider a durable delivery queue/retry policy for production. Current SMTP/Twilio calls already run in worker threads with timeouts, result logs and per-worker/source/channel cooldowns. Preview mode blocks delivery independently of saved channel toggles.
- Add better native webcam-stall recovery and measure realistic multi-camera load before offering simultaneous monitoring. Configured cameras and Dashboard switching already work.
- Consider a different database/storage architecture only after measured SQLite contention or retention needs justify it. Keep DB/evidence backups coordinated.
- Reduce the frontend's large bundle by lazy-loading report generation. The production build currently warns about a chunk over 500 kB.
- Plan removal of Python/Pydantic/FastAPI deprecations before incompatible major-version upgrades.

CSV/PDF exports, review/archive workflow, camera CRUD/switching, upload results/downloads, persisted settings, real health and non-delivering email previews are implemented. Bulk violation deletion is disabled. None of the future work above authorizes sending alerts, deleting data or retraining automatically.
