# SPDX-License-Identifier: GPL-3.0-or-later
"""Building an environment (plan task VS-1.9): the order, the checks, and every way it can refuse or fail without damaging anything.

The computer and the network are stand-ins (tests/vs_env_helpers.py); the real thing, with a real Python environment, is test_vs_envbuild_real.py.
"""
import json
import os
import stat
import tarfile
from pathlib import Path

import pytest

from vs_env_helpers import GIB, GOOD_FILES, LOCK, PATCH, TOP, link, make_archive, make_rig, make_spec, special
from voice_studio.core import envbuild as eb
from voice_studio.core import fetch
from voice_studio.core.consent import make_consent
from voice_studio.core.envspec import lock_digest
from voice_studio.core.jobs import OFFLINE_ENV, boot_id, parse_proc_starttime, read_text_file

ALL_STEPS = ["source_unpack", "venv", "pip_lock", "pip_source", "native_build", "wrapper"]


def code_of(result):
    assert not result.ok and result.error is not None
    return result.error.code


@pytest.fixture
def rig(tmp_path):
    return make_rig(tmp_path)


# ---------------------------------------------------------------- a whole build

def test_a_fresh_build_runs_every_step_in_order_and_ends_ready(rig):
    result = rig.build()
    assert result.ok and result.error is None and list(result.did) == ALL_STEPS and result.kept == ()
    assert rig.record()["state"] == "ready" and sorted(rig.record()["steps"]) == sorted(ALL_STEPS)
    assert rig.step_ids("start") == ["room", "source_unpack", "source_fetch", "venv", "pip_lock", "pip_source", "native_build", "wrapper", "self_test"]
    assert rig.step_ids("done") == ["room", "source_fetch", "source_unpack", "venv", "pip_lock", "pip_source", "native_build", "wrapper", "self_test"]


def test_a_fresh_build_leaves_exactly_what_the_launcher_and_the_checks_need(rig):
    rig.build()
    paths = rig.paths
    assert Path(paths.source, "README").read_bytes() == b"hello\n" and Path(paths.source, "src/demo/__init__.py").exists()
    assert not Path(paths.source, TOP).exists(), "the archive's one top folder is dropped"
    assert Path(paths.env_dir, eb.LOCK_COPY_NAME).read_bytes() == LOCK
    assert Path(paths.launcher).read_text() == eb.launcher_text(rig.spec)
    assert Path(paths.source, eb.UNPACK_MARKER).read_text() == rig.item.sha256
    assert (Path(paths.venv) / "bin" / "python").exists() and list(Path(paths.source, "src").glob("core*.so"))


def test_the_pip_commands_are_the_safe_ones_and_carry_the_agreement_by_name(rig):
    rig.build()
    lock_cmd, source_cmd = rig.doors.pip_runs
    assert lock_cmd[:3] == (rig.paths.python, "-m", "pip") and lock_cmd[3] == "install"
    assert {"--require-hashes", "--only-binary=:all:", "--no-deps", "--no-input"} <= set(lock_cmd)
    assert lock_cmd[lock_cmd.index("-r") + 1] == rig.paths.env_dir + "/" + eb.LOCK_COPY_NAME
    assert {"--no-deps", "--no-build-isolation", "--no-index", "-e"} <= set(source_cmd) and source_cmd[source_cmd.index("-e") + 1] == rig.paths.source
    assert not any(a.startswith("http") or "index-url" in a or "find-links" in a for cmd in rig.doors.pip_runs for a in cmd)
    assert rig.doors.fetches == ["demo-source"]


def test_nothing_in_a_build_is_readable_by_other_people(rig):
    rig.build()
    for name in (rig.paths.env_dir, rig.paths.record, rig.paths.log, rig.paths.launcher, rig.paths.env_dir + "/" + eb.LOCK_COPY_NAME):
        mode = stat.S_IMODE(os.stat(name).st_mode)
        assert mode & 0o077 == 0, (name, oct(mode))


def test_building_again_changes_nothing_and_asks_the_network_for_nothing(rig):
    rig.build()
    rig.doors.fetches.clear()
    rig.doors.pip_runs.clear()
    before = rig.record()
    result = rig.build()
    assert result.ok and result.did == () and list(result.kept) == ALL_STEPS
    assert rig.doors.fetches == [] and rig.doors.pip_runs == []
    assert rig.record()["steps"] == before["steps"] and rig.record()["state"] == "ready"


def test_the_launcher_names_the_module_after_the_workarounds_and_edits_no_program_file(rig):
    rig.build()
    text = Path(rig.paths.launcher).read_text()
    assert text.index("import os") < text.index("runpy.run_module") and "sys.argv = sys.argv[1:]" in text
    assert compile(text, "launcher", "exec")


def test_the_probes_run_inside_the_environment_with_the_network_switched_off_and_no_compiled_files(rig):
    rig.build()
    codes = {code: env for code, env, cwd in rig.system.probe_runs}
    assert set(codes) == {"import os"}
    env = codes["import os"]
    assert all(env.get(k) == v for k, v in OFFLINE_ENV.items()) and env["PYTHONDONTWRITEBYTECODE"] == "1"
    assert rig.system.launcher_runs and rig.system.launcher_runs[0][0][-1] == "platform"


def test_a_probe_that_needs_the_graphics_card_is_skipped_without_one_and_run_with_one(tmp_path):
    without = make_rig(tmp_path / "a", gpu_ok=False)
    result = without.build()
    assert result.ok and result.skipped == ("card",) and ("skipped", "card") in [(e.kind, e.step) for e in without.events]
    assert without.record()["self_test"]["skipped"] == ["card"]
    with_card = make_rig(tmp_path / "b", gpu_ok=True)
    result = with_card.build()
    assert result.ok and result.skipped == () and {c for c, _, _ in with_card.system.probe_runs} == {"import os", "import sys"}


def test_an_environment_with_no_source_has_only_the_steps_it_needs(tmp_path):
    rig = make_rig(tmp_path, spec_over={"source": None, "patches": []})
    result = rig.build()
    assert result.ok and list(result.did) == ["venv", "pip_lock", "wrapper"] and rig.doors.fetches == []
    assert len(rig.doors.pip_runs) == 1


def test_an_environment_with_nothing_to_work_around_has_a_plain_launcher(tmp_path):
    rig = make_rig(tmp_path, spec_over={"prelude": []})
    assert rig.build().ok and rig.system.launcher_runs == [], "no workarounds, so no launcher check"


# ---------------------------------------------------------------- the name of the folder

def test_the_folder_is_named_for_what_it_is_built_from_and_a_different_lock_gets_a_different_folder(tmp_path):
    a = make_rig(tmp_path / "a")
    other = (LOCK + b"extra==1.0 --hash=sha256:" + b"c" * 64 + b"\n")
    b = make_rig(tmp_path / "b", lock=other)
    assert os.path.basename(a.env_dir).startswith("demo-") and os.path.basename(a.env_dir) != os.path.basename(b.env_dir)
    assert eb.fingerprint(a.spec, lock_digest(LOCK), a.item, (3, 12)) != eb.fingerprint(a.spec, lock_digest(other), a.item, (3, 12))


