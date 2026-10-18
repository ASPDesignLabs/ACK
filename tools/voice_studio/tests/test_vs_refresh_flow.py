# SPDX-License-Identifier: GPL-3.0-or-later
"""The terminal front for refreshing the tool (plan task VS-6.6): what a check says, what a repair shows and asks and does, how a second copy is built and switched to, and the old copies.
The flows are the real code, on the builder tests' stand-in for the computer and the network, with a real downloader serving made-up bytes."""
import json
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path

import pytest

from dataclasses import replace
from types import SimpleNamespace

from vs_refresh_helpers import CAT, SPEECH, VOICE_BYTES, RefreshRig, TermIO, ticking
from vs_rounds_helpers import fake_job
from vs_startvoice_helpers import implies_permission, leaked_keys
from voice_studio.core import envbuild as eb, envfind, envgen, projectbackup as pb, refresh as rf, refresh_flow as rff
from voice_studio.core.describe import error_text
from voice_studio.core.project import create_project
from voice_studio.core.paths import ProjectPaths

NOW = datetime(2026, 10, 17, 9, 30, 0, tzinfo=timezone.utc)


@pytest.fixture
def rig(tmp_path):
    return RefreshRig(tmp_path)


def run(rig, *argv, answers=(), interactive=True):
    code, io = rig.run(*argv, answers=answers, interactive=interactive, now=NOW)
    assert leaked_keys(io.text + "\n".join(io.prompts)) == [], "a catalog key was printed instead of words"
    assert implies_permission(io.text) == [], "something printed says or implies that use is permitted"
    return code, io


def tree(root):
    found = {}
    for path in sorted(Path(root).rglob("*")):
        if path.is_file() and not path.is_symlink():
            found[str(path.relative_to(root))] = (path.read_bytes(), path.stat().st_mtime_ns)
    return found


def damage_voice(rig):
    rig.voice_path().write_bytes(b"z" * len(VOICE_BYTES))


def break_window_note(rig):
    path = Path(rig.home.window_file)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("garbage")
    return path


# ---------------------------------------------------------------- help

def test_no_command_and_help_list_the_four_commands_and_the_options(rig):
    for argv in ((), ("help",), ("--help",), ("-h",)):
        code, io = run(rig, *argv)
        assert code == 0 and io.prompts == []
        for part in ("check [--quick]:", "repair [--quick] [--yes]:", "rebuild [--programs name] [--yes]:", "older [--remove] [--yes]:", "No project, recording, round, finished voice or backup is ever touched."):
            assert part in io.text, part


def test_an_unknown_command_is_named_and_nothing_is_done(rig):
    before = tree(rig.home.root)
    code, io = run(rig, "frobnicate")
    assert code == 2 and "frobnicate" in io.text and tree(rig.home.root) == before


def test_the_options_each_command_publishes_are_the_options_it_accepts(rig):
    assert set(rff.OPTIONS) == set(rff.COMMANDS) - {"help"}
    for command, options in rff.OPTIONS.items():
        for option in options:
            args = [option, "demo"] if option == "--programs" else [option]
            if option == "--yes" or option == "-y":
                continue                                                           # it answers a question, which these commands may never reach
            code, io = run(rig, command, *args, answers=["no", "no"])
            assert "is not something this command knows" not in io.text, (command, option)
        code, io = run(rig, command, "--nonsense")
        assert code == 2 and "--nonsense" in io.text, command


def test_the_published_options_are_exactly_these():
    assert rff.OPTIONS == {"check": {"--quick"}, "repair": {"--quick", "--yes", "-y"}, "rebuild": {"--yes", "-y", "--programs"}, "older": {"--remove", "--yes", "-y"}}


def test_a_word_where_none_is_wanted_is_refused_and_nothing_is_done(rig):
    for command in ("check", "repair", "older"):
        code, io = run(rig, command, "extra")
        assert code == 2 and io.prompts == []


# ---------------------------------------------------------------- check

def test_a_check_of_everything_in_order_says_each_thing_and_that_all_is_in_order(rig):
    before = tree(rig.home.root)
    code, io = run(rig, "check")
    assert code == 0 and io.prompts == [] and tree(rig.home.root) == before
    assert io.lines[:2] == ["ACK Voice Studio: refresh", "Looking at the programs, the downloaded files and the tool's own notes. This changes nothing."]
    assert "  [ok] The programs called demo: Every step is in place and its own check passed." in io.lines
    assert "  [ok] The listening model: It is here and exactly what was agreed." in io.lines
    assert "  [ok] The starting voice Mike: It is here and exactly what was agreed." in io.lines
    assert "  [ok] The note of what you agreed to download: It can be read." in io.lines
    assert "  [not here] The note of the window's choices: There is none yet. Nothing is wrong." in io.lines
    assert io.lines[-1] == "Everything that is here is in order." and "needs attention" not in io.text and "need attention" not in io.text


def test_it_says_what_it_is_looking_at_before_the_slow_things_and_nothing_before_the_notes(rig):
    code, io = run(rig, "check")
    assert [l for l in io.lines if l.startswith("  Looking at")] == ["  Looking at the programs called demo.", "  Looking at the listening model.", "  Looking at the starting voice Mike."]
    assert io.lines.index("  Looking at the programs called demo.") < io.lines.index("  [ok] The programs called demo: Every step is in place and its own check passed.")


