"""Session-reset confirmation dialog for Phase 16."""

from __future__ import annotations

from typing import Optional

from PySide6.QtWidgets import QDialog, QLabel, QLineEdit, QPushButton, QVBoxLayout

from frontend.client import Client


class ResetConfirmDialog(QDialog):
    """Confirm and request session reset through the backend API."""

    def __init__(self, client: Optional[Client] = None) -> None:
        super().__init__()
        self.client = client or Client()
        self.session_id = QLineEdit()
        self.session_id.setPlaceholderText("Session identifier")
        self.message = QLabel("Reset is not yet requested.")
        reset_button = QPushButton("Reset session")
        reset_button.clicked.connect(self.reset_session)
        layout = QVBoxLayout(self)
        layout.addWidget(self.session_id)
        layout.addWidget(reset_button)
        layout.addWidget(self.message)

    def reset_session(self) -> None:
        """Request deletion of the selected session through the API bridge."""
        response = self.client.call("reset_session", self.session_id.text().strip())
        self.message.setText("Session reset." if response.get("result") else "Session reset failed.")
