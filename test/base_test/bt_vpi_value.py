"""Test blocks extracted verbatim from base_test.py (bt_vpi_value)."""

import ctypes

from svuvm import _svuvm as svuvm
from bt_common import (_SKIPPED, _product, check, fail, skip, try_api,
                       try_api_ex)


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

    # IEEE 1800-2023 38.15: only the format-selected union arm is valid.
    # Constructors now zero the whole struct and .str is guarded by format,
    # so reading a non-string arm (or a mutated format) returns "" instead of
    # dereferencing a wild pointer. A crash here fails the whole run, which
    # is exactly the regression we want to catch.
    for label, value in (("vpiStringVal", v.VpiValue(v.vpiStringVal)),
                         ("vpiIntVal", v.VpiValue(v.vpiIntVal, 5))):
        check(value.str == "", f"VpiValue({label}).str is empty",
              f"got {value.str!r}")
    mutated = v.VpiValue(v.vpiIntVal, 5)
    mutated.format = v.vpiStringVal
    check(mutated.str == "", "VpiValue format mutation .str is empty",
          f"got {mutated.str!r}")

    # P2#9: unified BridgeError hierarchy (kept inside this existing case so
    # the 53-case TESTS table and the AST case collector stay untouched).
    check(issubclass(svuvm.BridgeInvalidArgument, svuvm.BridgeError),
          "BridgeInvalidArgument <: BridgeError")
    check(issubclass(svuvm.BridgeInvalidArgument, ValueError),
          "BridgeInvalidArgument <: ValueError (兼容)")
    check(issubclass(svuvm.BridgeOutOfRange, (svuvm.BridgeError, IndexError)),
          "BridgeOutOfRange 双基类")
    check(issubclass(svuvm.BridgeUnsupported, (svuvm.BridgeError, RuntimeError)),
          "BridgeUnsupported 双基类")
    # Real throw: both the new type and the legacy ValueError must catch it.
    bad_format = getattr(v, "vpiVectorVal", None)
    if bad_format is not None:
        try:
            v.VpiValue(bad_format, 5)
        except svuvm.BridgeInvalidArgument as exc:
            check(isinstance(exc, ValueError),
                  "BridgeInvalidArgument 实例可被 ValueError 捕获", str(exc))
        except Exception as exc:
            check(False, "VpiValue 非法 format -> BridgeInvalidArgument",
                  f"wrong exception {type(exc).__name__}: {exc}")
        else:
            check(False, "VpiValue 非法 format -> BridgeInvalidArgument",
                  "exception not raised")


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

    # A setter replaces the union arm, so it must also update `format`.
    # Previously set_reals() on an int array left format=vpiIntVal and
    # _buf_len=3, so reading 3 ints from the new 8-byte buffer returned heap
    # garbage instead of raising. Both the rejection and the still-valid
    # set_integers() path are simulator-independent and run everywhere.
    import ctypes as _ct

    new_cap = _ct.pythonapi.PyCapsule_New
    new_cap.restype = _ct.py_object
    new_cap.argtypes = [_ct.c_void_p, _ct.c_char_p, _ct.c_void_p]
    switched = v.VpiArrayValue(v.vpiIntVal, 0, [1, 2, 3])
    reals = (_ct.c_double * 1)(2.5)
    reals_cap = new_cap(_ct.addressof(reals), b"audit", None)
    switched.set_reals(reals_cap)
    stale_fmt_rejected = False
    try:
        switched.get_integers_values(3)
    except (IndexError, ValueError):
        stale_fmt_rejected = True
    check(stale_fmt_rejected,
          "set_reals switches format so get_integers_values is rejected",
          "stale int format read past the new real buffer")
    check(switched.format == v.vpiRealVal,
          "set_reals updates format to vpiRealVal", f"got {switched.format}")

    kept = v.VpiArrayValue(v.vpiIntVal, 0, [1, 2, 3])
    ints = (_ct.c_int32 * 3)(7, 8, 9)
    ints_cap = new_cap(_ct.addressof(ints), b"audit", None)
    kept.set_integers(ints_cap)
    check(kept.get_integers_values(3) == [7, 8, 9],
          "set_integers keeps get_integers_values readable",
          "int buffer readback broke after set_integers")


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
        # IEEE 1800-2023 38.34: vpiReturnEvent is a bit mask OR'ed with the
        # delay constant; it must not hide a missing time_p from validation.
        ("vpiInertialDelay|vpiReturnEvent with NULL time",
         v.vpiInertialDelay | v.vpiReturnEvent, None),
        ("vpiTransportDelay|vpiReturnEvent with NULL time",
         v.vpiTransportDelay | v.vpiReturnEvent, None),
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

    # The three union arms below are the ones touched by the recent union
    # initialisation / keep_alive fixes. Constructors were covered, but the
    # vpi_get_value query path was not. Read each arm back through the
    # binding's getters (capsules for vector/time, str for string).
    def _capsule_addr(cap):
        api = ctypes.pythonapi
        api.PyCapsule_GetPointer.restype = ctypes.c_void_p
        api.PyCapsule_GetPointer.argtypes = [ctypes.py_object, ctypes.c_char_p]
        return api.PyCapsule_GetPointer(cap, None)

    # vpiVectorVal: s_vpi_vecval[] is {aval, bval} per 32-bit word. The
    # simulator may replace our buffer with one from its own pool, so always
    # read the pointer from the value object *after* the call.
    vecbuf = (ctypes.c_uint32 * 2)(0, 0)
    new_cap = ctypes.pythonapi.PyCapsule_New
    new_cap.restype = ctypes.py_object
    new_cap.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_void_p]
    cap = new_cap(ctypes.addressof(vecbuf), b"base_test", None)
    vv = v.VpiValue(v.vpiVectorVal)
    vv.vector = cap

    def get_vector():
        v.vpi_get_value(obj, vv)
        return vv.vector

    vec_cap = try_api_ex("vpi_get_value(vpiVectorVal)", get_vector)
    if vec_cap is not _SKIPPED:
        words = (ctypes.c_uint32 * 2).from_address(_capsule_addr(vec_cap))
        check((words[0], words[1]) == (0xABCD, 0),
              "vpi_get_value(vpiVectorVal) aval/bval",
              f"got aval=0x{words[0]:X}, bval=0x{words[1]:X}")

    # vpiTimeVal: the union arm holds s_vpi_time*. Verilator's
    # vl_check_format() rejects vpiTimeVal for a logic vector and records a
    # VPI error, so that leg is skipped there; xezim is probed for real.
    class _VpiTimeCT(ctypes.Structure):
        _fields_ = [("type", ctypes.c_int32), ("high", ctypes.c_uint32),
                    ("low", ctypes.c_uint32), ("real", ctypes.c_double)]

    tv = v.VpiValue(v.vpiTimeVal)

    def get_time_arm():
        v.vpi_get_value(obj, tv)
        return tv.time

    time_cap = try_api_ex("vpi_get_value(vpiTimeVal)", get_time_arm,
                          verilator_unsafe=True)
    if time_cap is not _SKIPPED:
        raw = _VpiTimeCT.from_address(_capsule_addr(time_cap))
        check(raw.type in (v.vpiSimTime, v.vpiScaledRealTime) and
              (int(raw.low) >= 0 and int(raw.high) >= 0),
              "vpi_get_value(vpiTimeVal) time arm",
              f"got type={raw.type} high={raw.high} low={raw.low} real={raw.real}")

    # vpiStringVal: for a packed vector the string arm is the vector's byte
    # representation. "ABCD" is printable on both backends (unlike 0xCDAB,
    # whose high bytes decode differently and are replaced by spaces).
    svuvm.uvm_hdl_deposit("top.dpi_vec_test", svuvm.VpiVecVal(0x41424344, 0x0))
    sv = v.VpiValue(v.vpiStringVal)

    def get_string_arm():
        v.vpi_get_value(obj, sv)
        return str(sv.str).strip()

    text = try_api_ex("vpi_get_value(vpiStringVal)", get_string_arm)
    if text is not _SKIPPED:
        check(text.encode("utf-8", "replace") in (b"ABCD", b"DCBA"),
              "vpi_get_value(vpiStringVal) byte string", f"got {text!r}")
    svuvm.uvm_hdl_deposit("top.dpi_vec_test", svuvm.VpiVecVal(0x0000ABCD, 0x0))


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

        # Common query properties on the same handles. Verilator's vpi_get
        # switch (verilated_vpi.cpp) implements vpiDirection and vpiSigned but
        # routes vpiNetType/vpiLeftRange/vpiRightRange through
        # VL_VPI_ERROR_, so those three are skipped there. Avoid asserting a
        # concrete value: the encoding and the range of a 1-bit reg differ
        # between backends.
        for prop, unsafe in (
            ("vpiDirection", False),
            ("vpiNetType", True),
            ("vpiSigned", False),
            ("vpiLeftRange", True),
            ("vpiRightRange", True),
        ):
            value = try_api_ex(f"vpi_get({prop}, {path})",
                               lambda p=prop, h=handle: v.vpi_get(getattr(v, p), h),
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

    # The bridge must reject `num` larger than the buffer it allocated: a
    # conforming simulator writes exactly `num` elements (IEEE 1800 38.14),
    # which would overflow this 3-element heap buffer. The guard fires before
    # the simulator call, so this runs safely on every backend.
    small = v.VpiArrayValue(v.vpiIntVal, 0, [1, 2, 3])
    for api in ("vpi_get_value_array", "vpi_put_value_array"):
        num_oob = False
        try:
            getattr(v, api)(obj, small, 0, 100)
        except (IndexError, ValueError):
            num_oob = True
        check(num_oob, f"{api} rejects num beyond buffer length",
              "oversized num reached the simulator")

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


__all__ = [
    "test_vpi_array_value_ctors",
    "test_vpi_error_info_fields",
    "test_vpi_get64_compare",
    "test_vpi_get_properties",
    "test_vpi_get_value",
    "test_vpi_get_value_formats",
    "test_vpi_handle",
    "test_vpi_handle_by_multi_index",
    "test_vpi_handle_management",
    "test_vpi_hierarchy",
    "test_vpi_info",
    "test_vpi_io",
    "test_vpi_mcd_multichannel",
    "test_vpi_property_matrix",
    "test_vpi_put_value",
    "test_vpi_put_value_flags",
    "test_vpi_scalar_structs",
    "test_vpi_value_array_control",
    "test_vpi_value_ctors",
]
