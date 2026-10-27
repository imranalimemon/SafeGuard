"""
SafeGuard AI — PPE Violation & Compliance Engine

Architectural Design:
1. Canonical Normalization: Maps variations ('hardhat', 'safety helmet', 'vest', 'mask')
   to standard classes: 'Helmet', 'Safety Vest', 'Face Mask'.
2. Anatomical Zoning: Restricts PPE association to physiologically realistic regions
   (e.g., Helmet on head [top 35%], Vest on torso [15%-70%]).
3. Bipartite Mutual Exclusion: Scores every (person, PPE) pair and assigns each PPE
   item to the single best-matching person. No two workers can claim the same helmet.
4. Detected Workers Only: Unclaimed PPE cannot create a worker or a violation.
5. Deterministic Violation Output: Explicitly guarantees 'missing_ppe', 'has_ppe',
   'status', and formatted 'violation_type'.
"""

from typing import List, Dict, Optional
from config import settings


def normalize_ppe_name(name: str) -> str:
    """Normalize any PPE class name variation to canonical form."""
    if not name:
        return ""
    n = name.strip().lower()
    if "helm" in n or "hard" in n:
        return "Helmet"
    if "vest" in n:
        return "Safety Vest"
    if "mask" in n or "shield" in n:
        return "Face Mask"
    if "person" in n or "worker" in n:
        return "Person"
    return name.strip()


def compute_iou(box_a: List[int], box_b: List[int]) -> float:
    """Standard Intersection-over-Union (IoU) between two bounding boxes."""
    xA = max(box_a[0], box_b[0])
    yA = max(box_a[1], box_b[1])
    xB = min(box_a[2], box_b[2])
    yB = min(box_a[3], box_b[3])

    interArea = max(0, xB - xA) * max(0, yB - yA)
    if interArea == 0:
        return 0.0

    boxAArea = (box_a[2] - box_a[0]) * (box_a[3] - box_a[1])
    boxBArea = (box_b[2] - box_b[0]) * (box_b[3] - box_b[1])

    return interArea / float(boxAArea + boxBArea - interArea)


def compute_containment(inner_box: List[int], outer_box: List[int]) -> float:
    """Fraction of inner_box contained inside outer_box (0.0 to 1.0)."""
    xA = max(inner_box[0], outer_box[0])
    yA = max(inner_box[1], outer_box[1])
    xB = min(inner_box[2], outer_box[2])
    yB = min(inner_box[3], outer_box[3])

    interArea = max(0, xB - xA) * max(0, yB - yA)
    if interArea == 0:
        return 0.0

    innerArea = (inner_box[2] - inner_box[0]) * (inner_box[3] - inner_box[1])
    if innerArea <= 0:
        return 0.0

    return interArea / float(innerArea)


def get_anatomical_zone(person_box: List[int], ppe_type: str) -> List[int]:
    """Calculate the expected anatomical bounding box for a given PPE type
    relative to the person's bounding box."""
    px1, py1, px2, py2 = person_box
    pw = max(1, px2 - px1)
    ph = max(1, py2 - py1)

    if ppe_type == "Helmet":
        # Head zone: extends slightly above the person box up to top 35% of body
        return [
            int(px1 - 0.15 * pw),
            int(py1 - 0.15 * ph),
            int(px2 + 0.15 * pw),
            int(py1 + 0.35 * ph),
        ]
    elif ppe_type == "Face Mask":
        # A close-up person may contain only head/torso. Allow the upper half
        # while keeping masks horizontally within the central head/body area.
        return [
            int(px1 + 0.05 * pw),
            py1,
            int(px2 - 0.05 * pw),
            int(py1 + 0.50 * ph),
        ]
    elif ppe_type == "Safety Vest":
        # Torso zone: from top 15% to 70% of body, excluding the lower legs.
        return [
            int(px1 - 0.15 * pw),
            int(py1 + 0.15 * ph),
            int(px2 + 0.15 * pw),
            int(py1 + 0.70 * ph),
        ]
    return person_box


