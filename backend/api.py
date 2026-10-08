"""IPDS backend API bridge.

This module exposes the frozen backend API surface declared in the project
specification. It intentionally stays thin: each function delegates to the
existing backend services and catches exceptions so the UI layer can surface a
friendly message without crashing.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from backend.config.capture_schema import validate_captured_tags
from backend.config.pipeline_constants import get_pipeline_constants_dict
from backend.pipeline.runner import PipelineRunner
from backend.reporting.pdf_report import PdfReportGenerator
from backend.reporting.version_stamp import build_version_metadata
from backend.session.archive import SessionArchiver
from backend.session.session_manager import SessionManager
from backend.validation.validation_engine import ValidationEngine


def _session_manager() -> SessionManager:
    return SessionManager()


def _manifest(session_id: str) -> Dict[str, Any]:
    return _session_manager().get_manifest_manager(session_id).load()


def _safe_error(message: str) -> Dict[str, Any]:
    return {"success": False, "error": message}


def _read_json(path: Path) -> Any:
    if not path.exists():
        return None
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return json.load(handle)
    except (json.JSONDecodeError, OSError):
        return None


def validate_upload(session_id: str, tags: Dict[str, str]) -> Dict[str, Any]:
    """Feature 1: validate required capture tags for the session."""
    try:
        counts: Dict[str, int] = {}
        for key, value in (tags or {}).items():
            try:
                counts[str(key)] = int(value)
            except (TypeError, ValueError):
                counts[str(key)] = 0
        result = validate_captured_tags(counts)
        result["session_id"] = session_id
        return result
    except Exception as exc:  # pragma: no cover - defensive UI safety
        return _safe_error(f"Unable to validate upload: {exc}")


def compute_elevation(height: float, distance: float, correction: float = 0.0) -> float:
    """Feature 2: compute torch elevation from height and distance."""
    try:
        return SessionManager.compute_elevation(float(height), float(distance), float(correction))
    except Exception as exc:  # pragma: no cover - defensive UI safety
        return float(correction)


def save_session_log(session_id: str, log_data: Dict[str, Any]) -> bool:
    """Feature 2: persist the session log."""
    try:
        manager = _session_manager()
        if not manager.session_exists(session_id):
            manager.create_session(session_id, str((log_data or {}).get("specimen_id", "")))
        return manager.save_session_log(session_id, log_data or {})
    except Exception:
        return False


def acknowledge_shadow_bleed_check(session_id: str) -> bool:
    """Feature 3: record that a shadow-bleed check was acknowledged."""
    try:
        return _session_manager().set_shadow_bleed_acknowledged(session_id, True)
    except Exception:
        return False


def get_brightness_warnings(session_id: str) -> List[Dict[str, Any]]:
    """Feature 4: read brightness mismatches and warnings for the current session."""
    try:
        session_dir = _session_manager().get_session_dir(session_id)
        stage_path = session_dir / "stages" / "brightness_correction.json"
        payload = _read_json(stage_path) or {}
        warnings = payload.get("warnings") or payload.get("brightness_warnings") or []
        if isinstance(warnings, dict):
            return [{"message": str(warnings)}]
        return [dict(item) for item in warnings if isinstance(item, dict)]
    except Exception:
        return []


def get_pipeline_status(session_id: str) -> Dict[str, Any]:
    """Feature 5: current stage and status information for a session."""
    try:
        manager = _session_manager()
        if not manager.session_exists(session_id):
            return {"session_id": session_id, "status": "not_found", "stages": [], "holes_total": 0, "holes_processed": 0}
        manifest = manager.get_manifest_manager(session_id).load()
        return {
            "session_id": session_id,
            "status": manifest.get("status", "not_started"),
            "stages": manifest.get("stages", []),
            "holes_total": manifest.get("holes_total", 0),
            "holes_processed": manifest.get("holes_processed", 0),
            "low_confidence_holes": manifest.get("low_confidence_holes", []),
        }
    except Exception as exc:
        return _safe_error(f"Unable to read pipeline status: {exc}")


def get_manifest_diff(session_id: str, since_token: int = 0) -> Dict[str, Any]:
    """Feature 6: return the manifest changes since a given token."""
    try:
        manager = _session_manager()
        if not manager.session_exists(session_id):
            return {"session_id": session_id, "status": "not_found", "latest_token": 0, "new_images": [], "stages": [], "mod_token": 0}
        return manager.get_manifest_manager(session_id).get_manifest_diff(since_token)
    except Exception as exc:
        return _safe_error(f"Unable to read manifest diff: {exc}")


def get_hole_progress(session_id: str) -> Dict[str, Any]:
    """Feature 7: current hole processing progress."""
    try:
        manifest = _manifest(session_id)
        total = int(manifest.get("holes_total", 0))
        processed = int(manifest.get("holes_processed", 0))
        return {
            "session_id": session_id,
            "status": manifest.get("status", "not_started"),
            "holes_total": total,
            "holes_processed": processed,
            "remaining": max(total - processed, 0),
        }
    except Exception as exc:
        return _safe_error(f"Unable to read hole progress: {exc}")


def get_comparison_pair(session_id: str, image_id_a: str, image_id_b: str) -> Dict[str, Any]:
    """Feature 8: fetch a pair of images for side-by-side comparison."""
    try:
        images = (_manifest(session_id).get("images") or [])
        lookup = {str(img.get("path", "")): img for img in images}
        a = lookup.get(image_id_a) or {"path": image_id_a, "stage": "unknown"}
        b = lookup.get(image_id_b) or {"path": image_id_b, "stage": "unknown"}
        return {"success": True, "pair": [{"image_id": image_id_a, "image": a}, {"image_id": image_id_b, "image": b}]}
    except Exception as exc:
        return _safe_error(f"Unable to fetch comparison pair: {exc}")


def query_gallery(session_id: str, filters: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Feature 10: query the session gallery using simple filters."""
    try:
        images = (_manifest(session_id).get("images") or [])
        filtered: List[Dict[str, Any]] = []
        for image in images:
            match = True
            for key, value in (filters or {}).items():
                if value is None:
                    continue
                if image.get(key) != value:
                    match = False
                    break
            if match:
                filtered.append(image)
        return filtered
    except Exception:
        return []


