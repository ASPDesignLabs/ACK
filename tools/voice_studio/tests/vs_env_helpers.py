# SPDX-License-Identifier: GPL-3.0-or-later
"""Stand-ins for building an environment: a small source archive, a computer that answers the commands the builder runs, and fake doors to the
network that obey the same agreement check as the real ones (they call core/fetch.run_networked with a runner of their own)."""
import copy
import hashlib
import io
import json
import os
import shutil
import tarfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

from vs_fakes import FakeSystem
from voice_studio.core import envbuild as eb
from voice_studio.core import fetch
from voice_studio.core.consent import make_consent
from voice_studio.core.envspec import lock_digest, parse_environments, parse_lock
from voice_studio.core.paths import DataHome
from voice_studio.core.registry import Item, Registry
from voice_studio.core.system import CommandResult

GIB = 2**30
H1, H2 = "a" * 64, "b" * 64
LOCK = ("# a lock\nnumpy==1.26.4 \\\n    --hash=sha256:%s\nquart==0.20.0 --hash=sha256:%s\n" % (H1, H2)).encode()
TOP = "demo-abc123"
GOOD_FILES = {"build.sh": (b"#!/bin/sh\necho building\n", 0o755), "README": (b"hello\n", 0o644), "src/demo/__init__.py": (b"VALUE = 1\n", 0o644),
              "src/demo/train.py": (b"def main():\n    return 'old'\n", 0o644)}


def make_archive(path: Path, files=None, top: str = TOP, extra=(), skip_top_entry: bool = False) -> Path:
    """A .tar.gz shaped like GitHub's: one top folder, then everything inside it. `extra` are ready-made TarInfo (and optional bytes) added as they are."""
    files = GOOD_FILES if files is None else files
    path = Path(path)
    with tarfile.open(str(path), "w:gz") as tar:
        if not skip_top_entry and top:
            info = tarfile.TarInfo(top)
            info.type, info.mode = tarfile.DIRTYPE, 0o755
            tar.addfile(info)
        for name, (data, mode) in files.items():
            info = tarfile.TarInfo("%s/%s" % (top, name) if top else name)
            info.size, info.mode = len(data), mode
            tar.addfile(info, io.BytesIO(data))
        for info, data in extra:
            tar.addfile(info, io.BytesIO(data) if data is not None else None)
    return path


def link(name: str, target: str, hard: bool = False) -> tarfile.TarInfo:
    info = tarfile.TarInfo(name)
    info.type = tarfile.LNKTYPE if hard else tarfile.SYMTYPE
    info.linkname = target
    return info


def special(name: str, kind) -> tarfile.TarInfo:
    info = tarfile.TarInfo(name)
    info.type = kind
    return info


