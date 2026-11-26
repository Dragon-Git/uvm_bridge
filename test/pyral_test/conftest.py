"""Thin pytest driver for the PyRAL register-access test.

All the logic lives in :mod:`ral_common`; this module only declares which
sources/incdirs/entry point this suite uses and binds the shared hooks. The
simulator-side ``reg_test.py`` is a simulator module, not a pytest module, so
it is excluded by name while the pure-Python ``demo_test.py`` is collected.
"""

from __future__ import annotations

import sys
from pathlib import Path


HERE = Path(__file__).resolve().parent
TEST_ROOT = HERE.parent

# ral_common is a package under test/, not under this directory.
if str(TEST_ROOT) not in sys.path:
    sys.path.insert(0, str(TEST_ROOT))

from ral_common import (  # noqa: E402  (sys.path prepared above)
    ArtifactSpec,
    PYRAL_CASES,
    RALSuiteSpec,
    SimConfig,
    VerdictPolicy,
    build_driver,
)

PY_DIR = HERE / "pyral_test"
SV_DIR = HERE / "sv"
GEN_DIR = HERE / "gen"
RTL_DIR = HERE / "rtl"
RTL_MODULE = "demo_reg_block"

_DRIVER = build_driver(
    RALSuiteSpec(
        suite="pyral",
        cases=PYRAL_CASES,
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
            incdirs=(SV_DIR, GEN_DIR, RTL_DIR / RTL_MODULE),
            uvm_testname="reg_test",
            py_dir=str(PY_DIR),
            pythonpath_roots=(PY_DIR, GEN_DIR),
            # TEST_PASS/TEST_FAIL remain human-facing UVM log lines.
            # PYRAL_TEST_DONE is printed unconditionally at the end of main(),
            # so a single failing case is visible in the JSON replay instead
            # of turning the whole simulator run into a hard failure.
            completion_marker="PYRAL_TEST_DONE",
            verdict=VerdictPolicy.CasesOnly,
            # TIMESCALEMOD comes from UVM/peakrdl packages without a
            # timescale; MULTIDRIVEN is Verilator's struct-granularity view
            # of peakrdl writing distinct struct members in separate blocks.
            # Neither is a real driver conflict. Base_test's flags are intact.
            verilator_warnings=("-Wno-TIMESCALEMOD", "-Wno-MULTIDRIVEN"),
            build_root=HERE / "build",
        ),
        artifacts=ArtifactSpec(
            root=HERE,
            rdl=HERE / "demo_regs.rdl",
            need_pyral=True,
            need_regblock=True,
            gen_dir=GEN_DIR,
            rtl_dir=RTL_DIR,
            build_dir=HERE / "build",
            rdl_module=RTL_MODULE,
        ),
    )
)

pytest_generate_tests = _DRIVER.pytest_generate_tests
backend_results = _DRIVER.backend_results
artifacts = _DRIVER.artifacts

collect_ignore = ["pyral_test/reg_test.py"]
