/* Bare-metal firmware for the unicorn test.
 *
 * It reaches the register block through memory-mapped I/O and nothing else:
 * no libc, no driver, no register model. Unicorn runs this image and turns
 * every access into a UVM sequence on the APB agent.
 *
 * The offsets and field positions come from the header `peakrdl c-header`
 * generates from demo_regs.rdl - the same .rdl the RTL comes from, so the
 * firmware and the hardware under test cannot drift apart.
 *
 * The order of operations is asserted on by reg_test.py:
 *
 *   read  scratch        -> 0, a fresh block
 *   write scratch        <- 0xdeadbeef
 *   read  scratch        -> 0xdeadbeef
 *   write ctrl           <- 0xa1, enable in bit 0 and mode in bits 7:4
 *   read  ctrl           -> 0xa1
 *   read  status         -> 0; it is sw=r and the testbench drives 0
 *   write status         <- 0x15, dropped: the block keeps no storage for it
 *   read  status         -> still 0
 *
 * then a store to DONE_ADDR, which is not a register access and tells the
 * Python side the firmware finished.
 */

#include "demo_regs.h"

#define REG_BASE   0x40000000u
#define DONE_ADDR  0x40000ff0u
#define DONE_MAGIC 0x5eed0000u

/* The generated struct is __packed__ - it has to describe the byte layout of
 * a register file - and going through its members would make the compiler
 * emit byte loads and stores. The offsets are taken from that struct and the
 * accesses are made with explicit 32-bit pointers, which is how a register
 * file is meant to be touched and what the APB bridge understands. */
#define REG_OFF(field) ((unsigned int)__builtin_offsetof(demo_regs_t, field))
#define REG(field)     (*(volatile unsigned int *)(REG_BASE + REG_OFF(field)))

void _start(void) {
    volatile unsigned int v;

    v = REG(scratch);
    REG(scratch) = 0xdeadbeefu;
    v = REG(scratch);

    REG(ctrl) = (0xau << DEMO_REGS__CTRL__CTRL_MODE_bp)
              | (0x1u << DEMO_REGS__CTRL__CTRL_ENABLE_bp);
    v = REG(ctrl);

    v = REG(status);
    REG(status) = 0x15u;
    v = REG(status);

    (void)v;

    *(volatile unsigned int *)DONE_ADDR = DONE_MAGIC;

    for (;;) {
    }
}
