#!/usr/bin/env python3
"""Generate DPI-C export declarations from the tracked SystemVerilog package.

Since the source-tree refactor the declarations no longer overwrite
``src/svuvm/python_bridge_pkg.sv``.  The tracked package carries a stable
`` `include "python_bridge_pkg_export.svh" `` between the EXPORT_DPIC markers,
and this script writes that .svh into the build directory.  Declaration
discovery still reads the tracked package with pyslang, so the generated
declarations are identical to the former in-place region (line for line).

The companion ``export_dpi.h`` header also goes to the build directory; the
repository copy under ``inc/`` is gitignored and is only a stale artifact.
"""

import argparse
import sys
from pathlib import Path

try:
    import pyslang
except ImportError:
    print("Error: pyslang is required. Install with: pip install pyslang")
    sys.exit(1)

sys.path.insert(0, str(Path(__file__).resolve().parent))
import gen_manifest as manifest  # noqa: E402  (path set above)


def validate_source(source_file):
    """Fail fast if the tracked package regressed to an inline export region.

    The marker block must contain exactly one stable include line and no inline
    ``export "DPI-C"`` declarations.  This keeps the source reproducible: a
    generator run can never silently edit it again.

    Args:
        source_file: Path to the tracked ``python_bridge_pkg.sv``.
    """
    lines = source_file.read_text(encoding="utf-8").splitlines()
    begin = next(
        (i for i, line in enumerate(lines)
         if line.strip() == manifest.SV_EXPORT_BEGIN_MARKER),
        None,
    )
    end = next(
        (i for i, line in enumerate(lines)
         if line.strip() == manifest.SV_EXPORT_END_MARKER),
        None,
    )
    if begin is None or end is None or end <= begin:
        raise SystemExit(
            f"{source_file}: missing or unordered EXPORT_DPIC markers"
        )

    region = lines[begin + 1:end]
    include_lines = [
        line for line in region
        if line.strip() == manifest.SV_EXPORT_INCLUDE_LINE.strip()
    ]
    if len(include_lines) != 1:
        raise SystemExit(
            f"{source_file}: expected exactly one "
            f'`include "{manifest.SV_EXPORT_INCLUDE_FILE}"` in the export region'
        )
    inline = [line for line in region if 'export "DPI-C"' in line]
    if inline:
        raise SystemExit(
            f"{source_file}: {len(inline)} inline DPI-C export declaration(s) "
            "found; the export region must stay a single include"
        )


def _package_members(source_file):
    """Yield ``(kind, name)`` for direct task/function members of the package.

    pyslang reports one diagnostic for the unresolved include when the .svh is
    not on its include path; that diagnostic does not affect the member list,
    which was verified against the pre-refactor package (122 members).
    """
    tree = pyslang.syntax.SyntaxTree.fromFile(str(source_file))
    members = []
    for member in tree.root.members[0].members:
        if member.kind == pyslang.syntax.SyntaxKind.TaskDeclaration:
            members.append(("task", member.prototype.name.identifier.value))
        elif member.kind == pyslang.syntax.SyntaxKind.FunctionDeclaration:
            members.append(("function", member.prototype.name.identifier.value))
    return members


def build_export_lines(source_file):
    """Return the .svh lines, byte-identical to the legacy export region."""
    lines = list(manifest.SV_EXPORT_GENERATED_COMMENTS)
    for kind, name in _package_members(source_file):
        if name in manifest.SV_EXPORT_EXCLUDE_FUNC_LIST:
            continue
        prefix = (
            manifest.SV_EXPORT_TASK_PREFIX if kind == "task"
            else manifest.SV_EXPORT_FUNCTION_PREFIX
        )
        lines.append(f"{prefix}{name}{manifest.SV_EXPORT_DECL_SUFFIX}")
    return lines


def build_header_lines(source_file):
    """Return export_dpi.h lines with the legacy prototype transformations."""
    tree = pyslang.syntax.SyntaxTree.fromFile(str(source_file))
    output_lines = list(manifest.SV_EXPORT_GENERATED_COMMENTS)
    for member in tree.root.members[0].members:
        if member.kind == pyslang.syntax.SyntaxKind.TaskDeclaration:
            if member.prototype.name.identifier.value in manifest.SV_EXPORT_EXCLUDE_FUNC_LIST:
                continue
            prototype = str(member.prototype)
            prototype = (
                prototype.replace("task automatic", "void")
                .replace("output string", "char **")
                .replace("string", "const char *")
                .replace("output int", "int *")
                .replace("uvm_action", "int")
                .replace("bit", "unsigned char")
                .replace("longint", "long long")
            )
            output_lines.append(f"{prototype};")
        elif member.kind == pyslang.syntax.SyntaxKind.FunctionDeclaration:
            if member.prototype.name.identifier.value in manifest.SV_EXPORT_EXCLUDE_FUNC_LIST:
                continue
            prototype = str(member.prototype)
            prototype = (
                prototype.replace("function automatic ", "")
                .replace("output string", "const char *")
                .replace("string", "const char *")
                .replace("output int", "int *")
                .replace("uvm_action", "int")
                .replace("bit", "unsigned char")
                .replace("longint", "long long")
                .replace("config_const char *", "config_string")
            )
            output_lines.append(f"{prototype};")
    return output_lines


def main():
    """CLI entry point; declaration parsing stays on the tracked source."""
    parser = argparse.ArgumentParser(description="Generate SV DPI-C exports")
    parser.add_argument(
        "source_dir",
        nargs="?",
        default=str(Path(__file__).resolve().parent.parent),
        help="repository root (default: parent of scripts/)",
    )
    parser.add_argument(
        "--output-dir", default=None,
        help="directory for generated .svh/.h (default: current directory)",
    )
    parser.add_argument(
        "--header-output", default=None,
        help="explicit export_dpi.h path override",
    )
    args = parser.parse_args()

    source_file = manifest.source_package(args.source_dir)
    validate_source(source_file)

    output_dir = Path(args.output_dir) if args.output_dir else Path.cwd()
    output_dir.mkdir(parents=True, exist_ok=True)

    export_lines = build_export_lines(source_file)
    svh = output_dir / manifest.SV_EXPORT_INCLUDE_FILE
    svh.write_text("\n".join(export_lines) + "\n", encoding="utf-8")

    header = (
        Path(args.header_output) if args.header_output
        else output_dir / manifest.SV_EXPORT_HEADER_FILE
    )
    header.parent.mkdir(parents=True, exist_ok=True)
    header.write_text("".join(build_header_lines(source_file)), encoding="utf-8")

    print(f"Generated {svh} and {header} ({len(export_lines) - 2} exports)")


if __name__ == "__main__":
    main()
