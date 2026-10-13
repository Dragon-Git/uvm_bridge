"""Run a bare-metal firmware against the register block, through APB.

The firmware reaches the registers as memory-mapped I/O. Unicorn executes it,
and every access inside the register window is turned into one UVM sequence
on the APB agent:

    firmware -> MMIO -> unicorn -> DPI -> UVM sequencer -> driver -> APB -> RTL

A read travels the same path back: the read hook writes the value the
register returned into the emulated memory before the load completes, so the
firmware's own load sees it.

The firmware is built from fw/main.c using the offsets and field masks that
`peakrdl c-header` generates from demo_regs.rdl. No register model is
involved: the firmware is the thing doing the accessing.

The module is called reg_test because that is the name top.sv's test class
carries, and the SV side reaches Python through
py_task(get_type_name(), "main", ...) - which imports a module by that name
and calls its main(). It shares test/pyral_test/sv/top.sv for the same
reason: the testbench around the register block is identical, only what
drives the bus differs.

    seq path: uvm_test_top.m_agent.m_sqr
"""

import os
from pathlib import Path

from unicorn import (
    UC_ARCH_ARM64,
    UC_HOOK_MEM_READ,
    UC_HOOK_MEM_WRITE,
    UC_MODE_ARM,
    Uc,
    UcError,
)
from unicorn.arm64_const import UC_ARM64_REG_SP

from svuvm import _svuvm as svuvm

SEQ_PATH = "uvm_test_top.m_agent.m_sqr"

# Where the firmware is linked, and what it expects to find. These match
# fw/main.c.
CODE_BASE = 0x0000_0000
CODE_SIZE = 0x1000
STACK_BASE = 0x2000_0000
STACK_SIZE = 0x0001_0000
REG_BASE = 0x4000_0000
REG_SIZE = 0x1000

# The firmware's last act: a store here, outside the register block.
DONE_OFFSET = 0x0FF0
DONE_MAGIC = 0x5EED_0000

ACCESS_SIZE = 4

# Register offsets, matching demo_regs.rdl.
OFF_CTRL = 0x0
OFF_STATUS = 0x4
OFF_SCRATCH = 0x8

# What the firmware does, in order. The driver is a register file, so a read
# returns the last write; status is sw=r, so the block keeps no storage for it
# and a software write is dropped.
EXPECTED = [
    ("R", OFF_SCRATCH, 0x0000_0000),
    ("W", OFF_SCRATCH, 0xDEAD_BEEF),
    ("R", OFF_SCRATCH, 0xDEAD_BEEF),
    ("W", OFF_CTRL, (0xA << 4) | 0x1),
    ("R", OFF_CTRL, (0xA << 4) | 0x1),
    ("R", OFF_STATUS, 0x0000_0000),
    ("W", OFF_STATUS, 0x0000_0015),
    ("R", OFF_STATUS, 0x0000_0000),
]

FAILURES: list[str] = []


def report(line: str) -> None:
    """Put a line in the simulation log.

    Not print(): xezim embeds CPython but never finalizes it, and stdout is a
    file rather than a tty, so the interpreter's block buffering discards
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


def firmware_image() -> Path:
    path = os.environ.get("UNICORN_TEST_FW")
    if path:
        return Path(path)
    return Path(__file__).resolve().parent / "build" / "fw.bin"


class FirmwareRun:
    """Unicorn running the firmware, with its register window served by APB."""

    def __init__(self, image: bytes) -> None:
        self.trace: list[tuple[str, int, int]] = []
        self.done = False

        self.mu = Uc(UC_ARCH_ARM64, UC_MODE_ARM)
        mu = self.mu
        mu.mem_map(CODE_BASE, CODE_SIZE)
        mu.mem_write(CODE_BASE, image)
        mu.mem_map(STACK_BASE, STACK_SIZE)
        # A bare-metal image has no startup code to set the stack pointer, and
        # the firmware's prologue writes to the stack straight away.
        mu.reg_write(UC_ARM64_REG_SP, STACK_BASE + STACK_SIZE // 2)
        # The register window is mapped so its accesses are ordinary loads and
        # stores; the hooks below decide what they mean.
        mu.mem_map(REG_BASE, REG_SIZE)

        mu.hook_add(UC_HOOK_MEM_READ, self._on_read)
        mu.hook_add(UC_HOOK_MEM_WRITE, self._on_write)

    @staticmethod
    def _in_window(address: int) -> bool:
        return REG_BASE <= address < REG_BASE + REG_SIZE

    def _on_read(self, uc, access, address, size, value, user):
        if not self._in_window(address):
            return
        offset = address - REG_BASE
        if offset == DONE_OFFSET:
            return
        if size != ACCESS_SIZE:
            raise RuntimeError(f"firmware read {size} bytes at 0x{offset:03x}")
        data = one_sequence(offset, is_write=False)
        self.trace.append(("R", offset, data))
        # The read hook runs before the load completes, so writing the location
        # here is what the firmware's load ends up seeing.
        uc.mem_write(address, data.to_bytes(ACCESS_SIZE, "little"))

    def _on_write(self, uc, access, address, size, value, user):
        if not self._in_window(address):
            return
        offset = address - REG_BASE
        if offset == DONE_OFFSET:
            if value == DONE_MAGIC:
                self.done = True
                uc.emu_stop()
            return
        if size != ACCESS_SIZE:
            raise RuntimeError(f"firmware write {size} bytes at 0x{offset:03x}")
        self.trace.append(("W", offset, value & 0xFFFF_FFFF))
        one_sequence(offset, is_write=True, wdata=value)

    def run(self) -> None:
        try:
            self.mu.emu_start(CODE_BASE, CODE_BASE + CODE_SIZE, count=100_000)
        except UcError as exc:
            raise RuntimeError(f"firmware faulted: {exc}") from exc
        if not self.done:
            raise RuntimeError(
                "firmware used up its instruction budget without reaching its done marker"
            )


def compare_trace(trace: list[tuple[str, int, int]]) -> None:
    """Assert the firmware touched the registers in the expected order, with
    the values the register block should have produced."""
    if len(trace) != len(EXPECTED):
        svuvm.uvm_error(
            f"firmware made {len(trace)} register accesses, expected {len(EXPECTED)}"
        )
    for i, (exp_kind, exp_off, exp_val) in enumerate(EXPECTED):
        if i >= len(trace):
            break
        kind, off, val = trace[i]
        if (kind, off) != (exp_kind, exp_off):
            svuvm.uvm_error(
                f"access {i}: firmware did {kind} 0x{off:03x}, "
                f"expected {exp_kind} 0x{exp_off:03x}"
            )
            continue
        check(f"access {i}: {kind} 0x{off:03x}", val, exp_val)


def main() -> None:
    image_file = firmware_image()
    image = image_file.read_bytes()
    report(f"firmware: {image_file.name}, {len(image)} bytes")

    run = FirmwareRun(image)
    run.run()
    compare_trace(run.trace)

    report("")
    if FAILURES:
        report(f"TEST_FAIL count={len(FAILURES)}")
        for failure in FAILURES:
            report("  " + failure)
        return
    report("TEST_PASS")


# No call at module scope on purpose: the SV side imports this module and then
# calls its main() attribute, so a bare main() here would run the whole test a
# second time, at import.
