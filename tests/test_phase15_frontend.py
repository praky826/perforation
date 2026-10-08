import importlib


def test_phase15_results_surface_imports():
    results = importlib.import_module("frontend.tabs.results_tab")

    assert hasattr(results, "ResultsTab")
    assert hasattr(results.ResultsTab, "load_results_summary")
    assert hasattr(results.ResultsTab, "load_region_summary")
    assert hasattr(results.ResultsTab, "load_version_metadata")
    assert hasattr(results.ResultsTab, "export_session")
