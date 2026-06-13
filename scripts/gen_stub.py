#!/usr/bin/env python3
"""
Generate Python stub (.pyi) for the svuvm DPI library.

The svuvm .so file contains undefined DPI/VPI symbols provided at runtime by
the Verilog simulator. This script preloads a dpi_stub shared library with
empty implementations of those symbols, so Python can import svuvm for stub
generation.
"""
import sys
import os
import ctypes
import glob

# 使用 os 模块提供的平台无关 dlopen 标志，避免硬编码 macOS/Linux 差异：
# - macOS: RTLD_GLOBAL=0x8, RTLD_LAZY=0x1
# - Linux: RTLD_GLOBAL=0x100, RTLD_LAZY=0x1  (0x8 在 Linux 上是 RTLD_DEEPBIND，与 GLOBAL 相反)
RTLD_LAZY = getattr(os, "RTLD_LAZY", 0x1)
RTLD_GLOBAL = getattr(os, "RTLD_GLOBAL", 0x8)
DLOPEN_FLAGS = RTLD_GLOBAL | RTLD_LAZY

# 设置 Python 导入扩展模块时的 dlopen 标志（影响 import _svuvm）
sys.setdlopenflags(DLOPEN_FLAGS)

def find_so(search_dirs, patterns):
    """Find a shared library matching any of the patterns in given dirs."""
    for d in search_dirs:
        for pattern in patterns:
            matches = glob.glob(os.path.join(d, pattern))
            if matches:
                return matches[0]
    return None

def preload_libs(search_dirs):
    """Load dpi_stub (provides DPI symbols) then svuvm with RTLD_LAZY|GLOBAL.
    """
    dpi_stub = find_so(search_dirs, ["libdpi_stub*", "dpi_stub*"])
    if dpi_stub:
        try:
            ctypes.CDLL(dpi_stub, mode=DLOPEN_FLAGS)
        except OSError as e:
            print(f"Warning: preload of {dpi_stub} failed: {e}", file=sys.stderr)

    svuvm_so = find_so(search_dirs, ["_svuvm*.so", "_svuvm*.dylib"])
    if svuvm_so:
        try:
            ctypes.CDLL(svuvm_so, mode=DLOPEN_FLAGS)
        except OSError as e:
            print(f"Warning: preload of {svuvm_so} failed: {e}", file=sys.stderr)

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("-i", "--include", action="append", default=[])
    args, _ = parser.parse_known_args()

    search_dirs = args.include + [os.getcwd()]
    for d in search_dirs:
        if d and d not in sys.path:
            sys.path.insert(0, d)
    preload_libs(search_dirs)

    from nanobind import stubgen
    stubgen.main(sys.argv[1:])