@pytest.mark.parametrize("change", ["python", "source", "install", "dist", "native", "patch"])
def test_each_thing_that_needs_a_new_environment_changes_the_name(tmp_path, change):
    base = make_rig(tmp_path / "base", spec_over={"patches": []})
    fp = eb.fingerprint(base.spec, lock_digest(LOCK), base.item, (3, 12))
    if change == "python":
        new = eb.fingerprint(base.spec, lock_digest(LOCK), base.item, (3, 11))
    elif change == "source":
        other = make_archive(tmp_path / "o.tar.gz", files={"x": (b"y", 0o644)})
        from vs_env_helpers import pinned_item
        new = eb.fingerprint(base.spec, lock_digest(LOCK), pinned_item(other), (3, 12))
    else:
        over = {"install": {"source": dict(__import__("copy").deepcopy(__import__("vs_env_helpers").BASE_SPEC["source"]), install=False)},
                "dist": {"source": dict(__import__("copy").deepcopy(__import__("vs_env_helpers").BASE_SPEC["source"]), dist="other-dist")},
                "native": {"source": dict(__import__("copy").deepcopy(__import__("vs_env_helpers").BASE_SPEC["source"]), native_build="other.sh")},
                "patch": {"patches": [PATCH]}}[change]
        spec = make_spec(LOCK, **over)
        new = eb.fingerprint(spec, lock_digest(LOCK), base.item, (3, 12))
    assert new != fp


def test_the_launchers_workarounds_do_not_change_the_name_because_they_are_rewritten_in_place(tmp_path):
    a = make_rig(tmp_path / "a", spec_over={"prelude": ["import os"]})
    b = make_rig(tmp_path / "b", spec_over={"prelude": ["import os", "import sys"]})
    assert eb.fingerprint(a.spec, lock_digest(LOCK), a.item, (3, 12)) == eb.fingerprint(b.spec, lock_digest(LOCK), b.item, (3, 12))


def test_a_new_lock_builds_next_to_the_old_environment_and_leaves_it_alone(tmp_path):
    first = make_rig(tmp_path)
    assert first.build().ok
    old_dir = first.env_dir
    marker = Path(old_dir, "mine.txt")
    marker.write_text("keep")
    newer = (LOCK + b"extra==1.0 --hash=sha256:" + b"c" * 64 + b"\n")
    second = make_rig(tmp_path / "again", lock=newer)
    second.ctx.home = first.ctx.home                                   # the same data home
    second.system.venv_dists = {}
    assert second.build().ok
    assert second.env_dir != old_dir and Path(old_dir).is_dir() and marker.read_text() == "keep"
    assert first.record()["state"] == "ready"


# ---------------------------------------------------------------- it refuses to start

def test_an_unpinned_environment_is_refused_before_anything_is_made(tmp_path):
    rig = make_rig(tmp_path)
    unpinned = make_spec(LOCK)
    object.__setattr__(unpinned, "lock_sha256", None)
    result = eb.build(unpinned, rig.ctx)
    assert code_of(result) == "not_pinned" and "lock_unpinned" in result.error.detail
    assert not rig.environments.exists() and rig.doors.fetches == []


def test_a_source_that_is_not_pinned_in_the_registry_is_refused(tmp_path):
    rig = make_rig(tmp_path)
    from voice_studio.core.registry import Item, Registry
    rig.ctx.registry = Registry((Item("demo-source", "source", "fetch.why.x", "l", approx_size_bytes=5),))
    result = rig.build()
    assert code_of(result) == "not_pinned" and "source_unpinned" in result.error.detail and not rig.environments.exists()


def test_a_lock_file_that_cannot_be_read_is_refused(tmp_path):
    rig = make_rig(tmp_path)

    def gone(spec):
        raise FileNotFoundError(2, "No such file or directory")

    rig.ctx.read_lock = gone
    assert code_of(rig.build()) == "lock_missing" and not rig.environments.exists()


def test_a_lock_that_is_not_the_one_that_was_checked_is_refused_even_by_one_byte(tmp_path):
    rig = make_rig(tmp_path)
    rig.ctx.read_lock = lambda s: LOCK + b" "
    assert code_of(rig.build()) == "lock_changed" and not rig.environments.exists() and rig.doors.pip_runs == []


@pytest.mark.parametrize("bad", [b"numpy==1.0\n", b"numpy>=1.0 --hash=sha256:" + b"a" * 64 + b"\n", b"--index-url x\nnumpy==1.0 --hash=sha256:" + b"a" * 64 + b"\n",
                                 b"# nothing\n", b"\xff\xfe"])
def test_a_lock_the_rules_do_not_allow_is_refused_though_its_checksum_matches(tmp_path, bad):
    rig = make_rig(tmp_path, lock=bad)
    assert code_of(rig.build()) == "lock_invalid" and not rig.environments.exists()


@pytest.mark.parametrize("version, ok", [((3, 9, 18), False), ((3, 10, 0), True), ((3, 10, 12), True), ((3, 12, 3), True), ((2, 7, 18), False)])
def test_the_python_must_be_new_enough_at_the_exact_edge(tmp_path, version, ok):
    rig = make_rig(tmp_path, system_kw={"python": version})
    result = rig.build()
    assert result.ok if ok else code_of(result) == "python_old"
    if not ok:
        assert not rig.environments.exists()


# ---------------------------------------------------------------- what is already there

def test_a_folder_with_the_name_but_no_record_is_never_touched(tmp_path):
    rig = make_rig(tmp_path)
    target = Path(rig.env_dir)
    target.mkdir(parents=True)
    (target / "precious.txt").write_text("not yours to touch")
    result = rig.build()
    assert code_of(result) == "not_ours" and sorted(os.listdir(target)) == ["precious.txt"]
    assert (target / "precious.txt").read_text() == "not yours to touch" and rig.doors.pip_runs == [] and rig.doors.fetches == []


def test_a_file_where_the_folder_should_be_is_not_ours_either(tmp_path):
    rig = make_rig(tmp_path)
    target = Path(rig.env_dir)
    target.parent.mkdir(parents=True)
    target.write_text("a file")
    assert code_of(rig.build()) == "not_ours" and target.read_text() == "a file"


def test_a_record_from_a_newer_version_is_left_exactly_as_it_is(tmp_path):
    rig = make_rig(tmp_path)
    assert rig.build().ok
    record_path = Path(rig.paths.record)
    data = json.loads(record_path.read_text())
    data["schema"] = eb.SCHEMA + 1
    data["from_the_future"] = {"x": 1}
    record_path.write_text(json.dumps(data))
    before = record_path.read_bytes()
    assert code_of(rig.build()) == "newer_record" and record_path.read_bytes() == before


@pytest.mark.parametrize("damage", ["not json", "[]", "{}", '{"schema": "1", "steps": {}, "patches": {}, "id": "demo", "fingerprint": "x"}',
                                    '{"schema": true, "steps": {}, "patches": {}, "id": "demo", "fingerprint": "x"}',
                                    '{"schema": 1, "steps": [], "patches": {}, "id": "demo", "fingerprint": "x"}',
                                    '{"schema": 1, "steps": {}, "patches": {}, "id": 5, "fingerprint": "x"}', ""])
def test_a_damaged_record_is_reported_and_never_rewritten(tmp_path, damage):
    rig = make_rig(tmp_path)
    assert rig.build().ok
    Path(rig.paths.record).write_text(damage)
    result = rig.build()
    assert code_of(result) == "damaged_record" and Path(rig.paths.record).read_text() == damage


def test_a_record_for_a_different_environment_is_not_trusted(tmp_path):
    rig = make_rig(tmp_path)
    assert rig.build().ok
    data = rig.record()
    data["id"] = "something-else"
    Path(rig.paths.record).write_text(json.dumps(data))
    assert code_of(rig.build()) == "damaged_record"
    data["id"], data["fingerprint"] = "demo", "0" * 64
    Path(rig.paths.record).write_text(json.dumps(data))
    assert code_of(rig.build()) == "damaged_record"


# ---------------------------------------------------------------- one build at a time

