import importlib


def test_phase17_validation_surface_imports():
    validation = importlib.import_module("frontend.tabs.validation_tab")
    main_window = importlib.import_module("frontend.main_window")
    upload = importlib.import_module("frontend.tabs.upload_tab")
    results = importlib.import_module("frontend.tabs.results_tab")

    assert hasattr(validation, "ValidationTab")
    assert hasattr(main_window, "MainWindow")
    assert hasattr(upload.UploadTab, "run_quality_gate")
    assert hasattr(results.ResultsTab, "load_config_snapshot")
    assert hasattr(results.ResultsTab, "run_quality_gate")
