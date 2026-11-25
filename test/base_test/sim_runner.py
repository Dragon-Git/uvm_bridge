"""Simulator build/run logic for test/base_test, without a Makefile.

conftest.py (the pytest driver) and test/uvm_compat/test_compat.py both call
:func:`run` and :func:`lint` here, so the verilator and xezim command lines live
in exactly one place. Environment variables keep their old Makefile names:

  NPROC         parallel verilator compile jobs (default: os.cpu_count())
  RUN_OPTS      extra plusargs appended to the base_test run flags
  MAX_TIME      xezim --max-time (default 10ms)
  XEZIM_PREFIX  xezim install prefix; otherwise derived from `xezim` on PATH
  XEZIM_UVM_SRC path to uvm_pkg.sv, used to derive the xezim UVM home

Pass criteria are unchanged: exit 0 AND the completion marker that base_test.py
prints only when every check passed. Grep for the marker, not the UVM_ERROR
count: base_test.py intentionally raises UVM_ERROR/UVM_FATAL, and xezim stops
silently at --max-time. A ``[VPI]`` diagnostic also fails the run.

Also usable as a CLI, which replaces the old make targets:

    python test/base_test/sim_runner.py run  --sim verilator
    python test/base_test/sim_runner.py run  --sim xezim --uvm-home /tmp/uvm-1.2
    python test/base_test/sim_runner.py lint --uvm-home uvm-verilator/src
"""

import glob
import os
import platform
import shlex
import shutil
import subprocess
import sys
import sysconfig
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TEST_DIR = Path(__file__).resolve().parent
TOP_SV = TEST_DIR / "top.sv"
DEFAULT_BUILD_DIR = TEST_DIR / "build"
DEFAULT_UVM_HOME = ROOT / "uvm-verilator" / "src"

# Written by base_test.py on its last line; xezim also stops silently at
# --max-time, so a zero exit alone does not mean the test ran to the end.
FINISHED = "所有新增API测试完成"

VERILATOR_FLAGS = [
    "--vpi", "--binary", "-top", "top",
    "-Wno-lint", "-Wno-style", "-Wno-SYMRSVDWORD", "-Wno-WIDTHTRUNC",
    "-Wno-WIDTHEXPAND", "-Wno-IGNOREDRETURN", "-Wno-CONSTRAINTIGN",
    "-Wno-ZERODLY", "-Wno-CASTCONST",
]
LINT_FLAGS = [
    "-Wno-fatal", "-Wno-lint", "-Wno-style", "-Wno-SYMRSVDWORD",
    "-Wno-WIDTHTRUNC", "-Wno-WIDTHEXPAND", "-Wno-IGNOREDRETURN",
    "-Wno-CONSTRAINTIGN", "-Wno-ZERODLY", "-Wno-CASTCONST",
    "-DUVM_NO_MALLOC", "-DVERILATOR",
]


class SimError(RuntimeError):
    """A prerequisite is missing; callers surface this as a failure."""


