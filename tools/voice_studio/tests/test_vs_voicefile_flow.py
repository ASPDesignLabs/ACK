# SPDX-License-Identifier: GPL-3.0-or-later
"""The terminal front for making the voice file: make, list. What is held to here: `make` shows what it will do and checks the room before it asks, a terminal with nobody at it
is never asked, nothing is written before a yes, everything lands in one new folder, a failed step says which and where the folder is and that nothing was deleted, `list` changes
nothing, and nothing printed is a catalog key or says that use is permitted."""
import os
import subprocess
import sys
from datetime import timedelta
from pathlib import Path

import pytest

from vs_fakes import FakeSystem
from vs_rounds_helpers import NOW, World, end_job, make_world, slurp, stamp
from vs_startvoice_helpers import Terminal, implies_permission, leaked_keys
from vs_voicefile_helpers import MakerSystem, TOOLS, finished_rounds, tree_of, write_settings
from voice_studio.core import jobs, rounds as rd, text, voicefile as vf, voicefile_flow as vff
from voice_studio.core.diskbudget import DEFAULT_TABLE, floors_for
from voice_studio.core.envbuild import EnvPaths
from voice_studio.core.paths import DataHome, ProjectPaths, ScratchPaths
from voice_studio.core.project import create_project
from voice_studio.core.text import size_text

CAT = text.load_catalog("en")
FOLDER = "voice-check-round-%03d-20261011-120000"        # NOW is 2026-10-11 12:00 UTC


class Rig:
    """A project with a training environment (a made-up one) and a stand-in for the programs that make the voice."""

    def __init__(self, tmp_path, environment="ready", **system_kw):
        self.home = DataHome(str(tmp_path / "home"))
        create_project(self.home.projects, "Voice check", "own")
        self.paths = ProjectPaths(self.home.projects + "/voice-check")
        os.makedirs(self.home.jobs, exist_ok=True)
        self.training = EnvPaths(str(tmp_path / "environments" / "training-abc"))
        self.environment = environment
        base = tmp_path / "voices" / "mike.ckpt"
        base.parent.mkdir(parents=True)
        from vs_rounds_helpers import write_checkpoint
        write_checkpoint(str(base))
        self.world = World(self.paths, ScratchPaths(self.paths.default_scratch), self.home.jobs, self.training, str(base))
        self.system = MakerSystem(disks={self.paths.rounds: (500 * 2**30, 300 * 2**30)}, **system_kw)

    def training_env(self):
        return (self.training, "ready") if self.environment == "ready" else (None, self.environment)

    def run(self, *argv, answers=(), interactive=True):
        io = Terminal(answers, interactive)
        code = vff.run_voicefile(list(argv), self.home, None, CAT, io, training=self.training_env, now=NOW, system=self.system, tools_dir=str(TOOLS))
        assert leaked_keys(io.text + "\n".join(io.prompts)) == [], "a catalog key was printed instead of words"
        assert implies_permission(io.text) == [], "something printed says or implies that use is permitted"
        return code, io

    def finish(self, count=2, **kw):
        for version in range(count):
            self.world.run_round(version=version, **kw)
            write_settings(self.paths, version + 1)

    def exports(self):
        return sorted(os.listdir(self.paths.exports)) if os.path.isdir(self.paths.exports) else []


@pytest.fixture
def rig(tmp_path):
    return Rig(tmp_path)


# ---------------------------------------------------------------- help and mistakes

@pytest.mark.parametrize("argv", [(), ("help",), ("-h",), ("--help",)])
def test_help_lists_both_commands(rig, argv):
    code, io = rig.run(*argv)
    assert code == 0 and all(word in io.text for word in ("make", "list", "--yes", "--project")) and rig.exports() == []


def test_an_unknown_command_or_option_does_nothing_and_says_so(rig):
    rig.finish(1)
    for argv, said in ((("fly",), "fly"), (("make", "--bogus"), "--bogus"), (("list", "extra"), "extra"), (("make", "--project", "a", "--project", "b"), "--project"),
                       (("make", "extra"), "extra")):
        code, io = rig.run(*argv)
        assert code == 2 and said in io.text and "Nothing was done" in io.text and rig.exports() == [], argv


def test_the_options_each_command_publishes_are_the_options_it_accepts():
    assert set(vff.OPTIONS) == {"make", "list"} and vff.OPTIONS["make"] == {"--yes", "-y", "--project"} and vff.OPTIONS["list"] == {"--project"}


def test_a_project_that_does_not_exist_is_named_and_nothing_is_made(rig):
    code, io = rig.run("make", "--project", "nobody", "--yes")
    assert code == 2 and "nobody" in io.text and rig.exports() == []


