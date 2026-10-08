"""IPDS Session Manager.

Manages session filesystem lifecycle under data/sessions/<session_id>/.
Creates directories (raw, stages, holes, results), discovers incomplete
sessions for crash-resume, handles session resets, and persists SessionLog.
"""

import json
import math
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from backend.session.manifest import ManifestManager


class SessionManager:
    """Manages session creation, directory structures, and session log I/O."""

    def __init__(self, sessions_root: Optional[Path | str] = None) -> None:
        if sessions_root is None:
            # Default to <workspace_root>/data/sessions
            self.sessions_root = Path(__file__).resolve().parents[2] / "data" / "sessions"
        else:
            self.sessions_root = Path(sessions_root)
        self.sessions_root.mkdir(parents=True, exist_ok=True)

    def get_session_dir(self, session_id: str) -> Path:
        """Return absolute path to session directory."""
        return self.sessions_root / session_id

    def session_exists(self, session_id: str) -> bool:
        """Check if a session folder exists on disk."""
        return self.get_session_dir(session_id).exists()

    def create_session(self, session_id: str, specimen_id: str = "") -> Dict[str, Any]:
        """Create standard folder layout and initialize manifest.json."""
        sdir = self.get_session_dir(session_id)
        sdir.mkdir(parents=True, exist_ok=True)
        (sdir / "raw").mkdir(exist_ok=True)
        (sdir / "stages").mkdir(exist_ok=True)
        (sdir / "holes").mkdir(exist_ok=True)
        (sdir / "results").mkdir(exist_ok=True)

        manifest = ManifestManager(sdir)
        initial_log = {
            "session_id": session_id,
            "specimen_id": specimen_id,
            "torches": [],
            "camera_settings": {},
            "ball_bearing_used": False,
            "capture_timestamp": datetime.now(timezone.utc).isoformat(),
            "operator_notes": ""
        }
        log_path = sdir / "session_log.json"
        if not log_path.exists():
            with open(log_path, "w", encoding="utf-8") as f:
                json.dump(initial_log, f, indent=2)

        return {
            "session_id": session_id,
            "session_dir": str(sdir),
            "manifest": manifest.load()
        }

    def get_manifest_manager(self, session_id: str) -> ManifestManager:
        """Get the ManifestManager for an existing session."""
        sdir = self.get_session_dir(session_id)
        return ManifestManager(sdir)

    def list_sessions(self) -> List[Dict[str, Any]]:
        """List all sessions on disk and their current manifest status."""
        results = []
        if not self.sessions_root.exists():
            return results

        for child in self.sessions_root.iterdir():
            if child.is_dir():
                manifest_file = child / "manifest.json"
                if manifest_file.exists():
                    try:
                        with open(manifest_file, "r", encoding="utf-8") as f:
                            m = json.load(f)
                        results.append({
                            "session_id": child.name,
                            "status": m.get("status", "unknown"),
                            "created_at": m.get("created_at"),
                            "updated_at": m.get("updated_at"),
                            "holes_total": m.get("holes_total", 0),
                            "holes_processed": m.get("holes_processed", 0)
                        })
                    except Exception:
                        results.append({
                            "session_id": child.name,
                            "status": "corrupt"
                        })
        return results

    def check_incomplete_session(self) -> Optional[Dict[str, Any]]:
        """Scan for a session marked 'in_progress' or 'failed' for crash-resume (Feature 22)."""
        for s in self.list_sessions():
            if s.get("status") in {"in_progress", "failed"}:
                sdir = self.get_session_dir(s["session_id"])
                manifest = ManifestManager(sdir).load()
                return {
                    "session_id": s["session_id"],
                    "status": s["status"],
                    "manifest": manifest,
                    "session_dir": str(sdir)
                }
        return None

    def resume_session(self, session_id: str) -> Dict[str, Any]:
        """Reload session state and return last completed step index."""
        if not self.session_exists(session_id):
            raise FileNotFoundError(f"Session {session_id} not found.")

        manifest = self.get_manifest_manager(session_id).load()
        stages = manifest.get("stages", [])
        completed_steps = [s["step_id"] for s in stages if s.get("status") == "complete"]
        last_step = max(completed_steps) if completed_steps else 0

        return {
            "session_id": session_id,
            "status": manifest.get("status"),
            "last_completed_step": last_step,
            "manifest": manifest
        }

    def reset_session(self, session_id: str) -> bool:
        """Permanently delete session folder on disk (Feature 23).
        
        Requires external confirmation by caller per specification.
        """
        sdir = self.get_session_dir(session_id)
        if sdir.exists():
            shutil.rmtree(sdir)
            return True
        return False

    def save_session_log(self, session_id: str, log_data: Dict[str, Any]) -> bool:
        """Persist structured SessionLog to session_log.json (Feature 2)."""
        sdir = self.get_session_dir(session_id)
        if not sdir.exists():
            raise FileNotFoundError(f"Session {session_id} does not exist.")

        # Ensure elevation is calculated for torches if missing
        torches = log_data.get("torches", [])
        for t in torches:
            if "computed_elevation_deg" not in t:
                h = t.get("height_cm", 0.0)
                d = t.get("distance_cm", 1.0)
                corr = t.get("manual_correction_deg", 0.0)
                t["computed_elevation_deg"] = self.compute_elevation(h, d, corr)

        log_path = sdir / "session_log.json"
        with open(log_path, "w", encoding="utf-8") as f:
            json.dump(log_data, f, indent=2)
        return True

    def load_session_log(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Load session_log.json if present."""
        sdir = self.get_session_dir(session_id)
        log_path = sdir / "session_log.json"
        if not log_path.exists():
            return None
        with open(log_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def set_shadow_bleed_acknowledged(self, session_id: str, value: bool = True) -> bool:
        """Persist the shadow-bleed acknowledgment boolean on the session record (Feature 3)."""
        sdir = self.get_session_dir(session_id)
        sdir.mkdir(parents=True, exist_ok=True)
        log = self.load_session_log(session_id) or {}
        log["shadow_bleed_acknowledged"] = bool(value)
        log_path = sdir / "session_log.json"
        with open(log_path, "w", encoding="utf-8") as f:
            json.dump(log, f, indent=2)
        return True

    @staticmethod
    def compute_elevation(height_cm: float, distance_cm: float, manual_correction_deg: float = 0.0) -> float:
        """Compute elevation angle: arctan(height / distance) in degrees + correction (Feature 2)."""
        if distance_cm <= 0:
            return float(manual_correction_deg)
        elev = math.degrees(math.atan(height_cm / distance_cm)) + manual_correction_deg
        return round(elev, 2)

    def get_tagged_files(self, session_id: str) -> Dict[str, int]:
        """Count tagged files in data/sessions/<session_id>/raw/."""
        sdir = self.get_session_dir(session_id)
        raw_dir = sdir / "raw"
        if not raw_dir.exists():
            return {}

        # Standard filename prefixes / tags mapping
        counts: Dict[str, int] = {}
        for f in raw_dir.iterdir():
            if f.is_file():
                stem = f.stem.lower()
                for tag in [
                    "diffuse", "torch_1", "torch_2", "torch_3", "torch_4",
                    "backlit", "calibration", "ball_bearing_diffuse",
                    "ball_bearing_torch_1", "ball_bearing_torch_2",
                    "ball_bearing_torch_3", "ball_bearing_torch_4"
                ]:
                    if stem == tag or stem.startswith(tag + "_") or stem.startswith(tag + "."):
                        counts[tag] = counts.get(tag, 0) + 1
                        break
        return counts