def write_lock(rig, **fields):
    Path(rig.env_dir).mkdir(parents=True, exist_ok=True)
    Path(rig.env_dir, eb.BUILD_LOCK_NAME).write_text(json.dumps(fields) if fields else "garbage")


def test_a_build_already_running_makes_this_one_wait_and_does_not_disturb_it(tmp_path):
    rig = make_rig(tmp_path)
    assert rig.build().ok
    mine = {"pid": os.getpid(), "starttime": parse_proc_starttime(read_text_file("/proc/self/stat")), "boot": boot_id()}
    if mine["starttime"] is None or not mine["boot"]:
        pytest.skip("needs /proc")
    write_lock(rig, **mine)
    before = Path(rig.env_dir, eb.BUILD_LOCK_NAME).read_text()
    result = rig.build()
    assert code_of(result) == "busy" and Path(rig.env_dir, eb.BUILD_LOCK_NAME).read_text() == before


@pytest.mark.parametrize("held", [{"pid": 2**22 + 7, "starttime": 1, "boot": "x"}, {"pid": None, "starttime": None, "boot": ""}, {}, None],
                         ids=["dead process", "no process", "empty", "unreadable"])
def test_a_lock_left_by_a_build_that_is_gone_is_taken_over(tmp_path, held):
    rig = make_rig(tmp_path)
    assert rig.build().ok
    write_lock(rig, **(held or {}))
    assert rig.build().ok and not Path(rig.env_dir, eb.BUILD_LOCK_NAME).exists()


def test_a_lock_from_before_a_restart_is_not_the_running_build(tmp_path):
    rig = make_rig(tmp_path)
    assert rig.build().ok
    mine = {"pid": os.getpid(), "starttime": parse_proc_starttime(read_text_file("/proc/self/stat")), "boot": "an-earlier-boot"}
    if mine["starttime"] is None:
        pytest.skip("needs /proc")
    write_lock(rig, **mine)
    assert rig.build().ok


def test_the_build_lock_is_released_after_success_and_after_failure(tmp_path):
    rig = make_rig(tmp_path)
    assert rig.build().ok and not Path(rig.env_dir, eb.BUILD_LOCK_NAME).exists()
    rig.doors.pip_fail["lock"] = 1
    Path(rig.paths.record).unlink()                        # a fresh claim is not possible over a folder with no record, so use a new name
    other = make_rig(tmp_path / "x")
    other.doors.pip_fail["lock"] = 1
    assert code_of(other.build()) == "pip_failed" and not Path(other.env_dir, eb.BUILD_LOCK_NAME).exists()


def test_the_build_lock_appears_complete_or_not_at_all_and_leaves_no_temporary_file(tmp_path, monkeypatch):
    rig = make_rig(tmp_path)
    seen = []
    real_link = os.link

    def watching(src, dst, *args, **kwargs):
        seen.append(json.loads(Path(src).read_text()))              # the file being linked in is already complete
        return real_link(src, dst, *args, **kwargs)

    monkeypatch.setattr(eb.os, "link", watching)
    assert rig.build().ok
    assert len(seen) == 1 and seen[0]["pid"] == os.getpid() and set(seen[0]) == {"pid", "starttime", "boot"}
    assert [n for n in os.listdir(rig.env_dir) if n.startswith(eb.BUILD_LOCK_NAME)] == []


def test_a_drive_that_cannot_make_hard_links_still_gets_a_lock(tmp_path, monkeypatch):
    import errno
    rig = make_rig(tmp_path)

    def refuse(src, dst, *args, **kwargs):
        raise OSError(errno.EPERM, "Operation not permitted")

    monkeypatch.setattr(eb.os, "link", refuse)
    held_during = []
    original = rig.ctx.fetcher

    def watching(item, dest, consent):
        held_during.append(Path(rig.env_dir, eb.BUILD_LOCK_NAME).exists())
        return original(item, dest, consent)

    rig.ctx.fetcher = watching
    assert rig.build().ok and held_during == [True] and not Path(rig.env_dir, eb.BUILD_LOCK_NAME).exists()


def test_without_hard_links_a_second_build_is_still_kept_out(tmp_path, monkeypatch):
    import errno
    rig = make_rig(tmp_path)
    assert rig.build().ok
    mine = {"pid": os.getpid(), "starttime": parse_proc_starttime(read_text_file("/proc/self/stat")), "boot": boot_id()}
    if mine["starttime"] is None or not mine["boot"]:
        pytest.skip("needs /proc")
    write_lock(rig, **mine)
    monkeypatch.setattr(eb.os, "link", lambda *a, **k: (_ for _ in ()).throw(OSError(errno.EPERM, "no links")))
    assert code_of(rig.build()) == "busy"


def test_unexpected_trouble_with_files_is_a_plain_failure_and_the_lock_is_still_released(tmp_path):
    rig = make_rig(tmp_path)

    def broken(item, dest, consent):
        raise OSError(28, "No space left on device")

    rig.ctx.fetcher = broken
    result = rig.build()
    assert code_of(result) == "write_failed" and result.error.detail == "No space left on device"
    assert rig.record()["state"] == "failed" and not Path(rig.env_dir, eb.BUILD_LOCK_NAME).exists()


def test_the_lock_file_is_owner_only_while_held(tmp_path):
    rig = make_rig(tmp_path)
    seen = []
    original = rig.ctx.fetcher

    def watching(item, dest, consent):
        seen.append(stat.S_IMODE(os.stat(Path(rig.env_dir, eb.BUILD_LOCK_NAME)).st_mode))
        return original(item, dest, consent)

    rig.ctx.fetcher = watching
    assert rig.build().ok and seen == [0o600]


# ---------------------------------------------------------------- room

NEED = 1000 + eb.ROOM_MARGIN_BYTES


@pytest.mark.parametrize("free, ok", [(NEED - 1, False), (NEED, True), (NEED + 1, True), (0, False)])
def test_there_must_be_room_for_the_whole_environment_and_the_margin_at_the_exact_edge(tmp_path, free, ok):
    rig = make_rig(tmp_path, system_kw={"free": free})
    result = rig.build()
    assert result.ok if ok else code_of(result) == "no_room"
    if not ok:
        assert rig.doors.fetches == [] and rig.doors.pip_runs == [] and rig.record()["state"] == "failed" and rig.record()["failed"]["code"] == "no_room"


def test_a_drive_that_reports_nothing_does_not_block_the_build(tmp_path):
    rig = make_rig(tmp_path)
    rig.system.disk_free = lambda path: None
    assert rig.build().ok


def test_a_resumed_build_with_only_small_steps_left_needs_much_less_room(tmp_path):
    rig = make_rig(tmp_path)
    assert rig.build().ok
    Path(rig.paths.launcher).unlink()
    rig.system.free = eb.RESUME_NEED_BYTES + eb.ROOM_MARGIN_BYTES
    assert rig.build().ok
    Path(rig.paths.launcher).unlink()
    rig.system.free = eb.RESUME_NEED_BYTES + eb.ROOM_MARGIN_BYTES - 1
    assert code_of(rig.build()) == "no_room"


def test_nothing_is_checked_for_room_when_nothing_is_left_to_do(tmp_path):
    rig = make_rig(tmp_path)
    assert rig.build().ok
    rig.system.free = 0
    assert rig.build().ok and "room" not in rig.step_ids("start")[len(ALL_STEPS) + 3:]


# ---------------------------------------------------------------- the agreement

def test_without_the_agreement_for_the_packages_nothing_is_installed(tmp_path):
    rig = make_rig(tmp_path, consent_pip=False)
    result = rig.build()
    assert code_of(result) == "consent" and "pip:demo" in result.error.detail and rig.doors.pip_runs == []
    assert list(result.did) == ["source_unpack", "venv"] and rig.record()["state"] == "failed"


