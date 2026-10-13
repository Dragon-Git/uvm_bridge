/* Bare-metal firmware for the emulator register tests.
 *
 * It reaches the register block through memory-mapped I/O and nothing else:
 * no libc, no driver, no register model. An instruction-set emulator - unicorn
 * in test/unicorn_test, Renode in test/renode_test - runs this image and turns
 * every access into a UVM sequence on the APB agent.
 *
 * The offsets and field positions come from the header `peakrdl c-header`
 * generates from demo_regs.rdl - the same .rdl the RTL comes from, so the
 * firmware and the hardware under test cannot drift apart.
 *
 * A read that only happened is not worth asserting on, so every read is one
 * the firmware depends on: each value it takes out of a register is added to
 * a running sum, and the sum is stored to CHECK_ADDR at the end. If a read
 * never reaches the firmware - the emulator's hook dropping the value, the
 * UVM sequence not running, the APB transfer failing - the sum is wrong and
 * the test says so, wherever the break was.
 *
 * The order of operations is asserted on by both tests' reg_test.py:
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
/* Both of these are inside the register window's address range but are not
 * registers, so the emulator's hooks treat them as the firmware's own
 * memory rather than forwarding them. */
#define CHECK_ADDR 0x40000fe0u
#define DONE_ADDR  0x40000ff0u
#define DONE_MAGIC 0x5eed0000u

/* What the sum of the values above comes to. Each tests' Python side
 * recomputes this from its own expected trace and asserts the firmware
 * stored it, so it cannot be a number the firmware invented. */
#define CHECK_MAGIC 0xdeadbee0u

/* The generated struct is __packed__ - it has to describe the byte layout of
 * a register file - and going through its members would make the compiler
 * emit byte loads and stores. The offsets are taken from that struct and the
 * accesses are made with explicit 32-bit pointers, which is how a register
 * file is meant to be touched and what the APB bridge understands. */
#define REG_OFF(field) ((unsigned int)__builtin_offsetof(demo_regs_t, field))
#define REG(field)     (*(volatile unsigned int *)(REG_BASE + REG_OFF(field)))

void _start(void) {
    unsigned int sum = 0;

    sum += REG(scratch);
    REG(scratch) = 0xdeadbeefu;
    sum += REG(scratch);

    REG(ctrl) = (0xau << DEMO_REGS__CTRL__CTRL_MODE_bp)
              | (0x1u << DEMO_REGS__CTRL__CTRL_ENABLE_bp);
    sum += REG(ctrl);

    sum += REG(status);
    REG(status) = 0x15u;
    sum += REG(status);

    *(volatile unsigned int *)CHECK_ADDR = sum;

    *(volatile unsigned int *)DONE_ADDR = DONE_MAGIC;

    for (;;) {
    }
}
