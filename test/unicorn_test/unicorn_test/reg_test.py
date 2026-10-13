"""Register-access test driven from Python through a Unicorn-emulated
ARM core.

Exercises the PeakRDL-PyRAL generated model of demo_regs.rdl against
UnicornHWIO, where each access the model makes becomes one ARM Thumb
``ldr``/``str`` instruction retired by the Unicorn CPU emulator. No
simulator is involved - the path is

    Python RAL -> HWIO -> Unicorn -> ARM ldr/str -> mapped APB RAM

so the test is the bisect point for the model: if an access is wrong
here too, the model is wrong rather than the bus or the simulator.

Run it after generating the model:

    peakrdl pyral demo_regs.rdl --rename demo_reg_block -o gen
    python -m unicorn_test.reg_test
"""

import sys
from pathlib import Path

GEN_DIR = Path(__file__).resolve().parent.parent / "gen"
sys.path.insert(0, str(GEN_DIR))

import demo_reg_block  # noqa: E402  (generated, needs gen/ on sys.path)
from unicorn_test.unicorn_hwio import UnicornHWIO  # noqa: E402

FAILURES: list[str] = []


def check(name: str, got: int, expected: int) -> None:
    """Compare one value and record a failure instead of raising.

    Raising on the first mismatch would hide whatever else is broken, and
    the point of this test is to report the whole picture in one run.
    """
    if got == expected:
        print(f"PASS  {name}: 0x{got:08x}")
    else:
        msg = f"FAIL  {name}: got 0x{got:08x}, expected 0x{expected:08x}"
        print(msg)
        FAILURES.append(msg)


def main() -> int:
    ral = demo_reg_block.get_ral()
    hwio = UnicornHWIO()
    ral.attach_hwio(hwio)

    # Whole-register access. A fresh Unicorn mapping is zeroed, so 0 is
    # the value every register must read back before anything is
    # written. (DemoHWIO is the same.)
    check("scratch initial", ral.scratch.read(), 0x0000_0000)

    # Plain write then read. Each side is one ARM Thumb str / ldr at
    # 0x8, retired by Unicorn.
    ral.scratch.write(0xDEAD_BEEF)
    check("scratch write/read", ral.scratch.read(), 0xDEAD_BEEF)
    # The witness hook records the address of the last APB write, so
    # pin down that the str really landed where the model thinks it
    # did rather than somewhere else.
    check("scratch write hit APB", hwio._last_addr, 0x8)
    check("scratch write value", hwio._last_value & 0xFFFF_FFFF, 0xDEAD_BEEF)

    # Field-aware access: the field is the low 32 bits of scratch, so a
    # field write covers the whole register here. The point is that the
    # field path goes through a different code path than read()/write()
    # - a read-modify-write that is two ldr/str pairs, not one.
    with ral.scratch.change_fields() as fields:
        fields.scratch_data = 0x1234_5678
    check("scratch change_fields", ral.scratch.read(), 0x1234_5678)

    # Multi-field register, checked bit by bit.
    with ral.ctrl.change_fields() as fields:
        fields.ctrl_enable = 0x1
        fields.ctrl_mode = 0xA
    expected_ctrl = (0xA << 4) | 0x1
    check("ctrl write", ral.ctrl.read(), expected_ctrl)

    ctrl_fields = ral.ctrl.read_fields()
    check("ctrl.enable", ctrl_fields.ctrl_enable, 0x1)
    check("ctrl.mode", ctrl_fields.ctrl_mode, 0xA)

    # Read-only register: the APB region is plain RAM (no RTL behind
    # it), so a software write goes through and the value is readable.
    # This documents that behaviour rather than asserting on real
    # hardware semantics - the contrast is with pyral_test/reg_test.py,
    # where the peakrdl regblock RTL is what makes status ignore
    # writes.
    with ral.status.change_fields() as fields:
        fields.status_state = 0x5
        fields.status_busy = 0x1
    expected_status = (0x1 << 4) | 0x5
    check("status write", ral.status.read(), expected_status)

    print()
    if FAILURES:
        print(f"TEST_FAIL count={len(FAILURES)}")
        for f in FAILURES:
            print("  " + f)
        return 1
    print("TEST_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
