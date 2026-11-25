"""Test blocks extracted verbatim from base_test.py (bt_vpi_behavior)."""

import ctypes
import gc
import weakref

from svuvm import _svuvm as svuvm
from bt_common import _SKIPPED, check, fail, skip, try_api, try_api_ex


def cb_test(data):
    print("hello cb")
    return 1


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

    vpiStop/vpiFinish are deliberately not executed from inside the
    regression: they suspend or terminate the simulation before the
    completion marker can be printed. vpiReset is called with its three
    IEEE-mandated integer arguments: both in-tree backends implement
    vpi_control(vpiReset, ...) as a no-op / warning, so it cannot reset the
    running regression. The one operation that is always safe mid-run,
    vpiSetInteractiveScope, is called with a real vpiScope handle.
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

    # Isolated-only terminal operations: the opcodes are verified above, but
    # executing them from main() would either terminate the simulator
    # (vpiFinish) or suspend it waiting for interactive input (vpiStop), so
    # main() could never print the completion marker the Makefile gates on.
    # A +UVM_PY_FUNC standalone entry is not viable either: probing it with
    # both backends showed no Python call at all (no [PASS]/sys.path output),
    # so a real isolated test needs a separate SV test component and a
    # dedicated make target. Record the boundary explicitly instead of
    # pretending the behavior was exercised.
    skip("vpiStop/vpiFinish terminal behavior",
         "isolated-only: terminates/suspends before completion marker; opcodes verified")

    # IEEE 1800-2023 38.4: vpiReset carries stop_value, reset_value and
    # diagnostics_value. Exercise both the raw VPI call and the convenience
    # binding (with and without explicit arguments) to catch a lost-vararg
    # regression. Verilator accepts the call as a no-op; xezim refuses to
    # reset a running simulation and emits a leading [VPI] diagnostic that the
    # Makefile treats as a hard failure, so skip these calls there.
    for label, fn in (
        ("vpi_control(vpiReset, 1, 2, 3)",
         lambda: v.vpi_control(v.vpiReset, 1, 2, 3)),
        ("svuvm.reset(1, 2, 3)", lambda: svuvm.reset(1, 2, 3)),
        ("svuvm.reset()", lambda: svuvm.reset()),
    ):
        rc = try_api_ex(label, fn, xezim_unsafe=True)
        if rc is not _SKIPPED:
            check(isinstance(rc, int), f"{label} returns a status",
                  f"got {rc!r}")

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
    """vpi_get_time() with a real scope handle and the NULL-object global form.

    IEEE 1800 38.25 allows object=NULL to read the current simulation time
    without scope scaling. The binding used to reject None in its signature;
    it now declares the argument .none() and the wrapper converts None to a
    NULL vpiHandle.
    """
    v = svuvm.vpi
    top = v.vpi_handle_by_name("top")
    for label, obj in (("top", top), ("NULL", None)):
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
        # xezim's vpi_user.h documents cbAtEndOfSimTime, cbNBASynch and
        # cbStartOfSimulation as supported (issue #1190 is about assertion
        # callbacks, not these). Verilator handles cbAtEndOfSimTime and
        # cbStartOfSimulation but has no cbNBASynch case in vpi_register_cb.
        ("cbAtEndOfSimTime", v.cbAtEndOfSimTime, False),
        ("cbNBASynch", v.cbNBASynch, True),
        ("cbStartOfSimulation", v.cbStartOfSimulation, False),
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
    payload = b"vpi-data"
    rc = try_api_ex(
        "vpi_put_data",
        lambda: v.vpi_put_data(0, payload, len(payload)),
        verilator_unsafe=True, xezim_unsafe=True,
    )
    if rc is not _SKIPPED:
        check(isinstance(rc, int), "vpi_put_data returns an integer status",
              f"got {rc!r}")

    buffer = bytearray(len(payload))
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


