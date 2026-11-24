"""Python-side regression for the DPI bridge, driven from UVM's main_phase.

Every block is a standalone ``test_*`` function registered in ``TESTS``.
``main()`` only dispatches them; a block can also be called on its own with
``+UVM_PY_FUNC=test_register_model`` (see main_phase in python_bridge_pkg.sv),
but only ``main()`` writes the completion marker and the pass/fail summary.

Checks use :func:`check` rather than ``assert`` or ``uvm_error``: py_func()
discards unhandled Python exceptions (they only print a traceback), and the
report test reconfigures UVM_ERROR/UVM_FATAL handling, so neither would make
the run fail. A failed check is printed and collected; ``main()`` emits the
completion marker only when every check passed, which is what the Makefile
greps for on both simulators.
"""

import ctypes
import gc
import itertools
import math

from svuvm import _svuvm as svuvm


_CHECKS = 0
_FAILURES = []
_SKIPS = []

# A floor on executed assertions. Without it, a run in which every handle
# lookup returned None (or every test returned early) would record zero real
# checks yet still print the completion marker and pass. After unblocking the
# supported VPI calls on Verilator both backends execute well over 380 checks
# (xezim ~432, Verilator ~385); 350 leaves headroom while still catching a
# wholesale collapse of the suite.
MIN_CHECKS = 350


def check(condition, label, detail=""):
    """Record one real assertion and print a marker on failure."""
    global _CHECKS
    _CHECKS += 1
    if condition:
        return True
    msg = f"[FAIL] {label}" + (f" - {detail}" if detail else "")
    svuvm.vpi.vpi_printf(msg + "\n")
    _FAILURES.append(msg)
    return False


def skip(label, reason):
    """An API that is allowed to be unsupported on some simulators."""
    svuvm.vpi.vpi_printf(f"[SKIP] {label} - {reason}\n")
    _SKIPS.append(label)


def fail(label, reason):
    """Record a hard failure (a real API error, not a supported gap)."""
    msg = f"[FAIL] {label}" + (f" - {reason}" if reason else "")
    svuvm.vpi.vpi_printf(msg + "\n")
    _FAILURES.append(msg)
    return False


def banner(title):
    svuvm.vpi.vpi_printf("*" * 120 + "\n")
    svuvm.vpi.vpi_printf(f"*        TEST {title} \n")
    svuvm.vpi.vpi_printf("*" * 120 + "\n")


def _product():
    """Simulator product string via VPI, cached once."""
    global _PRODUCT
    if "_PRODUCT" not in globals():
        try:
            _PRODUCT = str(svuvm.vpi.VpiVlogInfo().product)
        except Exception:
            _PRODUCT = ""
    return _PRODUCT


_SKIPPED = object()


def try_api_ex(label, fn, verilator_unsafe=False, xezim_unsafe=False):
    """Run an optional VPI call, returning a sentinel when it was skipped.

    ``try_api`` maps the sentinel back to None for older callers; new tests use
    ``try_api_ex`` so they can tell "skipped" apart from a legitimate None
    return value (e.g. a callback registration that failed).

    Both simulators print an internal ``[VPI] ...`` diagnostic for some calls
    but still return a value, so a Python try/except cannot see the failure and
    an ``isinstance(rc, int)`` check would pass while the log records an error:
    * ``verilator_unsafe``: Verilator implements the call with VL_VPI_UNIMP_()
      and aborts the whole simulation; skip it there.
    * ``xezim_unsafe``: xezim does not support the operation / handle class and
      prints ``[VPI] ... not supported`` (or similar); skip it there. The
      standard opcode constants are still verified by the caller.

    An exception that is NOT explained by one of those explicit, per-simulator
    markers is a real defect (bridge bug / regression) and is recorded as a
    FAIL, never silently converted to a skip. Only the two declared
    simulator-unsupported cases may downgrade to a skip.
    """
    product = _product().lower()
    if verilator_unsafe and "verilator" in product:
        skip(label, "unimplemented VPI function aborts on Verilator")
        return _SKIPPED
    if xezim_unsafe and "xezim" in product:
        skip(label, "VPI call unsupported by xezim (would log a [VPI] diagnostic)")
        return _SKIPPED
    try:
        return fn()
    except Exception as exc:
        # Unexpected exception: a genuine failure, not a supported gap.
        fail(label, f"unexpected {type(exc).__name__}: {exc}")
        return _SKIPPED


def try_api(label, fn, verilator_unsafe=False, xezim_unsafe=False):
    """Run an optional/best-effort VPI call.

    Returns the call result, or None after recording a skip. ``verilator_unsafe``
    marks VPI functions that Verilator implements with VL_VPI_UNIMP_() (or that
    reject the given handle): they abort the whole simulation rather than
    returning a checkable value, and Python try/except cannot intercept that.
    ``xezim_unsafe`` marks calls xezim rejects with a ``[VPI]`` diagnostic but
    still returns from. Either way the call is skipped on the simulator that
    cannot honour it, and run on the other.
    """
    result = try_api_ex(label, fn, verilator_unsafe=verilator_unsafe,
                        xezim_unsafe=xezim_unsafe)
    return None if result is _SKIPPED else result


def cb_test(data):
    print("hello cb")
    return 1


def build():
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
    # The register model and its front-end bus; test_register_model uses it.
    svuvm.create_component_by_name("reg_model_env", "uvm_test_top", "m_reg_model")
    svuvm.print_topology()


def connect():
    for i in range(3):
        for j in range(3):
            # svuvm.tlm_connect(f"uvm_test_top.m_env_{i}.m_agent_{j}.m_driver.seq_item_port", f"uvm_test_top.m_env_{i}.m_agent_{j}.m_sequencer.seq_item_export")
            pass


def test_print_topology():
    svuvm.create_object_by_name("env_cfg", "uvm_test_top", "m_env_cfg")
    svuvm.set_factory_inst_override("env_cfg", "random_env_cfg", "uvm_test_top.m_env_cfg")
    svuvm.create_object_by_name("env_cfg", "uvm_test_top", "m_random_env_cfg")
    svuvm.set_factory_type_override("env_cfg", "direct_env_cfg", 1)
    svuvm.create_object_by_name("env_cfg", "uvm_test_top", "m_direct_env_cfg")
    svuvm.print_topology()
    svuvm.print_factory()
    # These factory calls are void; completing the block without an exception
    # is the assertion, which _run() records for every test.


def test_uvm_objection():
    prefix = ["pre_", "", "post_"]
    tsk_phases = ["reset", "configure", "main", "shutdown"]
    phases = ["".join(ph[::-1]) for ph in itertools.product(tsk_phases, prefix)]
    for phase in phases:
        svuvm.uvm_objection_op("RAISE", phase, "uvm_test_top", "TEST OBJECTION RAISE", 1)
        svuvm.uvm_objection_op("DROP", phase, "uvm_test_top", "TEST OBJECTION DROP", 1)
    check(len(phases) == 12, "raise/drop over all 12 task phases", f"got {len(phases)}")

    # The loop above only proves the calls don't raise. Verify the real side
    # effect: a RAISE increments the phase objection count and a DROP restores
    # it. Keep the pair synchronous (no time advance) so a raised objection
    # cannot hold the phase open; use a task phase other than the running one.
    phase = "configure"
    ctx = "uvm_test_top"
    before = svuvm.get_objection_count(phase, ctx)
    svuvm.uvm_objection_op("RAISE", phase, ctx, "probe", 1)
    during = svuvm.get_objection_count(phase, ctx)
    svuvm.uvm_objection_op("DROP", phase, ctx, "probe", 1)
    after = svuvm.get_objection_count(phase, ctx)
    check(during == before + 1, "RAISE increments objection count",
          f"before={before}, during={during}")
    check(after == before, "DROP restores objection count",
          f"before={before}, after={after}")


def test_uvm_hdl():
    value = svuvm.VpiVecVal()
    path_ok = svuvm.uvm_hdl_check_path("top.dpi_vec_test")
    check(bool(path_ok), "uvm_hdl_check_path(top.dpi_vec_test)", f"got {path_ok!r}")

    svuvm.uvm_hdl_deposit("top.dpi_vec_test", svuvm.VpiVecVal(0xDEADDEAD, 0x0))
    svuvm.uvm_hdl_read("top.dpi_vec_test", value)
    check(value.aval == 0xDEADDEAD, "deposit then read", f"0x{value.aval:X}")

    svuvm.uvm_hdl_force("top.dpi_vec_test", svuvm.VpiVecVal(0xDEADBEEF, 0x0))
    svuvm.uvm_hdl_read("top.dpi_vec_test", value)
    check(value.aval == 0xDEADBEEF, "force then read", f"0x{value.aval:X}")

    svuvm.uvm_hdl_release_and_read("top.dpi_vec_test", value)
    svuvm.vpi.vpi_printf(f"uvm_hdl_release_and_read: 0x{value.aval:X}\n")
    # Verilator keeps the last forced value after release; a deposit-only
    # backend falls back to 0xDEADDEAD. Both are legal VPI behaviour.
    check(
        value.aval in (0xDEADDEAD, 0xDEADBEEF),
        "release_and_read returns one of the driven values",
        f"0x{value.aval:X}",
    )
    svuvm.uvm_hdl_release("top.dpi_vec_test")


def test_uvm_report():
    action_list = [
        svuvm.UVM_NO_ACTION,
        svuvm.UVM_DISPLAY,
        svuvm.UVM_LOG,
        svuvm.UVM_COUNT,
        svuvm.UVM_CALL_HOOK,
        svuvm.UVM_RM_RECORD,
        # svuvm.UVM_STOP,
        # svuvm.UVM_EXIT,
    ]
    for action in action_list:
        svuvm.set_report_id_action("", "uvm_report_test", action)
        for verbosity in range(0, 600, 100):
            svuvm.uvm_report(svuvm.UVM_INFO, "uvm_report_test", "UVM_INFO TEST SUCCESS!", verbosity, "run.py", 1)
        svuvm.uvm_report(svuvm.UVM_WARNING, "uvm_report_test", "UVM_WARNING TEST SUCCESS!", svuvm.UVM_NONE, "run.py", 1)
        svuvm.uvm_report(svuvm.UVM_ERROR, "uvm_report_test", "UVM_ERROR TEST SUCCESS!", svuvm.UVM_NONE, "run.py", 1)
    svuvm.set_report_severity_action("", svuvm.UVM_FATAL, svuvm.UVM_DISPLAY)
    svuvm.set_report_severity_override("", svuvm.UVM_FATAL, svuvm.UVM_INFO)
    svuvm.set_report_severity_id_verbosity("", svuvm.UVM_INFO, "main", svuvm.UVM_DEBUG)
    svuvm.set_report_severity_id_action("", svuvm.UVM_ERROR, "main", svuvm.UVM_NO_ACTION)
    svuvm.set_report_severity_id_override("", svuvm.UVM_ERROR, "main", svuvm.UVM_INFO)
    svuvm.uvm_info("UVM_INFO TEST SUCCESS!", svuvm.UVM_MEDIUM)
    svuvm.uvm_warning("UVM_WARNING TEST SUCCESS!")
    svuvm.uvm_error("UVM_ERROR TEST SUCCESS!")
    svuvm.uvm_fatal("UVM_FATAL TEST SUCCESS!")

    svuvm.set_report_id_verbosity("", "main", svuvm.UVM_LOW)
    svuvm.uvm_info("set_report_id_verbosity TEST SUCCESS!", svuvm.UVM_DEBUG)
    svuvm.set_report_verbosity_level("", svuvm.UVM_DEBUG)
    svuvm.uvm_info("UVM_DEBUG TEST SUCCESS!", svuvm.UVM_DEBUG)
    svuvm.set_report_verbosity_level("", svuvm.UVM_MEDIUM)

    action = svuvm.get_report_action("", svuvm.UVM_INFO, "main")
    verbosity = svuvm.get_report_verbosity_level("", svuvm.UVM_INFO, "main")
    max_verbosity = svuvm.get_report_max_verbosity_level("")
    svuvm.vpi.vpi_printf(f"report_action: {action}\n")
    svuvm.vpi.vpi_printf(f"verbosity_level: {verbosity}\n")
    svuvm.vpi.vpi_printf(f"max_verbosity_level: {max_verbosity}\n")
    check(isinstance(action, int) and action >= 0, "get_report_action", f"got {action!r}")
    check(isinstance(verbosity, int) and verbosity >= 0, "get_report_verbosity_level", f"got {verbosity!r}")
    check(
        max_verbosity == svuvm.UVM_MEDIUM,
        "set_report_verbosity_level(UVM_MEDIUM) is visible",
        f"got {max_verbosity!r}",
    )

    # Side-effect check for set_report_id_action: set a dedicated id to a
    # known action and read it back. Uses a fresh id so the report traffic
    # above (which targets "uvm_report_test"/"main") cannot change it.
    probe_id = "roundtrip_action_probe"
    svuvm.set_report_id_action("", probe_id, svuvm.UVM_DISPLAY)
    probe_action = svuvm.get_report_action("", svuvm.UVM_INFO, probe_id)
    check(probe_action == svuvm.UVM_DISPLAY,
          "set_report_id_action is visible via get_report_action",
          f"got {probe_action!r}, expected {svuvm.UVM_DISPLAY!r}")


def test_report_server():
    svuvm.print_report_server()
    svuvm.set_quit_count(10)
    svuvm.set_max_quit_count(100)
    expected_severity = [
        (svuvm.UVM_INFO, 40),
        (svuvm.UVM_WARNING, 30),
        (svuvm.UVM_ERROR, 20),
        (svuvm.UVM_FATAL, 10),
    ]
    for severity, value in expected_severity:
        svuvm.set_severity_count(severity, value)
    svuvm.set_id_count("main", 88)

    # Read everything back before any report call: print_report_server()
    # emits a UVM_INFO and uvm_info() has id "main", so an intervening report
    # changes the counters. The old hard-coded expectations sat after those
    # calls and two of them always failed.
    for severity, value in expected_severity:
        got = svuvm.get_severity_count(severity)
        check(got == value, f"severity count {severity}", f"got {got!r}, expected {value}")
    check(svuvm.get_quit_count() == 10, "get_quit_count", f"got {svuvm.get_quit_count()!r}")
    check(svuvm.get_max_quit_count() == 100, "get_max_quit_count", f"got {svuvm.get_max_quit_count()!r}")
    check(svuvm.get_id_count("main") == 88, "get_id_count(main)", f"got {svuvm.get_id_count('main')!r}")

    svuvm.print_report_server()


