"""Run real-model sanity checks directly, without API, DB, or alert imports.

Run from the project root with: python -B backend/tools/sanity_check.py
Annotated comparisons and a JSON report are written only outside the repository.
"""
import argparse
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import statistics
import sys
import time
import traceback


sys.dont_write_bytecode = True
BACKEND = Path(__file__).resolve().parents[1]
REPOSITORY = BACKEND.parent
DEFAULT_PREFIXES = (
    "chv_test_00003", "chv_test_00041", "chv_test_00062", "chv_test_00110",
    "chv_test_00033", "chv_test_00094", "har_test_00001", "har_test_01223",
    "men_test_00000", "men_test_01222", "fac_test_00005", "fac_test_01220",
)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, default=Path(r"I:\AntiGRavity\My_FYP_Dataset\test\images"))
    parser.add_argument("--output-dir", type=Path, default=Path(r"I:\AntiGRavity\sanity_output"))
    parser.add_argument("--images", nargs=12, help="Optional exact filenames of 12 test images")
    parser.add_argument("--confidence", type=float, help="Process-only threshold override; never saves config")
    parser.add_argument("--required-ppe", nargs="+", choices=["Helmet", "Safety Vest", "Face Mask"],
                        help="Process-only required-PPE override")
    parser.add_argument("--compare-required-ppe", nargs="+", choices=["Helmet", "Safety Vest", "Face Mask"],
                        help="Recompute an earlier PPE policy on identical detections; never reads a database")
    args = parser.parse_args()
    if args.confidence is not None and not 0 < args.confidence <= 1:
        parser.error("--confidence must be greater than 0 and at most 1")
    input_dir = args.input_dir.resolve()
    output_dir = args.output_dir.resolve()
    if output_dir == REPOSITORY or REPOSITORY in output_dir.parents:
        parser.error("Output images must be outside the repository")

    if args.images:
        if any(Path(name).name != name for name in args.images):
            parser.error("--images accepts filenames only")
        image_paths = [input_dir / name for name in args.images]
    else:
        image_paths = []
        for prefix in DEFAULT_PREFIXES:
            matches = sorted(input_dir.glob(prefix + "_*"))
            if len(matches) != 1:
                parser.error(f"Expected one image matching {prefix}, found {len(matches)}")
            image_paths.append(matches[0])

    if len(set(image_paths)) != 12 or not all(p.is_file() for p in image_paths):
        parser.error("Exactly 12 distinct, existing input images are required")
    output_paths = [output_dir / f"{i:02d}_{path.name}" for i, path in enumerate(image_paths, 1)]
    report_path = output_dir / 'sanity_results.json'
    if report_path.exists() or any(path.exists() for path in output_paths):
        parser.error("Refusing to overwrite existing output images; choose a fresh output directory")

    # Prevent config's import-time directory creation from targeting the repo.
    # Notification transports remain disabled in this process as an extra guard.
    output_dir.mkdir(parents=True, exist_ok=True)
    os.environ["SCREENSHOT_DIR"] = str(output_dir)
    os.environ["ENABLE_EMAIL_ALERTS"] = "false"
    os.environ["ENABLE_WHATSAPP_ALERTS"] = "false"
    os.environ["ALERT_DEBUG_MODE"] = "false"
    os.environ["ALERT_DELIVERY_MODE"] = "preview"
    os.environ["DATABASE_URL"] = "sqlite:///:memory:"
    sys.path.insert(0, str(BACKEND))

    import cv2
    import numpy as np
    from config import settings
    from detection.annotator import annotate_frame
    from detection.model import PPEDetector
    from detection.violation_logic import compute_violations

    if args.confidence is not None:
        settings.CONFIDENCE_THRESHOLD = args.confidence
    if args.required_ppe is not None:
        settings.REQUIRED_PPE = args.required_ppe

    model_path = BACKEND / "best.onnx"
    started = time.perf_counter()
    detector = PPEDetector(model_path=str(model_path))
    load_ms = (time.perf_counter() - started) * 1000
    config_report = {
        "model": str(model_path), "sha256": hashlib.sha256(model_path.read_bytes()).hexdigest(),
        "providers": detector.session.get_providers(), "confidence": settings.CONFIDENCE_THRESHOLD,
        "nms_iou": settings.IOU_THRESHOLD, "required_ppe": settings.REQUIRED_PPE,
        "model_load_ms": round(load_ms, 2),
        "timing": "Detection includes preprocessing, ONNX inference, and NMS; excludes loading, rules, annotation, and saving",
    }
    print("CONFIG", json.dumps(config_report), flush=True)

    # Warm up on a blank synthetic frame, not an extra dataset image.
    detector.detect(np.zeros((640, 640, 3), dtype=np.uint8))
    times = []
    failures = []
    total_detections = Counter()
    total_violations = 0
    results = []
    baseline_violations = 0
    mask_not_assessable = 0
    missing_masks = 0
    for image_number, (image_path, output_path) in enumerate(zip(image_paths, output_paths), 1):
        try:
            image = cv2.imread(str(image_path))
            if image is None:
                raise ValueError("OpenCV could not decode image")
            started = time.perf_counter()
            detections = detector.detect(image)
            detection_ms = (time.perf_counter() - started) * 1000
            workers = compute_violations(detections, frame=image)
            baseline = compute_violations(detections, required_ppe=args.compare_required_ppe, frame=image) if args.compare_required_ppe else None
            annotated = annotate_frame(image, detections, workers)
            worker_results = []
            for index, worker in enumerate(workers, 1):
                x1, y1, _, y2 = worker["person_bbox"]
                label_position = (max(0, x1 + 3), max(15, min(image.shape[0] - 5, y2 - 8)))
                cv2.putText(annotated, f"W{index}", label_position, cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 3)
                cv2.putText(annotated, f"W{index}", label_position, cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
                worker_results.append({"worker": index, **worker})

            # Keep the original visible: the existing annotator can obscure heads.
            comparison = cv2.hconcat([image, annotated])
            comparison = cv2.copyMakeBorder(comparison, 42, 0, 0, 0, cv2.BORDER_CONSTANT, value=(245, 245, 245))
            cv2.putText(comparison, f"{image_number:02d} {image_path.name}", (8, 15), cv2.FONT_HERSHEY_SIMPLEX, 0.35, (0, 0, 0), 1)
            cv2.putText(comparison, "ORIGINAL", (8, 34), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 0, 0), 1)
            cv2.putText(comparison, "ANNOTATED", (image.shape[1] + 8, 34), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 0, 0), 1)
            encoded, buffer = cv2.imencode(".jpg", comparison, [cv2.IMWRITE_JPEG_QUALITY, 95])
            if not encoded:
                raise ValueError("OpenCV could not encode annotated image")
            with output_path.open("xb") as output_file:
                output_file.write(buffer.tobytes())

            counts = Counter(d["class_name"] for d in detections)
            annotation_counts = Counter()
            label_path = input_dir.parent / "labels" / (image_path.stem + ".txt")
            if label_path.is_file():
                for line in label_path.read_text(encoding="utf-8").splitlines():
                    if line.strip():
                        annotation_counts[settings.CLASS_NAMES[int(line.split()[0])]] += 1
            result = {
                "image_number": image_number, "filename": image_path.name,
                "image_shape": list(image.shape[:2]), "detection_ms": round(detection_ms, 2),
                "detections_per_class": {name: counts[name] for name in settings.CLASS_NAMES.values()},
                "dataset_annotation_counts": dict(annotation_counts),
                "workers_found": len(workers), "workers": worker_results,
                "final_violations": [w for w in worker_results if w["status"] == "VIOLATION"],
                "detections": detections, "output_image": str(output_path),
            }
            if baseline is not None:
                result['comparison'] = {
                    'required_ppe': args.compare_required_ppe,
                    'violations': sum(w['status'] == 'VIOLATION' for w in baseline),
                    'helmet_vest_decisions_match': all(
                        set(before['missing_ppe']) & {'Helmet', 'Safety Vest'} == set(after['missing_ppe']) & {'Helmet', 'Safety Vest'}
                        for before, after in zip(baseline, workers)),
                    'changed_workers': [
                        {'worker': i, 'before_status': before['status'], 'after_status': after['status'],
                         'before_missing': before['missing_ppe'], 'after_missing': after['missing_ppe'],
                         'mask_assessment': after['mask_assessment']}
                        for i, (before, after) in enumerate(zip(baseline, workers), 1)
                        if before['status'] != after['status'] or before['missing_ppe'] != after['missing_ppe']
                    ],
                }
                baseline_violations += result['comparison']['violations']
            mask_not_assessable += sum(w['mask_assessment'] == 'not assessable' for w in workers)
            missing_masks += sum('Face Mask' in w['missing_ppe'] for w in workers)
            results.append(result)
            times.append(detection_ms)
            total_detections.update(counts)
            total_violations += len(result["final_violations"])
            print("RESULT_JSON " + json.dumps(result), flush=True)
        except Exception as exc:
            failures.append({"filename": image_path.name, "error": f"{type(exc).__name__}: {exc}"})
            traceback.print_exc()
            print("ERROR_JSON " + json.dumps(failures[-1]), flush=True)

    forbidden = [name for name in sys.modules if name.split(".")[0] in {"api", "db", "alerts"}]
    summary = {
        "requested": 12, "completed": len(times), "failures": failures,
        "average_detection_ms": round(statistics.mean(times), 2) if times else None,
        "median_detection_ms": round(statistics.median(times), 2) if times else None,
        "min_detection_ms": round(min(times), 2) if times else None,
        "max_detection_ms": round(max(times), 2) if times else None,
        "forbidden_modules_imported": forbidden, "output_dir": str(output_dir),
        "confidence": settings.CONFIDENCE_THRESHOLD, "required_ppe": settings.REQUIRED_PPE,
        "total_detections_per_class": {name: total_detections[name] for name in settings.CLASS_NAMES.values()},
        "total_violations": total_violations,
        "mask_not_assessable_workers": mask_not_assessable,
        "missing_mask_workers": missing_masks,
        "comparison_required_ppe": args.compare_required_ppe,
        "comparison_total_violations": baseline_violations if args.compare_required_ppe else None,
    }
    with report_path.open('x', encoding='utf-8') as output:
        json.dump({'config': config_report, 'results': results, 'summary': summary}, output, indent=2)
    print("SUMMARY_JSON " + json.dumps(summary), flush=True)
    return 1 if failures or forbidden else 0


if __name__ == "__main__":
    raise SystemExit(main())
