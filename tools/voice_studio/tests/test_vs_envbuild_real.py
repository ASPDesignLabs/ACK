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
        "Plain_Name==2.5 --hash=sha256:%s\n"
        "zope.interface==6.0 --hash=sha256:%s\n" % (H, H, H, H)).encode()
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
                shown = {"plain-name": "Plain_Name", "zope-interface": "zope.interface"}.get(pin.name, pin.name)   # as the package spells itself
                folder = site / ("%s-%s.dist-info" % (shown, version))
                folder.mkdir(exist_ok=True)
                (folder / "METADATA").write_text("Metadata-Version: 2.1\nName: %s\nVersion: %s\n" % (shown, version))
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
    shutil.rmtree(site / "Plain_Name-2.5.dist-info")
    assert eb.inspect(spec, ctx).stale == ("pip_lock",)
    again = eb.build(spec, ctx)
    assert again.ok and list(again.did) == ["pip_lock"] and "Plain_Name-2.5.dist-info" in installed_names(site)


def test_a_package_whose_pin_has_a_marker_for_this_python_is_required_and_found_missing(tmp_path):
    spec, ctx, doors = make_real(tmp_path)
    result = eb.build(spec, ctx)
    site = doors._site_packages(eb.EnvPaths(result.env_dir).python)
    shutil.rmtree(site / "thing-1.0.dist-info")
    assert eb.inspect(spec, ctx).stale == ("pip_lock",)
    assert list(eb.build(spec, ctx).did) == ["pip_lock"]


def test_a_package_with_a_dot_in_its_name_is_found_missing_by_the_real_check(tmp_path):
    spec, ctx, doors = make_real(tmp_path)
    result = eb.build(spec, ctx)
    site = doors._site_packages(eb.EnvPaths(result.env_dir).python)
    assert "zope.interface-6.0.dist-info" in installed_names(site)
    shutil.rmtree(site / "zope.interface-6.0.dist-info")
    assert eb.inspect(spec, ctx).stale == ("pip_lock",)


def test_the_trainers_own_package_missing_means_only_its_install_runs_again(tmp_path):
    spec, ctx, doors = make_real(tmp_path)
    result = eb.build(spec, ctx)
    site = doors._site_packages(eb.EnvPaths(result.env_dir).python)
    shutil.rmtree(site / "demo_dist-0.0.dist-info")
    assert eb.inspect(spec, ctx).stale == ("pip_source",)
    assert list(eb.build(spec, ctx).did) == ["pip_source"]


def test_a_package_at_a_different_version_is_found_by_the_real_check(tmp_path):
    spec, ctx, doors = make_real(tmp_path)
    result = eb.build(spec, ctx)
    site = doors._site_packages(eb.EnvPaths(result.env_dir).python)
    meta = site / "Plain_Name-2.5.dist-info" / "METADATA"
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


# ---------------------------------------------------------------- the environment's own Python (found on a real Ubuntu 22.04)

import subprocess

MINOR = tuple(sys.version_info[:2])


def chain_to_another_environment(paths, outer: Path):
    """Make `paths`' interpreter links the way Python 3.10 makes them when another environment is active: pointing at that environment's Python.
    On 3.10 Python itself does this (so the test uses it, as it happened on the developer's computer: the links and `home` in pyvenv.cfg together); 3.11 and
    later no longer chain, so there the same layout is written by hand."""
    subprocess.run([RealSystem().python_executable(), "-m", "venv", "--without-pip", str(outer)], check=True, capture_output=True, timeout=120)      # from the real Python: made from a venv's, it would be chained itself on 3.10
    for name in ("python", "python3", "python%d.%d" % MINOR):
        os.unlink(paths.venv + "/bin/" + name)
    if sys.version_info < (3, 11):
        subprocess.run([str(outer / "bin" / "python"), "-m", "venv", "--without-pip", paths.venv], check=True, capture_output=True, timeout=120)
        assert eb.broken_interpreter_links(paths.venv, MINOR) == ["python", "python3", "python%d.%d" % MINOR], "this Python chained it by itself"
        return
    os.symlink(str(outer / "bin" / "python3"), paths.venv + "/bin/python3")
    os.symlink("python3", paths.venv + "/bin/python")
    os.symlink("python3", paths.venv + "/bin/python%d.%d" % MINOR)
    cfg = Path(paths.venv + "/pyvenv.cfg")
    cfg.write_text(cfg.read_text().replace("home = ", "home = %s\n#was " % (outer / "bin"), 1))