def _exec(cmd, *, env=None, cwd=None):
    try:
        return subprocess.run(
            [str(part) for part in cmd],
            cwd=str(cwd) if cwd else None,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError as exc:
        raise SimError(f"command not found: {cmd[0]} ({exc})") from exc


def _output(proc):
    return proc.stdout + proc.stderr


def _run_flags():
    extra = os.environ.get("RUN_OPTS", "").split()
    return ["+UVM_TESTNAME=base_test", "+UVM_NO_RELNOTES", "+UVM_OBJECTION_TRACE", *extra]


def _nproc():
    raw = os.environ.get("NPROC")
    return int(raw) if raw else (os.cpu_count() or 10)


def _svuvm_dir(python):
    proc = _exec([python, "-c", "import svuvm, os; print(os.path.dirname(svuvm.__file__))"])
    path = proc.stdout.strip()
    if proc.returncode != 0 or not path:
        raise SimError(f"svuvm is not importable with {python}")
    return Path(path)


def _svuvm_config(python):
    """Split ``python -m svuvm.config`` into [sv, so, -LDFLAGS, ldflags]."""
    proc = _exec([python, "-m", "svuvm.config"])
    if proc.returncode != 0:
        raise SimError(f"python -m svuvm.config failed:\n{_output(proc)}")
    parts = shlex.split(proc.stdout.strip())
    if len(parts) != 4:
        raise SimError(f"unexpected svuvm.config output: {proc.stdout!r}")
    return parts


def _libpython(python):
    code = (
        "import sysconfig, os, glob; "
        "d=sysconfig.get_config_var('LIBDIR'); "
        "v=sysconfig.get_config_var('LDVERSION') or ''; "
        "c=[f for p in ('.dylib', '.so') for f in glob.glob(os.path.join(d, 'libpython' + v + p + '*'))]; "
        "print(c[0] if c else '')"
    )
    path = _exec([python, "-c", code]).stdout.strip()
    if not path:
        raise SimError("libpython not found (needed to preload Py* symbols for xezim)")
    return path


def _verdict(rc, out, sim):
    """Apply the completion-marker and [VPI] checks, mirroring the Makefile."""
    if rc != 0:
        return rc, out + f"\n{sim} exited with {rc}\n"
    if FINISHED not in out:
        if sim == "xezim":
            message = "ERROR: Python test did not run to completion (max-time cap?)"
        else:
            message = "ERROR: Python test did not pass all checks"
        return 1, out + f"\n{message}\n"
    diagnostics = [line for line in out.splitlines() if line.startswith("[VPI]")]
    if diagnostics:
        body = "\n".join(diagnostics)
        return 1, out + f"\nERROR: simulator emitted [VPI] diagnostics:\n{body}\n"
    return 0, out


def _verilator_build(python, build_dir, uvm_home):
    sv_file, so_file, _flag, ldflags = _svuvm_config(python)
    jobs = _nproc()
    pre = ["-LDFLAGS", "-Wl,--no-as-needed"] if platform.system() == "Linux" else []
    post = ["-LDFLAGS", "-Wl,--as-needed"] if platform.system() == "Linux" else []
    cflags = f"-I{uvm_home / 'dpi'} -I{ROOT / 'inc'} -DVERILATOR -DUVM_NO_MALLOC"
    cmd = [
        "verilator", "-j", str(jobs), *VERILATOR_FLAGS,
        "-Mdir", build_dir, "--output-groups", str(jobs),
        f"+incdir+{uvm_home}", f"+incdir+{Path(sv_file).parent}",
        uvm_home / "dpi" / "uvm_dpi.cc", uvm_home / "uvm_pkg.sv",
        *pre, sv_file, so_file, "-LDFLAGS", ldflags, TOP_SV, "-CFLAGS", cflags, *post,
    ]
    proc = _exec(cmd, cwd=TEST_DIR)
    return proc.returncode, _output(proc)


def verilator_run(python, build_dir, uvm_home, extra_env):
    build_dir.mkdir(parents=True, exist_ok=True)
    rc, out = _verilator_build(python, build_dir, uvm_home)
    if rc != 0:
        return rc, out

    env = os.environ.copy()
    if extra_env:
        env.update({key: str(value) for key, value in extra_env.items()})
    env["PYTHONPATH"] = str(TEST_DIR)
    # The old Makefile exported this for the macOS loader; harmless on Linux.
    env["DYLD_LIBRARY_PATH"] = str(Path(sysconfig.get_paths()["purelib"]) / "svuvm")

    proc = _exec([build_dir / "Vtop", *_run_flags()], cwd=TEST_DIR, env=env)
    log = _output(proc)
    (build_dir / "verilator.log").write_text(log, encoding="utf-8")
    return _verdict(proc.returncode, log, "verilator")


def _xezim_prefix():
    raw = os.environ.get("XEZIM_PREFIX")
    if raw:
        return Path(raw)
    which = shutil.which("xezim")
    if which:
        return Path(which).resolve().parent.parent
    raise SimError("xezim not on PATH; set XEZIM_PREFIX to the unpacked xezim/ dir")


def _xezim_uvm_home(prefix, uvm_home):
    if uvm_home is not None:
        return Path(uvm_home)
    src = os.environ.get("XEZIM_UVM_SRC")
    if src:
        path = Path(src)
        return path.parent if path.name == "uvm_pkg.sv" else path
    return prefix / "share" / "uvm"


def xezim_run(python, build_dir, uvm_home, max_time, extra_env):
    prefix = _xezim_prefix()
    xezim = prefix / "bin" / "xezim"
    if not xezim.is_file():
        raise SimError(f"{xezim} not found")

    home = _xezim_uvm_home(prefix, uvm_home)
    if not (home / "src" / "uvm_pkg.sv").is_file():
        raise SimError(f"bundled UVM not found at {home}")

    svuvm_dir = _svuvm_dir(python)
    sv = svuvm_dir / "python_bridge_pkg.sv"
    if not sv.is_file():
        raise SimError(f"{sv} not found")
    dpi_libs = sorted(glob.glob(str(svuvm_dir / "_svuvm*.so")))
    if not dpi_libs:
        raise SimError(f"no _svuvm*.so under {svuvm_dir}")
    libpython = _libpython(python)

    dpi_src = prefix / "include" / "uvm_dpi_xezim.cc"
    if not dpi_src.is_file():
        raise SimError(f"{dpi_src} not found")

    build_dir.mkdir(parents=True, exist_ok=True)
    dpi_so = build_dir / "uvm_dpi_xezim.so"
    if platform.system() == "Darwin":
        linker = ["-Wl,-undefined,dynamic_lookup"]
    else:
        linker = ["-Wl,-z,lazy"]
    proc = _exec([
        "c++", "-shared", "-fPIC", *linker, "-std=c++17", "-Wno-format-security",
        "-DUVM_NO_MALLOC", "-I", prefix / "include", "-I", home / "src" / "dpi",
        dpi_src, "-o", dpi_so,
    ])
    if proc.returncode != 0:
        return proc.returncode, _output(proc)

    env = os.environ.copy()
    if extra_env:
        env.update({key: str(value) for key, value in extra_env.items()})
    existing = env.get("PYTHONPATH")
    env["PYTHONPATH"] = str(TEST_DIR) + (os.pathsep + existing if existing else "")
    env["XEZIM_UVM_DIR"] = str(home)

    cmd = [
        xezim, "--simulate", "-s", "top",
        "--dpi-lib", libpython,
        "--dpi-lib", dpi_so.resolve(),
        "--dpi-lib", dpi_libs[0],
        "--max-time", max_time or os.environ.get("MAX_TIME", "10ms"),
        "--error-exit", "-uvm", f"+incdir+{svuvm_dir}", sv, TOP_SV, *_run_flags(),
    ]
    proc = _exec(cmd, cwd=ROOT, env=env)
    log = _output(proc)
    (build_dir / "xezim.log").write_text(log, encoding="utf-8")
    return _verdict(proc.returncode, log, "xezim")


def run(sim, *, python=None, build_dir=None, uvm_home=None, max_time=None, extra_env=None):
    """Run the base test on ``sim``; return ``(returncode, output)``."""
    python = python or sys.executable
    build_dir = Path(build_dir) if build_dir else DEFAULT_BUILD_DIR
    if sim == "verilator":
        return verilator_run(python, build_dir, Path(uvm_home) if uvm_home else DEFAULT_UVM_HOME, extra_env)
    if sim == "xezim":
        return xezim_run(python, build_dir, uvm_home, max_time, extra_env)
    raise SimError(f"unknown simulator {sim!r}")


def lint(*, python=None, uvm_home=None):
    """Elaborate the bridge + top against a UVM source tree; return (rc, output)."""
    python = python or sys.executable
    home = Path(uvm_home) if uvm_home else DEFAULT_UVM_HOME
    sv = _svuvm_dir(python) / "python_bridge_pkg.sv"
    cmd = [
        "verilator", "--lint-only", "-top", "top", *LINT_FLAGS,
        f"+incdir+{home}", f"+incdir+{sv.parent}",
        f"-I{home / 'dpi'}", f"-I{ROOT / 'inc'}",
        home / "uvm_pkg.sv", sv, TOP_SV,
    ]
    proc = _exec(cmd, cwd=TEST_DIR)
    return proc.returncode, _output(proc)


def main(argv=None):
    import argparse

    parser = argparse.ArgumentParser(description="Build/run test/base_test without make")
    sub = parser.add_subparsers(dest="action", required=True)
    for action in ("run", "lint"):
        p = sub.add_parser(action)
        p.add_argument("--sim", default=os.environ.get("SIM", "verilator"), choices=["verilator", "xezim"])
        p.add_argument("--uvm-home")
        p.add_argument("--build-dir")
        p.add_argument("--max-time")
    args = parser.parse_args(argv)
    try:
        if args.action == "lint":
            rc, out = lint(uvm_home=args.uvm_home)
        else:
            rc, out = run(
                args.sim,
                build_dir=args.build_dir,
                uvm_home=args.uvm_home,
                max_time=args.max_time,
            )
    except SimError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(out, end="")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