def test_a_quick_check_does_not_run_the_programs_own_check_and_does_not_announce_them(rig):
    rig.system.probe_runs.clear()
    code, io = run(rig, "check", "--quick")
    assert code == 0 and rig.system.probe_runs == [] and "  Looking at the programs called demo." not in io.lines and "  Looking at the listening model." in io.lines


def test_a_check_names_each_problem_counts_them_and_says_what_to_run(rig):
    rig.system.bad_probe_codes = {"import os"}
    damage_voice(rig)
    break_window_note(rig)
    code, io = run(rig, "check")
    assert code == 1
    assert "  [problem] The programs called demo: Its own check failed at this step: imports. Some of its files may be damaged." in io.lines
    assert "  [problem] The starting voice Mike: The file is not what was agreed." in io.lines and "  [problem] The note of the window's choices: It cannot be read." in io.lines
    assert "3 things need attention." in io.lines
    assert "To mend what can be mended, run: python3 -m voice_studio.refresh repair" in io.lines
    assert "To build a fresh copy of the programs called demo beside the old one, run: python3 -m voice_studio.refresh rebuild --programs demo" in io.lines


def test_one_problem_is_counted_as_one_and_a_thing_nobody_can_mend_here_gets_no_command(tmp_path):
    rig = RefreshRig(tmp_path, built=False, system_kw={"python": (3, 9, 0)})
    code, io = run(rig, "check")
    assert code == 1 and "1 thing needs attention." in io.lines and not any(l.startswith("To ") for l in io.lines)
    assert "  [problem] The programs called demo: It cannot be looked at: The system software that runs this tool is too old for this part. Update Ubuntu, then try again." in io.lines


def test_programs_that_are_not_set_up_are_not_a_problem_but_the_way_to_set_them_up_is_said(tmp_path):
    rig = RefreshRig(tmp_path, built=False)
    code, io = run(rig, "check")
    assert code == 0 and io.lines[-2] == "Everything that is here is in order." and io.lines[-1] == "To set up the programs called demo, run: python3 -m voice_studio"
    assert "  [not here] The programs called demo: Not set up yet." in io.lines


def test_a_note_that_cannot_be_read_alone_is_followed_by_the_repair_command(rig):
    break_window_note(rig)
    code, io = run(rig, "check")
    assert code == 1 and io.lines[-2:] == ["1 thing needs attention.", "To mend what can be mended, run: python3 -m voice_studio.refresh repair"]


def test_a_problem_and_programs_not_set_up_are_each_followed_by_their_own_command(tmp_path):
    rig = RefreshRig(tmp_path, built=False)
    damage_voice(rig)
    code, io = run(rig, "check")
    assert code == 1 and io.lines[-3:] == ["1 thing needs attention.", "To mend what can be mended, run: python3 -m voice_studio.refresh repair", "To set up the programs called demo, run: python3 -m voice_studio"]


def test_a_check_changes_nothing_even_when_everything_is_broken(rig):
    rig.system.bad_probe_codes = {"import os"}
    damage_voice(rig)
    break_window_note(rig)
    shutil.rmtree(rig.env.paths.venv)
    before = tree(rig.home.root)
    run(rig, "check")
    run(rig, "check", "--quick")
    assert tree(rig.home.root) == before


# ---------------------------------------------------------------- repair

def test_a_repair_with_nothing_wrong_says_so_and_asks_nothing(rig):
    code, io = run(rig, "repair")
    assert code == 0 and io.prompts == [] and "Nothing needs repair." in io.lines


def test_a_problem_a_repair_cannot_mend_is_named_with_the_command_that_can_and_nothing_is_asked(rig):
    rig.system.bad_probe_codes = {"import os"}
    code, io = run(rig, "repair")
    assert code == 1 and io.prompts == [] and "A repair cannot mend this." in io.lines
    assert "To build a fresh copy of the programs called demo beside the old one, run: python3 -m voice_studio.refresh rebuild --programs demo" in io.lines
    assert "To mend what can be mended, run: python3 -m voice_studio.refresh repair" not in io.lines


def test_the_plan_is_shown_before_the_one_question_and_a_no_changes_nothing(rig):
    damage_voice(rig)
    path = break_window_note(rig)
    before = tree(rig.home.root)
    code, io = run(rig, "repair", answers=["no"])
    assert code == 2 and io.prompts == ["Repair these now? Type yes to go on. "] and "Nothing was done." in io.lines and tree(rig.home.root) == before
    ask = io.events.index(("ask", io.prompts[0]))
    said = [t for kind, t in io.events[:ask] if kind == "say"]
    assert "A repair would do this:" in said
    assert "  Fetch the starting voice Mike again. The file in the way is replaced only after the new one has been checked." in said
    assert "  Set the note of the window's choices aside under another name, beside itself. It is not deleted." in said
    assert path.read_text() == "garbage"


def test_with_nobody_to_ask_a_repair_does_nothing(rig):
    damage_voice(rig)
    before = tree(rig.home.root)
    code, io = run(rig, "repair", interactive=False)
    assert code == 2 and io.prompts == [] and "There was nobody to ask. To say yes on the command line, add --yes. Nothing was done." in io.lines and tree(rig.home.root) == before


