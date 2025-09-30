"""Test package initialization utilities."""
from __future__ import annotations

import sys
from pathlib import Path

# Ensure the backend directory is importable so ``open_webui`` can be resolved
# when running the test suite directly from the repository root.
backend_dir = Path(__file__).resolve().parents[2]
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

# Expose the ``test`` package alias to maintain compatibility with modules
# importing ``test.util`` helpers.
sys.modules.setdefault("test", sys.modules[__name__])
try:
    sys.modules.setdefault("test.util", sys.modules[f"{__name__}.util"])
except KeyError:
    # Lazily import util helpers if they have not been loaded yet.
    import importlib

    sys.modules.setdefault(
        "test.util", importlib.import_module(f"{__name__}.util")
    )
