"""Per-case results of the Renode firmware regression, replayed from JSON.

The simulator-side work happens once per backend in the session-scoped
``backend_results`` fixture (see conftest.py). Renode itself is started from
the simulator, not from pytest, so both the xezim and verilator legs use this
same replay. Missing Renode prerequisites are reported by the conftest guard.

    pytest -v test/renode_test
    SVUVM_BACKENDS=xezim pytest -v test/renode_test
"""

from __future__ import annotations

import pytest

from ral_common import assert_case, assert_floor
from ral_common.spec import FIRMWARE_CASES

pytestmark = pytest.mark.ral


def test_case(case_name: str, backend_results: dict) -> None:
    """Replay one named firmware case from the backend's simulator JSON."""
    assert_case(case_name, backend_results)


def test_assertion_floor(backend_results: dict) -> None:
    """Every firmware case (8 trace accesses + read sum) must have run."""
    assert_floor(backend_results, len(FIRMWARE_CASES))
