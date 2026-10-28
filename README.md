# SafeGuard

SafeGuard is a React + FastAPI construction-safety project. A YOLOv8-family PPE model runs through ONNX Runtime. It detects Face Mask, Helmet, Person and Safety Vest, associates equipment with detected workers, and records reviewable violations with annotated evidence.

**Current limits:** CPU inference is slower than camera capture; the stream reuses sampled results. Missing-mask assessment uses a frontal-face heuristic. Position-based cooldowns are not persistent identity tracking. Existing test/validation data leaked into augmentation, so reported model metrics are provisional. See [limitations](docs/limitations.md) and [measured facts](docs/final-year-report-notes.md).

## Clean-machine setup

Verified backend installation: Windows CPython 3.14.0 in a fresh temporary venv. Node 24 was used for frontend tests/build. The shell launcher also started both services under Git Bash on Windows; native Linux camera/codec behavior is unverified.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r backend/requirements.txt
python -m pip check
npm install
npm --prefix frontend install
```

Keep `backend/best.onnx` available. The runtime contract is `1x3x640x640` input and `1x8x8400` output without embedded NMS. [Model validation and rollback](docs/model-swap.md).

Set secrets in the process environment; do not commit them. For first startup, choose an admin password of at least 12 characters. The password is stored as a salted hash in SQLite. Later environment changes do not reset that account.

```powershell
$sgSecret = Read-Host 'Choose initial admin password' -AsSecureString
$env:SAFEGUARD_ADMIN_PASSWORD = [System.Net.NetworkCredential]::new('', $sgSecret).Password
# Generate ONCE, save securely outside the repo, and reuse this same key thereafter:
$env:SAFEGUARD_CREDENTIAL_KEY = python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
$env:ALERT_DELIVERY_MODE = 'preview'
.\start.bat
```

**Retain the encryption key securely before stopping that terminal.** Every restart must receive the same `SAFEGUARD_CREDENTIAL_KEY`; losing it prevents camera-credential decryption. Use an OS-managed secret store or a private secret file loaded into the environment. Never generate a replacement key for an existing encrypted camera database.

On Linux/macOS: activate `.venv/bin/activate`, set the same environment variables with `export`, then run `bash start.sh`. Both launchers run the backend at `127.0.0.1:8000` and Vite at `http://127.0.0.1:5173`; Ctrl+C stops their process manager. An explicit `ALLOWED_ORIGINS` must include the actual frontend origin. Launchers provide the local Vite origins when no process override is present. Startup output alone is not a health check.

For disposable QA, set these **before starting**:

```powershell
$env:DATABASE_URL = 'sqlite:///C:/path/to/temporary/trial.db'
$env:SCREENSHOT_DIR = 'C:/path/to/temporary/screenshots'
$env:LOG_DIR = 'C:/path/to/temporary/logs'
```

The default SQLite URL is relative to the backend working directory. Do not start against an existing production database merely to try the UI. Startup creates missing tables, adds legacy columns, restores settings and encrypts legacy camera credentials. Back up the DB/evidence and retain the key before a real deployment.

## Use

1. Open Vite and sign in (`admin` unless `SAFEGUARD_ADMIN_USERNAME` was configured for initial setup).
2. Add/test a camera, then select it on Dashboard. Camera selection starts/switches the stream; Stop closes it. A local webcam uses its numeric index; network sources use HTTP(S)/RTSP(S).
3. Upload JPG/PNG/WEBP or supported video files. Review worker statuses and download annotations/key frames.
4. Review evidence before acknowledging/escalating. Archive hides records from the default list and preserves files. CSV/PDF respect current filters.
5. Save site PPE, confidence, recipients, cooldowns and frame interval in Settings. Defaults require Helmet + Safety Vest + Face Mask. Unknown face visibility does not create a missing-mask violation.
6. Inspect email previews and System Logs. Preview mode contacts neither SMTP nor Twilio.

Live delivery is deliberately gated: configure `ALERT_DELIVERY_MODE=live` at startup, validate recipients/transport configuration, then type `ENABLE LIVE ALERTS` in Settings. A restart returns the process to unconfirmed preview. A banner appears when delivery is actually live. Real delivery was **not** tested during this work. See [alert flow](docs/ml-violations-alerts.md).

## Verification and documentation

- [User guide](docs/user-guide.md), [architecture](docs/architecture.md), [API contract](docs/backend_api_contract.md)
- [Backend](docs/backend.md), [frontend](docs/frontend.md), [database](docs/database.md)
- [Testing/evaluation commands](docs/testing.md), [final QA](docs/qa-report.md)
- [Phase reports](docs/progress/phase1.md), [phase 2](docs/progress/phase2.md), [phase 3](docs/progress/phase3.md), [phase 4](docs/progress/phase4.md), [phase 5](docs/progress/phase5.md)

Never combine all twelve original backend modules in one unittest process on this machine; use the documented split. No final accuracy claim is supported until a leakage-free retrain/evaluation and independently labeled worker-compliance subset exist.
