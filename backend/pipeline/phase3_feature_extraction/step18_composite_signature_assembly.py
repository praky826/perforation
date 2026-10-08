"""Step 18: Composite Signature Assembly & Normalization.

File: backend/pipeline/phase3_feature_extraction/step18_composite_signature_assembly.py
Concatenates the shape (Step 13), roughness (Step 15), and shadow (Step 17)
descriptors for one hole into a single ordered 14-element vector using the
fixed COMPOSITE_FIELD_ORDER. No rescaling is performed here (deferred to
Step 20 per comparison group). Completes Phase 3 for the hole.
"""

import json
import logging
import math
from pathlib import Path
from typing import Any, Dict, List, Optional

from backend.config.pipeline_constants import COMPOSITE_FIELD_ORDER
from backend.pipeline.phase2_geometry_classification.step07_perforation_candidate_detection import HoleRecord
from backend.session.session_manager import SessionManager

logger = logging.getLogger(__name__)


def _load_descriptors(descriptors_path: Path) -> Dict[str, Any]:
    if not descriptors_path.exists():
        return {}
    try:
        with open(descriptors_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def assemble_vector(descriptors: Dict[str, Any]) -> List[float]:
    """Build the 14-element ordered feature vector from the three descriptor blocks."""
    shape = descriptors.get("shape", {})
    roughness = descriptors.get("roughness", {})
    shadow = descriptors.get("shadow", {})
    fourier = shape.get("fourier_coeffs", [0.0, 0.0, 0.0, 0.0])

    def fourier_at(i: int) -> float:
        return float(fourier[i]) if i < len(fourier) else 0.0

    roundness = shape.get("roundness_ratio", None)
    roundness_val = float(roundness) if roundness is not None else float("nan")

    field_values: Dict[str, float] = {
        "mean_radius_um": float(shape.get("mean_radius_um", 0.0)),
        "radius_std_um": float(shape.get("radius_std_um", 0.0)),
        "fourier_c1": fourier_at(0),
        "fourier_c2": fourier_at(1),
        "fourier_c3": fourier_at(2),
        "fourier_c4": fourier_at(3),
        "roundness_ratio": roundness_val,
        "sobel_mean": float(roughness.get("sobel_mean", 0.0)),
        "sobel_std": float(roughness.get("sobel_std", 0.0)),
        "glcm_contrast": float(roughness.get("glcm_contrast", 0.0)),
        "glcm_homogeneity": float(roughness.get("glcm_homogeneity", 0.0)),
        "residual_wobble": float(roughness.get("residual_wobble", 0.0)),
        "shadow_strength": float(shadow.get("strength", 0.0)),
        "shadow_direction_deg": float(shadow.get("direction_deg", 0.0)),
    }
    return [field_values[name] for name in COMPOSITE_FIELD_ORDER]


def run_step18(
    session_id: str,
    holes: List[HoleRecord],
    session_manager: Optional[SessionManager] = None
) -> Dict[str, Dict[str, Any]]:
    """Execute Step 18: Composite Signature Assembly."""
    if session_manager is None:
        session_manager = SessionManager()

    session_dir = session_manager.get_session_dir(session_id)
    manifest = session_manager.get_manifest_manager(session_id)
    holes_dir = session_dir / "holes"

    composites: Dict[str, Dict[str, Any]] = {}

    for h in holes:
        desc_path = holes_dir / h.hole_id / "descriptors.json"
        descriptors = _load_descriptors(desc_path)
        vector = assemble_vector(descriptors)

        composite = {
            "vector": vector,
            "field_names": list(COMPOSITE_FIELD_ORDER)
        }
        composites[h.hole_id] = composite

        descriptors["composite"] = composite
        with open(desc_path, "w", encoding="utf-8") as f:
            json.dump(descriptors, f, indent=2)

        manifest.increment_holes_processed()

    manifest.add_stage_entry(
        step_id=18,
        phase=3,
        stage_name="composite_signature_assembly",
        output_path="holes/",
        status="complete"
    )

    return composites