def test_a_note_that_cannot_be_read_is_set_aside_beside_itself_on_a_yes(rig):
    path = break_window_note(rig)
    code, io = run(rig, "repair", answers=["yes"])
    moved = str(path) + ".damaged-20261017-093000"
    assert code == 0 and not path.exists() and Path(moved).read_text() == "garbage"
    assert "  The note of the window's choices was set aside as %s." % moved in io.lines and "Looking again." in io.lines and io.lines[-1] == "Everything that is here is in order."


def test_a_damaged_download_is_fetched_again_and_replaced_only_by_the_checked_file(rig):
    damage_voice(rig)
    code, io = run(rig, "repair", "--yes")
    assert code == 0 and io.prompts == [] and rig.voice_path().read_bytes() == VOICE_BYTES and rig.fetched == ["voice-mike"]
    assert "  Fetching the starting voice Mike." in io.lines and "  The starting voice Mike is fetched again and checked." in io.lines


def test_a_download_that_cannot_be_fetched_leaves_the_file_that_was_there_and_says_so(rig):
    damage_voice(rig)
    import urllib.error
    rig.opener.fail_with = urllib.error.HTTPError("https://huggingface.co/x", 503, "unavailable", {}, None)
    code, io = run(rig, "repair", "--yes")
    assert code == 1 and rig.voice_path().read_bytes() == b"z" * len(VOICE_BYTES)
    assert "  The starting voice Mike could not be fetched again. The file that was there is as it was." in io.lines
    assert not [l for l in io.lines if "is fetched again" in l]
    parts = error_text(CAT, "fetch", "connection_lost")
    start = io.lines.index("  The starting voice Mike could not be fetched again. The file that was there is as it was.")
    assert len({parts.what, parts.changed, parts.next}) == 3 and io.lines[start + 1:start + 4] == ["  " + parts.what, "  " + parts.changed, "  " + parts.next]


def test_a_download_with_no_saved_agreement_is_not_fetched(rig):
    damage_voice(rig)
    Path(rig.home.consent_file).unlink()
    code, io = run(rig, "repair", "--yes")
    assert code == 1 and rig.opener.calls == [] and "The download was not started because it has not been agreed to yet." in io.text
    assert rig.voice_path().read_bytes() == b"z" * len(VOICE_BYTES)


def test_only_the_listening_files_that_are_not_right_are_fetched_again(tmp_path):
    rig = RefreshRig(tmp_path, speech=False)
    rig.put_speech(["a.bin"])
    code, io = run(rig, "repair", "--yes")
    folder = Path(envfind.speech_places(rig.home)[0])
    assert code == 0 and rig.fetched == ["speech-b.bin"] and (folder / "b.bin").read_bytes() == SPEECH["b.bin"] and (folder / "a.bin").read_bytes() == SPEECH["a.bin"]


def test_a_step_that_was_lost_is_finished_by_the_builder_which_asks_for_itself(rig):
    shutil.rmtree(rig.env.paths.venv)
    code, io = run(rig, "repair", answers=["yes", "yes"])
    assert code == 0 and io.prompts[0] == "Repair these now? Type yes to go on. "
    assert any("Finish the programs called demo:" in l for l in io.lines)
    assert eb.inspect(rig.spec, rig.env.ctx).state == "ready" and io.lines[-1] == "Everything that is here is in order."


def test_a_builder_that_goes_wrong_stops_the_repair_and_says_so(rig):
    shutil.rmtree(rig.env.paths.venv)
    rig.env.doors.pip_fail["lock"] = 1
    code, io = run(rig, "repair", answers=["yes", "yes"])
    assert code == 1 and eb.inspect(rig.spec, rig.env.ctx).state == "failed"
    assert "  The programs this part needs could not be installed." in io.lines and "Looking again." in io.lines and "1 thing needs attention." in io.lines
    assert "  [problem] The programs called demo: The last attempt to set it up did not finish. These steps would run again: Installing the programs this part needs, Building the part made for this computer." in io.lines


def test_everything_that_can_be_mended_is_mended_in_one_go_and_what_cannot_is_still_named(rig):
    damage_voice(rig)
    break_window_note(rig)
    shutil.rmtree(rig.env.paths.venv)
    code, io = run(rig, "repair", answers=["yes", "yes"])
    assert code == 0 and rig.voice_path().read_bytes() == VOICE_BYTES and not Path(rig.home.window_file).exists() and eb.inspect(rig.spec, rig.env.ctx).state == "ready"
    ask = io.events.index(("ask", io.prompts[0]))
    said = [t for kind, t in io.events[:ask] if kind == "say"]
    assert io.prompts[0] == "Repair these now? Type yes to go on. " and "A repair would do this:" in said
    assert [l for l in said if l.startswith("  ") and not l.startswith("  Looking")] == [
        "  Finish the programs called demo: Creating a separate space for the programs, Installing the programs this part needs, Building the part made for this computer. The next screen shows what it will download and asks again.",
        "  Fetch the starting voice Mike again. The file in the way is replaced only after the new one has been checked.",
        "  Set the note of the window's choices aside under another name, beside itself. It is not deleted."]
    assert io.lines[-1] == "Everything that is here is in order."


