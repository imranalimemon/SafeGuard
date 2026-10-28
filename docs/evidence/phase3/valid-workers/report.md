# Worker-level exploratory evaluation

LEAKAGE WARNING: test/valid images were pooled into the augmentation workflow. Scores are likely optimistic and are not leakage-free generalization evidence; a clean retrain/evaluation is pending.

Worker/PPE relations are geometric annotation proxies. Absence assumes exhaustive PPE labels. Ambiguous associations are unknown. Mask absence is assessable ONLY with independent human face-visibility labels; model visibility predictions are never used as truth. These are exploratory proxy scores, not validated compliance accuracy.

```json
{
  "compliant": {
    "tp": 0,
    "fp": 0,
    "fn": 0,
    "precision": null,
    "recall": null
  },
  "violation": {
    "tp": 2648,
    "fp": 187,
    "fn": 769,
    "precision": 0.9340388007054674,
    "recall": 0.774948785484343
  }
}
```

Command: `C:\Users\imran\AppData\Local\Temp\safeguard-master-6ceo9ejc\venv\Scripts\python.exe -B backend/tools/violation_eval.py --predictions docs/evidence/phase3/valid/predictions.json --output docs/evidence/phase3/valid-workers`
