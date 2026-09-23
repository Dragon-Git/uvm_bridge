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
[![Platform](https://img.shields.io/badge/platform-Linux%20x86__64%20%7C%20macOS%20arm64-lightgrey)](https://pypi.org/project/svuvm)
[![Verilator](https://img.shields.io/badge/verilator-5.x-brightgreen)](https://github.com/verilator/verilator)
[![UVM](https://img.shields.io/badge/UVM-IEEE%201800.2--2020-informational)](https://github.com/Dragon-Git/uvm-verilator)
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
            py_func(get_type_name(), "main", dirname(`__FILE__));
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
git clone https://github.com/Dragon-Git/uvm-verilator.git # Workaround version, verilator has not fully supported UVM yet
mkdir build
verilator -j $(nproc) --vpi --binary -top top -Mdir build --output-groups $(($(nproc))) \
+incdir+$PWD/uvm-verilator/src $PWD/uvm-verilator/src/uvm_pkg.sv \
$(python -m svuvm.config) $PWD/top.sv \
-Wno-lint -Wno-style -Wno-SYMRSVDWORD -Wno-IGNOREDRETURN -Wno-CONSTRAINTIGN -Wno-ZERODLY \
$PWD/uvm-verilator/src/dpi/uvm_dpi.cc \
-CFLAGS "-I$PWD/uvm-verilator/src/dpi -I$PWD/inc -DVERILATOR" \

./build/Vtop +UVM_TESTNAME=example_test
```
