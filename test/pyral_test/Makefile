# Makefile
#
# PyRAL register-access test: Python stages each operation in the UVM
# config_db and calls start_seq(); a UVM sequence + driver perform the APB
# transfer into the peakrdl-generated register block, and the result comes
# back through the same config_db. Run with xezim.
#
# The generated artefacts (gen/, rtl/) are produced by peakrdl from
# demo_regs.rdl and are intentionally not checked in; `make gen` rebuilds
# them.

PYTHON          ?= python3
ROOT            = $(shell git rev-parse --show-toplevel)
TEST_DIR        = $(ROOT)/test/pyral_test
# Absolute, so every path derived from it means the same thing no matter
# which directory make was invoked from (CI runs from the repo root, a
# developer is likely to run it from here).
BUILD_DIR       = $(TEST_DIR)/build
LOG             = $(BUILD_DIR)/xezim.log

# SystemRDL source, and the two peakrdl-generated trees.
RDL             = $(TEST_DIR)/demo_regs.rdl
GEN_DIR         = $(TEST_DIR)/gen
RTL_DIR         = $(TEST_DIR)/rtl
RDL_MODULE      = demo_reg_block
RDL_SEQ         = reg_seq
RDL_SVR         = $(SEQ_PATH_MARK)

# The register block and the generated UVM model both derive from the same
# .rdl, so regenerating keeps them in step.
GEN_PY          = $(GEN_DIR)/$(RDL_MODULE).py
GEN_RTL         = $(RTL_DIR)/$(RDL_MODULE)/demo_regs.sv

MAX_TIME        ?= 10ms
SEQ_PATH_MARK   = uvm_test_top.m_agent.m_sqr

# xezim root: XEZIM_PREFIX wins, else derive from the binary on PATH
XEZIM_PREFIX   ?= $(shell p="$$(command -v xezim 2>/dev/null)"; [ -n "$$p" ] && cd "$$(dirname "$$p")/.." && pwd)
XEZIM           = $(XEZIM_PREFIX)/bin/xezim
UVM_HOME        = $(if $(XEZIM_UVM_SRC),$(patsubst %/uvm_pkg.sv,%,$(XEZIM_UVM_SRC)),$(XEZIM_PREFIX)/share/uvm)

SVUVM_DIR       = $(shell $(PYTHON) -c "import svuvm, os; print(os.path.dirname(svuvm.__file__))" 2>/dev/null)
SVUVM_SV        = $(SVUVM_DIR)/python_bridge_pkg.sv
SVUVM_DPI_LIB   = $(firstword $(wildcard $(SVUVM_DIR)/_svuvm*.so))
UVM_DPI_SRC     = $(XEZIM_PREFIX)/include/uvm_dpi_xezim.cc
UVM_DPI_SO      = $(BUILD_DIR)/uvm_dpi_xezim.so
LIBPYTHON       = $(shell $(PYTHON) -c "import sysconfig, os, glob; d=sysconfig.get_config_var('LIBDIR'); v=sysconfig.get_config_var('LDVERSION') or ''; c=[f for p in ('.dylib', '.so') for f in glob.glob(os.path.join(d, 'libpython' + v + p + '*'))]; print(c[0] if c else '')" 2>/dev/null)

UNAME_S         := $(shell uname)

# The UVM DPI layer references vpi_*/svSetScope, which only exist inside
# xezim: Linux's -shared tolerates that, ld64 needs to be told.
ifeq ($(UNAME_S),Darwin)
LAZY            =
UNDEF           = -Wl,-undefined,dynamic_lookup
# xezim generates the export-trampoline link itself, as
# "cc -m64 -fPIC -shared" with no -U; the trampoline's
# __xezim_dpi_export_dispatch lives in the xezim binary, and ld64 rejects
# undefined symbols in a dylib. xezim spawns a bare "cc" through PATH and
# ignores CC, so the flag is injected by shadowing cc.
CC_WRAPPER      = $(BUILD_DIR)/cc
REAL_CC         = $(shell command -v cc)
CC_WRAPPER_SH   = $(TEST_DIR)/sv/xezim_cc_wrapper.sh
CC_MAKE         = @cp "$(CC_WRAPPER_SH)" $(CC_WRAPPER) && chmod +x $(CC_WRAPPER)
CC_PATH         = PATH="$(abspath $(BUILD_DIR)):$$PATH" XEZIM_REAL_CC="$(REAL_CC)"
else
LAZY            = -Wl,-z,lazy
UNDEF           =
CC_WRAPPER      =
REAL_CC         =
CC_WRAPPER_SH   =
CC_MAKE         =
CC_PATH         =
endif