# ---------------------------------------------------------------- make: what it says before it asks

def test_make_shows_what_it_will_do_and_checks_the_room_before_it_asks(rig):
    rig.finish(2)
    code, io = rig.run("make", "--project", "voice-check", answers=["no"])
    asked = next(i for i, e in enumerate(io.events) if e[0] == "ask")
    said = [e[1] for e in io.events[:asked] if e[0] == "say"]
    assert code == 2 and rig.exports() == [] and rig.system.kinds() == []
    assert "The voice file would be made like this:" in said and "Checked before starting:" in said
    plan = vf.plan_voice(rig.paths, rd.load(rig.paths), "voice-check", jobs.utc_stamp(NOW), None)
    assert "  take the saved point of round 2, the chosen round (%s), which has about %d minutes of training in it" % (size_text(plan.checkpoint_bytes), plan.trained_minutes) in said
    assert "  take that round's own settings file" in said and "  make the voice, give it its settings file, and prepare it for the phone" in said
    assert "  make the zip file ACK takes, then read it back as the phone would" in said
    assert "  write everything into a new folder, %s/%s, and change nothing that is already there" % (rig.paths.exports, FOLDER % 2) in said
    assert "  write at most about %s, with about %s free" % (size_text(vf.NEED_BYTES), size_text(300 * 2**30)) in said
    assert io.prompts == ["Make the voice file from round 2 now? Type yes to make it. "] and "Nothing was done." in io.lines


@pytest.mark.parametrize("answers, interactive, said", [(["no"], True, "Nothing was done."), ([""], True, "Nothing was done."), ([], True, "There was nobody to ask."),
                                                        ([], False, "There was nobody to ask.")])
def test_make_writes_nothing_unless_the_answer_is_a_yes(rig, answers, interactive, said):
    rig.finish(2)
    before = tree_of(rig.paths.root)
    code, io = rig.run("make", "--project", "voice-check", answers=answers, interactive=interactive)
    assert code == 2 and said in io.text and tree_of(rig.paths.root) == before and rig.system.kinds() == []


def test_a_disk_that_is_getting_tight_says_so_and_goes_on_and_one_that_cannot_be_read_says_that(rig):
    rig.finish(1)
    floors = floors_for(DEFAULT_TABLE, holds_recordings=True)
    rig.system.disks[rig.paths.rounds] = (500 * 2**30, vf.NEED_BYTES + floors.stop)
    code, io = rig.run("make", "--project", "voice-check", answers=["no"])
    assert "  Free space is getting tight: about %s is free and this can write about %s. It can go on." % (size_text(vf.NEED_BYTES + floors.stop), size_text(vf.NEED_BYTES)) in io.lines
    del rig.system.disks[rig.paths.rounds]
    code, io = rig.run("make", "--project", "voice-check", answers=["no"])
    assert "  The free space of the disk could not be read, so it was not checked." in io.lines and code == 2


# ---------------------------------------------------------------- make: refusals come before the question

def test_without_the_training_programs_nothing_is_asked_or_made_and_the_way_to_set_them_up_is_given(tmp_path):
    rig = Rig(tmp_path, environment="missing")
    rig.finish(1)
    code, io = rig.run("make", "--project", "voice-check", "--yes")
    assert code == 1 and "The training programs are not ready on this computer (missing). Nothing was made." in io.text and "python3 -m voice_studio.buildenv training" in io.text
    assert rig.exports() == [] and io.prompts == []


@pytest.mark.parametrize("setup, said", [
    ("no_rounds", "No round is chosen yet, so there is no voice to make a file from."),
    ("no_settings", "The chosen round has no settings file."),
    ("no_room", "There is not enough free space to make the voice file."),
    ("gone", "The chosen round's saved file is missing."),
])
def test_a_refusal_says_what_it_is_what_was_not_done_and_what_to_do_next_and_asks_nothing(rig, setup, said):
    if setup != "no_rounds":
        rig.finish(1)
    if setup == "no_settings":
        os.unlink(rig.paths.round_configs + "/round-001.json")
    if setup == "no_room":
        rig.system.disks[rig.paths.rounds] = (500 * 2**30, 1000)
    if setup == "gone":
        os.unlink(vf.plan_voice(rig.paths, rd.load(rig.paths), "voice-check", STAMP_FOR_TESTS, None).checkpoint)
    code, io = rig.run("make", "--project", "voice-check", "--yes")
    assert code == 1 and said in io.text and io.prompts == [] and rig.exports() == [] and rig.system.kinds() == []
    assert sum(1 for l in io.lines if l.startswith("  ")) >= 3                      # what, what changed, what to do


STAMP_FOR_TESTS = "2026-10-11T12:00:00Z"


