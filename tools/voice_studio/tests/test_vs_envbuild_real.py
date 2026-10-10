# SPDX-License-Identifier: GPL-3.0-or-later
"""Building an environment for real (plan task VS-1.9): a real Python environment is made, the real native build script runs, and the checks that
look inside it run for real. Only the network is a stand-in: "installing" writes the records a real install leaves, so what is checked afterwards,
including pip's own rules for markers and versions, is the real thing."""
import os
import shutil
import sys
from pathlib import Path

import pytest

from vs_env_helpers import Doors, make_archive, pinned_item
from voice_studio.core import envbuild as eb
from voice_studio.core import fetch
from voice_studio.core.consent import make_consent
from voice_studio.core.envspec import lock_digest, parse_environments, parse_lock
from voice_studio.core.paths import DataHome
from voice_studio.core.registry import Registry
from voice_studio.core.system import CommandResult, RealSystem

import json

H = "a" * 64
LOCK = ("thing==1.0.0 ; python_version >= \"3.8\" --hash=sha256:%s\n"
        "onlyold==1.0 ; python_version < \"3.0\" --hash=sha256:%s\n"
        "Plain_Name==2.5 --hash=sha256:%s\n" % (H, H, H)).encode()
BUILD_SH = (b"#!/bin/sh\n"
            b"test \"$(command -v python)\" = \"$VIRTUAL_ENV/bin/python\" || exit 7\n"          # the environment's own python must come first
            b"mkdir -p src && echo built > src/core.cpython-312.so\n")
FILES = {"build.sh": (BUILD_SH, 0o755), "src/fakedemo/__init__.py": (b"VALUE = 41\n", 0o644)}
SPEC = {"id": "demo", "why_key": "env.why.training", "python_min": [3, 10], "approx_size_bytes": 1000,
        "lock": {"filename": "demo.lock.txt", "sha256": lock_digest(LOCK)},
        "source": {"item_id": "demo-source", "install": True, "dist": "demo-dist", "native_build": "build.sh", "native_artifact": "src/core*.so"},
        "prelude": ["import os"], "patches": [],
        "probes": [{"id": "imports", "code": "import fakedemo; assert fakedemo.VALUE == 41", "needs_gpu": False},
                   {"id": "card", "code": "raise SystemExit(5)", "needs_gpu": True}]}


class InstallingDoors(Doors):
    """Fakes only the download: "installing" leaves what a real install leaves inside the real environment."""

    def _site_packages(self, python: str) -> Path:
        return next((Path(python).parents[1] / "lib").glob("python*/site-packages"))

    def _simulate(self, argv):
        argv = list(argv)
        self.pip_runs.append(tuple(argv))
        site = self._site_packages(argv[0])
        if "--require-hashes" in argv:
            pins, problems = parse_lock(Path(argv[argv.index("-r") + 1]).read_text())
            assert problems == []
            for pin in pins:
                version = {"thing": "1.0", "plain-name": "2.5"}.get(pin.name, pin.version)       # "1.0" is the same version as "1.0.0"
                if pin.marker and "< \"3.0\"" in pin.marker:
                    continue                                                                        # not for this Python: a real install skips it
                folder = site / ("%s-%s.dist-info" % (pin.name.replace("-", "_"), version))
                folder.mkdir(exist_ok=True)
                (folder / "METADATA").write_text("Metadata-Version: 2.1\nName: %s\nVersion: %s\n" % (pin.name, version))
            return CommandResult(0, "Successfully installed\n")
        source = Path(argv[argv.index("-e") + 1])
        (site / "__editable__.fakedemo.pth").write_text(str(source / "src") + "\n")
        folder = site / "demo_dist-0.0.dist-info"
        folder.mkdir(exist_ok=True)
        (folder / "METADATA").write_text("Metadata-Version: 2.1\nName: demo_dist\nVersion: 0.0\n")
        return CommandResult(0, "Successfully installed demo-dist\n")


def make_real(tmp_path):
    archive = make_archive(tmp_path / "demo.tar.gz", files=FILES)
    item = pinned_item(archive)
    spec = parse_environments(json.dumps({"schema": 1, "environments": [SPEC]}))[0]
    system = RealSystem()
    doors = InstallingDoors(system, archive)
    ctx = eb.Context(system=system, home=DataHome(str(tmp_path / "home")), registry=Registry((item,)), consent=make_consent([item], extra_ids=["pip:demo"]),
                     fetcher=doors.fetcher, networked=doors.networked, read_lock=lambda s: LOCK)
    return spec, ctx, doors


