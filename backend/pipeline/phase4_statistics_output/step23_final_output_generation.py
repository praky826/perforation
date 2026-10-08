"""Step 23: Final Output Generation.

File: backend/pipeline/phase4_statistics_output/step23_final_output_generation.py
Draws a score-colored marker at every hole on the overview photo, highlights
each candidate region, and writes a per-hole results table. Uses OpenCV drawing
and a plain CSV table (both sanctioned by the algorithm document) and marks the
session complete.
"""

import csv
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

import cv2
import numpy as np

from backend.config.pipeline_constants import COMPOSITE_FIELD_ORDER
from backend.pipeline.phase2_geometry_classification.step06_stamp_boundary_orientation import StampFrame
from backend.pipeline.phase2_geometry_classification.step07_perforation_candidate_detection import HoleRecord
from backend.session.session_manager import SessionManager

logger = logging.getLogger(__name__)


def score_to_bgr(combined_score: float, threshold: float) -> tuple:
    """Map combined_score (relative to threshold) to a blue->red BGR color."""
    ratio = 0.0 if threshold <= 0 else min(1.0, max(0.0, combined_score / threshold))
    b = int(round(255 * (1.0 - ratio)))
    r = int(round(255 * ratio))
    return (b, 0, r)


def _load_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def run_step23(
    session_id: str,
    holes: List[HoleRecord],
    overview_image: np.ndarray,
    reference_groups: Dict[str, Dict[str, Any]],
    candidate_regions: List[Dict[str, Any]],
    session_manager: Optional[SessionManager] = None
) -> Dict[str, str]:
    """Execute Step 23: Final Output Generation. Returns output paths."""
    if session_manager is None:
        session_manager = SessionManager()

    session_dir = session_manager.get_session_dir(session_id)
    manifest = session_manager.get_manifest_manager(session_id)
    holes_dir = session_dir / "holes"
    results_dir = session_dir / "results"
    results_dir.mkdir(parents=True, exist_ok=True)

    # Prepare BGR canvas from the orientation-normalized overview.
    canvas_u8 = (np.clip(overview_image, 0.0, 1.0) * 255.0).astype(np.uint8)
    canvas = cv2.cvtColor(canvas_u8, cv2.COLOR_GRAY2BGR)
    marker_radius = max(3, canvas.shape[1] // 200)

    table_rows: List[Dict[str, Any]] = []

    for h in holes:
        score = _load_json(holes_dir / h.hole_id / "score.json")
        descriptors = _load_json(holes_dir / h.hole_id / "descriptors.json")
        combined = float(score.get("combined_score", 0.0))
        outlier = score.get("outlier", {})
        threshold = float(outlier.get("threshold_used", 0.0))
        is_outlier = bool(outlier.get("is_outlier", False))
        low_conf = bool(reference_groups.get(h.hole_id, {}).get("low_confidence", False))

        color = score_to_bgr(combined, threshold)
        cx, cy = int(round(h.centroid_px[0])), int(round(h.centroid_px[1]))
        cv2.circle(canvas, (cx, cy), marker_radius, color, thickness=-1)
        if is_outlier:
            cv2.circle(canvas, (cx, cy), marker_radius + 2, (0, 0, 255), thickness=1)

        composite = descriptors.get("composite", {})
        vector = composite.get("vector", [])
        field_map = {name: (vector[i] if i < len(vector) else "") for i, name in enumerate(COMPOSITE_FIELD_ORDER)}

        row = {
            "hole_id": h.hole_id,
            "edge": h.edge,
            "position_index": h.position_index,
            "type": h.type
        }
        row.update({name: field_map[name] for name in COMPOSITE_FIELD_ORDER})
        row.update({
            "combined_score": combined,
            "is_outlier": is_outlier,
            "threshold_used": threshold,
            "low_confidence": low_conf
        })
        table_rows.append(row)

    # Draw candidate regions.
    for region in candidate_regions:
        pts = np.array(region.get("region_coords_px", []), dtype=np.int32)
        if pts.shape[0] >= 2:
            cv2.polylines(canvas, [pts.reshape(-1, 1, 2)], isClosed=True, color=(0, 255, 255), thickness=2)

    annotated_path = results_dir / "annotated_overview.png"
    cv2.imwrite(str(annotated_path), canvas)

    # Write results table (plain CSV).
    table_path = results_dir / "results_table.csv"
    fieldnames = (
        ["hole_id", "edge", "position_index", "type"]
        + list(COMPOSITE_FIELD_ORDER)
        + ["combined_score", "is_outlier", "threshold_used", "low_confidence"]
    )
    with open(table_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in table_rows:
            writer.writerow(row)

    manifest.add_image_entry(path="results/annotated_overview.png", stage="final_output")
    manifest.add_stage_entry(
        step_id=23,
        phase=4,
        stage_name="final_output_generation",
        output_path="results/",
        status="complete"
    )
    manifest.set_status("complete")

    return {
        "annotated_overview": "results/annotated_overview.png",
        "results_table": "results/results_table.csv"
    }