def test_vpi_delay_variants():
    """VpiDelay constructor forms and all control flags (IEEE 1800 38.10/38.32)."""
    v = svuvm.vpi
    # IEEE 1800: s_vpi_time.type must be vpiSimTime/vpiScaledRealTime; 0 is
    # illegal. The default-constructed VpiDelay used to carry time_type=0.
    default_delay = v.VpiDelay()
    check(default_delay.time_type == v.vpiSimTime,
          "VpiDelay() defaults time_type to vpiSimTime",
          f"got {default_delay.time_type}")
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
    All standard opcodes are checked (pure binding surface). IEEE 1800-2023
    39.5.1 requires a SECOND handle argument for the system-level operations
    too: it is a vpiHandle for a scope, and NULL means the control applies to
    all assertions regardless of scope. Those calls therefore pass a scope
    handle (or None for the all-scopes form) and only assert the status code;
    this works even when no assertion object is exposed through VPI.
    Per-assertion controls (39.5.2, incl. Lock/Unlock 645/646) need a real
    assertion handle, which simulators need not expose, so those are skipped
    when no assertion object is available.
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

    # Lock/Unlock (645/646, IEEE 1800-2023 39.5.2) take a single assertion
    # handle -- the same `ah` used by the per-assertion controls above. xezim
    # reports these operations as unsupported, so keep them skipped there
    # after their opcode constants have been checked.
    if ah is None:
        skip("vpi_control(Lock/Unlock, assertion)", "no assertion handle")
    else:
        for name in ("vpiAssertionLock", "vpiAssertionUnlock"):
            rc = try_api_ex(
                f"vpi_control({name}, assertion)",
                lambda name=name: v.vpi_control(getattr(v, name), ah),
                xezim_unsafe=True,
            )
            if rc is not _SKIPPED:
                check(isinstance(rc, int) and rc in (0, 1),
                      f"vpi_control({name}, assertion) returns a status",
                      f"got {rc!r}, expected 0 or 1")

    # System-level controls (IEEE 1800-2023 39.5.1) DO take a second handle
    # argument: a scope handle, where NULL applies to all assertions. Passing
    # only the opcode made a conforming tool read a garbage va_arg. They are
    # usable even when VPI exposes no assertion object (our simulators do not).
    # The sequence re-enables after Off/Reset so the assertion system stays
    # live for later tests; Kill is last since it ends the assertions.
    sys_sequence = (
        "vpiAssertionSysOn", "vpiAssertionSysReset", "vpiAssertionSysOff",
        "vpiAssertionSysOn", "vpiAssertionSysKill",
    )
    for name in sys_sequence:
        op = getattr(v, name)
        rc = try_api_ex(
            f"vpi_control({name}, scope) [system]",
            lambda op=op: v.vpi_control(op, scope),
        )
        if rc is _SKIPPED:
            continue
        check(isinstance(rc, int) and rc in (0, 1),
              f"vpi_control({name}, scope) [system] returns a status",
              f"got {rc!r}, expected 0 or 1")

    # Explicitly cover the legal NULL-handle form ("all assertions, all
    # scopes") required by IEEE 1800-2023 39.5.1.
    rc = try_api_ex(
        "vpi_control(vpiAssertionSysOn, None) [system, NULL handle]",
        lambda: v.vpi_control(v.vpiAssertionSysOn, None),
    )
    if rc is not _SKIPPED:
        check(isinstance(rc, int) and rc in (0, 1),
              "vpi_control(system, None) returns a status",
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


def _capsule_with_deleter(tag, freed):
    """Build a PyCapsule whose deleter records `tag` in `freed`.

    The CPython PyCapsule destructor receives the capsule object (not the
    payload pointer), so the tag comes from a Python closure. The CFUNCTYPE
    object is returned because the capsule stores only a raw function pointer.
    """
    new_capsule = ctypes.pythonapi.PyCapsule_New
    new_capsule.restype = ctypes.py_object
    new_capsule.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_void_p]
    buffer = (ctypes.c_int * 1)(tag)

    def on_delete(capsule_obj):
        freed.append(tag)

    deleter = ctypes.CFUNCTYPE(None, ctypes.c_void_p)(on_delete)
    cap = new_capsule(ctypes.addressof(buffer), b"base_test",
                      ctypes.cast(deleter, ctypes.c_void_p))
    return cap, (buffer, deleter)


