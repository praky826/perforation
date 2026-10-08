"""Hole breakdown and traceability table for Phases 13 and 14."""

from __future__ import annotations

from typing import Any, Mapping

from PySide6.QtWidgets import QTableWidget, QTableWidgetItem


class BreakdownTable(QTableWidget):
    """Show compact hole tooltip data and nested descriptor values."""

    def __init__(self) -> None:
        super().__init__(0, 2)
        self.setHorizontalHeaderLabels(("Field", "Value"))
        self.setAlternatingRowColors(True)

    def update_tooltip(self, payload: Mapping[str, Any]) -> None:
        """Render the compact Feature 11 tooltip payload."""
        rows = (("hole_id", payload.get("hole_id")), ("score", payload.get("score")), ("type", payload.get("type")), ("outlier", payload.get("outlier")), ("summary", payload.get("summary")))
        self._set_rows(rows)

    def update_breakdown(self, payload: Mapping[str, Any]) -> None:
        """Render a descriptor/score payload for the selected hole."""
        rows = []
        for section in ("descriptors", "score"):
            values = payload.get(section, {})
            if isinstance(values, Mapping):
                rows.extend((f"{section}.{key}", value) for key, value in values.items())
        self._set_rows(rows)

    def update_pairwise(self, payload: Mapping[str, Any]) -> None:
        """Render the two sides of a pairwise hole comparison."""
        rows = []
        for side in ("left", "right"):
            record = payload.get(side, {})
            if isinstance(record, Mapping):
                rows.extend((f"{side}.{field}", value) for field, value in record.items() if field != "descriptors")
        self._set_rows(rows)

    def update_traceability(self, payload: Mapping[str, Any]) -> None:
        """Render calculation method and descriptor traceability fields."""
        rows = [("hole_id", payload.get("hole_id")), ("method", payload.get("method")), ("summary", payload.get("summary"))]
        descriptors = payload.get("descriptors", {})
        if isinstance(descriptors, Mapping):
            rows.extend((f"descriptors.{key}", value) for key, value in descriptors.items())
        self._set_rows(rows)

    def _set_rows(self, rows: Any) -> None:
        self.setRowCount(0)
        for field, value in rows:
            row = self.rowCount()
            self.insertRow(row)
            self.setItem(row, 0, QTableWidgetItem(str(field)))
            self.setItem(row, 1, QTableWidgetItem(str(value)))
