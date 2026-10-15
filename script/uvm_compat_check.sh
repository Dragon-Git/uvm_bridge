#!/bin/sh
# Run one UVM version on one simulator, and check the result against what that
# combination is known to do.
#
#   uvm_compat_check.sh SIMULATOR UVM_TAG EXPECTED [MODE]
#
# MODE is "run" (the default) or "lint". Lint is for the Verilator leg, and is
# covered below.
#
# EXPECTED is "pass" or "fail" - what this combination does today, measured
# rather than assumed. The script exits 0 when the result matches, 1 when it
# does not, so a cell that is known to fail is green. That makes the caller a
# "nothing changed" check rather than an "everything passes" one, which is
# what a compatibility matrix is for: a known gap stays quiet, and a version
# that starts passing is reported instead of being swallowed.
#
# UVM_HOME must be set by the caller. The two legs want different things from
# it: the xezim Makefile appends /src to it, while the verilator one is given
# the src directory itself. XEZIM_PREFIX must be set too, for the xezim leg.
set -u

sim=$1
tag=$2
expect=$3
mode=${4:-run}

ROOT=$(cd "$(dirname "$0")/.." && pwd)
: "${UVM_HOME:?uvm_compat_check.sh needs UVM_HOME}"
: "${RUNNER_TEMP:=/tmp}"

# The two legs point UVM_HOME at different things, so accept either shape:
# the src directory itself (verilator) or its parent (xezim, whose Makefile
# appends /src).
if [ ! -f "$UVM_HOME/uvm_pkg.sv" ] && [ ! -f "$UVM_HOME/src/uvm_pkg.sv" ]; then
    echo "::error::no uvm_pkg.sv under $UVM_HOME"
    exit 1
fi

log="$RUNNER_TEMP/uvm-compat.$tag.$sim.$mode.log"

if [ "$mode" = lint ]; then
    # Elaborate only. The Verilator leg is checked this way rather than by
    # building: upstream UVM gains a Verilator HDL backend only in 2020-3.2,
    # and uvm_hdl.c #errors without one, so a build is impossible for the
    # earlier releases regardless of the bridge. Lint still compares the
    # bridge's SystemVerilog surface against each version, which is the
    # compatibility signal this matrix is after, and it takes seconds.
    make -f "$ROOT/test/base_test/Makefile" lint UVM_HOME="$UVM_HOME" > "$log" 2>&1
    rc=$?
    if [ $rc -eq 0 ]; then actual=pass; else actual=fail; fi
else
    # Both legs write into their own build directory, and the verilator one is
    # the repository root rather than the test's. Clearing it between versions
    # keeps a previous UVM's objects from being reused - easy to miss, because
    # the sources live outside the checkout and so look unchanged.
    rm -rf "$ROOT/build" "$ROOT/test/base_test/build"

    # UVM_HOME goes on the command line, not through the environment: the
    # Makefile assigns it with = rather than ?=, which an inherited value does
    # not override. Passing it in the environment silently runs whatever
    # XEZIM_PREFIX points at instead of the version under test.
    if [ "$sim" = xezim ]; then
        make -f "$ROOT/test/base_test/Makefile" SIM=xezim run \
            UVM_HOME="$UVM_HOME" ${XEZIM_PREFIX:+XEZIM_PREFIX="$XEZIM_PREFIX"} > "$log" 2>&1
    else
        make -f "$ROOT/test/base_test/Makefile" run UVM_HOME="$UVM_HOME" > "$log" 2>&1
    fi
    rc=$?

    if [ $rc -eq 0 ] && grep -q "所有新增API测试完成" "$log"; then
        actual=pass
    else
        actual=fail
    fi
fi

echo "$sim / $tag ($mode): expected $expect, got $actual (make exit $rc)"

if [ "$actual" = "$expect" ]; then
    if [ "$actual" = fail ]; then
        echo "known gap, unchanged:"
        grep -E "^%Error|UVM_FATAL @|not found|Fatal" "$log" | head -3 || true
    fi
    exit 0
fi

echo "--- last 40 lines of $log ---"
tail -40 "$log"
echo ""
if [ "$expect" = pass ]; then
    echo "::error::$sim / $tag ($mode) regressed: expected to pass but did not"
else
    echo "::error::$sim / $tag ($mode) now passes: update the expectation in the matrix"
fi
exit 1
