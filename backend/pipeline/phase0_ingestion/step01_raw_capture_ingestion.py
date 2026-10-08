"""Step 1: Raw Capture Ingestion.

File: backend/pipeline/phase0_ingestion/step01_raw_capture_ingestion.py
Decodes camera RAW frames in linear space, collapses them to luminance arrays,
validates session log and camera settings consistency, and attaches torch metadata.
"""

import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, Optional

import numpy as np

try:
    import rawpy
except ImportError:
    rawpy = None

from backend.config.capture_schema import CAPTURE_SCHEMA, validate_captured_tags
from backend.config.pipeline_constants import CAMERA_MATCH_KEYS
from backend.session.manifest import ManifestManager
from backend.session.session_manager import SessionManager

logger = logging.getLogger(__name__)


class RawFrameRecord:
    """Represents a decoded linear brightness frame with its metadata."""

    def __init__(
        self,
        tag: str,
        brightness_array: np.ndarray,
        source_filename: str,
        torch_meta: Optional[Dict[str, Any]] = None
    ) -> None:
        self.tag = tag
        self.brightness_array = brightness_array.astype(np.float32)
        self.source_filename = source_filename
        self.torch_meta = torch_meta

    def to_dict(self) -> Dict[str, Any]:
        """Return serializable summary of frame record (without full pixel matrix)."""
        return {
            "tag": self.tag,
            "source_filename": self.source_filename,
            "shape": list(self.brightness_array.shape),
            "mean_brightness": float(np.mean(self.brightness_array)),
            "torch_meta": self.torch_meta
        }


def decode_raw_to_luminance(file_path: Path | str) -> np.ndarray:
    """Decode a RAW image file to linear luminance float32 plane [0.0, 1.0].
    
    Formula: Y = 0.2126 * R + 0.7152 * G + 0.0722 * B
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Source file not found: {path}")

    raw_extensions = {".raf", ".cr2", ".cr3", ".nef", ".arw", ".dng", ".orf", ".rw2"}
    if rawpy is not None and path.suffix.lower() in raw_extensions:
        with rawpy.imread(str(path)) as raw:
            # Linear demosaic: gamma=(1, 1), no auto brightness adjustment
            rgb = raw.postprocess(
                gamma=(1, 1),
                no_auto_bright=True,
                use_camera_wb=True,
                output_bps=16
            ).astype(np.float32) / 65535.0
    else:
        # Fallback for standard image formats or testing arrays
        import cv2
        img = cv2.imread(str(path), cv2.IMREAD_UNCHANGED)
        if img is None:
            raise ValueError(f"Unable to read image at {path}")
        if img.ndim == 2:
            max_val = 65535.0 if img.dtype == np.uint16 else 255.0
            return (img.astype(np.float32) / max_val)
        rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB).astype(np.float32)
        max_val = 65535.0 if img.dtype == np.uint16 else 255.0
        rgb /= max_val

    luminance = (0.2126 * rgb[:, :, 0] + 0.7152 * rgb[:, :, 1] + 0.0722 * rgb[:, :, 2]).astype(np.float32)
    return luminance


def match_filename_to_tag(filename: str) -> Optional[str]:
    """Match filename to expected CAPTURE_SCHEMA tag based on naming convention."""
    stem = Path(filename).stem.lower()
    for tag in CAPTURE_SCHEMA.keys():
        if stem == tag or stem.startswith(tag + "_") or stem.startswith(tag + "-") or stem.startswith(tag + "."):
            return tag
    return None


def run_step01(
    session_id: str,
    session_manager: Optional[SessionManager] = None
) -> Dict[str, RawFrameRecord]:
    """Execute Step 1: Raw Capture Ingestion."""
    if session_manager is None:
        session_manager = SessionManager()

    session_dir = session_manager.get_session_dir(session_id)
    manifest = session_manager.get_manifest_manager(session_id)
    raw_dir = session_dir / "raw"

    if not raw_dir.exists():
        raise FileNotFoundError(f"Raw capture directory does not exist: {raw_dir}")

    session_log = session_manager.load_session_log(session_id)
    if not session_log:
        raise ValueError(f"Missing session_log.json for session {session_id}")

    torches = session_log.get("torches", [])
    if len(torches) != 4:
        raise ValueError(f"session_log.json must contain exactly 4 torch records, found {len(torches)}")

    camera_settings = session_log.get("camera_settings", {})
    for key in CAMERA_MATCH_KEYS:
        if key not in camera_settings:
            logger.warning(f"Camera setting '{key}' not specified in session_log.json")

    torch_meta_map: Dict[str, Dict[str, Any]] = {
        t.get("torch_id", f"torch_{i+1}"): t
        for i, t in enumerate(torches)
    }

    tagged_files: Dict[str, Path] = {}
    tagged_counts: Dict[str, int] = {}

    for entry in raw_dir.iterdir():
        if entry.is_file():
            tag = match_filename_to_tag(entry.name)
            if tag:
                tagged_files[tag] = entry
                tagged_counts[tag] = tagged_counts.get(tag, 0) + 1

    validation_res = validate_captured_tags(tagged_counts)
    if not validation_res["ready"]:
        failed_tags = [
            t for t, info in validation_res["tag_status"].items()
            if "Fail" in info["status"]
        ]
        raise ValueError(
            f"Pre-flight schema validation failed for session {session_id}. "
            f"Failed required tags: {failed_tags}"
        )

    records: Dict[str, RawFrameRecord] = {}
    for tag, file_path in tagged_files.items():
        brightness_plane = decode_raw_to_luminance(file_path)
        meta = torch_meta_map.get(tag) if tag.startswith("torch_") else None
        record = RawFrameRecord(
            tag=tag,
            brightness_array=brightness_plane,
            source_filename=file_path.name,
            torch_meta=meta
        )
        records[tag] = record

    manifest.set_status("in_progress")
    manifest.add_stage_entry(
        step_id=1,
        phase=0,
        stage_name="raw_capture_ingestion",
        output_path="raw/",
        status="complete"
    )

    return records
