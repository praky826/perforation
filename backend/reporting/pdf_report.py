"""Exportable PDF Report (Feature 20).

File: backend/reporting/pdf_report.py
Combines Step 23's annotated overview image, the per-hole results table, the
candidate-region summary, and Feature 28's version-metadata block into one
self-contained PDF, pulling directly from existing outputs with no new
computation. ReportLab is imported lazily so this module loads even when the
package is not yet installed.

Contains zero Qt/PySide6 imports.
"""

import csv
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from backend.reporting.version_stamp import build_version_metadata
from backend.session.session_manager import SessionManager

logger = logging.getLogger(__name__)


def _load_json(path: Path) -> Any:
    if not path.exists():
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None


def _read_results_table(path: Path) -> List[List[str]]:
    if not path.exists():
        return []
    with open(path, "r", encoding="utf-8", newline="") as f:
        return [row for row in csv.reader(f)]


class PdfReportGenerator:
    """Lays out and writes the session report PDF from existing session outputs."""

    def __init__(self, session_manager: Optional[SessionManager] = None) -> None:
        self.session_manager = session_manager or SessionManager()

    def generate_report(self, session_id: str) -> str:
        """Assemble results/report.pdf and return its relative path."""
        # Lazy import keeps the module importable without reportlab installed.
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import landscape, letter
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.lib.units import inch
        from reportlab.platypus import (
            Image,
            PageBreak,
            Paragraph,
            SimpleDocTemplate,
            Spacer,
            Table,
            TableStyle,
        )

        session_dir = self.session_manager.get_session_dir(session_id)
        results_dir = session_dir / "results"
        results_dir.mkdir(parents=True, exist_ok=True)

        manifest = self.session_manager.get_manifest_manager(session_id)
        manifest_data = manifest.load()
        version_meta = manifest_data.get("version_metadata") or build_version_metadata()
        session_log = self.session_manager.load_session_log(session_id) or {}

        annotated = results_dir / "annotated_overview.png"
        table_rows = _read_results_table(results_dir / "results_table.csv")
        regions = _load_json(session_dir / "stages" / "candidate_regions.json") or []

        out_path = results_dir / "report.pdf"
        styles = getSampleStyleSheet()
        doc = SimpleDocTemplate(str(out_path), pagesize=landscape(letter))
        story: List[Any] = []

        # Title / session metadata.
        story.append(Paragraph("IPDS Reperforation Analysis Report", styles["Title"]))
        story.append(Spacer(1, 0.15 * inch))
        meta_lines = [
            f"Session ID: {session_id}",
            f"Specimen ID: {session_log.get('specimen_id', 'N/A')}",
            f"Status: {manifest_data.get('status', 'unknown')}",
            f"Holes total: {manifest_data.get('holes_total', 0)}",
            f"Holes processed: {manifest_data.get('holes_processed', 0)}",
            f"Capture timestamp: {session_log.get('capture_timestamp', 'N/A')}",
        ]
        for line in meta_lines:
            story.append(Paragraph(line, styles["Normal"]))
        story.append(PageBreak())

        # Annotated overview image.
        story.append(Paragraph("Annotated Overview", styles["Heading2"]))
        if annotated.exists():
            story.append(Image(str(annotated), width=9.0 * inch, height=6.0 * inch, kind="proportional"))
        else:
            story.append(Paragraph("Annotated overview image not available.", styles["Normal"]))
        story.append(PageBreak())

        # Full per-hole results table.
        story.append(Paragraph("Per-Hole Results Table", styles["Heading2"]))
        if table_rows:
            tbl = Table(table_rows, repeatRows=1)
            tbl.setStyle(TableStyle([
                ("FONTSIZE", (0, 0), (-1, -1), 5),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
                ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ]))
            story.append(tbl)
        else:
            story.append(Paragraph("Results table not available.", styles["Normal"]))
        story.append(PageBreak())

        # Candidate-region summary.
        story.append(Paragraph("Candidate Region Summary", styles["Heading2"]))
        if regions:
            for r in regions:
                story.append(Paragraph(
                    f"{r.get('region_id')}: edge={r.get('edge')}, "
                    f"positions {r.get('start_position')}-{r.get('end_position')}, "
                    f"holes={', '.join(r.get('hole_ids', []))}",
                    styles["Normal"],
                ))
        else:
            story.append(Paragraph("No candidate regions were flagged.", styles["Normal"]))
        story.append(Spacer(1, 0.25 * inch))

        # Version / method metadata block.
        story.append(Paragraph("Method &amp; Version Metadata", styles["Heading2"]))
        story.append(Paragraph(f"App version: {version_meta.get('app_version', 'N/A')}", styles["Normal"]))
        story.append(Paragraph(f"Python: {version_meta.get('python_version', 'N/A')}", styles["Normal"]))
        story.append(Paragraph(f"Captured at: {version_meta.get('captured_at', 'N/A')}", styles["Normal"]))
        libs = version_meta.get("library_versions", {})
        if libs:
            lib_str = ", ".join(f"{k} {v}" for k, v in libs.items())
            story.append(Paragraph(f"Libraries: {lib_str}", styles["Normal"]))

        doc.build(story)
        logger.info("Generated PDF report for session %s at %s", session_id, out_path)
        return "results/report.pdf"
