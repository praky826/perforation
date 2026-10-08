"""Step 20: Robust Statistics & Combined Deviation Score.

File: backend/pipeline/phase4_statistics_output/step20_robust_stats_deviation_score.py
For each composite field, computes the median and MAD across a hole's comparison
group (never itself), converts the hole's own value to a robust z-score, and
combines them into one deviation score via summed-z (L2) or Mahalanobis distance,
per COMBINATION_METHOD.
"""

import json
import logging
import math
import warnings
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
from scipy.stats import median_abs_deviation

from backend.config.pipeline_constants import COMBINATION_METHOD, MAD_SCALE_CONSTANT
from backend.pipeline.phase2_geometry_classification.step07_perforation_candidate_detection import HoleRecord
from backend.session.session_manager import SessionManager

logger = logging.getLogger(__name__)

_EPS = 1e-9


def robust_z_scores(value_vec: np.ndarray, group_matrix: np.ndarray):
    """Per-field robust z, plus group median and MAD vectors.

    group_matrix: shape (n_group, n_fields). NaN-safe (teeth roundness).
    """
    n_fields = value_vec.shape[0]
    # An all-NaN field (e.g. roundness across a group of teeth) is expected; the
    # resulting NaN median/MAD is handled below as z=0, so silence those warnings.
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        median = np.nanmedian(group_matrix, axis=0)
        mad = median_abs_deviation(group_matrix, axis=0, nan_policy="omit", scale=1.0)

    z = np.zeros(n_fields, dtype=np.float64)
    for i in range(n_fields):
        v = value_vec[i]
        m = median[i]
        d = mad[i]
        if not np.isfinite(v) or not np.isfinite(m) or not np.isfinite(d) or d < _EPS:
            z[i] = 0.0
        else:
            z[i] = MAD_SCALE_CONSTANT * (v - m) / d
    return z, median, mad


def _mahalanobis_distance(value_vec: np.ndarray, group_matrix: np.ndarray) -> float:
    """Robust Mahalanobis distance using scikit-learn's MinCovDet (lazy import)."""
    from sklearn.covariance import MinCovDet

    clean = np.nan_to_num(group_matrix, nan=0.0)
    val = np.nan_to_num(value_vec, nan=0.0)
    mcd = MinCovDet().fit(clean)
    dist_sq = float(mcd.mahalanobis(val.reshape(1, -1))[0])
    return math.sqrt(max(0.0, dist_sq))


def run_step20(
    session_id: str,
    holes: List[HoleRecord],
    composites: Dict[str, Dict[str, Any]],
    reference_groups: Dict[str, Dict[str, Any]],
    session_manager: Optional[SessionManager] = None
) -> Dict[str, Dict[str, Any]]:
    """Execute Step 20: Robust Statistics & Combined Deviation Score."""
    if session_manager is None:
        session_manager = SessionManager()

    session_dir = session_manager.get_session_dir(session_id)
    manifest = session_manager.get_manifest_manager(session_id)
    holes_dir = session_dir / "holes"

    scores: Dict[str, Dict[str, Any]] = {}

    for h in holes:
        comp = composites.get(h.hole_id, {})
        vector = np.asarray(comp.get("vector", []), dtype=np.float64)
        group_ids = reference_groups.get(h.hole_id, {}).get("comparison_group_ids", [])
        group_vectors = [
            composites[gid]["vector"] for gid in group_ids
            if gid in composites and composites[gid].get("vector")
        ]

        if vector.size == 0 or len(group_vectors) == 0:
            per_field_z = [0.0] * int(vector.size)
            combined = 0.0
            median = [0.0] * int(vector.size)
            mad = [0.0] * int(vector.size)
        else:
            group_matrix = np.asarray(group_vectors, dtype=np.float64)
            z, median_arr, mad_arr = robust_z_scores(vector, group_matrix)
            per_field_z = [float(x) for x in z]
            median = [float(x) for x in median_arr]
            mad = [float(x) for x in mad_arr]

            if COMBINATION_METHOD == "mahalanobis" and group_matrix.shape[0] > group_matrix.shape[1]:
                try:
                    combined = _mahalanobis_distance(vector, group_matrix)
                except Exception as exc:
                    logger.warning("Mahalanobis failed for %s (%s); falling back to summed_z", h.hole_id, exc)
                    combined = float(math.sqrt(np.sum(z ** 2)))
            else:
                combined = float(math.sqrt(np.sum(z ** 2)))

        score = {
            "per_field_z": per_field_z,
            "combined_score": float(combined),
            "method": COMBINATION_METHOD,
            "group_median": median,
            "group_mad": mad
        }
        scores[h.hole_id] = score

        h_dir = holes_dir / h.hole_id
        h_dir.mkdir(parents=True, exist_ok=True)
        with open(h_dir / "score.json", "w", encoding="utf-8") as f:
            json.dump(score, f, indent=2)

    manifest.add_stage_entry(
        step_id=20,
        phase=4,
        stage_name="robust_stats_deviation_score",
        output_path="holes/",
        status="complete"
    )

    return scores
