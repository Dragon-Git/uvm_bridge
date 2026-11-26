"""Assertion helpers shared by the RAL replay test modules.

The simulator-side JSON is the only verdict source. These helpers make a
missing case, a failed case and a vacuously short run three distinct, readable
pytest failures instead of one opaque "TEST_PASS not found" grep result.
"""

from __future__ import annotations

from typing import Any
from collections.abc import Mapping


def _log_tail(results: Mapping[str, Any], limit: int = 4000) -> str:
    log = str(results.get("_log", ""))
    return log[-limit:]


def assert_case(case_name: str, results: Mapping[str, Any]) -> None:
    """Assert that one named case ran and passed on this backend.

    Args:
        case_name: Label from ``ral_common.spec`` (parametrized by conftest).
        results: The session fixture payload, including ``_log``.

    Raises:
        AssertionError: If the case did not run, failed, or recorded no check.
    """
    cases = {str(case.get("name", "")): case for case in results.get("cases", [])}
    assert case_name in cases, (
        f"{case_name} did not run on this backend\n{_log_tail(results)}"
    )
    case = cases[case_name]
    failures = [str(item) for item in case.get("failures", [])]
    assert case.get("status") == "pass", (
        "\n".join(failures) or f"{case_name} failed" + f"\n{_log_tail(results)}"
    )
    assert int(case.get("checks", 0)) >= 1, (
        f"{case_name} recorded no checks on this backend\n{_log_tail(results)}"
    )


def assert_floor(results: Mapping[str, Any], expected: int) -> None:
    """Guard against a run in which most cases bailed out early.

    Args:
        results: The session fixture payload.
        expected: Minimum number of cases and checks (8 for pyral, 9 for fw).

    Raises:
        AssertionError: If the run recorded fewer cases or checks than
            ``expected``. Individual failures are asserted by ``assert_case``
            so one bad check fails exactly one test.
    """
    cases = results.get("cases", [])
    checks = int(results.get("checks", 0))
    assert len(cases) >= expected, (
        f"only {len(cases)} of {expected} cases ran\n{_log_tail(results)}"
    )
    assert checks >= expected, (
        f"only {checks} checks for {expected} cases\n{_log_tail(results)}"
    )
