"""What the two emulator register tests share.

A bare-metal firmware in test/fw/main.c reaches a register block through
memory-mapped I/O. An instruction-set emulator runs that image, and every
access inside the register window becomes one UVM sequence on the APB agent,
which drives the peakrdl-generated register block:

    firmware -> MMIO -> emulator -> DPI -> UVM sequencer -> driver -> APB -> RTL

Only the emulator differs between test/unicorn_test and test/renode_test, so
the operation staged in the config_db, the expected access trace, the result
JSON and the reporting all live here; the layout itself is test/fw/layout.py,
which the Renode-side helper imports as well.

Results are accumulated through :class:`ral_common.ResultWriter` and published
by :func:`finish` to ``SVUVM_RESULT_JSON`` when the simulator runners supply
it. Manual runs without that variable keep the original UVM log behaviour.
TEST_PASS / TEST_FAIL stay as human-facing log lines, while FW_TEST_DONE is
the separate completion marker used by pytest to distinguish "ran to the end"
from "every case passed": one failed check is replayed as its own failing case
instead of aborting the whole run.

The module runs inside the simulator's embedded CPython, imported by the SV
side.
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
from ral_common.result_writer import ResultWriter  # noqa: E402
from ral_common.spec import FIRMWARE_CASES  # noqa: E402

# The sequencer the APB agent's driver listens on, as top.sv builds it.
SEQ_PATH = "uvm_test_top.m_agent.m_sqr"

# Legacy log-only failure list, kept in step with ResultWriter.failures.
FAILURES: list[str] = []

_WRITER: ResultWriter | None = None
_FINISHED = False


def begin_run() -> ResultWriter:
    """Start a fresh result accumulation for one simulator invocation.

    Returns:
        The new writer; the same instance :func:`check`, :func:`record_abort`
        and :func:`finish` will use.
    """
    global _WRITER, _FINISHED
    _WRITER = ResultWriter()
    _FINISHED = False
    FAILURES.clear()
    return _WRITER


def current_writer() -> ResultWriter:
    """Return the active writer, creating one if no run was begun explicitly."""
    global _WRITER
    if _WRITER is None:
        _WRITER = ResultWriter()
    return _WRITER


def report(line: str) -> None:
    """Put a line in the simulation log.

    Not print(): xezim's Python is embedded and never finalized, and stdout is
    a file rather than a tty, so the interpreter's block buffering discards
    print() output when the run ends at $finish. Reporting through UVM also
    puts the results in the report summary.
    """
    svuvm.vpi.vpi_printf(line + "\n")


def check(name: str, got: int, expected: int) -> None:
    """Compare one value, record its case in JSON and keep the UVM log.

    Args:
        name: Stable label from ``ral_common.spec.FIRMWARE_CASES``.
        got: Value returned by the register block / firmware path.
        expected: Value the register map promises.
    """
    ok = got == expected
    detail = "" if ok else f"got 0x{got:08x}, expected 0x{expected:08x}"
    writer = current_writer()
    writer.case(name, lambda: writer.check(name, ok, detail))
    if ok:
        report(f"PASS  {name}: 0x{got:08x}")
    else:
        message = f"FAIL  {name}: {detail}"
        svuvm.uvm_error(message)
        FAILURES.append(message)


def record_abort(reason: str) -> None:
    """Fail every case that did not run, so an aborted session cannot replay green.

    An emulator/process failure (unicorn fault, Renode not connecting, timeout)
    happens before the trace checks. Publishing only the checks that did run
    would leave the remaining cases absent from the JSON; pytest's
    ``assert_case`` treats an absent case as a failure, but making it explicit
    here gives a readable reason in the result file as well.

    Args:
        reason: Human-readable description of the abort.
    """
    writer = current_writer()
    recorded = {str(case.get("name", "")) for case in writer.cases}
    for name in FIRMWARE_CASES:
        if name in recorded:
            continue
        writer.case(name, lambda case_name=name: writer.check(case_name, False, reason))
        FAILURES.append(f"[FAIL] {name} - {reason}")


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
    """The firmware image to run, from the environment or beside the test.

    ``FW_REG_IMAGE`` is the shared/renode name; ``UNICORN_TEST_FW`` is kept for
    the original unicorn Makefile interface. Both are injected by the suite
    conftest and point at the same fixture-generated ``build/fw.bin``.
    """
    for key in ("FW_REG_IMAGE", "UNICORN_TEST_FW"):
        override = os.environ.get(key)
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
    """Publish the result JSON and report the verdict in the UVM log.

    Idempotent: simulator-side ``main()`` functions call it from ``finally``,
    and an explicit call after the checks is harmless. The completion marker
    is printed even when cases failed, so pytest sees "ran to completion" and
    replays individual cases instead of failing the whole simulator run.
    """
    global _FINISHED
    if _FINISHED:
        return
    _FINISHED = True

    writer = current_writer()
    failures = list(FAILURES) or list(writer.failures)
    report("")
    if failures:
        report(f"TEST_FAIL count={len(failures)}")
        for failure in failures:
            report("  " + failure)
    else:
        report("TEST_PASS")
    writer.dump(os.environ.get("SVUVM_RESULT_JSON"))
    report("FW_TEST_DONE")