def calculate_association_score(person_box: List[int], ppe_box: List[int], ppe_type: str) -> float:
    """Calculate an association compatibility score between a person and a PPE item.
    Returns a float between 0.0 (incompatible) and 1.0 (perfect match)."""
    # 1. Containment in the person's overall bounding box
    full_containment = compute_containment(ppe_box, person_box)

    # 2. Containment in the specific anatomical zone
    zone = get_anatomical_zone(person_box, ppe_type)
    zone_containment = compute_containment(ppe_box, zone)

    # Body containment alone does not show that equipment is worn. Require
    # most of the item to overlap its anatomical zone, with its center there.
    ppe_cy = (ppe_box[1] + ppe_box[3]) / 2.0
    if zone_containment < 0.50 or not zone[1] <= ppe_cy <= zone[3]:
        return 0.0

    # 3. Horizontal centroid alignment (a vest or helmet should align with the body axis)
    p_cx = (person_box[0] + person_box[2]) / 2.0
    ppe_cx = (ppe_box[0] + ppe_box[2]) / 2.0
    pw = max(1, person_box[2] - person_box[0])
    h_dist_ratio = abs(p_cx - ppe_cx) / float(pw)

    # If center is way too far horizontally, reject (belonging to another person)
    if h_dist_ratio > 0.65:
        return 0.0

    # Weighted composite score
    alignment_score = max(0.0, 1.0 - h_dist_ratio)
    score = (zone_containment * 0.55) + (full_containment * 0.30) + (alignment_score * 0.15)
    return score


def compute_violations(detections: List[Dict], required_ppe: Optional[List[str]] = None) -> List[Dict]:
    """Analyze PPE compliance for detected persons only.

    Returns a list of dictionaries for each detected person:
    {
        "person_bbox": [x1, y1, x2, y2],
        "status": "COMPLIANT" | "VIOLATION",
        "missing_ppe": ["Helmet", "Safety Vest", "Face Mask"],  # Exact list of missing items
        "has_ppe": ["Helmet", "Safety Vest"],                  # Verified items worn
        "violation_type": "Missing: Face Mask",                 # Human-readable summary
        "confidence": float,
        "compliance_score": float (0.0 to 1.0)
    }
    """
    if required_ppe is None:
        required_ppe = list(settings.REQUIRED_PPE)

    # Normalize required PPE items
    canonical_required = []
    for item in required_ppe:
        c = normalize_ppe_name(item)
        if c and c not in canonical_required:
            canonical_required.append(c)

    if not canonical_required:
        canonical_required = ["Helmet", "Safety Vest"]

    # Separate Person and PPE detections
    persons = [d for d in detections if d.get("class_id") == settings.PERSON_CLASS_ID]
    ppes = [d for d in detections if d.get("class_id") != settings.PERSON_CLASS_ID]

    # Pre-filter PPEs to only those relevant to requirements
    filtered_ppes = []
    for ppe in ppes:
        canon_name = normalize_ppe_name(ppe.get("class_name", ""))
        if canon_name:
            filtered_ppes.append({**ppe, "canonical_name": canon_name})

    # Step 1: Bipartite Association between Persons and PPEs
    # Each PPE can only belong to ONE person (mutual exclusion)
    candidate_matches = []
    for p_idx, person in enumerate(persons):
        for ppe_idx, ppe in enumerate(filtered_ppes):
            score = calculate_association_score(person["bbox"], ppe["bbox"], ppe["canonical_name"])
            if score > 0.0:
                candidate_matches.append((score, p_idx, ppe_idx))

    # Sort matches by compatibility score descending (best match first)
    candidate_matches.sort(key=lambda x: x[0], reverse=True)

    person_ppe_map: Dict[int, List[Dict]] = {i: [] for i in range(len(persons))}
    assigned_ppes = set()
    assigned_ppe_types_per_person: Dict[int, set] = {i: set() for i in range(len(persons))}

    for score, p_idx, ppe_idx in candidate_matches:
        ppe = filtered_ppes[ppe_idx]
        ppe_type = ppe["canonical_name"]

        # An item can only be assigned once, and one person gets one instance of each type
        if ppe_idx not in assigned_ppes and ppe_type not in assigned_ppe_types_per_person[p_idx]:
            assigned_ppes.add(ppe_idx)
            assigned_ppe_types_per_person[p_idx].add(ppe_type)
            person_ppe_map[p_idx].append(ppe)

    # Step 2: Ignore unclaimed PPE; compute compliance only for real detections.
    results = []
    for p_idx, person in enumerate(persons):
        matched_ppes = person_ppe_map.get(p_idx, [])
        has_ppe = sorted(list(set(ppe["canonical_name"] for ppe in matched_ppes)))

        # Missing elements: required items that are NOT in has_ppe
        missing_ppe = [item for item in canonical_required if item not in has_ppe]

        status = "VIOLATION" if len(missing_ppe) > 0 else "COMPLIANT"
        violation_type = f"Missing: {', '.join(missing_ppe)}" if missing_ppe else "Compliant"

        total_req = len(canonical_required)
        compliance_score = round((total_req - len(missing_ppe)) / float(total_req), 2) if total_req > 0 else 1.0

        results.append({
            "person_bbox": [int(x) for x in person["bbox"]],
            "status": status,
            "missing_ppe": missing_ppe,
            "has_ppe": has_ppe,
            "violation_type": violation_type,
            "confidence": round(float(person.get("confidence", 0.8)), 3),
            "compliance_score": compliance_score,
        })

    return results
