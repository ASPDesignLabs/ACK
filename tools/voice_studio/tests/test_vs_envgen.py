# SPDX-License-Identifier: GPL-3.0-or-later
"""Which copy of a set of programs is in use (plan task VS-6.6, decision P18): the note that says so, the builder's use of it, and the look that runs the self-test again without writing
anything. A rebuild is a second whole copy beside the first, so generation 0 must name every folder exactly as before and a higher one must name a new folder."""
import dataclasses
import json
import os
import stat
from pathlib import Path

import pytest

from vs_env_helpers import LOCK, make_rig
from voice_studio.core import envbuild as eb, envgen
from voice_studio.core.envspec import lock_digest
from voice_studio.core.paths import DataHome


@pytest.fixture
def rig(tmp_path):
    return make_rig(tmp_path)


def tree(root):
    found = {}
    for path in sorted(Path(root).rglob("*")):
        if path.is_file() and not path.is_symlink():
            found[str(path.relative_to(root))] = (path.read_bytes(), path.stat().st_mtime_ns)
    return found


# ---------------------------------------------------------------- the note

def test_with_no_note_every_set_of_programs_is_generation_zero(tmp_path):
    home = DataHome(str(tmp_path))
    assert envgen.read(home) == {} and envgen.generation_of(home, "studio") == 0


@pytest.mark.parametrize("text", ["", "{not json", "[]", '"x"', '{"generations": []}', '{"generations": "2"}', "null"])
def test_a_note_that_is_damaged_reads_as_no_rebuild_having_happened(tmp_path, text):
    home = DataHome(str(tmp_path))
    os.makedirs(home.state)
    Path(envgen.path_of(home)).write_text(text)
    assert envgen.read(home) == {}


def test_only_the_entries_that_can_be_used_are_read(tmp_path):
    home = DataHome(str(tmp_path))
    os.makedirs(home.state)
    entries = {"studio": 2, "training": 9999, "zero": 0, "negative": -1, "flag": True, "text": "3", "toobig": 10000, "Bad Name": 1, "": 1, "fraction": 1.5}
    Path(envgen.path_of(home)).write_text(json.dumps({"generations": entries}))
    assert envgen.read(home) == {"studio": 2, "training": 9999}


def test_a_generation_is_noted_for_the_owner_only_and_other_notes_are_kept(tmp_path):
    home = DataHome(str(tmp_path))
    envgen.write(home, "studio", 1)
    envgen.write(home, "training", 3)
    assert envgen.read(home) == {"studio": 1, "training": 3}
    assert stat.S_IMODE(os.stat(envgen.path_of(home)).st_mode) == 0o600 and stat.S_IMODE(os.stat(home.state).st_mode) & 0o077 == 0
    envgen.write(home, "studio", 2)
    assert envgen.read(home) == {"studio": 2, "training": 3} and envgen.generation_of(home, "studio") == 2
    assert json.loads(Path(envgen.path_of(home)).read_text())["schema"] == 1


def test_generation_zero_removes_the_note_for_that_set_and_a_nonsense_one_is_refused(tmp_path):
    home = DataHome(str(tmp_path))
    envgen.write(home, "studio", 2)
    envgen.write(home, "training", 1)
    envgen.write(home, "studio", 0)
    assert envgen.read(home) == {"training": 1}
    for bad in (("Studio", 1), ("", 1), ("studio", -1), ("studio", 10000)):
        with pytest.raises(ValueError):
            envgen.write(home, *bad)
    assert envgen.read(home) == {"training": 1}
    envgen.write(home, "studio", 9999)
    assert envgen.generation_of(home, "studio") == 9999


# ---------------------------------------------------------------- the name of the folder

def test_generation_zero_names_a_folder_as_it_always_was_and_each_higher_one_names_a_new_folder(rig):
    zero = eb.fingerprint(rig.spec, lock_digest(LOCK), rig.item, (3, 12))
    assert eb.fingerprint(rig.spec, lock_digest(LOCK), rig.item, (3, 12), 0) == zero
    names = {eb.fingerprint(rig.spec, lock_digest(LOCK), rig.item, (3, 12), n) for n in (0, 1, 2, 3)}
    assert len(names) == 4