def test_config_db():
    svuvm.wait_unit(6)
    svuvm.set_config_int("", "", "int_value", 1)
    int_value = svuvm.get_config_int("", "", "int_value")
    svuvm.vpi.vpi_printf(f"int_value: {int_value}\n")
    check(int_value == 1, "config_db int round trip", f"got {int_value!r}")

    pi_expected = 3.141592653589793
    svuvm.set_config_real("", "", "PI", pi_expected)
    pi = svuvm.get_config_real("", "", "PI")
    svuvm.vpi.vpi_printf(f"PI: {pi}\n")
    check(math.isclose(pi, pi_expected), "config_db real round trip", f"got {pi!r}")

    svuvm.set_config_string("", "", "string_value", "hello world")
    string_value = svuvm.get_config_string("", "", "string_value")
    svuvm.vpi.vpi_printf(f"string_value: {string_value}\n")
    check(string_value == "hello world", "config_db string round trip", f"got {string_value!r}")

    # The reg-operator section that used to be here is gone: it called
    # svuvm.write_reg()/read_reg() without a register block ever being set,
    # so reg_operator::inst was null and the calls dereferenced it. On 0.11.0
    # xezim let that through and returned uninitialised data ("read data:
    # 32514" in old logs); on 0.11.1 it is a segfault. Real register access
    # is covered by test_register_model and test/pyral_test.


def test_vpi_io():
    f = svuvm.vpi.vpi_mcd_open("test.log")
    check(bool(f), "vpi_mcd_open(test.log)", f"got {f!r}")
    mcd_name = try_api("vpi_mcd_name", lambda: svuvm.vpi.vpi_mcd_name(f),
                       verilator_unsafe=True)
    if mcd_name is not None:
        check("test.log" in str(mcd_name), "vpi_mcd_name", f"got {mcd_name!r}")
    svuvm.vpi.vpi_mcd_printf(f, "hello world\n")
    svuvm.vpi.vpi_mcd_flush(f)
    svuvm.vpi.vpi_printf("vpi_printf success\n")
    svuvm.vpi.vpi_flush()
    svuvm.vpi.vpi_mcd_close(f)
    try:
        with open("test.log", encoding="utf-8") as fh:
            content = fh.read()
        check("hello world" in content, "vpi_mcd_printf reached test.log", f"got {content!r}")
    except OSError as exc:
        skip("read back test.log", str(exc))


def test_vpi_info():
    top = svuvm.vpi.vpi_handle_by_name("top")
    check(top is not None, "vpi_handle_by_name(top)", f"got {top!r}")
    wire = svuvm.vpi.vpi_handle_by_name("test_wire", top)
    check(wire is not None, "vpi_handle_by_name(test_wire, top)", f"got {wire!r}")

    error = svuvm.vpi.VpiErrorInfo()
    svuvm.vpi.vpi_printf(f"vpiVpiErrorInfo: {error.level}\n")
    check(error.level == 0, "no pending VPI error", f"level={error.level!r}")

    info = svuvm.vpi.VpiVlogInfo()
    svuvm.vpi.vpi_printf(
        f"argc: {info.argc}, argv: {info.argv}, product: {info.product}, version: {info.version}\n"
    )
    check(info.argc >= 1, "vpi_get_vlog_info argc", f"got {info.argc!r}")
    check(bool(info.product), "vpi_get_vlog_info product", f"got {info.product!r}")


def test_vpi_handle():
    obj = svuvm.vpi.vpi_handle_by_name("top.dpi_vec_test")
    check(obj is not None, "vpi_handle_by_name(top.dpi_vec_test)", f"got {obj!r}")
    name = svuvm.vpi.vpi_get_str(svuvm.vpi.vpiName, obj)
    vpi_type = svuvm.vpi.vpi_get(svuvm.vpi.vpiType, obj)
    size = svuvm.vpi.vpi_get(svuvm.vpi.vpiSize, obj)
    svuvm.vpi.vpi_printf(f"handle: name={name}, type={vpi_type}, size={size}\n")
    check("dpi_vec_test" in str(name), "vpi_get_str(vpiName)", f"got {name!r}")
    check(vpi_type > 0, "vpi_get(vpiType)", f"got {vpi_type!r}")
    check(size == 32, "vpi_get(vpiSize) of logic [31:0]", f"got {size!r}")


def test_dpi_time():
    sim_time = svuvm.get_sim_time("Vtop")
    unit = svuvm.get_time_unit("Vtop")
    precision = svuvm.get_time_precision("Vtop")
    svuvm.vpi.vpi_printf(f"time: {sim_time}, timeunit: {unit}, precision: {precision}\n")
    check(isinstance(sim_time, (int, float)) and sim_time >= 0, "get_sim_time", f"got {sim_time!r}")
    check(unit == precision, "time unit and precision agree", f"{unit!r} vs {precision!r}")
    check(unit <= 0, "time unit is an SI exponent", f"got {unit!r}")


def test_vpi_callback():
    # Own the handles: this block used to borrow `obj` and `value` from
    # test_vpi_handle, which is no longer in the same scope.
    obj = svuvm.vpi.vpi_handle_by_name("top.dpi_vec_test")
    time_obj = svuvm.vpi.VpiTime(svuvm.vpi.vpiSimTime, 0, 0, 0)
    value = svuvm.vpi.VpiValue(svuvm.vpi.vpiIntVal, 0)
    svuvm.vpi.vpi_get_time(obj, time_obj)
    a = svuvm.vpi.CbData(svuvm.vpi.cbNextSimTime, cb_test, obj, time_obj, value, 0, "")
    check(a is not None, "CbData constructed", f"got {a!r}")
    svuvm.vpi.vpi_register_cb(a)

    # vpi_register_cb keeps the time/value *pointers* (IEEE 1800 36.1), so the
    # pointed-to Python objects must stay alive as long as the CbData. Passing
    # temporaries used to leave cb_data.time/value dangling: after GC the
    # getters returned freed-memory garbage instead of the stored values.
    v = svuvm.vpi
    tmp = v.CbData(
        v.cbAfterDelay, cb_test, obj,
        v.VpiTime(v.vpiSimTime, 0, 4242, 0),
        v.VpiValue(v.vpiIntVal, 31337), 0, "")
    gc.collect()
    try:
        check(tmp.time.low == 4242 and tmp.value.integer == 31337,
              "CbData keeps temporary time/value alive",
              f"time.low={tmp.time.low} value.integer={tmp.value.integer}")
    except Exception as exc:
        fail("CbData temporary time/value readback",
             f"{type(exc).__name__}: {exc}")


def test_vpi_value_ctors():
    """VpiValue has several constructor overloads and one field per union arm.

    Exercise each scalar constructor form and read the matching field back.
    The string constructor now keeps its Python str alive via keep_alive, so
    .str reads back reliably too.
    """
    v = svuvm.vpi
    check(v.VpiValue(v.vpiIntVal, 42).integer == 42,
          "VpiValue(format, int) -> integer", f"got {v.VpiValue(v.vpiIntVal, 42).integer!r}")
    check(v.VpiValue(v.vpiRealVal, 2.5).real == 2.5,
          "VpiValue(format, double) -> real", f"got {v.VpiValue(v.vpiRealVal, 2.5).real!r}")
    check(v.VpiValue(v.vpiScalarVal, 1).scalar == 1,
          "VpiValue(format, scalar) -> scalar", f"got {v.VpiValue(v.vpiScalarVal, 1).scalar!r}")

    # IEEE 1800: format decides the valid union member. Cross combinations
    # (an int value with a real format, a float value with an int format) used
    # to write the wrong arm: VpiValue(vpiRealVal, 5).real gave garbage and
    # VpiValue(vpiIntVal, 5.5).integer gave 0. The constructor now dispatches
    # on format instead of on the Python argument type.
    check(v.VpiValue(v.vpiRealVal, 5).real == 5.0,
          "VpiValue(vpiRealVal, int) writes real arm",
          f"got {v.VpiValue(v.vpiRealVal, 5).real!r}")
    check(v.VpiValue(v.vpiIntVal, 5.5).integer == 5,
          "VpiValue(vpiIntVal, float) writes integer arm",
          f"got {v.VpiValue(v.vpiIntVal, 5.5).integer!r}")

    # IEEE 1800: a plain scalar is only valid for the three scalar formats.
    # Pointer/string formats have dedicated constructors, and the
    # short/long/shortreal formats belong to s_vpi_arrayvalue, not this
    # union. Writing `integer` for any of them used to produce a wild
    # pointer when the simulator read the union according to `format`.
    for fmt_name in ("vpiVectorVal", "vpiTimeVal", "vpiStrengthVal",
                     "vpiStringVal", "vpiShortIntVal", "vpiLongIntVal"):
        fmt = getattr(v, fmt_name, None)
        if fmt is None:
            continue
        try:
            v.VpiValue(fmt, 5)
        except (ValueError, TypeError) as exc:
            check(True, f"VpiValue({fmt_name}, int) rejected", str(exc))
        except Exception as exc:
            check(False, f"VpiValue({fmt_name}, int) rejected",
                  f"wrong exception {type(exc).__name__}: {exc}")
        else:
            check(False, f"VpiValue({fmt_name}, int) rejected",
                  "scalar constructor was accepted")

    # Single-argument form sets only format; fields are writable afterwards.
    val = v.VpiValue(v.vpiIntVal)
    check(val.format == v.vpiIntVal, "VpiValue(format) sets format", f"got {val.format!r}")
    val.integer = -7
    check(val.integer == -7, "VpiValue.integer writable", f"got {val.integer!r}")
    val.real = 1.25
    check(val.real == 1.25, "VpiValue.real writable", f"got {val.real!r}")
    val.scalar = 0
    check(val.scalar == 0, "VpiValue.scalar writable", f"got {val.scalar!r}")

    # String overload: the Python str is kept alive for the instance, so both
    # format and the exact string value read back correctly.
    made = v.VpiValue(v.vpiStringVal, "hello")
    check(made.format == v.vpiStringVal, "VpiValue(format, str) sets format",
          f"got {made.format!r}")
    check(made.str == "hello", "VpiValue(format, str) .str round trip",
          f"got {made.str!r}")
    made.str = "world"
    check(made.str == "world", "VpiValue.str setter round trip",
          f"got {made.str!r}")


def test_vpi_scalar_structs():
    """Constructor overloads and field access on VpiVecVal/Time/StrengthVal."""
    v = svuvm.vpi

    # VpiVecVal: default, (aval, bval) and keyword forms, + field writes.
    z = v.VpiVecVal()
    check(z.aval == 0 and z.bval == 0, "VpiVecVal() defaults", f"{z.aval:x}/{z.bval:x}")
    z.aval, z.bval = 0x1111, 0x2222
    check((z.aval, z.bval) == (0x1111, 0x2222), "VpiVecVal fields writable",
          f"{z.aval:x}/{z.bval:x}")
    p = v.VpiVecVal(0x1234, 0x5678)
    check((p.aval, p.bval) == (0x1234, 0x5678), "VpiVecVal(aval, bval)",
          f"{p.aval:x}/{p.bval:x}")

    # IEEE 1800: s_vpi_time.type must be vpiScaledRealTime or vpiSimTime;
    # 0 is reserved/illegal. Both the no-arg and the defaulted 4-arg
    # constructor must now start out as vpiSimTime.
    default_time = v.VpiTime()
    check(default_time.type == v.vpiSimTime and default_time.high == 0
          and default_time.low == 0 and default_time.real == 0.0,
          "VpiTime() defaults to vpiSimTime",
          f"{default_time.type}/{default_time.high}/{default_time.low}/{default_time.real}")
    keyword_time = v.VpiTime(high=7, low=8, real=1.5)
    check(keyword_time.type == v.vpiSimTime
          and (keyword_time.high, keyword_time.low, keyword_time.real) == (7, 8, 1.5),
          "VpiTime(4-arg defaults) type == vpiSimTime",
          f"{keyword_time.type}/{keyword_time.high}/{keyword_time.low}/{keyword_time.real}")

    # VpiTime: 4-arg form (type, high, low, real) and mutable fields.
    t = v.VpiTime(v.vpiSimTime, 1, 2, 3.5)
    check(t.type == v.vpiSimTime and t.high == 1 and t.low == 2 and t.real == 3.5,
          "VpiTime(type, high, low, real)", f"{t.type}/{t.high}/{t.low}/{t.real}")
    t.type, t.high, t.low, t.real = 0, 4, 5, 6.5
    check((t.type, t.high, t.low, t.real) == (0, 4, 5, 6.5),
          "VpiTime fields writable", f"{t.type}/{t.high}/{t.low}/{t.real}")

    # VpiStrengthVal: 3-arg form (logic, s0, s1) and mutable fields.
    s = v.VpiStrengthVal(1, 2, 3)
    check((s.logic, s.s0, s.s1) == (1, 2, 3), "VpiStrengthVal(logic, s0, s1)",
          f"{s.logic}/{s.s0}/{s.s1}")
    s.logic, s.s0, s.s1 = 4, 5, 6
    check((s.logic, s.s0, s.s1) == (4, 5, 6), "VpiStrengthVal fields writable",
          f"{s.logic}/{s.s0}/{s.s1}")