def test_a_problem_found_beside_work_is_listed_as_not_mended(rig):
    damage_voice(rig)
    rig.system.bad_probe_codes = {"import os"}
    code, io = run(rig, "repair", "--yes")
    assert code == 1 and "A repair does not mend these:" in io.lines and rig.voice_path().read_bytes() == VOICE_BYTES
    assert io.lines[-2:] == ["1 thing needs attention.", "To build a fresh copy of the programs called demo beside the old one, run: python3 -m voice_studio.refresh rebuild --programs demo"]


# ---------------------------------------------------------------- rebuild

def test_a_rebuild_of_programs_that_are_not_there_says_to_set_them_up_and_does_nothing(tmp_path):
    rig = RefreshRig(tmp_path, built=False)
    code, io = run(rig, "rebuild")
    assert code == 2 and "No programs are set up yet, so there is nothing to build again. To set them up, run: python3 -m voice_studio" in io.lines and io.prompts == []


def test_a_name_that_is_no_set_of_programs_is_refused_with_the_choices(rig):
    code, io = run(rig, "rebuild", "--programs", "nonsense")
    assert code == 2 and "There are no programs called nonsense. The choices are: demo." in io.lines and io.prompts == [] and envgen.read(rig.home) == {}


def test_the_rebuild_says_how_it_works_and_what_it_leaves_alone_before_it_asks(rig):
    code, io = run(rig, "rebuild", answers=["no"])
    ask = io.events.index(("ask", io.prompts[0]))
    said = [t for kind, t in io.events[:ask] if kind == "say"]
    assert code == 2 and said[1:5] == ["A rebuild of the programs called demo would work like this:",
                                       "  It builds a second, whole copy beside the one in use, from the same list as before.",
                                       "  The copy in use keeps working until the new one is built and its own check has passed. If anything fails, nothing changes.",
                                       "  No project, recording, round, finished voice or backup is touched."]
    assert io.prompts == ["Download and set it up now? Type yes to go on. "] and envgen.read(rig.home) == {}
    assert len(os.listdir(rig.home.environments)) == 1


def test_the_projects_without_an_up_to_date_backup_are_named_with_the_command(rig):
    create_project(rig.home.projects, "Anna", "own")
    create_project(rig.home.projects, "Ben", "own")
    paths = ProjectPaths(rig.home.projects + "/ben")
    made = pb.create(pb.plan_backup(paths, rig.home, "ben", rig.home.root + "-b", 10 ** 12), paths, NOW)
    pb.record_backup(rig.home, made, "ben", rig.home.root + "-b")
    code, io = run(rig, "rebuild", answers=["no"])
    assert "These projects have no up-to-date backup. A rebuild does not touch them, but a backup costs little:" in io.lines
    assert "  Anna has never been backed up. To back it up, run: python3 -m voice_studio.backup now --project anna" in io.lines and not any("Ben" in l for l in io.lines)


def test_no_backup_is_mentioned_when_every_project_is_backed_up_or_there_is_none(rig):
    code, io = run(rig, "rebuild", answers=["no"])
    assert "These projects have no up-to-date backup" not in io.text and "has never been backed up" not in io.text


def test_a_yes_builds_a_second_copy_beside_the_first_and_switches_to_it_only_when_it_is_ready(rig):
    old = rig.env.env_dir
    before = tree(old)
    code, io = run(rig, "rebuild", answers=["yes", "no"])
    new = eb.environment_dir(rig.spec, rig.env.ctx)
    assert code == 0 and envgen.read(rig.home) == {"demo": 1} and new != old and tree(old) == before
    assert eb.inspect(rig.spec, rig.env.ctx).state == "ready" and os.path.isdir(old) and os.path.isdir(new)
    switched = io.lines.index("The new copy of the programs called demo is now the one in use. The old copy is still on the disk.")
    assert switched > max(i for i, l in enumerate(io.lines) if l.startswith("Ready, after "))


def test_the_old_copy_is_offered_for_removal_and_a_no_keeps_it(rig):
    old = rig.env.env_dir
    code, io = run(rig, "rebuild", answers=["yes", "no"])
    assert code == 0 and os.path.isdir(old)
    assert any(l.startswith("1 old copy of the programs is on the disk:") for l in io.lines) and "The old copy was kept. To remove it later, run: python3 -m voice_studio.refresh older --remove" in io.lines
    assert io.prompts[-1].startswith("Remove this old copy, about ") and io.prompts[-1].endswith("now? Type yes to delete it. ")
    assert io.prompts[-1] == "Remove this old copy, about %s, now? Type yes to delete it. " % together(io) and not together(io).startswith("0 ")


def test_a_yes_to_the_offer_removes_the_old_copy_and_only_that(rig):
    old = rig.env.env_dir
    code, io = run(rig, "rebuild", answers=["yes", "yes"])
    new = eb.environment_dir(rig.spec, rig.env.ctx)
    assert code == 0 and not os.path.exists(old) and os.path.isdir(new) and any(l.startswith("Done. 1 old copy was removed.") for l in io.lines)
    assert eb.inspect(rig.spec, rig.env.ctx).state == "ready"


