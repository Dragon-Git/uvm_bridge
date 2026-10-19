# Makefile
#
# Renode register-access test: a bare-metal firmware reaches the register
# block through memory-mapped I/O; Renode runs it, in a process of its own,
# and every access becomes one UVM sequence on the APB agent, which drives the
# peakrdl-generated register block. Both ends come from demo_regs.rdl - the RTL
# from `peakrdl regblock`, the firmware's offsets and field masks from
# `peakrdl c-header`.
#
# The testbench (top.sv, the APB agent, the sequence) is shared with
# test/pyral_test, and the firmware and the Python around it with
# test/unicorn_test: it is the same register block on the same bus, and only
# what drives the bus differs. That is why this Makefile points into
# ../pyral_test/sv and ../fw rather than carrying copies.
#
# Generated or built artefacts (rtl/, c_header/, build/) are not checked in;
# `make gen` and `make fw` rebuild them.

PYTHON          ?= python3
ROOT            = $(shell git rev-parse --show-toplevel)
TEST_DIR        = $(ROOT)/test/renode_test
SV_DIR          = $(ROOT)/test/pyral_test/sv
FW_DIR          = $(ROOT)/test/fw
RDL             = $(ROOT)/test/pyral_test/demo_regs.rdl
RDL_MODULE      = demo_reg_block
BUILD_DIR       = $(TEST_DIR)/build
RTL_DIR         = $(TEST_DIR)/rtl
HDR_DIR         = $(TEST_DIR)/c_header
LOG             = $(BUILD_DIR)/xezim.log

FW_ELF          = $(BUILD_DIR)/fw.o
FW_IMAGE        = $(BUILD_DIR)/fw.bin

# The Renode half of the test runs in a plain CPython with pyrenode3, which the
# simulator's own interpreter does not have: RENODE_RUNNER names the
# interpreter to use, and PYRENODE_PATH points at an unpacked Renode package,
# which is where pyrenode3 looks for the .NET assemblies. CI sets both; see
# the "Install Renode" step in .github/workflows/test.yml.
RENODE_RUNNER  ?= $(PYTHON)
RENODE_PATH    ?= $(PYRENODE_PATH)

MAX_TIME        ?= 10ms

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

# The firmware is compiled for a bare aarch64 target, which needs neither a
# sysroot nor a linker: it is a single function with no global data, so its
# .text is the whole image (see ../fw/elf2bin.py). Only a clang with the
# aarch64 backend is required.
CLANG          ?= clang
FW_TARGET       = aarch64-none-elf
FW_FLAGS        = --target=$(FW_TARGET) -march=armv8-a -mgeneral-regs-only \
                  -std=gnu11 -nostdlib -ffreestanding -fno-builtin \
                  -I "$(HDR_DIR)" -I "$(FW_DIR)/compat"

UNAME_S         := $(shell uname)

# The UVM DPI layer references vpi_*/svSetScope, which only exist inside
# xezim: Linux's -shared tolerates that, ld64 needs to be told.
ifeq ($(UNAME_S),Darwin)
LAZY            =
UNDEF           = -Wl,-undefined,dynamic_lookup
else
LAZY            = -Wl,-z,lazy
UNDEF           =
endif

.PHONY: all run gen fw clean
all: run

# peakrdl is only needed to (re)generate; the test itself does not import it.
# The register block and the C header both derive from the same .rdl, so
# regenerating keeps the hardware and the firmware's view of it in step.
gen:
	mkdir -p $(RTL_DIR) $(HDR_DIR)
	cd $(RTL_DIR) && peakrdl regblock $(RDL) -o $(RDL_MODULE) --cpuif apb3
	peakrdl c-header $(RDL) -o $(HDR_DIR)/demo_regs.h

fw: gen
	@mkdir -p $(BUILD_DIR)
	@$(CLANG) --print-targets 2>/dev/null | grep -qw aarch64 || { \
	  echo "ERROR: $(CLANG) has no aarch64 backend; set CLANG to one that has"; exit 1; }
	$(CLANG) $(FW_FLAGS) -c "$(FW_DIR)/main.c" -o $(FW_ELF)
	$(PYTHON) $(FW_DIR)/elf2bin.py $(FW_ELF) $(FW_IMAGE)

