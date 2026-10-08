"""Step 11: Subpixel Contour Extraction (Feature 1 - Shape).

File: backend/pipeline/phase3_feature_extraction/step11_subpixel_contour.py
Traces each hole's boundary in its backlit crop at the per-hole midpoint
brightness threshold using marching squares (skimage.measure.find_contours),
producing a smooth ordered polyline whose points sit at fractional pixel
coordinates.
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
from skimage import measure

from backend.pipeline.phase2_geometry_classification.step07_perforation_candidate_detection import HoleRecord
from backend.session.session_manager import SessionManager

logger = logging.getLogger(__name__)


def compute_midpoint_threshold(crop: np.ndarray) -> float:
    """Derive the brightness midpoint between the bright hole plateau and dark paper plateau."""
    finite = crop[np.isfinite(crop)]
    if finite.size == 0:
        return 0.5
    lo = float(np.percentile(finite, 5.0))
    hi = float(np.percentile(finite, 95.0))
    return (lo + hi) / 2.0


def extract_subpixel_outline(backlit_crop: np.ndarray) -> List[List[float]]:
    """Run marching squares at the midpoint threshold and select the best hole contour.

    Returns an ordered list of subpixel [x, y] coordinates (image coordinates).
    """
    threshold = compute_midpoint_threshold(backlit_crop)
    # find_contours returns rows of (row, col) == (y, x) at subpixel precision.
    contours = measure.find_contours(backlit_crop, level=threshold)
    if not contours:
        return []

    # Select the contour enclosing the largest area (discards spurious noise contours).
    def _polygon_area(c: np.ndarray) -> float:
        ys = c[:, 0]
        xs = c[:, 1]
        return abs(float(np.sum(xs * np.roll(ys, -1) - np.roll(xs, -1) * ys))) / 2.0

    best = max(contours, key=_polygon_area)
    # Convert (row, col) -> (x, y)
    outline = [[float(pt[1]), float(pt[0])] for pt in best]
    return outline


def run_step11(
    session_id: str,
    holes: List[HoleRecord],
    crops: Dict[str, Dict[str, np.ndarray]],
    session_manager: Optional[SessionManager] = None
) -> Dict[str, List[List[float]]]:
    """Execute Step 11: Subpixel Contour Extraction.

    crops: mapping hole_id -> {frame_tag: ndarray}. Uses the (fused) backlit crop
    per hole. Returns mapping hole_id -> subpixel outline polyline.
    """
    if session_manager is None:
        session_manager = SessionManager()

    session_dir = session_manager.get_session_dir(session_id)
    manifest = session_manager.get_manifest_manager(session_id)
    holes_dir = session_dir / "holes"

    outlines: Dict[str, List[List[float]]] = {}

    for h in holes:
        hole_crops = crops.get(h.hole_id, {})
        backlit = hole_crops.get("backlit")
        if backlit is None:
            logger.warning("Step 11: hole %s has no backlit crop; skipping outline", h.hole_id)
            outlines[h.hole_id] = []
            continue

        outline = extract_subpixel_outline(backlit)
        outlines[h.hole_id] = outline

        h_dir = holes_dir / h.hole_id
        h_dir.mkdir(parents=True, exist_ok=True)
        out_path = h_dir / "subpixel_outline.json"
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump({"hole_id": h.hole_id, "type": h.type, "outline_px": outline}, f, indent=2)

    manifest.add_stage_entry(
        step_id=11,
        phase=3,
        stage_name="subpixel_contour",
        output_path="holes/",
        status="complete"
    )

    return outlines