def test_an_environment_built_here_is_not_linked_to_any_other_virtual_environment_even_when_built_from_inside_one(tmp_path):
    spec, ctx, doors = make_real(tmp_path)
    result = eb.build(spec, ctx)
    paths = eb.EnvPaths(result.env_dir)
    assert result.ok and eb.broken_interpreter_links(paths.venv, MINOR) == []
    ends = [os.path.realpath(paths.venv + "/bin/" + n) for n in ("python", "python3")]
    assert all(not os.path.isfile(os.path.join(os.path.dirname(os.path.dirname(e)), "pyvenv.cfg")) for e in ends), ends


def test_a_healthy_environments_links_are_never_rewritten(tmp_path):
    spec, ctx, doors = make_real(tmp_path)
    paths = eb.EnvPaths(eb.build(spec, ctx).env_dir)
    names = ("python", "python3", "python%d.%d" % MINOR)
    before = {n: (os.readlink(paths.venv + "/bin/" + n), os.lstat(paths.venv + "/bin/" + n).st_ino) for n in names}
    cfg = os.stat(paths.venv + "/pyvenv.cfg").st_mtime_ns
    again = eb.build(spec, ctx)
    assert again.ok and again.did == ()
    assert before == {n: (os.readlink(paths.venv + "/bin/" + n), os.lstat(paths.venv + "/bin/" + n).st_ino) for n in names} and os.stat(paths.venv + "/pyvenv.cfg").st_mtime_ns == cfg


def test_an_environment_chained_to_another_one_is_found_not_done_and_repaired_in_place_and_survives_that_one_being_deleted(tmp_path):
    spec, ctx, doors = make_real(tmp_path)
    paths = eb.EnvPaths(eb.build(spec, ctx).env_dir)
    site = doors._site_packages(paths.python)
    before = installed_names(site)
    outer = tmp_path / "outer"
    chain_to_another_environment(paths, outer)
    assert eb.broken_interpreter_links(paths.venv, MINOR) == ["python", "python3", "python%d.%d" % MINOR]
    looked = eb.inspect(spec, ctx)
    assert looked.state == "needs_work" and looked.stale == ("venv",), "it still runs, so only the link step is out of date"

    doors.pip_runs.clear()
    fixed = eb.build(spec, ctx)
    assert fixed.ok and list(fixed.did) == ["venv"] and doors.pip_runs == [], "nothing is downloaded or installed again"
    assert eb.broken_interpreter_links(paths.venv, MINOR) == [] and installed_names(site) == before
    assert "replaced the links python, python3, python%d.%d" % MINOR in Path(paths.log).read_text()
    shutil.rmtree(outer)                                                  # the day the other environment goes away
    ran = RealSystem().run([paths.python, "-c", "import fakedemo; print(fakedemo.VALUE)"], timeout=60)
    assert ran is not None and ran.stdout.split() == ["41"] and eb.inspect(spec, ctx).state == "ready"


