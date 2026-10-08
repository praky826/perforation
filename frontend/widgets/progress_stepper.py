"""Pipeline progress stepper for Phase 12."""

from __future__ import annotations

from typing import Any, Iterable

from PySide6.QtWidgets import QLabel, QProgressBar, QVBoxLayout, QWidget


class ProgressStepper(QWidget):
    """Display the current pipeline stage and hole-processing progress."""

    def __init__(self) -> None:
        super().__init__()
        self.stage_label = QLabel("Stage: not started")
        self.hole_label = QLabel("Holes: 0 / 0")
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        layout = QVBoxLayout(self)
        layout.addWidget(self.stage_label)
        layout.addWidget(self.hole_label)
        layout.addWidget(self.progress)

    def update_status(self, status: dict[str, Any], progress: dict[str, Any] | None = None) -> None:
        """Render status and optional hole-progress payloads from the API."""
        stages: Iterable[dict[str, Any]] = status.get("stages", []) if isinstance(status, dict) else []
        latest = list(stages)[-1] if stages else {}
        stage_name = latest.get("stage_name", status.get("status", "not started"))
        self.stage_label.setText(f"Stage: {stage_name}")
        payload = progress or status
        total = int(payload.get("holes_total", 0))
        processed = int(payload.get("holes_processed", 0))
        self.hole_label.setText(f"Holes: {processed} / {total}")
        self.progress.setValue(round(processed * 100 / total) if total else 0)
