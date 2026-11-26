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
expected access trace, the result JSON and the reporting - comes from ../fw/,
which test/unicorn_test uses too.

The module is called reg_test because that is the name top.sv's test class
carries, and the SV side reaches Python through
py_task(get_type_name(), "main", ...) - which imports a module by that name
and calls its main(). It shares test/pyral_test/sv/top.sv for the same
reason: the testbench around the register block is identical, only what
drives the bus differs.

Timeouts are application-level on purpose: xezim has ``--max-time`` but
verilator does not, so both backends rely on ``RENODE_ACCEPT_TIMEOUT`` and
``RENODE_TEST_TIMEOUT`` here. Every resource is closed in ``finally`` blocks,
including the failure paths, and the result JSON is always published.

    seq path: uvm_test_top.m_agent.m_sqr
"""

from __future__ import annotations

import os
import socket
import subprocess
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_FW_DIR = _HERE.parent / "fw"
_TEST_ROOT = _HERE.parent
for _path in (str(_FW_DIR), str(_TEST_ROOT)):
    if _path not in sys.path:
        sys.path.insert(0, _path)

from layout import is_checksum_store, is_done_store  # noqa: E402
from register_access import (  # noqa: E402
    begin_run,
    check_read_sum,
    compare_trace,
    finish,
    firmware_image,
    one_sequence,
    record_abort,
    report,
)

DEFAULT_ACCEPT_TIMEOUT = 30.0
DEFAULT_TEST_TIMEOUT = 300.0
TERMINATE_GRACE = 5.0

CONTINUE = "0"
FINISHED = "OK"


def _env_float(name: str, default: float) -> float:
    """Read a positive timeout from the environment, failing loudly if invalid."""
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return default
    try:
        value = float(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be a number of seconds, got {raw!r}") from exc
    if value <= 0:
        raise ValueError(f"{name} must be positive, got {value}")
    return value


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

    try:
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
            except socket.timeout:
                # A stalled peer is an infrastructure failure, not a bad
                # register value: let main() abort with a bounded timeout.
                raise
            except Exception as exc:  # noqa: BLE001 -- reported to the emulator
                reply(f"E {exc}")
    finally:
        reader.close()

    return checksum


class Driver:
    """The Renode process, started with the port this side is listening on."""

    def __init__(self, listener: socket.socket, timeout: float) -> None:
        """Spawn the helper; the caller must already be bound and listening.

        Args:
            listener: Listening socket whose ephemeral port is passed over.
            timeout: Seconds allowed for the firmware and process shutdown.
        """
        port = listener.getsockname()[1]
        # Renode needs pyrenode3, which the simulator's own interpreter does not
        # have; the suite config injects the interpreter that has it.
        python = os.environ.get("RENODE_TEST_PYTHON", "python3")
        platform = os.environ.get("RENODE_TEST_PLATFORM", str(_HERE / "platform" / "renode_test.repl"))
        self.timeout = timeout
        report(f"renode: {os.environ.get('PYRENODE_PATH', 'PYRENODE_PATH unset')}")
        self.process = subprocess.Popen(
            [
                *python.split(),
                str(_HERE / "renode_runner.py"),
                "--port",
                str(port),
                "--platform",
                platform,
                "--firmware",
                firmware_image(str(_HERE)),
                "--timeout",
                str(timeout),
            ],
            stdin=subprocess.DEVNULL,
        )

    def wait(self) -> None:
        """Wait for a clean exit, bounding the wait and always reaping the child."""
        try:
            rc = self.process.wait(timeout=self.timeout)
        except subprocess.TimeoutExpired as exc:
            self.cleanup()
            raise RuntimeError(
                f"the Renode process did not exit within {self.timeout:g}s"
            ) from exc
        if rc != 0:
            raise RuntimeError(f"the Renode process exited with {rc}")

    def cleanup(self) -> None:
        """Terminate the child, escalating to kill if it ignores SIGTERM."""
        if self.process.poll() is not None:
            return
        self.process.terminate()
        try:
            self.process.wait(timeout=TERMINATE_GRACE)
        except subprocess.TimeoutExpired:
            self.process.kill()
            self.process.wait(timeout=TERMINATE_GRACE)


def main() -> None:
    """Serve the firmware's MMIO accesses, with bounded waits and full cleanup."""
    begin_run()
    accept_timeout = _env_float("RENODE_ACCEPT_TIMEOUT", DEFAULT_ACCEPT_TIMEOUT)
    test_timeout = _env_float("RENODE_TEST_TIMEOUT", DEFAULT_TEST_TIMEOUT)

    trace: list[tuple[str, int, int]] = []
    checksum: int | None = None
    listener: socket.socket | None = None
    connection: socket.socket | None = None
    driver: Driver | None = None

    # Binding before starting Renode means the driver connects to a port that
    # is already listening, so neither side needs a retry loop. The connection
    # waits in the backlog until accept() runs.
    try:
        listener = socket.socket()
        listener.bind(("127.0.0.1", 0))
        listener.listen(1)
        report(f"firmware: {Path(firmware_image(str(_HERE))).name}")

        listener.settimeout(accept_timeout)
        driver = Driver(listener, test_timeout)
        try:
            connection, _ = listener.accept()
        except socket.timeout as exc:
            raise RuntimeError(
                f"Renode did not connect to port {listener.getsockname()[1]} "
                f"within {accept_timeout:g}s"
            ) from exc
        finally:
            listener.settimeout(None)
        # Bound round trips too: verilator has no --max-time, so this is the
        # only backstop if the peer stops answering halfway through the trace.
        connection.settimeout(test_timeout)
        try:
            checksum = serve(connection, trace)
        finally:
            connection.close()
            connection = None
        driver.wait()

        compare_trace(trace)
        check_read_sum(checksum)
    except BaseException as exc:
        # An aborted session is not a single bad check: mark the cases that
        # never ran as failed so replay cannot pass the run silently.
        record_abort(f"renode session: {type(exc).__name__}: {exc}")
        raise
    finally:
        if connection is not None:
            connection.close()
        if driver is not None:
            driver.cleanup()
        if listener is not None:
            listener.close()
        # On every path, including accept timeout and process failure.
        finish()


# No call at module scope on purpose: the SV side imports this module and then
# calls its main() attribute, so a bare main() here would run the whole test a
# second time, at import.
