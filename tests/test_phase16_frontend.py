import importlib


def test_phase16_continuity_modules_import():
    resume = importlib.import_module("frontend.dialogs.resume_session_dialog")
    reset = importlib.import_module("frontend.dialogs.reset_confirm_dialog")
    processing = importlib.import_module("frontend.tabs.processing_tab")

    assert hasattr(resume, "ResumeSessionDialog")
    assert hasattr(reset, "ResetConfirmDialog")
    assert hasattr(processing.ProcessingTab, "resume_session")
    assert hasattr(processing.ProcessingTab, "reprocess_from_stage")
