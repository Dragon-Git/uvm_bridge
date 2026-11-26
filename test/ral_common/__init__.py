"""Shared infrastructure for the pytest-driven RAL register tests.

Exports are resolved lazily so importing this package inside the simulator's
embedded Python (``reg_test.py`` uses :class:`ResultWriter` there) does not
pull pytest, clang or peakrdl into a process that only needs a JSON writer.
"""

from __future__ import annotations

import importlib
from typing import Any

__all__ = [
    "FIRMWARE_CASES",
    "PYRAL_CASES",
    "ArtifactCache",
    "ArtifactPaths",
    "ArtifactSpec",
    "RALSuiteSpec",
    "RalDriver",
    "ResultWriter",
    "SimConfig",
    "VerdictPolicy",
    "assert_case",
    "assert_floor",
    "build_driver",
]

_LAZY_EXPORTS: dict[str, str] = {
    "ArtifactCache": "artifacts",
    "ArtifactPaths": "artifacts",
    "ArtifactSpec": "spec",
    "FIRMWARE_CASES": "spec",
    "PYRAL_CASES": "spec",
    "RALSuiteSpec": "spec",
    "RalDriver": "driver",
    "ResultWriter": "result_writer",
    "SimConfig": "spec",
    "VerdictPolicy": "spec",
    "assert_case": "replay",
    "assert_floor": "replay",
    "build_driver": "driver",
}


def __getattr__(name: str) -> Any:
    """Import an export on first access (PEP 562)."""
    module_name = _LAZY_EXPORTS.get(name)
    if module_name is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    value = getattr(importlib.import_module(f".{module_name}", __name__), name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    """Make lazily exported names visible to ``dir()`` and IDEs."""
    return sorted(set(globals()) | set(__all__))