def test_without_the_agreement_for_the_source_nothing_is_downloaded(tmp_path):
    rig = make_rig(tmp_path)
    rig.ctx.consent = make_consent([], extra_ids=["pip:demo"])
    result = rig.build()
    assert code_of(result) == "consent" and result.error.detail == "demo-source" and rig.doors.pip_runs == []


def test_with_no_agreement_at_all_nothing_happens(tmp_path):
    rig = make_rig(tmp_path)
    rig.ctx.consent = None
    assert code_of(rig.build()) == "consent" and not Path(rig.env_dir, "venv").exists()


def test_an_agreement_for_another_environments_packages_does_not_cover_this_one(tmp_path):
    rig = make_rig(tmp_path, consent_pip=False)
    rig.ctx.consent = make_consent([rig.item], extra_ids=["pip:training"])
    assert code_of(rig.build()) == "consent"


def test_a_download_that_fails_says_why_and_leaves_the_rest_alone(tmp_path):
    rig = make_rig(tmp_path)
    rig.doors.fetch_error = "http"
    result = rig.build()
    assert code_of(result) == "source_fetch" and result.error.detail == "http" and not Path(rig.paths.source).exists()
    rig.doors.fetch_error = None
    assert rig.build().ok


# ---------------------------------------------------------------- unpacking safely

def unpack(tmp_path, **kw):
    archive = make_archive(tmp_path / "a.tar.gz", **kw)
    dest = tmp_path / "out" / "source"
    dest.parent.mkdir(exist_ok=True)
    eb.unpack_archive(archive, dest, "marker")
    return dest


def test_unpacking_drops_the_top_folder_keeps_the_executable_bit_and_writes_the_marker(tmp_path):
    dest = unpack(tmp_path)
    assert (dest / "build.sh").stat().st_mode & 0o111 and not (dest / "README").stat().st_mode & 0o111
    assert (dest / eb.UNPACK_MARKER).read_text() == "marker" and (dest / "src/demo/train.py").read_bytes() == GOOD_FILES["src/demo/train.py"][0]
    assert not Path(str(dest) + ".part").exists()


def test_a_link_that_stays_inside_the_folder_is_allowed(tmp_path):
    dest = unpack(tmp_path, extra=[(link(TOP + "/latest", "src/demo"), None)])
    assert os.path.islink(dest / "latest") and os.path.realpath(dest / "latest") == os.path.realpath(dest / "src/demo")


@pytest.mark.parametrize("name, extra", [
    ("absolute name", [(special("/etc/evil", tarfile.REGTYPE), b"")]),
    ("dot dot name", [(special(TOP + "/../evil", tarfile.REGTYPE), b"")]),
    ("dot dot at the start", [(special("../evil", tarfile.REGTYPE), b"")]),
    ("a backslash in a name", [(special(TOP + "/a\\b", tarfile.REGTYPE), b"")]),
    ("link out of the folder", [(link(TOP + "/out", "../../../etc"), None)]),
    ("absolute link", [(link(TOP + "/out", "/etc/passwd"), None)]),
    ("hard link", [(link(TOP + "/hard", TOP + "/README", hard=True), None)]),
    ("device", [(special(TOP + "/dev", tarfile.CHRTYPE), None)]),
    ("pipe", [(special(TOP + "/pipe", tarfile.FIFOTYPE), None)]),
    ("a second top folder", [(special("other/file", tarfile.REGTYPE), b"")]),
    ("link with no target", [(link(TOP + "/empty", ""), None)]),
])
def test_an_archive_with_something_unsafe_in_it_is_refused_and_leaves_nothing_behind(tmp_path, name, extra):
    archive = make_archive(tmp_path / "a.tar.gz", extra=extra)
    dest = tmp_path / "out" / "source"
    dest.parent.mkdir()
    with pytest.raises(eb.EnvError) as caught:
        eb.unpack_archive(archive, dest, "m")
    assert caught.value.code == "unpack_unsafe", name
    assert os.listdir(dest.parent) == [] and not (tmp_path / "evil").exists() and not Path("/etc/evil").exists()


def test_a_link_that_looks_inside_but_would_leave_by_way_of_another_link_is_refused(tmp_path):
    # x/y/z points at the top folder itself, so a link written *through* it with "../../.." climbs out of the folder, though its name does not
    extra = [(link(TOP + "/x/y/z", "../.."), None), (link(TOP + "/x/y/z/w", "../../.."), None)]
    archive = make_archive(tmp_path / "a.tar.gz", extra=extra)
    dest = tmp_path / "out" / "source"
    dest.parent.mkdir()
    with pytest.raises(eb.EnvError) as caught:
        eb.unpack_archive(archive, dest, "m")
    assert caught.value.code == "unpack_unsafe" and os.listdir(dest.parent) == []


