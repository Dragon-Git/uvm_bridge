#!/bin/sh
# Compiler wrapper for xezim's export-trampoline link on macOS.
#
# xezim builds the trampoline with the compiler named by $CC. On macOS the
# generated link leaves ___xezim_dpi_export_dispatch undefined; ld64
# rejects undefined symbols in a dylib by default, which is why the
# trampoline link fails (Linux's -shared allows them, so Linux works).
# The definition lives in the xezim binary, so marking the symbol as
# runtime-resolved is enough - the same -U trick nanobind uses for _Py*.
#
# The real compiler is passed in as $XEZIM_REAL_CC; this script must not
# refer to itself, hence the explicit path.
echo "[ccwrap] $*" >&2
exec "$XEZIM_REAL_CC" "$@" -Wl,-U,___xezim_dpi_export_dispatch