def get_hole_tooltip(session_id: str, hole_id: str) -> Dict[str, Any]:
    """Feature 11: tooltip summary for a hole."""
    try:
        hole_path = _session_manager().get_session_dir(session_id) / "holes" / hole_id
        score = _read_json(hole_path / "score.json") or {}
        desc = _read_json(hole_path / "descriptors.json") or {}
        return {
            "hole_id": hole_id,
            "score": score.get("combined_score"),
            "type": score.get("type") or (desc.get("shape") or {}).get("kind"),
            "outlier": (score.get("outlier") or {}).get("is_outlier"),
            "summary": "Hole summary is available from the stored score and descriptor files.",
        }
    except Exception as exc:
        return _safe_error(f"Unable to load hole tooltip: {exc}")


def get_hole_breakdown(session_id: str, hole_id: str) -> Dict[str, Any]:
    """Feature 12: read all descriptor blocks and score for one hole."""
    try:
        hole_path = _session_manager().get_session_dir(session_id) / "holes" / hole_id
        descriptors = _read_json(hole_path / "descriptors.json") or {}
        score = _read_json(hole_path / "score.json") or {}
        return {"hole_id": hole_id, "descriptors": descriptors, "score": score}
    except Exception as exc:
        return _safe_error(f"Unable to load hole breakdown: {exc}")


def get_pairwise_comparison(session_id: str, hole_id: str, compare_to: str) -> Dict[str, Any]:
    """Feature 13: compare two holes and summarize features."""
    try:
        left = get_hole_breakdown(session_id, hole_id)
        right = get_hole_breakdown(session_id, compare_to)
        return {
            "success": True,
            "hole_id": hole_id,
            "compare_to": compare_to,
            "left": left,
            "right": right,
        }
    except Exception as exc:
        return _safe_error(f"Unable to compare holes: {exc}")


