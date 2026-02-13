# uvm-bridge Documentation

English | [简体中文](README-zh.md)

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
- pybind11, pyslang (not required at runtime)
### Commands:
- verilator
```sh
pip install .
```
- vcs  
```sh
CFLAGS="-DVCS -I $VCS_HOME/include" pip install .
```
- xcelium
```sh
CFLAGS="-DXCELIUM -I $XRUN_HOME/include" pip install .                                                                            
```
- questa
```sh
CFLAGS="-DMENTOR -I $MENTOR_HOME/include" pip install .                                                             
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
