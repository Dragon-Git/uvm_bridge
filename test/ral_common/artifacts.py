"""Content-hashed, concurrency-safe peakrdl / firmware artefact cache.

The commands below are the single source of truth that used to live in the
three deleted Makefiles. Outputs are generated into a private temporary
directory, verified, then published with ``os.replace`` under an exclusive
``flock``. A manifest keyed by sha256(inputs + commands + tool versions) makes
repeated pytest runs free and immune to mtime changes from clone/CI restore.
A missing tool is an explicit :class:`~base_test.sim_runner.SimError`, never a
silent fallback to stale files.
"""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import os
import shutil
import subprocess
import sys
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from collections.abc import Iterator, Sequence

# sim_runner.py is a plain module in test/base_test (no package __init__), so
# put that directory on sys.path before importing its SimError. All RAL error
# paths then raise the same type the driver already knows how to classify.
_BASE_TEST_DIR = Path(__file__).resolve().parents[1] / "base_test"
if str(_BASE_TEST_DIR) not in sys.path:
    sys.path.insert(0, str(_BASE_TEST_DIR))
from sim_runner import SimError  # noqa: E402  (path prepared immediately above)

from .spec import ArtifactSpec


@dataclass(frozen=True)
class ArtifactPaths:
    """Final locations of the generated artefacts a suite may consume."""

    gen_py: Path | None = None
    rtl_pkg: Path | None = None
    rtl_sv: Path | None = None
    header: Path | None = None
    firmware: Path | None = None


@dataclass(frozen=True)
class _Job:
    """One independently cached generator invocation."""

    name: str
    target_dir: Path
    commands: tuple[Sequence[str], ...]
    outputs: tuple[tuple[str, Path], ...]
    inputs: tuple[Path, ...]
    tools: tuple[str, ...]


_MANIFEST_NAME = ".artifact-manifest.json"


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(65536), b""):
            digest.update(block)
    return digest.hexdigest()