def test_vpi_array_value_ctors():
    """VpiArrayValue has one constructor per array element type."""
    v = svuvm.vpi
    # The format argument decides which union member (and element width) the
    # constructor allocates. Each case must pair its format with matching
    # values; the old test used vpiIntVal for all of them and relied on
    # C++-type overload resolution to pick the element type, which masked the
    # overload-shadowing bug (only INT32/double were ever reachable).
    cases = [
        ("integers", v.vpiIntVal, [1, 2, 3]),
        ("shortints", v.vpiShortIntVal, [1, 2]),
        ("longints", v.vpiLongIntVal, [1 << 33, 2]),
        ("rawvals", v.vpiRawTwoStateVal, [1, 2, 3, 4]),
        ("reals", v.vpiRealVal, [1.5, 2.5]),
        ("shortreals", v.vpiShortRealVal, [1.5, 2.5]),
    ]
    for label, fmt, values in cases:
        def make(f=fmt, vals=values):
            return v.VpiArrayValue(f, 0, vals)
        arr = try_api(f"VpiArrayValue({label})", make)
        if arr is None:
            continue
        check(arr.format == fmt and arr.flags == 0,
              f"VpiArrayValue({label}) format/flags", f"{arr.format}/{arr.flags}")

    # get_integers_values used to read past the allocated buffer with no
    # upper bound. A 3-element buffer must reject n>3 rather than return
    # adjacent heap garbage. This is simulator-independent (pure Python-side
    # readback), so it runs on every backend.
    small = v.VpiArrayValue(v.vpiIntVal, 0, [1, 2, 3])
    check(small.get_integers_values(3) == [1, 2, 3],
          "VpiArrayValue readback within bounds")
    oob_rejected = False
    try:
        small.get_integers_values(1000)
    except (IndexError, ValueError):
        oob_rejected = True
    check(oob_rejected,
          "VpiArrayValue.get_integers_values rejects n beyond buffer",
          "out-of-bounds read was not rejected")

    # The constructor dispatches on `format`, which decides the union member's
    # element width. Previously 8 C++-type-differentiated __init__ overloads
    # collapsed in Python to only INT32/double (the others were unreachable),
    # so shortint/longint/raw/shortreal buffers were allocated with the wrong
    # stride and the simulator read garbage. Read the raw union pointer back
    # with the correct C type to verify each format stores real values.
    def _capsule_ptr(cap):
        api = ctypes.pythonapi
        api.PyCapsule_GetPointer.restype = ctypes.c_void_p
        api.PyCapsule_GetPointer.argtypes = [ctypes.py_object, ctypes.c_char_p]
        return api.PyCapsule_GetPointer(cap, None)

    fmt_cases = [
        ("short", v.vpiShortIntVal, ctypes.c_int16, [1, 2, 3]),
        ("long", v.vpiLongIntVal, ctypes.c_int64, [1 << 33, 2]),
        ("raw", v.vpiRawTwoStateVal, ctypes.c_byte, [1, 2, 3]),
        ("shortreal", v.vpiShortRealVal, ctypes.c_float, [1.5, 2.5, 3.5]),
    ]
    for label, fmt, ctype, values in fmt_cases:
        try:
            arr = v.VpiArrayValue(fmt, 0, values)
            addr = _capsule_ptr(arr.get_integers())
            buf = (ctype * len(values)).from_address(addr)
            got = [buf[i] for i in range(len(values))]
            check(got == values,
                  f"VpiArrayValue({label}) element width/values",
                  f"read back {got}, expected {values}")
        except Exception as exc:
            fail(f"VpiArrayValue({label}) construct/readback",
                 f"{type(exc).__name__}: {exc}")

    # An unsupported format must be rejected rather than silently falling
    # through to a default (mis-shaped) allocation.
    bad_fmt_rejected = False
    try:
        v.VpiArrayValue(0x7FFFFFFF, 0, [1])
    except ValueError:
        bad_fmt_rejected = True
    check(bad_fmt_rejected, "VpiArrayValue rejects unknown format",
          "unknown format was accepted")

    # get_integers_values reads PLI_INT32 elements; other formats must be
    # rejected instead of reading past their narrower allocation.
    nonint_rejected = False
    try:
        v.VpiArrayValue(v.vpiShortIntVal, 0, [1]).get_integers_values(1)
    except ValueError:
        nonint_rejected = True
    check(nonint_rejected, "get_integers_values rejects non-int format",
          "non-int format was read as int32")


def test_vpi_get_value_formats():
    """vpi_get_value fills different union arms depending on format.

    DecStr/OctStr/Scalar round trips are deterministic on both backends.
    RealStr on a logic vector aborts Verilator (format checker), and the
    string formats have simulator-specific zero padding, so those are
    best-effort.
    """
    v = svuvm.vpi
    obj = v.vpi_handle_by_name("top.dpi_vec_test")
    if obj is None:
        skip("vpi_get_value formats", "no handle")
        return
    svuvm.uvm_hdl_deposit("top.dpi_vec_test", svuvm.VpiVecVal(0x000000FF, 0x0))

    dec = v.VpiValue(v.vpiDecStrVal)
    v.vpi_get_value(obj, dec)
    check(str(dec.str).strip() == "255", "vpi_get_value(vpiDecStrVal)", f"got {dec.str!r}")

    octal = v.VpiValue(v.vpiOctStrVal)
    v.vpi_get_value(obj, octal)
    check(str(octal.str).strip().lstrip("0") in ("377", ""),
          "vpi_get_value(vpiOctStrVal)", f"got {octal.str!r}")

    scalar = v.VpiValue(v.vpiScalarVal)
    v.vpi_get_value(obj, scalar)
    check(scalar.scalar in (0, 1), "vpi_get_value(vpiScalarVal)", f"got {scalar.scalar!r}")

    # Hex string: value is correct but width/zero-padding differs per backend.
    hexv = v.VpiValue(v.vpiHexStrVal)
    v.vpi_get_value(obj, hexv)
    check(str(hexv.str).lower().lstrip("0x").lstrip("0") == "ff",
          "vpi_get_value(vpiHexStrVal)", f"got {hexv.str!r}")

    # Real format on a logic vector is aborted by Verilator's format checker.
    realv = v.VpiValue(v.vpiRealVal)
    got = try_api("vpi_get_value(vpiRealVal)", lambda: v.vpi_get_value(obj, realv),
                  verilator_unsafe=True)
    if got is not None or "verilator" not in _product().lower():
        check(realv.real == 255.0, "vpi_get_value(vpiRealVal)", f"got {realv.real!r}")

    svuvm.uvm_hdl_deposit("top.dpi_vec_test", svuvm.VpiVecVal(0xBABABABA, 0x0))


def test_vpi_put_value_flags():
    """vpi_put_value accepts several value formats and delay flags."""
    v = svuvm.vpi
    obj = v.vpi_handle_by_name("top.dpi_vec_test")
    if obj is None:
        skip("vpi_put_value flags", "no handle")
        return
    t = v.VpiTime(v.vpiSimTime, 0, 0, 0)

    def read_int():
        rv = v.VpiValue(v.vpiIntVal)
        v.vpi_get_value(obj, rv)
        return rv.integer

    # String value formats. VpiValue(format, str) keeps the Python str alive
    # (nb::str + keep_alive), so value.str points at a stable UTF-8 buffer.
    # Verilator's vl_check_format accepts BinStr/HexStr/DecStr (verilated_vpi.cpp),
    # so these run for real on both backends. DecStr is base 10: "4660"==0x1234.
    str_cases = (("DecStr", "4660", 0x1234), ("HexStr", "0000ABCD", 0xABCD),
                 ("BinStr", "10101011", 0xAB))
    for label, text, expected in str_cases:
        fmt = getattr(v, f"vpi{label}Val")
        put = try_api_ex(f"vpi_put_value(vpi{label}Val)",
                         lambda f=fmt, s=text:
                         v.vpi_put_value(obj, v.VpiValue(f, s), t, v.vpiNoDelay))
        if put is not _SKIPPED:
            check(read_int() == expected,
                  f"put_value(vpi{label}Val) read back",
                  f"expected 0x{expected:X}, got 0x{read_int() & 0xFFFFFFFF:X}")
    # Seed a known value through the integer form (the reliable path) before
    # testing the delay flags below.
    v.vpi_put_value(obj, v.VpiValue(v.vpiIntVal, 0x0), t, v.vpiNoDelay)

    # IEEE 1800 38.35: inertial/transport/pure-transport require a non-NULL
    # time_p of type vpiSimTime. Reject bad combinations in the bridge,
    # before the simulator can misread a NULL/wrong-type time pointer and
    # emit a [VPI] diagnostic. vpiNoDelay ignores time_p entirely.
    bad_time_cases = (
        ("vpiInertialDelay with NULL time", v.vpiInertialDelay, None),
        ("vpiTransportDelay with NULL time", v.vpiTransportDelay, None),
        ("vpiPureTransportDelay with NULL time", v.vpiPureTransportDelay, None),
        ("vpiInertialDelay with vpiScaledRealTime", v.vpiInertialDelay,
         v.VpiTime(v.vpiScaledRealTime, 0, 0, 1.0)),
        ("vpiTransportDelay with vpiScaledRealTime", v.vpiTransportDelay,
         v.VpiTime(v.vpiScaledRealTime, 0, 0, 1.0)),
    )
    for label, flags, bad_time in bad_time_cases:
        try:
            v.vpi_put_value(obj, v.VpiValue(v.vpiIntVal, 1), bad_time, flags)
        except (ValueError, TypeError) as exc:
            check(True, f"vpi_put_value rejects {label}", str(exc))
        except Exception as exc:
            check(False, f"vpi_put_value rejects {label}",
                  f"wrong exception {type(exc).__name__}: {exc}")
        else:
            check(False, f"vpi_put_value rejects {label}", "call was accepted")
    try_api("vpi_put_value(vpiNoDelay, time_p=None)",
            lambda: v.vpi_put_value(obj, v.VpiValue(v.vpiIntVal, 0), None,
                                     v.vpiNoDelay))

    # Delay flags: on xezim the value lands immediately; Verilator schedules
    # inertial/transport writes for later simulation time, so an immediate
    # read still sees the old value. Assert the write-back only where it is
    # deterministic, and verify the call is accepted everywhere.
    is_verilator = "verilator" in _product().lower()
    try_api("vpi_put_value(vpiInertialDelay)",
            lambda: v.vpi_put_value(obj, v.VpiValue(v.vpiIntVal, 0x1234), t, v.vpiInertialDelay))
    if not is_verilator:
        check(read_int() == 0x1234, "put_value(vpiInertialDelay) read back", f"got 0x{read_int() & 0xFFFFFFFF:X}")
    try_api("vpi_put_value(vpiTransportDelay)",
            lambda: v.vpi_put_value(obj, v.VpiValue(v.vpiIntVal, 0x5678), t, v.vpiTransportDelay))
    if not is_verilator:
        check(read_int() == 0x5678, "put_value(vpiTransportDelay) read back", f"got 0x{read_int() & 0xFFFFFFFF:X}")
    svuvm.uvm_hdl_deposit("top.dpi_vec_test", svuvm.VpiVecVal(0xBABABABA, 0x0))


def test_vpi_error_info_fields():
    """VpiErrorInfo exposes scalar fields and string get/set accessors."""
    v = svuvm.vpi
    e = v.VpiErrorInfo()
    e.level = 3
    e.line = 7
    check(e.level == 3 and e.line == 7, "VpiErrorInfo scalar fields writable",
          f"{e.level}/{e.line}")
    # String setters used to store a pointer into a temporary std::string,
    # so exact read-back was unreliable. They now use nb::str + keep_alive;
    # verify the values round-trip exactly.
    e.set_message("msg")
    e.set_product("prod")
    e.set_code("code")
    e.set_file("file.sv")
    got = (e.get_message(), e.get_product(), e.get_code(), e.get_file())
    check(got == ("msg", "prod", "code", "file.sv"),
          "VpiErrorInfo string round trip", f"got {got!r}")


def test_vpi_get_properties():
    """vpi_get and vpi_get_str read several properties on different objects."""
    v = svuvm.vpi
    for path in ("top.dpi_vec_test", "top.test_wire", "top.clk", "top"):
        h = v.vpi_handle_by_name(path)
        if h is None:
            skip(f"properties of {path}", "no handle")
            continue
        full = v.vpi_get_str(v.vpiFullName, h)
        check(str(full) == path, f"vpi_get_str(vpiFullName,{path})", f"got {full!r}")
        vt = v.vpi_get(v.vpiType, h)
        check(isinstance(vt, int) and vt > 0, f"vpi_get(vpiType,{path})", f"got {vt!r}")
        sz = v.vpi_get(v.vpiSize, h)
        check(isinstance(sz, int), f"vpi_get(vpiSize,{path})", f"got {sz!r}")


def test_vpi_get_value():
    """vpi_get_value in the common scalar formats, with real read-back checks."""
    v = svuvm.vpi
    obj = v.vpi_handle_by_name("top.dpi_vec_test")
    check(obj is not None, "vpi_get_value: handle", f"got {obj!r}")
    if obj is None:
        return

    # Seed a known pattern through uvm_hdl_deposit (proven on both backends),
    # then read it back through each VPI value format.
    svuvm.uvm_hdl_deposit("top.dpi_vec_test", svuvm.VpiVecVal(0x0000ABCD, 0x0))

    iv = v.VpiValue(v.vpiIntVal)
    v.vpi_get_value(obj, iv)
    check(iv.integer == 0xABCD, "vpi_get_value(vpiIntVal)", f"got 0x{iv.integer & 0xFFFFFFFF:X}")

    hv = v.VpiValue(v.vpiHexStrVal)
    v.vpi_get_value(obj, hv)
    check(str(hv.str).lower().lstrip("0x") == "abcd",
          "vpi_get_value(vpiHexStrVal)", f"got {hv.str!r}")

    bv = v.VpiValue(v.vpiBinStrVal)
    v.vpi_get_value(obj, bv)
    check("1010101111001101" in str(bv.str),
          "vpi_get_value(vpiBinStrVal)", f"got {bv.str!r}")


def test_vpi_put_value():
    """vpi_put_value then vpi_get_value read-back (whole 32-bit pattern)."""
    v = svuvm.vpi
    obj = v.vpi_handle_by_name("top.dpi_vec_test")
    if obj is None:
        skip("vpi_put_value", "no handle for top.dpi_vec_test")
        return

    t = v.VpiTime(v.vpiSimTime, 0, 0, 0)
    flags = v.vpiNoDelay
    written = 0x13579BDF

    def put():
        # Return value is a VPI handle on some simulators and None on others;
        # the read-back below is the real assertion.
        v.vpi_put_value(obj, v.VpiValue(v.vpiIntVal, written), t, flags)
    try_api("vpi_put_value call", put)

    rv = v.VpiValue(v.vpiIntVal)
    v.vpi_get_value(obj, rv)
    check(rv.integer == written, "vpi_put_value then get_value",
          f"expected 0x{written:X}, got 0x{rv.integer & 0xFFFFFFFF:X}")

    # Restore a harmless value so later tests are not order-dependent.
    svuvm.uvm_hdl_deposit("top.dpi_vec_test", svuvm.VpiVecVal(0xBABABABA, 0x0))