def test_a_file_written_through_a_link_that_goes_outside_is_refused(tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    extra = [(link(TOP + "/escape", str(outside)), None), (special(TOP + "/escape/pwned", tarfile.REGTYPE), b"")]
    archive = make_archive(tmp_path / "a.tar.gz", extra=extra)
    dest = tmp_path / "out" / "source"
    dest.parent.mkdir()
    with pytest.raises(eb.EnvError):
        eb.unpack_archive(archive, dest, "m")
    assert os.listdir(outside) == []


def test_too_much_data_or_too_many_files_is_refused(tmp_path, monkeypatch):
    archive = make_archive(tmp_path / "a.tar.gz")
    dest = tmp_path / "out" / "source"
    dest.parent.mkdir()
    total = sum(len(d) for d, _ in GOOD_FILES.values())
    monkeypatch.setattr(eb, "MAX_UNPACK_BYTES", total - 1)
    with pytest.raises(eb.EnvError) as caught:
        eb.unpack_archive(archive, dest, "m")
    assert caught.value.code == "unpack_unsafe" and os.listdir(dest.parent) == []
    monkeypatch.setattr(eb, "MAX_UNPACK_BYTES", total)
    eb.unpack_archive(archive, dest, "m")
    shutil_target = tmp_path / "out" / "again"
    monkeypatch.setattr(eb, "MAX_UNPACK_FILES", len(GOOD_FILES))
    with pytest.raises(eb.EnvError) as caught:
        eb.unpack_archive(archive, shutil_target, "m")
    assert caught.value.code == "unpack_unsafe"
    monkeypatch.setattr(eb, "MAX_UNPACK_FILES", len(GOOD_FILES) + 1)
    eb.unpack_archive(archive, shutil_target, "m")


def member(name, kind=tarfile.REGTYPE, size=0, linkname=""):
    info = tarfile.TarInfo(name)
    info.type, info.size, info.linkname = kind, size, linkname
    return info


@pytest.mark.parametrize("members, fragment", [
    ([member("top/"), member("top/../x")], "unsafe name"),
    ([member("top/a"), member("/abs/x")], "unsafe name"),
    ([member("top/a\\b")], "unsafe name"),
    ([member("")], "unsafe name"),
    ([member("top/dev", tarfile.CHRTYPE)], "not an ordinary"),
    ([member("top/blk", tarfile.BLKTYPE)], "not an ordinary"),
    ([member("top/hard", tarfile.LNKTYPE, linkname="top/a")], "not an ordinary"),
    ([member("top/s", tarfile.SYMTYPE)], "no usable link target"),
    ([member("one/a"), member("two/b")], "one top folder"),
    ([], "empty"),
])
def test_each_rule_about_what_may_be_in_an_archive_is_enforced_on_its_own(members, fragment):
    with pytest.raises(eb.EnvError) as caught:
        eb._check_members(members)
    assert fragment in caught.value.detail


def test_the_list_of_members_accepts_an_ordinary_archive_and_the_edges_of_its_limits(monkeypatch):
    ordinary = [member("top/", tarfile.DIRTYPE), member("top/a", size=5), member("top/s", tarfile.SYMTYPE, linkname="a")]
    eb._check_members(ordinary)
    monkeypatch.setattr(eb, "MAX_UNPACK_BYTES", 5)
    eb._check_members(ordinary)
    monkeypatch.setattr(eb, "MAX_UNPACK_BYTES", 4)
    with pytest.raises(eb.EnvError, match="too large"):
        eb._check_members(ordinary)
    monkeypatch.setattr(eb, "MAX_UNPACK_BYTES", 5)
    monkeypatch.setattr(eb, "MAX_UNPACK_FILES", 3)
    eb._check_members(ordinary)
    monkeypatch.setattr(eb, "MAX_UNPACK_FILES", 2)
    with pytest.raises(eb.EnvError, match="too many"):
        eb._check_members(ordinary)


def test_a_name_that_climbs_out_is_stopped_again_at_the_moment_of_writing_even_if_the_list_check_were_skipped(tmp_path, monkeypatch):
    monkeypatch.setattr(eb, "_check_members", lambda members: None)
    archive = make_archive(tmp_path / "a.tar.gz", extra=[(special(TOP + "/../../escaped", tarfile.REGTYPE), b"x")])
    dest = tmp_path / "work" / "out" / "source"
    dest.parent.mkdir(parents=True)
    with pytest.raises(eb.EnvError) as caught:
        eb.unpack_archive(archive, dest, "m")
    assert caught.value.code == "unpack_unsafe" and not (tmp_path / "work" / "escaped").exists() and not (tmp_path / "escaped").exists()
    assert os.listdir(dest.parent) == []


def test_two_files_of_the_same_name_in_an_archive_are_not_allowed_to_overwrite_each_other(tmp_path):
    archive = make_archive(tmp_path / "a.tar.gz", extra=[(special(TOP + "/README", tarfile.REGTYPE), b"")])
    dest = tmp_path / "out" / "source"
    dest.parent.mkdir()
    with pytest.raises(eb.EnvError) as caught:
        eb.unpack_archive(archive, dest, "m")
    assert caught.value.code == "unpack_failed" and os.listdir(dest.parent) == []


@pytest.mark.parametrize("kind", ["empty folder", "link"])
def test_not_even_an_empty_folder_or_a_link_in_the_way_is_replaced(tmp_path, kind):
    archive = make_archive(tmp_path / "a.tar.gz")
    dest = tmp_path / "source"
    if kind == "empty folder":
        dest.mkdir()
    else:
        dest.symlink_to(tmp_path / "elsewhere")                        # a link to nowhere: it does not "exist", but it is in the way
    with pytest.raises(eb.EnvError) as caught:
        eb.unpack_archive(archive, dest, "m")
    assert caught.value.code == "unpack_failed" and (dest.is_symlink() if kind == "link" else dest.is_dir())
    assert (not (tmp_path / "elsewhere").exists()) if kind == "link" else os.listdir(dest) == []


def test_an_archive_that_is_not_an_archive_or_is_empty_is_a_plain_failure(tmp_path):
    bad = tmp_path / "bad.tar.gz"
    bad.write_bytes(b"this is not a tar file at all")
    dest = tmp_path / "source"
    with pytest.raises(eb.EnvError) as caught:
        eb.unpack_archive(bad, dest, "m")
    assert caught.value.code == "unpack_failed" and not dest.exists() and not Path(str(dest) + ".part").exists()
    empty = tmp_path / "empty.tar.gz"
    with tarfile.open(str(empty), "w:gz"):
        pass
    with pytest.raises(eb.EnvError) as caught:
        eb.unpack_archive(empty, dest, "m")
    assert caught.value.code == "unpack_failed"


def test_a_truncated_archive_leaves_nothing_that_looks_finished(tmp_path):
    archive = make_archive(tmp_path / "a.tar.gz", files={"big": (os.urandom(200_000), 0o644)})
    data = archive.read_bytes()
    archive.write_bytes(data[: len(data) // 2])
    dest = tmp_path / "source"
    with pytest.raises(eb.EnvError) as caught:
        eb.unpack_archive(archive, dest, "m")
    assert caught.value.code == "unpack_failed" and not dest.exists() and not Path(str(dest) + ".part").exists()


def test_a_leftover_half_unpacked_folder_from_a_stopped_build_is_replaced(tmp_path):
    archive = make_archive(tmp_path / "a.tar.gz")
    dest = tmp_path / "source"
    Path(str(dest) + ".part").mkdir()
    (Path(str(dest) + ".part") / "stale").write_text("x")
    eb.unpack_archive(archive, dest, "m")
    assert not (dest / "stale").exists() and (dest / "README").exists() and not Path(str(dest) + ".part").exists()


def test_a_folder_already_in_the_way_is_never_replaced(tmp_path):
    archive = make_archive(tmp_path / "a.tar.gz")
    dest = tmp_path / "source"
    dest.mkdir()
    (dest / "mine").write_text("keep")
    with pytest.raises(eb.EnvError) as caught:
        eb.unpack_archive(archive, dest, "m")
    assert caught.value.code == "unpack_failed" and (dest / "mine").read_text() == "keep"


def test_a_source_folder_that_is_not_what_was_unpacked_is_never_replaced(tmp_path):
    rig = make_rig(tmp_path)
    assert rig.build().ok
    Path(rig.paths.source, eb.UNPACK_MARKER).write_text("something else")
    (Path(rig.paths.source) / "mine.txt").write_text("keep")
    result = rig.build()
    assert code_of(result) == "unpack_failed" and (Path(rig.paths.source) / "mine.txt").read_text() == "keep" and Path(rig.paths.source, "README").exists()


def test_a_build_that_meets_a_bad_archive_stops_there_and_installs_nothing(tmp_path):
    rig = make_rig(tmp_path, archive_extra=[(link(TOP + "/out", "../../x"), None)])
    result = rig.build()
    assert code_of(result) == "unpack_unsafe" and rig.doors.pip_runs == [] and not Path(rig.paths.source).exists() and not Path(rig.paths.venv).exists()


# ---------------------------------------------------------------- failures, and carrying on afterwards

def test_a_venv_that_cannot_be_made_stops_the_build_and_the_next_try_continues_from_there(tmp_path):
    rig = make_rig(tmp_path)
    from voice_studio.core.system import CommandResult
    rig.system.fail_venv = CommandResult(1, "", "The virtual environment was not created successfully because ensurepip is not available.\n")
    result = rig.build()
    assert code_of(result) == "venv_failed" and list(result.did) == ["source_unpack"] and any("ensurepip" in line for line in result.error.tail)
    assert rig.record()["failed"]["code"] == "venv_failed"
    rig.system.fail_venv = None
    again = rig.build()
    assert again.ok and list(again.kept) == ["source_unpack"] and list(again.did) == ["venv", "pip_lock", "pip_source", "native_build", "wrapper"]
    assert "failed" not in rig.record()


def test_a_venv_command_that_cannot_run_at_all_is_a_plain_failure(tmp_path):
    rig = make_rig(tmp_path)
    rig.system.fail_venv = "none"
    result = rig.build()
    assert code_of(result) == "venv_failed" and "could not run" in result.error.detail


def test_a_failed_package_install_keeps_what_was_done_and_shows_the_end_of_the_output(tmp_path):
    rig = make_rig(tmp_path)
    rig.doors.pip_fail["lock"] = 1
    result = rig.build()
    assert code_of(result) == "pip_failed" and result.error.detail == "exit 1" and list(result.did) == ["source_unpack", "venv"]
    assert "ERROR: No matching distribution" in result.error.tail and len(result.error.tail) <= eb.TAIL_LINES
    rig.doors.pip_fail.clear()
    again = rig.build()
    assert again.ok and list(again.kept) == ["source_unpack", "venv"] and list(again.did) == ["pip_lock", "pip_source", "native_build", "wrapper"]


def test_a_failed_source_install_is_retried_on_its_own(tmp_path):
    rig = make_rig(tmp_path)
    rig.doors.pip_fail["source"] = 2
    result = rig.build()
    assert code_of(result) == "pip_failed" and result.error.detail == "exit 2" and list(result.did) == ["source_unpack", "venv", "pip_lock"]
    rig.doors.pip_fail.clear()
    rig.doors.pip_runs.clear()
    again = rig.build()
    assert again.ok and list(again.did) == ["pip_source", "native_build", "wrapper"] and len(rig.doors.pip_runs) == 1


def test_the_native_part_is_built_from_the_source_folder_with_the_environments_tools_first(tmp_path):
    rig = make_rig(tmp_path)
    rig.system._environ["PATH"] = "/usr/bin:/bin"
    assert rig.build().ok
    argv, cwd, env = rig.system.native_runs[0]
    assert argv == ["bash", "build.sh"] and cwd == rig.paths.source
    assert env["PATH"] == rig.paths.venv + "/bin:/usr/bin:/bin" and env["VIRTUAL_ENV"] == rig.paths.venv


@pytest.mark.parametrize("how", ["exit", "nothing built", "cannot run"])
def test_a_native_build_that_fails_or_builds_nothing_is_not_called_done(tmp_path, how):
    rig = make_rig(tmp_path)
    from voice_studio.core.system import CommandResult
    if how == "exit":
        rig.system.fail_native = CommandResult(1, "", "cython: command not found\n")
    elif how == "cannot run":
        rig.system.fail_native = None
        rig.system.run_bash_missing = True
        original = rig.system.run

        def run(argv, timeout=15.0, cwd=None, env=None):
            return None if argv[0] == "bash" else original(argv, timeout, cwd, env)

        rig.system.run = run
    else:
        rig.system.native_makes = False
    result = rig.build()
    assert code_of(result) == "native_failed" and "native_build" not in result.did and "wrapper" not in result.did
    if how == "exit":
        assert any("cython" in line for line in result.error.tail)
    if how == "nothing built":
        assert result.error.detail == "nothing was built"
    if how == "cannot run":
        assert "could not run" in result.error.detail


def test_a_native_build_that_exits_with_an_error_is_failed_even_though_it_left_a_file_behind(tmp_path):
    rig = make_rig(tmp_path)
    rig.system.native_makes_then_fails = True
    result = rig.build()
    assert code_of(result) == "native_failed" and result.error.detail == "exit 2" and any("Error 2" in line for line in result.error.tail)


def test_a_python_that_is_not_a_virtual_environment_is_not_accepted_as_one(tmp_path):
    rig = make_rig(tmp_path)
    assert rig.build().ok
    rig.system.venv_flag = "0"
    assert list(rig.build().did)[:1] == ["venv"]


def test_a_failed_probe_names_itself_and_the_build_is_not_ready(tmp_path):
    rig = make_rig(tmp_path)
    rig.system.bad_probe_codes = {"import os"}
    result = rig.build()
    assert code_of(result) == "self_test_failed" and result.error.detail == "imports" and any("ImportError" in line for line in result.error.tail)
    assert rig.record()["state"] == "failed" and list(result.did) == ALL_STEPS


def test_a_failed_launcher_check_is_its_own_error(tmp_path):
    rig = make_rig(tmp_path)
    rig.system.fail_launcher = True
    result = rig.build()
    assert code_of(result) == "launcher_failed" and rig.record()["state"] == "failed"


def test_after_a_failed_self_test_the_next_build_only_repeats_the_test(tmp_path):
    rig = make_rig(tmp_path)
    rig.system.bad_probe_codes = {"import os"}
    assert not rig.build().ok
    rig.system.bad_probe_codes = set()
    rig.doors.pip_runs.clear()
    again = rig.build()
    assert again.ok and again.did == () and rig.record()["state"] == "ready" and rig.doors.pip_runs == []


def test_only_the_end_of_a_long_output_is_kept_with_the_error(tmp_path):
    rig = make_rig(tmp_path)
    rig.doors.pip_lines = ["line %02d" % n for n in range(40)]
    rig.doors.pip_fail["lock"] = 1
    tail = rig.build().error.tail
    assert len(tail) == eb.TAIL_LINES and tail[-1] == "ERROR: No matching distribution" and tail[0] == "line 29"
    assert "line 00" in Path(rig.paths.log).read_text(), "the whole output is in the log"


def test_every_failure_is_written_to_the_record_with_a_short_detail(tmp_path):
    rig = make_rig(tmp_path)
    rig.doors.pip_fail["lock"] = 1
    rig.build()
    failed = rig.record()["failed"]
    assert failed["code"] == "pip_failed" and failed["detail"] == "exit 1" and failed["at"].endswith("Z")


def test_the_log_keeps_every_line_the_commands_printed_and_the_events_carry_them(tmp_path):
    rig = make_rig(tmp_path)
    assert rig.build().ok
    log = Path(rig.paths.log).read_text()
    assert "Collecting x" in log and "built" in log and "created" in log
    lines = [e.text for e in rig.events if e.kind == "line"]
    assert "Collecting x" in lines and "built" in lines
    assert all(e.step in eb.ACTION_IDS for e in rig.events if e.kind != "skipped"), "a skipped probe is named by its own id"


# ---------------------------------------------------------------- repairing what was removed

def test_a_removed_environment_is_rebuilt_from_the_venv_on_and_the_source_is_kept(tmp_path):
    import shutil
    rig = make_rig(tmp_path)
    assert rig.build().ok
    shutil.rmtree(rig.paths.venv)
    rig.doors.fetches.clear()
    result = rig.build()
    assert result.ok and list(result.kept) == ["source_unpack", "native_build", "wrapper"] and list(result.did) == ["venv", "pip_lock", "pip_source"]
    assert rig.doors.fetches == []


def test_a_removed_source_is_unpacked_again_from_the_downloaded_file(tmp_path):
    import shutil
    rig = make_rig(tmp_path)
    assert rig.build().ok
    shutil.rmtree(rig.paths.source)
    result = rig.build()
    assert result.ok and "source_unpack" in result.did and "native_build" in result.did, "the built part lived in the source folder"


def test_a_missing_native_part_is_built_again(tmp_path):
    rig = make_rig(tmp_path)
    assert rig.build().ok
    for f in Path(rig.paths.source, "src").glob("core*.so"):
        f.unlink()
    result = rig.build()
    assert result.ok and list(result.did) == ["native_build"]


def test_a_missing_launcher_is_written_again_and_a_changed_one_too(tmp_path):
    rig = make_rig(tmp_path)
    assert rig.build().ok
    Path(rig.paths.launcher).unlink()
    assert list(rig.build().did) == ["wrapper"]
    Path(rig.paths.launcher).write_text("tampered")
    assert list(rig.build().did) == ["wrapper"] and Path(rig.paths.launcher).read_text() == eb.launcher_text(rig.spec)


def test_a_package_that_was_uninstalled_is_installed_again(tmp_path):
    rig = make_rig(tmp_path)
    assert rig.build().ok
    del rig.system.venv_dists["quart"]
    result = rig.build()
    assert result.ok and list(result.did) == ["pip_lock"]


def test_a_package_at_the_wrong_version_is_installed_again(tmp_path):
    rig = make_rig(tmp_path)
    assert rig.build().ok
    rig.system.venv_dists["numpy"] = "9.9.9"
    assert list(rig.build().did) == ["pip_lock"]


def test_the_source_package_missing_means_the_source_step_runs_again(tmp_path):
    rig = make_rig(tmp_path)
    assert rig.build().ok
    del rig.system.venv_dists["demo-dist"]
    assert list(rig.build().did) == ["pip_source"]


def test_an_environment_on_a_different_python_minor_than_recorded_is_rebuilt_in_place(tmp_path):
    rig = make_rig(tmp_path)
    assert rig.build().ok
    rig.system.venv_minor = "3.11"
    assert "venv" in rig.build().did


def test_a_step_whose_input_changed_runs_again_even_if_it_looks_fine(tmp_path):
    rig = make_rig(tmp_path)
    assert rig.build().ok
    record = rig.record()
    record["steps"]["pip_lock"]["input"] = "an older lock"
    Path(rig.paths.record).write_text(json.dumps(record))
    assert list(rig.build().did) == ["pip_lock"]


def test_a_changed_workaround_list_rewrites_the_launcher_only(tmp_path):
    rig = make_rig(tmp_path)
    assert rig.build().ok
    changed = make_spec(LOCK, prelude=["import os", "import sys"])
    result = eb.build(changed, rig.ctx)
    assert result.ok and list(result.did) == ["wrapper"] and "import sys" in Path(rig.paths.launcher).read_text()


# ---------------------------------------------------------------- changes to source files

def confirming(answer, seen=None):
    def confirm(proposal):
        if seen is not None:
            seen.append(proposal)
        return answer
    return confirm


def patched_rig(tmp_path, answer=True, seen=None):
    return make_rig(tmp_path, spec_over={"patches": [PATCH]}, confirm=confirming(answer, seen))


def test_a_source_change_needs_a_yes_and_without_one_nothing_is_touched(tmp_path):
    rig = patched_rig(tmp_path, answer=False)
    result = rig.build()
    assert code_of(result) == "patch_declined" and result.error.detail == "fix-it"
    assert Path(rig.paths.source, PATCH["file"]).read_bytes() == GOOD_FILES[PATCH["file"]][0]
    assert not list(Path(rig.paths.source, "src/demo").glob("*" + eb.BACKUP_SUFFIX + "*")) and rig.doors.pip_runs == [] and not Path(rig.paths.venv).exists()


def test_the_person_is_shown_the_change_before_it_is_made(tmp_path):
    seen = []
    rig = patched_rig(tmp_path, seen=seen)
    rig.build()
    assert len(seen) == 1
    proposal = seen[0]
    assert proposal.env_id == "demo" and proposal.patch == rig.spec.patches[0] and proposal.path == rig.paths.source + "/" + PATCH["file"]
    assert "return 'old'" in proposal.before and "return 'old'" not in proposal.after and "return 'new'" in proposal.after
    assert "def main" in proposal.before and "def main" in proposal.after, "a few lines around it are shown"


def test_a_confirmed_change_keeps_the_original_first_and_records_both(tmp_path):
    rig = patched_rig(tmp_path)
    assert rig.build().ok
    target = Path(rig.paths.source, PATCH["file"])
    assert b"return 'new'" in target.read_bytes() and b"return 'old'" not in target.read_bytes()
    backup = Path(str(target) + eb.BACKUP_SUFFIX)
    assert backup.read_bytes() == GOOD_FILES[PATCH["file"]][0]
    entry = rig.record()["patches"]["fix-it"]
    assert entry["backup"] == backup.name and entry["before"] != entry["after"] and entry["file"] == PATCH["file"]
    assert eb.sha256_bytes(backup.read_bytes()) == entry["before"] and eb.sha256_file(str(target)) == entry["after"]


def test_the_change_is_made_before_anything_is_installed_so_a_no_costs_nothing(tmp_path):
    rig = patched_rig(tmp_path)
    result = rig.build()
    assert list(result.did)[:2] == ["source_unpack", "patches"] and list(result.did).index("patches") < list(result.did).index("venv")


def test_a_change_already_made_is_not_asked_again(tmp_path):
    seen = []
    rig = patched_rig(tmp_path, seen=seen)
    assert rig.build().ok and rig.build().ok
    assert len(seen) == 1 and "patches" in rig.build().kept


def test_a_changed_file_keeps_its_permissions(tmp_path):
    files = dict(GOOD_FILES)
    files[PATCH["file"]] = (files[PATCH["file"]][0], 0o755)
    rig = make_rig(tmp_path, spec_over={"patches": [PATCH]}, archive_files=files, confirm=confirming(True))
    assert rig.build().ok
    assert stat.S_IMODE(os.stat(Path(rig.paths.source, PATCH["file"])).st_mode) == 0o755


def test_a_file_someone_else_changed_after_the_change_is_never_overwritten(tmp_path):
    rig = patched_rig(tmp_path)
    assert rig.build().ok
    target = Path(rig.paths.source, PATCH["file"])
    target.write_text("their own edit\n")
    result = rig.build()
    assert code_of(result) == "patch_changed" and target.read_text() == "their own edit\n"


def test_a_file_put_back_to_the_original_is_changed_again_after_asking_and_the_first_backup_survives(tmp_path):
    seen = []
    rig = patched_rig(tmp_path, seen=seen)
    assert rig.build().ok
    target = Path(rig.paths.source, PATCH["file"])
    target.write_bytes(GOOD_FILES[PATCH["file"]][0])
    assert rig.build().ok and len(seen) == 2 and b"return 'new'" in target.read_bytes()
    backups = sorted(p.name for p in target.parent.glob(target.name + eb.BACKUP_SUFFIX + "*"))
    assert backups == [target.name + eb.BACKUP_SUFFIX, target.name + eb.BACKUP_SUFFIX + ".2"]


@pytest.mark.parametrize("old_text", ["not in the file", "n"])
def test_a_change_whose_text_is_missing_or_not_unique_is_refused_without_touching_the_file(tmp_path, old_text):
    patch = dict(PATCH, old=old_text, new="x")
    rig = make_rig(tmp_path, spec_over={"patches": [patch]}, confirm=confirming(True))
    result = rig.build()
    assert code_of(result) == "patch_changed" and Path(rig.paths.source, PATCH["file"]).read_bytes() == GOOD_FILES[PATCH["file"]][0]


def test_a_change_to_a_file_that_is_not_there_is_refused(tmp_path):
    patch = dict(PATCH, file="src/demo/nope.py")
    rig = make_rig(tmp_path, spec_over={"patches": [patch]}, confirm=confirming(True))
    assert code_of(rig.build()) == "patch_changed"


def test_a_change_to_a_file_that_is_not_text_is_refused(tmp_path):
    files = dict(GOOD_FILES)
    files["src/demo/train.py"] = (b"\xff\xfe\x00 binary", 0o644)
    rig = make_rig(tmp_path, spec_over={"patches": [PATCH]}, archive_files=files, confirm=confirming(True))
    assert code_of(rig.build()) == "patch_changed"


def test_a_file_that_was_edited_by_hand_but_still_holds_the_old_text_is_never_overwritten(tmp_path):
    rig = patched_rig(tmp_path)
    assert rig.build().ok
    target = Path(rig.paths.source, PATCH["file"])
    target.write_text(GOOD_FILES[PATCH["file"]][0].decode() + "# my own notes\n")          # the old line is back, with more beside it
    mine = target.read_bytes()
    result = rig.build()
    assert code_of(result) == "patch_changed" and target.read_bytes() == mine


def test_a_second_try_after_declining_one_change_does_not_ask_about_the_first_again(tmp_path):
    second = dict(PATCH, id="second", file="src/demo/__init__.py", old="VALUE = 1", new="VALUE = 2")
    asked = []
    answers = iter([True, False, True])

    def confirm(proposal):
        asked.append(proposal.patch.id)
        return next(answers)

    rig = make_rig(tmp_path, spec_over={"patches": [PATCH, second]}, confirm=confirm)
    assert code_of(rig.build()) == "patch_declined"
    assert rig.build().ok
    assert asked == ["fix-it", "second", "second"]
    assert b"VALUE = 2" in Path(rig.paths.source, "src/demo/__init__.py").read_bytes() and b"return 'new'" in Path(rig.paths.source, PATCH["file"]).read_bytes()


def test_two_changes_are_each_asked_for_and_each_can_be_declined_after_the_first_is_made(tmp_path):
    second = dict(PATCH, id="second", file="src/demo/__init__.py", old="VALUE = 1", new="VALUE = 2")
    answers = iter([True, False])
    rig = make_rig(tmp_path, spec_over={"patches": [PATCH, second]}, confirm=lambda p: next(answers))
    result = rig.build()
    assert code_of(result) == "patch_declined" and result.error.detail == "second"
    assert b"return 'new'" in Path(rig.paths.source, PATCH["file"]).read_bytes() and Path(rig.paths.source, "src/demo/__init__.py").read_bytes() == b"VALUE = 1\n"
    assert set(rig.record()["patches"]) == {"fix-it"}


# ---------------------------------------------------------------- looking without changing

def test_inspecting_a_missing_environment_makes_nothing(tmp_path):
    rig = make_rig(tmp_path)
    result = eb.inspect(rig.spec, rig.ctx)
    assert result.state == "absent" and result.env_dir == rig.env_dir and not rig.environments.exists()


def test_inspecting_a_good_one_says_ready_and_runs_no_command_that_writes(tmp_path):
    rig = make_rig(tmp_path)
    assert rig.build().ok
    rig.system.commands.clear()
    rig.doors.pip_runs.clear()
    assert eb.inspect(rig.spec, rig.ctx).state == "ready"
    assert rig.system.commands and all(argv[1] == "-c" and env == {"PYTHONDONTWRITEBYTECODE": "1"} for argv, cwd, env in rig.system.commands)
    assert not Path(rig.env_dir, eb.BUILD_LOCK_NAME).exists() and rig.doors.pip_runs == []


def test_inspecting_one_with_something_missing_lists_what_would_run_again(tmp_path):
    rig = make_rig(tmp_path)
    assert rig.build().ok
    Path(rig.paths.launcher).unlink()
    del rig.system.venv_dists["quart"]
    result = eb.inspect(rig.spec, rig.ctx)
    assert result.state == "needs_work" and result.stale == ("pip_lock", "wrapper") and not Path(rig.paths.launcher).exists()


def test_inspecting_after_a_failure_says_so(tmp_path):
    rig = make_rig(tmp_path)
    rig.doors.pip_fail["lock"] = 1
    rig.build()
    result = eb.inspect(rig.spec, rig.ctx)
    assert result.state == "failed" and result.stale[0] == "pip_lock"


@pytest.mark.parametrize("state", ["not_ours", "newer", "damaged"])
def test_inspecting_a_folder_that_is_not_usable_says_which_kind(tmp_path, state):
    rig = make_rig(tmp_path)
    target = Path(rig.env_dir)
    target.mkdir(parents=True)
    if state == "newer":
        (target / eb.RECORD_NAME).write_text(json.dumps({"schema": 99, "steps": {}, "patches": {}, "id": "demo", "fingerprint": "x"}))
    elif state == "damaged":
        (target / eb.RECORD_NAME).write_text("garbage")
    assert eb.inspect(rig.spec, rig.ctx).state == state


def test_inspecting_after_a_failed_check_never_says_ready_even_though_every_step_is_in_place(tmp_path):
    rig = make_rig(tmp_path)
    rig.system.bad_probe_codes = {"import os"}
    assert not rig.build().ok
    assert eb.inspect(rig.spec, rig.ctx).state == "needs_work"
    rig.system.bad_probe_codes = set()
    assert rig.build().ok and eb.inspect(rig.spec, rig.ctx).state == "ready"


def test_inspecting_a_folder_whose_record_belongs_to_another_environment_says_damaged(tmp_path):
    rig = make_rig(tmp_path)
    assert rig.build().ok
    data = rig.record()
    for field, value in (("id", "something-else"), ("fingerprint", "0" * 64)):
        Path(rig.paths.record).write_text(json.dumps(dict(data, **{field: value})))
        assert eb.inspect(rig.spec, rig.ctx).state == "damaged", field


def test_inspecting_something_that_cannot_be_built_gives_the_reason(tmp_path):
    rig = make_rig(tmp_path)
    rig.ctx.read_lock = lambda s: LOCK + b"x"
    result = eb.inspect(rig.spec, rig.ctx)
    assert result.state == "not_buildable" and result.error.code == "lock_changed"


def test_environment_dir_names_the_place_without_making_it(tmp_path):
    rig = make_rig(tmp_path)
    assert eb.environment_dir(rig.spec, rig.ctx).startswith(rig.ctx.home.environments + "/demo-") and not rig.environments.exists()


# ---------------------------------------------------------------- the pieces

def test_the_record_writer_reports_a_folder_it_cannot_write_to(tmp_path):
    with pytest.raises(eb.EnvError) as caught:
        eb._atomic_write(str(tmp_path / "missing" / "file"), b"x")
    assert caught.value.code == "write_failed"
    with pytest.raises(eb.EnvError):
        eb._save_record(str(tmp_path / "missing"), {"a": 1}, "now")


def test_the_atomic_write_leaves_no_temporary_file_and_replaces_in_one_step(tmp_path):
    target = tmp_path / "f"
    target.write_text("old")
    eb._atomic_write(str(target), b"new")
    assert target.read_text() == "new" and os.listdir(tmp_path) == ["f"] and stat.S_IMODE(target.stat().st_mode) == 0o600


def test_sha256_helpers_agree_and_a_missing_file_has_none(tmp_path):
    f = tmp_path / "f"
    f.write_bytes(b"abc")
    assert eb.sha256_file(str(f)) == eb.sha256_bytes(b"abc") == "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
    assert eb.sha256_file(str(tmp_path / "nope")) is None


def test_the_environment_paths_are_all_inside_the_environment_folder():
    paths = eb.EnvPaths("/x/env")
    assert {paths.venv, paths.python, paths.source, paths.launcher, paths.record, paths.log} <= {"/x/env/" + n for n in
                                                                                                 ("venv", "venv/bin/python", "source", "ack_run.py", "ack-env.json", "build.log")}


def test_every_error_code_in_the_list_can_be_told_apart_and_the_list_has_no_repeats():
    assert len(set(eb.ERROR_CODES)) == len(eb.ERROR_CODES) and all(c == c.lower() for c in eb.ERROR_CODES)
    assert "tail" in vars(eb.EnvError("busy", "x", ["a"])) and eb.EnvError("busy", "x", ["a"]).tail == ("a",)
    assert str(eb.EnvError("busy")) == "busy" and str(eb.EnvError("busy", "why")) == "busy: why"


def test_this_module_starts_no_program_of_its_own():
    source = Path(eb.__file__).read_text()
    for forbidden in ("subprocess", "os.system", "os.popen", "os.exec", "os.spawn", "urllib", "socket", "shell=True"):
        assert forbidden not in source, forbidden
