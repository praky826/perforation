"""Application entry point for the IPDS desktop shell."""

from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from frontend.main_window import MainWindow


def main() -> int:
    """Create the application and show the main window."""
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
