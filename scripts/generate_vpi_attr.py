#!/usr/bin/env python3
"""Generate the VPI attribute header; all configuration lives in gen_manifest.

The output stays in ``inc/vpi_attr.h`` (gitignored) to preserve the C++
``#include <vpi_attr.h>`` in svuvm.cpp.  An optional ``--output`` path is used
by the reproducibility guard to generate into a temporary directory.
"""

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import gen_manifest as manifest  # noqa: E402  (path set above)


def generate(source_dir, output_file):
    """Extract numeric vpi*/cb* macros and render them into ``output_file``.

    Args:
        source_dir: Repository root containing ``inc/``.
        output_file: Destination path (parent directories are created).

    Returns:
        The resolved output path.
    """
    content = ""
    for header_name in manifest.VPI_ATTR_SOURCE_HEADERS:
        header = Path(source_dir) / "inc" / header_name
        content += header.read_text(encoding="utf-8")

    matches = re.findall(manifest.VPI_ATTR_MACRO_PATTERN, content)
    vpi_attr = [manifest.VPI_ATTR_TEMPLATE.format(name=m[0]) for m in matches]

    output_file = Path(output_file)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text("\n".join(vpi_attr), encoding="utf-8")

    print(f"Generated {output_file} with {len(vpi_attr)} attributes")
    return output_file


def main():
    """CLI entry point; defaults preserve the legacy ``<source_dir>`` usage."""
    parser = argparse.ArgumentParser(description="Generate vpi_attr.h")
    parser.add_argument(
        "source_dir",
        nargs="?",
        default=str(Path(__file__).resolve().parent.parent),
        help="repository root (default: parent of scripts/)",
    )
    parser.add_argument(
        "-o", "--output", default=None,
        help="output path override (default: <source_dir>/inc/vpi_attr.h)",
    )
    args = parser.parse_args()
    output = args.output or manifest.vpi_attr_output(args.source_dir)
    generate(args.source_dir, output)


if __name__ == "__main__":
    main()
