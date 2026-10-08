"""Resume-session dialog for Phase 16."""

from __future__ import annotations

from typing import Any, Optional

from PySide6.QtWidgets import QDialog, QLabel, QPushButton, QVBoxLayout

from frontend.client import Client


class ResumeSessionDialog(QDialog):
    """Find and resume the incomplete session through the API bridge."""

    def __init__(self, client: Optional[Client] = None) -> None:
        super().__init__()
        self.client = client or Client()
        self.session_id: Optional[str] = None
        self.message = QLabel("No incomplete session checked.")
        check_button = QPushButton("Check incomplete session")
        check_button.clicked.connect(self.check_incomplete)
        resume_button = QPushButton("Resume found session")
        resume_button.clicked.connect(self.resume_found)
        layout = QVBoxLayout(self)
        layout.addWidget(self.message)
        layout.addWidget(check_button)
        layout.addWidget(resume_button)

    def check_incomplete(self) -> None:
        """Ask the backend for an incomplete session."""
        response = self.client.call("check_incomplete_session")
        payload = response.get("result", response)
        self.session_id = payload.get("session_id") if isinstance(payload, dict) else None
        self.message.setText(f"Incomplete session: {self.session_id or 'none'}")

    def resume_found(self) -> None:
        """Resume the session found by the previous check."""
        if not self.session_id:
            self.message.setText("Check for an incomplete session first.")
            return
        response = self.client.call("resume_session", self.session_id)
        self.message.setText(f"Resume result: {response.get('result', response)}")
