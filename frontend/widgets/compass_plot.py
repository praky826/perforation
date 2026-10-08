"""Shadow-vector compass display for Phase 14."""

from __future__ import annotations

from typing import Any, Iterable

from PySide6.QtWidgets import QListWidget, QListWidgetItem


class CompassPlot(QListWidget):
    """Display edge shadow direction and strength values from the backend."""

    def update_vectors(self, vectors: Iterable[dict[str, Any]]) -> None:
        """Render shadow-vector records without performing numerical processing."""
        self.clear()
        for record in vectors:
            shadow = record.get("shadow", {}) if isinstance(record, dict) else {}
            direction = shadow.get("direction_deg", "n/a")
            strength = shadow.get("strength", "n/a")
            item = QListWidgetItem(f"{record.get('hole_id', 'unknown')}: direction {direction}, strength {strength}")
            item.setData(256, record)
            self.addItem(item)