def test_dash_dash_yes_builds_without_the_question_but_does_not_answer_the_offer_to_remove(rig):
    old = rig.env.env_dir
    code, io = run(rig, "rebuild", "--yes")
    assert code == 0 and os.path.isdir(old) and envgen.read(rig.home) == {"demo": 1}
    assert io.prompts == [io.prompts[-1]] and io.prompts[-1].startswith("Remove this old copy") and "The old copy was kept." in io.text


def test_with_nobody_to_ask_nothing_is_built_and_nothing_is_switched(rig):
    code, io = run(rig, "rebuild", interactive=False)
    assert code == 2 and envgen.read(rig.home) == {} and len(os.listdir(rig.home.environments)) == 1


def test_a_build_that_fails_leaves_the_old_copy_in_use_and_the_next_try_carries_on(rig):
    old = rig.env.env_dir
    rig.env.doors.pip_fail["lock"] = 1
    code, io = run(rig, "rebuild", answers=["yes"])
    assert code == 1 and envgen.read(rig.home) == {} and "The new copy of the programs called demo is not in use. The copy that was in use still is." in io.lines
    assert eb.environment_dir(rig.spec, rig.env.ctx) == old and eb.inspect(rig.spec, rig.env.ctx).state == "ready"
    folders = sorted(os.listdir(rig.home.environments))
    assert len(folders) == 2
    rig.env.doors.pip_fail.clear()
    code, io = run(rig, "rebuild", answers=["no"])                                  # the unfinished copy is carried on without asking again: the one answer is to the offer to remove the old one
    assert code == 0 and envgen.read(rig.home) == {"demo": 1} and sorted(os.listdir(rig.home.environments)) == folders, "the unfinished copy is carried on, in its own folder"
    assert "You already said yes to this, so it carries on from where it stopped and does not ask again. Press Ctrl+C to stop." in io.lines
    assert io.prompts[0].startswith("Remove this old copy")


def test_a_switch_that_cannot_be_noted_is_said_and_the_old_copy_stays_in_use(rig, monkeypatch):
    old = rig.env.env_dir

    def broken(home, env_id, generation):
        raise OSError(28, "No space left on device")
    monkeypatch.setattr(envgen, "write", broken)
    code, io = run(rig, "rebuild", answers=["yes", "no"])
    assert code == 1 and "The new copy is built, but it could not be marked as the one to use." in io.lines and "The old copy is still the one in use, and nothing was removed." in io.lines
    assert "  Technical detail: No space left on device" in io.lines and not any(l.startswith("  Technical detail") and l != "  Technical detail: No space left on device" for l in io.lines)
    assert eb.environment_dir(rig.spec, rig.env.ctx) == old and envgen.read(rig.home) == {}


def test_a_second_rebuild_makes_the_third_copy_and_both_older_ones_are_offered(rig):
    run(rig, "rebuild", answers=["yes", "no"])
    code, io = run(rig, "rebuild", answers=["yes", "no"])
    assert code == 0 and envgen.read(rig.home) == {"demo": 2} and any(l.startswith("2 old copies of the programs are on the disk:") for l in io.lines)
    assert io.prompts[-1].startswith("Remove these 2 old copies, about ")


def test_after_a_rebuild_a_check_looks_at_the_new_copy(rig):
    run(rig, "rebuild", answers=["yes", "no"])
    code, io = run(rig, "check")
    assert code == 0 and "  [ok] The programs called demo: Every step is in place and its own check passed." in io.lines and "  [ok] The note of which copy of the programs is in use: It can be read." in io.lines


def test_no_copy_higher_than_the_last_can_be_made(rig):
    from voice_studio.core import refresh as rf
    assert eb.build(rig.spec, rf.with_generation(rig.env.ctx, "demo", envgen.MAX_GENERATION)).ok
    envgen.write(rig.home, "demo", envgen.MAX_GENERATION)
    code, io = run(rig, "rebuild", answers=["yes"])
    assert code == 1 and "There is no higher number to give to another copy of these programs." in io.lines


def test_a_rebuild_touches_no_project(rig):
    create_project(rig.home.projects, "Anna", "own")
    keep = Path(rig.home.projects, "anna", "recordings")
    keep.mkdir(parents=True, exist_ok=True)
    (keep / "x.wav").write_bytes(b"RIFF")
    before = tree(rig.home.projects)
    run(rig, "rebuild", answers=["yes", "yes"])
    assert tree(rig.home.projects) == before


# ---------------------------------------------------------------- older

def copies(rig, count):
    for _ in range(count):
        run(rig, "rebuild", "--yes")


def together(io):
    """The size the list says all the old copies take together."""
    line = next(l for l in io.lines if l.startswith("Together they take "))
    return line[len("Together they take "):].split(". They can be built again")[0]


def test_with_no_old_copy_it_says_so(rig):
    code, io = run(rig, "older")
    assert code == 0 and "No old copies of the programs are on the disk." in io.lines and io.prompts == [] and "left alone" not in io.text


def test_folders_it_did_not_make_are_counted_and_left_alone(rig):
    (Path(rig.home.environments) / "somebody-elses").mkdir()
    code, io = run(rig, "older")
    assert code == 0 and "1 other folder there was left alone, because this tool did not make it." in io.lines and (Path(rig.home.environments) / "somebody-elses").is_dir()
    (Path(rig.home.environments) / "another").mkdir()
    assert "2 other folders there were left alone, because this tool did not make them." in run(rig, "older")[1].lines


