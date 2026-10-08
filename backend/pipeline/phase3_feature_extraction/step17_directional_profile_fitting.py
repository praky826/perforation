"""Step 17: Directional Profile Fitting (Feature 3 output - Shadow).

File: backend/pipeline/phase3_feature_extraction/step17_directional_profile_fitting.py
Per boundary point, fits brightness across the known torch azimuths to a single
cosine I(phi) = A + B*cos(phi - psi) via linear least squares, then combines all
points by circular vector averaging into one hole-level shadow direction and
strength (ShadowDescriptor).
"""

import json
import logging
import math
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np

from backend.pipeline.phase2_geometry_classification.step07_perforation_candidate_detection import HoleRecord
from backend.session.session_manager import SessionManager

logger = logging.getLogger(__name__)


def _merge_descriptor(descriptors_path: Path, key: str, payload: Dict[str, Any]) -> None:
    """Read-modify-write a single key into the per-hole descriptors.json (never wholesale)."""
    data: Dict[str, Any] = {}
    if descriptors_path.exists():
        try:
            with open(descriptors_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError):
            data = {}
    data[key] = payload
    with open(descriptors_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def fit_point_cosine(phis_rad: np.ndarray, brightness: np.ndarray):
    """Solve I = A + u*cos(phi) + v*sin(phi); return (u, v, B) for one boundary point."""
    design = np.column_stack([np.ones_like(phis_rad), np.cos(phis_rad), np.sin(phis_rad)])
    sol, *_ = np.linalg.lstsq(design, brightness, rcond=None)
    _a, u, v = float(sol[0]), float(sol[1]), float(sol[2])
    b = math.hypot(u, v)
    return u, v, b


def run_step17(
    session_id: str,
    holes: List[HoleRecord],
    angular_tables: Dict[str, Dict[str, Any]],
    illumination_geometry: List[Dict[str, Any]],
    session_manager: Optional[SessionManager] = None
) -> Dict[str, Dict[str, Any]]:
    """Execute Step 17: Directional Profile Fitting."""
    if session_manager is None:
        session_manager = SessionManager()

    session_dir = session_manager.get_session_dir(session_id)
    manifest = session_manager.get_manifest_manager(session_id)
    holes_dir = session_dir / "holes"

    # Map torch tag -> azimuth (degrees) from IlluminationGeometry.
    azimuth_by_tag: Dict[str, float] = {}
    for entry in illumination_geometry:
        idx = entry.get("torch_index")
        if idx is not None:
            azimuth_by_tag[f"torch_{idx}"] = float(entry.get("azimuth_deg", 0.0))

    shadow_descriptors: Dict[str, Dict[str, Any]] = {}

    for h in holes:
        table = angular_tables.get(h.hole_id, {})
        torch_order = table.get("torch_order", [])
        rows = table.get("rows", [])
        phis = np.radians([azimuth_by_tag.get(t, 0.0) for t in torch_order])

        sum_u, sum_v = 0.0, 0.0
        b_values: List[float] = []
        for row in rows:
            brightness = np.asarray(row.get("brightness", []), dtype=np.float64)
            if brightness.size < 3 or brightness.size != phis.size:
                continue
            u, v, b = fit_point_cosine(phis, brightness)
            sum_u += u
            sum_v += v
            b_values.append(b)

        strength = math.hypot(sum_u, sum_v)
        direction_deg = math.degrees(math.atan2(sum_v, sum_u)) % 360.0
        if b_values:
            conf = {"mean": float(np.mean(b_values)), "min": float(np.min(b_values)), "max": float(np.max(b_values))}
        else:
            conf = {"mean": 0.0, "min": 0.0, "max": 0.0}

        descriptor = {
            "strength": float(strength),
            "direction_deg": float(direction_deg),
            "per_point_confidence_summary": conf
        }
        shadow_descriptors[h.hole_id] = descriptor

        h_dir = holes_dir / h.hole_id
        h_dir.mkdir(parents=True, exist_ok=True)
        _merge_descriptor(h_dir / "descriptors.json", "shadow", descriptor)

    manifest.add_stage_entry(
        step_id=17,
        phase=3,
        stage_name="directional_profile_fitting",
        output_path="holes/",
        status="complete"
    )

    return shadow_descriptors
