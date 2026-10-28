# Reversible ONNX model replacement

The current detector expects one float input `1x3x640x640`, RGB letterbox preprocessing with pixels divided by 255, and one output `1x8x8400` without embedded NMS. Required class order: `0 Face Mask`, `1 Helmet`, `2 Person`, `3 Safety Vest`. ONNX metadata records declared names; visual inspection is still needed to verify learned semantics.

1. Keep the candidate outside the deployed path. Run `python -B backend/tools/validate_model.py --model <candidate.onnx> --images-dir <read-only-images-folder> --output <validation.json>`. If names metadata is absent, supply a JSON object with `--class-map`; the output flags this as operator-provided evidence.
2. Inspect all five results and annotated outputs from `backend/tools/sanity_check.py` on the same fixed 12-image set. Run the isolated detector/PPE tests and the evaluation/violation tools on a leakage-free held-out split when available. Do not compare AP figures from different confidence cutoffs or different splits as if equivalent.
3. Stop the backend. Record SHA-256 hashes of both files (`Get-FileHash <path> -Algorithm SHA256` on Windows). Copy the deployed file to `best_previous.onnx` in a private backup directory **outside git**. Verify its hash equals the recorded old hash. Do not remove the original until that verification succeeds.
4. Copy the validated candidate to `backend/best.onnx`; record its new hash and validation/evaluation output in the release notes. Preserve the candidate and old backup separately. Restart with a disposable DB and preview delivery first; confirm health reports the actual provider and visually inspect the fixed sanity set.
5. Roll back by stopping the backend, copying the verified old backup back to `backend/best.onnx`, verifying the old hash, and restarting. Re-run health and sanity checks. A running ONNX session does not reload automatically when its file changes.

No model was swapped or backed over during this task. Real database migration and live alert delivery are separate deployment actions. Never claim improved model accuracy until a leakage-free evaluation supports it.
