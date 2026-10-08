"""Step 21: Outlier Thresholding.

File: backend/pipeline/phase4_statistics_output/step21_outlier_thresholding.py
Converts each hole's continuous combined_score into a yes/no outlier decision.
For summed_z the cutoff is the fixed OUTLIER_CUTOFF; for mahalanobis it is the
chi-square critical value for the configured significance level and the
composite vector's degrees of freedom. The cutoff used is recorded per hole.
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from scipy.stats import chi2

from backend.config.pipeline_constants import (
    COMPOSITE_FIELD_ORDER,
    MAHALANOBIS_SIGNIFICANCE_LEVEL,
    OUTLIER_CUTOFF,
)
from backend.pipeline.phase2_geometry_classification.step07_perforation_candidate_detection import HoleRecord
from backend.session.session_manager import SessionManager

logger = logging.getLogger(__name__)


def compute_threshold(method: str, dof: int) -> float:
    """Resolve the cutoff for the active combination method."""
    if method == "mahalanobis":
        return float(chi2.ppf(1.0 - MAHALANOBIS_SIGNIFICANCE_LEVEL, df=max(1, dof)) ** 0.5)
    return float(OUTLIER_CUTOFF)


def run_step21(
    session_id: str,
    holes: List[HoleRecord],
    deviation_scores: Dict[str, Dict[str, Any]],
    session_manager: Optional[SessionManager] = None
) -> Dict[str, Dict[str, Any]]:
    """Execute Step 21: Outlier Thresholding."""
    if session_manager is None:
        session_manager = SessionManager()

    session_dir = session_manager.get_session_dir(session_id)
    manifest = session_manager.get_manifest_manager(session_id)
    holes_dir = session_dir / "holes"

    dof = len(COMPOSITE_FIELD_ORDER)
    flags: Dict[str, Dict[str, Any]] = {}

    for h in holes:
        score = deviation_scores.get(h.hole_id, {})
        method = score.get("method", "summed_z")
        combined = float(score.get("combined_score", 0.0))
        threshold = compute_threshold(method, dof)
        is_outlier = combined > threshold

        outlier = {"is_outlier": bool(is_outlier), "threshold_used": threshold}
        flags[h.hole_id] = outlier

        # Read-modify-write score.json so the "outlier" field is merged, not overwritten.
        score_path = holes_dir / h.hole_id / "score.json"
        data: Dict[str, Any] = {}
        if score_path.exists():
            try:
                with open(score_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except (json.JSONDecodeError, OSError):
                data = dict(score)
        data["outlier"] = outlier
        score_path.parent.mkdir(parents=True, exist_ok=True)
        with open(score_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    manifest.add_stage_entry(
        step_id=21,
        phase=4,
        stage_name="outlier_thresholding",
        output_path="holes/",
        status="complete"
    )

    return flags
