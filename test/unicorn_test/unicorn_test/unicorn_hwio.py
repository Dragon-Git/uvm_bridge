"""A PyRAL HWIO whose every access is one ARM Thumb load/store.

Gives the generated register model a backend that runs on a real (if
emulated) CPU core: each hardware access the model makes becomes

    RAL -> HWIO -> Unicorn -> ARM ldr/str -> mapped APB RAM

by pointing the Thumb PC at the right pre-loaded instruction (``ldr
r0, [r1]`` for reads, ``str r0, [r1]`` for writes), setting ``r1`` to
the register address (and ``r0`` to the value for writes), and asking
Unicorn to retire exactly one instruction. The APB region is plain
RAM, so reads come back from it and writes update it - the model has
no other backend.

This is the bisect point for the model: if an access is wrong here,
where every access is a real CPU load/store, it is the model that is
wrong rather than the bus, the simulator, or anything further down. It
mirrors ``peakrdl_pyral_runtime.hwio.demo.DemoHWIO`` (same behaviour,
same 4-byte-only accesses) except the storage is the address space of
an emulated Cortex-M rather than a Python dict.

Subclasses HWIO directly rather than reaching for one of the runtime's
own implementations: peakrdl_pyral_runtime.hwio deliberately exports
only HWIO (see its __init__.py), and _read_impl/_write_impl are all a
subclass has to provide - read_list, the byte accessors and the async
variants are built on top of them.

The two instructions are written into separate code slots once at
init, so the bytes at each PC never change and Unicorn's JIT icache
stays valid across accesses. Rewriting one slot in place and reusing
the same PC would also work, but only after a manual ``UC_CTL_TB_FLUSH``
- far more fragile than just having two fixed entry points.
"""

from unicorn import (
    Uc,
    UC_ARCH_ARM,
    UC_MODE_THUMB,
    UC_HOOK_MEM_WRITE,
    UcError,
)
from unicorn.arm_const import (
    UC_ARM_REG_R0,
    UC_ARM_REG_R1,
    UC_ARM_REG_SP,
)

from peakrdl_pyral_runtime.hwio import HWIO

# Map a small APB region at 0x0. demo_regs.rdl puts ctrl at 0x0, status
# at 0x4, scratch at 0x8, so 4KB is more than enough; the same region
# also keeps Unicorn happy with a small, fixed mapping.
APB_BASE = 0x0000_0000
APB_SIZE = 0x1000

# Code lives in its own region so the APB region is only ever touched by
# the emulated load/store. The stack is mapped because some Unicorn
# builds touch SP on emu_start even when the program never pushes.
CODE_BASE = 0x1000_0000
CODE_SIZE = 0x1000
STACK_BASE = 0x2000_0000
STACK_SIZE = 0x1000
STACK_TOP = STACK_BASE + STACK_SIZE

# Two slots inside the code region, one per instruction. Each is 4-byte
# aligned so the Thumb PC bit (LSB) is the only thing that differs
# between the entry address and the address the bytes live at.
CODE_LDR = CODE_BASE + 0x00
CODE_STR = CODE_BASE + 0x04

ACCESS_SIZE = 4

# ARM Thumb (16-bit, T1) encodings. The imm5=0 form is
#   15:11  opcode-class
#   10:6   imm5 (offset in units of 4 bytes; 0 here)
#    5:3   Rn  (base register; r1 here)
#    2:0   Rt  (source/destination; r0 here)
# ldr r0, [r1, #0] -> 0x6808 -> bytes 0x08 0x68
# str r0, [r1, #0] -> 0x6008 -> bytes 0x08 0x60
THUMB_LDR_R0_R1 = bytes([0x08, 0x68])
THUMB_STR_R0_R1 = bytes([0x08, 0x60])


class UnicornHWIO(HWIO):
    def __init__(self, offset: int = 0) -> None:
        self._mu = Uc(UC_ARCH_ARM, UC_MODE_THUMB)
        self._mu.mem_map(CODE_BASE, CODE_SIZE)
        self._mu.mem_map(STACK_BASE, STACK_SIZE)
        self._mu.mem_map(APB_BASE, APB_SIZE)
        # Write both load and store instructions once, at fixed PCs,
        # before any emu_start call. The bytes at each entry point then
        # never change, so Unicorn's JIT icache stays valid for the
        # lifetime of the object - no per-access flush needed.
        self._mu.mem_write(CODE_LDR, THUMB_LDR_R0_R1)
        self._mu.mem_write(CODE_STR, THUMB_STR_R0_R1)
        self._mu.reg_write(UC_ARM_REG_SP, STACK_TOP)
        # Witness hook only - the str instruction itself updates
        # Unicorn's RAM, so we have nothing to mirror. Keeping the last
        # access lets the test assert "the CPU really touched this
        # address" without inspecting Unicorn's internal state.
        self._last_addr = -1
        self._last_value = 0
        self._mu.hook_add(UC_HOOK_MEM_WRITE, self._on_write)
        super().__init__(offset)

    def _on_write(self, uc, access, address, size, value, user_data) -> None:
        # Unicorn has already written to its RAM by the time this fires;
        # just record the access for the test to inspect.
        self._last_addr = address
        self._last_value = value

    def _run_one(self, entry: int, r1: int, r0: int = 0) -> int:
        self._mu.reg_write(UC_ARM_REG_R1, r1 & 0xFFFF_FFFF)
        # Always set r0: writes pass the value, reads ignore it. Setting
        # it for reads is harmless and keeps the path symmetric.
        self._mu.reg_write(UC_ARM_REG_R0, r0 & 0xFFFF_FFFF)
        # count=1 retires exactly one instruction (the load/store). The
        # entry address | 1 sets the Thumb bit in the PC.
        try:
            self._mu.emu_start(entry | 1, 0, count=1)
        except UcError as e:
            raise RuntimeError(
                f"Unicorn failed to retire an instruction at 0x{entry:08x} "
                f"with r1=0x{r1:08x}: {e}"
            ) from e
        return self._mu.reg_read(UC_ARM_REG_R0)

    def _read_impl(self, addr: int, size: int) -> int:
        if size != ACCESS_SIZE:
            raise NotImplementedError(
                f"the agent only does {ACCESS_SIZE}-byte accesses, got {size}"
            )
        return self._run_one(CODE_LDR, addr)

    def _write_impl(self, addr: int, value: int, size: int) -> None:
        if size != ACCESS_SIZE:
            raise NotImplementedError(
                f"the agent only does {ACCESS_SIZE}-byte accesses, got {size}"
            )
        self._run_one(CODE_STR, addr, value)
