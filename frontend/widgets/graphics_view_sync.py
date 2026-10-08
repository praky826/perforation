"""Synchronized comparison views for Phase 13."""

from __future__ import annotations

from typing import Any, Iterable

from PySide6.QtWidgets import QGraphicsScene, QGraphicsView, QLabel, QHBoxLayout, QVBoxLayout, QWidget


class GraphicsViewSync(QWidget):
    """Present two comparison records with synchronized zoom state."""

    def __init__(self) -> None:
        super().__init__()
        self.left_view = QGraphicsView()
        self.right_view = QGraphicsView()
        self.left_view.setScene(QGraphicsScene(self.left_view))
        self.right_view.setScene(QGraphicsScene(self.right_view))
        self.left_view.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.right_view.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self._scale = 1.0
        layout = QHBoxLayout(self)
        layout.addWidget(self._panel("Image A", self.left_view))
        layout.addWidget(self._panel("Image B", self.right_view))

    @staticmethod
    def _panel(title: str, view: QGraphicsView) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.addWidget(QLabel(title))
        layout.addWidget(view)
        return panel

    def set_pair(self, pair: Iterable[dict[str, Any]]) -> None:
        """Render comparison metadata as scene labels without frontend file I/O."""
        views = (self.left_view, self.right_view)
        for view, record in zip(views, pair):
            scene = view.scene()
            scene.clear()
            image = record.get("image", record) if isinstance(record, dict) else {}
            scene.addText(str(image.get("path", "No image selected")))
            scene.addText(f"Stage: {image.get('stage', 'unknown')}").setPos(0, 24)

    def set_zoom(self, factor: float) -> None:
        """Apply the same relative zoom factor to both views."""
        if factor <= 0:
            return
        relative = factor / self._scale
        self.left_view.scale(relative, relative)
        self.right_view.scale(relative, relative)
        self._scale = factor
