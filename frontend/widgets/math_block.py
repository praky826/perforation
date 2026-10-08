"""Calculation explanation display for Phase 14."""

from __future__ import annotations

from typing import Any, Mapping

from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget


class MathBlock(QWidget):
    """Render the backend-provided calculation method and explanation."""

    def __init__(self) -> None:
        super().__init__()
        self.method = QLabel("Method: not loaded")
        self.summary = QLabel("No calculation explanation loaded.")
        self.summary.setWordWrap(True)
        layout = QVBoxLayout(self)
        layout.addWidget(self.method)
        layout.addWidget(self.summary)

    def update_explanation(self, payload: Mapping[str, Any]) -> None:
        """Display a math explanation payload without recalculating it."""
        self.method.setText(f"Method: {payload.get('method', 'unknown')}")
        self.summary.setText(str(payload.get("summary", "No calculation explanation loaded.")))