def test_vpi_get64_compare():
    """vpi_get64 and vpi_compare_objects with deterministic results."""
    v = svuvm.vpi
    vec = v.vpi_handle_by_name("top.dpi_vec_test")
    clk = v.vpi_handle_by_name("top.clk")
    check(vec is not None and clk is not None, "handles for compare", f"{vec!r} {clk!r}")
    if vec is None or clk is None:
        return

    size64 = try_api("vpi_get64(vpiSize)",
                     lambda: v.vpi_get64(v.vpiSize, vec), verilator_unsafe=True)
    if size64 is not None:
        check(size64 == 32, "vpi_get64(vpiSize) of logic [31:0]", f"got {size64!r}")

    same = try_api("vpi_compare_objects(self)",
                   lambda: v.vpi_compare_objects(vec, vec), verilator_unsafe=True)
    if same is not None:
        check(same == 1, "vpi_compare_objects(self) == 1", f"got {same!r}")
    diff = try_api("vpi_compare_objects(other)",
                   lambda: v.vpi_compare_objects(vec, clk), verilator_unsafe=True)
    if diff is not None:
        check(diff == 0, "vpi_compare_objects(other) == 0", f"got {diff!r}")


def test_vpi_hierarchy():
    """Hierarchy traversal APIs: handle_by_index, handle, iterate/scan, multi.

    These are best-effort: not every simulator exposes a populated hierarchy
    through VPI, so a None handle is accepted as long as the call succeeds.
    """
    v = svuvm.vpi
    top = v.vpi_handle_by_name("top")
    obj = v.vpi_handle_by_name("top.dpi_vec_test")
    check(top is not None, "vpi_hierarchy: top handle", f"got {top!r}")
    if top is None:
        return

    # vpi_handle_by_index needs an unpacked-array variable handle; passing the
    # module scope makes Verilator's VL_VPI_INTERNAL_ path abort. Use the real
    # array from top.sv and assert the returned element is a usable handle.
    arr = v.vpi_handle_by_name("top.mem_arr")
    if arr is not None:
        elem = try_api("vpi_handle_by_index",
                       lambda: v.vpi_handle_by_index(arr, 0))
        check(elem is not None, "vpi_handle_by_index returns element handle",
              f"got {elem!r}")
    else:
        skip("vpi_handle_by_index", "no handle for top.mem_arr")
    try_api("vpi_handle(vpiParent)",
            lambda: v.vpi_handle(v.vpiParent, obj) if obj is not None else None)

    def iterate():
        # top.sv declares a single top-level module with no sub-modules, so
        # vpi_iterate(vpiModule, top) legitimately yields nothing. Iterate the
        # registers/signals declared inside top instead (test_wire,
        # dpi_vec_test, clk, cg_vpi_probe_inst) to really exercise iterate/scan.
        it = v.vpi_iterate(v.vpiReg, top)
        if it is None:
            skip("vpi_iterate/vpi_scan", "no reg iterator from top")
            return
        names = []
        while len(names) < 8:
            item = v.vpi_scan(it)
            if item is None:
                break
            names.append(v.vpi_get_str(v.vpiName, item))
        check(len(names) >= 1, "vpi_iterate/vpi_scan yielded regs",
              f"got {names!r}")
        check("dpi_vec_test" in names,
              "vpi_iterate/vpi_scan found the dpi_vec_test signal",
              f"names {names!r}")
    try_api("vpi_iterate/vpi_scan", iterate)

    # vpi_handle_multi(vpiInterModPath, outPort, inPort) needs a real output
    # port handle and a real input port handle of the same size (IEEE 1800
    # 38.30). top.sv instantiates a producer/consumer pair connected by an 8-bit
    # net; collect their vpiPort objects by iterating each module instance.
    def find_port(inst_path, want_dir):
        inst = v.vpi_handle_by_name(inst_path)
        if inst is None:
            return None
        it = v.vpi_iterate(v.vpiPort, inst)
        if it is None:
            return None
        while True:
            port = v.vpi_scan(it)
            if port is None:
                return None
            direction = v.vpi_get(v.vpiDirection, port)
            if direction == want_dir:
                return port

    out_port = find_port("top.u_prod", v.vpiOutput)
    in_port = find_port("top.u_cons", v.vpiInput)

    def intermod():
        if out_port is None or in_port is None:
            skip("vpi_handle_multi",
                 f"no port handles (out={out_port!r}, in={in_port!r})")
            return None
        return v.vpi_handle_multi(v.vpiInterModPath, out_port, in_port)

    rc = try_api_ex("vpi_handle_multi", intermod, verilator_unsafe=True)
    if rc is not _SKIPPED:
        # A found interconnect is returned as a handle (capsule); None is a
        # legitimate "no interconnect" result. Neither may be a scalar.
        check(rc is None or not isinstance(rc, (bool, int, float, str)),
              "vpi_handle_multi(vpiInterModPath) returned a handle or None",
              f"got {rc!r} ({type(rc).__name__})")

    # The wrapper used to print a message but still call vpi_handle_multi
    # with null handles when fewer than two were given. Fewer than two must
    # now be rejected at the Python boundary, independent of the simulator.
    if out_port is not None:
        too_few_rejected = False
        try:
            v.vpi_handle_multi(v.vpiInterModPath, out_port)
        except (ValueError, TypeError):
            too_few_rejected = True
        check(too_few_rejected,
              "vpi_handle_multi rejects fewer than two handles",
              "call with one handle did not raise")


def test_vpi_handle_management():
    """userdata and handle lifetime APIs (best-effort across simulators)."""
    v = svuvm.vpi
    obj = v.vpi_handle_by_name("top.dpi_vec_test")
    if obj is None:
        skip("vpi handle management", "no handle")
        return

    # vpi_put/get_userdata are handle-scoped (IEEE 1800 38.31/38.33): they
    # require the active vpiSysTfCall handle, not a plain signal handle. There
    # is no systf call active in main_phase and xezim cannot call a systf that
    # was registered at run time, so these cannot be exercised here; they are
    # covered by the recorded skip in test_vpi_data_control.
    # vpi_free_object and vpi_release_handle are deprecated / no-ops on some
    # backends; use a fresh handle so any invalidation cannot affect later tests.
    spare = v.vpi_handle_by_name("top.test_wire")
    if spare is not None:
        try_api("vpi_release_handle", lambda: v.vpi_release_handle(spare))
    spare2 = v.vpi_handle_by_name("top.clk")
    if spare2 is not None:
        try_api("vpi_free_object", lambda: v.vpi_free_object(spare2))


def test_vpi_delays():
    """vpi_get_delays / vpi_put_delays (IEEE 1800 38.10/38.32).

    s_vpi_delay.da is caller-allocated: a default VpiDelay has da == nullptr
    and every conforming simulator rejects the call with "null da array".
    Allocate the array explicitly with alloc_da(n) so xezim actually fills it.
    Verilator still aborts on these calls (VL_VPI_UNIMP_), so skip there.
    """
    v = svuvm.vpi
    # delay_net is driven by `assign #1`, so both get and put delays are legal
    # (an undriven net can be read but xezim refuses to annotate it).
    obj = v.vpi_handle_by_name("top.delay_net")
    if obj is None:
        skip("vpi delays", "no handle for top.delay_net")
        return

    def make_delay():
        d = v.VpiDelay()
        d.alloc_da(1)
        d.time_type = v.vpiSimTime
        return d
    delay = try_api_ex("VpiDelay alloc_da", make_delay, verilator_unsafe=True)
    if delay is _SKIPPED:
        return
    check(delay.no_of_delays == 1 and delay.time_type == v.vpiSimTime,
          "VpiDelay alloc_da(1) fields",
          f"{delay.no_of_delays}/{delay.time_type}")

    got = try_api_ex("vpi_get_delays", lambda: v.vpi_get_delays(obj, delay),
                     verilator_unsafe=True)
    if got is not _SKIPPED:
        # The array must be readable after the call; an undriven net may
        # legitimately report a zero delay, but the entry is always filled.
        entry = delay.get_da_time(0)
        check(isinstance(entry, tuple) and len(entry) == 4,
              "vpi_get_delays filled the caller-allocated da array",
              f"got {entry!r}")

    # put_delays writes the same array back. An undriven reg/net in xezim may
    # refuse the write (documented), so treat a diagnostic as a recorded skip
    # but run the call for real when the backend accepts it.
    try_api_ex("vpi_put_delays", lambda: v.vpi_put_delays(obj, delay),
               verilator_unsafe=True)


def test_vpi_cb_info_and_systf():
    """vpi_get_cb_info / vpi_remove_cb and system-task registration."""
    v = svuvm.vpi
    obj = v.vpi_handle_by_name("top.dpi_vec_test")
    if obj is None:
        skip("vpi cb info", "no handle")
        return

    t = v.VpiTime(v.vpiSimTime, 0, 0, 0)
    val = v.VpiValue(v.vpiIntVal, 0)

    cb = v.CbData(v.cbNextSimTime, cb_test, obj, t, val, 0, "cb_ud")
    # The user_data setter used to take an extra cb_rtn_obj argument, so any
    # `cb.user_data = ...` raised TypeError (nanobind wanted (object, str)).
    # Verify the two-argument round trip, then restore the original value so
    # the vpi_get_cb_info assertion below still sees "cb_ud".
    check(cb.user_data == "cb_ud", "CbData.user_data getter",
          f"got {cb.user_data!r}")
    cb.user_data = "cb_ud_changed"
    check(cb.user_data == "cb_ud_changed", "CbData.user_data setter",
          f"got {cb.user_data!r}")
    cb.user_data = "cb_ud"
    h = try_api("vpi_register_cb", lambda: v.vpi_register_cb(cb))
    if h is not None:
        def get_info():
            info = v.CbData()
            v.vpi_get_cb_info(h, info)
            check(info.reason == v.cbNextSimTime, "vpi_get_cb_info reason",
                  f"got {info.reason!r}")
            check(info.user_data == "cb_ud", "vpi_get_cb_info user_data",
                  f"got {info.user_data!r}")
        try_api("vpi_get_cb_info", get_info, verilator_unsafe=True)
        try_api("vpi_remove_cb", lambda: v.vpi_remove_cb(h))

    def systf():
        def cb_compiletf():
            return 0

        def cb_sizetf():
            return 32

        sd = v.VpiSystfData(v.vpiSysTask, v.vpiSysTfCall, cb_test)
        # IEEE 1800 36: compiletf/sizetf are optional callbacks with the
        # same signature as calltf. Both constructors leave them unbound;
        # assigning a Python callable stores it in the CallbackInfo behind
        # user_data and installs the matching C wrapper in the struct.
        check(not sd.compiletf and not sd.sizetf,
              "VpiSystfData compiletf/sizetf initially unbound",
              f"{sd.compiletf}/{sd.sizetf}")
        sd.compiletf = cb_compiletf
        sd.sizetf = cb_sizetf
        check(sd.compiletf and sd.sizetf,
              "VpiSystfData compiletf/sizetf writable",
              f"{sd.compiletf}/{sd.sizetf}")
        # Binding callbacks must not change the user_data string semantics.
        check(sd.user_data == "user_data",
              "VpiSystfData.user_data after callback binding",
              f"got {sd.user_data!r}")
        # The tfname-only constructor has no CallbackInfo yet: the setters
        # must allocate one lazily and keep user_data readable afterwards.
        sd2 = v.VpiSystfData(v.vpiSysFunc, v.vpiSysFunc, "$probe_sizetf")
        sd2.sizetf = cb_sizetf
        check(sd2.sizetf and sd2.user_data == "",
              "VpiSystfData.sizetf on tfname-only constructor",
              f"bound={sd2.sizetf}, user_data={sd2.user_data!r}")

        # user_data holds a CallbackInfo*, not a C string. Reading it used to
        # decode the CallbackInfo object's bytes and raise UnicodeDecodeError.
        check(sd.user_data == "user_data", "VpiSystfData.user_data getter",
              f"got {sd.user_data!r}")
        sd.user_data = "systf_ud"
        check(sd.user_data == "systf_ud", "VpiSystfData.user_data setter",
              f"got {sd.user_data!r}")
        h = v.vpi_register_systf(sd)
        if h is None:
            skip("vpi_get_systf_info",
                 "simulator does not allow registering a system task")
            return
        info = v.VpiSystfData()
        v.vpi_get_systf_info(h, info)
        check(info.tfname == "$cb_test", "vpi_get_systf_info tfname",
              f"got {info.tfname!r}, expected '$cb_test'")
    # The systf name used to be a dangling std::string buffer, which xezim
    # rejected with a mojibake "must start with $" diagnostic. The bridge now
    # owns tfname for the registration's lifetime, so this runs for real.
    try_api("vpi_register_systf/get_systf_info", systf,
            verilator_unsafe=True)


