"""Backend configuration and static case discovery for the cocotb regression.

The cocotb suite runs the same simulator-side ``base_test.py`` on every enabled
backend. This module is the single source for

* the backend list (``SVUVM_COCOTB_BACKENDS``, comma separated, default both),
  with the same empty-string handling as ``test/base_test/conftest.py``; and
* the static ``CASES`` table parsed out of ``base_test.py`` with :mod:`ast`,
  because that module can only be imported inside a live simulator.

:class:`CocotbBackendConfig` is a small frozen carrier used by the session
fixture in ``conftest.py``. It deliberately does not reuse RAL's ``SimConfig``:
the cocotb top and UVM test name are fixed, so the RAL fields would be noise.
"""

from __future__ import annotations

import ast
import os
from dataclasses import dataclass, field
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
SIMULATOR_MODULE = HERE / "base_test.py"

DEFAULT_BACKENDS = ("verilator", "xezim")


def _parse_cases() -> list[str]:
    """Read the case names out of ``CASES`` without importing base_test.py."""
    tree = ast.parse(SIMULATOR_MODULE.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == "CASES" for target in node.targets
        ):
            return [entry.value for entry in node.value.elts]
    raise pytest.UsageError(f"could not find a CASES table in {SIMULATOR_MODULE}")


CASES = _parse_cases()


def cocotb_backends() -> list[str]:
    """Return enabled cocotb backends from ``SVUVM_COCOTB_BACKENDS``.

    Unset means both backends in the canonical order. A set-but-empty value is
    an error rather than a silent no-op; whitespace is stripped and duplicates
    are removed while preserving the user's order.
    """
    raw = os.environ.get("SVUVM_COCOTB_BACKENDS")
    if raw is None:
        return list(DEFAULT_BACKENDS)
    names = [name.strip() for name in raw.split(",") if name.strip()]
    if not names:
        raise pytest.UsageError(
            "SVUVM_COCOTB_BACKENDS is set but empty; use verilator,xezim or unset it"
        )
    return list(dict.fromkeys(names))


# The design uses both spellings in different sections; they are the same API.
_cocotb_backends = cocotb_backends


@dataclass(frozen=True)
class CocotbBackendConfig:
    """Immutable per-backend description consumed by ``cocotb_results``."""

    backend: str
    result_json: Path
    build_dir: Path
    uvm_home: Path | None = None
    max_time: str = "10ms"
    extra_env: dict[str, str] = field(default_factory=dict)

    def merged_env(self, extra: dict[str, str] | None = None) -> dict[str, str]:
        """Return ``extra_env`` overlaid by ``extra`` without mutating self."""
        merged = dict(self.extra_env)
        if extra:
            merged.update({key: str(value) for key, value in extra.items()})
        return merged
