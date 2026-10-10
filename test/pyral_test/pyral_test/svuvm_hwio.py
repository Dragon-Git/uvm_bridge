"""A PyRAL HWIO whose every access is one UVM sequence.

Gives the generated register model a backend inside the simulator: each
hardware access the model makes becomes

    RAL -> HWIO -> DPI -> UVM sequencer -> driver -> APB -> RTL

by staging the operation in the UVM config_db, calling start_seq() to run
reg_seq on the agent's sequencer, and reading the result back out of the
same database. The sequence's driver is what performs the APB transfer.

Subclasses HWIO directly rather than reaching for one of the runtime's own
implementations: peakrdl_pyral_runtime.hwio deliberately exports only HWIO
(see its __init__.py), and _read_impl/_write_impl are all a subclass has to
provide - read_list, the byte accessors and the async variants are built on
top of them.
"""

from peakrdl_pyral_runtime.hwio import HWIO

from svuvm import _svuvm as svuvm

SEQ_PATH = "uvm_test_top.m_agent.m_sqr"

ACCESS_SIZE = 4


class SvuvmHWIO(HWIO):
    def __init__(self, seq_path: str = SEQ_PATH, *, offset: int = 0) -> None:
        # No reads or writes happen during __init__ - the path is only
        # stored - so it is available by the time they run.
        self._seq_path = seq_path
        super().__init__(offset)

    def _op(self, is_write: bool, addr: int, wdata: int = 0) -> int:
        """Run one register operation as one UVM sequence and return the
        value read back (0 for writes)."""
        label = f"{'wr' if is_write else 'rd'} 0x{addr:08x}"

        svuvm.set_config_int("", "*", "op_addr", addr & 0xFFFF_FFFF)
        svuvm.set_config_int("", "*", "op_wdata", wdata & 0xFFFF_FFFF)
        svuvm.set_config_int("", "*", "op_is_write", 1 if is_write else 0)
        svuvm.set_config_string("", "*", "op_label", label)

        # rand_en=0: the sequence fills the item explicitly. background=0:
        # block until the transfer completes, so the result is already in
        # the database when it is read back below.
        svuvm.start_seq("reg_seq", self._seq_path, 0, 0)

        err = svuvm.get_config_int("", "*", "res_err")
        if err:
            raise RuntimeError(f"APB error response for {label}")
        return svuvm.get_config_int("", "*", "res_rdata")

    def _read_impl(self, addr: int, size: int) -> int:
        if size != ACCESS_SIZE:
            raise NotImplementedError(
                f"the agent only does {ACCESS_SIZE}-byte accesses, got {size}"
            )
        return self._op(False, addr)

    def _write_impl(self, addr: int, value: int, size: int) -> None:
        if size != ACCESS_SIZE:
            raise NotImplementedError(
                f"the agent only does {ACCESS_SIZE}-byte accesses, got {size}"
            )
        self._op(True, addr, value)
