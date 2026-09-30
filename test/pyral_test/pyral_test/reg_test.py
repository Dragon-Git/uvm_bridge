"""Register-access test driven from Python through a UVM agent.

The Python side never touches VPI or the RTL directly. For every register
operation it stages the request in the UVM config_db, calls start_seq() to
run one UVM sequence, and reads the result back out of the same config_db.
The sequence's driver is what drives the APB bus into the generated
register block, so this exercises the whole path: Python -> DPI -> UVM
sequencer -> driver -> APB -> RTL -> back again.

    seq path: uvm_test_top.m_agent.m_sqr
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "gen"))

from svuvm import _svuvm as svuvm  # noqa: E402

SEQ_PATH = "uvm_test_top.m_agent.m_sqr"

FAILURES: list[str] = []

# Register offsets, matching demo_regs.rdl.
ADDR_CTRL = 0x0
ADDR_STATUS = 0x4
ADDR_SCRATCH = 0x8


def check(name: str, got: int, expected: int) -> None:
    """Compare one value and record rather than raise, so a single run
    reports every mismatch instead of stopping at the first."""
    if got == expected:
        print(f"PASS  {name}: 0x{got:08x}")
    else:
        msg = f"FAIL  {name}: got 0x{got:08x}, expected 0x{expected:08x}"
        print(msg)
        FAILURES.append(msg)


def do_op(
    is_write: bool,
    addr: int,
    wdata: int = 0,
    label: str = "",
) -> int:
    """Run one register operation as one UVM sequence and return the value
    read back (0 for writes)."""
    svuvm.set_config_int("", "*", "op_addr", addr)
    svuvm.set_config_int("", "*", "op_wdata", wdata)
    svuvm.set_config_int("", "*", "op_is_write", 1 if is_write else 0)
    svuvm.set_config_string("", "*", "op_label", label)

    # rand_en=0: the sequence fills the item explicitly. background=0: block
    # until the transfer completes so the result is ready to read back.
    svuvm.start_seq("reg_seq", SEQ_PATH, 0, 0)

    rdata = svuvm.get_config_int("", "*", "res_rdata")
    err = svuvm.get_config_int("", "*", "res_err")
    if err:
        print(f"  note: {label} returned APB error response")
    return rdata


def main() -> None:
    # A fresh block reads as zero.
    check("scratch initial", do_op(False, ADDR_SCRATCH, label="read scratch"), 0)

    # Write then read back the same value.
    do_op(True, ADDR_SCRATCH, 0xDEAD_BEEF, label="write scratch")
    check(
        "scratch write/read",
        do_op(False, ADDR_SCRATCH, label="read scratch"),
        0xDEAD_BEEF,
    )

    # The multi-field control register: two fields, one register.
    do_op(True, ADDR_CTRL, (0xA << 4) | 0x1, label="write ctrl")
    ctrl = do_op(False, ADDR_CTRL, label="read ctrl")
    check("ctrl value", ctrl, (0xA << 4) | 0x1)
    check("ctrl.enable", ctrl & 0x1, 0x1)
    check("ctrl.mode", (ctrl >> 4) & 0xF, 0xA)

    # status is writable too, so the same round trip applies.
    do_op(True, ADDR_STATUS, (0x1 << 4) | 0x5, label="write status")
    check(
        "status write/read",
        do_op(False, ADDR_STATUS, label="read status"),
        (0x1 << 4) | 0x5,
    )

    print()
    if FAILURES:
        print(f"TEST_FAIL count={len(FAILURES)}")
        for f in FAILURES:
            print("  " + f)
        return
    print("TEST_PASS")


# No call here on purpose. The SV side reaches this module through
# py_task(get_type_name(), "main", ...): py_task imports the module and then
# calls its "main" attribute. A bare main() at module scope therefore ran
# the whole test a second time, at import - 7 operations became 14, two
# sequences in flight per operation, and every read-back raced a sequence
# that had not run yet.
