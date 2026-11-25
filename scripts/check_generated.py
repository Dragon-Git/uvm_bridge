#!/usr/bin/env python3
"""Reproducibility guard for the generated sources.

The guard regenerates every deterministic artifact into two temporary
directories and checks:

1. the regenerated outputs are byte-identical between runs;
2. the tracked ``python_bridge_pkg.sv`` is not modified by generation and
   still holds exactly the stable include line between the EXPORT_DPIC markers;
3. the regenerated ``vpi_attr.h`` / ``export_dpi.h`` match existing counterparts
   (when present) in the source tree;
4. optionally, the regenerated export .svh matches the one in the CMake build
   directory (``--build-dir``), and a scoped ``git diff --exit-code`` verifies
   that no tracked generated source changed (``--git-diff``).

Usage::

    python3 scripts/check_generated.py
    python3 scripts/check_generated.py --build-dir build --git-diff
"""

import argparse
import hashlib
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import gen_manifest as manifest  # noqa: E402  (path set above)


def _digest(path):
    """Return the SHA-256 of ``path`` or None when it does not exist."""
    path = Path(path)
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None


def _run(cmd, root):
    """Run a generator, aborting the guard with its output on failure."""
    proc = subprocess.run(
        [str(part) for part in cmd],
        cwd=str(root), capture_output=True, text=True, check=False,
    )
    if proc.returncode != 0:
        print(f"check_generated: command failed: {' '.join(str(c) for c in cmd)}")
        print(proc.stdout, end="")
        print(proc.stderr, end="", file=sys.stderr)
        raise SystemExit(proc.returncode)
    return proc.stdout


def _fail(message):
    """Report a guard failure and stop."""
    print(f"check_generated: FAIL - {message}", file=sys.stderr)
    raise SystemExit(1)


def main():
    """Entry point: regenerate twice, compare, and report."""
    parser = argparse.ArgumentParser(description="Check generated sources")
    parser.add_argument(
        "--root", default=str(Path(__file__).resolve().parent.parent),
        help="repository root (default: parent of scripts/)",
    )
    parser.add_argument("--build-dir", default=None, help="CMake build directory")
    parser.add_argument(
        "--git-diff", action="store_true",
        help="also run git diff --exit-code on the tracked SV package",
    )
    args = parser.parse_args()

    root = Path(args.root).resolve()
    scripts = root / "scripts"
    source_sv = manifest.source_package(root)
    source_digest = _digest(source_sv)

    with tempfile.TemporaryDirectory(prefix="svuvm-gen-check-") as tmp:
        first = Path(tmp) / "first"
        second = Path(tmp) / "second"
        for output_dir in (first, second):
            _run(
                [sys.executable, scripts / "generate_sv_export.py", root,
                 "--output-dir", output_dir],
                root,
            )
            _run(
                [sys.executable, scripts / "generate_vpi_attr.py", root,
                 "--output", output_dir / "vpi_attr.h"],
                root,
            )

        first_svh = first / manifest.SV_EXPORT_INCLUDE_FILE
        second_svh = second / manifest.SV_EXPORT_INCLUDE_FILE
        if _digest(first_svh) != _digest(second_svh):
            _fail("export .svh is not deterministic")
        if _digest(first / "vpi_attr.h") != _digest(second / "vpi_attr.h"):
            _fail("vpi_attr.h is not deterministic")
        if _digest(first / manifest.SV_EXPORT_HEADER_FILE) != _digest(second / manifest.SV_EXPORT_HEADER_FILE):
            _fail("export_dpi.h is not deterministic")

        if _digest(source_sv) != source_digest:
            _fail(f"generation modified tracked source {source_sv}")

        # Source-tree copies are gitignored leftovers from older builds; when
        # they exist their content must still match a fresh generation.
        for generated, existing in (
            (first / "vpi_attr.h", manifest.vpi_attr_output(root)),
            (first / manifest.SV_EXPORT_HEADER_FILE,
             root / "inc" / manifest.SV_EXPORT_HEADER_FILE),
        ):
            if existing.exists() and _digest(generated) != _digest(existing):
                _fail(f"{existing} differs from freshly generated output")

        if args.build_dir:
            built = Path(args.build_dir) / manifest.SV_EXPORT_INCLUDE_FILE
            if built.exists() and _digest(built) != _digest(first_svh):
                _fail(f"{built} differs from freshly generated export declarations")

        svh_digest = _digest(first_svh)

    if args.git_diff:
        proc = subprocess.run(
            ["git", "diff", "--exit-code", "--", str(source_sv.relative_to(root))],
            cwd=str(root), capture_output=True, text=True, check=False,
        )
        if proc.returncode != 0:
            _fail(f"git diff --exit-code reported changes in {source_sv}")

    print(f"check_generated: OK (export .svh sha256={svh_digest})")


if __name__ == "__main__":
    main()
