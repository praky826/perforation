import importlib


def test_phase12_processing_modules_import():
    processing = importlib.import_module("frontend.tabs.processing_tab")
    stepper = importlib.import_module("frontend.widgets.progress_stepper")
    thumbnails = importlib.import_module("frontend.widgets.thumbnail_strip")

    assert hasattr(processing, "ProcessingTab")
    assert hasattr(stepper, "ProgressStepper")
    assert hasattr(thumbnails, "ThumbnailStrip")
