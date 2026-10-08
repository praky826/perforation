"""Capture checklist display for Phase 11."""

from __future__ import annotations

from typing import Any, Dict

from PySide6.QtWidgets import QFormLayout, QLabel, QWidget


class ChecklistWidget(QWidget):
    """Display capture-tag validation results returned by the backend."""

    def __init__(self) -> None:
        super().__init__()
        self._rows: Dict[str, QLabel] = {}
        layout = QFormLayout(self)
        for tag in ("diffuse", "torch_1", "torch_2", "torch_3", "torch_4", "backlit", "calibration"):
            status = QLabel("Not checked")
            self._rows[tag] = status
            layout.addRow(tag.replace("_", " ").title(), status)

    def update_result(self, result: Dict[str, Any]) -> None:
        """Render a validate_upload payload or a safe-call result payload."""
        payload = result.get("result", result) if isinstance(result, dict) else {}
        statuses = payload.get("tag_status", {}) if isinstance(payload, dict) else {}
        for tag, label in self._rows.items():
            status = statuses.get(tag, {}).get("status", "Not checked")
            label.setText(str(status))
