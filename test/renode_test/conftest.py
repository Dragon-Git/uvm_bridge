"""Thin pytest driver for the Renode firmware register-access test.

All simulation logic lives in :mod:`ral_common` and in the simulator-side
``reg_test.py``. This module declares the suite spec, binds the shared hooks,
and adds one dependency guard: Renode, pyrenode3 and PYRENODE_PATH are not
available on every developer machine. A missing prerequisite is an explicit
skip locally and an explicit failure in CI (``RAL_STRICT=1``) - never a silent
pass and never an opaque import error from inside the simulator.
"""

from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
TEST_ROOT = HERE.parent

if str(TEST_ROOT) not in sys.path:
    sys.path.insert(0, str(TEST_ROOT))

from ral_common import (  # noqa: E402  (sys.path prepared above)
    ArtifactSpec,
    FIRMWARE_CASES,
    RALSuiteSpec,
    SimConfig,
    VerdictPolicy,
    build_driver,
)

SV_DIR = TEST_ROOT / "pyral_test" / "sv"
RDL = TEST_ROOT / "pyral_test" / "demo_regs.rdl"
RTL_DIR = HERE / "rtl"
HEADER_DIR = HERE / "c_header"
BUILD_DIR = HERE / "build"
RTL_MODULE = "demo_reg_block"
FW_IMAGE = BUILD_DIR / "fw.bin"
PLATFORM = HERE / "platform" / "renode_test.repl"

_DRIVER = build_driver(
    RALSuiteSpec(
        suite="renode",
        cases=FIRMWARE_CASES,
        needs_renode=True,
        sim=SimConfig(
            test_dir=HERE,
            top_sv=SV_DIR / "top.sv",
            sv_sources=(
                SV_DIR / "apb3_intf.sv",
                SV_DIR / "apb3_intf_driver.sv",
                SV_DIR / "reg_agent_pkg.sv",
                SV_DIR / "reg_seq_pkg.sv",
                RTL_DIR / RTL_MODULE / "demo_regs_pkg.sv",
                RTL_DIR / RTL_MODULE / "demo_regs.sv",
            ),
            incdirs=(SV_DIR, RTL_DIR / RTL_MODULE, HEADER_DIR),
            uvm_testname="reg_test",
            py_dir=str(HERE),
            pythonpath_roots=(TEST_ROOT / "fw", TEST_ROOT),
            completion_marker="FW_TEST_DONE",
            verdict=VerdictPolicy.CasesOnly,
            verilator_warnings=("-Wno-TIMESCALEMOD", "-Wno-MULTIDRIVEN"),
            # The simulator-side reg_test.main() still starts Renode itself;
            # these variables only stage the artefacts and interpreter for it.
            extra_env={
                "FW_REG_IMAGE": str(FW_IMAGE),
                "PYRENODE_PATH": os.environ.get("PYRENODE_PATH", ""),
                "RENODE_TEST_PLATFORM": str(PLATFORM),
                "RENODE_TEST_PYTHON": os.environ.get("RENODE_TEST_PYTHON", sys.executable),
                "RENODE_ACCEPT_TIMEOUT": os.environ.get("RENODE_ACCEPT_TIMEOUT", "30"),
                "RENODE_TEST_TIMEOUT": os.environ.get("RENODE_TEST_TIMEOUT", "300"),
            },
            build_root=BUILD_DIR,
        ),
        artifacts=ArtifactSpec(
            root=HERE,
            rdl=RDL,
            need_regblock=True,
            need_cheader=True,
            need_firmware=True,
            rtl_dir=RTL_DIR,
            header_dir=HEADER_DIR,
            build_dir=BUILD_DIR,
            rdl_module=RTL_MODULE,
        ),
    )
)

pytest_generate_tests = _DRIVER.pytest_generate_tests
backend_results = _DRIVER.backend_results
artifacts = _DRIVER.artifacts

collect_ignore = ["reg_test.py", "renode_runner.py"]


def _missing_dependencies() -> list[str]:
    """List every missing Renode prerequisite with an actionable hint."""
    missing: list[str] = []
    try:
        found = importlib.util.find_spec("pyrenode3") is not None
    except (ImportError, ValueError):
        found = False
    if not found:
        missing.append("pyrenode3 is not importable (pip install . --group renode)")

    renode_home = os.environ.get("PYRENODE_PATH", "")
    if not renode_home:
        missing.append("PYRENODE_PATH is not set (point it at an unpacked Renode package)")
    else:
        home = Path(renode_home)
        if not home.is_dir():
            missing.append(f"PYRENODE_PATH {home} does not exist")
        elif not any(
            (home / name).exists()
            for name in ("Renode.runtimeconfig.json", "renode", "Renode.exe", "Renode")
        ):
            missing.append(f"PYRENODE_PATH {home} has no Renode runtime")

    python = os.environ.get("RENODE_TEST_PYTHON", sys.executable)
    if not Path(python.split()[0]).exists() and not os.environ.get("RENODE_TEST_PYTHON"):
        missing.append(f"RENODE_TEST_PYTHON {python!r} does not exist")
    return missing


@pytest.fixture(scope="session", autouse=True)
def renode_dependencies() -> None:
    """Skip locally / fail in CI when the Renode toolchain is not available.

    Session-scoped and autouse so it runs before ``artifacts`` and
    ``backend_results``: no simulator is started when the prerequisites are
    absent.
    """
    missing = _missing_dependencies()
    if not missing:
        return
    detail = "renode: missing prerequisites: " + "; ".join(missing)
    if os.environ.get("RAL_STRICT") == "1":
        pytest.fail(detail, pytrace=False)
    pytest.skip(detail, allow_module_level=False)
