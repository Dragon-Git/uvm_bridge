"""Run the bare-metal firmware against the register block, through APB.

The firmware reaches the registers as memory-mapped I/O. Unicorn executes it,
and every access inside the register window is turned into one UVM sequence
on the APB agent:

    firmware -> MMIO -> unicorn -> DPI -> UVM sequencer -> driver -> APB -> RTL

A read travels the same path back: the read hook writes the value the
register returned into the emulated memory before the load completes, so the
firmware's own load sees it.

Everything that is not unicorn - the register map, the sequence, the expected
access trace, the reporting - lives in ../fw/register_access.py, which
test/renode_test drives the same way.

The module is called reg_test because that is the name top.sv's test class
carries, and the SV side reaches Python through
py_task(get_type_name(), "main", ...) - which imports a module by that name
and calls its main(). It shares test/pyral_test/sv/top.sv for the same
reason: the testbench around the register block is identical, only what
drives the bus differs.

    seq path: uvm_test_top.m_agent.m_sqr
"""

from __future__ import annotations

import os
import sys
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

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "fw"))

from register_access import (  # noqa: E402
    ACCESS_SIZE,
    DONE_MAGIC,
    DONE_OFFSET,
    REG_BASE,
    REG_SIZE,
    check_read_sum,
    compare_trace,
    finish,
    firmware_image,
    one_sequence,
    report,
)
from layout import CODE_BASE, CODE_SIZE, STACK_BASE, STACK_SIZE, STACK_TOP, is_checksum_store  # noqa: E402

class FirmwareRun:
    """Unicorn running the firmware, with its register window served by APB."""

    def __init__(self, image: bytes) -> None:
        self.trace: list[tuple[str, int, int]] = []
        self.done = False
        self.checksum: int | None = None

        self.mu = Uc(UC_ARCH_ARM64, UC_MODE_ARM)
        mu = self.mu
        mu.mem_map(CODE_BASE, CODE_SIZE)
        mu.mem_write(CODE_BASE, image)
        mu.mem_map(STACK_BASE, STACK_SIZE)
        # A bare-metal image has no startup code to set the stack pointer, and
        # the firmware's prologue writes to the stack straight away. Renode
        # needs the same thing - see ../renode_test/renode_runner.py.
        mu.reg_write(UC_ARM64_REG_SP, STACK_TOP)
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
        if is_checksum_store(offset):
            self.checksum = value & 0xFFFF_FFFF
            return
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

def main() -> None:
    image_file = Path(firmware_image(str(Path(__file__).resolve().parent)))
    image = image_file.read_bytes()
    report(f"firmware: {image_file.name}, {len(image)} bytes")

    run = FirmwareRun(image)
    run.run()
    compare_trace(run.trace)
    check_read_sum(run.checksum)

    finish()

# No call at module scope on purpose: the SV side imports this module and then
# calls its main() attribute, so a bare main() here would run the whole test a
# second time, at import.
