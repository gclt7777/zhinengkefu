"""Expose backend Open WebUI tests as a top-level ``test`` package."""
from __future__ import annotations

import importlib
import sys
from pathlib import Path

_repo_root = Path(__file__).resolve().parents[1]
_backend_dir = _repo_root / "backend"
if str(_backend_dir) not in sys.path:
    sys.path.insert(0, str(_backend_dir))

_backend_tests = importlib.import_module("backend.open_webui.test")
# Ensure common subpackages remain importable via ``test.util`` and similar paths.
sys.modules.setdefault("test.util", importlib.import_module("backend.open_webui.test.util"))

__all__ = getattr(_backend_tests, "__all__", ())
