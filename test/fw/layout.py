"""Where everything the emulator tests use lives: the register map and the
memory the firmware is loaded into.

Nothing here imports svuvm, so the Renode-side helper in test/renode_test -
which runs in a plain CPython, with no UVM around it - can import this module
too. The UVM-facing half is test/fw/register_access.py.

All of it has to agree with test/fw/main.c, which cannot import Python, so it
is spelled out again there.

The register offsets, field positions and the access size come from the header
`peakrdl c-header` generates from demo_regs.rdl, the same .rdl the RTL comes
from, so the firmware and the hardware under test cannot drift apart.
"""

# Register offsets and the access size, matching demo_regs.rdl.
OFF_CTRL = 0x0
OFF_STATUS = 0x4
OFF_SCRATCH = 0x8
ACCESS_SIZE = 4

# The register window the firmware maps the block into. Matches REG_BASE in
# test/fw/main.c.
REG_BASE = 0x4000_0000
REG_SIZE = 0x1000

# The firmware's last act: a store here, inside the window but not a register,
# tells the Python side the sweep is over. Matches DONE_ADDR in test/fw/main.c.
DONE_OFFSET = 0x0FF0
DONE_MAGIC = 0x5EED_0000

# Just before that, the firmware stores the sum of everything it read, so the
# values it actually received can be checked. Matches CHECK_ADDR and
# CHECK_MAGIC in test/fw/main.c.
CHECK_OFFSET = 0x0FE0
CHECK_MAGIC = 0xDEAD_BEE0

# What the firmware does, in order. The block is a register file, so a read
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

def is_done_store(offset: int, value: int) -> bool:
    """Is this the store that ends the firmware's sweep?

    It lands inside the register window, so the emulator's window handler sees
    it, but it is not a register access and must not become a sequence.
    """
    return offset == DONE_OFFSET and value == DONE_MAGIC

def is_checksum_store(offset: int) -> bool:
    """Is this where the firmware reports the sum of what it read?

    Like the done marker this is not a register access, so the handler has to
    keep it away from the sequence path - but unlike the done marker it is a
    value the test asserts on, and the one that proves the read path worked.
    """
    return offset == CHECK_OFFSET

# Where the firmware runs. The image is entered at CODE_BASE and the stack
# grows down from STACK_TOP; both emulators map them the same way, so the
# firmware behaves identically under either.
CODE_BASE = 0x0000_0000
CODE_SIZE = 0x0010_0000
STACK_BASE = 0x2000_0000
STACK_SIZE = 0x0001_0000
# A bare-metal image sets up its own stack pointer, and neither emulator does
# it for us: unicorn has no reset code at all, and Renode's CPU starts with SP
# at zero, which sends every access below the address space. Both are told
# this value before the first instruction runs.
STACK_TOP = STACK_BASE + STACK_SIZE
