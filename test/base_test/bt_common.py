"""Shared state and helpers for the split base-test suite.

Only this module owns the counters/lists; test modules import the helper
functions and never mutate (or rebind) the state themselves.
"""

from svuvm import _svuvm as svuvm


_CHECKS = 0
_FAILURES = []
_SKIPS = []
# Per-block outcome, consumed by test_base_test.py through SVUVM_RESULT_JSON.
_CASE_RESULTS = []

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


def run_case(name, fn):
    """Isolate each block: one failure must not hide the rest of the checks."""
    global _CHECKS
    banner(name)
    _CHECKS += 1  # the block itself completing without raising
    before = len(_FAILURES)
    checks_before = _CHECKS - 1
    case = {"name": name, "status": "pass", "failures": [], "checks": 0}
    try:
        fn()
    except Exception as exc:
        msg = f"[FAIL] {name} raised {type(exc).__name__}: {exc}"
        svuvm.vpi.vpi_printf(msg + "\n")
        _FAILURES.append(msg)
        case["status"] = "fail"
        case["failures"].append(msg)
        case["checks"] = _CHECKS - checks_before
        _CASE_RESULTS.append(case)
        return
    case["checks"] = _CHECKS - checks_before
    if len(_FAILURES) == before:
        svuvm.vpi.vpi_printf(f"[PASS] {name}\n")
    else:
        case["status"] = "fail"
        case["failures"] = list(_FAILURES[before:])
    _CASE_RESULTS.append(case)


def write_results():
    """Dump the per-block outcome for pytest, atomically and only if asked."""
    import json
    import os

    path = os.environ.get("SVUVM_RESULT_JSON")
    if not path:
        return
    payload = {
        "checks": _CHECKS,
        "skips": len(_SKIPS),
        "failures": list(_FAILURES),
        "cases": _CASE_RESULTS,
    }
    tmp = f"{path}.tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2)
    os.replace(tmp, path)


def finalize():
    # Guard against a vacuous pass: too few executed assertions means the
    # suite largely skipped/returned early, which must not print the marker
    # that the Makefile checks for.
    if _CHECKS < MIN_CHECKS:
        fail("assertion floor",
             f"only {_CHECKS} checks executed, expected >= {MIN_CHECKS}")
        _CASE_RESULTS.append({
            "name": "assertion_floor",
            "status": "fail",
            "failures": list(_FAILURES[-1:]),
            "checks": 0,
        })

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
    write_results()


def hello():
    print("hello world")


def hello1():
    print("hello world1")


def hello2():
    print("hello world2")

