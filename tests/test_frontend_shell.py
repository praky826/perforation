import importlib


def test_frontend_shell_imports():
    main_mod = importlib.import_module("frontend.main")
    main_window_mod = importlib.import_module("frontend.main_window")
    client_mod = importlib.import_module("frontend.client")

    assert hasattr(main_mod, "main")
    assert hasattr(main_window_mod, "MainWindow")
    assert hasattr(client_mod, "safe_call")
    assert hasattr(client_mod, "Client")