def test_while_a_round_trains_nothing_is_made(rig):
    rig.finish(1)
    plan = rig.world.begin()
    rd.attach_job(rig.paths, plan.number, rig.world.job_for(plan, "running").id)
    code, io = rig.run("make", "--project", "voice-check", "--yes")
    assert code == 1 and "A round is still training." in io.text and rig.exports() == []


# ---------------------------------------------------------------- make: the whole thing

def test_make_with_yes_does_everything_in_order_and_says_where_the_file_is(rig):
    rig.finish(2)
    code, io = rig.run("make", "--yes", "--project", "voice-check")
    zip_path = "%s/%s/%s.zip" % (rig.paths.exports, FOLDER % 2, FOLDER % 2)
    assert code == 0 and io.prompts == [] and rig.system.kinds() == ["export", "patch"] and os.path.isfile(zip_path)
    steps = [l for l in io.lines if l.startswith("Step ")]
    assert steps == ["Step 1 of 5: making the voice from the saved point. This is the slow step.", "Step 2 of 5: giving it its settings file.",
                     "Step 3 of 5: preparing it for the phone.", "Step 4 of 5: making the zip file.", "Step 5 of 5: reading the zip file back as the phone would."]
    assert io.lines.index(steps[0]) < io.lines.index(steps[4]) < io.lines.index("Done. The file to give to ACK is: " + zip_path)
    assert "It is %s, and read back as the phone would, it has no problems." % size_text(os.stat(zip_path).st_size) in io.lines
    assert "Everything is in %s/%s: the voice, its settings file, the original before it was prepared, and the zip file." % (rig.paths.exports, FOLDER % 2) in io.lines
    assert io.lines[-1].startswith("Copy the zip file to the phone, then in ACK open the audio screen")
    assert rig.exports() == [FOLDER % 2]


def test_make_with_a_typed_yes_asks_once_and_then_makes_it(rig):
    rig.finish(1)
    code, io = rig.run("make", "--project", "voice-check", answers=["yes"])
    assert code == 0 and len(io.prompts) == 1 and rig.exports() == [FOLDER % 1]
    assert io.events.index(("ask", io.prompts[0])) < io.events.index(("say", "Step 1 of 5: making the voice from the saved point. This is the slow step."))


def test_make_names_the_only_project_without_being_told_and_a_second_run_in_the_same_second_is_refused_not_overwritten(rig):
    rig.finish(1)
    assert rig.run("make", "--yes")[0] == 0
    before = {p: slurp(p) for p in tree_of(rig.paths.exports)}
    code, io = rig.run("make", "--yes")
    assert code == 1 and "The new folder could not be made, because that name is already there." in io.text and "what is there was left as it is" in io.text
    assert not any(l.startswith("  What was made so far") for l in io.lines)                      # the folder that is there is not this run's to describe
    assert {p: slurp(p) for p in tree_of(rig.paths.exports)} == before


def test_make_only_writes_into_the_new_folder_and_leaves_everything_else_byte_for_byte(rig):
    rig.finish(2)
    before = {p: slurp(p) for p in tree_of(rig.paths.root)}
    assert rig.run("make", "--yes", "--project", "voice-check")[0] == 0
    assert all(os.path.exists(p) and slurp(p) == data for p, data in before.items())
    new = [p for p in tree_of(rig.paths.root) if p not in before]
    assert new and all(p.startswith("%s/%s/" % (rig.paths.exports, FOLDER % 2)) for p in new)


def test_make_brings_the_record_up_to_date_and_says_so_when_a_round_ended_since(rig):
    plan = rig.world.begin()
    info = rig.world.job_for(plan, "running")
    rd.attach_job(rig.paths, 1, info.id)
    rig.world.trainer_makes(0)
    end_job(info.dir, "finished", ended_at=stamp(20))
    write_settings(rig.paths, 1)
    assert rd.load(rig.paths).rounds[0].state == "running"
    code, io = rig.run("make", "--yes", "--project", "voice-check")
    assert code == 0 and "Noticed: round 1 is now: Finished." in io.lines and rd.load(rig.paths).rounds[0].state == "finished"


# ---------------------------------------------------------------- make: when a step fails

def test_a_failed_export_says_which_step_what_was_left_and_that_nothing_was_deleted(tmp_path):
    rig = Rig(tmp_path, export="fail")
    rig.finish(1)
    code, io = rig.run("make", "--yes", "--project", "voice-check")
    folder = "%s/%s" % (rig.paths.exports, FOLDER % 1)
    assert code == 1 and "  The voice could not be made from the saved file." in io.lines
    assert "  The new folder was left as it is, and nothing was deleted." in io.lines and "  What was made so far is in %s. Nothing was deleted." % folder in io.lines
    assert any("GuardOnDataDependentSymNode: boom" in l and l.startswith("  Technical detail:") for l in io.lines) and os.path.isdir(folder)
    assert not any(l.startswith("Done.") for l in io.lines) and rig.system.kinds() == ["export"]


