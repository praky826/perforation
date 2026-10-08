"""Comparison and hole-inspection view for Phase 13."""

from __future__ import annotations

from typing import Optional

from PySide6.QtWidgets import QFormLayout, QLabel, QLineEdit, QListWidget, QPushButton, QVBoxLayout, QWidget

from frontend.client import Client
from frontend.widgets.breakdown_table import BreakdownTable
from frontend.widgets.graphics_view_sync import GraphicsViewSync


class ViewTab(QWidget):
    """Query gallery items and inspect comparison or hole details through Client."""

    def __init__(self, client: Optional[Client] = None) -> None:
        super().__init__()
        self.client = client or Client()
        self.session_id = QLineEdit()
        self.image_a = QLineEdit()
        self.image_b = QLineEdit()
        self.hole_id = QLineEdit()
        self.message = QLabel("No view data loaded.")
        self.gallery = QListWidget()
        self.comparison = GraphicsViewSync()
        self.breakdown = BreakdownTable()

        form = QFormLayout()
        form.addRow("Session", self.session_id)
        form.addRow("Image A", self.image_a)
        form.addRow("Image B", self.image_b)
        form.addRow("Hole", self.hole_id)
        gallery_button = QPushButton("Refresh gallery")
        gallery_button.clicked.connect(self.refresh_gallery)
        compare_button = QPushButton("Compare images")
        compare_button.clicked.connect(self.compare_images)
        tooltip_button = QPushButton("Load hole tooltip")
        tooltip_button.clicked.connect(self.load_tooltip)
        breakdown_button = QPushButton("Load hole breakdown")
        breakdown_button.clicked.connect(self.load_breakdown)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(gallery_button)
        layout.addWidget(compare_button)
        layout.addWidget(tooltip_button)
        layout.addWidget(breakdown_button)
        layout.addWidget(self.gallery)
        layout.addWidget(self.comparison)
        layout.addWidget(self.breakdown)
        layout.addWidget(self.message)

    def refresh_gallery(self) -> None:
        """Load gallery records using the backend query endpoint."""
        response = self.client.call("query_gallery", self.session_id.text().strip(), {})
        if response.get("success") is False:
            self.message.setText(response.get("error", "Unable to load gallery."))
            return
        records = response.get("result", response)
        self.gallery.clear()
        for record in records if isinstance(records, list) else []:
            self.gallery.addItem(f"{record.get('stage', 'unknown')}: {record.get('path', '')}")
        self.message.setText(f"Gallery entries: {self.gallery.count()}")

    def compare_images(self) -> None:
        """Load a comparison pair through the backend API."""
        response = self.client.call("get_comparison_pair", self.session_id.text().strip(), self.image_a.text().strip(), self.image_b.text().strip())
        if response.get("success") is False:
            self.message.setText(response.get("error", "Unable to load comparison."))
            return
        payload = response.get("result", response)
        self.comparison.set_pair(payload.get("pair", []) if isinstance(payload, dict) else [])
        self.message.setText("Comparison loaded.")

    def load_tooltip(self) -> None:
        """Load compact hole details through the backend API."""
        response = self.client.call("get_hole_tooltip", self.session_id.text().strip(), self.hole_id.text().strip())
        payload = response.get("result", response)
        self.breakdown.update_tooltip(payload if isinstance(payload, dict) else {})
        self.message.setText("Hole tooltip loaded.")

    def load_breakdown(self) -> None:
        """Load the selected hole's descriptor breakdown."""
        response = self.client.call("get_hole_breakdown", self.session_id.text().strip(), self.hole_id.text().strip())
        payload = response.get("result", response)
        self.breakdown.update_breakdown(payload if isinstance(payload, dict) else {})
        self.message.setText("Hole breakdown loaded.")
