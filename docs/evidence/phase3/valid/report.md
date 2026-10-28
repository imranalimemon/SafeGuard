# ONNX evaluation

LEAKAGE WARNING: test/valid images were pooled into the augmentation workflow. Scores are likely optimistic and are not leakage-free generalization evidence; a clean retrain/evaluation is pending.

101-point interpolated AP at IoU .50:.05:.95. Production confidence cutoff unchanged; PR/AP are truncated at this cutoff and are NOT full-score Ultralytics/COCO metrics.

| Class | Precision | Recall | AP50 (thresholded) | AP50-95 (thresholded) |
|---|---:|---:|---:|---:|
| Face Mask | 0.9850 | 0.9398 | 0.9303 | 0.6981 |
| Helmet | 0.9547 | 0.9090 | 0.8949 | 0.6145 |
| Person | 0.9426 | 0.8027 | 0.7903 | 0.4755 |
| Safety Vest | 0.9521 | 0.9313 | 0.9237 | 0.6690 |

Command: `C:\Users\imran\AppData\Local\Temp\safeguard-master-6ceo9ejc\venv\Scripts\python.exe -B backend/tools/evaluate_onnx.py --split I:\AntiGRavity\My_FYP_Dataset\valid --output docs/evidence/phase3/valid`