def test_a_failed_patch_names_the_step_and_leaves_the_voice_and_settings_file(tmp_path):
    rig = Rig(tmp_path, patch="fail")
    rig.finish(1)
    code, io = rig.run("make", "--yes", "--project", "voice-check")
    folder = "%s/%s" % (rig.paths.exports, FOLDER % 1)
    assert code == 1 and "  The voice was made, but it could not be prepared for the phone." in io.lines and "  What was made so far is in %s. Nothing was deleted." % folder in io.lines
    assert sorted(os.listdir(folder)) == ["my_voice.onnx", "my_voice.onnx.json"]


def test_a_voice_the_zip_check_refuses_lists_why_in_plain_words_and_makes_no_zip(tmp_path):
    rig = Rig(tmp_path, patch="silent")
    rig.finish(1)
    code, io = rig.run("make", "--yes", "--project", "voice-check")
    folder = "%s/%s" % (rig.paths.exports, FOLDER % 1)
    assert code == 1 and "  This voice is not ready to send to the phone." in io.lines
    assert "    - The voice file has not been prepared for the phone yet. Without that step, ACK would stop on the first word it tries to say." in io.lines
    assert "  What was made so far is in %s. Nothing was deleted." % folder in io.lines and not any(n.endswith(".zip") for n in os.listdir(folder))


def test_ctrl_c_during_the_export_says_where_the_folder_is_and_deletes_nothing(tmp_path):
    rig = Rig(tmp_path, export="interrupt")
    rig.finish(2)
    before = tree_of(rig.paths.root)
    code, io = rig.run("make", "--yes", "--project", "voice-check")
    folder = "%s/%s" % (rig.paths.exports, FOLDER % 2)
    assert code == 1 and "Stopped. What was made so far is in %s. Nothing was deleted." % folder in io.lines
    assert tree_of(rig.paths.root) == before and os.path.isdir(folder)


# ---------------------------------------------------------------- list

def test_list_with_nothing_made_says_so_and_how_to_make_one_and_changes_nothing(rig):
    before = tree_of(rig.paths.root)
    code, io = rig.run("list", "--project", "voice-check")
    assert code == 0 and "No voice file has been made for this project yet." in io.lines and tree_of(rig.paths.root) == before
    assert "Make one from the chosen round with: python3 -m voice_studio.voicefile make --project voice-check" in io.lines


def test_list_shows_each_voice_file_made_with_its_size_and_where_it_is(rig):
    rig.finish(2)
    rig.run("make", "--yes", "--project", "voice-check")
    before = tree_of(rig.paths.root)
    code, io = rig.run("list", "--project", "voice-check")
    zip_path = "%s/%s/%s.zip" % (rig.paths.exports, FOLDER % 2, FOLDER % 2)
    assert code == 0 and tree_of(rig.paths.root) == before and "Voice files made for Voice check:" in io.lines
    assert "  %s: %s" % (FOLDER % 2, size_text(os.stat(zip_path).st_size)) in io.lines and "    " + zip_path in io.lines


# ---------------------------------------------------------------- the real front

def test_the_front_runs_help_and_list_and_makes_nothing_when_the_training_programs_are_not_set_up(tmp_path):
    env = dict(os.environ, HOME=str(tmp_path), PYTHONDONTWRITEBYTECODE="1")

    def run(*argv):
        return subprocess.run([sys.executable, "-m", "voice_studio.voicefile"] + list(argv), cwd=str(TOOLS), env=env, text=True, capture_output=True, timeout=60,
                              stdin=subprocess.DEVNULL)
    helped = run("help")
    assert helped.returncode == 0 and "make" in helped.stdout and "Traceback" not in helped.stderr
    made = subprocess.run([sys.executable, "-m", "voice_studio.projects", "new", "--own", "--name", "Voice check", "--voice", "mike", "--yes"], cwd=str(TOOLS), env=env,
                          text=True, capture_output=True, timeout=60, stdin=subprocess.DEVNULL)
    assert made.returncode == 0
    listed = run("list", "--project", "voice-check")
    assert listed.returncode == 0 and "No voice file has been made for this project yet." in listed.stdout and "Traceback" not in listed.stderr
    refused = run("make", "--project", "voice-check", "--yes")
    assert refused.returncode == 1 and "Traceback" not in refused.stderr and "Nothing was made." in refused.stdout
    assert sorted(os.listdir(tmp_path / "ack-voice-studio" / "projects" / "voice-check" / "exports")) == []