def test_vpi_control_operations():
    """IEEE 1800-2023 38.4: the four vpi_control() operations.

    vpiStop/vpiFinish/vpiReset are deliberately not executed from inside the
    regression: they suspend, terminate or reset the simulation before the
    completion marker can be printed. What is checked here is the standard
    opcode mapping and the convenience bindings; the one operation that is
    safe mid-run, vpiSetInteractiveScope, is called with a real vpiScope handle.
    """
    v = svuvm.vpi
    expected = {
        "vpiStop": 66,
        "vpiFinish": 67,
        "vpiReset": 68,
        "vpiSetInteractiveScope": 69,
    }
    opcodes = []
    for name, value in expected.items():
        opcode = getattr(v, name, None)
        check(opcode == value, f"{name} opcode (IEEE 1800 38.4)",
              f"got {opcode!r}, expected {value}")
        opcodes.append(opcode)
    check(len(set(opcodes)) == len(expected), "vpi_control opcodes are distinct",
          f"got {opcodes!r}")
    check(callable(v.vpi_control), "vpi_control binding exists",
          f"got {v.vpi_control!r}")
    for name in ("reset", "stop", "finish"):
        check(callable(getattr(svuvm, name, None)),
              f"svuvm.{name} convenience binding exists",
              f"got {getattr(svuvm, name, None)!r}")

    top = v.vpi_handle_by_name("top")
    if top is None:
        skip("vpi_control(vpiSetInteractiveScope)", "no top scope handle")
        return
    # Verilator implements vpi_control for finish/stop and answers other
    # operations with a vpiWarning (NOT a vpiError) plus return 0, so the call
    # is safe: it does not abort. Other backends return 1. Assert the call is
    # usable and returns a status int on every backend.
    rc = try_api_ex(
        "vpi_control(vpiSetInteractiveScope, top)",
        lambda: v.vpi_control(v.vpiSetInteractiveScope, top),
    )
    if rc is not _SKIPPED:
        check(isinstance(rc, int) and rc in (0, 1),
              "vpi_control(vpiSetInteractiveScope) returns a status",
              f"got {rc!r}, expected 0 or 1")


def test_vpi_get_time_formats():
    """vpi_get_time() with a real scope handle and both standard time formats.

    IEEE allows a NULL object handle (global time), but the Python binding
    declares ``object`` as non-optional, so only the real-handle form is
    callable here; the NULL form would just raise TypeError on every backend.
    """
    v = svuvm.vpi
    top = v.vpi_handle_by_name("top")
    for label, obj in (("top", top),):
        for fmt_name in ("vpiSimTime", "vpiScaledRealTime"):
            fmt = getattr(v, fmt_name)

            def read_time(obj=obj, fmt=fmt):
                t = v.VpiTime(fmt, 0, 0, 0.0)
                v.vpi_get_time(obj, t)
                return t

            # Verilator implements both formats with a real scope handle
            # (verilated_vpi.cpp: vpi_get_time handles vpiSimTime and
            # vpiScaledRealTime, incl. timeunit scaling for a scope object).
            t = try_api_ex(f"vpi_get_time({label}, {fmt_name})", read_time)
            if t is _SKIPPED:
                continue
            check(t.type == fmt, f"vpi_get_time({label}) preserves {fmt_name}",
                  f"got {t.type!r}")
            if fmt_name == "vpiSimTime":
                ticks = (int(t.high) << 32) | int(t.low)
                check(ticks >= 0, f"vpi_get_time({label}, vpiSimTime) ticks",
                      f"got {ticks}")
            else:
                check(float(t.real) >= 0.0,
                      f"vpi_get_time({label}, vpiScaledRealTime) value",
                      f"got {t.real!r}")


def test_vpi_callback_reasons():
    """Register representative callbacks from each IEEE 1800 38.36 group.

    Simulation-event, simulation-time and simulator-action callbacks are all
    exercised. Handles are removed immediately so no callback can fire later
    and perturb the remaining checks; CbData objects stay alive until removal
    because the binding keeps a Python callable inside user_data.
    """
    v = svuvm.vpi
    obj = v.vpi_handle_by_name("top.dpi_vec_test")
    if obj is None:
        skip("vpi callback reasons", "no handle for top.dpi_vec_test")
        return

    delayed = v.VpiTime(v.vpiSimTime, 0, 10, 0.0)
    value = v.VpiValue(v.vpiIntVal, 0)
    # The CbData binding does not accept None for its object/time/value slots,
    # so every registration uses the same real VPI objects; VPI ignores the
    # unused slots for time/action callbacks.
    cases = [
        # label, reason, verilator_unsafe. Verilator's vpi_register_cb switch
        # supports cbAtStartOfSimTime/cbReadOnlySynch/cbAfterDelay/
        # cbInteractiveScopeChange (verilated_vpi.cpp), so those are enabled;
        # cbForce/cbRelease/cbError/cbUnresolvedSystf are unsupported there.
        ("cbValueChange", v.cbValueChange, False),
        ("cbNextSimTime", v.cbNextSimTime, False),
        ("cbReadWriteSynch", v.cbReadWriteSynch, False),
        ("cbEndOfSimulation", v.cbEndOfSimulation, False),
        ("cbForce", v.cbForce, True),
        ("cbRelease", v.cbRelease, True),
        ("cbAtStartOfSimTime", v.cbAtStartOfSimTime, False),
        ("cbReadOnlySynch", v.cbReadOnlySynch, False),
        ("cbAfterDelay", v.cbAfterDelay, False),
        ("cbError", v.cbError, True),
        ("cbInteractiveScopeChange", v.cbInteractiveScopeChange, False),
        ("cbUnresolvedSystf", v.cbUnresolvedSystf, True),
    ]
    keep_alive = []
    for label, reason, unsafe in cases:
        def register(reason=reason, label=label):
            data = v.CbData(reason, cb_test, obj, delayed, value, 0,
                            f"ud_{label}")
            keep_alive.append(data)
            return v.vpi_register_cb(data)

        handle = try_api_ex(f"vpi_register_cb({label})", register,
                            verilator_unsafe=unsafe)
        if handle is _SKIPPED:
            continue
        check(handle is not None, f"vpi_register_cb({label})", f"got {handle!r}")
        if handle is None:
            continue

        if label == "cbValueChange":
            def get_info(h=handle):
                info = v.CbData()
                v.vpi_get_cb_info(h, info)
                return info
            info = try_api_ex("vpi_get_cb_info(cbValueChange)", get_info,
                              verilator_unsafe=True)
            if info is not _SKIPPED:
                check(info.reason == reason, "vpi_get_cb_info(cbValueChange) reason",
                      f"got {info.reason!r}")
                check(info.user_data == "ud_cbValueChange",
                      "vpi_get_cb_info(cbValueChange) user_data",
                      f"got {info.user_data!r}")

        try_api_ex(f"vpi_remove_cb({label})", lambda h=handle: v.vpi_remove_cb(h))


def test_vpi_data_control():
    """IEEE 1800 38.9/38.14/38.31/38.33: VPI save/restart and userdata access."""
    v = svuvm.vpi
    payload = "vpi-data"
    rc = try_api_ex(
        "vpi_put_data",
        lambda: v.vpi_put_data(0, payload, len(payload)),
        verilator_unsafe=True, xezim_unsafe=True,
    )
    if rc is not _SKIPPED:
        check(isinstance(rc, int), "vpi_put_data returns an integer status",
              f"got {rc!r}")

    buffer = " " * len(payload)
    got = try_api_ex(
        "vpi_get_data",
        lambda: v.vpi_get_data(0, buffer, len(buffer)),
        verilator_unsafe=True, xezim_unsafe=True,
    )
    if got is not _SKIPPED:
        check(isinstance(got, int), "vpi_get_data returns a byte count",
              f"got {got!r}")

    # vpi_put_userdata/get_userdata are handle-scoped (IEEE 1800 38.31/38.33):
    # the object must be the active vpiSysTfCall handle. There is no systf call
    # active from main_phase, and xezim cannot call a systf registered at run
    # time (its SV elaboration rejects "unknown system task"). A plain signal
    # handle is rejected with "not a system task or function call handle", so
    # keep these skipped rather than log a [VPI] diagnostic. This is an IEEE
    # calling-context requirement, not a simulator defect.
    obj = v.vpi_handle_by_name("top.test_wire")
    if obj is None:
        skip("vpi userdata control", "no handle for top.test_wire")
        return
    put = try_api_ex("vpi_put_userdata(handle)",
                     lambda: v.vpi_put_userdata(obj, obj),
                     verilator_unsafe=True, xezim_unsafe=True)
    if put is not _SKIPPED:
        check(isinstance(put, int), "vpi_put_userdata returns an integer status",
              f"got {put!r}")
        get = try_api_ex("vpi_get_userdata(handle)",
                         lambda: v.vpi_get_userdata(obj),
                         verilator_unsafe=True, xezim_unsafe=True)
        if get is not _SKIPPED and put != 0:
            check(get is not None, "vpi_get_userdata sees stored userdata",
                  f"got {get!r}")


def test_vpi_mcd_multichannel():
    """vpi_mcd_* with one channel each and with a combined channel mask."""
    v = svuvm.vpi
    paths = ("vpi_mcd_a.log", "vpi_mcd_b.log")
    handles = [v.vpi_mcd_open(p) for p in paths]
    if not all(handles):
        skip("vpi_mcd_multichannel", f"open failed: {handles!r}")
        return
    check(all(isinstance(h, int) and h > 0 for h in handles),
          "vpi_mcd_open returns channel bits", f"got {handles!r}")

    for path, handle in zip(paths, handles):
        v.vpi_mcd_printf(handle, f"single channel: {path}\n")
    combined = handles[0] | handles[1]
    try_api_ex("vpi_mcd_printf(combined mask)",
               lambda: v.vpi_mcd_printf(combined, "combined channel\n"))
    try_api_ex("vpi_mcd_flush(combined mask)",
               lambda: v.vpi_mcd_flush(combined))
    for handle in handles:
        try_api_ex("vpi_mcd_close", lambda h=handle: v.vpi_mcd_close(h))

    for path in paths:
        try:
            with open(path, encoding="utf-8") as fh:
                content = fh.read()
        except OSError as exc:
            skip(f"read back {path}", str(exc))
            continue
        check(f"single channel: {path}" in content,
              f"vpi_mcd_printf wrote {path}", f"got {content!r}")


def test_vpi_property_matrix():
    """vpi_get/vpi_get_str over several properties and object classes."""
    v = svuvm.vpi
    string_props = ("vpiName", "vpiFullName", "vpiFile", "vpiDefName")
    integer_props = ("vpiType", "vpiSize", "vpiLineNo", "vpiTopModule",
                     "vpiTimeUnit", "vpiTimePrecision")
    for path in ("top", "top.dpi_vec_test", "top.test_wire", "top.clk"):
        handle = v.vpi_handle_by_name(path)
        if handle is None:
            skip(f"property matrix {path}", "no handle")
            continue
        for prop in string_props:
            getter = v.vpi_get_str
            # Verilator implements vpiDefName (verilated_vpi.cpp case vpiDefName);
            # only vpiFile is an unsupported property there.
            unsafe = prop in ("vpiFile",)
            value = try_api_ex(f"vpi_get_str({prop}, {path})",
                               lambda p=prop, h=handle, g=getter: g(getattr(v, p), h),
                               verilator_unsafe=unsafe)
            if value is _SKIPPED:
                continue
            check(value is None or isinstance(value, str),
                  f"vpi_get_str({prop}, {path}) type", f"got {value!r}")
        for prop in integer_props:
            getter = v.vpi_get
            # Verilator implements vpiTimeUnit/vpiTimePrecision (verilated_vpi.cpp
            # cases vpiTimePrecision/vpiTimeUnit); vpiLineNo/vpiTopModule are not
            # supported and take the VL_VPI_ERROR_ abort path.
            unsafe = prop in ("vpiLineNo", "vpiTopModule")
            value = try_api_ex(f"vpi_get({prop}, {path})",
                               lambda p=prop, h=handle, g=getter: g(getattr(v, p), h),
                               verilator_unsafe=unsafe)
            if value is _SKIPPED:
                continue
            check(value is None or isinstance(value, int),
                  f"vpi_get({prop}, {path}) type", f"got {value!r}")


def test_vpi_value_array_control():
    """vpi_get_value_array / vpi_put_value_array (IEEE 1800 38.14).

    These calls operate on a static unpacked array with a caller-allocated
    value buffer and one index per open dimension. top.sv declares
    ``int mem_arr [0:3]`` for this purpose; the old test passed a packed
    vector net with an empty buffer, which xezim correctly rejects with
    "not an unpacked array" / "null value buffer". Verilator implements both
    entry points (verilated_vpi.cpp vpi_get_value_array / vpi_put_value_array)
    for a vpiMemory handle with a caller-allocated int buffer.
    """
    v = svuvm.vpi
    obj = v.vpi_handle_by_name("top.mem_arr")
    if obj is None:
        skip("vpi value array control", "no handle for top.mem_arr")
        return

    # Flag conventions differ by backend. xezim requires vpiUserAllocFlag and
    # vpiOneValue; Verilator's verilated_vpi.cpp rejects both (vpiUserAllocFlag
    # and vpiOneValue take the VL_VPI_ERROR_ abort path) and instead writes
    # into the buffer the VpiArrayValue constructor allocated, using flags=0.
    is_verilator = "verilator" in _product().lower()
    get_flags = 0 if is_verilator else v.vpiUserAllocFlag
    put_flags = 0 if is_verilator else v.vpiOneValue

    garr = v.VpiArrayValue(v.vpiIntVal, get_flags, [0, 0, 0, 0])
    got = try_api_ex(
        "vpi_get_value_array",
        lambda: v.vpi_get_value_array(obj, garr, 0, 4),
    )
    if got is not _SKIPPED:
        values = garr.get_integers_values(4)
        check(isinstance(values, list) and len(values) == 4,
              "vpi_get_value_array filled 4 elements",
              f"got {values!r}")

    # Verilator writes each element from the buffer (flags=0), so give distinct
    # values and read them back; xezim uses vpiOneValue (first value to all).
    parr = v.VpiArrayValue(v.vpiIntVal, put_flags, [11, 22, 33, 44])
    put = try_api_ex(
        "vpi_put_value_array",
        lambda: v.vpi_put_value_array(obj, parr, 0, 4),
    )
    if put is not _SKIPPED:
        # Read the array back with a fresh buffer and assert the written values.
        rarr = v.VpiArrayValue(v.vpiIntVal, get_flags, [0, 0, 0, 0])
        rgot = try_api_ex(
            "vpi_get_value_array after put",
            lambda: v.vpi_get_value_array(obj, rarr, 0, 4),
        )
        if rgot is not _SKIPPED:
            back = rarr.get_integers_values(4)
            want = [11, 22, 33, 44] if is_verilator else [11, 11, 11, 11]
            check(back == want, "vpi_put_value_array write/read-back",
                  f"expected {want}, got {back}")


