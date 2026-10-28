# Measured stream benchmark

| Measurement | Mean |
|---|---:|
| Detector ms | 258.248 |
| Delivered FPS | 14.887 |
| Frame age ms | 14.050 |
| Preview alert ms | 25.232 |

One warm-up excluded. Paced file replay; actual latest-frame/ACK/JPEG pipeline with an immediate local ACK sink. Excludes browser/network display latency. Preview MIME construction with real detected-violation screenshot; no DB or transports.

Command: `C:\Users\imran\AppData\Local\Temp\safeguard-master-6ceo9ejc\venv\Scripts\python.exe -B backend/tools/benchmark.py --video C:\Users\imran\AppData\Local\Temp\safeguard-master-6ceo9ejc\assets\workers.mp4 --frames 120 --output docs/evidence/phase2/benchmark`
