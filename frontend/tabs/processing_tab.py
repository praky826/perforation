"""Processing status and session continuity tab for Phases 12 and 16."""

from __future__ import annotations

from typing import Optional

from PySide6.QtWidgets import QLabel, QLineEdit, QPushButton, QVBoxLayout, QWidget

from frontend.client import Client
from frontend.widgets.progress_stepper import ProgressStepper
from frontend.widgets.thumbnail_strip import ThumbnailStrip


class ProcessingTab(QWidget):
    """Refresh pipeline status, hole progress, and manifest images via Client."""

    def __init__(self, client: Optional[Client] = None) -> None:
        super().__init__()
        self.client = client or Client()
        self.session_id = QLineEdit()
        self.session_id.setPlaceholderText("Session identifier")
        self.stage_id = QLineEdit("1")
        self.stage_id.setPlaceholderText("Stage or step identifier")
        self.message = QLabel("Processing status has not been loaded.")
        self.stepper = ProgressStepper()
        self.thumbnails = ThumbnailStrip()
        refresh_button = QPushButton("Refresh processing status")
        refresh_button.clicked.connect(self.refresh_status)
        resume_button = QPushButton("Resume session")
        resume_button.clicked.connect(self.resume_session)
        reprocess_button = QPushButton("Reprocess from stage")
        reprocess_button.clicked.connect(self.reprocess_from_stage)

        layout = QVBoxLayout(self)
        layout.addWidget(self.session_id)
        layout.addWidget(self.stage_id)
        layout.addWidget(refresh_button)
        layout.addWidget(resume_button)
        layout.addWidget(reprocess_button)
        layout.addWidget(self.stepper)
        layout.addWidget(self.thumbnails)
        layout.addWidget(self.message)

    def refresh_status(self) -> None:
        """Fetch current status and manifest changes through the API bridge."""
        session_id = self.session_id.text().strip()
        status_response = self.client.call("get_pipeline_status", session_id)
        progress_response = self.client.call("get_hole_progress", session_id)
        diff_response = self.client.call("get_manifest_diff", session_id)
        if status_response.get("success") is False:
            self.message.setText(status_response.get("error", "Unable to read pipeline status."))
            return
        status = status_response.get("result", status_response)
        progress = progress_response.get("result", progress_response)
        diff = diff_response.get("result", diff_response)
        self.stepper.update_status(status, progress)
        self.thumbnails.update_images(diff.get("new_images", []) if isinstance(diff, dict) else [])
        self.message.setText(f"Pipeline status: {status.get('status', 'unknown')}")

    def resume_session(self) -> None:
        """Resume the selected session through the backend API."""
        response = self.client.call("resume_session", self.session_id.text().strip())
        payload = response.get("result", response)
        self.message.setText(f"Session resume: {payload}")

    def reprocess_from_stage(self) -> None:
        """Request pipeline reprocessing from the selected stage."""
        response = self.client.call("reprocess_from_stage", self.session_id.text().strip(), self.stage_id.text().strip(), {})
        payload = response.get("result", response)
        self.message.setText(f"Reprocessing request: {payload}")