def test_the_old_copies_are_listed_with_size_and_state_and_how_to_remove_them(rig):
    old = rig.env.env_dir
    copies(rig, 1)
    before = tree(rig.home.root)
    code, io = run(rig, "older")
    assert code == 0 and tree(rig.home.root) == before and io.prompts == []
    assert "1 old copy of the programs is on the disk:" in io.lines
    assert any(l.startswith("  %s: " % old) and l.endswith(", it was complete") for l in io.lines)
    assert any(l.startswith("Together they take ") and l.endswith("They can be built again, and nothing of yours is in them.") for l in io.lines)
    assert "To remove them, run: python3 -m voice_studio.refresh older --remove" in io.lines


def test_the_states_of_the_old_copies_are_in_words(rig):
    old = Path(rig.env.env_dir)
    copies(rig, 1)
    for state, words in (("building", "it was never finished"), ("failed", "its last attempt failed")):
        record = json.loads((old / eb.RECORD_NAME).read_text())
        record["state"] = state
        (old / eb.RECORD_NAME).write_text(json.dumps(record))
        assert any(l.endswith(", " + words) for l in run(rig, "older")[1].lines), state


def test_removing_asks_and_a_no_removes_nothing(rig):
    old = rig.env.env_dir
    copies(rig, 1)
    code, io = run(rig, "older", "--remove", answers=["no"])
    assert code == 2 and os.path.isdir(old) and "Nothing was done." in io.lines and io.prompts[0].startswith("Remove this old copy, about ")
    assert io.prompts[0] == "Remove this old copy, about %s, now? Type yes to delete it. " % together(io) and not together(io).startswith("0 ") and "left alone" not in io.text


def test_a_yes_removes_the_old_copy_and_says_how_much_room_came_back(rig):
    old = rig.env.env_dir
    copies(rig, 1)
    code, io = run(rig, "older", "--remove", answers=["yes"])
    assert code == 0 and not os.path.exists(old) and any(l.startswith("Done. 1 old copy was removed. About ") and l.endswith("is free again.") for l in io.lines)
    assert "No old copies of the programs are on the disk." in run(rig, "older")[1].lines and "These could not be removed:" not in io.text


def test_dash_dash_yes_answers_the_question_of_an_older_remove(rig):
    old = rig.env.env_dir
    copies(rig, 1)
    code, io = run(rig, "older", "--remove", "--yes")
    assert code == 0 and io.prompts == [] and not os.path.exists(old)


def test_with_nobody_to_ask_nothing_is_removed(rig):
    old = rig.env.env_dir
    copies(rig, 1)
    code, io = run(rig, "older", "--remove", interactive=False)
    assert code == 2 and os.path.isdir(old) and "There was nobody to ask. To say yes on the command line, add --yes. Nothing was done." in io.lines


def test_a_running_task_stops_the_removal_in_three_parts(rig):
    old = rig.env.env_dir
    copies(rig, 1)
    os.makedirs(rig.home.jobs, exist_ok=True)
    fake_job(rig.home.jobs, ["x"], "running", project="voice-check")
    code, io = run(rig, "older", "--remove", "--yes")
    assert code == 1 and os.path.isdir(old)
    assert io.lines[-3:] == ["A task is running, and it may be using one of the old copies.", "Nothing was removed.", "Wait for the task to finish, or stop it, then try again."]


def test_only_ten_old_copies_are_listed_and_all_are_counted(rig):
    copies(rig, 12)
    code, io = run(rig, "older")
    assert "12 old copies of the programs are on the disk:" in io.lines and len([l for l in io.lines if l.startswith("  " + rig.home.environments)]) == 10 and "  And 2 more." in io.lines


def test_a_folder_that_could_not_be_removed_is_listed_and_the_command_fails(rig, monkeypatch):
    old = rig.env.env_dir
    copies(rig, 1)

    def refuse(folder):
        raise OSError(13, "Permission denied")
    monkeypatch.setattr(rf.shutil, "rmtree", refuse)
    monkeypatch.setattr(rf, "remove_older", lambda home, specs, ctx, shown: rf.Removed((), ((old, "Permission denied"),)))
    code, io = run(rig, "older", "--remove", "--yes")
    assert code == 1 and "These could not be removed:" in io.lines and "  %s: Permission denied" % old in io.lines and os.path.isdir(old)


def test_a_list_that_changed_since_it_was_shown_removes_nothing_and_says_so(rig, monkeypatch):
    old = rig.env.env_dir
    copies(rig, 1)
    real = rf.older_copies
    seen = {"n": 0}

    def changing(home, specs, ctx):
        seen["n"] += 1
        found = real(home, specs, ctx)
        return found if seen["n"] == 1 else rf.Older((), found.left_alone, found.in_use)
    monkeypatch.setattr(rf, "older_copies", changing)
    code, io = run(rig, "older", "--remove", "--yes")
    assert code == 1 and os.path.isdir(old) and "The old copies are not the ones that were shown." in io.lines


# ---------------------------------------------------------------- the pieces around it

def test_every_set_of_programs_the_tool_can_build_has_a_name_in_words():
    from voice_studio.core.envspec import load_environments
    for spec in load_environments():
        assert CAT.has("refresh.name." + spec.id), spec.id


