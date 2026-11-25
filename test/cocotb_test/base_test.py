"""Simulator-side cocotb regression, replayed by pytest after the run.

This module is imported by cocotb (``COCOTB_TEST_MODULES=base_test``) inside
the simulator, never by pytest: conftest.py ignores it. ``main()`` is reached
from the UVM test's ``main_phase`` through ``py_task``/``UVM_PY_FUNC``; it runs
the svuvm API smoke checks and starts the cocotb regression. ``test_main()`` is
the cocotb test that those calls schedule, and it writes the result JSON that
test_cocotb.py replays.

The JSON protocol is shared with test/base_test: both modules use
bt_common.write_results(), loaded from test/base_test/bt_common.py by path so
that no extra PYTHONPATH entry (which could shadow this ``base_test`` module)
is needed.
"""

import importlib.util
import sys
from pathlib import Path

import cocotb
import cocotb.regression  # noqa: F401 - 2.1 registers the submodule lazily
from cocotb.triggers import Timer

from svuvm import _svuvm as svuvm


# Reuse the base_test result collector verbatim. Loading it by explicit path
# keeps ``import base_test`` resolving to this file inside the simulator.
_BT_COMMON_PATH = Path(__file__).resolve().parent.parent / "base_test" / "bt_common.py"
_BT_COMMON_SPEC = importlib.util.spec_from_file_location("cocotb_bt_common", _BT_COMMON_PATH)
bt_common = importlib.util.module_from_spec(_BT_COMMON_SPEC)
sys.modules[_BT_COMMON_SPEC.name] = bt_common
_BT_COMMON_SPEC.loader.exec_module(bt_common)

# Static list: conftest.py parses this with ast to parametrize the replay
# tests without importing this simulator-only module.
CASES = [
    "factory_override",
    "uvm_hdl",
    "uvm_report",
    "config_db",
    "vpi_io",
    "vpi_info",
    "vpi_handle",
    "dpi_time",
    "vpi_callback",
    "cocotb_bridge",
    "cocotb_test_main",
]


def cb_test(data):
    """VPI callback used by the ``vpi_callback`` case."""
    print("hello cb")
    return 1


def build():
    """Build a small UVM component tree (kept for interactive debugging)."""
    svuvm.print_factory()
    svuvm.print_topology()
    svuvm.debug_factory_create("base_env", "uvm_test_top")
    for i in range(3):
        svuvm.create_component_by_name("base_env", "uvm_test_top", f"m_env_{i}")
        for j in range(3):
            svuvm.create_component_by_name("base_agent", f"uvm_test_top.m_env_{i}", f"m_agent_{j}")
            svuvm.create_component_by_name("base_driver", f"uvm_test_top.m_env_{i}.m_agent_{j}", "m_driver")
            svuvm.create_component_by_name("base_monitor", f"uvm_test_top.m_env_{i}.m_agent_{j}", "m_monitor")
            svuvm.create_component_by_name("base_sequencer", f"uvm_test_top.m_env_{i}.m_agent_{j}", "m_sequencer")
    svuvm.print_topology()


def connect():
    """Placeholder for the (currently commented-out) TLM connections."""
    for i in range(3):
        for j in range(3):
            # svuvm.tlm_connect(f"uvm_test_top.m_env_{i}.m_agent_{j}.m_driver.seq_item_port", f"uvm_test_top.m_env_{i}.m_agent_{j}.m_sequencer.seq_item_export")
            pass


def _factory_override():
    """Instance and type overrides on the env_cfg object."""
    svuvm.create_object_by_name("env_cfg", "uvm_test_top", "m_env_cfg")
    svuvm.set_factory_inst_override("env_cfg", "random_env_cfg", "uvm_test_top.m_env_cfg")
    svuvm.create_object_by_name("env_cfg", "uvm_test_top", "m_random_env_cfg")
    svuvm.set_factory_type_override("env_cfg", "direct_env_cfg", 1)
    svuvm.create_object_by_name("env_cfg", "uvm_test_top", "m_direct_env_cfg")
    svuvm.print_topology()
    svuvm.print_factory()


