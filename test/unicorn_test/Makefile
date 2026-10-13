# Makefile
#
# Unicorn register-access test: Python stages each operation as one
# ARM Thumb load/store instruction, runs it on a Unicorn-emulated
# Cortex-M core, and reads the result back from a memory-mapped APB
# region backed by plain RAM. No simulator involved - this is the
# bisect point for the model against a real CPU's bus accesses.
#
# The generated artefact (gen/) is produced by peakrdl from
# demo_regs.rdl and is intentionally not checked in; `make gen`
# rebuilds it.

PYTHON          ?= python3
ROOT            = $(shell git rev-parse --show-toplevel)
TEST_DIR        = $(ROOT)/test/unicorn_test
# Absolute, so every path derived from it means the same thing no matter
# which directory make was invoked from (CI runs from the repo root, a
# developer is likely to run it from here).
BUILD_DIR       = $(TEST_DIR)/build

# SystemRDL source and the peakrdl-generated Python model.
RDL             = $(TEST_DIR)/demo_regs.rdl
GEN_DIR         = $(TEST_DIR)/gen
RDL_MODULE      = demo_reg_block

GEN_PY          = $(GEN_DIR)/$(RDL_MODULE).py

.PHONY: all run gen clean check
all: run

# peakrdl is only needed to (re)generate; the test itself does not import it.
gen:
	mkdir -p $(GEN_DIR)
	cd $(GEN_DIR) && peakrdl pyral $(RDL) --rename $(RDL_MODULE) -o .

check:
	@test -f "$(GEN_PY)" || { echo "ERROR: $(GEN_PY) missing; run 'make gen'"; exit 1; }
	@$(PYTHON) -c "import unicorn" 2>/dev/null || { echo "ERROR: unicorn is not importable; pip install unicorn"; exit 1; }
	@$(PYTHON) -c "import peakrdl_pyral_runtime" 2>/dev/null || { echo "ERROR: peakrdl-pyral-runtime is not importable; pip install peakrdl-pyral-runtime"; exit 1; }

run: check
	PYTHONPATH="$(TEST_DIR):$$PYTHONPATH" \
	$(PYTHON) -m unicorn_test.reg_test; \
	rc=$$?; \
	if [ $$rc -ne 0 ]; then echo "reg_test exited with $$rc"; exit $$rc; fi

clean:
	rm -rf $(BUILD_DIR) $(GEN_DIR)
