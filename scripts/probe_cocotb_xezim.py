#!/usr/bin/env python3
"""Probe ``cocotb_run_xezim`` end to end and print its evidence.

This is the repeatable probe for design sections U1 (cocotb suspendable
callbacks on the xezim VPI), U2 (cocotb/svuvm access to the same signal) and
U4 (one libpython shared by ``GPI_USERS`` and ``--dpi-lib``). It invokes the
production function directly, so a passing probe proves the same code path
the pytest fixture uses.

Example::

    XEZIM_PREFIX=/path/to/prefix python3 scripts/probe_cocotb_xezim.py
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "test" / "base_test"))
import sim_runner  # noqa: E402

KEY_LINES = (
    "GPI: VPI support registered",
    "Loaded entry library",
    "Running entry func 'initialize'",
    "Using Python",
    "Initialized cocotb",
    "Running on xezim",
    "No GPI_USERS",
    "undefined symbol",
    "not supported",
    "Py_Initialize",
    "[FAIL]",
)


def main(argv=None) -> int:
    """Run one xezim cocotb simulation and report the machine-readable facts."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prefix", default=os.environ.get("XEZIM_PREFIX"))
    parser.add_argument(
        "--build-dir",
        default=str(ROOT / "test" / "cocotb_test" / "build" / "xezim-probe"),
    )
    parser.add_argument("--max-time", default=os.environ.get("MAX_TIME", "10ms"))
    parser.add_argument("--result-json")
    args = parser.parse_args(argv)

    if args.prefix:
        os.environ["XEZIM_PREFIX"] = args.prefix
    build_dir = Path(args.build_dir)
    build_dir.mkdir(parents=True, exist_ok=True)
    result_json = (
        Path(args.result_json) if args.result_json else build_dir / "probe_results.json"
    )

    try:
        rc, log = sim_runner.cocotb_run_xezim(
            sys.executable,
            build_dir,
            None,
            {"SVUVM_RESULT_JSON": str(result_json)},
            args.max_time,
        )
    except sim_runner.SimError as exc:
        print(f"PROBE SimError: {exc}", file=sys.stderr)
        return 2

    print(f"rc={rc}")
    print("--- key log lines ---")
    lines = log.splitlines()
    for line in lines:
        if any(key in line for key in KEY_LINES):
            print(line)
    print("--- result JSON ---")
    if not result_json.is_file():
        print("result JSON missing")
        return 1
    data = json.loads(result_json.read_text(encoding="utf-8"))
    cases = data.get("cases", [])
    print(
        f"checks={data.get('checks')} skips={data.get('skips')} "
        f"failures={len(data.get('failures', []))} cases={len(cases)}"
    )
    for case in cases:
        print(f"  {case['name']}: {case['status']}")

    # cocotb's Python-level "Initialized cocotb ... Running on <sim>" lines are
    # only emitted when its logging handler is configured by the standard
    # runner; the hand-written production path (like the verilator leg) does
    # not do that. Equivalent evidence is available from the C++ GPI/pygpi
    # logger plus cocotb's own results.xml, so assert on those instead.
    gpi_ready = any("GPI: VPI support registered" in line for line in lines)
    pygpi_ready = any(
        "Running entry func 'initialize'" in line and "cocotb/simulator" in line
        for line in lines
    )
    on_xezim = any("xezim " in line for line in lines[:5])
    no_hard_error = not any(
        marker in log
        for marker in ("No GPI_USERS specified", "undefined symbol", "[FAIL]")
    )
    results_xml = (build_dir / "results.xml").is_file()
    all_pass = bool(cases) and all(case["status"] == "pass" for case in cases)
    ok = (
        rc == 0 and gpi_ready and pygpi_ready and on_xezim
        and no_hard_error and results_xml and len(cases) >= 11 and all_pass
    )
    print(
        f"PROBE {'PASS' if ok else 'FAIL'} "
        f"(gpi={gpi_ready}, pygpi={pygpi_ready}, xezim={on_xezim}, "
        f"hard_errors={not no_hard_error}, xml={results_xml}, all_pass={all_pass})"
    )
    print(
        "NOTE: 'Initialized cocotb'/'Running on xezim' are Python-logging "
        "messages emitted only by the standard runner; the hand-written path "
        "uses the GPI/pygpi C++ evidence above."
    )
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
