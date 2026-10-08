"""Validation and patent-support tab for Phase 17."""

from __future__ import annotations

from typing import Optional

from PySide6.QtWidgets import QFormLayout, QLabel, QLineEdit, QListWidget, QPushButton, QVBoxLayout, QWidget

from frontend.client import Client


class ValidationTab(QWidget):
    """Run labelled-specimen validation and inspect its report through Client."""

    def __init__(self, client: Optional[Client] = None) -> None:
        super().__init__()
        self.client = client or Client()
        self.specimen_set_id = QLineEdit()
        self.specimen_set_id.setPlaceholderText("Labelled specimen set identifier")
        self.run_id = QLineEdit()
        self.run_id.setPlaceholderText("Validation run identifier")
        self.message = QLabel("No validation run loaded.")
        self.report = QListWidget()

        form = QFormLayout()
        form.addRow("Specimen set", self.specimen_set_id)
        form.addRow("Run", self.run_id)
        run_button = QPushButton("Run validation")
        run_button.clicked.connect(self.run_validation)
        report_button = QPushButton("Load validation report")
        report_button.clicked.connect(self.load_report)
        form.addRow(run_button)
        form.addRow(report_button)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(self.report)
        layout.addWidget(self.message)

    def run_validation(self) -> None:
        """Start validation through the backend API."""
        response = self.client.call("run_validation", self.specimen_set_id.text().strip())
        payload = response.get("result", response)
        if isinstance(payload, dict) and payload.get("run_id"):
            self.run_id.setText(str(payload["run_id"]))
        self.message.setText(f"Validation result: {payload}")

    def load_report(self) -> None:
        """Load a saved validation report through the backend API."""
        response = self.client.call("get_validation_report", self.run_id.text().strip())
        payload = response.get("result", response)
        self.report.clear()
        if isinstance(payload, dict):
            report = payload.get("report", payload)
            if isinstance(report, dict):
                for key, value in report.items():
                    self.report.addItem(f"{key}: {value}")
        self.message.setText("Validation report loaded.")