.PHONY: all run gen clean
all: run

# peakrdl is only needed to (re)generate; the test itself does not import it.
gen:
	mkdir -p $(GEN_DIR) $(RTL_DIR)
	cd $(GEN_DIR) && peakrdl pyral $(RDL) --rename $(RDL_MODULE) -o .
	cd $(RTL_DIR) && peakrdl regblock $(RDL) -o $(RDL_MODULE) --cpuif apb3

check:
	@test -n "$(XEZIM_PREFIX)" || { echo "ERROR: xezim not on PATH; set XEZIM_PREFIX"; exit 1; }
	@test -x "$(XEZIM)" || { echo "ERROR: $(XEZIM) not executable"; exit 1; }
	@test -f "$(UVM_HOME)/src/uvm_pkg.sv" || { echo "ERROR: bundled UVM not found at $(UVM_HOME)"; exit 1; }
	@test -f "$(GEN_PY)" || { echo "ERROR: $(GEN_PY) missing; run 'make gen'"; exit 1; }
	@test -f "$(GEN_RTL)" || { echo "ERROR: $(GEN_RTL) missing; run 'make gen'"; exit 1; }
	@test -n "$(SVUVM_DPI_LIB)" || { echo "ERROR: no _svuvm*.so under $(SVUVM_DIR)"; exit 1; }
	@test -n "$(LIBPYTHON)" || { echo "ERROR: libpython not found"; exit 1; }

run: check
	@mkdir -p $(BUILD_DIR)
	$(CC_MAKE)
	c++ -shared -fPIC $(LAZY) $(UNDEF) -std=c++17 -Wno-format-security \
	  -DUVM_NO_MALLOC \
	  -I "$(XEZIM_PREFIX)/include" -I "$(UVM_HOME)/src/dpi" \
	  $(UVM_DPI_SRC) -o $(UVM_DPI_SO)
# Every library _svuvm.so depends on arrives as a --dpi-lib sibling; xezim
# opens each RTLD_NOW | RTLD_GLOBAL and retries while a pass still loads
# something, so cross-library references resolve regardless of order.
	PYTHONPATH="$(TEST_DIR)/pyral_test:$$PYTHONPATH" \
	$(CC_PATH) \
	$(XEZIM) --simulate -s top \
	  --dpi-lib "$(LIBPYTHON)" \
	  --dpi-lib "$(abspath $(UVM_DPI_SO))" \
	  --dpi-lib "$(SVUVM_DPI_LIB)" \
	  --max-time $(MAX_TIME) --error-exit \
	  -I "$(UVM_HOME)/src" "$(UVM_HOME)/src/uvm_pkg.sv" \
	  -I "$(TEST_DIR)/sv" \
	  -I "$(GEN_DIR)" \
	  "$(SVUVM_SV)" \
	  "$(TEST_DIR)/sv/apb3_intf.sv" \
	  "$(TEST_DIR)/sv/apb3_intf_driver.sv" \
	  "$(TEST_DIR)/sv/reg_agent_pkg.sv" \
	  "$(TEST_DIR)/sv/reg_seq_pkg.sv" \
	  "$(RTL_DIR)/$(RDL_MODULE)/demo_regs_pkg.sv" \
	  "$(GEN_RTL)" \
	  "$(TEST_DIR)/sv/top.sv" \
	  +UVM_TESTNAME=reg_test +UVM_NO_RELNOTES \
	  +PY_DIR=$(TEST_DIR)/pyral_test > $(LOG) 2>&1; \
	rc=$$?; \
	cat $(LOG); \
	if [ $$rc -ne 0 ]; then echo "xezim exited with $$rc"; exit $$rc; fi; \
	grep -q "body: done" $(LOG) || { echo "ERROR: sequence did not run to completion"; exit 1; }

clean:
	rm -rf $(BUILD_DIR) $(GEN_DIR) $(RTL_DIR)