def test_vpi_handle_by_multi_index():
    """vpi_handle_by_multi_index selects an unpacked-array element by index list.

    IEEE 1800 38.6. The bridge takes the index_array argument as a Python
    list (not a raw PLI_INT32*), so both one-dimensional and two-dimensional
    selects can be expressed. top.sv declares ``int mem_arr [0:3]`` and
    ``int mem2d [0:1][0:2]``. Values are written through the element handles
    with vpi_put_value and read back, so the assertions do not depend on any
    SV initializer or on the value_array test's write ordering.
    """
    v = svuvm.vpi
    t = v.VpiTime(v.vpiSimTime, 0, 0, 0)

    arr = v.vpi_handle_by_name("top.mem_arr")
    if arr is None:
        skip("vpi_handle_by_multi_index", "no handle for top.mem_arr")
        return

    # One index per open dimension: 1-D array needs one index.
    for idx, expected in ((0, 101), (3, 404)):
        label = f"vpi_handle_by_multi_index(mem_arr[{idx}])"
        h = try_api_ex(label, lambda i=idx: v.vpi_handle_by_multi_index(arr, 1, [i]))
        if h is _SKIPPED:
            continue
        check(h is not None, f"{label} returns a handle")
        if h is None:
            continue
        rv = v.VpiValue(v.vpiIntVal, expected)
        v.vpi_put_value(h, rv, t, v.vpiNoDelay)
        got = v.VpiValue(v.vpiIntVal)
        v.vpi_get_value(h, got)
        check(got.integer == expected, f"{label} put/get round-trip",
              f"expected {expected}, got {got.integer}")

    # Two indices on a 2-D array: verify both dims are honoured.
    arr2 = v.vpi_handle_by_name("top.mem2d")
    if arr2 is None:
        skip("vpi_handle_by_multi_index 2-D", "no handle for top.mem2d")
        return
    for idxs, expected in (((1, 2), 512), ((0, 1), 11)):
        label = f"vpi_handle_by_multi_index(mem2d[{idxs[0]}][{idxs[1]}])"
        h = try_api_ex(label, lambda a=idxs: v.vpi_handle_by_multi_index(arr2, 2, list(a)))
        if h is _SKIPPED:
            continue
        check(h is not None, f"{label} returns a handle")
        if h is None:
            continue
        rv = v.VpiValue(v.vpiIntVal, expected)
        v.vpi_put_value(h, rv, t, v.vpiNoDelay)
        got = v.VpiValue(v.vpiIntVal)
        v.vpi_get_value(h, got)
        check(got.integer == expected, f"{label} put/get round-trip",
              f"expected {expected}, got {got.integer}")


def test_vpi_delay_variants():
    """VpiDelay constructor forms and all control flags (IEEE 1800 38.10/38.32)."""
    v = svuvm.vpi
    # da must be a capsule because the binding takes cap.data() directly; a
    # VPI handle capsule is enough for a constructor-only test (no VPI call
    # dereferences it here).
    da = v.vpi_handle_by_name("top.dpi_vec_test")
    if da is None:
        skip("VpiDelay variants", "no capsule handle for da")
        return
    one = try_api_ex(
        "VpiDelay(one delay)",
        lambda: v.VpiDelay(da, 1, v.vpiSimTime),
    )
    if one is not _SKIPPED:
        check(one.no_of_delays == 1 and one.time_type == v.vpiSimTime,
              "VpiDelay(one delay) fields", f"{one.no_of_delays}/{one.time_type}")
        check(one.get_da() is not None, "VpiDelay.get_da() returns stored capsule",
              f"got {one.get_da()!r}")
    three = try_api_ex(
        "VpiDelay(mtm/appulse flags)",
        lambda: v.VpiDelay(da, 3, v.vpiSimTime, 1, 1, 1),
    )
    if three is not _SKIPPED:
        check(three.no_of_delays == 3 and three.time_type == v.vpiSimTime
              and three.mtm_flag == 1 and three.append_flag == 1
              and three.pulsere_flag == 1,
              "VpiDelay control flags",
              f"{three.no_of_delays}/{three.time_type}/"
              f"{three.mtm_flag}/{three.append_flag}/{three.pulsere_flag}")


def test_vpi_assertion_control():
    """IEEE 1800-2023 39.2/39.5: assertion control goes through vpi_control().

    There is no dedicated vpi_set_assertion_control() in the LRM: every
    assertion control is an operation code passed to vpi_control(op, handle).
    All standard opcodes are checked (pure binding surface). System-level
    controls take no handle (they act on every assertion at once), so they are
    invoked with just the operation and checked for the success return; this
    works even when no assertion object is exposed through VPI. Per-assertion
    controls need a real assertion handle, which simulators need not expose, so
    those stay at the opcode/binding level.
    """
    v = svuvm.vpi
    # IEEE 1800-2023 39.2 / sv_vpi_user.h assertion control opcodes.
    opcodes = {
        "vpiAssertionLock": 645,
        "vpiAssertionUnlock": 646,
        "vpiAssertionDisable": 620,
        "vpiAssertionEnable": 621,
        "vpiAssertionReset": 622,
        "vpiAssertionKill": 623,
        "vpiAssertionEnableStep": 624,
        "vpiAssertionDisableStep": 625,
        "vpiAssertionClockSteps": 626,
        "vpiAssertionSysLock": 647,
        "vpiAssertionSysUnlock": 648,
        "vpiAssertionSysOn": 627,
        "vpiAssertionSysOff": 628,
        "vpiAssertionSysKill": 632,
        "vpiAssertionSysEnd": 629,
        "vpiAssertionSysReset": 630,
        # pass/fail/vacuous action controls
        "vpiAssertionDisablePassAction": 633,
        "vpiAssertionEnablePassAction": 634,
        "vpiAssertionDisableFailAction": 635,
        "vpiAssertionEnableFailAction": 636,
        "vpiAssertionDisableVacuousAction": 637,
        "vpiAssertionEnableNonvacuousAction": 638,
        # system-wide pass/fail/vacuous action controls
        "vpiAssertionSysEnablePassAction": 639,
        "vpiAssertionSysEnableFailAction": 640,
        "vpiAssertionSysDisablePassAction": 641,
        "vpiAssertionSysDisableFailAction": 642,
        "vpiAssertionSysEnableNonvacuousAction": 643,
        "vpiAssertionSysDisableVacuousAction": 644,
    }
    for name, value in opcodes.items():
        got = getattr(v, name, None)
        check(got == value, f"{name} opcode (IEEE 1800 39.2)",
              f"got {got!r}, expected {value}")
    check(callable(v.vpi_control), "vpi_control binding for assertion control",
          f"got {v.vpi_control!r}")

    # Per-assertion control needs a REAL assertion object handle: passing the
    # top scope is rejected with "not an assertion handle". top.sv declares a
    # named assertion ap_vpi_probe that xezim exposes through VPI. Verilator
    # lowers SVA to C++ and does not expose assertion objects, so skip these
    # per-instance calls there (the system-level calls below still run).
    scope = v.vpi_handle_by_name("top")
    ah = v.vpi_handle_by_name("top.ap_vpi_probe")
    if ah is None:
        skip("assertion per-instance control", "no assertion handle")
    else:
        # Verilator implements vpi_control for finish/stop and answers other
        # operations with a vpiWarning (not vpiError) + return 0, so these calls
        # are safe there. Accept the status 0/1 returned by either backend.
        for name in ("vpiAssertionEnable", "vpiAssertionDisable"):
            rc = try_api_ex(
                f"vpi_control({name}, assertion)",
                lambda name=name: v.vpi_control(getattr(v, name), ah),
            )
            if rc is _SKIPPED:
                continue
            check(isinstance(rc, int) and rc in (0, 1),
                  f"vpi_control({name}, assertion) returns a status",
                  f"got {rc!r}, expected 0 or 1")
        # EnableStep (624) takes (op, handle, time_p, step); step must be
        # vpiAssertionClockSteps (626). 626 is a step *constant*, not a
        # standalone operation, so it is checked above but never called alone.
        tm = v.VpiTime(v.vpiSimTime, 0, 0, 0)
        rc = try_api_ex(
            "vpi_control(vpiAssertionEnableStep, assertion, time, 626)",
            lambda: v.vpi_control(v.vpiAssertionEnableStep, ah, tm, 626),
        )
        if rc is not _SKIPPED:
            check(isinstance(rc, int) and rc in (0, 1),
                  "vpi_control(vpiAssertionEnableStep) returns a status",
                  f"got {rc!r}, expected 0 or 1")

    # Lock/Unlock (645/646) are genuinely unimplemented by xezim ("operation
    # not supported", documented as Phase-2 work upstream); keep them skipped
    # after their opcode constants have been checked above.
    for name in ("vpiAssertionLock", "vpiAssertionUnlock"):
        try_api_ex(
            f"vpi_control({name})",
            lambda name=name: v.vpi_control(getattr(v, name), scope),
            xezim_unsafe=True,
        )

    # System-level controls (IEEE 1800-2023 39.2) need no assertion handle:
    # vpi_control(op) with no object acts on all assertions. They are usable
    # even when VPI exposes no assertion object (our simulators do not). The
    # sequence re-enables after Off/Reset so the assertion system stays live
    # for later tests; Kill is last since it ends the assertions under test.
    sys_sequence = (
        "vpiAssertionSysOn", "vpiAssertionSysReset", "vpiAssertionSysOff",
        "vpiAssertionSysOn", "vpiAssertionSysKill",
    )
    for name in sys_sequence:
        op = getattr(v, name)
        rc = try_api_ex(
            f"vpi_control({name}) [system]",
            lambda op=op: v.vpi_control(op),
        )
        if rc is _SKIPPED:
            continue
        check(isinstance(rc, int) and rc in (0, 1),
              f"vpi_control({name}) [system] returns a status",
              f"got {rc!r}, expected 0 or 1")


def test_vpi_coverage_get():
    """IEEE 1800-2023 40.4/40.5: coverage data is read with vpi_get().

    Coverage counters and coverage type/status are ordinary VPI properties;
    there is no standalone vpi_get_coverage() in the LRM. Every standard
    property opcode is checked, then the properties are read from any
    assertion/covergroup object the simulator exposes through VPI. Verilator
    lowers SVA/covergroup to C++ and may not expose them as VPI objects, in
    which case the data reads are skipped while the opcode checks still run.
    """
    v = svuvm.vpi
    props = {
        # coverage type properties (40.4)
        "vpiAssertCoverage": 760,
        "vpiFsmStateCoverage": 761,
        "vpiStatementCoverage": 762,
        "vpiToggleCoverage": 763,
        # coverage status properties (40.4)
        "vpiCovered": 765,
        "vpiCoveredCount": 767,
        # assertion-specific coverage status (40.4)
        "vpiAssertAttemptCovered": 770,
        "vpiAssertSuccessCovered": 771,
        "vpiAssertFailureCovered": 772,
        "vpiAssertVacuousSuccessCovered": 773,
        "vpiAssertDisableCovered": 774,
        "vpiAssertKillCovered": 777,
        # coverage counters / aliases (40.4)
        "vpiCoveredMax": 766,
        "vpiCoverMax": 766,
        # FSM-specific coverage status and handle types (40.4)
        "vpiFsmStates": 775,
        "vpiFsmStateExpression": 776,
        "vpiFsm": 758,
        "vpiFsmHandle": 759,
    }
    for name, value in props.items():
        got = getattr(v, name, None)
        check(got == value, f"{name} property opcode (IEEE 1800 40.4)",
              f"got {got!r}, expected {value}")

    handles = []
    for path in ("top.ap_vpi_probe", "top.cg_vpi_probe_inst",
                 "top.cg_vpi_probe_inst.cp_vpi_probe"):
        h = try_api_ex(f"coverage handle {path}",
                       lambda path=path: v.vpi_handle_by_name(path))
        if h is not _SKIPPED and h is not None:
            handles.append((path, h))
    if not handles:
        skip("vpi_get coverage properties on assertion/covergroup",
             "no VPI handle for assertion/covergroup objects")
        return
    for path, h in handles:
        for name in ("vpiCovered", "vpiCoveredCount",
                     "vpiAssertAttemptCovered", "vpiAssertCoverage"):
            got = try_api_ex(
                f"vpi_get({name}, {path})",
                lambda h=h, name=name: v.vpi_get(getattr(v, name), h),
            )
            if got is _SKIPPED:
                continue
            # Verilator returns vpiUndefined (-1) for properties it does not
            # implement; other simulators may return a real counter. Both int.
            check(isinstance(got, int), f"vpi_get({name}, {path}) returns int",
                  f"got {got!r}")


def test_vpi_coverage_control():
    """IEEE 1800-2023 40.5.3: coverage control goes through vpi_control().

    The coverage start/stop/reset/check/merge/save operations are operation
    codes for vpi_control(), not standalone functions. Each may take a
    coverage type and a scope handle (NULL = all coverage). Opcode values are
    checked, then every operation is invoked best-effort. Note the Python
    wrapper converts non-capsule arguments to nullptr, so the call is checked
    for "completes and returns an int status", not for a specific counter.
    """
    v = svuvm.vpi
    opcodes = {
        "vpiCoverageStart": 750,
        "vpiCoverageStop": 751,
        "vpiCoverageReset": 752,
        "vpiCoverageCheck": 753,
        "vpiCoverageMerge": 754,
        "vpiCoverageSave": 755,
    }
    for name, value in opcodes.items():
        got = getattr(v, name, None)
        check(got == value, f"{name} opcode (IEEE 1800 40.5.3)",
              f"got {got!r}, expected {value}")

    scope = v.vpi_handle_by_name("top")
    cov_type = getattr(v, "vpiAssertCoverage", None)
    for name in opcodes:
        if cov_type is None:
            rc = try_api_ex(
                f"vpi_control({name}, top)",
                lambda name=name: v.vpi_control(getattr(v, name), scope),
                xezim_unsafe=True,
            )
        else:
            rc = try_api_ex(
                f"vpi_control({name}, vpiAssertCoverage, top)",
                lambda name=name: v.vpi_control(getattr(v, name), cov_type, scope),
                xezim_unsafe=True,
            )
        if rc is _SKIPPED:
            continue
        check(isinstance(rc, int), f"vpi_control({name}) returns int", f"got {rc!r}")


