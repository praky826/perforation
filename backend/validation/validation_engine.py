"""Validation Mode - Labeled Specimen Benchmarking (Feature 26).

File: backend/validation/validation_engine.py
Runs the unmodified Steps 1-23 pipeline against labeled validation specimens,
compares the flagged holes/regions against each specimen's known ground truth
to compute confusion counts, sweeps Step 21's cutoff to build ROC points, and
optionally computes per-hole score drift across two independently captured
sessions of the same specimen.

Per the Validation Data Rule, this module is complete and correct but creates
no specimen data. It reads whatever labeled specimens the user later supplies
under backend/validation/labeled_specimens/<specimen_set_id>/ and degrades
gracefully when none are present.

Expected specimen layout (supplied by the user, never generated here):
  labeled_specimens/<specimen_set_id>/<specimen_name>/
      ground_truth.json  -> {specimen_id, altered_hole_ids: [..],
                             ground_truth_region: {edge, start_position,
                             end_position} | null, has_repeat: bool}
      raw/               -> tagged raw capture files for the primary session
      raw_repeat/        -> (optional) second independent capture for repeatability

Contains zero Qt/PySide6 imports.
"""

import json
import logging
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from backend.config.pipeline_constants import (
    VALIDATION_ROC_CUTOFF_MAX,
    VALIDATION_ROC_CUTOFF_MIN,
    VALIDATION_ROC_CUTOFF_STEPS,
)
from backend.pipeline.runner import PipelineRunner
from backend.session.session_manager import SessionManager

logger = logging.getLogger(__name__)

LABELED_SPECIMENS_DIR = Path(__file__).parent / "labeled_specimens"


def _load_json(path: Path) -> Any:
    if not path.exists():
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None


def _cutoff_sweep() -> List[float]:
    """Build the configured list of cutoff values for the ROC sweep."""
    steps = max(2, VALIDATION_ROC_CUTOFF_STEPS)
    span = VALIDATION_ROC_CUTOFF_MAX - VALIDATION_ROC_CUTOFF_MIN
    return [VALIDATION_ROC_CUTOFF_MIN + span * i / (steps - 1) for i in range(steps)]


def _confusion_at(scores: Dict[str, float], altered: set, cutoff: float) -> Dict[str, int]:
    """Confusion counts treating combined_score > cutoff as a positive prediction."""
    tp = fp = fn = tn = 0
    for hole_id, score in scores.items():
        predicted = score > cutoff
        actual = hole_id in altered
        if predicted and actual:
            tp += 1
        elif predicted and not actual:
            fp += 1
        elif not predicted and actual:
            fn += 1
        else:
            tn += 1
    return {"tp": tp, "fp": fp, "fn": fn, "tn": tn}


def _rates(counts: Dict[str, int]) -> tuple:
    """Return (tpr, fpr) from a confusion-count dict."""
    tp, fp, fn, tn = counts["tp"], counts["fp"], counts["fn"], counts["tn"]
    tpr = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    fpr = fp / (fp + tn) if (fp + tn) > 0 else 0.0
    return tpr, fpr


