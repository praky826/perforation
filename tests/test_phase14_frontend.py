import importlib


def test_phase14_traceability_modules_import():
    results = importlib.import_module("frontend.tabs.results_tab")
    compass = importlib.import_module("frontend.widgets.compass_plot")
    math_block = importlib.import_module("frontend.widgets.math_block")

    assert hasattr(results, "ResultsTab")
    assert hasattr(compass, "CompassPlot")
    assert hasattr(math_block, "MathBlock")