def test_vpi_callbackinfo_lifecycle():
    """Bug#5: CallbackInfo dies with its Python owner (unregistered case).

    A registered callback must outlive its Python wrapper until vpi_remove_cb
    succeeds, so reclamation is asserted only for *unregistered* objects:
    those have no simulator user_data pointer and are safe to free on every
    backend. Registration and removal are exercised for crash-safety only.
    """
    v = svuvm.vpi
    obj = v.vpi_handle_by_name("top.dpi_vec_test")
    if obj is None:
        skip("callback info lifecycle", "no handle for top.dpi_vec_test")
        return

    t = v.VpiTime(v.vpiSimTime, 0, 0, 0)
    val = v.VpiValue(v.vpiIntVal, 0)

    def make_cb_data():
        def target():
            return 1
        wr = weakref.ref(target)
        data = v.CbData(v.cbNextSimTime, target, obj, t, val, 0, "lifecycle")
        return data, wr

    data, wr = make_cb_data()
    check(hasattr(data, "_vpi_callback_info_owner"),
          "CbData carries CallbackInfo capsule",
          f"attrs={list(data.__dict__.keys())}")
    check(wr() is not None, "CbData keeps its callable alive")
    del data
    gc.collect()
    gc.collect()
    check(wr() is None, "unregistered CbData releases callable on GC",
          f"weakref={wr()}")

    def make_systf():
        def target():
            return 0
        wr = weakref.ref(target)
        sd = v.VpiSystfData(v.vpiSysTask, v.vpiSysTfCall, target)
        return sd, wr

    sd, wr = make_systf()
    check(hasattr(sd, "_vpi_callback_info_owner"),
          "VpiSystfData carries CallbackInfo capsule")
    del sd
    gc.collect()
    gc.collect()
    check(wr() is None, "unregistered VpiSystfData releases calltf on GC",
          f"weakref={wr()}")

    # Lazy allocation from setters on a default-constructed object must also
    # install the capsule; otherwise the CallbackInfo (and the callable it
    # holds) would leak on that path.
    def make_lazy():
        def target():
            return 32
        wr = weakref.ref(target)
        sd = v.VpiSystfData()
        sd.user_data = "lazy"
        sd.sizetf = target
        return sd, wr

    sd, wr = make_lazy()
    check(hasattr(sd, "_vpi_callback_info_owner"),
          "VpiSystfData setters attach CallbackInfo capsule")
    check(sd.user_data == "lazy", "lazy user_data survives sizetf setter",
          f"got {sd.user_data!r}")
    del sd
    gc.collect()
    gc.collect()
    check(wr() is None, "lazy CallbackInfo releases callable on GC",
          f"weakref={wr()}")


def test_vpi_userdata_keepalive():
    """Bug#6: a capsule passed to vpi_put_userdata must not be freed early.

    The local control proves the deleter fires when nothing retains the
    capsule. The VPI call is only valid for a system-task-call handle; both
    supported simulators reject userdata on an ordinary signal handle, so the
    registry assertion is recorded as a skip there. The stub-driven probe
    (probe_lifecycle.py) verifies the registry end to end.
    """
    v = svuvm.vpi
    freed = []
    cap, keep = _capsule_with_deleter(7001, freed)
    del cap, keep
    gc.collect()
    check(freed == [7001], "capsule deleter fires without VPI keep-alive",
          f"freed={freed}")

    obj = v.vpi_handle_by_name("top.test_wire")
    if obj is None:
        skip("vpi userdata keepalive", "no handle for top.test_wire")
        return

    freed2 = []
    cap2, keep2 = _capsule_with_deleter(7002, freed2)
    rc = try_api_ex("vpi_put_userdata keepalive",
                    lambda: v.vpi_put_userdata(obj, cap2),
                    verilator_unsafe=True, xezim_unsafe=True)
    if rc is not _SKIPPED:
        local_cap = cap2
        cap2 = None
        del local_cap
        gc.collect()
        gc.collect()
        check(not freed2, "put_userdata retains capsule after Python GC",
              f"freed={freed2}")
        try_api_ex("vpi_release_handle after put_userdata",
                   lambda: v.vpi_release_handle(obj))
    cap2 = None
    del keep2  # drop the (buffer, deleter) guard so the capsule can finalize
    gc.collect()
    check(7002 in freed2, "capsule deleter fires after refs are dropped",
          f"freed2={freed2}")


__all__ = [
    "test_dpi_time",
    "test_vpi_assert_cover_object_types",
    "test_vpi_assertion_callback_reasons",
    "test_vpi_assertion_control",
    "test_vpi_callback",
    "test_vpi_callback_reasons",
    "test_vpi_callbackinfo_lifecycle",
    "test_vpi_cb_info_and_systf",
    "test_vpi_control_operations",
    "test_vpi_coverage_control",
    "test_vpi_coverage_get",
    "test_vpi_data_control",
    "test_vpi_delay_variants",
    "test_vpi_delays",
    "test_vpi_get_time_formats",
    "test_vpi_userdata_keepalive",
]
