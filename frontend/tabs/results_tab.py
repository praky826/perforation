"""Results, reporting, and traceability tab for Phases 14 and 15."""

from __future__ import annotations

from typing import Optional

from PySide6.QtWidgets import QFormLayout, QLabel, QLineEdit, QListWidget, QPushButton, QVBoxLayout, QWidget

from frontend.client import Client
from frontend.widgets.breakdown_table import BreakdownTable
from frontend.widgets.compass_plot import CompassPlot
from frontend.widgets.math_block import MathBlock


class ResultsTab(QWidget):
    """Load traceability, comparison, shadow, and citation data through Client."""

    def __init__(self, client: Optional[Client] = None) -> None:
        super().__init__()
        self.client = client or Client()
        self.session_id = QLineEdit()
        self.hole_id = QLineEdit()
        self.compare_to = QLineEdit()
        self.edge = QLineEdit("top")
        self.descriptor_type = QLineEdit("shape")
        self.region_id = QLineEdit()
        self.message = QLabel("No traceability data loaded.")
        self.summary_list = QListWidget()
        self.low_confidence = QLabel("Low-confidence holes: none loaded")
        self.breakdown = BreakdownTable()
        self.compass = CompassPlot()
        self.math = MathBlock()

        form = QFormLayout()
        form.addRow("Session", self.session_id)
        form.addRow("Hole", self.hole_id)
        form.addRow("Compare to", self.compare_to)
        form.addRow("Edge", self.edge)
        form.addRow("Descriptor", self.descriptor_type)
        form.addRow("Region", self.region_id)

        for label, handler in (
            ("Load pairwise comparison", self.load_pairwise),
            ("Load shadow vectors", self.load_shadow_vectors),
            ("Load math explanation", self.load_math),
            ("Load citation", self.load_citation),
            ("Load results summary", self.load_results_summary),
            ("Load region summary", self.load_region_summary),
            ("Load version metadata", self.load_version_metadata),
            ("Load config snapshot", self.load_config_snapshot),
            ("Run quality gate", self.run_quality_gate),
            ("Export session", self.export_session),
        ):
            button = QPushButton(label)
            button.clicked.connect(handler)
            form.addRow(button)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(self.summary_list)
        layout.addWidget(self.low_confidence)
        layout.addWidget(self.breakdown)
        layout.addWidget(self.compass)
        layout.addWidget(self.math)
        layout.addWidget(self.message)

    def load_pairwise(self) -> None:
        """Load pairwise hole comparison data."""
        response = self.client.call("get_pairwise_comparison", self.session_id.text().strip(), self.hole_id.text().strip(), self.compare_to.text().strip())
        payload = response.get("result", response)
        self.breakdown.update_pairwise(payload if isinstance(payload, dict) else {})
        self.message.setText("Pairwise comparison loaded.")

    def load_shadow_vectors(self) -> None:
        """Load shadow vectors for the selected edge."""
        response = self.client.call("get_shadow_vectors", self.session_id.text().strip(), self.edge.text().strip())
        payload = response.get("result", response)
        vectors = payload.get("holes", []) if isinstance(payload, dict) else []
        self.compass.update_vectors(vectors)
        self.message.setText("Shadow vectors loaded.")

    def load_math(self) -> None:
        """Load backend calculation explanation for the selected hole."""
        response = self.client.call("get_math_explanation", self.session_id.text().strip(), self.hole_id.text().strip())
        payload = response.get("result", response)
        if isinstance(payload, dict):
            self.math.update_explanation(payload)
            self.breakdown.update_traceability(payload)
        self.message.setText("Math explanation loaded.")

    def load_citation(self) -> None:
        """Load the citation associated with the selected descriptor."""
        response = self.client.call("get_citation", self.descriptor_type.text().strip())
        payload = response.get("result", response)
        self.message.setText(str(payload.get("citation", "Citation unavailable.")) if isinstance(payload, dict) else "Citation unavailable.")

    def load_results_summary(self) -> None:
        """Load score and suspicion rows for the current session."""
        session_id = self.session_id.text().strip()
        response = self.client.call("get_results_summary", session_id)
        payload = response.get("result", response)
        self.summary_list.clear()
        low_confidence = []
        for row in payload.get("holes", []) if isinstance(payload, dict) else []:
            hole_id = row.get("hole_id", "unknown")
            score = row.get("combined_score", "n/a")
            flagged = row.get("is_outlier", False)
            self.summary_list.addItem(f"{hole_id}: score={score}, outlier={flagged}")
            if row.get("low_confidence"):
                low_confidence.append(str(hole_id))
        self.low_confidence.setText("Low-confidence holes: " + (", ".join(low_confidence) if low_confidence else "none"))
        self.message.setText("Results summary loaded.")

    def load_region_summary(self) -> None:
        """Load one candidate-region summary."""
        response = self.client.call("get_region_summary", self.session_id.text().strip(), self.region_id.text().strip())
        payload = response.get("result", response)
        self.message.setText(f"Region summary: {payload.get('region', payload)}")

    def load_version_metadata(self) -> None:
        """Load application and configuration version metadata."""
        response = self.client.call("get_version_metadata", self.session_id.text().strip())
        payload = response.get("result", response)
        self.message.setText(f"Version metadata: {payload}")

    def export_session(self) -> None:
        """Request a packaged session archive through the backend API."""
        response = self.client.call("export_session", self.session_id.text().strip())
        self.message.setText(f"Session export: {response.get('result', response.get('error', 'unavailable'))}")

    def load_config_snapshot(self) -> None:
        """Load frozen constants and version information for traceability."""
        response = self.client.call("get_config_snapshot", self.session_id.text().strip())
        payload = response.get("result", response)
        self.message.setText(f"Config snapshot: {payload}")

    def run_quality_gate(self) -> None:
        """Load the backend quality-gate result for the session."""
        response = self.client.call("run_quality_gate", self.session_id.text().strip())
        payload = response.get("result", response)
        self.message.setText(f"Quality gate: {payload}")