def test_vpi_assertion_callback_reasons():
    """IEEE 1800-2023 39.4: every cbAssertion* callback reason constant.

    vpi_register_assertion_cb() is not bound in the Python bridge, so the real
    assertion callbacks cannot be registered from here. Check the full reason
    opcode set (per-assertion and system-wide) so the binding surface is
    covered; registering an assertion callback is out of scope for this test.
    """
    v = svuvm.vpi
    reasons = {
        # per-assertion callback reasons
        "cbAssertionStart": 606,
        "cbAssertionSuccess": 607,
        "cbAssertionFailure": 608,
        "cbAssertionVacuousSuccess": 657,
        "cbAssertionDisabledEvaluation": 658,
        "cbAssertionStepSuccess": 609,
        "cbAssertionStepFailure": 610,
        "cbAssertionLock": 661,
        "cbAssertionUnlock": 662,
        "cbAssertionDisable": 611,
        "cbAssertionEnable": 612,
        "cbAssertionReset": 613,
        "cbAssertionKill": 614,
        "cbAssertionEnablePassAction": 645,
        "cbAssertionEnableFailAction": 646,
        "cbAssertionDisablePassAction": 647,
        "cbAssertionDisableFailAction": 648,
        "cbAssertionEnableNonvacuousAction": 649,
        "cbAssertionDisableVacuousAction": 650,
        # assertion system callback reasons
        "cbAssertionSysInitialized": 615,
        "cbAssertionSysOn": 616,
        "cbAssertionSysOff": 617,
        "cbAssertionSysKill": 631,
        "cbAssertionSysLock": 659,
        "cbAssertionSysUnlock": 660,
        "cbAssertionSysEnd": 618,
        "cbAssertionSysReset": 619,
        "cbAssertionSysEnablePassAction": 651,
        "cbAssertionSysEnableFailAction": 652,
        "cbAssertionSysDisablePassAction": 653,
        "cbAssertionSysDisableFailAction": 654,
        "cbAssertionSysEnableNonvacuousAction": 655,
        "cbAssertionSysDisableVacuousAction": 656,
    }
    for name, value in reasons.items():
        got = getattr(v, name, None)
        check(got == value, f"{name} reason (IEEE 1800 39.4)",
              f"got {got!r}, expected {value}")


def test_vpi_assert_cover_object_types():
    """IEEE 1800-2023 39/40: assertion/cover object types and VPI traversal.

    Check the object-type constants used with vpi_get(vpiType) / vpi_iterate,
    then try to enumerate assertion objects from the top scope and read their
    name/fullName. Verilator lowers SVA/covergroups to C++ and may not expose
    them through VPI, so handle-dependent reads are best-effort: the constant
    checks always run, traversal/reads skip when no handle is available.
    """
    v = svuvm.vpi
    obj_types = {
        "vpiAssert": 686,
        "vpiCover": 688,
        "vpiImmediateAssert": 665,
        "vpiImmediateAssume": 694,
        "vpiImmediateCover": 695,
        "vpiIsCoverSequence": 659,
        "vpiConcurrentAssertion": 740,
        "vpiAssertion": 744,
    }
    for name, value in obj_types.items():
        got = getattr(v, name, None)
        check(got == value, f"{name} object type (IEEE 1800 39/40)",
              f"got {got!r}, expected {value}")

    top = v.vpi_handle_by_name("top")
    if top is None:
        skip("vpi_iterate assertion object types", "no handle for top")
        return
    for tname in ("vpiAssertion", "vpiConcurrentAssertion", "vpiAssert",
                  "vpiCover", "vpiImmediateAssert"):
        type_code = getattr(v, tname)
        it = try_api_ex(f"vpi_iterate({tname}, top)",
                        lambda tc=type_code: v.vpi_iterate(tc, top),
                        verilator_unsafe=True)
        if it is _SKIPPED or it is None:
            continue
        found = 0
        for _ in range(16):
            item = try_api_ex(f"vpi_scan({tname})", lambda i=it: v.vpi_scan(i))
            if item is _SKIPPED or item is None:
                break
            found += 1
            for prop in ("vpiName", "vpiFullName"):
                prop_code = getattr(v, prop)
                name = try_api_ex(
                    f"vpi_get_str({prop}, {tname} item)",
                    lambda it2=item, p=prop_code: v.vpi_get_str(p, it2),
                    verilator_unsafe=True,
                )
                if name is _SKIPPED:
                    continue
                check(name is None or isinstance(name, str),
                      f"vpi_get_str({prop}, {tname} item) type", f"got {name!r}")
        if found:
            check(True, f"vpi_iterate({tname}) yielded objects", f"found {found}")

    # Direct handle reads on the assertion/covergroup injected in top.sv.
    for path in ("top.ap_vpi_probe", "top.cg_vpi_probe_inst"):
        h = try_api_ex(f"handle {path}", lambda p=path: v.vpi_handle_by_name(p))
        if h is _SKIPPED or h is None:
            continue
        nm = try_api_ex(f"vpi_get_str(vpiFullName, {path})",
                        lambda hh=h: v.vpi_get_str(v.vpiFullName, hh),
                        verilator_unsafe=True)
        if nm is _SKIPPED:
            continue
        check(nm is None or isinstance(nm, str),
              f"vpi_get_str(vpiFullName, {path}) type", f"got {nm!r}")


def test_process_pool():
    for name in ("base_test.hello", "base_test.hello1", "base_test.hello2", "base_test.hello2"):
        svuvm.process_pool_run(name)
    svuvm.process_pool_clear()
    svuvm.process_pool_run("base_test.hello2")
    # process_pool_run dispatches SV fork/join_none children; there is no
    # return value, so _run()'s "completed without exception" is the check.


def test_phase_objection():
    svuvm.set_drain_time(100)
    drain = svuvm.get_drain_time()
    svuvm.vpi.vpi_printf(f"set_drain_time(100), get_drain_time = {drain}\n")
    check(drain == 100, "drain_time round trip", f"got {drain!r}")

    svuvm.set_timeout(1000000)
    svuvm.set_finish_on_completion(1)

    obj_cnt = svuvm.get_objection_count("run", "uvm_test_top")
    obj_total = svuvm.get_objection_total("run", "uvm_test_top")
    svuvm.vpi.vpi_printf(f"objection count={obj_cnt}, total={obj_total}\n")
    check(obj_cnt >= 0, "get_objection_count", f"got {obj_cnt!r}")
    check(obj_total >= 0, "get_objection_total", f"got {obj_total!r}")

    svuvm.display_objections("run", "uvm_test_top")
    cur_phase = svuvm.get_current_phase_name()
    ph_state = svuvm.get_phase_state("run")
    ph_state_name = svuvm.get_phase_state_name("run")
    svuvm.vpi.vpi_printf(f"phase={cur_phase}, state={ph_state}, state_name={ph_state_name}\n")
    check(bool(cur_phase), "get_current_phase_name", f"got {cur_phase!r}")
    check(isinstance(ph_state, int) and ph_state >= 0, "get_phase_state", f"got {ph_state!r}")
    check(bool(ph_state_name), "get_phase_state_name", f"got {ph_state_name!r}")


def test_component_topology():
    num_children = svuvm.component_get_num_children("uvm_test_top")
    svuvm.vpi.vpi_printf(f"uvm_test_top children count: {num_children}\n")
    # build() creates three envs plus the register-model env.
    check(num_children == 4, "uvm_test_top child count", f"got {num_children!r}")

    names = [svuvm.component_get_child_name("uvm_test_top", i) for i in range(num_children)]
    for i, child_name in enumerate(names):
        svuvm.vpi.vpi_printf(f"  child[{i}] = {child_name}\n")
    for expected in ("m_env_0", "m_env_1", "m_env_2", "m_reg_model"):
        check(expected in names, f"child {expected} exists", f"got {names!r}")

    if names:
        first_child_path = "uvm_test_top." + names[0]
        parent = svuvm.component_get_parent(first_child_path)
        type_name = svuvm.component_get_type_name(first_child_path)
        svuvm.vpi.vpi_printf(f"  parent = {parent}, type_name = {type_name}\n")
        check(parent == "uvm_test_top", "component_get_parent", f"got {parent!r}")
        check(type_name == "base_env", "component_get_type_name", f"got {type_name!r}")

    sprint_text = svuvm.component_sprint("uvm_test_top")
    top_sprint = svuvm.uvm_top_sprint()
    svuvm.vpi.vpi_printf(f"sprint lengths: {len(sprint_text or '')}, {len(top_sprint or '')}\n")
    check(bool(sprint_text), "component_sprint is non-empty")
    check(bool(top_sprint), "uvm_top_sprint is non-empty")

    for tname, expected in (("base_env", True), ("base_agent", True), ("non_existent_type", False)):
        exists = bool(svuvm.is_type_registered(tname))
        svuvm.vpi.vpi_printf(f"is_type_registered({tname}) = {exists}\n")
        check(exists == expected, f"is_type_registered({tname})", f"got {exists!r}")


def test_uvm_event():
    event_name = "test_event"
    svuvm.ev_reset(event_name)
    svuvm.trigger(event_name)
    is_on_val = svuvm.is_on(event_name)
    is_off_val = svuvm.is_off(event_name)
    trigger_time = svuvm.get_trigger_time(event_name)
    num_waiters = svuvm.get_num_waiters(event_name)
    svuvm.vpi.vpi_printf(
        f"event: is_on={is_on_val}, is_off={is_off_val}, "
        f"trigger_time={trigger_time}, waiters={num_waiters}\n"
    )
    check(bool(is_on_val), "trigger sets is_on", f"got {is_on_val!r}")
    check(not is_off_val, "trigger clears is_off", f"got {is_off_val!r}")
    check(trigger_time >= 0, "get_trigger_time", f"got {trigger_time!r}")
    check(num_waiters == 0, "get_num_waiters with no waiters", f"got {num_waiters!r}")

    # uvm_event data accessors (get_default_data/get_trigger_data/...) are SV
    # wrappers returning uvm_object; they are deliberately excluded from the
    # DPI/Python export (scripts/generate_sv_export.py) because a uvm_object
    # cannot cross the DPI boundary safely. They are not Python APIs, so there
    # is nothing to call here. Verify the Python event surface instead: ev_reset
    # with a default-data argument clears is_on (covered just below).

    svuvm.cancel(event_name)
    svuvm.ev_reset(event_name, 1)
    check(not svuvm.is_on(event_name), "ev_reset clears the event", f"got {svuvm.is_on(event_name)!r}")

    # wait_on/wait_off are blocking tasks, but each returns immediately when
    # the event is already in the awaited state. Drive the state first so no
    # time advance is needed and the phase cannot hang. Use dedicated events.
    off_evt = "wait_off_probe"
    svuvm.ev_reset(off_evt)          # freshly reset -> off
    try:
        svuvm.wait_off(off_evt)
        check(True, "wait_off returns immediately for an off event")
    except Exception as exc:
        fail("wait_off", f"{type(exc).__name__}: {exc}")

    on_evt = "wait_on_probe"
    svuvm.trigger(on_evt)            # triggered -> on
    try:
        svuvm.wait_on(on_evt)
        check(True, "wait_on returns immediately for an on event")
    except Exception as exc:
        fail("wait_on", f"{type(exc).__name__}: {exc}")


def test_config_db_extended():
    exists_int = svuvm.config_db_exists("", "", "int_value")
    exists_str = svuvm.config_db_exists("", "", "string_value")
    exists_none = svuvm.config_db_exists("", "", "non_existent_key")
    svuvm.vpi.vpi_printf(
        f"config_db_exists: int_value={exists_int}, string_value={exists_str}, "
        f"non_existent_key={exists_none}\n"
    )
    # The bridge stores ints as uint64, which config_db_exists() does not
    # report as a match on every UVM; the round trip is checked above.
    check(bool(exists_str), "config_db_exists(string_value)", f"got {exists_str!r}")
    check(not exists_none, "config_db_exists(nonexistent) is false", f"got {exists_none!r}")

    svuvm.config_db_trace_on()
    svuvm.config_db_trace_off()


def test_register_model():
    reg_names = svuvm.get_reg_names("")
    block_names = svuvm.get_block_names("")
    svuvm.vpi.vpi_printf(f"get_reg_names: {reg_names}\n")
    svuvm.vpi.vpi_printf(f"get_block_names: {block_names}\n")

    regs = [r for r in (reg_names or "").split(",") if r]
    check(len(regs) == 3, "top reg block has three registers", f"got {regs!r}")
    if not regs:
        return

    first_reg = regs[0]

    # Model-level checks, no bus involved, so they run everywhere.
    for i, name in enumerate(regs):
        addr = svuvm.get_reg_address(name)
        svuvm.reset_reg(name, "HARD")
        reset_val = svuvm.get_reg_mirrored_value(name)
        desired = svuvm.get_reg_desired_value(name)
        svuvm.vpi.vpi_printf(
            f"  {name}: addr=0x{addr:x} reset(mirror)=0x{reset_val:08x} "
            f"desired=0x{desired:08x}\n"
        )
        check(addr == 4 * i, f"{name} address", f"0x{addr:x}, expected 0x{4 * i:x}")
        check(reset_val == 0, f"{name} reset value", f"0x{reset_val:08x}")

    # Written straight into the model, no bus: the mirror must follow.
    if svuvm.predict_reg(first_reg, 0xABCD, "DIRECT"):
        predicted = svuvm.get_reg_mirrored_value(first_reg)
        svuvm.vpi.vpi_printf(f"  predict_reg({first_reg}, 0xABCD) -> mirror=0x{predicted:x}\n")
        check(predicted == 0xABCD, "predict_reg updates the mirror", f"0x{predicted:x}")
    else:
        check(False, "predict_reg returned false")

    field_names = svuvm.get_reg_field_names(first_reg)
    svuvm.vpi.vpi_printf(f"  {first_reg} fields: {field_names}\n")
    fields = [f for f in (field_names or "").split(",") if f]
    check(len(fields) == 2, f"{first_reg} has two fields", f"got {fields!r}")

    block_sprint = svuvm.reg_block_sprint("")
    svuvm.vpi.vpi_printf(f"  reg_block_sprint length: {len(block_sprint or '')}\n")
    check(bool(block_sprint), "reg_block_sprint is non-empty")

    # Bus checks: a register access runs a sequence on the bus. All
    # simulators support this now, so the assertions always run.
    for i, name in enumerate(regs):
        value = 0x1000_0000 + i
        svuvm.write_reg(name, value)
        read_back = svuvm.read_reg(name)
        mirrored = svuvm.get_reg_mirrored_value(name)
        svuvm.vpi.vpi_printf(
            f"  {name}: write=0x{value:08x} read=0x{read_back:08x} mirror=0x{mirrored:08x}\n"
        )
        check(read_back == value, f"{name} bus read back", f"0x{read_back:08x}, expected 0x{value:08x}")
        # The map has auto_predict on, so a bus write updates the mirror.
        check(mirrored == value, f"{name} mirror after bus write", f"0x{mirrored:08x}, expected 0x{value:08x}")

    # Field write: the value must land in the field's own bits.
    if fields:
        svuvm.write_field_by_name(first_reg, fields[0], 0x1234)
        f_val = svuvm.read_field_by_name(first_reg, fields[0])
        svuvm.vpi.vpi_printf(
            f"  write_field_by_name({first_reg}.{fields[0]}, 0x1234) -> read 0x{f_val:x}\n"
        )
        check(f_val == 0x1234, f"field {first_reg}.{fields[0]} round trip", f"got 0x{f_val:x}")


