"""Shared configuration objects and static case tables for the RAL suites.

Everything the three RAL tests (pyral / unicorn / renode) differ on is a
value in this module: which SystemVerilog sources to elaborate, which UVM test
to select, which Python entry point to call, which completion marker to grep,
and which check labels the simulator side must report. Keeping the labels here
means the simulator-side ``ResultWriter`` and the pytest-side parametrization
can never drift apart.

The tables are plain tuples so they can be imported inside the simulator's
embedded Python without pulling in pytest.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


class VerdictPolicy(str, Enum):
    """How ``sim_runner`` decides a simulator run reached its end.

    ``BaseLegacy`` is the untouched base_test rule: completion marker plus a
    rejection of any ``[VPI]`` diagnostic. ``CasesOnly`` is the RAL rule: the
    marker proves the Python side ran to the end, and the per-case JSON is the
    only source of pass/fail (RAL produces no ``[VPI]`` diagnostics).
    """

    BaseLegacy = "base_legacy"
    CasesOnly = "cases"


@dataclass(frozen=True)
class SimConfig:
    """Parameterized inputs for ``sim_runner.run``.

    A ``None`` config keeps every base_test / cocotb code path byte-for-byte
    unchanged. Supplying a config replaces only the hard-coded values: the
    top module, extra SV sources, include dirs, ``+UVM_TESTNAME``, ``+PY_DIR``,
    completion marker, verdict rule, extra run flags, extra environment and
    the PYTHONPATH roots the simulator-side Python needs.

    Attributes:
        test_dir: Directory used as the build/run cwd and the first PYTHONPATH
            entry.
        top_sv: The top-level SystemVerilog file.
        sv_sources: Additional SV files, in elaboration order (packages
            before the files that import them).
        incdirs: Directories passed as ``+incdir+`` to the simulator.
        uvm_testname: Value of ``+UVM_TESTNAME``.
        py_dir: Directory holding the simulator-side entry module; also added
            to PYTHONPATH and passed as ``+PY_DIR``.
        pythonpath_roots: Additional PYTHONPATH entries (e.g. a generated
            model directory).
        completion_marker: Text that must appear in the log to prove the
            Python side finished.
        verdict: Marker/[VPI] policy.
        run_flags: Extra plusargs appended after ``+UVM_TESTNAME``.
        verilator_warnings: Extra ``-Wno-*`` flags for the config path only.
            The base_test flag list is never modified.
        extra_env: Environment variables always injected for this suite.
        build_root: Backend-independent build root; the driver supplies the
            actual per-backend ``build_dir`` argument.
    """

    test_dir: Path
    top_sv: Path
    sv_sources: tuple[Path, ...] = ()
    incdirs: tuple[Path, ...] = ()
    uvm_testname: str = "base_test"
    py_dir: str = ""
    pythonpath_roots: tuple[Path, ...] = ()
    completion_marker: str = "所有新增API测试完成"
    verdict: VerdictPolicy = VerdictPolicy.CasesOnly
    run_flags: tuple[str, ...] = ()
    verilator_warnings: tuple[str, ...] = ()
    extra_env: dict[str, str] = field(default_factory=dict)
    build_root: Path | None = None

    def merged_env(self, extra_env: dict[str, str] | None) -> dict[str, str]:
        """Overlay the caller's explicit environment on the suite defaults.

        Explicit values win, so a per-run ``SVUVM_RESULT_JSON`` always
        overrides a suite-level default.

        Args:
            extra_env: Caller-provided environment, may be ``None``.

        Returns:
            A new dictionary; neither input is mutated.
        """
        merged = {key: str(value) for key, value in self.extra_env.items()}
        if extra_env:
            merged.update({key: str(value) for key, value in extra_env.items()})
        return merged


@dataclass(frozen=True)
class ArtifactSpec:
    """What a suite needs generated, and where the outputs must land."""

    root: Path
    rdl: Path
    need_pyral: bool = False
    need_regblock: bool = False
    need_cheader: bool = False
    need_firmware: bool = False
    gen_dir: Path | None = None
    rtl_dir: Path | None = None
    header_dir: Path | None = None
    build_dir: Path | None = None
    rdl_module: str = "demo_reg_block"

    def __post_init__(self) -> None:
        """Fill derived paths so callers only have to name the suite root."""
        object.__setattr__(self, "root", Path(self.root))
        object.__setattr__(self, "rdl", Path(self.rdl))
        if self.gen_dir is None:
            object.__setattr__(self, "gen_dir", self.root / "gen")
        if self.rtl_dir is None:
            object.__setattr__(self, "rtl_dir", self.root / "rtl")
        if self.header_dir is None:
            object.__setattr__(self, "header_dir", self.root / "c_header")
        if self.build_dir is None:
            object.__setattr__(self, "build_dir", self.root / "build")
        object.__setattr__(self, "gen_dir", Path(self.gen_dir))
        object.__setattr__(self, "rtl_dir", Path(self.rtl_dir))
        object.__setattr__(self, "header_dir", Path(self.header_dir))
        object.__setattr__(self, "build_dir", Path(self.build_dir))


@dataclass(frozen=True)
class RALSuiteSpec:
    """Everything the shared driver needs to run one RAL suite."""

    suite: str
    cases: tuple[str, ...]
    sim: SimConfig
    artifacts: ArtifactSpec
    emulator: str = "verilator,xezim"
    needs_renode: bool = False


# The eight labels reg_test.py reports. These are the single source of truth:
# conftest.py parametrizes them and reg_test.py names its cases from the same
# tuple, so a renamed check is a missing case rather than a silent pass.
PYRAL_CASES: tuple[str, ...] = (
    "scratch initial",
    "scratch write/read",
    "scratch change_fields",
    "ctrl value",
    "ctrl.enable",
    "ctrl.mode",
    "status initial",
    "status ignores writes",
)

# Derived from test/fw/layout.py:EXPECTED plus the final read-sum check.
FIRMWARE_CASES: tuple[str, ...] = (
    "access 0: R 0x008",
    "access 1: W 0x008",
    "access 2: R 0x008",
    "access 3: W 0x000",
    "access 4: R 0x000",
    "access 5: R 0x004",
    "access 6: W 0x004",
    "access 7: R 0x004",
    "firmware read sum",
)