check:
	@test -n "$(XEZIM_PREFIX)" || { echo "ERROR: xezim not on PATH; set XEZIM_PREFIX"; exit 1; }
	@test -x "$(XEZIM)" || { echo "ERROR: $(XEZIM) not executable"; exit 1; }
	@test -f "$(UVM_HOME)/src/uvm_pkg.sv" || { echo "ERROR: bundled UVM not found at $(UVM_HOME)"; exit 1; }
	@test -f "$(RTL_DIR)/$(RDL_MODULE)/demo_regs_pkg.sv" || { echo "ERROR: generated RTL missing; run 'make gen'"; exit 1; }
	@test -f "$(HDR_DIR)/demo_regs.h" || { echo "ERROR: generated header missing; run 'make gen'"; exit 1; }
	@test -n "$(SVUVM_DPI_LIB)" || { echo "ERROR: no _svuvm*.so under $(SVUVM_DIR)"; exit 1; }
	@test -n "$(LIBPYTHON)" || { echo "ERROR: libpython not found"; exit 1; }
	@test -n "$(RENODE_PATH)" || { echo "ERROR: PYRENODE_PATH is not set; point it at a Renode package"; exit 1; }
	@$(RENODE_RUNNER) -c "import pyrenode3" 2>/dev/null || { echo "ERROR: pyrenode3 is not importable by $(RENODE_RUNNER); pip install . --group test"; exit 1; }

run: fw check
	@mkdir -p $(BUILD_DIR)
	c++ -shared -fPIC $(LAZY) $(UNDEF) -std=c++17 -Wno-format-security \
	  -DUVM_NO_MALLOC \
	  -I "$(XEZIM_PREFIX)/include" -I "$(UVM_HOME)/src/dpi" \
	  $(UVM_DPI_SRC) -o $(UVM_DPI_SO)
# Every library _svuvm.so depends on arrives as a --dpi-lib sibling; xezim
# opens each RTLD_NOW | RTLD_GLOBAL and retries while a pass still loads
# something, so cross-library references resolve regardless of order.
	FW_REG_IMAGE="$(abspath $(FW_IMAGE))" \
	RENODE_TEST_PLATFORM="$(TEST_DIR)/platform/renode_test.repl" \
	RENODE_TEST_PYTHON="$(RENODE_RUNNER)" \
	PYRENODE_PATH="$(RENODE_PATH)" \
	PYTHONPATH="$(FW_DIR):$(TEST_DIR):$$PYTHONPATH" \
	$(XEZIM) --simulate -s top \
	  --dpi-lib "$(LIBPYTHON)" \
	  --dpi-lib "$(abspath $(UVM_DPI_SO))" \
	  --dpi-lib "$(SVUVM_DPI_LIB)" \
	  --max-time $(MAX_TIME) --error-exit \
	  -I "$(UVM_HOME)/src" "$(UVM_HOME)/src/uvm_pkg.sv" \
	  -I "$(SV_DIR)" \
	  "$(SVUVM_SV)" \
	  "$(SV_DIR)/apb3_intf.sv" \
	  "$(SV_DIR)/apb3_intf_driver.sv" \
	  "$(SV_DIR)/reg_agent_pkg.sv" \
	  "$(SV_DIR)/reg_seq_pkg.sv" \
	  "$(RTL_DIR)/$(RDL_MODULE)/demo_regs_pkg.sv" \
	  "$(RTL_DIR)/$(RDL_MODULE)/demo_regs.sv" \
	  "$(SV_DIR)/top.sv" \
	  +UVM_TESTNAME=reg_test +UVM_NO_RELNOTES \
	  +PY_DIR=$(TEST_DIR) > $(LOG) 2>&1; \
	rc=$$?; \
	cat $(LOG); \
	if [ $$rc -ne 0 ]; then echo "xezim exited with $$rc"; exit $$rc; fi; \
	grep -q "TEST_PASS" $(LOG) || { echo "ERROR: no TEST_PASS in the log - the run stalled, or the firmware test reported failures"; exit 1; }

clean:
	rm -rf $(BUILD_DIR) $(RTL_DIR) $(HDR_DIR)
