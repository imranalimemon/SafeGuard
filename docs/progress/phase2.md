# Phase 2 — stream reliability, providers and operational visibility

## Changes

The latest-frame slot and one-frame acknowledgement window remain bounded. Camera failures clear stale frames and retry with exponential backoff, capped at the configured attempt budget (`STREAM_RECONNECT_ATTEMPTS`, default 3). Each connection has independent capture/error state; selecting another camera closes the old connection. Reconnect status keeps the client informed. Active streams recheck the database session each second. Shutdown signals capture/inference, waits for owned work with deadlines, and releases captures on their owning threads. A disconnected generation cannot publish its stale inference result after reconnection.

ONNX Runtime tries installed CUDA/DirectML providers, then CPU. DirectML uses sequential execution and disables memory-pattern optimization. Initialization failure retries CPU; health/footer read the actual session providers. No thresholds, NMS or PPE rules changed.

Operational logs persist with 2 MB rotation and four backup files. Configured secrets and URL credentials/query strings are redacted. The authenticated System Logs page reads a bounded tail of the current log. Help/Safety Protocols contains actual operating instructions and limitations. Camera responses/cards include active stream status.

## Files

Backend: `config.py`, `main.py`, `api/cameras.py`, `api/system.py`, `detection/model.py`, `detection/providers.py`, `logging_setup.py`, `websocket/live.py`, `websocket/manager.py`, `websocket/registry.py`, `tools/benchmark.py`, `test_reliability.py`, `test_saved_settings.py`, `test_security.py`.
Frontend: `src/App.jsx`, `src/api/liveStream.js`, `src/components/layout/Footer.jsx`, `src/components/layout/Sidebar.jsx`, `src/pages/CamerasPage.jsx`, `src/pages/HelpPage.jsx`, `src/pages/SystemLogsPage.jsx`, `test/live_stream.test.mjs`, `test/ui_status.test.cjs`.
Also `.gitignore`, `tools/qa_reliability.cjs`, this report and `docs/evidence/phase2/`.

## Tests and measured evidence

Command: `<fresh-venv-python> -B tools/verify_phase.py --phase 2 --extra backend.test_security backend.test_reliability`. All groups passed: 130 core, 3 camera, 2 launcher, 9 security, 6 reliability tests; 20 frontend Node tests, rendering assertions and production build. [Commands and exit codes](../evidence/phase2/tests.json), numbered logs alongside it.

Benchmark command and exact raw samples/summary: [benchmark.json](../evidence/phase2/benchmark/benchmark.json), [table](../evidence/phase2/benchmark/benchmark.md). On CPU, replaying 120 frames from the disposable `workers.mp4` at its recorded 15 FPS: mean detector 258.248 ms, delivered 14.887 FPS, frame age 14.050 ms, preview MIME generation 25.232 ms. Warm-up excluded. These measurements use the real detector, rules, annotation and latest-frame/ACK loop with an immediate local sink; they exclude browser/network display delay. Cached boxes can lag current motion despite fresh image frames. Alert timing includes MIME construction and screenshot attachment, not SMTP or database persistence. No DB or transport was used by the benchmark.

Browser command: `node tools/qa_reliability.cjs <Playwright-directory> <temporary-auth.json>`. [Results](../evidence/phase2/browser.json): saw annotated video replay, camera switching to a failed loopback RTSP source, reconnect message with cleared frame, switching back to working replay, genuine operational logs, and Help content. [Stream](../evidence/phase2/stream.png), [reconnect](../evidence/phase2/reconnecting.png), [logs](../evidence/phase2/logs.png), [help](../evidence/phase2/help.png). No JavaScript errors. Initial browser script incorrectly clicked Start after selection had already started streaming; the test was corrected to follow actual behavior.

## Needs Imran

- GPU/DirectML execution has only synthetic provider-selection/fallback coverage; this installation actually used CPU. Install a compatible accelerator runtime separately and verify reported providers before claiming GPU performance.
- Physical camera drivers may block beyond their requested timeout. Shutdown logs this condition; Python cannot safely kill a stuck native camera call. Physical webcam disconnect/reconnect testing is still required.
- The benchmark is local replay, not an end-to-end camera-to-browser latency certification. Test the target deployment hardware/network and real SMTP separately. This task remains preview-only.
- Each viewer currently owns a stream/capture and shares the model session. High viewer counts need capacity testing; no unlimited multi-camera throughput is claimed.
