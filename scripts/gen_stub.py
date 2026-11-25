#!/usr/bin/env python3
"""
Generate Python stub (.pyi) for the svuvm DPI library.

The svuvm .so file contains undefined DPI/VPI symbols provided at runtime by
the Verilog simulator. This script preloads a dpi_stub shared library with
empty implementations of those symbols, so Python can import svuvm for stub
generation.

Stubgen discovers the bindings itself; gen_manifest.py supplies the module
name and the expected class/constant names, which are validated after each run
so a silently changed binding surface cannot pass unnoticed.  The validation
never rewrites the generated files.
"""
import sys
import os
import ctypes
import glob
import argparse
import re
from pathlib import Path

# 使用 os 模块提供的平台无关 dlopen 标志，避免硬编码 macOS/Linux 差异：
# - macOS: RTLD_GLOBAL=0x8, RTLD_LAZY=0x1
# - Linux: RTLD_GLOBAL=0x100, RTLD_LAZY=0x1  (0x8 在 Linux 上是 RTLD_DEEPBIND，与 GLOBAL 相反)
RTLD_LAZY = getattr(os, "RTLD_LAZY", 0x1)
RTLD_GLOBAL = getattr(os, "RTLD_GLOBAL", 0x8)
DLOPEN_FLAGS = RTLD_GLOBAL | RTLD_LAZY

# 设置 Python 导入扩展模块时的 dlopen 标志（影响 import _svuvm）
sys.setdlopenflags(DLOPEN_FLAGS)

sys.path.insert(0, str(Path(__file__).resolve().parent))
import gen_manifest as manifest  # noqa: E402  (path set above)


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


def output_dir_from_argv(argv):
    """Extract stubgen's ``-O`` destination without consuming other flags."""
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("-O", "--output", dest="destination", default=".")
    args, _ = parser.parse_known_args(argv)
    return Path(args.destination)


def validate_stub_files(output_dir):
    """Check the generated .pyi files contain the manifest-declared names.

    Args:
        output_dir: stubgen's ``-O`` directory; the package stubs live in
            ``<output_dir>/_svuvm/``.

    Raises:
        SystemExit: When a declared class or constant is missing from an
            existing stub file.
    """
    package_dir = output_dir / manifest.PYI_MODULE
    root_pyi = package_dir / manifest.PYI_ROOT_FILE
    vpi_pyi = package_dir / manifest.PYI_VPI_FILE

    # A stubgen invocation without -O writes to the CWD; if nothing was
    # generated there is nothing to validate and nothing to fail on.
    if not root_pyi.exists():
        print(f"Warning: {root_pyi} not found; skipping manifest validation", file=sys.stderr)
        return

    root_text = root_pyi.read_text(encoding="utf-8")
    vpi_text = vpi_pyi.read_text(encoding="utf-8") if vpi_pyi.exists() else ""

    missing = []
    classes = manifest.PYI_EXPECTED_CLASSES
    for module_classes, text, path in (
        (manifest.PYI_ROOT_CLASSES, root_text, root_pyi),
        (manifest.PYI_VPI_CLASSES, vpi_text, vpi_pyi),
    ):
        for name in module_classes:
            # Accept both ``class X:`` and ``class X(Exception):`` forms.
            if not re.search(rf"^class\s+{re.escape(name)}\b", text, re.MULTILINE):
                missing.append(f"{path}: class {name}")
    for name in manifest.PYI_EXPECTED_CONSTANTS:
        if not re.search(rf"^{re.escape(name)}\s*[:=]", root_text, re.MULTILINE):
            missing.append(f"{root_pyi}: constant {name}")

    if missing:
        print("Stub manifest validation failed:", file=sys.stderr)
        for entry in missing:
            print(f"  {entry}", file=sys.stderr)
        raise SystemExit(1)

    print(f"Stub manifest validation OK ({len(classes)} classes, "
          f"{len(manifest.PYI_EXPECTED_CONSTANTS)} constants)")


if __name__ == "__main__":
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
    validate_stub_files(output_dir_from_argv(sys.argv[1:]))
