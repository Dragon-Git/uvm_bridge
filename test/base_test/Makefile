# Makefile
#
# Run the base test. SIM selects the simulator:
#   SIM=verilator (default) - build Vtop with verilator, UVM from the
#                             verilator-compatible fork
#   SIM=xezim               - interpret with xezim (no build step), UVM from
#                             xezim's bundled copy; our DPI side (_svuvm.so,
#                             which embeds CPython) is loaded via --dpi-lib.
#                             Pass criteria: exit 0 AND the Python test's
#                             final marker in the log (xezim stops silently
#                             at --max-time, and base_test.py intentionally
#                             raises UVM_ERROR/UVM_FATAL, so grepping the
#                             UVM_ERROR count does not work here).

SIM             ?= verilator
PYTHON          = python
ROOT            = $(shell git rev-parse --show-toplevel)
BUILD_DIR       = build
TEST_DIR        = $(ROOT)/test/base_test
SV_SOURCE       = $(TEST_DIR)/top.sv
SVUVM_CONFIG    = $(shell $(PYTHON) -m svuvm.config)
NPROC           = $(shell nproc 2>/dev/null || echo 10)

RUN_FLAGS       = +UVM_TESTNAME=base_test +UVM_NO_RELNOTES +UVM_OBJECTION_TRACE $(RUN_OPTS)

ifeq ($(SIM),xezim)

MAX_TIME        ?= 10ms
# Separate from the verilator branch's relative BUILD_DIR: these paths end
# up in --dpi-lib arguments and in the log redirect, so they must mean the
# same thing whoever invokes make. The verilator branch keeps its relative
# build/ because verilator is given it as -Mdir.
XEZIM_BUILD_DIR = $(TEST_DIR)/build
LOG             = $(XEZIM_BUILD_DIR)/xezim.log

# XEZIM_PREFIX: env var wins; otherwise derive from the binary on PATH
XEZIM_PREFIX   ?= $(shell p="$$(command -v xezim 2>/dev/null)"; [ -n "$$p" ] && cd "$$(dirname "$$p")/.." && pwd)
XEZIM           = $(XEZIM_PREFIX)/bin/xezim
UVM_HOME        = $(if $(XEZIM_UVM_SRC),$(patsubst %/uvm_pkg.sv,%,$(XEZIM_UVM_SRC)),$(XEZIM_PREFIX)/share/uvm)

SVUVM_DIR       = $(shell $(PYTHON) -c "import svuvm, os; print(os.path.dirname(svuvm.__file__))" 2>/dev/null)
SVUVM_SV        = $(SVUVM_DIR)/python_bridge_pkg.sv
SVUVM_DPI_LIB   = $(firstword $(wildcard $(SVUVM_DIR)/_svuvm*.so))
# UVM's own DPI-C layer. verilator links uvm_dpi.cc into Vtop; under xezim
# it must be a preloaded library. The tarball ships a xezim-specific
# variant that implements the uvm_hdl_* surface on plain IEEE 1800 VPI.
UVM_DPI_SRC     = $(XEZIM_PREFIX)/include/uvm_dpi_xezim.cc
UVM_DPI_SO      = $(XEZIM_BUILD_DIR)/uvm_dpi_xezim.so

# _svuvm.so is a Python extension: it does not link libpython, so in a
# non-Python host (xezim dlopens it with RTLD_NOW) the Py* symbols must
# already be global. xezim's own --dpi-lib(RTLD_GLOBAL) turned out not to
# keep libpython's symbols visible, so preload it at the OS level instead;
# --dpi-lib stays as a belt-and-braces fallback.
LIBPYTHON       = $(shell $(PYTHON) -c "import sysconfig, os, glob; d=sysconfig.get_config_var('LIBDIR'); v=sysconfig.get_config_var('LDVERSION') or ''; c=[f for p in ('.dylib', '.so') for f in glob.glob(os.path.join(d, 'libpython' + v + p + '*'))]; print(c[0] if c else '')" 2>/dev/null)

check:
	@test -n "$(XEZIM_PREFIX)" || { echo "ERROR: xezim not on PATH; set XEZIM_PREFIX to the unpacked xezim/ dir"; exit 1; }
	@test -x "$(XEZIM)" || { echo "ERROR: $(XEZIM) not executable"; exit 1; }
	@test -f "$(UVM_HOME)/src/uvm_pkg.sv" || { echo "ERROR: bundled UVM not found at $(UVM_HOME)"; exit 1; }
	@test -n "$(SVUVM_DIR)" || { echo "ERROR: svuvm is not importable with $(PYTHON)"; exit 1; }
	@test -n "$(SVUVM_DPI_LIB)" || { echo "ERROR: no _svuvm*.so under $(SVUVM_DIR)"; exit 1; }
	@test -n "$(LIBPYTHON)" || { echo "ERROR: libpython not found (needed to preload Py* symbols)"; exit 1; }
	@echo "libpython : $(LIBPYTHON)"
	@echo "xezim     : $$( $(XEZIM) -V 2>/dev/null )"
	@echo "uvm       : $(UVM_HOME)"
	@echo "dpi lib   : $(SVUVM_DPI_LIB)"
	@echo "bridge sv : $(SVUVM_SV)"

