"""Per-case results of the cocotb regression, replayed from its JSON.

The simulator-side work happens in the session-scoped ``cocotb_results``
fixture (see conftest.py); these tests only assert on what the cocotb module
reported, so a failing case shows up as its own failing test.

    pytest -v test/cocotb_test
"""

import pytest

pytestmark = pytest.mark.cocotb

# Keep in sync with CASES in base_test.py; the floor prevents a run in which
# most cases bailed out early from passing vacuously.
EXPECTED_CASES = 11


def test_case(case_name, cocotb_results):
    cases = {case["name"]: case for case in cocotb_results["cases"]}
    assert case_name in cases, f"{case_name} did not run in the cocotb regression"
    case = cases[case_name]
    assert case["status"] == "pass", "\n".join(case["failures"]) or f"{case_name} failed"


def test_assertion_floor(cocotb_results):
    """Guard against a vacuous pass: every expected case recorded a check."""
    cases = cocotb_results["cases"]
    assert len(cases) >= EXPECTED_CASES, f"only {len(cases)} of {EXPECTED_CASES} cases ran"
    assert cocotb_results["checks"] >= EXPECTED_CASES, (
        f"only {cocotb_results['checks']} checks for {len(cases)} cases"
    )
