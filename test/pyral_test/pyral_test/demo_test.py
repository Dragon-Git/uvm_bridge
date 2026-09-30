"""Smoke test for the PeakRDL-PyRAL generated register model.

Step 1 of the pyral work: exercise the generated RAL against the runtime's
DemoHWIO, i.e. plain Python with no simulator involved. A later step adds
an svuvm-backed HWIO and drives the same model against RTL under xezim.

Run it after generating the model:

    peakrdl pyral demo_regs.rdl --rename demo_reg_block -o gen
    python -m pyral_test.demo_test
"""

import sys
from pathlib import Path

GEN_DIR = Path(__file__).resolve().parent.parent / "gen"
sys.path.insert(0, str(GEN_DIR))

import demo_reg_block  # noqa: E402  (generated, needs gen/ on sys.path)
from peakrdl_pyral_runtime.hwio.demo import DemoHWIO  # noqa: E402

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
    hwio = DemoHWIO()
    ral.attach_hwio(hwio)

    # Whole-register access. A fresh DemoHWIO is blank RAM, so 0 is the
    # value every register must read back before anything is written.
    check("scratch initial", ral.scratch.read(), 0x0000_0000)

    # Plain write then read.
    ral.scratch.write(0xDEAD_BEEF)
    check("scratch write/read", ral.scratch.read(), 0xDEAD_BEEF)

    # Field-aware access: the field is the low 32 bits of scratch, so a
    # field write covers the whole register here. The point is that the
    # field path goes through a different code path than read()/write().
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

    # Read-only register: DemoHWIO is plain RAM, so a software write goes
    # through and the value is readable. This documents that behaviour
    # rather than asserting on real hardware semantics.
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
