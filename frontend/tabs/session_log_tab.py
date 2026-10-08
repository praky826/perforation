"""Session log and capture-condition controls for Phase 11."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from PySide6.QtWidgets import QFormLayout, QLabel, QLineEdit, QPushButton, QVBoxLayout, QWidget

from frontend.client import Client


class SessionLogTab(QWidget):
    """Collect the basic session log and record the shadow-bleed check."""

    def __init__(self, client: Optional[Client] = None) -> None:
        super().__init__()
        self.client = client or Client()
        self.session_id = QLineEdit()
        self.specimen_id = QLineEdit()
        self.operator_notes = QLineEdit()
        self.height_cm = QLineEdit("0")
        self.distance_cm = QLineEdit("1")
        self.correction_deg = QLineEdit("0")
        self.elevation = QLabel("Not calculated")
        self.message = QLabel()

        form = QFormLayout()
        form.addRow("Session", self.session_id)
        form.addRow("Specimen", self.specimen_id)
        form.addRow("Operator notes", self.operator_notes)
        form.addRow("Torch height (cm)", self.height_cm)
        form.addRow("Torch distance (cm)", self.distance_cm)
        form.addRow("Manual correction (deg)", self.correction_deg)
        form.addRow("Computed elevation", self.elevation)

        calculate_button = QPushButton("Compute elevation")
        calculate_button.clicked.connect(self.compute_elevation)
        save_button = QPushButton("Save session log")
        save_button.clicked.connect(self.save_log)
        acknowledge_button = QPushButton("Acknowledge shadow-bleed check")
        acknowledge_button.clicked.connect(self.acknowledge_shadow_bleed)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(calculate_button)
        layout.addWidget(save_button)
        layout.addWidget(acknowledge_button)
        layout.addWidget(self.message)

    def compute_elevation(self) -> None:
        """Compute torch elevation through the backend API."""
        response = self.client.call(
            "compute_elevation",
            self._number(self.height_cm.text()),
            self._number(self.distance_cm.text(), default=1.0),
            self._number(self.correction_deg.text()),
        )
        if response.get("success") is False:
            self.message.setText(response.get("error", "Unable to compute elevation."))
            return
        self.elevation.setText(f"{response.get('result', 0.0):.3f} deg")

    def save_log(self) -> None:
        """Save the current session log through the backend API."""
        session_id = self.session_id.text().strip()
        log_data = {
            "session_id": session_id,
            "specimen_id": self.specimen_id.text().strip(),
            "torches": [],
            "camera_settings": {},
            "ball_bearing_used": False,
            "capture_timestamp": datetime.now(timezone.utc).isoformat(),
            "operator_notes": self.operator_notes.text(),
        }
        response = self.client.call("save_session_log", session_id, log_data)
        self.message.setText("Session log saved." if response.get("result") else "Unable to save session log.")

    def acknowledge_shadow_bleed(self) -> None:
        """Record the operator acknowledgement through the backend API."""
        response = self.client.call("acknowledge_shadow_bleed_check", self.session_id.text().strip())
        self.message.setText("Shadow-bleed check acknowledged." if response.get("result") else "Unable to record acknowledgement.")

    @staticmethod
    def _number(value: str, default: float = 0.0) -> float:
        try:
            return float(value)
        except ValueError:
            return default
