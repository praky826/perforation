"""Step 22: Spatial Clustering & Candidate Region Localization.

File: backend/pipeline/phase4_statistics_output/step22_spatial_clustering.py
Within each edge's ordered hole sequence, finds runs of consecutive flagged
holes (optionally bridging a single unflagged gap) and reports each as one
candidate suspect region, converting the run's position range into physical
coordinates for drawing.
"""

import json
import logging
from typing import Any, Dict, List, Optional

from backend.config.pipeline_constants import REGION_MERGE_ENABLED, REGION_MERGE_MAX_GAP
from backend.pipeline.phase2_geometry_classification.step06_stamp_boundary_orientation import StampFrame
from backend.pipeline.phase2_geometry_classification.step07_perforation_candidate_detection import HoleRecord
from backend.session.session_manager import SessionManager

logger = logging.getLogger(__name__)


def _find_runs(flagged_indices: List[int], max_gap: int, merge: bool) -> List[List[int]]:
    """Group ordered-position indices into runs, optionally bridging small gaps.

    Returns a list of [start_idx, end_idx] inclusive index ranges into the ordered list.
    """
    if not flagged_indices:
        return []
    flagged_indices = sorted(flagged_indices)
    runs: List[List[int]] = [[flagged_indices[0], flagged_indices[0]]]
    for idx in flagged_indices[1:]:
        gap = idx - runs[-1][1] - 1  # count of unflagged holes between
        if gap == 0 or (merge and gap <= max_gap):
            runs[-1][1] = idx
        else:
            runs.append([idx, idx])
    return runs


def _region_polygon(members: List[HoleRecord]) -> List[List[float]]:
    """Axis-aligned bounding polygon of member hole centroids (normalized coords)."""
    xs = [h.centroid_px[0] for h in members]
    ys = [h.centroid_px[1] for h in members]
    x0, x1 = min(xs), max(xs)
    y0, y1 = min(ys), max(ys)
    return [[x0, y0], [x1, y0], [x1, y1], [x0, y1]]


def build_candidate_regions(
    holes: List[HoleRecord],
    outlier_flags: Dict[str, Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """Build the CandidateRegion list from per-hole outlier flags."""
    by_edge: Dict[str, List[HoleRecord]] = {}
    for h in holes:
        if h.edge is None or h.position_index is None:
            continue
        by_edge.setdefault(h.edge, []).append(h)

    regions: List[Dict[str, Any]] = []
    for edge in ("top", "bottom", "left", "right"):
        ordered = sorted(by_edge.get(edge, []), key=lambda h: h.position_index)
        if not ordered:
            continue
        flagged_idx = [
            i for i, h in enumerate(ordered)
            if outlier_flags.get(h.hole_id, {}).get("is_outlier", False)
        ]
        runs = _find_runs(flagged_idx, REGION_MERGE_MAX_GAP, REGION_MERGE_ENABLED)

        for n, (start_i, end_i) in enumerate(runs, 1):
            members = ordered[start_i:end_i + 1]
            regions.append({
                "region_id": f"{edge}_region_{n}",
                "edge": edge,
                "hole_ids": [h.hole_id for h in members],
                "start_position": int(members[0].position_index),
                "end_position": int(members[-1].position_index),
                "region_coords_px": _region_polygon(members)
            })
    return regions


def run_step22(
    session_id: str,
    holes: List[HoleRecord],
    outlier_flags: Dict[str, Dict[str, Any]],
    stamp_frame: StampFrame,
    session_manager: Optional[SessionManager] = None
) -> List[Dict[str, Any]]:
    """Execute Step 22: Spatial Clustering & Candidate Region Localization."""
    if session_manager is None:
        session_manager = SessionManager()

    session_dir = session_manager.get_session_dir(session_id)
    manifest = session_manager.get_manifest_manager(session_id)
    stages_dir = session_dir / "stages"
    stages_dir.mkdir(parents=True, exist_ok=True)

    regions = build_candidate_regions(holes, outlier_flags)

    with open(stages_dir / "candidate_regions.json", "w", encoding="utf-8") as f:
        json.dump(regions, f, indent=2)

    manifest.add_stage_entry(
        step_id=22,
        phase=4,
        stage_name="spatial_clustering",
        output_path="stages/candidate_regions.json",
        status="complete"
    )

    return regions
