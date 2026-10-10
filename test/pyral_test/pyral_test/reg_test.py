"""Register-access test driven from Python through a UVM agent.

Uses the PeakRDL-PyRAL generated model of demo_regs.rdl. Every access the
model makes goes through SvuvmHWIO, which turns it into one UVM sequence,
so the whole path is exercised:

    Python RAL -> HWIO -> DPI -> UVM sequencer -> driver -> APB -> RTL

The RTL is the register block `peakrdl regblock` generates from the same
.rdl, so the model and the hardware under test cannot drift apart.

The Python side never touches VPI or the RTL directly.

    seq path: uvm_test_top.m_agent.m_sqr
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "gen"))

import demo_reg_block  # noqa: E402  (generated, needs gen/ on sys.path)

from svuvm import _svuvm as svuvm  # noqa: E402
from svuvm_hwio import SvuvmHWIO  # noqa: E402  (same directory as this file)

FAILURES: list[str] = []


def check(name: str, got: int, expected: int) -> None:
    """Compare one value and record rather than raise, so a single run
    reports every mismatch instead of stopping at the first.

    Reported through UVM rather than print(): xezim embeds CPython but never
    finalizes it, and stdout is a file rather than a tty, so the
    interpreter's block buffering discards print() output when the run ends
    at $finish - every access can complete and still leave no trace of the
    test's own result in the log.
    """
    if got == expected:
        svuvm.uvm_info(f"PASS  {name}: 0x{got:08x}", svuvm.UVM_LOW)
    else:
        msg = f"FAIL  {name}: got 0x{got:08x}, expected 0x{expected:08x}"
        svuvm.uvm_error(msg)
        FAILURES.append(msg)


def main() -> None:
    ral = demo_reg_block.get_ral()
    ral.attach_hwio(SvuvmHWIO())

    # A fresh block reads as zero.
    check("scratch initial", ral.scratch.read(), 0x0000_0000)

    # Whole-register write, then read it back.
    ral.scratch.write(0xDEAD_BEEF)
    check("scratch write/read", ral.scratch.read(), 0xDEAD_BEEF)

    # change_fields() is a read-modify-write: the model reads the register,
    # applies the fields and writes it back, so this is two APB transfers
    # rather than one.
    with ral.scratch.change_fields() as fields:
        fields.scratch_data = 0x1234_5678
    check("scratch change_fields", ral.scratch.read(), 0x1234_5678)

    # Two fields, one register, checked as a whole and field by field.
    with ral.ctrl.change_fields() as fields:
        fields.ctrl_enable = 0x1
        fields.ctrl_mode = 0xA
    check("ctrl value", ral.ctrl.read(), (0xA << 4) | 0x1)
    ctrl = ral.ctrl.read_fields()
    check("ctrl.enable", ctrl.ctrl_enable, 0x1)
    check("ctrl.mode", ctrl.ctrl_mode, 0xA)

    # status is sw=r, so the generated block keeps no storage for it: reads
    # come from hwif_in, which the testbench ties to 0, and a software write
    # is ignored. Both halves of that are worth pinning down, since a
    # read-only register that quietly accepts writes is a common way for a
    # register file to be wrong.
    check("status initial", ral.status.read(), 0x0)
    ral.status.write(0x0000_0015)
    check("status ignores writes", ral.status.read(), 0x0)

    if FAILURES:
        svuvm.uvm_info(f"TEST_FAIL count={len(FAILURES)}", svuvm.UVM_LOW)
        for f in FAILURES:
            svuvm.uvm_info("  " + f, svuvm.UVM_LOW)
        return
    svuvm.uvm_info("TEST_PASS", svuvm.UVM_LOW)
