"""Manifest thumbnail listing for Phase 12."""

from __future__ import annotations

from typing import Any, Iterable

from PySide6.QtWidgets import QListWidget, QListWidgetItem


class ThumbnailStrip(QListWidget):
    """List displayable manifest images without loading image data in the UI."""

    def update_images(self, images: Iterable[dict[str, Any]]) -> None:
        """Replace the displayed image entries from manifest data."""
        self.clear()
        for image in images:
            path = str(image.get("path", ""))
            stage = str(image.get("stage", "unknown"))
            hole_id = image.get("hole_id") or ""
            item = QListWidgetItem(f"{stage}: {hole_id} {path}".strip())
            item.setData(256, image)
            self.addItem(item)