def installed_names(site: Path):
    return sorted(p.name for p in site.glob("*.dist-info"))


def test_a_whole_environment_is_built_for_real_checked_from_inside_and_found_ready_the_second_time(tmp_path):
    spec, ctx, doors = make_real(tmp_path)
    result = eb.build(spec, ctx)
    assert result.ok, (result.error, result.error and result.error.tail)
    assert list(result.did) == ["source_unpack", "venv", "pip_lock", "pip_source", "native_build", "wrapper"] and result.skipped == ("card",)
    paths = eb.EnvPaths(result.env_dir)
    assert os.access(paths.python, os.X_OK) and Path(paths.launcher).exists()
    site = doors._site_packages(paths.python)
    assert "onlyold-1.0.dist-info" not in installed_names(site), "the pin for another Python is not required"

    doors.pip_runs.clear()
    again = eb.build(spec, ctx)
    assert again.ok and again.did == () and len(again.kept) == 6 and doors.pip_runs == []
    assert eb.inspect(spec, ctx).state == "ready"


def test_the_real_environment_runs_the_launcher_and_the_modules_it_was_built_for(tmp_path):
    spec, ctx, doors = make_real(tmp_path)
    result = eb.build(spec, ctx)
    assert result.ok
    paths = eb.EnvPaths(result.env_dir)
    ran = RealSystem().run([paths.python, paths.launcher, "platform"], timeout=60, cwd=paths.env_dir)
    assert ran is not None and ran.returncode == 0 and ran.stdout.strip()
    inside = RealSystem().run([paths.python, "-c", "import fakedemo, sys; print(fakedemo.VALUE, sys.prefix != sys.base_prefix)"], timeout=60)
    assert inside.stdout.split() == ["41", "True"]


def test_a_package_removed_from_the_real_environment_is_found_and_put_back_alone(tmp_path):
    spec, ctx, doors = make_real(tmp_path)
    result = eb.build(spec, ctx)
    paths = eb.EnvPaths(result.env_dir)
    site = doors._site_packages(paths.python)
    shutil.rmtree(site / "plain_name-2.5.dist-info")
    assert eb.inspect(spec, ctx).stale == ("pip_lock",)
    again = eb.build(spec, ctx)
    assert again.ok and list(again.did) == ["pip_lock"] and "plain_name-2.5.dist-info" in installed_names(site)


def test_a_package_at_a_different_version_is_found_by_the_real_check(tmp_path):
    spec, ctx, doors = make_real(tmp_path)
    result = eb.build(spec, ctx)
    site = doors._site_packages(eb.EnvPaths(result.env_dir).python)
    meta = site / "plain_name-2.5.dist-info" / "METADATA"
    meta.write_text(meta.read_text().replace("2.5", "2.6"))
    assert eb.inspect(spec, ctx).stale == ("pip_lock",)


def test_a_removed_real_environment_is_rebuilt_and_the_source_and_native_part_are_kept(tmp_path):
    spec, ctx, doors = make_real(tmp_path)
    result = eb.build(spec, ctx)
    shutil.rmtree(eb.EnvPaths(result.env_dir).venv)
    doors.fetches.clear()
    again = eb.build(spec, ctx)
    assert again.ok and list(again.did) == ["venv", "pip_lock", "pip_source"] and list(again.kept) == ["source_unpack", "native_build", "wrapper"]
    assert doors.fetches == []


def test_a_native_build_that_cannot_find_the_environments_python_first_fails_for_real(tmp_path):
    spec, ctx, doors = make_real(tmp_path)

    class WrongPath(RealSystem):
        def run(self, argv, timeout=15.0, cwd=None, env=None):
            if argv[0] == "bash":
                env = dict(env or {}, PATH="/usr/bin:/bin")             # as if the environment's own tools were not first
            return super().run(argv, timeout, cwd, env)

    ctx.system = WrongPath()
    result = eb.build(spec, ctx)
    assert not result.ok and result.error.code == "native_failed" and result.error.detail == "exit 7"


def test_a_real_probe_that_fails_stops_the_build_with_its_name(tmp_path):
    spec, ctx, doors = make_real(tmp_path)
    ctx.gpu_ok = True
    result = eb.build(spec, ctx)
    assert not result.ok and result.error.code == "self_test_failed" and result.error.detail == "card"