def test_the_folder_follows_the_generation_the_context_names(rig):
    old = rig.env_dir
    again = dataclasses.replace(rig.ctx, generations=lambda home, env_id: 1)
    new = eb.environment_dir(rig.spec, again)
    assert new != old and os.path.dirname(new) == os.path.dirname(old) and os.path.basename(new).startswith("demo-")
    assert eb.environment_dir(rig.spec, dataclasses.replace(rig.ctx, generations=lambda home, env_id: 0)) == old
    assert eb.environment_dir(rig.spec, dataclasses.replace(rig.ctx, generations=lambda home, env_id: 2)) not in (old, new)


def test_the_builder_asks_for_the_generation_of_this_set_of_programs_by_name(rig):
    asked = []

    def generations(home, env_id):
        asked.append((home, env_id))
        return 0
    ctx = dataclasses.replace(rig.ctx, generations=generations)
    eb.environment_dir(rig.spec, ctx)
    eb.inspect(rig.spec, ctx)
    eb.build(rig.spec, ctx)
    assert asked and set(asked) == {(rig.ctx.home, "demo")}


def test_without_a_context_of_its_own_the_note_on_the_disk_decides_which_copy_is_in_use(rig):
    first = rig.env_dir
    envgen.write(rig.ctx.home, "demo", 1)
    assert rig.env_dir != first and eb.inspect(rig.spec, rig.ctx).state == "absent"
    envgen.write(rig.ctx.home, "demo", 0)
    assert rig.env_dir == first


def test_a_second_copy_is_built_beside_the_first_and_the_first_is_left_exactly_as_it_was(rig):
    assert rig.build().ok
    old_dir = rig.env_dir
    before = tree(old_dir)
    second = dataclasses.replace(rig.ctx, generations=lambda home, env_id: 1)
    result = eb.build(rig.spec, second)
    assert result.ok and result.env_dir != old_dir and list(result.did) and result.kept == ()
    assert tree(old_dir) == before, "the copy that is in use is not touched by the building of the next one"
    assert eb.inspect(rig.spec, second).state == "ready" and eb.inspect(rig.spec, rig.ctx).state == "ready"
    record = json.loads(Path(result.env_dir, eb.RECORD_NAME).read_text())
    assert record["state"] == "ready" and record["fingerprint"] == eb.fingerprint(rig.spec, lock_digest(LOCK), rig.item, (3, 12), 1)
    assert record["fingerprint"] != json.loads(Path(old_dir, eb.RECORD_NAME).read_text())["fingerprint"]


def test_a_second_copy_that_fails_leaves_the_first_ready_and_the_next_try_carries_on_in_the_same_folder(rig):
    assert rig.build().ok
    second = dataclasses.replace(rig.ctx, generations=lambda home, env_id: 1)
    rig.doors.pip_fail["lock"] = 1
    failed = eb.build(rig.spec, second)
    assert not failed.ok and eb.inspect(rig.spec, rig.ctx).state == "ready"
    assert eb.inspect(rig.spec, second).state == "failed"
    rig.doors.pip_fail.clear()
    again = eb.build(rig.spec, second)
    assert again.ok and again.env_dir == failed.env_dir and "venv" in again.kept


# ---------------------------------------------------------------- the self-test, run again and changing nothing

def test_the_probes_of_a_finished_environment_pass_and_the_one_that_needs_a_card_is_skipped_without_one(rig):
    assert rig.build().ok
    report = eb.probe(rig.spec, rig.ctx, rig.env_dir)
    assert report == eb.ProbeReport(True, "", "", (), ("card",))


def test_with_a_card_every_probe_is_tried(rig):
    assert rig.build().ok
    rig.system.probe_runs.clear()
    report = eb.probe(rig.spec, dataclasses.replace(rig.ctx, gpu_ok=True), rig.env_dir)
    assert report.ok and report.skipped == () and [code for code, _env, _cwd in rig.system.probe_runs] == ["import os", "import sys"]


def test_a_probe_that_fails_is_named_with_the_end_of_what_it_printed(rig):
    assert rig.build().ok
    rig.system.bad_probe_codes = {"import os"}
    report = eb.probe(rig.spec, rig.ctx, rig.env_dir)
    assert not report.ok and report.code == "self_test_failed" and report.detail == "imports" and "ImportError: nothing called that" in report.tail