def test_the_name_of_a_voice_is_its_id_without_the_word_every_id_begins_with():
    assert rff.voice_name("voice-mike") == "Mike" and rff.voice_name("voice-amy") == "Amy" and rff.voice_name("other") == "other"
    assert rff.mid("The starting voice Mike") == "the starting voice Mike" and rff.mid("") == ""


def test_the_command_can_be_started_from_a_terminal(capsys):
    from voice_studio import refresh
    assert refresh.main(["help"]) == 0
    assert "ACK Voice Studio: refresh" in capsys.readouterr().out



# ---------------------------------------------------------------- what a mutation run found untested

def a_finding(reason, detail="", steps=(), fix="rebuild", status=rf.PROBLEM, subject="studio"):
    return rf.Finding("programs:" + subject, rf.PROGRAMS, subject, status, reason, fix, detail, tuple(steps))


def test_a_probe_is_named_in_words_when_the_catalog_has_them_and_as_it_is_when_it_does_not():
    assert rff.reason_text(CAT, a_finding("probe_failed", "studio-imports")) == "Its own check failed at this step: The recording and review tools open. Some of its files may be damaged."
    assert rff.reason_text(CAT, a_finding("probe_failed", "mystery-probe")) == "Its own check failed at this step: mystery-probe. Some of its files may be damaged."
    untried = a_finding("ready_untried", "studio-imports, mystery-probe, trainer-graphics-card", status=rf.GOOD, fix="")
    assert rff.reason_text(CAT, untried) == ("Every step is in place and its own check passed. Not tried on this computer: "
                                             "The recording and review tools open, mystery-probe, The training program can use the graphics card.")


def test_a_reason_the_programs_could_not_be_looked_at_is_the_sentence_in_two_parts_or_the_code_when_there_are_no_words():
    assert rff.reason_text(CAT, a_finding("cannot_build", "python_old")) == "It cannot be looked at: The system software that runs this tool is too old for this part. Update Ubuntu, then try again."
    assert rff.reason_text(CAT, a_finding("cannot_build", "no_words_for_this")) == "It cannot be looked at: no_words_for_this"
    assert rff.reason_text(CAT, a_finding("cannot_build", "")) == "It cannot be looked at: "


def test_programs_whose_last_step_was_done_but_never_checked_are_finished_by_the_check_alone(rig):
    record = json.loads(Path(rig.env.paths.record).read_text())
    record["state"] = "building"
    Path(rig.env.paths.record).write_text(json.dumps(record))
    code, io = run(rig, "repair", answers=["no"])
    ask = io.events.index(("ask", io.prompts[0]))
    said = [t for kind, t in io.events[:ask] if kind == "say"]
    assert code == 2 and "  Finish the programs called demo: Checking it works. The next screen shows what it will download and asks again." in said


def test_a_quick_repair_does_not_run_the_programs_own_check_before_or_after(rig):
    rig.system.bad_probe_codes = {"import os"}
    damage_voice(rig)
    rig.system.probe_runs.clear()
    code, io = run(rig, "repair", "--quick", "--yes")
    assert code == 0 and rig.system.probe_runs == [] and rig.voice_path().read_bytes() == VOICE_BYTES
    assert "  Looking at the programs called demo." not in io.lines and "Nothing needs repair." not in io.lines


def test_a_full_repair_runs_the_programs_own_check_before_and_after(rig):
    rig.system.probe_runs.clear()
    run(rig, "check")
    once = len(rig.system.probe_runs)
    damage_voice(rig)
    rig.system.probe_runs.clear()
    run(rig, "repair", "--yes")
    assert once > 0 and len(rig.system.probe_runs) == 2 * once


def test_nothing_found_to_fetch_is_said_and_nothing_is_fetched(rig, monkeypatch):
    damage_voice(rig)
    monkeypatch.setattr(rf, "items_to_fetch", lambda home, registry, findings: [])
    code, io = run(rig, "repair", "--yes")
    assert code == 1 and rig.fetched == [] and "  Nothing could be found to fetch for The starting voice Mike." in io.lines
    assert not [l for l in io.lines if "is fetched again" in l] and rig.voice_path().read_bytes() == b"z" * len(VOICE_BYTES)


def test_dash_dash_yes_on_a_repair_does_not_answer_the_builders_own_question(rig):
    shutil.rmtree(rig.env.paths.venv)
    code, io = run(rig, "repair", "--yes", answers=["yes"])
    assert code == 0 and io.prompts == ["Download and set it up now? Type yes to go on. "] and eb.inspect(rig.spec, rig.env.ctx).state == "ready"


def many_sets(rig, ids):
    return [replace(rig.spec, id=i) for i in ids]


def run_with(rig, specs, *argv, answers=(), monkeypatch=None):
    io = TermIO(answers, True)
    built = []

    def stub_build(options, *rest):
        built.append(options.env_id)
        return 0
    monkeypatch.setattr(rff, "run_build_env", stub_build)
    monkeypatch.setattr(rff.envbuild, "inspect", lambda spec, ctx: SimpleNamespace(state="ready"))
    code = rff.run_refresh(list(argv), rig.home, CAT, io, system=rig.system, registry=rig.registry, specs=specs, networked=rig.env.doors.networked, clock=ticking(), seams=rig.seams)
    return code, io, built


