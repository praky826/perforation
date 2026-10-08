"""Full Session Export/Archive (Feature 27).

File: backend/session/archive.py
A thin shutil.make_archive wrapper that packages an already-populated session
directory (raw uploads, stage images, manifest, results table, session log)
into one timestamped zip named from the specimen_id, for reproducibility.
No new data is generated here; the folder is only packaged.

Contains zero Qt/PySide6 imports.
"""

import logging
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from backend.session.session_manager import SessionManager

logger = logging.getLogger(__name__)


def _safe_name(text: str) -> str:
    """Reduce an arbitrary specimen_id to a filesystem-safe token."""
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", text).strip("_")
    return cleaned or "specimen"


class SessionArchiver:
    """Packages a completed session directory into a single zip archive."""

    def __init__(self, session_manager: Optional[SessionManager] = None) -> None:
        self.session_manager = session_manager or SessionManager()

    def export_session(self, session_id: str, allow_incomplete: bool = False) -> str:
        """Zip the whole session folder and return the archive path.

        By default the session manifest must be 'complete'; pass
        allow_incomplete=True to export an in-progress session on explicit
        user request (Feature 27's algorithm step 1).
        """
        session_dir = self.session_manager.get_session_dir(session_id)
        if not session_dir.exists():
            raise FileNotFoundError(f"Session directory not found: {session_id}")

        manifest = self.session_manager.get_manifest_manager(session_id)
        status = manifest.load().get("status", "not_started")
        if status != "complete" and not allow_incomplete:
            raise ValueError(
                f"Session '{session_id}' status is '{status}', not 'complete'. "
                "Pass allow_incomplete=True to export anyway."
            )

        log = self.session_manager.load_session_log(session_id) or {}
        specimen_id = _safe_name(str(log.get("specimen_id", session_id)))
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

        # Write the archive into the data/ root so it is not nested inside the
        # directory being archived (which would otherwise recurse).
        data_root = session_dir.parent.parent
        base_name = str(data_root / f"{specimen_id}_{timestamp}")

        archive_path = shutil.make_archive(
            base_name=base_name,
            format="zip",
            root_dir=str(session_dir.parent),
            base_dir=session_dir.name,
        )
        logger.info("Exported session %s to %s", session_id, archive_path)
        return archive_path
