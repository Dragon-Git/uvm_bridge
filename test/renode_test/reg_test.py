"""Run the bare-metal firmware against the register block, through APB.

The firmware reaches the registers as memory-mapped I/O. Renode executes it,
in a separate process driven by this one over a socket, and every access
inside the register window is turned into one UVM sequence on the APB agent:

    firmware -> MMIO -> Renode -> socket -> here -> sequencer -> driver -> APB -> RTL

and the value the register block produced travels back the same way, so the
firmware's own load sees it. This is test/unicorn_test's arrangement with
Renode in place of unicorn: there the emulator is a CPython module in this
process and its hook calls one_sequence() directly; here it is a process of
its own, because Renode needs to load its .NET runtime and that is not
something to do inside the simulator's interpreter.

Everything that is not the emulator - the register map, the sequence, the
expected access trace, the reporting - comes from ../fw/, which
test/unicorn_test uses too.

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
import socket
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "fw"))

from layout import is_checksum_store, is_done_store  # noqa: E402
from register_access import (  # noqa: E402
    check_read_sum,
    compare_trace,
    finish,
    firmware_image,
    one_sequence,
    report,
)

HERE = Path(__file__).resolve().parent

# Seconds to wait for Renode to run the firmware, and to shut down afterwards.
# Generous: Renode has a .NET runtime to start before the firmware gets going,
# and the firmware's every access is a round trip through the RTL.
DEFAULT_TIMEOUT = 300.0

CONTINUE = "0"
FINISHED = "OK"

def serve(connection: socket.socket, trace: list[tuple[str, int, int]]) -> int | None:
    """Answer the Renode-side helper, one UVM sequence per register access.

    The wire format is documented in renode_runner.py. The helper knows only
    that accesses inside the window have to be forwarded; which offsets are
    registers, and which two are the firmware's own markers, is decided here.

    Returns the firmware's total of what it read, if it got that far.
    """
    reader = connection.makefile("r", buffering=1)
    checksum = None

    def reply(line: str) -> None:
        connection.sendall((line + "\n").encode())

    for line in reader:
        parts = line.split()
        offset = int(parts[1], 0)
        try:
            if parts[0] == "R":
                data = one_sequence(offset, is_write=False)
                trace.append(("R", offset, data))
                reply(f"{data:#x}")
            elif parts[0] == "W":
                value = int(parts[2], 0) & 0xFFFF_FFFF
                if is_checksum_store(offset):
                    # What the firmware made of the values it read. The one
                    # store that proves the whole round trip worked.
                    checksum = value
                    reply(CONTINUE)
                elif is_done_store(offset, value):
                    # The firmware is finished; the helper stops on this.
                    reply(FINISHED)
                    return checksum
                else:
                    one_sequence(offset, is_write=True, wdata=value)
                    trace.append(("W", offset, value))
                    reply(CONTINUE)
            else:
                raise RuntimeError(f"unrecognised request {line.strip()!r}")
        except Exception as exc:  # noqa: BLE001 -- reported to the emulator
            reply(f"E {exc}")

    return checksum

class Driver:
    """The Renode process, started with the port this side is listening on."""

    def __init__(self, listener: socket.socket) -> None:
        port = listener.getsockname()[1]
        # Renode needs pyrenode3, which the simulator's own interpreter does not
        # have; the Makefile passes the interpreter the test was started with.
        python = os.environ.get("RENODE_TEST_PYTHON", "python3")
        platform = os.environ.get("RENODE_TEST_PLATFORM", str(HERE / "platform" / "renode_test.repl"))

        report(f"renode: {os.environ.get('PYRENODE_PATH', 'PYRENODE_PATH unset')}")
        self.process = subprocess.Popen(
            [
                *python.split(),
                str(HERE / "renode_runner.py"),
                "--port",
                str(port),
                "--platform",
                platform,
                "--firmware",
                firmware_image(str(HERE)),
                "--timeout",
                os.environ.get("RENODE_TEST_TIMEOUT", str(DEFAULT_TIMEOUT)),
            ],
            stdin=subprocess.DEVNULL,
        )

    def wait(self) -> None:
        rc = self.process.wait(timeout=DEFAULT_TIMEOUT)
        if rc != 0:
            raise RuntimeError(f"the Renode process exited with {rc}")

def main() -> None:
    report(f"firmware: {Path(firmware_image(str(HERE))).name}")

    trace: list[tuple[str, int, int]] = []

    # Binding before starting Renode means the driver connects to a port that is
    # already listening, so neither side needs a retry loop. The connection
    # waits in the backlog until accept() runs.
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    listener.listen(1)
    try:
        driver = Driver(listener)
        connection, _ = listener.accept()
        try:
            checksum = serve(connection, trace)
        finally:
            connection.close()
        driver.wait()
    finally:
        listener.close()

    compare_trace(trace)
    check_read_sum(checksum)
    finish()

# No call at module scope on purpose: the SV side imports this module and then
# calls its main() attribute, so a bare main() here would run the whole test a
# second time, at import.