def sha_of(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def pinned_item(archive: Path) -> Item:
    return Item("demo-source", "source", "fetch.why.x", "demo-license", approx_size_bytes=10, url="https://github.com/o/r/archive/abc123.tar.gz",
                filename="r-abc123.tar.gz", revision="abc123", size_bytes=archive.stat().st_size, sha256=sha_of(archive))


BASE_SPEC = {
    "id": "demo", "why_key": "env.why.training", "python_min": [3, 10], "approx_size_bytes": 1000,
    "lock": {"filename": "demo.lock.txt", "sha256": None},
    "source": {"item_id": "demo-source", "install": True, "dist": "demo-dist", "native_build": "build.sh", "native_artifact": "src/core*.so"},
    "prelude": ["import os"], "patches": [],
    "probes": [{"id": "imports", "code": "import os", "needs_gpu": False}, {"id": "card", "code": "import sys", "needs_gpu": True}],
}
PATCH = {"id": "fix-it", "file": "src/demo/train.py", "old": "return 'old'", "new": "return 'new'"}


def make_spec(lock: bytes = LOCK, **over):
    raw = copy.deepcopy(BASE_SPEC)
    raw["lock"]["sha256"] = lock_digest(lock)
    raw.update(over)
    return parse_environments(json.dumps({"schema": 1, "environments": [raw]}))[0]


class BuildSystem(FakeSystem):
    """A computer whose Python environment is simulated: it answers the builder's own commands and keeps a list of what was asked."""

    def __init__(self, python=(3, 12, 3), free=500 * GIB, **kw):
        super().__init__(python=python, **kw)
        self.free = free
        self._dists = {}                # what is "installed" inside each simulated environment: venv folder -> {normalised name: version}
        self.commands: List[tuple] = []
        self.venv_minor = "%d.%d" % python[:2]
        self.fail_venv = None           # a CommandResult, or "none" for "could not run at all"
        self.fail_native = None
        self.native_makes = True
        self.native_makes_then_fails = False
        self.venv_flag = "1"                # what the check inside the environment reports for "this is a virtual environment"
        self.bad_probe_codes = set()
        self.fail_launcher = False
        self.probe_runs = []
        self.launcher_runs = []
        self.native_runs = []

    def exists(self, path):
        return os.path.exists(path)

    def dists(self, venv_dir):
        return self._dists.setdefault(str(venv_dir), {})

    @property
    def venv_dists(self):
        """For a test with one environment: what is installed in it."""
        assert len(self._dists) == 1, "this test has more than one environment: use dists(venv folder)"
        return next(iter(self._dists.values()))

    @venv_dists.setter
    def venv_dists(self, value):
        self._dists = {key: dict(value) for key in self._dists}

    def disk_free(self, path):
        return (self.free * 2, self.free)

    def run(self, argv, timeout=15.0, cwd=None, env=None):
        self.commands.append((tuple(argv), cwd, dict(env or {})))
        argv = list(argv)
        if len(argv) == 4 and argv[1:3] == ["-m", "venv"]:
            if self.fail_venv == "none":
                return None
            if self.fail_venv is not None:
                return self.fail_venv
            target = Path(argv[3])
            (target / "bin").mkdir(parents=True, exist_ok=True)
            (target / "bin" / "python").write_text("#!/bin/sh\n")
            (target / "pyvenv.cfg").write_text("home = /usr/bin\n")
            self._dists[str(target)] = {}
            return CommandResult(0, "created\n")
        if argv[0].endswith("/venv/bin/python"):
            if len(argv) >= 3 and argv[1] == "-c":
                code = argv[2]
                if code == eb._MINOR_CODE:
                    return CommandResult(0, "%s\n%s\n" % (self.venv_minor, self.venv_flag))
                if code == eb._VERIFY_CODE:
                    want = json.loads(argv[3])
                    have = self._dists.get(argv[0][: -len("/bin/python")], {})
                    bad = []
                    for name, version, marker in want["pins"]:
                        if marker:
                            continue
                        if name not in have:
                            bad.append("missing " + name)
                        elif have[name] != version:
                            bad.append("version %s %s" % (name, have[name]))
                    bad += ["missing " + d for d in want["dists"] if d not in have]
                    return CommandResult(0, json.dumps(bad) + "\n")
                self.probe_runs.append((code, dict(env or {}), cwd))
                if code in self.bad_probe_codes:
                    return CommandResult(1, "", "Traceback\nImportError: nothing called that\n")
                return CommandResult(0, "ok\n")
            if len(argv) >= 2 and argv[1].endswith("ack_run.py"):
                self.launcher_runs.append((argv, dict(env or {})))
                return CommandResult(1, "", "boom\n") if self.fail_launcher else CommandResult(0, "Linux\n")
        if argv[0] == "bash":
            self.native_runs.append((argv, cwd, dict(env or {})))
            if self.native_makes_then_fails:
                target = Path(cwd) / "src"
                target.mkdir(parents=True, exist_ok=True)
                (target / "core.cpython-312.so").write_bytes(b"\x7fELF")
                return CommandResult(2, "", "make: *** [all] Error 2\n")
            if self.fail_native is not None:
                return self.fail_native
            if self.native_makes:
                target = Path(cwd) / "src"
                target.mkdir(parents=True, exist_ok=True)
                (target / "core.cpython-312.so").write_bytes(b"\x7fELF")
            return CommandResult(0, "built\n")
        return super().run(argv, timeout)


class Doors:
    """The two ways out to the network, as stand-ins: they keep the real agreement check by running the real run_networked with a runner of their own."""

    def __init__(self, system: BuildSystem, archive: Path):
        self.system, self.archive = system, archive
        self.fetches, self.pip_runs = [], []
        self.files = {}                 # item id -> the file served for it (the archive by default)
        self.fetch_error: Optional[str] = None
        self.pip_fail = {}              # "lock" / "source" -> exit status
        self.pip_lines = ["Collecting x", "Installing collected packages: x"]

    def fetcher(self, item, dest_dir, consent, progress=None, cancelled=None, **kwargs):
        self.fetches.append(item.id)
        if self.fetch_error:
            raise fetch.FetchError(self.fetch_error)
        if consent is None or not consent.covers(item):
            raise fetch.FetchError("consent", item.id)
        dest = Path(dest_dir)
        dest.mkdir(parents=True, exist_ok=True)
        target = dest / item.filename
        shutil.copyfile(str(self.files.get(item.id, self.archive)), str(target))
        if progress:
            progress(item.size_bytes, item.size_bytes)
        return target

    def networked(self, consent, argv, ids, cwd=None, on_line=None, runner=None, inherit_stdio=False):
        return fetch.run_networked(consent, argv, ids, cwd=cwd, on_line=on_line, runner=self._simulate)

    def _simulate(self, argv):
        argv = list(argv)
        self.pip_runs.append(tuple(argv))
        if "--require-hashes" in argv:
            if self.pip_fail.get("lock"):
                return CommandResult(self.pip_fail["lock"], "\n".join(self.pip_lines) + "\nERROR: No matching distribution\n")
            pins, problems = parse_lock(Path(argv[argv.index("-r") + 1]).read_text())
            assert problems == []
            for pin in pins:
                self.system.dists(argv[0][: -len("/bin/python")])[pin.name] = pin.version
            return CommandResult(0, "\n".join(self.pip_lines) + "\nSuccessfully installed\n")
        if "-e" in argv:
            if self.pip_fail.get("source"):
                return CommandResult(self.pip_fail["source"], "ERROR: build failed\n")
            self.system.dists(argv[0][: -len("/bin/python")])["demo-dist"] = "0.0"
            return CommandResult(0, "Successfully installed demo-dist\n")
        raise AssertionError("an unexpected network command: %r" % (argv,))


@dataclass
class Rig:
    root: Path
    system: BuildSystem
    doors: Doors
    spec: object
    item: Item
    registry: Registry
    consent: object
    ctx: eb.Context
    events: List[eb.Event] = field(default_factory=list)
    lock: bytes = LOCK

    @property
    def environments(self) -> Path:
        return Path(self.ctx.home.environments)

    @property
    def env_dir(self) -> str:
        return eb.environment_dir(self.spec, self.ctx)

    @property
    def paths(self) -> eb.EnvPaths:
        return eb.EnvPaths(self.env_dir)

    def build(self):
        return eb.build(self.spec, self.ctx)

    def record(self) -> dict:
        return json.loads(Path(self.paths.record).read_text())

    def step_ids(self, kind: str) -> List[str]:
        return [e.step for e in self.events if e.kind == kind]


def make_rig(tmp_path: Path, *, spec_over=None, archive_files=None, archive_extra=(), lock: bytes = LOCK, system_kw=None, consent_pip=True, confirm=None,
             gpu_ok=False) -> Rig:
    root = Path(tmp_path)
    root.mkdir(parents=True, exist_ok=True)
    archive = make_archive(root / "demo.tar.gz", files=archive_files, extra=archive_extra)
    item = pinned_item(archive)
    spec = make_spec(lock, **(spec_over or {}))
    system = BuildSystem(**(system_kw or {}))
    doors = Doors(system, archive)
    registry = Registry((item,))
    consent = make_consent([item], extra_ids=(["pip:demo"] if consent_pip else []))
    events: List[eb.Event] = []
    home = DataHome(str(root / "home"))
    ctx = eb.Context(system=system, home=home, registry=registry, consent=consent, gpu_ok=gpu_ok, confirm_patch=confirm or (lambda p: False),
                     on_event=events.append, fetcher=doors.fetcher, networked=doors.networked, read_lock=lambda s: lock)
    return Rig(root, system, doors, spec, item, registry, consent, ctx, events, lock)