def get_shadow_vectors(session_id: str, edge: str) -> Dict[str, Any]:
    """Feature 14: summarize shadow vectors on one edge."""
    try:
        session_dir = _session_manager().get_session_dir(session_id)
        holes_dir = session_dir / "holes"
        results: List[Dict[str, Any]] = []
        if holes_dir.exists():
            for hole_dir in holes_dir.iterdir():
                if not hole_dir.is_dir():
                    continue
                meta = _read_json(hole_dir / "metadata.json") or {}
                if meta.get("edge") == edge or (hole_dir.name.startswith(f"{edge}_") and edge in ["top", "bottom", "left", "right"]):
                    desc = (_read_json(hole_dir / "descriptors.json") or {}).get("shadow") or {}
                    results.append({"hole_id": hole_dir.name, "shadow": desc})
        return {"edge": edge, "holes": results}
    except Exception as exc:
        return _safe_error(f"Unable to summarize shadow vectors: {exc}")


def get_math_explanation(session_id: str, hole_id: str) -> Dict[str, Any]:
    """Feature 15: describe the calculations behind the hole's score."""
    try:
        descriptor = _read_json(_session_manager().get_session_dir(session_id) / "holes" / hole_id / "descriptors.json") or {}
        score = _read_json(_session_manager().get_session_dir(session_id) / "holes" / hole_id / "score.json") or {}
        return {
            "hole_id": hole_id,
            "method": score.get("method", "summed_z"),
            "summary": "The score is assembled from robust z-values across the fixed 14-field composite signature and aggregated using the configured scale-aware deviation method.",
            "descriptors": descriptor,
        }
    except Exception as exc:
        return _safe_error(f"Unable to load math explanation: {exc}")


def get_edge_summary(session_id: str, edge: str) -> Dict[str, Any]:
    """Feature 16: edge-level summary."""
    try:
        regions = _read_json(_session_manager().get_session_dir(session_id) / "stages" / "candidate_regions.json") or []
        matching = [r for r in regions if r.get("edge") == edge]
        return {"edge": edge, "regions": matching, "count": len(matching)}
    except Exception as exc:
        return _safe_error(f"Unable to summarize edge: {exc}")


def get_citation(descriptor_type: str) -> Dict[str, Any]:
    """Feature 17: return the static literature citation attached to a descriptor."""
    try:
        source = _read_json(Path(__file__).resolve().parent / "citations" / "descriptor_sources.json") or {}
        entry = source.get(str(descriptor_type), {})
        return {"descriptor_type": descriptor_type, "citation": entry}
    except Exception as exc:
        return _safe_error(f"Unable to load citation: {exc}")


def get_results_summary(session_id: str) -> Dict[str, Any]:
    """Feature 18: summary of the score and suspicion results."""
    try:
        session_dir = _session_manager().get_session_dir(session_id)
        rows = []
        for hole_dir in (session_dir / "holes").iterdir():
            if hole_dir.is_dir():
                score = _read_json(hole_dir / "score.json") or {}
                rows.append({
                    "hole_id": hole_dir.name,
                    "combined_score": score.get("combined_score"),
                    "is_outlier": (score.get("outlier") or {}).get("is_outlier"),
                    "threshold_used": (score.get("outlier") or {}).get("threshold_used"),
                })
        return {"session_id": session_id, "holes": rows}
    except Exception as exc:
        return _safe_error(f"Unable to load results summary: {exc}")


def get_region_summary(session_id: str, region_id: str) -> Dict[str, Any]:
    """Feature 19: summarize a specific candidate region."""
    try:
        regions = _read_json(_session_manager().get_session_dir(session_id) / "stages" / "candidate_regions.json") or []
        for region in regions:
            if region.get("region_id") == region_id:
                return {"success": True, "region": region}
        return {"success": False, "region": None, "error": f"Region {region_id} not found."}
    except Exception as exc:
        return _safe_error(f"Unable to load region summary: {exc}")


def get_version_metadata(session_id: str) -> Dict[str, Any]:
    """Features 20 and 28: return the manifest metadata block for the session."""
    try:
        manager = _session_manager()
        manifest = manager.get_manifest_manager(session_id).load()
        metadata = manifest.get("version_metadata") or build_version_metadata()
        if "version_metadata" not in manifest:
            manager.get_manifest_manager(session_id).set_version_metadata(metadata)
        return metadata
    except Exception as exc:
        return _safe_error(f"Unable to load version metadata: {exc}")


def check_incomplete_session() -> Optional[Dict[str, Any]]:
    """Feature 22: return a resumable incomplete session if one exists."""
    try:
        return _session_manager().check_incomplete_session()
    except Exception:
        return None


