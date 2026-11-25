"""pytest driver for the cocotb regression, using the base_test replay model.

base_test.py here is a simulator-side module (it imports svuvm._svuvm and
registers cocotb tests), so it is ignored during collection. Instead this
conftest

* parses its static ``CASES`` table with ast,
* builds and runs the cocotb top once through base_test/sim_runner.py, letting
  the simulator write the shared JSON result file, and
* replays that JSON as one pytest test per case (see test_cocotb.py).

There is no backend parameterization: the cocotb leg runs on verilator only.
Run this serially (no pytest-xdist): the build directory is shared with manual
``sim_runner.py cocotb`` runs.
"""

import ast
import json
import os
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
BASE_TEST_DIR = HERE.parent / "base_test"
SIMULATOR_MODULE = HERE / "base_test.py"

sys.path.insert(0, str(BASE_TEST_DIR))
import sim_runner  # noqa: E402

# Matches pytest's default ``*_test.py`` pattern, but this file only runs
# inside the simulator as a cocotb test module.
collect_ignore = ["base_test.py"]


def _parse_cases():
    """Read the case names out of ``CASES`` without importing base_test.py."""
    tree = ast.parse(SIMULATOR_MODULE.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == "CASES" for target in node.targets
        ):
            return [entry.value for entry in node.value.elts]
    raise pytest.UsageError(f"could not find a CASES table in {SIMULATOR_MODULE}")


CASES = _parse_cases()


def pytest_generate_tests(metafunc):
    if "case_name" in metafunc.fixturenames:
        metafunc.parametrize("case_name", CASES, ids=CASES)


@pytest.fixture(scope="session")
def cocotb_results(tmp_path_factory):
    """Run the cocotb regression once and return its per-case results."""
    # An explicit SVUVM_RESULT_JSON wins so `SVUVM_RESULT_JSON=/tmp/x.json
    # pytest test/cocotb_test` can be inspected by hand; CI gets a temp file.
    result_path = Path(
        os.environ.get("SVUVM_RESULT_JSON")
        or (tmp_path_factory.mktemp("cocotb_test") / "verilator.json")
    )
    try:
        returncode, log = sim_runner.cocotb_run(
            sys.executable,
            HERE / "build",
            sim_runner.DEFAULT_UVM_HOME,
            {"SVUVM_RESULT_JSON": str(result_path)},
        )
    except sim_runner.SimError as exc:
        pytest.fail(f"cocotb: {exc}", pytrace=False)

    # A cocotb test can fail while Vtop still exits 0; the JSON is the verdict.
    # A nonzero exit, however, is a hard failure (build/link/simulator crash).
    if returncode != 0:
        pytest.fail(f"cocotb: simulator exited {returncode}\n{log[-20000:]}", pytrace=False)
    if not result_path.exists():
        pytest.fail(
            f"cocotb: base_test.py produced no result file\n{log[-20000:]}",
            pytrace=False,
        )
    data = json.loads(result_path.read_text(encoding="utf-8"))
    data["_log"] = log
    return data