class ValidationEngine:
    """Benchmarks the pipeline against labeled specimens and writes a report."""

    def __init__(self, session_manager: Optional[SessionManager] = None) -> None:
        self.session_manager = session_manager or SessionManager()
        self.runner = PipelineRunner(self.session_manager)

    # ------------------------------------------------------------------ public
    def run_validation(self, specimen_set_id: str) -> Dict[str, Any]:
        """Run the pipeline over each labeled specimen and write validation_report.json."""
        set_dir = LABELED_SPECIMENS_DIR / specimen_set_id
        run_id = f"validation_{specimen_set_id}_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"

        results: List[Dict[str, Any]] = []
        specimen_dirs = sorted([d for d in set_dir.iterdir() if d.is_dir()]) if set_dir.exists() else []

        if not specimen_dirs:
            logger.warning("No labeled specimens found under %s", set_dir)

        for specimen_dir in specimen_dirs:
            try:
                results.append(self._evaluate_specimen(specimen_dir, run_id))
            except Exception as exc:
                logger.exception("Validation failed for specimen %s", specimen_dir.name)
                results.append({
                    "specimen_id": specimen_dir.name,
                    "error": str(exc),
                    "ground_truth_region": None,
                    "predicted_region": None,
                    "confusion_counts": {"tp": 0, "fp": 0, "fn": 0, "tn": 0},
                    "roc_points": [],
                    "repeatability_deltas": None,
                })

        report = {
            "run_id": run_id,
            "specimen_set_id": specimen_set_id,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "specimen_count": len(results),
            "results": results,
        }

        run_dir = self.session_manager.get_session_dir(run_id)
        run_dir.mkdir(parents=True, exist_ok=True)
        with open(run_dir / "validation_report.json", "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)
        return report

    def get_validation_report(self, run_id: str) -> Optional[Dict[str, Any]]:
        """Read a previously written validation_report.json for a run."""
        run_dir = self.session_manager.get_session_dir(run_id)
        return _load_json(run_dir / "validation_report.json")

    # --------------------------------------------------------------- internals
    def _evaluate_specimen(self, specimen_dir: Path, run_id: str) -> Dict[str, Any]:
        """Run the pipeline on one specimen and score it against its ground truth."""
        gt = _load_json(specimen_dir / "ground_truth.json") or {}
        specimen_id = gt.get("specimen_id", specimen_dir.name)
        altered = set(gt.get("altered_hole_ids", []))
        gt_region = gt.get("ground_truth_region")

        session_id = f"{run_id}_{specimen_dir.name}"
        self._stage_session(session_id, specimen_id, specimen_dir / "raw")
        self.runner.run(session_id)

        scores = self._read_scores(session_id)
        run_counts = _confusion_at(scores, altered, cutoff=self._run_threshold(session_id))
        roc_points = [
            {"threshold": c, **dict(zip(("tpr", "fpr"), _rates(_confusion_at(scores, altered, c))))}
            for c in _cutoff_sweep()
        ]
        predicted_region = self._predicted_region(session_id)

        repeatability = None
        if gt.get("has_repeat") and (specimen_dir / "raw_repeat").exists():
            repeatability = self._repeatability(specimen_id, specimen_dir, run_id, scores)

        return {
            "specimen_id": specimen_id,
            "ground_truth_region": gt_region,
            "predicted_region": predicted_region,
            "confusion_counts": run_counts,
            "roc_points": roc_points,
            "repeatability_deltas": repeatability,
        }

    def _stage_session(self, session_id: str, specimen_id: str, raw_src: Path) -> None:
        """Create a fresh session and copy the specimen's raw capture files into it."""
        if self.session_manager.session_exists(session_id):
            self.session_manager.reset_session(session_id)
        self.session_manager.create_session(session_id, specimen_id)
        dest = self.session_manager.get_session_dir(session_id) / "raw"
        dest.mkdir(parents=True, exist_ok=True)
        if raw_src.exists():
            for f in raw_src.iterdir():
                if f.is_file():
                    shutil.copy2(f, dest / f.name)

    def _read_scores(self, session_id: str) -> Dict[str, float]:
        """Map hole_id -> combined_score from each hole's score.json."""
        holes_dir = self.session_manager.get_session_dir(session_id) / "holes"
        scores: Dict[str, float] = {}
        if not holes_dir.exists():
            return scores
        for h_dir in holes_dir.iterdir():
            data = _load_json(h_dir / "score.json")
            if isinstance(data, dict):
                scores[h_dir.name] = float(data.get("combined_score", 0.0))
        return scores

    def _run_threshold(self, session_id: str) -> float:
        """Recover the threshold_used actually applied in this run (from any hole)."""
        holes_dir = self.session_manager.get_session_dir(session_id) / "holes"
        if holes_dir.exists():
            for h_dir in holes_dir.iterdir():
                data = _load_json(h_dir / "score.json")
                if isinstance(data, dict) and "outlier" in data:
                    return float(data["outlier"].get("threshold_used", 0.0))
        return 0.0

    def _predicted_region(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Summarize the largest candidate region as the specimen's predicted region."""
        regions = _load_json(
            self.session_manager.get_session_dir(session_id) / "stages" / "candidate_regions.json"
        )
        if not isinstance(regions, list) or not regions:
            return None
        largest = max(regions, key=lambda r: len(r.get("hole_ids", [])))
        return {
            "edge": largest.get("edge"),
            "start_position": largest.get("start_position"),
            "end_position": largest.get("end_position"),
        }

    def _repeatability(
        self, specimen_id: str, specimen_dir: Path, run_id: str, primary_scores: Dict[str, float]
    ) -> List[Dict[str, Any]]:
        """Run the second capture and compute per-matched-hole score deltas."""
        repeat_session = f"{run_id}_{specimen_dir.name}_repeat"
        self._stage_session(repeat_session, specimen_id, specimen_dir / "raw_repeat")
        self.runner.run(repeat_session)
        repeat_scores = self._read_scores(repeat_session)
        return [
            {"hole_id": hid, "score_delta": abs(primary_scores[hid] - repeat_scores[hid])}
            for hid in sorted(set(primary_scores) & set(repeat_scores))
        ]
