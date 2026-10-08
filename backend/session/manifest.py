"""IPDS Session Manifest Manager.

Single source of truth for session lifecycle, stage completion status,
displayable stage output images, and progress tracking.
Treats manifest.json as an append-mostly log to guarantee crash recovery.
"""

import json
import os
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


class ManifestManager:
    """Manages reading, atomic updating, and diff querying of manifest.json."""

    def __init__(self, session_dir: Path | str) -> None:
        self.session_dir = Path(session_dir)
        self.manifest_path = self.session_dir / "manifest.json"
        self._ensure_manifest()

    def _default_manifest(self) -> Dict[str, Any]:
        """Return the default skeleton for a new session manifest."""
        return {
            "session_id": self.session_dir.name,
            "status": "not_started",
            "stages": [],
            "images": [],
            "holes_total": 0,
            "holes_processed": 0,
            "low_confidence_holes": [],
            "version_metadata": {},
            "mod_token": 0,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat()
        }

    def _ensure_manifest(self) -> None:
        """Ensure manifest.json exists on disk; create default if absent."""
        if not self.manifest_path.exists():
            self.manifest_path.parent.mkdir(parents=True, exist_ok=True)
            self._write_manifest(self._default_manifest())

    def load(self) -> Dict[str, Any]:
        """Read and return the current manifest.json content."""
        if not self.manifest_path.exists():
            return self._default_manifest()
        try:
            with open(self.manifest_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            # Fallback for transient read issues
            return self._default_manifest()

    def _write_manifest(self, data: Dict[str, Any]) -> None:
        """Write manifest atomically via a temporary file."""
        data["updated_at"] = datetime.now(timezone.utc).isoformat()
        tmp_dir = self.manifest_path.parent
        tmp_file = tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=tmp_dir, delete=False
        )
        try:
            json.dump(data, tmp_file, indent=2)
            tmp_file.flush()
            os.fsync(tmp_file.fileno())
            tmp_file.close()
            shutil.move(tmp_file.name, self.manifest_path)
        except Exception:
            if os.path.exists(tmp_file.name):
                os.remove(tmp_file.name)
            raise

    def set_status(self, status: str) -> None:
        """Update session-level status (not_started, in_progress, complete, failed)."""
        valid_statuses = {"not_started", "in_progress", "complete", "failed"}
        if status not in valid_statuses:
            raise ValueError(f"Invalid status: {status}. Must be one of {valid_statuses}")
        data = self.load()
        data["status"] = status
        data["mod_token"] += 1
        self._write_manifest(data)

    def add_stage_entry(
        self,
        step_id: int,
        phase: int,
        stage_name: str,
        output_path: str,
        status: str = "complete"
    ) -> None:
        """Record or update a completed or active pipeline step stage."""
        data = self.load()
        stages: List[Dict[str, Any]] = data.get("stages", [])

        # Check if step_id already recorded, update if so
        updated = False
        now_str = datetime.now(timezone.utc).isoformat()
        for s in stages:
            if s.get("step_id") == step_id:
                s["phase"] = phase
                s["stage_name"] = stage_name
                s["output_path"] = output_path
                s["timestamp"] = now_str
                s["status"] = status
                updated = True
                break

        if not updated:
            stages.append({
                "step_id": step_id,
                "phase": phase,
                "stage_name": stage_name,
                "output_path": output_path,
                "timestamp": now_str,
                "status": status
            })

        data["stages"] = stages
        data["mod_token"] += 1
        self._write_manifest(data)

    def add_image_entry(
        self,
        path: str,
        stage: str,
        hole_id: Optional[str] = None,
        edge: Optional[str] = None,
        flagged: Optional[bool] = None
    ) -> int:
        """Append a displayable image entry to the images list.
        
        Returns the new monotonic image token.
        """
        data = self.load()
        images: List[Dict[str, Any]] = data.get("images", [])
        token = len(images) + 1

        entry = {
            "token": token,
            "path": path,
            "stage": stage,
            "hole_id": hole_id,
            "edge": edge,
            "flagged": flagged,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        images.append(entry)
        data["images"] = images
        data["mod_token"] += 1
        self._write_manifest(data)
        return token

    def get_manifest_diff(self, since_token: int = 0) -> Dict[str, Any]:
        """Return entries added since the specified token for incremental UI refresh."""
        data = self.load()
        all_images: List[Dict[str, Any]] = data.get("images", [])
        new_images = [img for img in all_images if img.get("token", 0) > since_token]
        latest_token = all_images[-1]["token"] if all_images else 0

        return {
            "session_id": data.get("session_id"),
            "status": data.get("status"),
            "latest_token": latest_token,
            "new_images": new_images,
            "holes_total": data.get("holes_total", 0),
            "holes_processed": data.get("holes_processed", 0),
            "stages": data.get("stages", []),
            "mod_token": data.get("mod_token", 0)
        }

    def set_holes_total(self, total: int) -> None:
        """Set the final count of candidate holes (from Step 8)."""
        data = self.load()
        data["holes_total"] = int(total)
        data["mod_token"] += 1
        self._write_manifest(data)

    def increment_holes_processed(self) -> int:
        """Increment running count of processed holes (during Step 18)."""
        data = self.load()
        current = data.get("holes_processed", 0) + 1
        data["holes_processed"] = current
        data["mod_token"] += 1
        self._write_manifest(data)
        return current

    def set_low_confidence_holes(self, hole_ids: List[str]) -> None:
        """Tag holes evaluated under low-confidence fallback (pooled reference)."""
        data = self.load()
        data["low_confidence_holes"] = list(hole_ids)
        data["mod_token"] += 1
        self._write_manifest(data)

    def set_version_metadata(self, metadata: Dict[str, Any]) -> None:
        """Record version stamp and configuration snapshot."""
        data = self.load()
        data["version_metadata"] = metadata
        data["mod_token"] += 1
        self._write_manifest(data)

    def invalidate_from_stage(self, step_id: int) -> None:
        """Invalidate stages and intermediate outputs at or after step_id for Feature 24."""
        data = self.load()
        stages = data.get("stages", [])
        data["stages"] = [s for s in stages if s.get("step_id", 0) < step_id]

        # Reset session status if it was previously complete
        if data.get("status") in {"complete", "failed"}:
            data["status"] = "in_progress"

        # If step_id <= 8, reset hole counts
        if step_id <= 8:
            data["holes_total"] = 0
            data["holes_processed"] = 0
            data["low_confidence_holes"] = []
        elif step_id <= 18:
            data["holes_processed"] = 0

        data["mod_token"] += 1
        self._write_manifest(data)
