"""pytest driver for the in-simulator base_test regression.

base_test.py cannot be imported here: it needs ``svuvm._svuvm`` and a live
simulator, and its blocks run inside ``main_phase``. So instead of importing
it, this module

* parses the ``TESTS`` table statically for the list of block names,
* runs the simulator once per backend (see sim_runner.run), letting
  base_test.py write a JSON result file, and
* replays that result as one pytest test per block.

Backends come from ``SVUVM_BACKENDS`` (comma separated; default both), so a
machine that only has one simulator installed can still run the other leg. Run
this serially (no pytest-xdist): both backends use ``test/base_test/build``.
On a memory-constrained box set ``NPROC=1`` so parallel cc1plus processes do
not get OOM-killed.

    SVUVM_BACKENDS=xezim pytest -v test/base_test
"""

import ast
import json
import os
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
BASE_TEST = HERE / "base_test.py"

sys.path.insert(0, str(HERE))
import sim_runner  # noqa: E402

# base_test.py matches pytest's default ``*_test.py`` pattern, but it is not a
# pytest module: it runs inside the simulator and imports svuvm._svuvm.
collect_ignore = ["base_test.py"]


def _parse_cases():
    """Read the block names out of ``TESTS`` without importing base_test."""
    tree = ast.parse(BASE_TEST.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == "TESTS" for target in node.targets
        ):
            return [entry.elts[0].value for entry in node.value.elts]
    raise pytest.UsageError(f"could not find a TESTS table in {BASE_TEST}")


CASES = _parse_cases()


def _backends():
    raw = os.environ.get("SVUVM_BACKENDS")
    if raw is None:
        return ["verilator", "xezim"]
    names = [name.strip() for name in raw.split(",") if name.strip()]
    if not names:
        raise pytest.UsageError("SVUVM_BACKENDS is set but empty; use verilator,xezim or unset it")
    return names


def pytest_generate_tests(metafunc):
    if "backend" in metafunc.fixturenames:
        metafunc.parametrize("backend", _backends(), scope="session")
    if "case_name" in metafunc.fixturenames:
        metafunc.parametrize("case_name", CASES, ids=CASES)


@pytest.fixture(scope="session")
def backend_results(backend, tmp_path_factory):
    """Run the whole base test once on one backend and return its results."""
    result_path = tmp_path_factory.mktemp("base_test") / f"{backend}.json"
    try:
        returncode, log = sim_runner.run(
            backend,
            python=sys.executable,
            extra_env={"SVUVM_RESULT_JSON": str(result_path)},
        )
    except sim_runner.SimError as exc:
        pytest.fail(f"{backend}: {exc}", pytrace=False)

    # _verdict maps [VPI] diagnostics and a missing completion marker to a
    # nonzero code, but writes nothing into the JSON; failing here keeps an
    # otherwise all-pass result file from masking either condition.
    if returncode != 0:
        pytest.fail(f"{backend}: simulator exited {returncode}\n{log[-20000:]}", pytrace=False)
    if not result_path.exists():
        pytest.fail(
            f"{backend}: base_test.py produced no result file\n{log[-20000:]}",
            pytrace=False,
        )
    data = json.loads(result_path.read_text(encoding="utf-8"))
    data["_log"] = log
    return data
