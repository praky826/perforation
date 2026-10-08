"""Step 2: Lens Distortion Correction & Pixel-to-Physical-Unit Calibration.

File: backend/pipeline/phase1_calibration_registration/step02_lens_and_unit_calibration.py
Solves for radial lens distortion coefficients (k1, k2, k3), undistorts all frames,
and derives the session's physical scale factor (microns_per_pixel).
"""

import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np

from backend.pipeline.phase0_ingestion.step01_raw_capture_ingestion import RawFrameRecord
from backend.session.manifest import ManifestManager
from backend.session.session_manager import SessionManager

logger = logging.getLogger(__name__)


class CalibrationRecord:
    """Represents calibration results including lens distortion and physical scale."""

    def __init__(
        self,
        distortion_coeffs: List[float],
        microns_per_pixel: float,
        calibration_source_tag: str = "calibration"
    ) -> None:
        self.distortion_coeffs = [float(k) for k in distortion_coeffs]
        self.microns_per_pixel = float(microns_per_pixel)
        self.calibration_source_tag = calibration_source_tag

    def to_dict(self) -> Dict[str, Any]:
        return {
            "distortion_coeffs": self.distortion_coeffs,
            "microns_per_pixel": self.microns_per_pixel,
            "calibration_source_tag": self.calibration_source_tag
        }


def detect_calibration_scale(
    calib_image: np.ndarray,
    known_pattern_spacing_um: float = 1000.0,
    pattern_size: Tuple[int, int] = (7, 7)
) -> Tuple[List[float], float]:
    """Detect calibration pattern, solve distortion coefficients, and compute microns_per_pixel.
    
    Tries circles grid first, then chessboard corners. If no pattern is detected
    (e.g., standard ruled target or flat target), returns zero distortion and estimated scale.
    """
    img_uint8 = (np.clip(calib_image, 0.0, 1.0) * 255.0).astype(np.uint8)
    h, w = img_uint8.shape

    # Try circles grid
    found, corners = cv2.findCirclesGrid(
        img_uint8, pattern_size, flags=cv2.CALIB_CB_SYMMETRIC_GRID
    )
    if not found:
        # Try chessboard
        found, corners = cv2.findChessboardCorners(img_uint8, pattern_size)

    if found and corners is not None:
        # Construct object points in microns
        objp = np.zeros((pattern_size[0] * pattern_size[1], 3), np.float32)
        objp[:, :2] = np.mgrid[0:pattern_size[0], 0:pattern_size[1]].T.reshape(-1, 2) * known_pattern_spacing_um

        ret, mtx, dist, rvecs, tvecs = cv2.calibrateCamera(
            [objp], [corners], (w, h), None, None
        )
        dist_coeffs = dist.ravel().tolist()[:3]

        # Calculate corrected pixel spacing between adjacent points
        diffs = np.linalg.norm(corners[1:] - corners[:-1], axis=2).ravel()
        median_px = float(np.median(diffs))
        microns_per_pixel = known_pattern_spacing_um / median_px if median_px > 0 else 10.0
        return dist_coeffs, microns_per_pixel

    # Default fallback: minimal distortion, nominal scale
    logger.info("No optical pattern recognized; using identity distortion model.")
    dist_coeffs = [0.0, 0.0, 0.0]
    microns_per_pixel = 10.0  # Nominal default (e.g. 10 microns per pixel for high-res macro)
    return dist_coeffs, microns_per_pixel


def undistort_frame(image: np.ndarray, dist_coeffs: List[float]) -> np.ndarray:
    """Apply radial lens undistortion to a 2D float32 image."""
    k = np.array(dist_coeffs, dtype=np.float32)
    if np.all(k == 0.0):
        return image.copy()

    h, w = image.shape
    # Approximate camera matrix with center principal point
    camera_matrix = np.array([
        [w, 0, w / 2.0],
        [0, w, h / 2.0],
        [0, 0, 1.0]
    ], dtype=np.float32)

    dist = np.array([k[0], k[1], 0.0, 0.0, k[2] if len(k) > 2 else 0.0], dtype=np.float32)
    undistorted = cv2.undistort(image, camera_matrix, dist)
    return undistorted.astype(np.float32)


def run_step02(
    session_id: str,
    frames: Dict[str, RawFrameRecord],
    session_manager: Optional[SessionManager] = None,
    known_pattern_spacing_um: float = 1000.0
) -> Tuple[Dict[str, RawFrameRecord], CalibrationRecord]:
    """Execute Step 2: Lens Distortion Correction & Physical Unit Calibration."""
    if session_manager is None:
        session_manager = SessionManager()

    session_dir = session_manager.get_session_dir(session_id)
    manifest = session_manager.get_manifest_manager(session_id)
    stages_dir = session_dir / "stages"
    stages_dir.mkdir(parents=True, exist_ok=True)

    if "calibration" not in frames:
        raise KeyError("Missing required 'calibration' frame from Step 1 output")

    calib_frame = frames["calibration"]
    dist_coeffs, microns_per_px = detect_calibration_scale(
        calib_frame.brightness_array,
        known_pattern_spacing_um=known_pattern_spacing_um
    )

    record = CalibrationRecord(
        distortion_coeffs=dist_coeffs,
        microns_per_pixel=microns_per_px,
        calibration_source_tag="calibration"
    )

    # Persist calibration record
    calib_json_path = stages_dir / "calibration.json"
    with open(calib_json_path, "w", encoding="utf-8") as f:
        json.dump(record.to_dict(), f, indent=2)

    # Undistort all frames
    corrected_frames: Dict[str, RawFrameRecord] = {}
    for tag, frame in frames.items():
        corrected_array = undistort_frame(frame.brightness_array, dist_coeffs)
        corrected_frames[tag] = RawFrameRecord(
            tag=tag,
            brightness_array=corrected_array,
            source_filename=frame.source_filename,
            torch_meta=frame.torch_meta
        )

    manifest.add_stage_entry(
        step_id=2,
        phase=1,
        stage_name="lens_and_unit_calibration",
        output_path="stages/calibration.json",
        status="complete"
    )

    return corrected_frames, record