def resume_session(session_id: str) -> Dict[str, Any]:
    """Feature 22: resume a session from the last completed step."""
    try:
        return _session_manager().resume_session(session_id)
    except Exception as exc:
        return _safe_error(f"Unable to resume session: {exc}")


def reset_session(session_id: str) -> bool:
    """Feature 23: delete the session directory."""
    try:
        return _session_manager().reset_session(session_id)
    except Exception:
        return False


def reprocess_from_stage(session_id: str, stage_id: str, corrected_inputs: Dict[str, Any] = None) -> Dict[str, Any]:
    """Feature 24: re-run the pipeline from a specific stage."""
    try:
        runner = PipelineRunner(_session_manager())
        try:
            step_id = int(str(stage_id).replace("step_", "").replace("stage_", ""))
        except ValueError:
            step_id = 1
        if corrected_inputs:
            # Corrected inputs are accepted for future UI-driven reprocessing; they are not
            # directly consumed by the runner in this phase.
            pass
        return runner.reprocess_from_stage(session_id, step_id)
    except Exception as exc:
        return _safe_error(f"Unable to reprocess from stage: {exc}")


def get_config_snapshot(session_id: str) -> Dict[str, Any]:
    """Feature 25: return the current config snapshot and version metadata."""
    try:
        return {
            "session_id": session_id,
            "constants": get_pipeline_constants_dict(),
            "version_metadata": get_version_metadata(session_id),
        }
    except Exception as exc:
        return _safe_error(f"Unable to read config snapshot: {exc}")


def run_validation(specimen_set_id: str) -> Dict[str, Any]:
    """Feature 26: run the validation benchmark for the specified specimen set."""
    try:
        return ValidationEngine(_session_manager()).run_validation(specimen_set_id)
    except Exception as exc:
        return _safe_error(f"Validation could not run: {exc}")


def get_validation_report(run_id: str) -> Dict[str, Any]:
    """Feature 26: fetch a saved validation report."""
    try:
        report = ValidationEngine(_session_manager()).get_validation_report(run_id)
        if report is None:
            return {"success": False, "report": None, "error": f"Run {run_id} not found."}
        return {"success": True, "report": report}
    except Exception as exc:
        return _safe_error(f"Unable to load validation report: {exc}")


def export_session(session_id: str) -> str:
    """Feature 27: package the session directory into a zip archive."""
    try:
        return SessionArchiver(_session_manager()).export_session(session_id)
    except Exception as exc:
        return str(exc)


def run_quality_gate(session_id: str) -> Dict[str, Any]:
    """Feature 29: evaluate whether the current session passes a minimal quality gate."""
    try:
        manifest = _manifest(session_id)
        stages = manifest.get("stages", [])
        holes_total = manifest.get("holes_total", 0)
        holes_processed = manifest.get("holes_processed", 0)
        issues: List[str] = []
        if manifest.get("status") not in {"complete", "in_progress"}:
            issues.append("Session status is not complete or in progress.")
        if holes_total and holes_processed < holes_total:
            issues.append("Not all holes have been processed.")
        if not any(stage.get("stage_name") == "step_23" for stage in stages):
            issues.append("Step 23 output not found.")
        return {"session_id": session_id, "passed": not issues, "issues": issues}
    except Exception as exc:
        return _safe_error(f"Unable to run quality gate: {exc}")


__all__ = [
    "validate_upload",
    "compute_elevation",
    "save_session_log",
    "acknowledge_shadow_bleed_check",
    "get_brightness_warnings",
    "get_pipeline_status",
    "get_manifest_diff",
    "get_hole_progress",
    "get_comparison_pair",
    "query_gallery",
    "get_hole_tooltip",
    "get_hole_breakdown",
    "get_pairwise_comparison",
    "get_shadow_vectors",
    "get_math_explanation",
    "get_edge_summary",
    "get_citation",
    "get_results_summary",
    "get_region_summary",
    "get_version_metadata",
    "check_incomplete_session",
    "resume_session",
    "reset_session",
    "reprocess_from_stage",
    "get_config_snapshot",
    "run_validation",
    "get_validation_report",
    "export_session",
    "run_quality_gate",
]
