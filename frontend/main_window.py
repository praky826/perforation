"""Main application window for the IPDS desktop shell."""

from __future__ import annotations

from PySide6.QtWidgets import QMainWindow, QTabWidget

from frontend.client import Client
from frontend.tabs.processing_tab import ProcessingTab
from frontend.tabs.results_tab import ResultsTab
from frontend.tabs.upload_tab import UploadTab
from frontend.tabs.validation_tab import ValidationTab
from frontend.tabs.view_tab import ViewTab


class MainWindow(QMainWindow):
    """Minimal top-level shell for the desktop application."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("IPDS Reperforation Detection")
        client = Client()
        tabs = QTabWidget()
        tabs.addTab(UploadTab(client), "Upload")
        tabs.addTab(ProcessingTab(client), "Processing")
        tabs.addTab(ViewTab(client), "View")
        tabs.addTab(ResultsTab(client), "Results")
        tabs.addTab(ValidationTab(client), "Validation")
        self.setCentralWidget(tabs)
        self.resize(1200, 800)