def _run(cmd: Sequence[str], cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            [str(part) for part in cmd],
            cwd=str(cwd) if cwd else None,
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError as exc:
        raise SimError(f"command not found: {cmd[0]} ({exc})") from exc


def _version_text(jobs: Sequence[_Job]) -> str:
    """Collect tool versions that participate in the cache key.

    Only ``peakrdl`` and ``clang`` are executables. A peakrdl plugin has no
    ``--version`` subcommand of its own; its distribution metadata is the
    version that actually changes generated output, so ask importlib instead
    of trying to execute it.
    """
    tools = sorted({tool for job in jobs for tool in job.tools})
    parts: list[str] = []
    for tool in tools:
        if tool not in ("peakrdl", "clang"):
            continue
        proc = _run([tool, "--version"])
        if proc.returncode != 0:
            raise SimError(f"{tool} --version failed: {proc.stdout}{proc.stderr}")
        parts.append(f"{tool}: {proc.stdout.strip() or proc.stderr.strip()}")

    # Plugins are imported by CLI entry point but their distribution versions
    # are what changes generated output; include them when installed.
    for dist in ("peakrdl-pyral", "peakrdl-regblock", "peakrdl-cheader"):
        if not any(dist == tool for tool in tools):
            continue
        try:
            parts.append(f"{dist}: {importlib.metadata.version(dist)}")
        except importlib.metadata.PackageNotFoundError as exc:
            raise SimError(f"peakrdl plugin {dist} is not installed") from exc
    return "\n".join(parts)


def _content_key(spec: ArtifactSpec, jobs: Sequence[_Job]) -> str:
    digest = hashlib.sha256()
    for job in jobs:
        digest.update(job.name.encode("utf-8"))
        for command in job.commands:
            digest.update("\0".join(str(part) for part in command).encode("utf-8"))
            digest.update(b"\n")
        for path in job.inputs:
            resolved = path.resolve()
            if not resolved.is_file():
                raise SimError(f"{job.name}: input {resolved} does not exist")
            # Name + bytes only: the key must stay stable across clone paths
            # and CI workspaces, so no absolute path goes into the hash.
            digest.update(resolved.name.encode("utf-8"))
            digest.update(_sha256_file(resolved).encode("utf-8"))
    digest.update(_version_text(jobs).encode("utf-8"))
    return digest.hexdigest()


def _jobs(spec: ArtifactSpec) -> tuple[_Job, ...]:
    rdl = spec.rdl.resolve()
    if not rdl.is_file():
        raise SimError(f"RDL source {rdl} does not exist")

    module = spec.rdl_module
    jobs: list[_Job] = []

    if spec.need_pyral:
        gen_dir = spec.gen_dir
        assert gen_dir is not None
        jobs.append(
            _Job(
                name="pyral",
                target_dir=gen_dir,
                commands=(("peakrdl", "pyral", rdl, "--rename", module, "-o", "."),),
                outputs=(
                    (f"{module}.py", gen_dir / f"{module}.py"),
                    (f"{module}_stubs.pyi", gen_dir / f"{module}_stubs.pyi"),
                    (f"{module}.db", gen_dir / f"{module}.db"),
                ),
                inputs=(rdl,),
                tools=("peakrdl", "peakrdl-pyral"),
            )
        )

    if spec.need_regblock:
        rtl_dir = spec.rtl_dir
        assert rtl_dir is not None
        jobs.append(
            _Job(
                name="regblock",
                target_dir=rtl_dir,
                commands=(("peakrdl", "regblock", rdl, "-o", module, "--cpuif", "apb3"),),
                outputs=(
                    (f"{module}/demo_regs_pkg.sv", rtl_dir / module / "demo_regs_pkg.sv"),
                    (f"{module}/demo_regs.sv", rtl_dir / module / "demo_regs.sv"),
                ),
                inputs=(rdl,),
                tools=("peakrdl", "peakrdl-regblock"),
            )
        )

    if spec.need_cheader:
        header_dir = spec.header_dir
        assert header_dir is not None
        jobs.append(
            _Job(
                name="c_header",
                target_dir=header_dir,
                # Generators run inside their target directory; c-header
                # receives the plain filename rather than the old Makefile's
                # repo-relative "c_header/demo_regs.h".
                commands=(("peakrdl", "c-header", rdl, "-o", "demo_regs.h"),),
                outputs=(("demo_regs.h", header_dir / "demo_regs.h"),),
                inputs=(rdl,),
                tools=("peakrdl", "peakrdl-cheader"),
            )
        )

    if spec.need_firmware:
        build_dir = spec.build_dir
        header_dir = spec.header_dir
        assert build_dir is not None and header_dir is not None
        repo_root = Path(__file__).resolve().parents[2]
        fw_dir = repo_root / "test" / "fw"
        header = header_dir / "demo_regs.h"
        # Every file that can change fw.bin must participate in the key:
        # main.c/register_access.py are compiled or imported, layout.py holds
        # the expected trace, elf2bin.py defines the image extraction, and the
        # compat headers are #included by the generated C header. Without the
        # last two, editing them left a stale fw.bin behind a manifest hit.
        compat_dir = fw_dir / "compat"
        if not compat_dir.is_dir():
            raise SimError(f"firmware compat header directory does not exist: {compat_dir}")
        compat_headers = tuple(sorted(compat_dir.glob("*.h")))
        if not compat_headers:
            raise SimError(f"no firmware compat headers found under {compat_dir}")
        jobs.append(
            _Job(
                name="firmware",
                target_dir=build_dir,
                commands=(
                    (
                        "clang",
                        "--target=aarch64-none-elf",
                        "-march=armv8-a",
                        "-mgeneral-regs-only",
                        "-std=gnu11",
                        "-nostdlib",
                        "-ffreestanding",
                        "-fno-builtin",
                        "-I", header_dir,
                        "-I", fw_dir / "compat",
                        "-c", fw_dir / "main.c",
                        "-o", "fw.o",
                    ),
                    (sys.executable, fw_dir / "elf2bin.py", "fw.o", "fw.bin"),
                ),
                outputs=(("fw.bin", build_dir / "fw.bin"), ("fw.o", build_dir / "fw.o")),
                inputs=(
                    fw_dir / "main.c",
                    fw_dir / "layout.py",
                    fw_dir / "register_access.py",
                    fw_dir / "elf2bin.py",
                    *compat_headers,
                    header,
                ),
                tools=("clang",),
            )
        )

    if not jobs:
        raise SimError(f"ArtifactSpec for {spec.root} requests no artefacts")
    return tuple(jobs)


def _manifest_path(job: _Job) -> Path:
    return job.target_dir / _MANIFEST_NAME


def _manifest_hit(job: _Job, key: str) -> bool:
    manifest = _manifest_path(job)
    if not manifest.is_file():
        return False
    try:
        data = json.loads(manifest.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return False
    if data.get("key") != key:
        return False
    recorded = {str(entry.get("path")): str(entry.get("sha256")) for entry in data.get("outputs", [])}
    for relative, destination in job.outputs:
        if not destination.is_file():
            return False
        if recorded.get(relative) != _sha256_file(destination):
            return False
    return True


def _write_manifest(job: _Job, key: str, backend: str) -> None:
    outputs = [
        {"path": relative, "sha256": _sha256_file(destination)}
        for relative, destination in job.outputs
    ]
    payload = {"key": key, "backend": backend, "outputs": outputs}
    manifest = _manifest_path(job)
    tmp = manifest.with_name(f"{manifest.name}.tmp-{os.getpid()}-{uuid.uuid4().hex}")
    with open(tmp, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)
    os.replace(tmp, manifest)


def _generate(job: _Job, key: str, backend: str) -> None:
    job.target_dir.mkdir(parents=True, exist_ok=True)
    tmpdir = job.target_dir / f".tmp-{os.getpid()}-{uuid.uuid4().hex}"
    tmpdir.mkdir(parents=True, exist_ok=True)
    try:
        for command in job.commands:
            proc = _run(command, cwd=tmpdir)
            if proc.returncode != 0:
                raise SimError(
                    f"{job.name}: generator failed ({' '.join(str(p) for p in command)}):\n"
                    f"{_output(proc)}"
                )
        for relative, destination in job.outputs:
            source = tmpdir / relative
            if not source.is_file():
                raise SimError(
                    f"{job.name}: generator did not produce {relative}; "
                    f"files were {[str(p.relative_to(tmpdir)) for p in tmpdir.rglob('*') if p.is_file()]}"
                )
            destination.parent.mkdir(parents=True, exist_ok=True)
            os.replace(source, destination)
        _write_manifest(job, key, backend)
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def _output(proc: subprocess.CompletedProcess[str]) -> str:
    return proc.stdout + proc.stderr


@contextmanager
def _locked(lock_path: Path) -> Iterator[None]:
    """Serialize the check/generate/publish sequence across pytest workers."""
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with open(lock_path, "a+", encoding="utf-8") as handle:
        import fcntl

        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def _paths(spec: ArtifactSpec) -> ArtifactPaths:
    return ArtifactPaths(
        gen_py=spec.gen_dir / f"{spec.rdl_module}.py" if spec.need_pyral else None,
        rtl_pkg=spec.rtl_dir / spec.rdl_module / "demo_regs_pkg.sv" if spec.need_regblock else None,
        rtl_sv=spec.rtl_dir / spec.rdl_module / "demo_regs.sv" if spec.need_regblock else None,
        header=spec.header_dir / "demo_regs.h" if spec.need_cheader else None,
        firmware=spec.build_dir / "fw.bin" if spec.need_firmware else None,
    )


class ArtifactCache:
    """Public façade for the cached generators."""

    @staticmethod
    def ensure(spec: ArtifactSpec, backend: str = "verilator") -> ArtifactPaths:
        """Return generated artefact paths, regenerating only on a key miss.

        The generated files themselves are backend-independent; ``backend`` is
        recorded in the manifest for diagnostics but is deliberately absent
        from the cache key so the two legs share one set of outputs.

        Args:
            spec: What to generate and where to publish it.
            backend: Simulator leg requesting the artefacts.

        Returns:
            Paths of the published artefacts.

        Raises:
            SimError: On a missing tool, missing input, or failed generator.
        """
        jobs = _jobs(spec)
        # Jobs are ordered by dependency: c_header publishes demo_regs.h,
        # which is an *input* of the firmware job. Keys therefore have to be
        # computed one job at a time after the earlier jobs have published,
        # otherwise a cold run rejects firmware for a header that does not
        # exist yet. The lock covers the whole check/generate sequence.
        lock = spec.root / ".artifact-gen.lock"
        with _locked(lock):
            for job in jobs:
                key = _content_key(spec, (job,))
                if _manifest_hit(job, key):
                    continue
                _generate(job, key, backend)
        return _paths(spec)
