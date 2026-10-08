"""Step 3: Illumination Geometry Determination.

File: backend/pipeline/phase1_calibration_registration/step03_illumination_geometry.py
Computes final azimuth and elevation angles for the 4 torches via Path A
(arithmetic rig geometry + correction) or Path B (ball-bearing mirror glint reflection).
"""

import json
import logging
import math
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np

from backend.pipeline.phase0_ingestion.step01_raw_capture_ingestion import RawFrameRecord
from backend.session.manifest import ManifestManager
from backend.session.session_manager import SessionManager

logger = logging.getLogger(__name__)


def solve_ball_bearing_reflection(
    diffuse_bb: np.ndarray,
    torch_bb: np.ndarray
) -> Optional[Tuple[float, float]]:
    """Solve 3D light direction via chrome ball bearing reflection geometry (Path B).
    
    Formula: Light Ray L = 2 * (V . N) * N - V
    where V is viewing ray [0, 0, 1] and N is sphere surface normal at glint.
    """
    diffuse_u8 = (np.clip(diffuse_bb, 0.0, 1.0) * 255.0).astype(np.uint8)
    torch_u8 = (np.clip(torch_bb, 0.0, 1.0) * 255.0).astype(np.uint8)

    # Detect circular ball boundary
    circles = cv2.HoughCircles(
        diffuse_u8, cv2.HOUGH_GRADIENT, dp=1.2, minDist=50,
        param1=50, param2=30, minRadius=20, maxRadius=int(min(diffuse_u8.shape) / 2)
    )
    if circles is None:
        # Fallback: thresholding + minEnclosingCircle
        _, thresh = cv2.threshold(diffuse_u8, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        cnts, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not cnts:
            return None
        largest = max(cnts, key=cv2.contourArea)
        (cx, cy), radius = cv2.minEnclosingCircle(largest)
    else:
        c = circles[0][0]
        cx, cy, radius = float(c[0]), float(c[1]), float(c[2])

    if radius <= 0:
        return None

    # Find brightest glint in torch image within the ball circle
    mask = np.zeros_like(torch_u8)
    cv2.circle(mask, (int(cx), int(cy)), int(radius), 255, -1)
    masked_torch = cv2.bitwise_and(torch_u8, torch_u8, mask=mask)
    min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(masked_torch)
    gx, gy = max_loc

    # Compute normalized glint position relative to ball center
    dx = (gx - cx) / radius
    dy = (gy - cy) / radius
    r_sq = dx * dx + dy * dy
    if r_sq > 1.0:
        return None

    dz = math.sqrt(1.0 - r_sq)
    # Surface normal N at glint
    nx, ny, nz = dx, dy, dz

    # Viewing vector V = [0, 0, 1] pointing to camera
    # L = 2 * (V . N) * N - V = 2 * nz * [nx, ny, nz] - [0, 0, 1]
    lx = 2.0 * nz * nx
    ly = 2.0 * nz * ny
    lz = 2.0 * nz * nz - 1.0

    # Convert L direction to azimuth and elevation in degrees
    azimuth = math.degrees(math.atan2(ly, lx)) % 360.0
    norm_xy = math.sqrt(lx * lx + ly * ly)
    elevation = math.degrees(math.atan2(lz, norm_xy))

    return round(azimuth, 2), round(elevation, 2)


def run_step03(
    session_id: str,
    frames: Dict[str, RawFrameRecord],
    session_manager: Optional[SessionManager] = None
) -> List[Dict[str, Any]]:
    """Execute Step 3: Illumination Geometry Determination."""
    if session_manager is None:
        session_manager = SessionManager()

    session_dir = session_manager.get_session_dir(session_id)
    manifest = session_manager.get_manifest_manager(session_id)
    session_log = session_manager.load_session_log(session_id) or {}
    ball_bearing_used = session_log.get("ball_bearing_used", False)

    illumination_geometry: List[Dict[str, Any]] = []

    for i in range(1, 5):
        tag = f"torch_{i}"
        frame = frames.get(tag)
        meta = frame.torch_meta if frame else None

        # Path A calculation
        if meta:
            h = float(meta.get("height_cm", 10.0))
            d = float(meta.get("distance_cm", 10.0))
            corr = float(meta.get("manual_correction_deg", 0.0))
            az = float(meta.get("azimuth_deg", (i - 1) * 90.0))
            elev = SessionManager.compute_elevation(h, d, corr)
        else:
            az = float((i - 1) * 90.0)
            elev = 45.0

        source_path = "calculated"
        final_az = az
        final_elev = elev

        # Path B check
        if ball_bearing_used:
            bb_diff_frame = frames.get("ball_bearing_diffuse")
            bb_torch_frame = frames.get(f"ball_bearing_torch_{i}")
            if bb_diff_frame is not None and bb_torch_frame is not None:
                bb_sol = solve_ball_bearing_reflection(
                    bb_diff_frame.brightness_array,
                    bb_torch_frame.brightness_array
                )
                if bb_sol is not None:
                    final_az, final_elev = bb_sol
                    source_path = "ball_bearing"

        illumination_geometry.append({
            "torch_index": i,
            "azimuth_deg": round(final_az, 2),
            "elevation_deg": round(final_elev, 2),
            "source_path": source_path
        })

    # Persist illumination geometry
    stages_dir = session_dir / "stages"
    stages_dir.mkdir(parents=True, exist_ok=True)
    out_path = stages_dir / "illumination_geometry.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(illumination_geometry, f, indent=2)

    manifest.add_stage_entry(
        step_id=3,
        phase=1,
        stage_name="illumination_geometry",
        output_path="stages/illumination_geometry.json",
        status="complete"
    )

    return illumination_geometry
