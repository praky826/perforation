import importlib


def test_phase13_view_modules_import():
    view = importlib.import_module("frontend.tabs.view_tab")
    sync = importlib.import_module("frontend.widgets.graphics_view_sync")
    breakdown = importlib.import_module("frontend.widgets.breakdown_table")

    assert hasattr(view, "ViewTab")
    assert hasattr(sync, "GraphicsViewSync")
    assert hasattr(breakdown, "BreakdownTable")
