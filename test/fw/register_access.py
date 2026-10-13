"""What the two emulator register tests share.

A bare-metal firmware in test/fw/main.c reaches a register block through
memory-mapped I/O. An instruction-set emulator runs that image, and every
access inside the register window becomes one UVM sequence on the APB agent,
which drives the peakrdl-generated register block:

    firmware -> MMIO -> emulator -> DPI -> UVM sequencer -> driver -> APB -> RTL

Only the emulator differs between test/unicorn_test and test/renode_test, so
the operation staged in the config_db, the expected access trace and the
reporting all live here; the layout itself is test/fw/layout.py,
which the Renode-side helper imports as well.

The module runs inside xezim's embedded CPython, imported by the SV side.
"""

from __future__ import annotations

import os

from svuvm import _svuvm as svuvm

from layout import (  # noqa: F401 -- re-exported for the two tests
    ACCESS_SIZE,
    DONE_MAGIC,
    DONE_OFFSET,
    EXPECTED,
    OFF_CTRL,
    OFF_SCRATCH,
    OFF_STATUS,
    REG_BASE,
    REG_SIZE,
    is_checksum_store,
    is_done_store,
)

# The sequencer the APB agent's driver listens on, as top.sv builds it.
SEQ_PATH = "uvm_test_top.m_agent.m_sqr"

FAILURES: list[str] = []

def report(line: str) -> None:
    """Put a line in the simulation log.

    Not print(): xezim's Python is embedded and never finalized, and stdout is
    a file rather than a tty, so the interpreter's block buffering discards
    print() output when the run ends at $finish. Reporting through UVM also
    puts the results in the report summary.
    """
    svuvm.vpi.vpi_printf(line + "\n")

def check(name: str, got: int, expected: int) -> None:
    if got == expected:
        report(f"PASS  {name}: 0x{got:08x}")
    else:
        msg = f"FAIL  {name}: got 0x{got:08x}, expected 0x{expected:08x}"
        svuvm.uvm_error(msg)
        FAILURES.append(msg)

def one_sequence(offset: int, is_write: bool, wdata: int = 0) -> int:
    """Run one register access as one UVM sequence, and return what was read."""
    label = f"fw {'wr' if is_write else 'rd'} 0x{offset:03x}"

    svuvm.set_config_int("", "*", "op_addr", offset & 0xFFFF_FFFF)
    svuvm.set_config_int("", "*", "op_wdata", wdata & 0xFFFF_FFFF)
    svuvm.set_config_int("", "*", "op_is_write", 1 if is_write else 0)
    svuvm.set_config_string("", "*", "op_label", label)

    # rand_en=0: the sequence fills the item explicitly. background=0: block
    # until the transfer completes, so the result is there to read back.
    svuvm.start_seq("reg_seq", SEQ_PATH, 0, 0)

    if svuvm.get_config_int("", "*", "res_err"):
        raise RuntimeError(f"APB error response for {label}")
    return svuvm.get_config_int("", "*", "res_rdata")

def firmware_image(default_dir: str) -> str:
    """The firmware image to run, from the environment or beside the test."""
    override = os.environ.get("FW_REG_IMAGE")
    if override:
        return override
    return os.path.join(default_dir, "build", "fw.bin")

def compare_trace(trace: list[tuple[str, int, int]]) -> None:
    """Assert the firmware touched the registers in the expected order, with
    the values the register block should have produced."""
    if len(trace) != len(EXPECTED):
        svuvm.uvm_error(f"firmware made {len(trace)} register accesses, expected {len(EXPECTED)}")
    for i, (exp_kind, exp_off, exp_val) in enumerate(EXPECTED):
        if i >= len(trace):
            break
        kind, off, val = trace[i]
        if (kind, off) != (exp_kind, exp_off):
            svuvm.uvm_error(
                f"access {i}: firmware did {kind} 0x{off:03x}, expected {exp_kind} 0x{exp_off:03x}"
            )
            continue
        check(f"access {i}: {kind} 0x{off:03x}", val, exp_val)

def expected_read_sum() -> int:
    """The sum the firmware should have accumulated, from the values the
    register block is supposed to return."""
    return sum(value for kind, _, value in EXPECTED if kind == "R") & 0xFFFF_FFFF

def check_read_sum(checksum: int | None) -> None:
    """Assert the firmware's own total of what it read.

    The trace above records what the register block produced; this records what
    the firmware received. They agree only if the value made the whole trip
    back - through the bus, the emulator and its read hook, into the load the
    firmware executed - which is the part a wrong answer would come from.
    """
    if checksum is None:
        # If the firmware faulted, the caller reports that; adding a second
        # complaint about the missing total would only obscure it.
        return
    check("firmware read sum", checksum, expected_read_sum())

def finish() -> None:
    """Report the verdict, in the form the Makefile greps for."""
    report("")
    if FAILURES:
        report(f"TEST_FAIL count={len(FAILURES)}")
        for failure in FAILURES:
            report("  " + failure)
        return
    report("TEST_PASS")
