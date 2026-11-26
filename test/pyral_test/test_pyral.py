"""Per-case results of the PyRAL regression, replayed from its JSON.

The simulator-side work happens once per backend in the session-scoped
``backend_results`` fixture (see conftest.py). A failing check therefore shows
up as its own failing test rather than as an opaque "no TEST_PASS" error, and
the floor prevents an early-exiting run from passing vacuously.

    pytest -v test/pyral_test
    SVUVM_BACKENDS=xezim pytest -v test/pyral_test
"""

from __future__ import annotations

import pytest

from ral_common import assert_case, assert_floor
from ral_common.spec import PYRAL_CASES

pytestmark = pytest.mark.ral


def test_case(case_name: str, backend_results: dict) -> None:
    """Replay one named case from the backend's simulator JSON."""
    assert_case(case_name, backend_results)


def test_assertion_floor(backend_results: dict) -> None:
    """Every pyral case must have run and recorded a check."""
    assert_floor(backend_results, len(PYRAL_CASES))