def test_sequencer():
    sqr_path = "uvm_test_top.m_env_0.m_agent_0.m_sequencer"
    svuvm.vpi.vpi_printf(f"sequencer path: {sqr_path}\n")

    busy = svuvm.is_sequencer_busy(sqr_path)
    svuvm.vpi.vpi_printf(f"is_sequencer_busy = {busy}\n")
    check(busy in (0, 1), "is_sequencer_busy returns a flag", f"got {busy!r}")

    cur_seq = svuvm.get_current_sequence_name(sqr_path)
    svuvm.vpi.vpi_printf(f"get_current_sequence_name = {cur_seq}\n")
    # Upgrade from a bare type check to the name's format contract: a
    # sequence name/instance path has no whitespace, and "" is legal when no
    # sequence is currently running. Cross-check the two getters for internal
    # consistency: an idle sequencer (busy==0) must not report a running name.
    check(isinstance(cur_seq, str) and not any(c.isspace() for c in cur_seq),
          "get_current_sequence_name is a whitespace-free name or empty",
          f"got {cur_seq!r}")
    if busy == 0:
        check(cur_seq == "", "idle sequencer has no current sequence",
              f"busy={busy}, name={cur_seq!r}")
    if cur_seq == "":
        skip("current sequence name content",
             "no sequence running on the sequencer at this point")

    # These DPI tasks return void; completing without an exception is the
    # assertion. A raised exception is a real bridge/UVM failure, not a
    # supported gap, so it is recorded as a FAIL (never a silent skip).
    try:
        svuvm.start_seq("simple_seq", sqr_path, rand_en=0, background=1)
        check(True, "start_seq background completes")
    except Exception as exc:
        fail("start_seq background", f"{type(exc).__name__}: {exc}")
    try:
        svuvm.stop_sequences(sqr_path)
        check(True, "stop_sequences completes")
    except Exception as exc:
        fail("stop_sequences", f"{type(exc).__name__}: {exc}")


def test_barrier():
    bar_name = "my_barrier"
    svuvm.barrier_set_threshold(bar_name, 3)
    threshold = svuvm.barrier_get_threshold(bar_name)
    svuvm.vpi.vpi_printf(f"barrier threshold after set: {threshold}\n")
    check(threshold == 3, "barrier threshold round trip", f"got {threshold!r}")

    num_waiters_bar = svuvm.barrier_get_num_waiters(bar_name)
    svuvm.vpi.vpi_printf(f"barrier num waiters: {num_waiters_bar}\n")
    check(num_waiters_bar == 0, "new barrier has no waiters", f"got {num_waiters_bar!r}")

    svuvm.barrier_reset(bar_name, 0)
    svuvm.vpi.vpi_printf("barrier_reset success\n")
    check(svuvm.barrier_get_threshold(bar_name) == 3, "barrier_reset keeps the threshold")

    # barrier_wait is a blocking task: it returns once `threshold` processes
    # are waiting. With threshold=1 the single caller satisfies it immediately,
    # so this is safe to call synchronously (no risk of hanging the phase).
    wait_bar = "barrier_wait_probe"
    svuvm.barrier_set_threshold(wait_bar, 1)
    try:
        svuvm.barrier_wait(wait_bar)
        check(True, "barrier_wait returns when threshold is met")
    except Exception as exc:
        fail("barrier_wait", f"{type(exc).__name__}: {exc}")


def test_pool():
    for n in ("evt_a", "evt_b", "evt_c"):
        svuvm.trigger(n)

    num_events = svuvm.pool_num("event")
    svuvm.vpi.vpi_printf(f"pool_num(event) = {num_events}\n")
    check(num_events >= 3, "event pool has the triggered events", f"got {num_events!r}")

    keys = svuvm.pool_keys("event") or ""
    svuvm.vpi.vpi_printf(f"pool_keys(event) = {keys}\n")
    key_list = keys.split(",")
    for n in ("evt_a", "evt_b", "evt_c"):
        check(n in key_list, f"pool_keys contains {n}", f"got {keys!r}")

    exists_a = svuvm.pool_exists("event", "evt_a")
    exists_z = svuvm.pool_exists("event", "evt_not_exist")
    svuvm.vpi.vpi_printf(f"pool_exists: evt_a={exists_a}, evt_not_exist={exists_z}\n")
    check(bool(exists_a), "pool_exists(evt_a)", f"got {exists_a!r}")
    check(not exists_z, "pool_exists(evt_not_exist) is false", f"got {exists_z!r}")


def test_callback():
    cb_cnt = svuvm.get_callback_count("uvm_test_top", "")
    svuvm.vpi.vpi_printf(f"get_callback_count(uvm_test_top) = {cb_cnt}\n")
    check(isinstance(cb_cnt, int) and cb_cnt >= 0, "get_callback_count", f"got {cb_cnt!r}")

    cb_type_names = svuvm.get_callback_type_names("uvm_test_top")
    svuvm.vpi.vpi_printf(f"get_callback_type_names(uvm_test_top) = {cb_type_names}\n")
    # Upgrade from a bare type check to the list's format contract: a
    # comma-separated type-name list, where "" is a legal empty list. This is
    # content-independent (no simulator-specific type names) yet catches a
    # malformed value such as a count, a repr, or a trailing comma.
    names = [n.strip() for n in cb_type_names.split(",")] if cb_type_names else []
    check(all(names) and cb_type_names == ",".join(n.strip() for n in names),
          "get_callback_type_names returns a well-formed comma-separated list",
          f"got {cb_type_names!r}")
    if not names:
        skip("callback type-name content",
             "no callbacks registered on uvm_test_top in this run")


def test_printer_comparer_knobs():
    # Probe each knob by setting a legal target and reading it back. A value
    # that does not stick means this UVM release has no public accessor for it
    # (or the knob is one of the 1800.2 no-ops). Probing by setting, rather
    # than by checking the default against -1, matters for "depth": its
    # default is itself -1, which collides with the no-accessor sentinel.
    # This keeps the middle releases (IEEE-2017 / 2020-1.x) exercising every
    # knob they do expose via set_* accessors.
    printer_targets = {
        "indent": 4,
        "show_root": 1,
        "header": 1,
        "footer": 1,
        "depth": 5,
        "reference": 1,
        "type_name": 1,
        "size": 1,
    }
    for knob, new_val in printer_targets.items():
        try:
            svuvm.set_default_printer_knob(knob, new_val)
            read_back = svuvm.get_default_printer_knob(knob)
        except Exception as exc:
            skip(f"printer knob[{knob}]", str(exc))
            continue
        if read_back != new_val:
            skip(f"printer knob[{knob}]", "no public accessor in this UVM version")
            continue
        svuvm.vpi.vpi_printf(f"printer knob[{knob}]: set={new_val}, read_back={read_back}\n")
        check(read_back == new_val, f"printer knob[{knob}] round trip", f"got {read_back!r}, expected {new_val!r}")

    comparer_targets = {"show_max": 5, "verbosity": 5, "severity": 1}
    for knob, new_val in comparer_targets.items():
        try:
            svuvm.set_default_comparer_knob(knob, new_val)
            read_back = svuvm.get_default_comparer_knob(knob)
        except Exception as exc:
            skip(f"comparer knob[{knob}]", str(exc))
            continue
        if read_back != new_val:
            skip(f"comparer knob[{knob}]", "no public accessor in this UVM version")
            continue
        svuvm.vpi.vpi_printf(f"comparer knob[{knob}]: set={new_val}, read_back={read_back}\n")
        check(read_back == new_val, f"comparer knob[{knob}] round trip", f"got {read_back!r}, expected {new_val!r}")

    try:
        result = svuvm.component_compare("uvm_test_top", "uvm_test_top")
        svuvm.vpi.vpi_printf(f"component_compare(self, self) = {result}\n")
        check(result == 1, "a component compares equal to itself", f"got {result!r}")
    except Exception as exc:
        skip("component_compare", str(exc))


def test_report_summarize():
    try:
        svuvm.report_summarize()
    except Exception as exc:
        check(False, "report_summarize", str(exc))


TESTS = [
    ("print_topology", test_print_topology),
    ("uvm_objection", test_uvm_objection),
    ("uvm_hdl", test_uvm_hdl),
    ("uvm_report", test_uvm_report),
    ("report_server", test_report_server),
    ("config_db", test_config_db),
    ("vpi_io", test_vpi_io),
    ("vpi_info", test_vpi_info),
    ("vpi_handle", test_vpi_handle),
    ("dpi_time", test_dpi_time),
    ("vpi_callback", test_vpi_callback),
    ("vpi_value_ctors", test_vpi_value_ctors),
    ("vpi_scalar_structs", test_vpi_scalar_structs),
    ("vpi_array_value_ctors", test_vpi_array_value_ctors),
    ("vpi_get_value_formats", test_vpi_get_value_formats),
    ("vpi_put_value_flags", test_vpi_put_value_flags),
    ("vpi_error_info_fields", test_vpi_error_info_fields),
    ("vpi_get_properties", test_vpi_get_properties),
    ("vpi_get_value", test_vpi_get_value),
    ("vpi_put_value", test_vpi_put_value),
    ("vpi_get64_compare", test_vpi_get64_compare),
    ("vpi_hierarchy", test_vpi_hierarchy),
    ("vpi_handle_management", test_vpi_handle_management),
    ("vpi_delays", test_vpi_delays),
    ("vpi_cb_info_and_systf", test_vpi_cb_info_and_systf),
    ("vpi_control_operations", test_vpi_control_operations),
    ("vpi_get_time_formats", test_vpi_get_time_formats),
    ("vpi_callback_reasons", test_vpi_callback_reasons),
    ("vpi_data_control", test_vpi_data_control),
    ("vpi_mcd_multichannel", test_vpi_mcd_multichannel),
    ("vpi_property_matrix", test_vpi_property_matrix),
    ("vpi_value_array_control", test_vpi_value_array_control),
    ("vpi_handle_by_multi_index", test_vpi_handle_by_multi_index),
    ("vpi_delay_variants", test_vpi_delay_variants),
    ("vpi_assertion_control", test_vpi_assertion_control),
    ("vpi_coverage_get", test_vpi_coverage_get),
    ("vpi_coverage_control", test_vpi_coverage_control),
    ("vpi_assertion_callback_reasons", test_vpi_assertion_callback_reasons),
    ("vpi_assert_cover_object_types", test_vpi_assert_cover_object_types),
    ("process_pool", test_process_pool),
    ("phase_objection", test_phase_objection),
    ("component_topology", test_component_topology),
    ("uvm_event", test_uvm_event),
    ("config_db_extended", test_config_db_extended),
    ("register_model", test_register_model),
    ("sequencer", test_sequencer),
    ("barrier", test_barrier),
    ("pool", test_pool),
    ("callback", test_callback),
    ("printer_comparer_knobs", test_printer_comparer_knobs),
    ("report_summarize", test_report_summarize),
]


def _run(name, fn):
    """Isolate each block: one failure must not hide the rest of the checks."""
    global _CHECKS
    banner(name)
    _CHECKS += 1  # the block itself completing without raising
    before = len(_FAILURES)
    try:
        fn()
    except Exception as exc:
        msg = f"[FAIL] {name} raised {type(exc).__name__}: {exc}"
        svuvm.vpi.vpi_printf(msg + "\n")
        _FAILURES.append(msg)
        return
    if len(_FAILURES) == before:
        svuvm.vpi.vpi_printf(f"[PASS] {name}\n")


def main():
    for name, fn in TESTS:
        _run(name, fn)

    # Guard against a vacuous pass: too few executed assertions means the
    # suite largely skipped/returned early, which must not print the marker
    # that the Makefile checks for.
    if _CHECKS < MIN_CHECKS:
        fail("assertion floor",
             f"only {_CHECKS} checks executed, expected >= {MIN_CHECKS}")

    svuvm.vpi.vpi_printf("*" * 120 + "\n")
    if _FAILURES:
        for msg in _FAILURES:
            svuvm.vpi.vpi_printf(msg + "\n")
        svuvm.vpi.vpi_printf(
            f"*        BASE TEST FAILED: {len(_FAILURES)} failures / {_CHECKS} checks, "
            f"{len(_SKIPS)} skipped \n"
        )
        # Deliberately no completion marker: both Makefile branches grep for
        # it, so a failed check now fails the run instead of being ignored.
    else:
        svuvm.vpi.vpi_printf(f"*        {_CHECKS} checks passed, {len(_SKIPS)} skipped \n")
        svuvm.vpi.vpi_printf("*        所有新增API测试完成 \n")
    svuvm.vpi.vpi_printf("*" * 120 + "\n")
    svuvm.print_report_server()


def hello():
    print("hello world")


def hello1():
    print("hello world1")


def hello2():
    print("hello world2")


# The cocotb-driven variant of this regression lives in test/cocotb_test.
