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
LOG             = $(BUILD_DIR)/xezim.log

# XEZIM_PREFIX: env var wins; otherwise derive from the binary on PATH
XEZIM_PREFIX   ?= $(shell p="$$(command -v xezim 2>/dev/null)"; [ -n "$$p" ] && cd "$$(dirname "$$p")/.." && pwd)
XEZIM           = $(XEZIM_PREFIX)/bin/xezim
UVM_HOME        = $(XEZIM_PREFIX)/share/uvm

SVUVM_DIR       = $(shell $(PYTHON) -c "import svuvm, os; print(os.path.dirname(svuvm.__file__))" 2>/dev/null)
SVUVM_SV        = $(SVUVM_DIR)/python_bridge_pkg.sv
SVUVM_DPI_LIB   = $(firstword $(wildcard $(SVUVM_DIR)/_svuvm*.so))
VPI_SHIM_SRC    = $(TEST_DIR)/xezim_vpi_shim.c
VPI_SHIM        = $(BUILD_DIR)/xezim_vpi_shim.so

# UVM's own DPI-C layer. verilator links uvm_dpi.cc into Vtop; under xezim
# it must be a preloaded library. The tarball ships a xezim-specific
# variant that implements the uvm_hdl_* surface on plain IEEE 1800 VPI.
UVM_DPI_SRC     = $(XEZIM_PREFIX)/include/uvm_dpi_xezim.cc
UVM_DPI_HEADER  = $(TEST_DIR)/xezim_uvm_report_bridge.h
UVM_DPI_SO      = $(BUILD_DIR)/uvm_dpi_xezim.so

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
# default for dylibs on macOS anyway). The shim and the UVM DPI library
# reference vpi_*/svSetScope, which only exist inside xezim, so they need
# -undefined dynamic_lookup to link.
LAZY            =
UNDEF           = -Wl,-undefined,dynamic_lookup
# macOS 13+ uses chained fixups by default, which eagerly binds even
# dynamic_lookup imports at load time. Inside the compiler child there are
# no VPI symbols, so the inserted shim would be killed before it can do
# anything. -no_fixup_chains restores classic lazy binding.
NO_FIXUP        = -Wl,-no_fixup_chains
SHIM_ARCH       = -arch arm64 -arch arm64e
# xezim's generated link for the export trampoline leaves
# ___xezim_dpi_export_dispatch undefined; ld64 rejects undefined symbols in
# a dylib by default (Linux -shared allows them), so the trampoline link
# fails on macOS. Route the compiler through a wrapper that marks the
# symbol as runtime-resolved - its definition lives in the xezim binary
# (the same -U trick nanobind uses for _Py* symbols).
# xezim spawns a bare "cc" for the trampoline and resolves it through PATH:
# setting CC (or CC_<triple>) has no effect. Shadow "cc" on PATH instead.
# Its generated link leaves ___xezim_dpi_export_dispatch undefined; ld64
# rejects undefined symbols in a dylib by default (Linux -shared allows
# them, which is why Linux works). The definition lives in the xezim
# binary, so marking the symbol as runtime-resolved is enough - the same
# -U trick nanobind uses for _Py* symbols.
CC_WRAPPER      = $(BUILD_DIR)/cc
REAL_CC         = $(shell command -v cc)
CC_WRAPPER_SH   = $(TEST_DIR)/xezim_cc_wrapper.sh
CC_MAKE         = @cp "$(CC_WRAPPER_SH)" $(CC_WRAPPER) && chmod +x $(CC_WRAPPER)
CC_PATH         = PATH="$(abspath $(BUILD_DIR)):$$PATH" XEZIM_REAL_CC="$(REAL_CC)"
PRELOAD_VAR     = DYLD_INSERT_LIBRARIES
PRELOAD_ARGS    = $(abspath $(VPI_SHIM))
BOOTSTRAP_ARGS  = $(abspath $(LIBPYTHON)) $(abspath $(UVM_DPI_SO))
else
LAZY            = -Wl,-z,lazy
UNDEF           =
NO_FIXUP        =
SHIM_ARCH       =
CC_WRAPPER      =
REAL_CC         =
CC_WRAPPER_SH   =
CC_MAKE         =
CC_PATH         =
PRELOAD_VAR     = LD_PRELOAD
PRELOAD_ARGS    = $(abspath $(LIBPYTHON)) $(abspath $(VPI_SHIM)) $(abspath $(UVM_DPI_SO))
BOOTSTRAP_ARGS  =
endif

run: check
	@mkdir -p $(BUILD_DIR)
	$(CC_MAKE)
	cc -shared -fPIC $(LAZY) $(UNDEF) $(NO_FIXUP) $(SHIM_ARCH) -I "$(XEZIM_PREFIX)/include" $(VPI_SHIM_SRC) -o $(VPI_SHIM)
	c++ -shared -fPIC $(LAZY) $(UNDEF) $(SHIM_ARCH) -std=c++17 -Wno-format-security \
	  -DUVM_NO_MALLOC \
	  -include "$(UVM_DPI_HEADER)" \
	  -I "$(XEZIM_PREFIX)/include" -I "$(UVM_HOME)/src/dpi" \
	  $(UVM_DPI_SRC) -o $(UVM_DPI_SO)
# xezim's --dpi-lib dlopen turns out to be RTLD_LOCAL despite the docs, so
# libpython, the VPI shim and UVM's DPI layer must reach the global
# namespace via the OS loader for _svuvm.so to relocate. Set only the
# platform's own variable: setting both loads the libraries twice and the
# second copy fails to relocate. Absolute paths are required because xezim
# changes directory before the loader sees the list.
	PYTHONPATH="$(TEST_DIR):$$PYTHONPATH" \
	XEZIM_PRELOAD_LIBS="$(BOOTSTRAP_ARGS)" \
	$(PRELOAD_VAR)="$(PRELOAD_ARGS)" \
	$(CC_PATH) \
	$(XEZIM) --simulate -s top \
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

.PHONY: all build run check clean
