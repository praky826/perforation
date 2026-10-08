"""Step 5: Cross-Pass Image Registration.

File: backend/pipeline/phase1_calibration_registration/step05_cross_pass_registration.py
Aligns all torch frames and the backlit frame to the diffuse overview frame,
using Enhanced Correlation Coefficient (ECC) with ORB+Homography fallback.
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


def align_frame_ecc(
    target: np.ndarray,
    reference: np.ndarray,
    motion_type: int = cv2.MOTION_EUCLIDEAN,
    max_iters: int = 100,
    eps: float = 1e-5
) -> Optional[np.ndarray]:
    """Align target to reference using Enhanced Correlation Coefficient (ECC)."""
    target_f32 = target.astype(np.float32)
    ref_f32 = reference.astype(np.float32)

    warp_matrix = np.eye(2, 3, dtype=np.float32)
    criteria = (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, max_iters, eps)

    try:
        ret, warp_matrix = cv2.findTransformECC(
            ref_f32, target_f32, warp_matrix, motion_type, criteria
        )
        return warp_matrix
    except cv2.error as e:
        logger.debug(f"ECC alignment failed to converge: {e}")
        return None


def align_frame_orb(
    target: np.ndarray,
    reference: np.ndarray,
    max_features: int = 1000
) -> Optional[np.ndarray]:
    """Fallback alignment using ORB keypoint matching and Homography."""
    t_u8 = (np.clip(target, 0.0, 1.0) * 255.0).astype(np.uint8)
    r_u8 = (np.clip(reference, 0.0, 1.0) * 255.0).astype(np.uint8)

    orb = cv2.ORB_create(max_features)
    kp1, des1 = orb.detectAndCompute(t_u8, None)
    kp2, des2 = orb.detectAndCompute(r_u8, None)

    if des1 is None or des2 is None or len(des1) < 10 or len(des2) < 10:
        return None

    matcher = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)
    matches = matcher.match(des1, des2)
    matches = sorted(matches, key=lambda x: x.distance)[:100]

    if len(matches) < 8:
        return None

    pts_target = np.float32([kp1[m.queryIdx].pt for m in matches]).reshape(-1, 1, 2)
    pts_ref = np.float32([kp2[m.trainIdx].pt for m in matches]).reshape(-1, 1, 2)

    homography, inliers = cv2.findHomography(pts_target, pts_ref, cv2.RANSAC, 5.0)
    return homography


def warp_registered_image(
    image: np.ndarray,
    transform: Optional[np.ndarray],
    ref_shape: Tuple[int, int]
) -> np.ndarray:
    """Apply solved transform (2x3 affine or 3x3 homography) to warp image."""
    if transform is None:
        return image.copy()

    h, w = ref_shape
    if transform.shape == (2, 3):
        return cv2.warpAffine(
            image, transform, (w, h), flags=cv2.INTER_LINEAR + cv2.WARP_INVERSE_MAP
        )
    elif transform.shape == (3, 3):
        return cv2.warpPerspective(
            image, transform, (w, h), flags=cv2.INTER_LINEAR
        )
    return image.copy()


def run_step05(
    session_id: str,
    frames: Dict[str, RawFrameRecord],
    session_manager: Optional[SessionManager] = None,
    max_shift_px_warning: float = 5.0
) -> Dict[str, RawFrameRecord]:
    """Execute Step 5: Cross-Pass Image Registration."""
    if session_manager is None:
        session_manager = SessionManager()

    session_dir = session_manager.get_session_dir(session_id)
    manifest = session_manager.get_manifest_manager(session_id)
    stages_dir = session_dir / "stages"
    registered_dir = stages_dir / "registered"
    registered_dir.mkdir(parents=True, exist_ok=True)

    if "diffuse" not in frames:
        raise KeyError("Missing required 'diffuse' reference frame for Step 5 registration")

    ref_frame = frames["diffuse"]
    ref_shape = ref_frame.brightness_array.shape

    registered_frames: Dict[str, RawFrameRecord] = {
        "diffuse": ref_frame
    }

    # Save reference registered image for thumbnail preview
    ref_preview_path = registered_dir / "diffuse_registered.png"
    ref_uint8 = (np.clip(ref_frame.brightness_array, 0.0, 1.0) * 255.0).astype(np.uint8)
    cv2.imwrite(str(ref_preview_path), ref_uint8)
    manifest.add_image_entry(
        path="stages/registered/diffuse_registered.png",
        stage="registration"
    )

    targets = ["torch_1", "torch_2", "torch_3", "torch_4", "backlit"]
    movement_warnings: List[str] = []

    for tag in targets:
        if tag not in frames:
            continue
        tgt_frame = frames[tag]

        # 1. Primary: ECC alignment
        transform = align_frame_ecc(tgt_frame.brightness_array, ref_frame.brightness_array)
        method_used = "ecc"

        # 2. Backup: ORB + Homography
        if transform is None:
            transform = align_frame_orb(tgt_frame.brightness_array, ref_frame.brightness_array)
            method_used = "orb_homography" if transform is not None else "identity"

        # Shift magnitude check
        shift_mag = 0.0
        if transform is not None and transform.shape == (2, 3):
            shift_mag = float(np.linalg.norm(transform[:, 2]))
        elif transform is not None and transform.shape == (3, 3):
            shift_mag = float(np.linalg.norm([transform[0, 2], transform[1, 2]]))

        if shift_mag > max_shift_px_warning:
            warn_msg = f"{tag} showed possible mid-session movement (shift: {shift_mag:.2f}px)"
            logger.warning(warn_msg)
            movement_warnings.append(warn_msg)

        warped = warp_registered_image(tgt_frame.brightness_array, transform, ref_shape)
        reg_record = RawFrameRecord(
            tag=tag,
            brightness_array=warped,
            source_filename=tgt_frame.source_filename,
            torch_meta=tgt_frame.torch_meta
        )
        registered_frames[tag] = reg_record

        # Save registered preview image and add manifest image entry
        out_img_path = registered_dir / f"{tag}_registered.png"
        warped_u8 = (np.clip(warped, 0.0, 1.0) * 255.0).astype(np.uint8)
        cv2.imwrite(str(out_img_path), warped_u8)
        manifest.add_image_entry(
            path=f"stages/registered/{tag}_registered.png",
            stage="registration"
        )

    # Persist registration metadata summary
    reg_summary = {
        "reference_tag": "diffuse",
        "registered_tags": list(registered_frames.keys()),
        "movement_warnings": movement_warnings
    }
    with open(stages_dir / "registration_summary.json", "w", encoding="utf-8") as f:
        json.dump(reg_summary, f, indent=2)

    manifest.add_stage_entry(
        step_id=5,
        phase=1,
        stage_name="cross_pass_registration",
        output_path="stages/registered/",
        status="complete"
    )

    return registered_frames
