"""Capture upload and pre-flight validation tab for Phase 11."""

from __future__ import annotations

from typing import Optional

from PySide6.QtWidgets import QFormLayout, QLabel, QLineEdit, QPushButton, QVBoxLayout, QWidget

from frontend.client import Client
from frontend.widgets.checklist_widget import ChecklistWidget


class UploadTab(QWidget):
    """Collect capture counts and validate them through the backend API."""

    def __init__(self, client: Optional[Client] = None) -> None:
        super().__init__()
        self.client = client or Client()
        self.session_id = QLineEdit()
        self.session_id.setPlaceholderText("Session identifier")
        self._count_fields = {}
        for tag in ("diffuse", "torch_1", "torch_2", "torch_3", "torch_4", "backlit", "calibration"):
            field = QLineEdit("0")
            field.setObjectName(f"count_{tag}")
            self._count_fields[tag] = field

        form = QFormLayout()
        form.addRow("Session", self.session_id)
        for tag, field in self._count_fields.items():
            form.addRow(tag.replace("_", " ").title(), field)

        self.checklist = ChecklistWidget()
        self.message = QLabel("Capture set has not been checked.")
        validate_button = QPushButton("Validate capture set")
        validate_button.clicked.connect(self.validate_capture)
        quality_button = QPushButton("Run quality gate")
        quality_button.clicked.connect(self.run_quality_gate)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(validate_button)
        layout.addWidget(quality_button)
        layout.addWidget(self.checklist)
        layout.addWidget(self.message)

    def validate_capture(self) -> None:
        """Validate entered capture counts through frontend.client."""
        tags = {tag: field.text() for tag, field in self._count_fields.items()}
        response = self.client.call("validate_upload", self.session_id.text().strip(), tags)
        self.checklist.update_result(response)
        if response.get("success") is False:
            self.message.setText(response.get("error", "Capture validation failed."))
            return
        payload = response.get("result", response)
        ready = payload.get("ready", False) if isinstance(payload, dict) else False
        self.message.setText("Capture set is ready." if ready else "Required captures are missing or duplicated.")

    def run_quality_gate(self) -> None:
        """Request the backend quality gate for the current session."""
        response = self.client.call("run_quality_gate", self.session_id.text().strip())
        payload = response.get("result", response)
        passed = payload.get("passed", False) if isinstance(payload, dict) else False
        self.message.setText("Quality gate passed." if passed else f"Quality gate issues: {payload.get('issues', payload)}")
