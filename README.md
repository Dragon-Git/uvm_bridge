# uvm-bridge Documentation

English | [简体中文](README-zh.md)

[![CI](https://github.com/Dragon-Git/uvm_bridge/actions/workflows/test.yml/badge.svg)](https://github.com/Dragon-Git/uvm_bridge/actions/workflows/test.yml)
[![Ask DeepWiki](https://deepwiki.com/badge.svg)](https://deepwiki.com/Dragon-Git/uvm_bridge)
[![PyPI - Version](https://img.shields.io/pypi/v/svuvm)](https://pypi.org/project/svuvm)
[![Latest Release](https://img.shields.io/github/v/release/Dragon-Git/uvm_bridge?color=blue&label=Latest%20Release)](https://github.com/Dragon-Git/uvm_bridge/releases/latest)
[![GitHub deployments](https://img.shields.io/github/deployments/Dragon-Git/uvm_bridge/pypi)](https://github.com/Dragon-Git/uvm_bridge/deployments)
[![downloads](https://pepy.tech/badge/svuvm)](https://pepy.tech/project/svuvm)
[![PyPI downloads](https://img.shields.io/pypi/dm/svuvm)](https://pypi.org/project/svuvm)
[![Python 3.9–3.14](https://img.shields.io/badge/python-3.9%E2%80%933.14-blue)](https://pypi.org/project/svuvm)
[![Platform](https://img.shields.io/badge/platform-Linux%20x86__64%20%7C%20Linux%20arm64%20%7C%20macOS%20arm64-lightgrey)](https://pypi.org/project/svuvm)
[![Simulators](https://img.shields.io/badge/simulators-Verilator%205.x%20%7C%20xezim%200.11.2%20%7C%20VCS-brightgreen)](docs/simulators.md)
[![UVM](https://img.shields.io/badge/UVM-1.2%20%7C%202017%20%7C%202020-informational)](docs/uvm-version-compatibility.md)
[![Stars](https://img.shields.io/github/stars/Dragon-Git/uvm_bridge)](https://github.com/Dragon-Git/uvm_bridge/stargazers)
[![Issues](https://img.shields.io/github/issues/Dragon-Git/uvm_bridge)](https://github.com/Dragon-Git/uvm_bridge/issues)
[![Open PRs](https://img.shields.io/github/issues-pr/Dragon-Git/uvm_bridge)](https://github.com/Dragon-Git/uvm_bridge/pulls)
[![Contributors](https://img.shields.io/github/contributors/Dragon-Git/uvm_bridge)](https://github.com/Dragon-Git/uvm_bridge/graphs/contributors)
[![Last commit](https://img.shields.io/github/last-commit/Dragon-Git/uvm_bridge)](https://github.com/Dragon-Git/uvm_bridge/commits/main)
[![Language count](https://img.shields.io/github/languages/count/Dragon-Git/uvm_bridge?logo=python)](https://github.com/Dragon-Git/uvm_bridge)

## Overview

svuvm is a hardware verification framework that allows users to call SystemVerilog UVM common APIs in Python to write test cases or dynamically configure environments, thereby saving compilation time and improving development efficiency. 
Compared to mainstream Python-based hardware verification frameworks like cocotb, svuvm has better compatibility with the SystemVerilog UVM framework, can make full use of commercial VIPs and rich Python ecosystems based on UVM, and does not destructively impact existing UVM-based verification environments. Users can freely choose to write some functions in Python without affecting other users who use SystemVerilog in the environment.

## Highlights
- Support writing SystemVerilog UVM test cases in Python and dynamically configuring environments
- Significantly reduce the number of compilations
- Can utilize the rich ecosystem of Python
- Compatible with the standard UVM framework, can make full use of the commercial VIP ecosystem
- Convenient for existing UVM users to migrate

## Supported UVM versions

Every version below is exercised in CI on every push; the per-version detail -
what fails, and which API is missing when it does - is in
[docs/uvm-version-compatibility.md](docs/uvm-version-compatibility.md).

| UVM | Full run (xezim) | Lint (Verilator) |
| --- | --- | --- |
| 1.2 | yes | yes |
| IEEE 1800.2-2017 (0.9, 1.0, 1.1) | yes | yes |
| IEEE 1800.2-2020 (1.0 … 3.2) | yes | yes |
| 1.1a, 1.1d | – | yes |
| 1.0p1, 1.1b, 1.1c | – | no |

The version matrix lints the bridge against each UVM release on Verilator rather than
building and running it, because upstream UVM gains a Verilator HDL backend only at
2020-3.2; the regular Verilator test job does build and run. 1.0p1 lacks three APIs the
bridge uses; 1.1b and 1.1c fail on defects in UVM itself. All three are upstream, and none
is worked around here. The 1.0 and 1.1 releases cannot run under xezim at all - their DPI
source layout predates 1.2, which the xezim adapter is written against.

## Simulators

`python -m svuvm.config` prints the three things a simulator needs - the bridge's SV
package, the compiled `_svuvm.so`, and Python's linker flags - so wiring it in is one
line added to the command you already have.

| Simulator | Full API | Notes |
| --- | --- | --- |
| Verilator | yes | a build with suspendable DPI exports ([PR #8863](https://github.com/verilator/verilator/pull/8863), merged 2026-11-12) - a nightly containing it, or any later stable release; add `-DVERILATOR` and use the `Dragon-Git/uvm-verilator` fork for UVM |
| xezim | yes | loads the bridge with `--dpi-lib` instead of linking |
| VCS | yes | add the same line, do **not** define `VERILATOR`, and pick UVM 1.2 or later with `-ntb_opts uvm-1.2` (the bare `-ntb_opts uvm` gives an older bundled UVM) |

All three paths need UVM 1.2 or later: the 1.0 and 1.1 releases predate the DPI source
layout the adapter is written against. Under VCS you otherwise keep your own UVM setup and
upstream Accellera UVM as-is - the fork only supplies UVM's Verilator HDL backend. Questa
and Xcelium need no separate write-up: nothing in the bridge is conditioned out for them, so
the VCS path applies. CI exercises the Verilator and xezim paths. Per-simulator commands are
in [docs/simulators.md](docs/simulators.md).

Verilator needs a build that includes suspendable DPI exports. Exported tasks may then wait
or delay, which is what lets `write_reg`, `read_reg`, `check_reg`, `mirror_reg`, `start_seq`,
the `wait_*` family, `barrier_wait`, `wait_unit` and `run_test_wrap` run on Verilator with the
full API. The feature landed in [PR #8863](https://github.com/verilator/verilator/pull/8863)
on 2026-11-12: use a nightly containing it, or any stable release published after it.
5.054 and earlier do not have it.

## Installation

### Dependencies:
- Python 3.9.0+
- nanobind, pyslang (not required at runtime)
### Commands:
```sh
pip install svuvm
```

## Compilation

The compilation command needs to add `$(python -m svuvm.config)`

## Quick Reference

- Write register: svuvm.write_reg("rm.reg_a", 0x12345678)
- Read register: data = svuvm.read_reg("rm.reg_a")
- Check register: svuvm.check_reg("rm.reg_a", 0x12345678)
- Start sequence: svuvm.start_seq("my_seq", "uvm_test_top.m_env.m_agent.my_sqr")
- Wait for 500 time units: svuvm.wait_unit(500)
- Force signal: svuvm.uvm_hdl_force("tb.dut.sig", svuvm.vpi.VpiVecVal(0,1))
- Release signal: svuvm.uvm_hdl_release("tb.dut.sig")
- Read signal: data = svuvm.uvm_hdl_read("tb.dut.sig")
- Print info: svuvm.uvm_info("msg", svuvm.UVM_LOW)
- Print error: svuvm.uvm_error("msg")
  
## Usage Example

### Python entry points

Both entries import the Python module named after the test type and call `func_name` in it.
Pick by the UVM phase:

| SV entry | DPI declaration | Phase | Python APIs |
| --- | --- | --- | --- |
| `py_func(name, func_name="main", mod_paths="")` | import `function int` | `build_phase`, `connect_phase` (function phases) | zero-time only |
| `py_task(name, func_name="main", mod_paths="")` | import `task` | `main_phase`, `run_phase`, `process_pool` | full API: registers, event waits, `start_seq`, `barrier_wait`, `wait_unit` |

IEEE 1800-2023 35.8 does not allow a time-consuming exported task in an import function
context, so keep `build_phase`/`connect_phase` callbacks zero-time. `py_task` forwards to
`py_func` on the C side; both return `int` (always 0). When calling `py_func` as a statement,
write `void'(py_func(...))` to discard the result. `call_py_func` is deprecated and still
uses `py_func`. Register calls resolve through the model installed by
`set_top_reg_block_by_path()` (a.k.a. `reg_operator::set_top_reg_block()`), so register it
before the first access. See [docs/simulators.md](docs/simulators.md) for the ABI details.

### Start Python function in SV
```systemverilog
// top.sv
module top ();
    import uvm_pkg::*;
    `include "uvm_macros.svh"
    import python_bridge_pkg::*;

    class example_test extends uvm_test;
        `uvm_component_utils(example_test)
        `uvm_new_func

        virtual task main_phase(uvm_phase phase);
            phase.raise_objection(this);
            py_task(get_type_name(), "main", dirname(`__FILE__));
            phase.drop_objection(this);
        endtask
    endclass

    logic clk/*verilator public_flat*/ = 1'b0;
    always #5 clk = ~clk;

    initial begin 
        run_test();
    end
endmodule
```
Call API in Python
```python
# example_test.py
import svuvm

def main():
    svuvm.uvm_info("example_test",svuvm.UVM_LOW)
```
### Compilation command

```bash
# Requires Verilator with suspendable DPI exports (PR #8863, 2026-11-12):
# a nightly containing it, or a stable release published after it.
git clone https://github.com/Dragon-Git/uvm-verilator.git # UVM with a Verilator HDL backend
mkdir -p build

# svuvm.config prints its linker flag value in quotes, which a plain command
# substitution does not re-parse; eval into an array and expand that instead.
eval "SVUVM_ARGS=($(python -m svuvm.config))"

verilator -j "$(nproc)" --vpi --binary -top top -Mdir build --output-groups "$(nproc)" \
+incdir+"$PWD/uvm-verilator/src" "$PWD/uvm-verilator/src/uvm_pkg.sv" \
"${SVUVM_ARGS[@]}" "$PWD/top.sv" \
-Wno-lint -Wno-style -Wno-SYMRSVDWORD -Wno-IGNOREDRETURN -Wno-CONSTRAINTIGN -Wno-ZERODLY \
"$PWD/uvm-verilator/src/dpi/uvm_dpi.cc" \
-CFLAGS "-I$PWD/uvm-verilator/src/dpi -I$PWD/inc -DVERILATOR"

PYTHONPATH=$PWD ./build/Vtop +UVM_TESTNAME=example_test
```

`PYTHONPATH` must point at the test module's directory: that directory does not otherwise
reach `sys.path`, and the bridge imports the module named after the test type from there.

Other simulators (xezim, VCS) take the same `svuvm.config` output; per-simulator commands
are in [docs/simulators.md](docs/simulators.md).
