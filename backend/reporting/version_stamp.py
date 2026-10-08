"""Version Stamping (Features 20 & 28).

File: backend/reporting/version_stamp.py
Captures the application version, a snapshot of all pipeline constants, and the
installed versions of the confirmed-stack libraries, and writes them once into
manifest.version_metadata at session start so every run is fully auditable.
"""

import logging
import sys
from datetime import datetime, timezone
from importlib import metadata
from typing import Any, Dict, Optional

from backend.config.pipeline_constants import get_pipeline_constants_dict
from backend.session.session_manager import SessionManager

logger = logging.getLogger(__name__)

APP_VERSION = "1.0.0"

# Confirmed technology-stack distributions whose versions are recorded for audit.
_TRACKED_DISTRIBUTIONS = [
    "numpy",
    "scipy",
    "scikit-learn",
    "pandas",
    "opencv-python",
    "scikit-image",
    "rawpy",
    "shapely",
    "PySide6",
    "matplotlib",
    "reportlab",
]


def get_library_versions() -> Dict[str, str]:
    """Return installed versions of the confirmed-stack libraries (best-effort)."""
    versions: Dict[str, str] = {}
    for dist in _TRACKED_DISTRIBUTIONS:
        try:
            versions[dist] = metadata.version(dist)
        except metadata.PackageNotFoundError:
            versions[dist] = "not_installed"
    return versions


def build_version_metadata() -> Dict[str, Any]:
    """Assemble the full version-metadata block."""
    return {
        "app_version": APP_VERSION,
        "python_version": sys.version.split()[0],
        "config_snapshot": get_pipeline_constants_dict(),
        "library_versions": get_library_versions(),
        "captured_at": datetime.now(timezone.utc).isoformat(),
    }


def stamp_session(session_id: str, session_manager: Optional[SessionManager] = None) -> Dict[str, Any]:
    """Write the version-metadata block once into the session manifest and return it."""
    if session_manager is None:
        session_manager = SessionManager()
    manifest = session_manager.get_manifest_manager(session_id)
    block = build_version_metadata()
    manifest.set_version_metadata(block)
    return block
