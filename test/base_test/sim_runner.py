"""Simulator build/run logic for test/base_test, without a Makefile.

conftest.py (the pytest driver) and test/uvm_compat/test_compat.py both call
:func:`run` and :func:`lint` here, so the verilator and xezim command lines live
in exactly one place. test/cocotb_test/conftest.py calls :func:`cocotb_run`,
which shares the svuvm/UVM build flags (including the critical +incdir for the
generated export header) with :func:`verilator_run`. Environment variables keep
their old Makefile names:

  NPROC         parallel verilator compile jobs (default: os.cpu_count())
  RUN_OPTS      extra plusargs appended to the base_test run flags
  MAX_TIME      xezim --max-time (simulation time, default 10ms)
  SIM_TIMEOUT   wall-clock cap for one simulator run (default 300s)
  SIM_BUILD_TIMEOUT wall-clock cap for one compile (default SIM_TIMEOUT * 2)
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

from __future__ import annotations

import glob
import hashlib
import math
import os
import platform
import shlex
import shutil
import subprocess
import sys
import sysconfig
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ral_common.spec import SimConfig

ROOT = Path(__file__).resolve().parents[2]
TEST_DIR = Path(__file__).resolve().parent
TOP_SV = TEST_DIR / "top.sv"
COCOTB_TEST_DIR = ROOT / "test" / "cocotb_test"
COCOTB_TOP_SV = COCOTB_TEST_DIR / "top.sv"
DEFAULT_BUILD_DIR = TEST_DIR / "build"
DEFAULT_COCOTB_BUILD_DIR = COCOTB_TEST_DIR / "build"
DEFAULT_UVM_HOME = ROOT / "uvm-verilator" / "src"

# Written by base_test.py on its last line; xezim also stops silently at
# --max-time, so a zero exit alone does not mean the test ran to the end.
FINISHED = "所有新增API测试完成"

# Shared by the base_test (--binary) and cocotb (-cc --exe --build) builds so
# the two drivers cannot drift apart on warning suppression.
VERILATOR_WARNINGS = [
    "-Wno-lint", "-Wno-style", "-Wno-SYMRSVDWORD", "-Wno-WIDTHTRUNC",
    "-Wno-WIDTHEXPAND", "-Wno-IGNOREDRETURN", "-Wno-CONSTRAINTIGN",
    "-Wno-ZERODLY", "-Wno-CASTCONST",
]
VERILATOR_FLAGS = ["--vpi", "--binary", "-top", "top", *VERILATOR_WARNINGS]
LINT_FLAGS = [
    "-Wno-fatal", "-Wno-lint", "-Wno-style", "-Wno-SYMRSVDWORD",
    "-Wno-WIDTHTRUNC", "-Wno-WIDTHEXPAND", "-Wno-IGNOREDRETURN",
    "-Wno-CONSTRAINTIGN", "-Wno-ZERODLY", "-Wno-CASTCONST",
    "-DUVM_NO_MALLOC", "-DVERILATOR",
]


class SimError(RuntimeError):
    """A prerequisite is missing; callers surface this as a failure."""


class SimTimeoutError(SimError):
    """A simulator/compiler run was killed after its wall-clock cap.

    Subclasses :class:`SimError` so every existing ``except SimError`` caller
    stays valid, while fixtures that skip *missing prerequisites* can treat a
    hang as a hard failure instead of a silent skip.
    """


DEFAULT_SIM_TIMEOUT = 300.0


def _env_timeout(name: str, default: float) -> float:
    """Read a positive timeout in seconds from ``name``, else return ``default``.

    A malformed or non-finite value is diagnosed on stderr and ignored: a typo
    in the environment must neither hang forever nor kill every run instantly.
    """
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return default
    try:
        value = float(raw)
    except ValueError:
        print(f"WARNING: {name}={raw!r} is not a number; using {default:g}s", file=sys.stderr)
        return default
    if not math.isfinite(value) or value <= 0:
        print(f"WARNING: {name}={raw!r} is not a positive finite number; using {default:g}s", file=sys.stderr)
        return default
    return value


def _sim_timeout() -> float:
    """Wall-clock seconds granted to one simulator run (``SIM_TIMEOUT``)."""
    return _env_timeout("SIM_TIMEOUT", DEFAULT_SIM_TIMEOUT)


def _build_timeout() -> float:
    """Wall-clock seconds granted to one compile (``SIM_BUILD_TIMEOUT``).

    Compilation is routinely slower than the run itself, so the default is
    twice the simulator cap and stays independent of simulation-time caps.
    """
    return _env_timeout("SIM_BUILD_TIMEOUT", _sim_timeout() * 2)


def _as_text(value) -> str:
    """Render captured subprocess output whether it is bytes, str or None."""
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value)


def _exec(cmd, *, env=None, cwd=None, timeout: float | None = None):
    """Run ``cmd`` without a shell; ``timeout`` caps wall-clock seconds.

    ``timeout=None`` keeps the original unbounded behaviour verbatim. On a
    timeout :func:`subprocess.run` has already killed and reaped the child;
    whatever it managed to print is attached to :class:`SimTimeoutError`.
    """
    try:
        return subprocess.run(
            [str(part) for part in cmd],
            cwd=str(cwd) if cwd else None,
            env=env,
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout,
        )
    except FileNotFoundError as exc:
        raise SimError(f"command not found: {cmd[0]} ({exc})") from exc
    except subprocess.TimeoutExpired as exc:
        command = " ".join(str(part) for part in cmd)
        stdout = _as_text(exc.stdout).strip()
        stderr = _as_text(exc.stderr).strip()
        message = f"command timed out after {timeout} seconds (killed): {command}"
        if stdout:
            message += f"\n--- partial stdout ---\n{stdout}"
        if stderr:
            message += f"\n--- partial stderr ---\n{stderr}"
        if not stdout and not stderr:
            message += "\n(no output captured before timeout)"
        raise SimTimeoutError(message) from exc


def _output(proc):
    return proc.stdout + proc.stderr


def _run_flags(config=None):
    """Build simulator plusargs; ``config=None`` is the untouched base path."""
    extra = os.environ.get("RUN_OPTS", "").split()
    if config is None:
        return ["+UVM_TESTNAME=base_test", "+UVM_NO_RELNOTES", "+UVM_OBJECTION_TRACE", *extra]
    flags = [f"+UVM_TESTNAME={config.uvm_testname}", "+UVM_NO_RELNOTES"]
    if config.py_dir:
        flags.append(f"+PY_DIR={config.py_dir}")
    flags.extend(config.run_flags)
    flags.extend(extra)
    return flags


def _cases_only(config):
    """True when the RAL verdict rule applies (no ``[VPI]`` diagnostics)."""
    if config is None:
        return False
    verdict = getattr(config, "verdict", None)
    return str(getattr(verdict, "value", verdict)) == "cases"


def _validate_config(config):
    """Fail loudly on a missing source, incdir or Python entry directory."""
    missing: list[str] = []
    if not config.top_sv.is_file():
        missing.append(f"top.sv {config.top_sv}")
    for path in config.sv_sources:
        if not Path(path).is_file():
            missing.append(f"SV source {path}")
    for path in config.incdirs:
        if not Path(path).is_dir():
            missing.append(f"incdir {path}")
    if config.py_dir and not Path(config.py_dir).is_dir():
        missing.append(f"PY_DIR {config.py_dir}")
    if missing:
        raise SimError("missing RAL simulation inputs: " + ", ".join(missing))


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


def _verdict(rc, out, sim, config=None):
    """Apply the completion-marker and [VPI] checks, mirroring the Makefile.

    With a RAL ``config`` the marker is suite-supplied and ``[VPI]`` diagnostics
    are irrelevant (RAL produces none); the JSON cases are the verdict there.
    """
    if rc != 0:
        return rc, out + f"\n{sim} exited with {rc}\n"
    marker = FINISHED if config is None else config.completion_marker
    if marker not in out:
        if sim == "xezim":
            message = "ERROR: Python test did not run to completion (max-time cap?)"
        else:
            message = "ERROR: Python test did not pass all checks"
        return 1, out + f"\n{message}\n"
    if _cases_only(config):
        return 0, out
    diagnostics = [line for line in out.splitlines() if line.startswith("[VPI]")]
    if diagnostics:
        body = "\n".join(diagnostics)
        return 1, out + f"\nERROR: simulator emitted [VPI] diagnostics:\n{body}\n"
    return 0, out


def _verilator_build(python, build_dir, uvm_home, config=None):
    sv_file, so_file, _flag, ldflags = _svuvm_config(python)
    jobs = _nproc()
    pre = ["-LDFLAGS", "-Wl,--no-as-needed"] if platform.system() == "Linux" else []
    post = ["-LDFLAGS", "-Wl,--as-needed"] if platform.system() == "Linux" else []
    cflags = f"-I{uvm_home / 'dpi'} -I{ROOT / 'inc'} -DVERILATOR -DUVM_NO_MALLOC"
    includes = [f"+incdir+{uvm_home}", f"+incdir+{Path(sv_file).parent}"]
    core_sources = [uvm_home / "dpi" / "uvm_dpi.cc", uvm_home / "uvm_pkg.sv"]
    if config is None:
        cmd = [
            "verilator", "-j", str(jobs), *VERILATOR_FLAGS,
            "-Mdir", build_dir, "--output-groups", str(jobs),
            *includes,
            *core_sources,
            *pre, sv_file, so_file, "-LDFLAGS", ldflags, TOP_SV, "-CFLAGS", cflags, *post,
        ]
        cwd = TEST_DIR
    else:
        # RAL: every extra package/RTL file is passed explicitly, in order,
        # and each suite incdir is visible to `import` and `include`.
        includes.extend(f"+incdir+{Path(path)}" for path in config.incdirs)
        # Extra warnings are suite-scoped: base_test keeps its exact old list.
        warnings = [*VERILATOR_FLAGS, *config.verilator_warnings]
        cmd = [
            "verilator", "-j", str(jobs), *warnings,
            "-Mdir", build_dir, "--output-groups", str(jobs),
            *includes,
            *core_sources,
            *pre, sv_file, so_file, "-LDFLAGS", ldflags,
            *config.sv_sources, config.top_sv,
            "-CFLAGS", cflags, *post,
        ]
        cwd = config.test_dir
    proc = _exec(cmd, cwd=cwd, timeout=_build_timeout())
    return proc.returncode, _output(proc)


def _pythonpath(config, env):
    """Return the PYTHONPATH for a RAL config, preserving the existing tail."""
    parts = [str(Path(config.test_dir))]
    parts.extend(str(Path(path)) for path in config.pythonpath_roots)
    if config.py_dir:
        parts.append(str(config.py_dir))
    existing = env.get("PYTHONPATH")
    if existing:
        parts.append(existing)
    return os.pathsep.join(parts)


def verilator_run(python, build_dir, uvm_home, extra_env, config=None):
    build_dir.mkdir(parents=True, exist_ok=True)
    rc, out = _verilator_build(python, build_dir, uvm_home, config)
    if rc != 0:
        return rc, out

    env = os.environ.copy()
    if extra_env:
        env.update({key: str(value) for key, value in extra_env.items()})
    if config is None:
        env["PYTHONPATH"] = str(TEST_DIR)
        cwd = TEST_DIR
    else:
        env["PYTHONPATH"] = _pythonpath(config, env)
        cwd = config.test_dir
    # The old Makefile exported this for the macOS loader; harmless on Linux.
    env["DYLD_LIBRARY_PATH"] = str(Path(sysconfig.get_paths()["purelib"]) / "svuvm")

    proc = _exec([build_dir / "Vtop", *_run_flags(config)], cwd=cwd, env=env, timeout=_sim_timeout())
    log = _output(proc)
    (build_dir / "verilator.log").write_text(log, encoding="utf-8")
    return _verdict(proc.returncode, log, "verilator", config)


def _cocotb_config(python, option, required=True):
    """Return one ``python -m cocotb_tools.config`` value."""
    proc = _exec([python, "-m", "cocotb_tools.config", option])
    value = proc.stdout.strip()
    if proc.returncode != 0 or (required and not value):
        raise SimError(
            f"cocotb_tools.config {option} failed with {python}:\n{_output(proc)}"
        )
    return value


def _cocotb_build(python, build_dir, uvm_home, cocotb_lib_dir, verilator_cpp):
    """Compile the cocotb top with the same svuvm/UVM sources as base_test."""
    sv_file, so_file, _flag, ldflags = _svuvm_config(python)
    jobs = _nproc()
    pre = ["-LDFLAGS", "-Wl,--no-as-needed"] if platform.system() == "Linux" else []
    post = ["-LDFLAGS", "-Wl,--as-needed"] if platform.system() == "Linux" else []
    cflags = f"-I{uvm_home / 'dpi'} -I{ROOT / 'inc'} -DVERILATOR -DUVM_NO_MALLOC"
    # Keep every cocotb VPI library in the link: the simulator binary resolves
    # these symbols through GPI_USERS at run time instead of via a direct call.
    cocotb_ldflags = (
        f"{ldflags} -L{cocotb_lib_dir} -Wl,-rpath,{cocotb_lib_dir} -lcocotbvpi_verilator"
    )
    cmd = [
        "verilator", "-j", str(jobs), "--vpi", "-cc", "--exe", "--build", "--timing",
        "-top", "top", "-Mdir", build_dir, "--output-groups", str(jobs),
        *VERILATOR_WARNINGS,
        # +incdir for the UVM package AND for the installed svuvm package:
        # python_bridge_pkg.sv includes python_bridge_pkg_export.svh from its
        # own directory. Omitting the second one was the cause of CI failure
        # 45630027133; keep it here as well as in _verilator_build/lint.
        f"+incdir+{uvm_home}", f"+incdir+{Path(sv_file).parent}",
        uvm_home / "dpi" / "uvm_dpi.cc", uvm_home / "uvm_pkg.sv",
        *pre, sv_file, so_file,
        "-LDFLAGS", cocotb_ldflags,
        COCOTB_TOP_SV, "-CFLAGS", cflags, *post,
        verilator_cpp,
    ]
    # ccache keys a compilation by the command line, but clang's PCH stores
    # the *absolute* path of the -Mdir header it was generated from. The
    # pre-pytest cocotb Makefile ran from the repository root with
    # "-Mdir build", so .ccache-vlt still holds a Vtop__pch.h.fast.gch that
    # names <repo>/build/Vtop__pch.h. Serving that entry to this build, which
    # uses -Mdir <repo>/test/cocotb_test/build, makes clang abort with
    # "malformed or corrupted precompiled file ... could not find file
    # '<repo>/build/Vtop__pch.h'". Give cocotb its own ccache namespace keyed
    # by the build directory: entries produced for another -Mdir can never be
    # served here, while repeated runs in the same directory still hit cache.
    # base_test and the wheel build keep their existing warmed caches.
    env = os.environ.copy()
    ccache_root = env.get("CCACHE_DIR")
    if ccache_root:
        mdir_key = hashlib.sha256(str(Path(build_dir).resolve()).encode("utf-8")).hexdigest()[:12]
        env["CCACHE_DIR"] = str(Path(ccache_root) / f"cocotb-{mdir_key}")
    proc = _exec(cmd, cwd=COCOTB_TEST_DIR, env=env, timeout=_build_timeout())
    return proc.returncode, _output(proc)


def cocotb_run(python, build_dir, uvm_home, extra_env):
    """Build and run ``test/cocotb_test``; return ``(returncode, log)``.

    Unlike :func:`verilator_run` this deliberately does not apply
    :func:`_verdict`: cocotb can report a failed test while Vtop still exits
    zero. The caller must consult the ``SVUVM_RESULT_JSON`` payload for the
    per-case verdict and only treat a nonzero returncode as a hard failure.
    """
    if not COCOTB_TOP_SV.is_file():
        raise SimError(f"{COCOTB_TOP_SV} not found")
    build_dir = Path(build_dir)

    share = _cocotb_config(python, "--share")
    lib_dir = _cocotb_config(python, "--lib-dir")
    libpython = _cocotb_config(python, "--libpython")
    python_bin = _cocotb_config(python, "--python-bin")
    pygpi_entry = _cocotb_config(python, "--pygpi-entry-point", required=False)
    verilator_cpp = Path(share) / "lib" / "verilator" / "verilator.cpp"
    if not verilator_cpp.is_file():
        raise SimError(f"cocotb verilator shim not found at {verilator_cpp}")

    build_dir.mkdir(parents=True, exist_ok=True)
    rc, out = _cocotb_build(python, build_dir, uvm_home, lib_dir, verilator_cpp)
    if rc != 0:
        return rc, out

    env = os.environ.copy()
    if extra_env:
        env.update({key: str(value) for key, value in extra_env.items()})
    existing = env.get("PYTHONPATH")
    env["PYTHONPATH"] = str(COCOTB_TEST_DIR) + (os.pathsep + existing if existing else "")
    env["DYLD_LIBRARY_PATH"] = str(Path(sysconfig.get_paths()["purelib"]) / "svuvm")
    # cocotb 2.1 splits the simulator-side loader (GPI_USERS) from the
    # Python-side entry point (PYGPI_USERS). GPI_USERS contains a semicolon,
    # so it must be passed through the env dict, never through a shell line.
    env["GPI_USERS"] = f"{libpython};{pygpi_entry}" if pygpi_entry else libpython
    env["PYGPI_USERS"] = "cocotb._init:init_package_from_simulation"
    env["PYGPI_PYTHON_BIN"] = python_bin
    env["COCOTB_TEST_MODULES"] = "base_test"
    env["COCOTB_RESULTS_FILE"] = str(build_dir / "results.xml")

    proc = _exec([build_dir / "Vtop", *_run_flags()], cwd=COCOTB_TEST_DIR, env=env, timeout=_sim_timeout())
    log = _output(proc)
    (build_dir / "cocotb.log").write_text(log, encoding="utf-8")
    return proc.returncode, log


def _cocotb_vpi_lib(python):
    """Resolve cocotb's plain IEEE 1800 VPI library (``vcs`` flavour by default).

    This mirrors the vendored runner's ``_vpi_lib`` property, including its
    2.0/2.1 fallback, but keeps the resolution in a subprocess so importing
    this module never imports cocotb into the pytest process.
    """
    flavour = os.environ.get("XEZIM_COCOTB_VPI_FLAVOUR", "vcs")
    code = (
        "import cocotb_tools.config as c; "
        "p = getattr(c, 'lib_name_path', None); "
        f"print(p('vpi', {flavour!r}) if p else c.libs_dir + '/' + c.lib_name('vpi', {flavour!r}))"
    )
    proc = _exec([python, "-c", code])
    path = proc.stdout.strip()
    if proc.returncode != 0 or not path or not Path(path).is_file():
        raise SimError(f"cocotb VPI lib ({flavour} flavour) not found: {path or _output(proc)}")
    return path


def _build_cocotb_uvm_dpi(build_dir: Path, prefix: Path, home: Path) -> Path:
    """Compile ``uvm_dpi_xezim.cc`` into ``<build_dir>/uvm_dpi_xezim.so``.

    Same recipe as :func:`xezim_run`. The shim has unresolved UVM DPI symbols
    and must be elaborated together with ``uvm_pkg.sv`` + ``-uvm`` (E11), which
    :func:`_cocotb_xezim_command` does. Compiler failures are raised as
    :class:`SimError` with the full output so the fixture fails loudly.
    """
    dpi_src = prefix / "include" / "uvm_dpi_xezim.cc"
    if not dpi_src.is_file():
        raise SimError(f"{dpi_src} not found")
    build_dir = Path(build_dir)
    build_dir.mkdir(parents=True, exist_ok=True)
    dpi_so = build_dir / "uvm_dpi_xezim.so"
    linker = (
        ["-Wl,-undefined,dynamic_lookup"]
        if platform.system() == "Darwin"
        else ["-Wl,-z,lazy"]
    )
    proc = _exec([
        "c++", "-shared", "-fPIC", *linker, "-std=c++17", "-Wno-format-security",
        "-DUVM_NO_MALLOC", "-I", prefix / "include", "-I", home / "src" / "dpi",
        dpi_src, "-o", dpi_so,
    ], timeout=_build_timeout())
    if proc.returncode != 0:
        raise SimError(f"uvm_dpi_xezim.so build failed:\n{_output(proc)}")
    if not dpi_so.is_file():
        raise SimError(f"uvm_dpi_xezim.so was not produced at {dpi_so}")
    return dpi_so


def _cocotb_xezim_command(python, build_dir, uvm_home, vpi_lib, libpython,
                          pygpi_entry, uvm_dpi_so, dpi_libs, sv_file, max_time) -> list[str]:
    """Assemble the xezim command that runs the cocotb regression.

    Reproduces the vendored runner's ``_test_command`` semantics (one VPI
    library, ``--sv2017``, ``-s top``, plusargs from ``_run_flags``) and adds
    the svuvm/UVM DPI assembly from design section 5.1. ``python`` and
    ``pygpi_entry`` are kept for signature parity: they configure the
    environment in :func:`cocotb_run_xezim`, not the command line.
    """
    prefix = _xezim_prefix()
    xezim = prefix / "bin" / "xezim"
    if not xezim.is_file():
        raise SimError(f"{xezim} not found")
    home = _xezim_uvm_home(prefix, uvm_home)
    uvm_pkg = home / "src" / "uvm_pkg.sv"
    if not uvm_pkg.is_file():
        raise SimError(f"bundled UVM not found at {home}")
    svuvm_dir = Path(sv_file).parent

    cmd = [
        xezim, "--simulate", "--sv2017",
        "--vpi-lib", vpi_lib,
        "--dpi-lib", libpython,
        "--dpi-lib", Path(uvm_dpi_so).resolve(),
        *(part for lib in dpi_libs for part in ("--dpi-lib", lib)),
        "-uvm", "-s", "top",
        f"+incdir+{home}", f"+incdir+{svuvm_dir}",
        uvm_pkg, sv_file, COCOTB_TOP_SV,
        *_run_flags(),
        "--max-time", max_time or os.environ.get("MAX_TIME", "10ms"),
        "--error-exit",
    ]
    return [str(part) for part in cmd]


def cocotb_run_xezim(python, build_dir, uvm_home, extra_env, max_time=None) -> tuple[int, str]:
    """Run ``test/cocotb_test`` on xezim; return ``(returncode, log)``.

    Like :func:`cocotb_run` this deliberately does not apply :func:`_verdict`:
    cocotb reports per-case failures through ``SVUVM_RESULT_JSON`` while the
    simulator may still exit zero. Only a nonzero returncode is a hard failure.
    All prerequisite checks raise :class:`SimError` instead of silently
    skipping a missing library or source.
    """
    if not COCOTB_TOP_SV.is_file():
        raise SimError(f"{COCOTB_TOP_SV} not found")
    build_dir = Path(build_dir)

    prefix = _xezim_prefix()
    xezim = prefix / "bin" / "xezim"
    if not xezim.is_file():
        raise SimError(f"{xezim} not found")
    home = _xezim_uvm_home(prefix, uvm_home)
    if not (home / "src" / "uvm_pkg.sv").is_file():
        raise SimError(f"bundled UVM not found at {home}")

    svuvm_dir = _svuvm_dir(python)
    sv_file = svuvm_dir / "python_bridge_pkg.sv"
    if not sv_file.is_file():
        raise SimError(f"{sv_file} not found")
    dpi_libs = sorted(glob.glob(str(svuvm_dir / "_svuvm*.so")))
    if not dpi_libs:
        raise SimError(f"no _svuvm*.so under {svuvm_dir}")

    vpi_lib = _cocotb_vpi_lib(python)
    libpython = _libpython(python)
    pygpi_entry = _cocotb_config(python, "--pygpi-entry-point", required=False)
    if not pygpi_entry:
        raise SimError("cocotb --pygpi-entry-point is required for xezim GPI_USERS")
    libs_dir = _cocotb_config(python, "--lib-dir")

    dpi_so = _build_cocotb_uvm_dpi(build_dir, prefix, home)
    cmd = _cocotb_xezim_command(
        python, build_dir, uvm_home, vpi_lib, libpython, pygpi_entry,
        dpi_so, dpi_libs, sv_file, max_time,
    )

    env = os.environ.copy()
    if extra_env:
        env.update({key: str(value) for key, value in extra_env.items()})
    # PYTHONPATH must contain the cocotb_test directory so both
    # py_task("base_test", "main") and COCOTB_TEST_MODULES resolve to the same
    # simulator-side module. Do NOT prepend site-packages here: in the
    # embedded interpreter PYTHONPATH entries precede the stdlib, and a PyPI
    # `argparse` backport installed there would shadow the stdlib module
    # (cocotb's regression then fails on `allow_abbrev`). site-packages is
    # already on the embedded interpreter's path via normal site init.
    parts = [str(COCOTB_TEST_DIR)]
    existing = env.get("PYTHONPATH")
    if existing:
        parts.append(existing)
    env["PYTHONPATH"] = os.pathsep.join(parts)
    # U4: GPI_USERS and --dpi-lib must use the SAME libpython. sysconfig and
    # cocotb_tools.config point at different interpreters in this environment,
    # so both places go through _libpython() (the sysconfig-derived path).
    env["GPI_USERS"] = f"{libpython};{pygpi_entry}"
    env["PYGPI_USERS"] = "cocotb._init:init_package_from_simulation"
    env["PYGPI_PYTHON_BIN"] = python
    env["COCOTB_TEST_MODULES"] = "base_test"
    env["COCOTB_RESULTS_FILE"] = str(build_dir / "results.xml")
    env["XEZIM_UVM_DIR"] = str(home)
    ld_parts = [libs_dir, str(svuvm_dir)]
    existing_ld = env.get("LD_LIBRARY_PATH")
    if existing_ld:
        ld_parts.append(existing_ld)
    env["LD_LIBRARY_PATH"] = os.pathsep.join(ld_parts)

    proc = _exec(cmd, cwd=COCOTB_TEST_DIR, env=env, timeout=_sim_timeout())
    log = _output(proc)
    (build_dir / "xezim.log").write_text(log, encoding="utf-8")
    return proc.returncode, log


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


def xezim_run(python, build_dir, uvm_home, max_time, extra_env, config=None):
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
    ], timeout=_build_timeout())
    if proc.returncode != 0:
        return proc.returncode, _output(proc)

    env = os.environ.copy()
    if extra_env:
        env.update({key: str(value) for key, value in extra_env.items()})
    if config is None:
        existing = env.get("PYTHONPATH")
        env["PYTHONPATH"] = str(TEST_DIR) + (os.pathsep + existing if existing else "")
        top = TOP_SV
        extra_sources: list[Path] = []
        extra_incdirs: list[str] = []
    else:
        # The old Makefile put py_dir first so `reg_test` and `svuvm_hwio`
        # resolve before anything else on the simulator's PYTHONPATH.
        env["PYTHONPATH"] = _pythonpath(config, env)
        top = config.top_sv
        extra_sources = [Path(path) for path in config.sv_sources]
        extra_incdirs = [f"+incdir+{Path(path)}" for path in config.incdirs]
    env["XEZIM_UVM_DIR"] = str(home)

    cmd = [
        xezim, "--simulate", "-s", "top",
        "--dpi-lib", libpython,
        "--dpi-lib", dpi_so.resolve(),
        "--dpi-lib", dpi_libs[0],
        "--max-time", max_time or os.environ.get("MAX_TIME", "10ms"),
        "--error-exit", "-uvm", f"+incdir+{svuvm_dir}", *extra_incdirs,
        sv, *extra_sources, top, *_run_flags(config),
    ]
    proc = _exec(cmd, cwd=ROOT, env=env, timeout=_sim_timeout())
    log = _output(proc)
    (build_dir / "xezim.log").write_text(log, encoding="utf-8")
    return _verdict(proc.returncode, log, "xezim", config)


def run(sim, *, config: SimConfig | None = None, python=None, build_dir=None,
        uvm_home=None, max_time=None, extra_env=None):
    """Run a test on ``sim``; return ``(returncode, output)``.

    With ``config=None`` (base_test / cocotb callers) every argument and
    default below is identical to the pre-parameterization implementation.
    A RAL ``config`` supplies its own sources, incdirs, UVM test, PY_DIR and
    verdict rule; the explicit ``extra_env`` still wins over config defaults.
    """
    python = python or sys.executable
    build_dir = Path(build_dir) if build_dir else DEFAULT_BUILD_DIR
    if config is not None:
        _validate_config(config)
        extra_env = config.merged_env(extra_env)
    if sim == "verilator":
        return verilator_run(python, build_dir, Path(uvm_home) if uvm_home else DEFAULT_UVM_HOME, extra_env, config)
    if sim == "xezim":
        return xezim_run(python, build_dir, uvm_home, max_time, extra_env, config)
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
    proc = _exec(cmd, cwd=TEST_DIR, timeout=_build_timeout())
    return proc.returncode, _output(proc)


def main(argv=None):
    import argparse

    parser = argparse.ArgumentParser(description="Build/run the base and cocotb tests without make")
    sub = parser.add_subparsers(dest="action", required=True)
    for action in ("run", "lint"):
        p = sub.add_parser(action)
        p.add_argument("--sim", default=os.environ.get("SIM", "verilator"), choices=["verilator", "xezim"])
        p.add_argument("--uvm-home")
        p.add_argument("--build-dir")
        p.add_argument("--max-time")
    cocotb_parser = sub.add_parser("cocotb", help="run test/cocotb_test on verilator or xezim")
    cocotb_parser.add_argument("--sim", default=os.environ.get("SIM", "verilator"),
                               choices=["verilator", "xezim"])
    cocotb_parser.add_argument("--uvm-home")
    cocotb_parser.add_argument("--build-dir")
    cocotb_parser.add_argument("--max-time")
    args = parser.parse_args(argv)
    try:
        if args.action == "lint":
            rc, out = lint(uvm_home=args.uvm_home)
        elif args.action == "cocotb" and args.sim == "xezim":
            xezim_build = (
                Path(args.build_dir) if args.build_dir else DEFAULT_COCOTB_BUILD_DIR / "xezim"
            )
            rc, out = cocotb_run_xezim(
                sys.executable,
                xezim_build,
                Path(args.uvm_home) if args.uvm_home else None,
                None,
                args.max_time,
            )
        elif args.action == "cocotb":
            rc, out = cocotb_run(
                sys.executable,
                Path(args.build_dir) if args.build_dir else DEFAULT_COCOTB_BUILD_DIR,
                Path(args.uvm_home) if args.uvm_home else DEFAULT_UVM_HOME,
                None,
            )
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