def _uvm_hdl():
    """Path check plus deposit/force/release/read on dpi_vec_test."""
    value = svuvm.VpiVecVal()
    present = svuvm.uvm_hdl_check_path("top.dpi_vec_test")
    bt_common.check(bool(present), "uvm_hdl_check_path", f"got {present!r}")
    svuvm.uvm_info(f"uvm_hdl_check_path: <top.dpi_vec_test> {present}", svuvm.UVM_LOW)
    svuvm.uvm_hdl_deposit("top.dpi_vec_test", svuvm.VpiVecVal(0xDEADDEAD, 0x0))
    svuvm.uvm_hdl_read("top.dpi_vec_test", value)
    bt_common.check(value.aval == 0xDEADDEAD, "uvm_hdl deposit readback", f"got 0x{value.aval:X}")
    svuvm.uvm_info(f"uvm_hdl_read: <top.dpi_vec_test> 0x{value.aval:X}", svuvm.UVM_LOW)
    svuvm.uvm_hdl_force("top.dpi_vec_test", svuvm.VpiVecVal(0xDEADBEEF, 0x0))
    svuvm.uvm_hdl_read("top.dpi_vec_test", value)
    bt_common.check(value.aval == 0xDEADBEEF, "uvm_hdl force readback", f"got 0x{value.aval:X}")
    svuvm.uvm_info(f"uvm_hdl_read: <top.dpi_vec_test> 0x{value.aval:X}", svuvm.UVM_LOW)
    svuvm.uvm_hdl_release_and_read("top.dpi_vec_test", value)
    svuvm.uvm_info(f"uvm_hdl_release_and_read: <top.dpi_vec_test> 0x{value.aval:X}", svuvm.UVM_LOW)
    svuvm.uvm_hdl_release("top.dpi_vec_test")


def _uvm_report():
    """Emit one info and one warning through the UVM report server."""
    svuvm.uvm_info("UVM_INFO TEST SUCCESS!", svuvm.UVM_MEDIUM)
    svuvm.uvm_warning("UVM_WARNING TEST SUCCESS!")


def _config_db():
    """Round-trip an int and a string through config_db."""
    svuvm.wait_unit(6)
    svuvm.set_config_int("", "", "int_value", 1)
    int_value = svuvm.get_config_int("", "", "int_value")
    svuvm.vpi.vpi_printf(f"int_value: {int_value}\n")
    bt_common.check(int_value == 1, "config_db int round-trip", f"got {int_value!r}")
    svuvm.set_config_string("", "", "string_value", "hello world")
    string_value = svuvm.get_config_string("", "", "string_value")
    svuvm.vpi.vpi_printf(f"string_value: {string_value}\n")
    bt_common.check(string_value == "hello world", "config_db string round-trip", f"got {string_value!r}")


def _vpi_io():
    """MCD open/printf/flush/close and the vpi_printf/vpi_flush pair."""
    f = svuvm.vpi.vpi_mcd_open("test.log")
    svuvm.vpi.vpi_mcd_printf(f, "hello world\n")
    svuvm.vpi.vpi_mcd_flush(f)
    svuvm.vpi.vpi_printf("vpi_printf success\n")
    svuvm.vpi.vpi_flush()
    svuvm.vpi.vpi_mcd_close(f)


def _vpi_info():
    """Handle-by-name traversal and the VPI info objects."""
    obj = svuvm.vpi.vpi_handle_by_name("top")
    obj = svuvm.vpi.vpi_handle_by_name("test_wire", obj)
    error = svuvm.vpi.VpiErrorInfo()
    svuvm.vpi.vpi_printf(f"vpiVpiErrorInfo: {error.level}\n")
    print(obj)
    info = svuvm.vpi.VpiVlogInfo()
    svuvm.vpi.vpi_printf(
        f"argc: {info.argc}, argv: {info.argv}, product: {info.product}, version: {info.version}\n"
    )


def _vpi_handle():
    """Query name/type/size of a VPI handle."""
    obj = svuvm.vpi.vpi_handle_by_name("top.dpi_vec_test")
    name = svuvm.vpi.vpi_get_str(svuvm.vpi.vpiName, obj)
    obj_type = svuvm.vpi.vpi_get(svuvm.vpi.vpiType, obj)
    size = svuvm.vpi.vpi_get(svuvm.vpi.vpiSize, obj)
    value = svuvm.vpi.VpiValue(svuvm.vpi.vpiIntVal, 0)  # value can not read
    bt_common.check(bool(name), "vpi_get_str(vpiName)", f"got {name!r}")
    print(name, obj_type, size, value)


def _dpi_time():
    """Simulator time, time unit and precision via the DPI exports."""
    for label, fn in (
        ("sim time", svuvm.get_sim_time),
        ("timeunit", svuvm.get_time_unit),
        ("precision", svuvm.get_time_precision),
    ):
        result = fn("Vtop")
        bt_common.check(result is not None, f"get_{label.replace(' ', '_')}", f"got {result!r}")
        svuvm.vpi.vpi_printf(f"{label}: {result}\n")


