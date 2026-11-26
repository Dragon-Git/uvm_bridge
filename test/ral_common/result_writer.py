"""Simulator-side result accumulator with the base_test JSON schema.

The payload produced by :meth:`ResultWriter.dump` is intentionally identical
to ``test/base_test/bt_common.write_results()``::

    {
      "checks": int,
      "skips": int,
      "failures": [str],
      "cases": [
        {"name": str, "status": "pass|fail", "failures": [str], "checks": int}
      ],
    }

Only the presence of ``SVUVM_RESULT_JSON`` makes the writer emit anything, so
the same simulator-side module still runs by hand and leaves just UVM logs.
Writes go through a ``.tmp`` file and ``os.replace`` like bt_common does.
"""

from __future__ import annotations

import json
import os
from contextlib import contextmanager
from pathlib import Path
from typing import Callable
from collections.abc import Iterator


class ResultWriter:
    """Collect checks and per-case outcomes inside the simulator.

    ``case(name, fn)`` sets an active case while ``fn`` runs; every
    :meth:`check` made inside is attributed to that case. A callable that
    raises is recorded as a failed case rather than escaping and losing the
    rest of the run, which is what lets one bad check fail on its own during
    replay instead of aborting the whole simulation.
    """

    def __init__(self) -> None:
        """Create an empty accumulator."""
        self._cases: list[dict[str, object]] = []
        self._checks: int = 0
        self._skips: int = 0
        self._failures: list[str] = []
        self._active: list[dict[str, object]] = []

    @property
    def checks(self) -> int:
        """Number of checks executed so far."""
        return self._checks

    @property
    def failures(self) -> list[str]:
        """Copy of the failures recorded so far."""
        return list(self._failures)

    @property
    def cases(self) -> list[dict[str, object]]:
        """Copy of the case records accumulated so far."""
        return list(self._cases)

    def check(self, name: str, ok: bool, detail: str = "") -> bool:
        """Record one check and attribute it to the active case.

        Args:
            name: Check label (also the case name in the RAL suites).
            ok: Whether the check passed.
            detail: Human-readable detail appended to a failure message.

        Returns:
            ``ok``, so callers can branch on it without a second comparison.
        """
        self._checks += 1
        if ok:
            return True
        message = f"[FAIL] {name}" + (f" - {detail}" if detail else "")
        self._failures.append(message)
        if self._active:
            case = self._active[-1]
            case["failures"] = [*case["failures"], message]  # type: ignore[operator]
            case["status"] = "fail"
        return False

    def skip(self, name: str, reason: str = "") -> None:
        """Record an explicitly skipped check (never a silent pass)."""
        self._skips += 1
        message = f"[SKIP] {name}" + (f" - {reason}" if reason else "")
        if self._active:
            case = self._active[-1]
            case["failures"] = [*case["failures"], message]  # type: ignore[operator]

    @contextmanager
    def case_scope(self, name: str) -> Iterator[dict[str, object]]:
        """Context-manager form of :meth:`case`, for inline check blocks."""
        record: dict[str, object] = {
            "name": name,
            "status": "pass",
            "failures": [],
            "checks": 0,
        }
        self._active.append(record)
        before = self._checks
        try:
            yield record
        except Exception as exc:  # noqa: BLE001 - a case must not abort the run
            message = f"[FAIL] {name} raised {type(exc).__name__}: {exc}"
            self._failures.append(message)
            record["failures"] = [*record["failures"], message]  # type: ignore[operator]
            record["status"] = "fail"
        finally:
            record["checks"] = self._checks - before
            self._active.pop()
            self._cases.append(record)

    def case(self, name: str, fn: Callable[[], None]) -> None:
        """Run ``fn`` as one case and record its outcome.

        Args:
            name: Stable case label, normally from ``ral_common.spec``.
            fn: Callable performing one or more :meth:`check` calls.
        """
        with self.case_scope(name):
            fn()

    def dump(self, path: str | Path | None) -> None:
        """Atomically write the JSON payload, only when a path is supplied.

        Args:
            path: Value of ``SVUVM_RESULT_JSON``; ``None`` or empty means
                "manual run", in which case nothing is written.
        """
        if not path:
            return
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "checks": self._checks,
            "skips": self._skips,
            "failures": list(self._failures),
            "cases": self._cases,
        }
        tmp = f"{target}.tmp"
        with open(tmp, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2)
        os.replace(tmp, target)
