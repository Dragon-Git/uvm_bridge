# Makefile

VERILATOR       = verilator
PYTHON          ?= python3
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

# cocotb 2.1.0 splits the simulator-side env var (GPI_USERS) from
# the pygpi-side env var (PYGPI_USERS) and the simulator binary
# now calls GpiCommon::gpi_load_users() at startup and aborts
# with "No GPI_USERS specified, exiting..." if GPI_USERS is
# unset. GPI_USERS is "<libpython>;<pygpi-entry-point>"; the
# two segments come from cocotb_tools.config. cocotb 2.0.1
# does not read GPI_USERS (GpiCommon::gpi_load_users was added
# in 2.1.0), so the extra env var is harmless there.
COCOTB_LIBPYTHON   = $(shell $(PYTHON) -m cocotb_tools.config --libpython 2>/dev/null)
COCOTB_PYGPI_ENTRY = $(shell $(PYTHON) -m cocotb_tools.config --pygpi-entry-point 2>/dev/null || true)
# cocotb 2.1.0's GPI_USERS value contains ';' (separating the
# libpython path from the pygpi entry point). Setting it via
# 'GPI_USERS=val ./Vtop' in the run recipe is brittle: the
# busybox /bin/sh shipped on the CI runners parses
# 'GPI_USERS=foo;bar ./Vtop' as two statements and tries to
# exec '...simulator.so,initialize' as a program
# (Error 127, 'not found'). Exported from Makefile instead,
# the variable is in make's process environment and is
# inherited by the Vtop child as a plain env var.
export GPI_USERS    = $(COCOTB_LIBPYTHON);$(COCOTB_PYGPI_ENTRY)

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
	PYGPI_PYTHON_BIN=$(shell $(PYTHON) -m cocotb_tools.config --python-bin) \
	PYGPI_USERS=cocotb._init:init_package_from_simulation \
	COCOTB_TEST_MODULES=base_test \
	COCOTB_RESULTS_FILE=results.xml \
	./$(BUILD_DIR)/Vtop $(RUN_FLAGS); \
	rc=$$?; \
	$(PYTHON) -m cocotb_tools.check_results results.xml; \
	check_rc=$$?; \
	if [ $$rc -ne 0 ]; then exit $$rc; else exit $$check_rc; fi

clean:
	rm -rf $(BUILD_DIR)/* *.pyc __pycache__ $(COCOTB_RESULTS_FILE)

.PHONY: all build run clean