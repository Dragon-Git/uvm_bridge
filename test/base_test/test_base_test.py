"""Per-block results of the base_test regression, across both backends.

The simulator-side work happens in the session-scoped ``backend_results``
fixture (see conftest.py); these tests only assert on what base_test.py
reported, so a failing block shows up as its own failing test.

    pytest -v test/base_test                     # verilator + xezim
    SVUVM_BACKENDS=xezim pytest -v test/base_test
"""

import pytest


pytestmark = pytest.mark.base_test


def test_case(case_name, backend_results):
    cases = {case["name"]: case for case in backend_results["cases"]}
    assert case_name in cases, f"{case_name} did not run on this backend"
    case = cases[case_name]
    assert case["status"] == "pass", "\n".join(case["failures"]) or f"{case_name} failed"


def test_assertion_floor(backend_results):
    """Guard against a vacuous pass: base_test.py enforces a minimum of checks."""
    assert backend_results["checks"] >= 350, (
        f"only {backend_results['checks']} checks executed on this backend"
    )
