"""The UVM version compatibility matrix, as pytest.

Two legs, one table. The verilator leg lints (see base_test/sim_runner.py)
because upstream UVM only gains a Verilator backend in 2020-3.2, so earlier
versions cannot be built at all; the xezim leg runs the base test against each
version.

Every combination carries the outcome it has today, measured rather than
assumed, and the test passes when the two agree. That makes this a "nothing
changed" check rather than an "everything passes" one, which is what a
compatibility matrix is for: a known gap stays quiet, and either kind of change
- a version that starts failing, or one that starts passing - turns the job red.

    pytest -m lint -n auto test/uvm_compat   # the verilator leg
    pytest -m run  -n auto test/uvm_compat   # the xezim leg
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
UVM_REPO = "https://github.com/chipsalliance/uvm-verilator.git"
UVM_ROOT = Path(os.environ.get("UVM_COMPAT_UVM_ROOT") or "/tmp/uvm-compat")
LOG_DIR = Path(os.environ.get("RUNNER_TEMP") or "/tmp")

sys.path.insert(0, str(ROOT / "test" / "base_test"))
import sim_runner  # noqa: E402

# Written by base_test.py on its last line; xezim also stops silently at
# --max-time, so a zero exit alone does not mean the test ran to the end.
FINISHED = "所有新增API测试完成"

# tag, expected outcome. The xezim list is a subset of the verilator one: the
# base test needs a UVM whose DPI source layout xezim's adapter can compile,
# which means 1.2 or later, while every version can be linted.
VERILATOR = [
    ("uvm-1.0p1", "fail"),
    ("uvm-1.1a", "pass"),
    ("uvm-1.1b", "fail"),
    ("uvm-1.1c", "fail"),
    ("uvm-1.1d", "pass"),
    ("uvm-1.2", "pass"),
    ("uvm-2017-0.9", "pass"),
    ("uvm-2017-1.0", "pass"),
    ("uvm-2017-1.1", "pass"),
    ("uvm-2020-1.0", "pass"),
    ("uvm-2020-1.1", "pass"),
    ("uvm-2020-2.0", "pass"),
    ("uvm-2020-3.0", "pass"),
    ("uvm-2020-3.1", "pass"),
    ("uvm-2020-3.2", "pass"),
]
XEZIM = [
    ("uvm-1.2", "pass"),
    ("uvm-2017-0.9", "pass"),
    ("uvm-2017-1.0", "pass"),
    ("uvm-2017-1.1", "pass"),
    ("uvm-2020-1.0", "pass"),
    ("uvm-2020-1.1", "pass"),
    ("uvm-2020-2.0", "pass"),
    ("uvm-2020-3.0", "pass"),
    ("uvm-2020-3.1", "pass"),
    ("uvm-2020-3.2", "pass"),
]


def _checkout(tag):
    """A shallow clone of one version, cloned once however many workers ask."""
    dest = UVM_ROOT / tag
    if (dest / "src" / "uvm_pkg.sv").exists():
        return dest
    UVM_ROOT.mkdir(parents=True, exist_ok=True)
    staging = UVM_ROOT / f".{tag}.{os.getpid()}"
    shutil.rmtree(staging, ignore_errors=True)
    try:
        subprocess.run(
            ["git", "clone", "--quiet", "--depth", "1", "--branch", tag, UVM_REPO, str(staging)],
            check=True,
            capture_output=True,
            text=True,
        )
        # Another worker may have been cloning the same tag in parallel; both
        # clones hold the same content, so losing one is harmless.
        try:
            os.replace(staging, dest)
        except OSError:
            shutil.rmtree(staging, ignore_errors=True)
    except subprocess.CalledProcessError as e:
        shutil.rmtree(staging, ignore_errors=True)
        pytest.fail(f"cannot clone {tag} from {UVM_REPO}: {e.stderr}", pytrace=False)
    return dest


def _sim(sim, mode, tag, home, log):
    """Run one simulator invocation into its own log; return (exit code, log text).

    The build directory is per version because pytest runs versions in
    parallel: a shared one would let a worker's objects - or its clean - land
    in another's build. ``home`` is passed explicitly, not through the
    environment, so the version under test is used instead of whatever
    XEZIM_PREFIX points at. The directory is cleared first so an earlier run
    of the same version cannot be reused - the UVM sources live outside the
    checkout and so look unchanged.
    """
    if mode == "lint":
        # Elaborate only: uvm_hdl.c #errors without a Verilator backend, so a
        # build is impossible before 2020-3.2. Lint still compares the
        # bridge's SystemVerilog surface, which is the signal this matrix is
        # after, and it takes seconds.
        build = None
    elif mode == "run" and sim == "xezim":
        build = ROOT / "test" / "base_test" / f"build.uvm-compat.{tag}"
    elif mode == "run":
        build = ROOT / f"build.uvm-compat.{tag}"
    else:
        pytest.fail(f"unknown combination {sim}/{mode}", pytrace=False)

    if build is not None:
        shutil.rmtree(build, ignore_errors=True)

    if mode == "lint":
        rc, text = sim_runner.lint(uvm_home=home)
    else:
        rc, text = sim_runner.run(sim, uvm_home=home, build_dir=build)
    log.write_text(text, encoding="utf-8", errors="replace")
    return rc, text


def _check(sim, tag, expect, mode):
    if mode == "run" and not os.environ.get("XEZIM_PREFIX") and sim == "xezim":
        # A leg without its toolchain must fail rather than skip: a broken
        # workflow has to be visible.
        pytest.fail("XEZIM_PREFIX is unset - the xezim leg needs its build", pytrace=False)

    root = _checkout(tag)
    # The two legs point at different things: verilator is given the src
    # directory itself, while xezim is given its parent and appends /src.
    home = root / "src" if mode == "lint" else root

    log = LOG_DIR / f"uvm-compat.{tag}.{sim}.{mode}.log"
    rc, text = _sim(sim, mode, tag, home, log)

    # A run counts only when the test reached its last line; lint is a build
    # that either elaborates or does not.
    passed = rc == 0 and (mode == "lint" or FINISHED in text)
    actual = "pass" if passed else "fail"

    if actual == expect:
        if actual == "fail":
            head = [ln for ln in text.splitlines() if ln.startswith(("%Error", "UVM_FATAL @"))][:3]
            print(f"{sim} / {tag} ({mode}): known gap, unchanged" + ("".join(f"\n  {ln}" for ln in head)))
        return

    tail = "\n".join(text.splitlines()[-40:])
    if expect == "pass":
        pytest.fail(
            f"{sim} / {tag} ({mode}) regressed: expected to pass, simulator exited {rc}.\n"
            f"--- last 40 lines of {log} ---\n{tail}",
            pytrace=False,
        )
    pytest.fail(
        f"{sim} / {tag} ({mode}) now passes: update VERILATOR/XEZIM in {Path(__file__).name}.\n"
        f"--- last 40 lines of {log} ---\n{tail}",
        pytrace=False,
    )


@pytest.mark.lint
@pytest.mark.parametrize("tag,expect", VERILATOR, ids=[t for t, _ in VERILATOR])
def test_verilator_lint(tag, expect):
    _check("verilator", tag, expect, "lint")


@pytest.mark.run
@pytest.mark.parametrize("tag,expect", XEZIM, ids=[t for t, _ in XEZIM])
def test_xezim_run(tag, expect):
    _check("xezim", tag, expect, "run")
