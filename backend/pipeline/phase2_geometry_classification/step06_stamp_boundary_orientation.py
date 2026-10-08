"""Step 6: Stamp Boundary Detection & Orientation Normalization.

File: backend/pipeline/phase2_geometry_classification/step06_stamp_boundary_orientation.py
Separates stamp from dark backdrop in diffuse frame, traces outer contour,
determines rotation angle, and rotates all frames so edges are axis-aligned.
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


class StampFrame:
    """Represents the coordinate frame of the orientation-normalized stamp."""

    def __init__(
        self,
        boundary_polygon: List[List[float]],
        rotation_deg: float,
        stamp_bbox: List[float]
    ) -> None:
        self.boundary_polygon = [[float(pt[0]), float(pt[1])] for pt in boundary_polygon]
        self.rotation_deg = float(rotation_deg)
        self.stamp_bbox = [float(v) for v in stamp_bbox]  # [x, y, w, h]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "boundary_polygon": self.boundary_polygon,
            "rotation_deg": self.rotation_deg,
            "stamp_bbox": self.stamp_bbox
        }


def detect_stamp_orientation(
    diffuse_image: np.ndarray
) -> Tuple[float, List[List[float]], List[float]]:
    """Detect stamp outer boundary and compute rotation angle to square it to axes.
    
    Returns (rotation_deg, boundary_polygon, stamp_bbox).
    """
    img_u8 = (np.clip(diffuse_image, 0.0, 1.0) * 255.0).astype(np.uint8)
    h, w = img_u8.shape

    # Separate stamp from dark backdrop using Otsu threshold
    blur = cv2.GaussianBlur(img_u8, (5, 5), 0)
    _, thresh = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    # Find external contours
    cnts, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not cnts:
        # Fallback to whole frame
        return 0.0, [[0.0, 0.0], [w, 0.0], [w, h], [0.0, h]], [0.0, 0.0, float(w), float(h)]

    largest_cnt = max(cnts, key=cv2.contourArea)

    # Fit minimum area rectangle
    rect = cv2.minAreaRect(largest_cnt)
    (cx, cy), (rw, rh), angle = rect

    # OpenCV minAreaRect angle normalization:
    # We want the angle relative to horizontal / vertical axes
    if rw < rh:
        angle = angle + 90.0
    if angle > 45.0:
        angle = angle - 90.0
    elif angle < -45.0:
        angle = angle + 90.0

    # Approx polygon
    poly = largest_cnt.reshape(-1, 2).tolist()
    bbox = [float(cx - rw / 2.0), float(cy - rh / 2.0), float(rw), float(rh)]

    return float(angle), poly, bbox


def rotate_image_plane(image: np.ndarray, angle_deg: float) -> np.ndarray:
    """Rotate image about center by angle_deg using affine warp."""
    if abs(angle_deg) < 1e-3:
        return image.copy()

    h, w = image.shape
    center = (w / 2.0, h / 2.0)
    rot_mat = cv2.getRotationMatrix2D(center, angle_deg, 1.0)
    rotated = cv2.warpAffine(
        image, rot_mat, (w, h), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE
    )
    return rotated.astype(np.float32)


def run_step06(
    session_id: str,
    frames: Dict[str, RawFrameRecord],
    session_manager: Optional[SessionManager] = None
) -> Tuple[Dict[str, RawFrameRecord], StampFrame]:
    """Execute Step 6: Stamp Boundary Detection & Orientation Normalization."""
    if session_manager is None:
        session_manager = SessionManager()

    session_dir = session_manager.get_session_dir(session_id)
    manifest = session_manager.get_manifest_manager(session_id)
    stages_dir = session_dir / "stages"
    stages_dir.mkdir(parents=True, exist_ok=True)

    if "diffuse" not in frames:
        raise KeyError("Missing required 'diffuse' frame for Step 6")

    diffuse_frame = frames["diffuse"]
    angle_deg, raw_poly, raw_bbox = detect_stamp_orientation(diffuse_frame.brightness_array)

    # Rotate all frames by -angle_deg so stamp edges become axis-aligned
    normalized_frames: Dict[str, RawFrameRecord] = {}
    for tag, frame in frames.items():
        rot_array = rotate_image_plane(frame.brightness_array, -angle_deg)
        normalized_frames[tag] = RawFrameRecord(
            tag=tag,
            brightness_array=rot_array,
            source_filename=frame.source_filename,
            torch_meta=frame.torch_meta
        )

    # Re-derive axis-aligned boundary on rotated diffuse frame
    norm_diffuse = normalized_frames["diffuse"].brightness_array
    _, final_poly, final_bbox = detect_stamp_orientation(norm_diffuse)

    stamp_frame = StampFrame(
        boundary_polygon=final_poly,
        rotation_deg=angle_deg,
        stamp_bbox=final_bbox
    )

    # Persist StampFrame
    out_path = stages_dir / "stamp_frame.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(stamp_frame.to_dict(), f, indent=2)

    manifest.add_stage_entry(
        step_id=6,
        phase=2,
        stage_name="stamp_boundary_orientation",
        output_path="stages/stamp_frame.json",
        status="complete"
    )

    return normalized_frames, stamp_frame
