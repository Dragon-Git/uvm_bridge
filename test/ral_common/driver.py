"""Shared pytest driver: backend × case parametrization and one sim per leg.

A suite's thin ``conftest.py`` only declares a :class:`RALSuiteSpec` and binds
the two hooks this class produces. Everything else - artefact preparation,
build-directory isolation, environment injection, hard-failure handling, JSON
readback - lives here so pyral / unicorn / renode cannot drift apart.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

import pytest

_BASE_TEST_DIR = Path(__file__).resolve().parents[1] / "base_test"
if str(_BASE_TEST_DIR) not in sys.path:
    sys.path.insert(0, str(_BASE_TEST_DIR))
import sim_runner  # noqa: E402  (path prepared immediately above)

from .artifacts import ArtifactCache
from .spec import RALSuiteSpec


def _backends() -> list[str]:
    """Read ``SVUVM_BACKENDS``; both legs are the default, as in base_test."""
    raw = os.environ.get("SVUVM_BACKENDS")
    if raw is None:
        return ["verilator", "xezim"]
    names = [name.strip() for name in raw.split(",") if name.strip()]
    if not names:
        raise pytest.UsageError("SVUVM_BACKENDS is set but empty; use verilator,xezim or unset it")
    return names


class RalDriver:
    """Turn a :class:`RALSuiteSpec` into pytest hooks for one suite."""

    def __init__(self, spec: RALSuiteSpec) -> None:
        """Bind the driver to one suite specification."""
        self.spec = spec

    def pytest_generate_tests(self, metafunc: pytest.Metafunc) -> None:
        """Parametrize ``backend`` and ``case_name`` from the shared spec."""
        if "backend" in metafunc.fixturenames:
            metafunc.parametrize("backend", _backends(), scope="session")
        if "case_name" in metafunc.fixturenames:
            cases = list(self.spec.cases)
            metafunc.parametrize("case_name", cases, ids=cases)

    @pytest.fixture(scope="session")
    def artifacts(self) -> Any:
        """Generate (or reuse) the suite's peakrdl / firmware artefacts."""
        try:
            return ArtifactCache.ensure(self.spec.artifacts, "verilator")
        except sim_runner.SimError as exc:
            self._prerequisite_failure(exc)
        raise AssertionError("unreachable")  # pragma: no cover

    @pytest.fixture(scope="session")
    def backend_results(self, backend: str, artifacts: Any, tmp_path_factory: Any) -> dict[str, Any]:
        """Run the whole suite once on one backend and return its JSON."""
        result_path = tmp_path_factory.mktemp(f"{self.spec.suite}_{backend}") / "result.json"
        returncode, log = self._run_sim(backend, result_path)
        return self._guard(backend, returncode, log, result_path)

    def _prerequisite_failure(self, exc: BaseException) -> None:
        """Skip locally for a missing tool, fail in CI via ``RAL_STRICT=1``."""
        detail = f"{self.spec.suite}: {exc}"
        if os.environ.get("RAL_STRICT") == "1":
            pytest.fail(detail, pytrace=False)
        pytest.skip(detail, allow_module_level=False)

    def _build_dir(self, backend: str) -> Path:
        root = self.spec.sim.build_root or self.spec.artifacts.root / "build"
        return root / backend

    def _run_sim(self, backend: str, result_path: Path) -> tuple[int, str]:
        config = self.spec.sim
        env = config.merged_env({"SVUVM_RESULT_JSON": str(result_path)})
        try:
            return sim_runner.run(
                backend,
                config=config,
                python=sys.executable,
                build_dir=self._build_dir(backend),
                extra_env=env,
            )
        except sim_runner.SimTimeoutError as exc:
            # A wall-clock kill is a real failure, not a missing prerequisite:
            # never downgrade it to a local skip, regardless of RAL_STRICT.
            pytest.fail(f"{self.spec.suite}/{backend}: {exc}", pytrace=False)
        except sim_runner.SimError as exc:
            self._prerequisite_failure(exc)
        raise AssertionError("unreachable")  # pragma: no cover

    def _guard(self, backend: str, returncode: int, log: str, result_path: Path) -> dict[str, Any]:
        """Turn simulator exit / JSON problems into explicit pytest failures."""
        if returncode != 0:
            pytest.fail(f"{self.spec.suite}/{backend}: simulator exited {returncode}\n{log[-20000:]}", pytrace=False)
        if not result_path.is_file():
            pytest.fail(
                f"{self.spec.suite}/{backend}: no result JSON at {result_path}\n{log[-20000:]}",
                pytrace=False,
            )
        try:
            data = json.loads(result_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            pytest.fail(f"{self.spec.suite}/{backend}: unreadable result JSON: {exc}", pytrace=False)
        if not isinstance(data, dict) or not all(
            key in data for key in ("checks", "skips", "failures", "cases")
        ):
            pytest.fail(
                f"{self.spec.suite}/{backend}: result JSON has the wrong schema: "
                f"{sorted(data) if isinstance(data, dict) else data!r}",
                pytrace=False,
            )
        data["_log"] = log
        return data


def build_driver(spec: RALSuiteSpec) -> RalDriver:
    """Factory used by each suite's thin conftest."""
    if not spec.cases:
        raise ValueError(f"{spec.suite}: cases must not be empty")
    return RalDriver(spec)
