"""The UVM version compatibility matrix, as pytest.

Two legs, one table. The verilator leg lints (see the lint target in
test/base_test/Makefile) because upstream UVM only gains a Verilator backend
in 2020-3.2; the xezim leg runs the base test against each version. The mode
is what each marker selects, and it decides both the command and the UVM_HOME
shape the Makefile wants.

Every combination carries the outcome it has today, measured rather than
assumed, and script/uvm_compat_check.sh compares the two: the test passes when
they agree, so a known gap stays quiet and either kind of change - a version
that starts failing, or one that starts passing - turns the job red.

    pytest -m lint -n auto test/uvm_compat   # the verilator leg
    pytest -m run  -n auto test/uvm_compat   # the xezim leg
"""

import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "script" / "uvm_compat_check.sh"
UVM_REPO = "https://github.com/chipsalliance/uvm-verilator.git"
UVM_ROOT = Path(os.environ.get("UVM_COMPAT_UVM_ROOT") or "/tmp/uvm-compat")

# tag, expected outcome. The xezim list is a subset of the verilator one: it
# runs the base test, which needs a version with a Verilator HDL backend,
# while every version can be linted.
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
    ("uvm-2017-0.9", "fail"),
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
            ["git", "clone", "--quiet", "--depth", "1", "--branch", tag,
             UVM_REPO, str(staging)],
            check=True,
            capture_output=True,
            text=True,
        )
        # Another worker may have been cloning the same tag in parallel; both
        # clones are of the same content, so losing one is harmless.
        try:
            os.replace(staging, dest)
        except OSError:
            shutil.rmtree(staging, ignore_errors=True)
    except subprocess.CalledProcessError as e:
        shutil.rmtree(staging, ignore_errors=True)
        pytest.fail(f"cannot clone {tag} from {UVM_REPO}: {e.stderr}", pytrace=False)
    return dest


def _check(sim, tag, expect, mode):
    # Before anything expensive: a leg without its toolchain must fail, not
    # skip - otherwise a broken workflow goes quietly green.
    if mode == "run" and not os.environ.get("XEZIM_PREFIX"):
        pytest.fail("XEZIM_PREFIX is unset - the xezim leg needs its build", pytrace=False)
    root = _checkout(tag)
    # The two Makefiles want different shapes: the verilator leg is given the
    # src directory itself, the xezim one its parent, which it appends /src to.
    home = root / "src" if mode == "lint" else root
    result = subprocess.run(
        [str(SCRIPT), sim, tag, expect, mode],
        cwd=ROOT,
        env={**os.environ, "UVM_HOME": str(home)},
        capture_output=True,
        text=True,
        check=False,  # the assertion below is the check
    )
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.lint
@pytest.mark.parametrize("tag,expect", VERILATOR, ids=[t for t, _ in VERILATOR])
def test_verilator_lint(tag, expect):
    _check("verilator", tag, expect, "lint")


@pytest.mark.run
@pytest.mark.parametrize("tag,expect", XEZIM, ids=[t for t, _ in XEZIM])
def test_xezim_run(tag, expect):
    _check("xezim", tag, expect, "run")