def test_a_launcher_that_does_not_start_is_named(rig):
    assert rig.build().ok
    rig.system.fail_launcher = True
    report = eb.probe(rig.spec, rig.ctx, rig.env_dir)
    assert (report.ok, report.code, report.detail) == (False, "launcher_failed", "exit 1") and "boom" in report.tail[-1]


def test_looking_changes_nothing_in_the_environment_and_says_nothing_to_the_builders_screens(rig):
    assert rig.build().ok
    before = tree(rig.env_dir)
    rig.events.clear()
    rig.system.bad_probe_codes = {"import sys"}
    eb.probe(rig.spec, dataclasses.replace(rig.ctx, gpu_ok=True), rig.env_dir)
    rig.system.bad_probe_codes = set()
    eb.probe(rig.spec, rig.ctx, rig.env_dir)
    assert tree(rig.env_dir) == before and rig.events == []


def test_the_probes_run_offline_and_leave_no_compiled_files(rig):
    assert rig.build().ok
    rig.system.probe_runs.clear()
    eb.probe(rig.spec, rig.ctx, rig.env_dir)
    (code, env, cwd), = rig.system.probe_runs
    assert env["PYTHONDONTWRITEBYTECODE"] == "1" and env["HF_HUB_OFFLINE"] == "1" and cwd == rig.env_dir


def test_the_note_is_in_the_file_called_environments_json_under_the_tools_state_folder(tmp_path):
    home = DataHome(str(tmp_path))
    assert envgen.FILE == "environments.json" and envgen.path_of(home) == home.state + "/environments.json"


def test_a_set_that_goes_back_to_generation_zero_leaves_no_entry_in_the_file(tmp_path):
    home = DataHome(str(tmp_path))
    envgen.write(home, "studio", 1)
    envgen.write(home, "training", 2)
    envgen.write(home, "studio", 0)
    assert json.loads(Path(envgen.path_of(home)).read_text())["generations"] == {"training": 2}


def test_generation_zero_names_a_folder_exactly_as_it_was_named_before_generations_existed(rig):
    """The name of a folder before a generation was part of it, written out again here: a computer that has never rebuilt must find its programs where it left them."""
    import hashlib
    spec, item = rig.spec, rig.item
    data = {"builder": eb.BUILDER_VERSION, "id": spec.id, "python": "3.12", "lock": lock_digest(LOCK), "source": item.sha256, "install": bool(spec.source and spec.source.install),
            "dist": spec.source.dist if spec.source else None, "native": spec.source.native_build if spec.source else None,
            "patches": [[p.id, p.file, eb.sha256_bytes(p.old.encode()), eb.sha256_bytes(p.new.encode())] for p in spec.patches]}
    if spec.native is not None:
        data["native_part"] = [spec.native.sha256, spec.native.module, spec.native.into]
    before = hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()
    assert eb.fingerprint(spec, lock_digest(LOCK), item, (3, 12)) == before == eb.fingerprint(spec, lock_digest(LOCK), item, (3, 12), 0)
    assert eb.fingerprint(spec, lock_digest(LOCK), item, (3, 12), 1) != before


def test_a_failed_probe_keeps_the_lines_it_printed_up_to_the_limit(rig):
    assert rig.build().ok
    rig.system.bad_probe_codes = {"import os"}
    report = eb.probe(rig.spec, rig.ctx, rig.env_dir)
    assert report.tail == ("Linux", "Traceback", "ImportError: nothing called that"), "the launcher's own line, then what the failed probe printed"


def test_the_launcher_is_run_offline_and_without_leaving_compiled_files(rig):
    assert rig.build().ok
    rig.system.launcher_runs.clear()
    eb.probe(rig.spec, rig.ctx, rig.env_dir)
    (argv, env), = rig.system.launcher_runs
    assert env["PYTHONDONTWRITEBYTECODE"] == "1" and env["HF_HUB_OFFLINE"] == "1" and argv[-1] == "platform"


def test_a_launcher_that_cannot_be_run_at_all_is_named_as_that(rig):
    assert rig.build().ok
    real = rig.system.run

    def run(argv, timeout=15.0, cwd=None, env=None):
        return None if len(argv) >= 2 and str(argv[1]).endswith("ack_run.py") else real(argv, timeout, cwd, env)
    rig.system.run = run
    report = eb.probe(rig.spec, rig.ctx, rig.env_dir)
    assert (report.ok, report.code, report.detail, report.tail) == (False, "launcher_failed", "could not run", ())

