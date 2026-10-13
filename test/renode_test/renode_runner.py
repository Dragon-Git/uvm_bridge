"""Run the firmware under Renode, with the register block served by xezim.

This is the Renode half of test/renode_test. It runs in a plain CPython with
pyrenode3, Renode's own Python binding, which loads Renode's .NET assemblies
into this process - so the emulated bus and the code below are in the same
interpreter, and a hook can be a Python function.

    firmware -> MMIO -> Renode -> this process --socket--> reg_test.py
                                                              |
                     UVM sequencer -> driver -> APB -> RTL  <-+

The register window is an ordinary Memory peripheral in the platform
description. Two hooks turn it into the APB agent:
SetHookAfterPeripheralRead returns the value the register block produced - the
read hook runs before the load completes, so the firmware's own load is what
sees it - and SetHookBeforePeripheralWrite is told what the firmware stores.
Both block until the xezim side answers, which is what keeps the emulated time
from running ahead of the RTL.

The two ends split the work the same way they do in test/unicorn_test: this
side only knows that accesses inside the window are to be forwarded, and the
test side knows which offsets are registers and which two are the firmware's
own markers. So a write's reply is either "0" to carry on or "OK" when the
firmware has announced it is finished, which is the only thing this side needs
to act on.

Renode's own Python peripherals are IronPython, and the hooks above are the
CPython alternative: pythonnet converts these plain functions to the delegates
the bus expects, with no IronPython involved.

The wire format is one request per line, ASCII:

    ->  R <offset>            <- <value>   what the register block returned
    ->  W <offset> <value>    <- <ack>     "0", or "OK" to stop the emulator

with an error answered by a line starting with "E ".
"""

from __future__ import annotations

import argparse
import os
import socket
import sys
import threading

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "fw"))

import pyrenode3  # noqa: E402, F401 -- importing it loads Renode's assemblies
from pyrenode3 import wrappers  # noqa: E402
from System import Func, Int64, UInt32  # noqa: E402

from layout import STACK_TOP  # noqa: E402

CONTINUE = "0"
FINISHED = "OK"

class Link:
    """The socket to the xezim side, and the errors it reports."""

    def __init__(self, port: int) -> None:
        self.sock = socket.create_connection(("127.0.0.1", port), timeout=300)
        self.reader = self.sock.makefile("r", buffering=1)

    def request(self, line: str) -> str:
        self.sock.sendall((line + "\n").encode())
        reply = self.reader.readline()
        if not reply:
            raise RuntimeError(f"the register server closed the connection on {line!r}")
        reply = reply.strip()
        if reply.startswith("E "):
            raise RuntimeError(f"{line}: {reply[2:]}")
        return reply

    def close(self) -> None:
        self.reader.close()
        self.sock.close()

class FirmwareRun:
    """Renode running the firmware, with its register window served over a socket."""

    def __init__(self, platform: str, firmware: str, port: int) -> None:
        self.link = Link(port)
        self.accesses = 0
        self.done = threading.Event()
        self.error: BaseException | None = None

        emulation = wrappers.Emulation()
        self.machine = emulation.add_mach("renode_test")
        self.machine.load_repl(platform)
        self.monitor = wrappers.Monitor()
        self.monitor.Machine = self.machine.internal

        bus = self.machine.sysbus
        regs = bus.get_child("regs")
        # The generic argument is the access width: the delegates are
        # Func<T, long, T>, taking (value, offset) and returning the value the
        # bus should use.
        bus.internal.SetHookAfterPeripheralRead[UInt32](
            regs.internal, Func[UInt32, Int64, UInt32](self._on_read), None
        )
        bus.internal.SetHookBeforePeripheralWrite[UInt32](
            regs.internal, Func[UInt32, Int64, UInt32](self._on_write), None
        )

        self.machine.load_binary(firmware, 0)

    def _on_read(self, value: int, offset: int) -> int:
        try:
            data = int(self.link.request(f"R {offset:#x}"), 0)
        except BaseException as exc:  # noqa: BLE001 -- reported on the main thread
            self._fail(exc)
            return 0
        self.accesses += 1
        return data & 0xFFFF_FFFF

    def _on_write(self, value: int, offset: int) -> int:
        try:
            reply = self.link.request(f"W {offset:#x} {value & 0xFFFF_FFFF:#x}")
        except BaseException as exc:  # noqa: BLE001
            self._fail(exc)
            return value
        if reply == FINISHED:
            # The firmware's done marker. It is not a register write, so the
            # test side answers it differently and the trace gains nothing.
            self.done.set()
        elif reply == CONTINUE:
            self.accesses += 1
        else:
            self._fail(RuntimeError(f"unexpected acknowledgement {reply!r}"))
        return value

    def _fail(self, exc: BaseException) -> None:
        """A hook cannot raise into the bus, so park the failure for the main
        thread and stop the emulation."""
        if self.error is None:
            self.error = exc
        self.done.set()

    def run(self, timeout: float) -> None:
        # A bare-metal image has no startup code: the emulator's reset vector is
        # what the firmware wants, and the platform's CPU already starts there.
        # The stack, though, has to be given to it - see test/fw/layout.py.
        self.monitor.execute(f"cpu SP {STACK_TOP:#x}")
        self.monitor.execute("start")

        if not self.done.wait(timeout):
            self.monitor.execute("pause")
            raise RuntimeError(f"the firmware did not reach its done marker within {timeout:g}s")

        self.monitor.execute("pause")
        if self.error is not None:
            raise self.error

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--platform", required=True)
    parser.add_argument("--firmware", required=True)
    parser.add_argument("--timeout", type=float, default=120.0)
    args = parser.parse_args()

    run = FirmwareRun(args.platform, args.firmware, args.port)
    run.run(args.timeout)
    run.link.close()
    print(f"firmware: {run.accesses} register accesses", file=sys.stderr, flush=True)

if __name__ == "__main__":
    main()
