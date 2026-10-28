# Phase 1 — access protection and robustness

## Changes

- Single-admin login uses a salted PBKDF2 password hash. The database holds hashed session tokens; cookies are HttpOnly/SameSite Strict with an eight-hour expiry. Logout revokes the session. API routes, WebSockets, OpenAPI/docs and evidence downloads require a session. Mutations require CSRF tokens and configured origins.
- First startup requires `SAFEGUARD_ADMIN_PASSWORD` (at least 12 characters) and `SAFEGUARD_CREDENTIAL_KEY` (Fernet key). The password initializes the account only; changing the environment does not silently reset an existing account. Set `SAFEGUARD_COOKIE_SECURE=true` when serving over HTTPS.
- Camera usernames, passwords and network URLs are encrypted, including credentials embedded in URLs. Responses omit credentials and URL query tokens. Existing camera records migrate transactionally at startup. Keep the encryption key stable and backed up separately from the database.
- Camera URLs accept HTTP(S)/RTSP(S); webcam inputs accept indexes. Evidence routes reject traversal and unsupported extensions. Request size limits supplement existing upload signature/decode limits. Validation responses omit submitted values. Stream failures no longer expose arbitrary exception text.
- Lifespan replaces deprecated startup/shutdown decorators; UTC timestamps use timezone-aware acquisition while retaining existing SQLite UTC storage. Pydantic uses ConfigDict.
- Dependencies are pinned and contain exactly one OpenCV distribution. A clean Windows Python 3.14 venv installed them successfully.

## Files

Backend: `security.py`, `credentials.py`, `evidence.py`, `config.py`, `main.py`, `db/models.py`, `api/cameras.py`, `api/stats.py`, `api/upload.py`, `api/violations.py`, `detection/camera_capture.py`, `detection/deduplicator.py`, `websocket/live.py`, `websocket/manager.py`, `alerts/debug_receiver.py`, `requirements.txt`, `test_security.py`, `test_status.py`, `test_live_stream.py`.

Frontend: `src/context/Auth.jsx`, `src/App.jsx`, `src/api/client.js`, `src/api/cameraForm.js`, `src/components/layout/Navbar.jsx`, `src/pages/CamerasPage.jsx`, `src/index.css`, `test/ui_status.test.cjs`.

Verification: `tools/verify_phase.py`, `tools/qa_security.cjs`, this report and `docs/evidence/phase1/`.

## Verification and evidence

Command: `<fresh-venv-python> -B tools/verify_phase.py --phase 1`.
The runner preserves the required ten-module group and separate camera/launcher processes; security tests also run separately. Exact commands, exit codes and output: [tests.json](../evidence/phase1/tests.json) and numbered logs in that directory. Backend baseline: 130 tests; camera: 3; launchers: 2; security: 9. Frontend: 19 Node tests, rendering assertions including login, and production build.

Clean installation: `python -m venv <temp>/venv`, then `<temp>/venv/Scripts/python -m pip install -r backend/requirements.txt --report <temp>/pip-install-report.json`. Saved [install output](../evidence/phase1/requirements-install.log), [package report](../evidence/phase1/pip-install-report.json), [pip check and imports](../evidence/phase1/environment-check.log). Downloads needed retries; final install/import/check succeeded.

Browser command: `node tools/qa_security.cjs <Playwright-module-directory> <temporary-auth.json>`. [Results](../evidence/phase1/browser.json), [login screenshot](../evidence/phase1/login.png), [authenticated screenshot](../evidence/phase1/authenticated.png). Saw login, real model/database health, session restoration after reload, logout and subsequent 401. No browser JavaScript errors. The trial used a disposable copy of the earlier QA database and preview delivery only.

The first regression run caught a missing timezone import; [initial failure output](../evidence/phase1/initial-failure.log) is retained. It was fixed. Initial browser attempts also exposed a configured-origin mismatch and external-font loading delays. Trial origins were explicitly configured, and browser navigation now waits for DOM readiness. Cancelled React session checks cannot overwrite newer login state.

## Needs Imran

- Choose a strong deployment password and securely retain the encryption key before first real-database startup. No real database was migrated during this phase. Losing the key means saved camera credentials cannot be recovered; old backups may still contain plaintext credentials.
- Set `ALLOWED_ORIGINS` to the actual frontend origin. `localhost` and `127.0.0.1` are different origins. The trial explicitly allowed both local Vite origins; `.env` was not edited.
- Physical cameras, real SMTP/Twilio delivery, HTTPS deployment and password recovery are not validated here. This is a single-admin system, not a multi-user identity service. Session access is checked at WebSocket connection time; ongoing-stream revocation belongs to the reliability work.
