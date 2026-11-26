"""Contract tests for the vendored xezim cocotb runner (no real xezim needed).

The vendored runner is the authority for the command-line semantics that
``sim_runner.cocotb_run_xezim`` reproduces by hand. These tests lock those
semantics down without launching a simulator:

* the VPI flavour is the plain IEEE 1800 ``vcs`` build;
* ``build()`` records sources/includes/defines without compiling;
* ``_test_command()`` keeps ``--sv2017``, one ``--vpi-lib``, ``-s <top>`` and
  the plusargs in the documented order;
* ``register()`` is idempotent and leaves the stock verilator runner intact.

The ``register()`` side effect is contained: the in-process fixture restores
every global it mutates, and the idempotence check runs in a subprocess, so
the verilator leg of the main pytest process never sees a patched
``get_runner``.
"""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from cocotb_tools import config as cocotb_config
from cocotb_tools import runner as cocotb_runner

HERE = Path(__file__).resolve().parent
VENDORED = HERE / "xezim_runner.py"
_MODULE_NAME = "_xezim_runner_contract"


def _load_vendored():
    """Import the vendored module under a private name (fires ``register()``)."""
    spec = importlib.util.spec_from_file_location(_MODULE_NAME, VENDORED)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[_MODULE_NAME] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def vendored():
    """Load the vendored runner, then undo all of its global registration."""
    runner = cocotb_runner

    stock_get_runner = runner.get_runner
    supported = getattr(runner, "SUPPORTED_RUNNERS", None)
    supported_before = dict(supported) if isinstance(supported, dict) else None
    had_xezim_attr = hasattr(runner, "Xezim")
    module = _load_vendored()
    try:
        yield module
    finally:
        # Plain assignment, not monkeypatch: monkeypatch would restore the
        # *wrapped* function it saw at teardown time.
        runner.get_runner = stock_get_runner
        if isinstance(supported, dict) and supported_before is not None:
            supported.clear()
            supported.update(supported_before)
        if not had_xezim_attr and hasattr(runner, "Xezim"):
            delattr(runner, "Xezim")
        sys.modules.pop(_MODULE_NAME, None)


def test_vpi_flavour_and_gpi_interface(vendored, monkeypatch):
    """The runner must use the plain VPI library and declare VPI-only support."""
    monkeypatch.delenv("XEZIM_COCOTB_VPI_FLAVOUR", raising=False)
    reloaded = _load_vendored()  # re-read the flavour after the env cleanup
    monkeypatch.setattr(reloaded, "XEZIM_BIN", sys.executable)  # needs a real file at ctor
    assert reloaded._VPI_LIB_FLAVOUR == "vcs"
    assert reloaded.Xezim.supported_gpi_interfaces == {"verilog": ["vpi"]}
    lib = reloaded.Xezim()._vpi_lib
    assert lib.name == "libcocotbvpi_vcs.so"
    assert lib.is_file()


def test_build_records_sources_without_compiling(vendored, tmp_path, monkeypatch):
    """xezim has no compile step: build() writes a JSON record only."""
    monkeypatch.setattr(vendored, "XEZIM_BIN", sys.executable)  # satisfies _simulator_in_path
    runner = vendored.Xezim()
    source = tmp_path / "dut.sv"
    source.write_text("module dut(); endmodule\n", encoding="utf-8")
    inc = tmp_path / "inc"
    inc.mkdir()
    runner.build(
        sources=[source],
        includes=[inc],
        defines={"WIDTH": 8},
        build_dir=tmp_path / "build",
        hdl_toplevel="dut",
    )

    assert runner.build_file.name == "xezim_build.json"
    record = json.loads(runner.build_file.read_text(encoding="utf-8"))
    args = record["args"]
    assert ["-I", str(inc)] == args[args.index("-I"):args.index("-I") + 2]
    assert ["-D", "WIDTH=8"] == args[args.index("-D"):args.index("-D") + 2]
    assert str(source) in args
    assert not list((tmp_path / "build").glob("*.o"))


def test_test_command_semantics(vendored, tmp_path, monkeypatch):
    """_test_command() mirrors the hand-written production command."""
    monkeypatch.setattr(vendored, "XEZIM_BIN", sys.executable)  # ctor checks the file
    runner = vendored.Xezim()
    monkeypatch.setattr(vendored, "XEZIM_BIN", "/opt/xezim/bin/xezim")
    source = tmp_path / "dut.sv"
    source.write_text("module dut(); endmodule\n", encoding="utf-8")
    runner.build(sources=[source], build_dir=tmp_path / "build", hdl_toplevel="dut")
    runner.sim_hdl_toplevel = "dut"  # normally set by Runner.test()
    runner.env = {}
    runner.elab_args = []
    runner.test_args = []
    runner.plusargs = ["+UVM_TESTNAME=base_test"]
    runner.pre_cmd = None
    runner.timescale = None
    runner.parameters = {}
    runner.waves = False
    runner.gui = False

    cmd = runner._test_command()[0]
    assert cmd[0] == "/opt/xezim/bin/xezim"
    assert cmd[1] == "--sv2017"
    assert cmd[2] == "--vpi-lib"
    assert cmd[3].endswith("libcocotbvpi_vcs.so")
    assert str(source) in cmd
    assert cmd[cmd.index("-s") + 1] == "dut"
    assert cmd[-1] == "+UVM_TESTNAME=base_test"
    # Only one VPI library; every other client would be loaded as a DPI lib.
    assert cmd.count("--vpi-lib") == 1
    assert runner.env["LD_LIBRARY_PATH"].startswith(str(cocotb_config.libs_dir))


def test_register_is_idempotent_and_preserves_stock_runner():
    """register() wraps get_runner once and keeps non-xezim simulators working."""
    code = """
import importlib.util, json, sys
import cocotb_tools.runner as r
stock = r.get_runner
def load(name):
    spec = importlib.util.spec_from_file_location(name, sys.argv[1])
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod
m1 = load("vendored_one")
first = r.get_runner
m2 = load("vendored_two")
second = r.get_runner
report = {
    "registered": r.SUPPORTED_RUNNERS.get("xezim") is m2.Xezim,
    "wrapped": bool(getattr(second, "_xezim_wrapped", False)),
    "not_stacked": first is second,
    "xezim_runner": type(second("xezim")).__name__ == "Xezim",
    "stock_runner": isinstance(second("verilator"), type(stock("verilator"))),
}
print(json.dumps(report))
"""
    proc = subprocess.run(
        [sys.executable, "-c", code, str(VENDORED)],
        capture_output=True,
        text=True,
        check=False,
        env={**os.environ, "XEZIM_BIN": sys.executable},
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert all(json.loads(proc.stdout).values()), proc.stdout


def test_production_path_never_imports_vendored_runner():
    """Guard the architecture boundary: sim_runner hand-writes the command."""
    source = (HERE.parent / "base_test" / "sim_runner.py").read_text(encoding="utf-8")
    assert "xezim_runner" not in source
    assert "get_runner(" not in source
