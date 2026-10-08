import importlib


def test_phase11_category_a_modules_import():
    upload = importlib.import_module("frontend.tabs.upload_tab")
    checklist = importlib.import_module("frontend.widgets.checklist_widget")
    session_log = importlib.import_module("frontend.tabs.session_log_tab")

    assert hasattr(upload, "UploadTab")
    assert hasattr(checklist, "ChecklistWidget")
    assert hasattr(session_log, "SessionLogTab")