ifeq ($(shell uname),Darwin)
# -Wl,-z,lazy is a GNU-ld option; ld64 rejects it (and lazy binding is the
# default for dylibs on macOS anyway). The UVM DPI library references
# vpi_*/svSetScope, which only exist inside xezim, so it needs
# -undefined dynamic_lookup to link.
LAZY            =
UNDEF           = -Wl,-undefined,dynamic_lookup
# xezim generates the export-trampoline link itself, as
# "cc -m64 -fPIC -shared" with no -U (simulator.rs). The trampoline
# references __xezim_dpi_export_dispatch, whose definition lives in the
# xezim binary, and ld64 rejects undefined symbols in a dylib - Linux's
# -shared allows them, which is why only macOS needs this. xezim spawns a
# bare "cc" resolved through PATH and ignores CC, so the flag is injected
# by shadowing cc.
CC_WRAPPER      = $(XEZIM_BUILD_DIR)/cc
REAL_CC         = $(shell command -v cc)
CC_WRAPPER_SH   = $(TEST_DIR)/xezim_cc_wrapper.sh
CC_MAKE         = @cp "$(CC_WRAPPER_SH)" $(CC_WRAPPER) && chmod +x $(CC_WRAPPER)
CC_PATH         = PATH="$(abspath $(XEZIM_BUILD_DIR)):$$PATH" XEZIM_REAL_CC="$(REAL_CC)"
else
LAZY            = -Wl,-z,lazy
UNDEF           =
CC_WRAPPER      =
REAL_CC         =
CC_WRAPPER_SH   =
CC_MAKE         =
CC_PATH         =
endif

run: check
	@mkdir -p $(XEZIM_BUILD_DIR)
	$(CC_MAKE)
	c++ -shared -fPIC $(LAZY) $(UNDEF) -std=c++17 -Wno-format-security \
	  -DUVM_NO_MALLOC \
	  -I "$(XEZIM_PREFIX)/include" -I "$(UVM_HOME)/src/dpi" \
	  $(UVM_DPI_SRC) -o $(UVM_DPI_SO)
# Everything _svuvm.so needs comes in as a --dpi-lib sibling. xezim opens
# each with RTLD_NOW | RTLD_GLOBAL and retries while a pass still loads
# something, so one library may call into another in any command-line
# order; no OS-level preloading is needed. Order below is dependency-first
# anyway, purely for readability:
#   libpython  - Py* symbols (the extension deliberately does not link it)
#   uvm_dpi    - UVM's DPI-C layer (uvm_hdl_* and friends)
#   _svuvm     - the bridge itself
	PYTHONPATH="$(TEST_DIR):$$PYTHONPATH" \
	$(CC_PATH) \
	$(XEZIM) --simulate -s top \
	  --dpi-lib "$(LIBPYTHON)" \
	  --dpi-lib "$(abspath $(UVM_DPI_SO))" \
	  --dpi-lib "$(SVUVM_DPI_LIB)" \
	  --max-time $(MAX_TIME) --error-exit \
	  -I "$(UVM_HOME)/src" "$(UVM_HOME)/src/uvm_pkg.sv" \
	  "$(SVUVM_SV)" "$(SV_SOURCE)" \
	  $(RUN_FLAGS) > $(LOG) 2>&1; \
	rc=$$?; \
	cat $(LOG); \
	if [ $$rc -ne 0 ]; then echo "xezim exited with $$rc"; exit $$rc; fi; \
	grep -q "所有新增API测试完成" $(LOG) || { echo "ERROR: Python test did not run to completion (max-time cap?)"; exit 1; }

else

VERILATOR       = verilator
COCOTB_LIB_DIR  = $(shell cocotb-config --lib-dir)
UVM_HOME        = $(ROOT)/uvm-verilator/src
INCLUDE_DIRS    = +incdir+$(UVM_HOME)
UVM_PKG         = $(UVM_HOME)/uvm_pkg.sv
UVM_DPI         = $(UVM_HOME)/dpi/uvm_dpi.cc

VERILATOR_FLAGS = -j $(NPROC) --vpi --binary \
                  -top top -Mdir $(BUILD_DIR) \
                  --output-groups $(NPROC) \
				  -Wno-lint -Wno-style -Wno-SYMRSVDWORD -Wno-WIDTHTRUNC -Wno-WIDTHEXPAND \
				  -Wno-IGNOREDRETURN -Wno-CONSTRAINTIGN -Wno-ZERODLY -Wno-CASTCONST \

CXXFLAGS        = -CFLAGS "-I$(UVM_HOME)/dpi -I$(ROOT)/inc  -DVERILATOR -DUVM_NO_MALLOC"

ifeq ($(shell uname),Linux)
ASNEEDED_PRE    = -LDFLAGS "-Wl,--no-as-needed"
ASNEEDED_POST   = -LDFLAGS "-Wl,--as-needed"
endif

$(BUILD_DIR):
	mkdir -p $@

build: $(BUILD_DIR)
	$(VERILATOR) $(VERILATOR_FLAGS) $(INCLUDE_DIRS) $(UVM_DPI) \
	$(UVM_PKG) $(ASNEEDED_PRE) $(SVUVM_CONFIG) $(SV_SOURCE) $(CXXFLAGS) $(ASNEEDED_POST) $(LDFLAGS)


run: build
	DYLD_LIBRARY_PATH=$(shell pip show pip | grep Location | awk '{print $$2}')/svuvm \
	PYTHONPATH=$(TEST_DIR) \
	./$(BUILD_DIR)/Vtop $(RUN_FLAGS)

endif

clean:
	rm -rf $(BUILD_DIR)/* *.pyc __pycache__
ifeq ($(SIM),xezim)
	rm -rf $(XEZIM_BUILD_DIR)
endif

.PHONY: all build run check clean