def _vpi_callback():
    """Register a cbNextSimTime callback on dpi_vec_test."""
    obj = svuvm.vpi.vpi_handle_by_name("top.dpi_vec_test")
    time_obj = svuvm.vpi.VpiTime(svuvm.vpi.vpiSimTime, 0, 0, 0)
    svuvm.vpi.vpi_get_time(obj, time_obj)
    a = svuvm.vpi.CbData(svuvm.vpi.cbNextSimTime, cb_test, obj, time_obj, svuvm.vpi.VpiValue(), 0, "")
    print(a)
    svuvm.vpi.vpi_register_cb(a)


def _cocotb_bridge():
    """Touch cocotb from UVM, disable auto-finish, then start the regression."""
    sim_time = cocotb.simulator.get_sim_time()
    bt_common.check(sim_time is not None, "cocotb.simulator.get_sim_time", f"got {sim_time!r}")
    cocotb.log.info("hello cocotb")
    cocotb.top.dpi_vec_test.value = 0xDEADBEEF
    cocotb.log.info(hex(cocotb.top.dpi_vec_test.value.to_unsigned()))
    # Let UVM finish normally; the cocotb regression owns the end of sim now.
    svuvm.set_finish_on_completion(False)
    # cocotb 2.0.x exposes run_regression on cocotb._init; 2.1.0 moved it to
    # cocotb.regression._run_regression. The explicit import at module scope
    # is required because 2.1.0 does not attach 'regression' to cocotb.
    if hasattr(cocotb._init, "run_regression"):
        cocotb._init.run_regression(None)
    else:
        cocotb.regression._run_regression()
    cocotb.top.dpi_vec_test.value = 0xBABABABA
    cocotb.log.info(hex(cocotb.top.dpi_vec_test.value.to_unsigned()))


def main():
    """UVM ``main_phase`` entry point: run every smoke case, then the cocotb test.

    Each group is isolated by bt_common.run_case so one failing API cannot
    hide the rest. The JSON written here is a partial result (test_main is
    scheduled, not completed, when this returns); test_main rewrites it at
    the end with the final case included.
    """
    svuvm.vpi.vpi_printf("*" * 120 + "\n")
    svuvm.vpi.vpi_printf("*        COCOTB BRIDGE TEST STARTED \n")
    svuvm.vpi.vpi_printf("*" * 120 + "\n")

    cases = (
        ("factory_override", _factory_override),
        ("uvm_hdl", _uvm_hdl),
        ("uvm_report", _uvm_report),
        ("config_db", _config_db),
        # No register block is installed in this top, so the old reg-op calls
        # would hit a null reg_operator and raise UVM_FATAL. Real register
        # coverage lives in test/pyral_test and base_test.py instead.
        ("vpi_io", _vpi_io),
        ("vpi_info", _vpi_info),
        ("vpi_handle", _vpi_handle),
        ("dpi_time", _dpi_time),
        ("vpi_callback", _vpi_callback),
        ("cocotb_bridge", _cocotb_bridge),
    )
    for name, fn in cases:
        bt_common.run_case(name, fn)
    bt_common.write_results()


@cocotb.test()
async def test_main(dut):
    """Cocotb-side checks: report server, UVM errors, dpi_vec_test read/write.

    Never let an assertion escape before the JSON is written: pytest decides
    pass/fail from the JSON, so a raising assert with no result file would
    hide every other case.
    """
    try:
        await Timer(100, unit="ns")
        dut.dpi_vec_test.value = 0xDEADBEEF
        await Timer(1, unit="ns")
        observed = int(dut.dpi_vec_test.value.to_unsigned())
        svuvm.print_report_server()
        count = svuvm.get_severity_count(svuvm.UVM_ERROR)
        svuvm.report_summarize()

        def _assertions():
            bt_common.check(count == 0, "UVM_ERROR count", f"got {count}")
            bt_common.check(
                observed == 0xDEADBEEF,
                "cocotb dpi_vec_test readback",
                f"got 0x{observed:X}",
            )

        bt_common.run_case("cocotb_test_main", _assertions)
    except Exception as exc:  # record the failure, then still write the JSON
        def _raise(_exc=exc):
            raise RuntimeError(f"{type(_exc).__name__}: {_exc}") from _exc

        bt_common.run_case("cocotb_test_main", _raise)
    finally:
        bt_common.write_results()
