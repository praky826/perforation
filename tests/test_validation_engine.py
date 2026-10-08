from backend.validation.validation_engine import ValidationEngine
from backend.session.session_manager import SessionManager


def test_validation_without_specimens_writes_empty_report(tmp_path):
    manager = SessionManager(tmp_path / "sessions")
    report = ValidationEngine(manager).run_validation("missing_specimen_set")

    assert report["specimen_set_id"] == "missing_specimen_set"
    assert report["specimen_count"] == 0
    stored = ValidationEngine(manager).get_validation_report(report["run_id"])
    assert stored["run_id"] == report["run_id"]
    assert stored["results"] == []
