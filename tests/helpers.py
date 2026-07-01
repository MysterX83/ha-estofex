"""Test helpers for loading ESTOFEX modules without Home Assistant."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import types
from types import ModuleType

ROOT = Path(__file__).resolve().parents[1]
PACKAGE_NAME = "custom_components.estofex"


def load_estofex_module(module_name: str) -> ModuleType:
    """Load an ESTOFEX module without importing the integration package."""
    _ensure_package()
    full_name = f"{PACKAGE_NAME}.{module_name}"
    if full_name in sys.modules:
        return sys.modules[full_name]

    module_path = ROOT / "custom_components" / "estofex" / f"{module_name}.py"
    spec = importlib.util.spec_from_file_location(full_name, module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load module {module_name}")

    module = importlib.util.module_from_spec(spec)
    sys.modules[full_name] = module
    spec.loader.exec_module(module)
    return module


def _ensure_package() -> None:
    """Create package placeholders without executing integration __init__."""
    sys.modules.setdefault("custom_components", types.ModuleType("custom_components"))
    package = sys.modules.get(PACKAGE_NAME)
    if package is None:
        package = types.ModuleType(PACKAGE_NAME)
        package.__path__ = []  # type: ignore[attr-defined]
        sys.modules[PACKAGE_NAME] = package
