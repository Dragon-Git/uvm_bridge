"""Register-access test driven from Python through a UVM agent.

Uses the PeakRDL-PyRAL generated model of demo_regs.rdl. Every access the
model makes goes through SvuvmHWIO, which turns it into one UVM sequence,
so the whole path is exercised:

    Python RAL -> HWIO -> DPI -> UVM sequencer -> driver -> APB -> RTL

The RTL is the register block `peakrdl regblock` generates from the same
.rdl, so the model and the hardware under test cannot drift apart.

The Python side never touches VPI or the RTL directly. Check outcomes are
also recorded through ``ResultWriter`` into ``SVUVM_RESULT_JSON`` so pytest
can replay them per case; without that environment variable this file keeps
working exactly as before and only leaves UVM log lines.

    seq path: uvm_test_top.m_agent.m_sqr
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
if str(_HERE.parent / "gen") not in sys.path:
    sys.path.insert(0, str(_HERE.parent / "gen"))
_TEST_ROOT = _HERE.parent.parent
if str(_TEST_ROOT) not in sys.path:
    sys.path.insert(0, str(_TEST_ROOT))

import demo_reg_block  # noqa: E402  (generated, needs gen/ on sys.path)

from ral_common.result_writer import ResultWriter  # noqa: E402
from ral_common.spec import PYRAL_CASES  # noqa: E402
from svuvm import _svuvm as svuvm  # noqa: E402
from svuvm_hwio import SvuvmHWIO  # noqa: E402  (same directory as this file)

FAILURES: list[str] = []

(
    C_SCRATCH_INIT,
    C_SCRATCH_RW,
    C_SCRATCH_CHANGE,
    C_CTRL_VALUE,
    C_CTRL_ENABLE,
    C_CTRL_MODE,
    C_STATUS_INIT,
    C_STATUS_IGNORES,
) = PYRAL_CASES


def check(writer: ResultWriter, name: str, got: int, expected: int) -> None:
    """Compare one value, record it in the JSON and keep the UVM log.

    Reporting through UVM rather than print() is deliberate: xezim embeds
    CPython but never finalizes it, so stdout is a file rather than a tty and
    block buffering would discard print() output at $finish.
    """
    ok = got == expected
    detail = "" if ok else f"got 0x{got:08x}, expected 0x{expected:08x}"
    writer.check(name, ok, detail)
    if ok:
        svuvm.uvm_info(f"PASS  {name}: 0x{got:08x}", svuvm.UVM_LOW)
    else:
        message = f"FAIL  {name}: {detail}"
        svuvm.uvm_error(message)
        FAILURES.append(message)


def main() -> None:
    """Run all eight register checks, then publish the result JSON."""
    writer = ResultWriter()
    FAILURES.clear()
    try:
        ral = demo_reg_block.get_ral()
        ral.attach_hwio(SvuvmHWIO())

        def scratch_initial() -> None:
            # A fresh block reads as zero.
            check(writer, C_SCRATCH_INIT, ral.scratch.read(), 0x0000_0000)

        def scratch_write_read() -> None:
            # Whole-register write, then read it back.
            ral.scratch.write(0xDEAD_BEEF)
            check(writer, C_SCRATCH_RW, ral.scratch.read(), 0xDEAD_BEEF)

        def scratch_change_fields() -> None:
            # change_fields() is a read-modify-write: two APB transfers.
            with ral.scratch.change_fields() as fields:
                fields.scratch_data = 0x1234_5678
            check(writer, C_SCRATCH_CHANGE, ral.scratch.read(), 0x1234_5678)

        def ctrl_value() -> None:
            with ral.ctrl.change_fields() as fields:
                fields.ctrl_enable = 0x1
                fields.ctrl_mode = 0xA
            check(writer, C_CTRL_VALUE, ral.ctrl.read(), (0xA << 4) | 0x1)

        def ctrl_enable() -> None:
            ctrl = ral.ctrl.read_fields()
            check(writer, C_CTRL_ENABLE, ctrl.ctrl_enable, 0x1)

        def ctrl_mode() -> None:
            ctrl = ral.ctrl.read_fields()
            check(writer, C_CTRL_MODE, ctrl.ctrl_mode, 0xA)

        def status_initial() -> None:
            # status is sw=r: reads come from hwif_in, tied to zero in top.sv.
            check(writer, C_STATUS_INIT, ral.status.read(), 0x0)

        def status_ignores_writes() -> None:
            ral.status.write(0x0000_0015)
            check(writer, C_STATUS_IGNORES, ral.status.read(), 0x0)

        writer.case(C_SCRATCH_INIT, scratch_initial)
        writer.case(C_SCRATCH_RW, scratch_write_read)
        writer.case(C_SCRATCH_CHANGE, scratch_change_fields)
        writer.case(C_CTRL_VALUE, ctrl_value)
        writer.case(C_CTRL_ENABLE, ctrl_enable)
        writer.case(C_CTRL_MODE, ctrl_mode)
        writer.case(C_STATUS_INIT, status_initial)
        writer.case(C_STATUS_IGNORES, status_ignores_writes)
    finally:
        # Human-facing log lines are preserved for manual runs. The completion
        # marker is separate so one failed case is still reported per-case by
        # pytest instead of failing the whole simulator invocation.
        if writer.failures:
            svuvm.uvm_info(f"TEST_FAIL count={len(writer.failures)}", svuvm.UVM_LOW)
            for message in writer.failures:
                svuvm.uvm_info("  " + message, svuvm.UVM_LOW)
        else:
            svuvm.uvm_info("TEST_PASS", svuvm.UVM_LOW)
        writer.dump(os.environ.get("SVUVM_RESULT_JSON"))
        svuvm.uvm_info("PYRAL_TEST_DONE", svuvm.UVM_LOW)