def test_a_rebuild_goes_through_the_sets_in_the_order_of_the_first_setup_and_the_unnamed_ones_last(rig, monkeypatch):
    specs = many_sets(rig, ["aaa", "training", "studio"])
    code, io, built = run_with(rig, specs, "rebuild", "--yes", monkeypatch=monkeypatch)
    assert code == 0 and built == ["studio", "training", "aaa"] and envgen.read(rig.home) == {"studio": 1, "training": 1, "aaa": 1}


def test_a_rebuild_of_one_named_set_builds_that_one_only(rig, monkeypatch):
    specs = many_sets(rig, ["aaa", "training", "studio"])
    code, io, built = run_with(rig, specs, "rebuild", "--yes", "--programs", "training", monkeypatch=monkeypatch)
    assert code == 0 and built == ["training"] and envgen.read(rig.home) == {"training": 1}


def test_when_there_is_no_old_copy_to_offer_nothing_is_asked_after_a_rebuild(rig, monkeypatch):
    code, io, built = run_with(rig, many_sets(rig, ["studio"]), "rebuild", "--yes", monkeypatch=monkeypatch)
    assert code == 0 and io.prompts == [] and "of the programs is on the disk" not in io.text and "of the programs are on the disk" not in io.text


def test_an_old_copy_that_cannot_be_removed_after_a_rebuild_fails_the_command_and_says_why(rig):
    old = rig.env.env_dir
    os.makedirs(rig.home.jobs, exist_ok=True)
    fake_job(rig.home.jobs, ["x"], "running", project="voice-check")
    code, io = run(rig, "rebuild", "--yes", answers=["yes"])
    assert code == 1 and os.path.isdir(old) and envgen.read(rig.home) == {"demo": 1}
    assert io.lines[-3:] == ["A task is running, and it may be using one of the old copies.", "Nothing was removed.", "Wait for the task to finish, or stop it, then try again."]


def older_of(count):
    return rf.Older(tuple(rf.OlderCopy("/old/%02d" % i, "demo", 1000 + i, 3, "ready", "") for i in range(count)), 0, ())


def test_exactly_ten_old_copies_are_all_listed_with_no_more_line_and_eleven_have_one():
    io = TermIO()
    rff._say_older(older_of(10), CAT, io)
    assert len([l for l in io.lines if l.startswith("  /old/")]) == 10 and not any(l.startswith("  And") for l in io.lines)
    io = TermIO()
    rff._say_older(older_of(11), CAT, io)
    assert len([l for l in io.lines if l.startswith("  /old/")]) == 10 and "  And 1 more." in io.lines


def test_only_ten_folders_that_could_not_be_removed_are_listed(monkeypatch):
    failed = tuple(("/old/%02d" % i, "Permission denied") for i in range(12))
    monkeypatch.setattr(rf, "remove_older", lambda home, specs, ctx, shown: rf.Removed((), failed))
    io = TermIO()
    assert rff._remove_older(older_of(12), None, [], None, CAT, io) == 1
    assert [l for l in io.lines if l.startswith("  /old/")] == ["  /old/%02d: Permission denied" % i for i in range(10)] and "These could not be removed:" in io.lines


def test_ctrl_c_stops_cleanly_says_so_and_is_not_a_success(rig, monkeypatch):
    def interrupt(*args, **kwargs):
        raise KeyboardInterrupt
    monkeypatch.setattr(rf, "look", interrupt)
    code, io = run(rig, "check")
    assert code == 1 and io.lines[-1] == "Stopped. What was finished is kept, and the same command carries on."


def test_a_build_that_goes_wrong_stops_the_ones_after_it_but_one_that_was_declined_does_not(rig, monkeypatch):
    specs = many_sets(rig, ["training", "studio"])
    monkeypatch.setattr(rff.envbuild, "inspect", lambda spec, ctx: SimpleNamespace(state="needs_work", stale=("venv",), env_dir="/nowhere"))
    for codes, expected in (((1, 0), ["studio"]), ((2, 0), ["studio", "training"])):
        built = []

        def stub_build(options, *rest):
            built.append(options.env_id)
            return codes[len(built) - 1]
        monkeypatch.setattr(rff, "run_build_env", stub_build)
        io = TermIO()
        code = rff.run_refresh(["repair", "--yes"], rig.home, CAT, io, system=rig.system, registry=rig.registry, specs=specs, networked=rig.env.doors.networked, clock=ticking(), seams=rig.seams)
        assert built == expected and code == 1, codes


def test_when_a_download_cannot_be_fetched_the_rest_of_that_download_is_not_tried_and_it_is_not_called_fetched(tmp_path):
    rig = RefreshRig(tmp_path)
    for name in SPEECH:
        (Path(envfind.speech_places(rig.home)[0]) / name).write_bytes(b"zz")
    import urllib.error
    rig.opener.fail_with = urllib.error.HTTPError("https://huggingface.co/x", 503, "unavailable", {}, None)
    code, io = run(rig, "repair", "--yes")
    assert code == 1 and len([l for l in io.lines if l.endswith("could not be fetched again. The file that was there is as it was.")]) == 1
    assert not [l for l in io.lines if "is fetched again" in l] and len([l for l in io.lines if l == "  Fetching the listening model."]) == 1
