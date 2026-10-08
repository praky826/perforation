"""Frontend API client for the IPDS desktop application."""

from __future__ import annotations

from typing import Any, Callable, Dict, Optional

from backend import api as backend_api


def safe_call(func: Callable[..., Any], *args: Any, **kwargs: Any) -> Dict[str, Any]:
    """Wrap backend calls in a safe, structured response."""
    try:
        result = func(*args, **kwargs)
        if isinstance(result, dict) and "success" in result and "error" in result:
            return result
        return {"success": True, "result": result}
    except Exception as exc:  # pragma: no cover - defensive UI safety
        return {"success": False, "error": f"Unable to complete the requested action: {exc}"}


class Client:
    """Thin wrapper used by frontend tabs and widgets to call backend.api."""

    def __init__(self, backend_module: Optional[Any] = None) -> None:
        self.backend = backend_module or backend_api

    def call(self, fn_name: str, *args: Any, **kwargs: Any) -> Dict[str, Any]:
        """Execute a backend method through the safe wrapper."""
        func = getattr(self.backend, fn_name)
        return safe_call(func, *args, **kwargs)