def test_an_environment_whose_links_point_at_nothing_is_repaired_in_place_with_its_packages_kept(tmp_path):
    """The real failure: the environment it was linked to was deleted, so the environment's own python was gone, with every package still beside it."""
    spec, ctx, doors = make_real(tmp_path)
    paths = eb.EnvPaths(eb.build(spec, ctx).env_dir)
    site = doors._site_packages(paths.python)
    before = installed_names(site)
    outer = tmp_path / "outer"
    chain_to_another_environment(paths, outer)
    shutil.rmtree(outer)
    assert not os.path.exists(paths.python) and RealSystem().run([paths.python, "-c", "print(1)"], timeout=60) is None
    looked = eb.inspect(spec, ctx)
    assert looked.state == "needs_work" and "venv" in looked.stale

    doors.pip_runs.clear()
    fixed = eb.build(spec, ctx)
    assert fixed.ok, (fixed.error, fixed.error and fixed.error.tail)
    assert list(fixed.did) == ["venv"] and doors.pip_runs == [] and installed_names(site) == before
    ran = RealSystem().run([paths.python, "-c", "import fakedemo; print(fakedemo.VALUE)"], timeout=60)
    assert ran is not None and ran.stdout.split() == ["41"] and eb.inspect(spec, ctx).state == "ready"


def test_an_environment_whose_earlier_repair_failed_is_repaired_by_the_next_try(tmp_path):
    """The state the developer's computer was in: links gone bad, and a recorded failed attempt."""
    spec, ctx, doors = make_real(tmp_path)
    paths = eb.EnvPaths(eb.build(spec, ctx).env_dir)
    outer = tmp_path / "outer"
    chain_to_another_environment(paths, outer)
    shutil.rmtree(outer)
    record, _ = eb.read_record(paths.env_dir)
    record["state"] = "failed"
    record["failed"] = {"code": "venv_failed", "detail": "exit 1"}
    eb._save_record(paths.env_dir, record, "2026-10-11T17:19:00Z")
    assert eb.inspect(spec, ctx).state == "failed"
    assert eb.build(spec, ctx).ok and eb.inspect(spec, ctx).state == "ready"
    assert "failed" not in eb.read_record(paths.env_dir)[0]


def test_only_the_broken_links_are_removed_and_a_real_file_in_their_place_is_never_touched(tmp_path):
    spec, ctx, doors = make_real(tmp_path)
    paths = eb.EnvPaths(eb.build(spec, ctx).env_dir)
    outer = tmp_path / "outer"
    chain_to_another_environment(paths, outer)
    versioned = paths.venv + "/bin/python%d.%d" % MINOR
    os.unlink(versioned)
    Path(versioned).write_text("#!/bin/sh\nexec true\n")                                # a file, not a link: the tool never deletes one
    assert eb.broken_interpreter_links(paths.venv, MINOR) == ["python", "python3"]
    removed = []
    real_unlink = os.unlink
    os.unlink = lambda p, *a, **k: (removed.append(os.path.basename(str(p))), real_unlink(p, *a, **k))[1]
    try:
        assert eb.build(spec, ctx).ok
    finally:
        os.unlink = real_unlink
    assert [n for n in removed if n.startswith("python")] == ["python", "python3"], "the tool removed the two broken links and nothing else"
    assert os.access(versioned, os.X_OK) and eb.broken_interpreter_links(paths.venv, MINOR) == []


def test_a_link_that_cannot_be_removed_stops_the_repair_in_words_and_changes_nothing_else(tmp_path, monkeypatch):
    spec, ctx, doors = make_real(tmp_path)
    paths = eb.EnvPaths(eb.build(spec, ctx).env_dir)
    outer = tmp_path / "outer"
    chain_to_another_environment(paths, outer)
    site = doors._site_packages(paths.python)
    before = installed_names(site)

    real_unlink = os.unlink

    def refuse(path, *args, **kwargs):
        if "/venv/bin/python" in str(path):
            raise PermissionError(13, "Permission denied")
        return real_unlink(path, *args, **kwargs)                          # the build's own lock file is released as usual
    monkeypatch.setattr(eb.os, "unlink", refuse)
    result = eb.build(spec, ctx)
    assert not result.ok and result.error.code == "write_failed" and "Permission denied" in result.error.detail
    monkeypatch.undo()
    assert installed_names(site) == before and eb.broken_interpreter_links(paths.venv, MINOR) != []
    assert eb.build(spec, ctx).ok, "and the next try, with the fault gone, repairs it"
