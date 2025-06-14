# Makefile

VERILATOR       = verilator
PYTHON          = python
COCOTB_LIB_DIR  = $(shell cocotb-config --lib-dir)
ROOT            = $(shell git rev-parse --show-toplevel)
BUILD_DIR       = build
UVM_HOME        = $(ROOT)/uvm-verilator/src
TEST_DIR        = $(ROOT)/test/cocotb_test
INCLUDE_DIRS    = +incdir+$(UVM_HOME)
UVM_PKG         = $(UVM_HOME)/uvm_pkg.sv
UVM_DPI         = $(UVM_HOME)/dpi/uvm_dpi.cc
SV_SOURCE       = $(TEST_DIR)/top.sv
SVUVM_CONFIG    = $(shell $(PYTHON) -m svuvm.config)
NPROC           = $(shell nproc 2>/dev/null || echo 10)

VERILATOR_FLAGS = -j $(NPROC) --vpi   -cc --exe --build --timing \
                  -top top -Mdir $(BUILD_DIR) \
                  --output-groups $(NPROC) \
				  -Wno-lint -Wno-style -Wno-SYMRSVDWORD -Wno-WIDTHTRUNC -Wno-WIDTHEXPAND \
				  -Wno-IGNOREDRETURN -Wno-CONSTRAINTIGN -Wno-ZERODLY -Wno-CASTCONST \

CXXFLAGS        = -CFLAGS "-I$(UVM_HOME)/dpi -I$(ROOT)/inc  -DVERILATOR" \
					-LDFLAGS "-Wl,-rpath,$(shell cocotb-config --lib-dir) \
          			-L$(shell cocotb-config --lib-dir) \
          			-lcocotbvpi_verilator" \
					$(shell cocotb-config --share)/lib/verilator/verilator.cpp

RUN_FLAGS       = +UVM_TESTNAME=base_test +UVM_NO_RELNOTES +UVM_OBJECTION_TRACE $(RUN_OPTS)

all: run

$(BUILD_DIR):
	mkdir -p $@

build: $(BUILD_DIR)
	$(VERILATOR) $(VERILATOR_FLAGS) $(INCLUDE_DIRS) $(UVM_DPI) \
	$(UVM_PKG) $(SVUVM_CONFIG) $(SV_SOURCE) $(CXXFLAGS) $(LDFLAGS)


run: build
	DYLD_LIBRARY_PATH=$(shell pip show pip | grep Location | awk '{print $$2}')/svuvm \
	PYTHONPATH=$(TEST_DIR) \
	PYGPI_PYTHON_BIN=$(shell which python3) \
	PYGPI_USERS=cocotb._init:init_package_from_simulation \
	COCOTB_TEST_MODULES=base_test \
	./$(BUILD_DIR)/Vtop $(RUN_FLAGS)

clean:
	rm -rf $(BUILD_DIR)/* *.pyc __pycache__

.PHONY: all build run clean