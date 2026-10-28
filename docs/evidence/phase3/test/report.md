# ONNX evaluation

LEAKAGE WARNING: test/valid images were pooled into the augmentation workflow. Scores are likely optimistic and are not leakage-free generalization evidence; a clean retrain/evaluation is pending.

101-point interpolated AP at IoU .50:.05:.95. Production confidence cutoff unchanged; PR/AP are truncated at this cutoff and are NOT full-score Ultralytics/COCO metrics.

| Class | Precision | Recall | AP50 (thresholded) | AP50-95 (thresholded) |
|---|---:|---:|---:|---:|
| Face Mask | 0.9904 | 0.9786 | 0.9702 | 0.7870 |
| Helmet | 0.9536 | 0.9137 | 0.9034 | 0.6229 |
| Person | 0.9713 | 0.7596 | 0.7472 | 0.4544 |
| Safety Vest | 0.9617 | 0.9464 | 0.9365 | 0.6898 |

Command: `C:\Users\imran\AppData\Local\Temp\safeguard-master-6ceo9ejc\venv\Scripts\python.exe -B backend/tools/evaluate_onnx.py --split I:\AntiGRavity\My_FYP_Dataset\test --output docs/evidence/phase3/test`
