"""pytest driver for the cocotb regression, using the base_test replay model.

base_test.py here is a simulator-side module (it imports svuvm._svuvm and
registers cocotb tests), so it is ignored during collection. Instead this
conftest

* parses its static ``CASES`` table with ast (via ``cocotb_config``),
* runs the cocotb top once per enabled backend through base_test/sim_runner.py,
  letting the simulator write a backend-local JSON result file, and
* replays that JSON as one pytest test per case (see test_cocotb.py).

Backends come from ``SVUVM_COCOTB_BACKENDS`` (comma separated; default both),
so a machine that only has one simulator installed can still run the other
leg. The concrete simulation command and environment live in ``sim_runner``;
this module only dispatches on the backend name. Run serially (no
pytest-xdist): each backend has its own build directory under ``build/``.
"""

import json
import os
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
BASE_TEST_DIR = HERE.parent / "base_test"
CONTRACT_TEST = HERE / "test_xezim_runner_contract.py"

# cocotb_config lives next to this file; sim_runner lives in base_test/.
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(BASE_TEST_DIR))
import sim_runner  # noqa: E402
from cocotb_config import CASES, CocotbBackendConfig, cocotb_backends  # noqa: E402

# Matches pytest's default ``*_test.py`` pattern, but this file only runs
# inside the simulator as a cocotb test module.
collect_ignore = ["base_test.py"]


def pytest_collection_modifyitems(config, items):
    """Keep the directory-level regression at its 12-test baseline.

    The vendored-runner contract tests are a separate, explicit gate (CI runs
    the file by name). Including them in a directory-level run would change
    the long-standing ``12 passed`` count and, more importantly, import
    ``xezim_runner`` into the process that drives the verilator leg. Its
    ``register()`` side effect is only allowed in the xezim subprocess or in
    the dedicated contract-test process.
    """
    explicit = any(
        Path(arg).resolve() == CONTRACT_TEST.resolve() for arg in config.args
    )
    if explicit:
        return
    kept = [item for item in items if item.path.resolve() != CONTRACT_TEST.resolve()]
    if len(kept) != len(items):
        items[:] = kept


def pytest_generate_tests(metafunc):
    if "backend" in metafunc.fixturenames:
        metafunc.parametrize("backend", cocotb_backends(), scope="session")
    if "case_name" in metafunc.fixturenames:
        metafunc.parametrize("case_name", CASES, ids=CASES)


@pytest.fixture(scope="session")
def cocotb_results(backend, tmp_path_factory):
    """Run the cocotb regression once on ``backend`` and return its results."""
    # An explicit SVUVM_RESULT_JSON wins so a hand-written path can be
    # inspected; otherwise each backend gets its own file so the two legs can
    # never overwrite each other's verdict.
    result_json = Path(
        os.environ.get("SVUVM_RESULT_JSON")
        or (tmp_path_factory.mktemp("cocotb_test") / f"{backend}.json")
    )
    cfg = CocotbBackendConfig(
        backend=backend,
        result_json=result_json,
        build_dir=HERE / "build" / backend,
        uvm_home=None if backend == "xezim" else sim_runner.DEFAULT_UVM_HOME,
        max_time=os.environ.get("MAX_TIME", "10ms"),
        extra_env={"SVUVM_RESULT_JSON": str(result_json)},
    )
    env = cfg.merged_env()
    try:
        if cfg.backend == "verilator":
            returncode, log = sim_runner.cocotb_run(
                sys.executable, cfg.build_dir, cfg.uvm_home, env
            )
        elif cfg.backend == "xezim":
            returncode, log = sim_runner.cocotb_run_xezim(
                sys.executable, cfg.build_dir, cfg.uvm_home, env, cfg.max_time
            )
        else:
            pytest.fail(f"cocotb: unknown backend {cfg.backend!r}", pytrace=False)
    except sim_runner.SimError as exc:
        pytest.fail(f"cocotb/{cfg.backend}: {exc}", pytrace=False)

    # A cocotb test can fail while the simulator still exits 0; the JSON is
    # the verdict. A nonzero exit, however, is a hard failure (build/link/
    # simulator crash) and must never be silently turned into a pass.
    if returncode != 0:
        pytest.fail(
            f"cocotb/{cfg.backend}: simulator exited {returncode}\n{log[-20000:]}",
            pytrace=False,
        )
    if not result_json.exists():
        pytest.fail(
            f"cocotb/{cfg.backend}: base_test.py produced no result file\n{log[-20000:]}",
            pytrace=False,
        )
    data = json.loads(result_json.read_text(encoding="utf-8"))
    data["_log"] = log
    return data
