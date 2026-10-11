# SPDX-License-Identifier: GPL-3.0-or-later
"""The terminal front for training rounds: list, keep, start, stop, choose, back, note. What is held to here: commands that look change nothing (not even the record),
every command that changes something shows what it will do and asks first, a terminal with nobody at it is never asked, a round continues from the chosen round and
from the starting voice only when there is none, a job that does not start leaves no round behind, and nothing printed is a catalog key or says that use is permitted."""
import json
import os
import subprocess
import sys
from datetime import timedelta
from pathlib import Path

import pytest

from vs_rounds_helpers import DATASET, NOW, PROJECT, VOICE, World, end_job, fake_job, make_world, slurp, stamp
from vs_startvoice_helpers import VOICE_A, Terminal, implies_permission, leaked_keys, make_registry
from voice_studio import rounds as front
from voice_studio.core import jobs, rounds as rd, startvoice as sv, text
from voice_studio.core import rounds_flow as rf
from voice_studio.core.cliargs import parse_args
from voice_studio.core.envbuild import EnvPaths
from voice_studio.core.paths import DataHome, ProjectPaths, ScratchPaths
from voice_studio.core.project import create_project, load_project, save_project, with_starting_voice
from voice_studio.core.scratch import MARKER_NAME, marker_text

CAT = text.load_catalog("en")
TOOLS = Path(__file__).resolve().parents[2]


class Rig:
    """A project on disk with a starting voice that is chosen, acknowledged and on the computer, a built training environment (a made-up one), and a job starter that
    only writes the job's folder."""

    def __init__(self, tmp_path, *, voice=True, environment="ready", projects=("Anna",)):
        self.home = DataHome(str(tmp_path / "home"))
        self.registry = make_registry()
        for name in projects:
            create_project(self.home.projects, name, "own")
        self.paths = ProjectPaths(self.home.projects + "/anna")
        os.makedirs(self.home.jobs, exist_ok=True)
        self.training = EnvPaths(str(tmp_path / "environments" / "training-abc"))
        self.environment = environment
        self.started = []
        self.start_error = None
        folder = Path(self.home.voices) / "voice-mike"
        folder.mkdir(parents=True)
        (folder / "voice-mike.ckpt").write_bytes(VOICE_A)
        if voice:
            project = sv.acknowledge(sv.choose(load_project(self.paths), self.registry, "voice-mike"), self.registry, "voice-mike")
            save_project(self.paths, project)
        self.world = World(self.paths, ScratchPaths(self.paths.default_scratch), self.home.jobs, self.training, str(folder / "voice-mike.ckpt"))

    def training_env(self):
        return (self.training, "ready") if self.environment == "ready" else (None, self.environment)

    def start(self, jobs_root, spec):
        if self.start_error is not None:
            raise self.start_error
        self.started.append(spec)
        return fake_job(jobs_root, spec.argv, "running", run_dir=spec.cwd)

    def run(self, *argv, answers=(), interactive=True):
        io = Terminal(answers, interactive)
        code = rf.run_rounds(list(argv), self.home, self.registry, CAT, io, training=self.training_env, now=NOW, start=self.start)
        assert leaked_keys(io.text + "\n".join(io.prompts)) == [], "a catalog key was printed instead of words"
        assert implies_permission(io.text) == [], "something printed says or implies that use is permitted"
        return code, io

    def record_bytes(self):
        return slurp(self.paths.rounds_file) if os.path.exists(self.paths.rounds_file) else None

    def finish_rounds(self, count=1, **kw):
        for version in range(count):
            self.world.run_round(version=version, **kw)


@pytest.fixture
def rig(tmp_path):
    return Rig(tmp_path)


def start_args(*extra, dataset=DATASET):
    return ("start", "--set", dataset, "--project", "anna") + extra


# ---------------------------------------------------------------- help and mistakes

@pytest.mark.parametrize("argv", [(), ("help",), ("-h",), ("--help",)])
def test_help_lists_every_command(rig, argv):
    code, io = rig.run(*argv)
    assert code == 0 and all(word in io.text for word in ("list", "start", "stop", "choose", "back", "note", "keep", "--yes")) and rig.record_bytes() is None


def test_an_unknown_command_or_option_does_nothing_and_says_so(rig):
    for argv, said in ((("fly",), "fly"), (("list", "--bogus"), "--bogus"), (("start", "--set"), "--set"), (("list", "extra"), "extra"),
                       (("list", "--project", "a", "--project", "b"), "--project")):
        code, io = rig.run(*argv)
        assert code == 2 and said in io.text and "Nothing was done" in io.text and rig.record_bytes() is None, argv


def test_the_options_each_command_publishes_are_the_options_it_accepts():
    for command, options in rf.OPTIONS.items():
        flags = {o: o.lstrip("-") for o in options if o in rf.YES}
        values = {o: o.lstrip("-") for o in options if o not in rf.YES}
        sample = [x for o in sorted(options) for x in ((o,) if o in rf.YES else (o, "v"))]
        parse_args(sample + ["word"] if command in ("choose", "note") else sample, flags=flags, values=values, max_words=1)
    assert set(rf.OPTIONS) == {"list", "start", "stop", "choose", "back", "note", "keep"}
    long = {c: {o for o in options if o.startswith("--")} for c, options in rf.OPTIONS.items()}
    assert long["list"] == {"--project"} and long["keep"] == {"--project"} and {"--set", "--minutes", "--yes", "--project"} == long["start"]
    assert {"--text", "--yes", "--project"} == long["note"] and {"--yes", "--project"} == long["stop"] == long["choose"] == long["back"]


def test_with_two_projects_and_none_named_nothing_is_guessed(tmp_path):
    rig = Rig(tmp_path, projects=("Anna", "Ben"))
    for command in ("list", "keep", "stop", "back", "start"):
        code, io = rig.run(command)
        assert code == 2 and "anna, ben" in io.text, command
    assert rig.record_bytes() is None


# ---------------------------------------------------------------- list and keep look and change nothing

def test_a_project_with_no_rounds_says_so_and_says_where_the_first_one_starts_from(rig):
    code, io = rig.run("list")
    assert code == 0 and "There are no rounds yet" in io.text and "No round is chosen yet" in io.text and "start --set" in io.text and rig.record_bytes() is None
    assert not os.path.exists(rig.paths.rounds_lock)


def test_list_shows_every_round_with_what_it_continued_from_and_marks_the_chosen_one(rig):
    rig.finish_rounds(2)
    rd.set_note(rig.paths, 2, "clearer on the S sounds")
    before = rig.record_bytes()
    code, io = rig.run("list", "--project", "anna")
    lines = io.lines
    assert code == 0 and rig.record_bytes() == before
    assert "Round 1: Finished." in lines and "Round 2 (chosen): Finished." in lines
    assert "  Asked to train for 25 minutes, starting from the starting voice voice-mike, on the training set %s." % DATASET in lines
    assert "  Asked to train for 25 minutes, continuing from round 1, on the training set %s." % DATASET in lines
    assert "  Note: clearer on the S sounds" in lines and "  The saved point is there" in lines and "  Started 2026-10-11 12:00:00 UTC." in lines
    assert any(l.startswith("Chosen: round 2.") and "About 50 minutes of training" in l for l in lines) and "To train another round" in io.text


def test_list_shows_what_a_write_would_find_without_writing_it(rig):
    plan = rig.world.begin()
    info = rig.world.job_for(plan, "running")
    rd.attach_job(rig.paths, 1, info.id)
    rig.world.trainer_makes(0)
    end_job(info.dir, "finished", ended_at=stamp(20))
    before = rig.record_bytes()
    code, io = rig.run("list", "--project", "anna")
    assert "Round 1 (chosen): Finished." in io.lines and rig.record_bytes() == before and rd.load(rig.paths).rounds[0].state == "running"


def test_a_running_round_is_said_to_be_running_and_how_to_stop_it(rig):
    plan = rig.world.begin()
    rd.attach_job(rig.paths, 1, rig.world.job_for(plan, "running").id)
    code, io = rig.run("list", "--project", "anna")
    assert "Round 1: Training now." in io.lines and any("Round 1 is running now" in l and "stop --project anna" in l for l in io.lines)


def test_a_failed_round_says_why_and_a_missing_saved_point_is_said(rig):
    rig.world.run_round(version=0, ends="failed")
    rig.world.run_round(version=1)
    os.unlink(rig.paths.run + "/lightning_logs/version_1/checkpoints/last.ckpt")
    code, io = rig.run("list", "--project", "anna")
    assert "Round 1: Ended with an error." in io.lines and "  The training program ended with an error." in io.lines and "  The saved point is missing" in io.lines
    assert "No round is chosen yet" not in io.text and "Chosen: round 2." in io.text


def test_keep_says_what_is_kept_what_is_spare_and_what_is_not_ours_and_removes_nothing(rig):
    rig.finish_rounds(3)
    rig.world.trainer_makes(7)
    before = rig.record_bytes()
    files = sorted(str(p) for p in Path(rig.paths.run).rglob("*") if p.is_file())
    code, io = rig.run("keep", "--project", "anna")
    assert code == 0 and rig.record_bytes() == before and sorted(str(p) for p in Path(rig.paths.run).rglob("*") if p.is_file()) == files
    assert any(l.startswith("Kept for sure (2 files") for l in io.lines) and "  round 3: last.ckpt," in io.text and "  round 2: last.ckpt," in io.text
    assert any(l.startswith("Spare (7 files") for l in io.lines) and any(l.startswith("Not made by a round of this tool (3 files") for l in io.lines)
    assert "This command removes nothing." in io.lines


def test_keep_with_nothing_saved_yet_says_so(rig):
    code, io = rig.run("keep", "--project", "anna")
    assert code == 0 and "There are no saved files yet." in io.lines and "This command removes nothing." in io.lines


def test_a_damaged_record_is_reported_and_left_exactly_as_it_is(rig):
    os.makedirs(rig.paths.rounds, exist_ok=True)
    Path(rig.paths.rounds_file).write_text("{broken")
    for argv in (("list",), ("keep",), ("choose", "1"), ("back",), ("stop",), ("note", "1", "--text", "x"), start_args()):
        code, io = rig.run(*argv, "--project", "anna") if argv[0] != "start" else rig.run(*argv)
        assert code == 1 and "damaged" in io.text and "left exactly as it was" in io.text, argv
    assert Path(rig.paths.rounds_file).read_text() == "{broken" and not os.path.exists(rig.paths.rounds_previous)


# ---------------------------------------------------------------- start

def test_the_first_round_shows_what_it_will_do_asks_and_then_starts_from_the_starting_voice(rig):
    rig.world.dataset()
    code, io = rig.run(*start_args(), answers=["yes"])
    assert code == 0 and len(rig.started) == 1
    plan_at, ask_at = io.events.index(("say", "Round 1 would:")), next(i for i, e in enumerate(io.events) if e[0] == "ask")
    assert plan_at < ask_at and io.prompts == ["Start round 1 now? Type yes to start. "]
    for line in ("  continue from the starting voice voice-mike", "  train on the training set %s, which has 1 clips" % DATASET, "  run for about 25 minutes and then stop by itself",
                 "  use the graphics card until it ends; closing this terminal does not stop it", "  keep its files under " + rig.paths.run):
        assert line in io.lines
    spec = rig.started[0]
    assert spec.argv[spec.argv.index("--ckpt_path") + 1] == rig.world.base_path and spec.kind == "train" and spec.gpu and spec.cwd == rig.paths.run
    record = rd.load(rig.paths)
    assert (record.rounds[0].state, record.rounds[0].parent, record.rounds[0].voice) == ("running", 0, VOICE) and any(l.startswith("Round 1 started (job ") for l in io.lines)
    assert "list --project anna" in io.text and "stop --project anna" in io.text


def test_yes_on_the_command_line_answers_the_question_and_nothing_else_is_asked(rig):
    rig.world.dataset()
    code, io = rig.run(*start_args("--yes"))
    assert code == 0 and io.prompts == [] and len(rig.started) == 1


def test_a_no_or_nobody_to_ask_starts_nothing_and_writes_nothing(rig):
    rig.world.dataset()
    for answers, interactive, said in ((["no"], True, "Nothing was done"), ([""], True, "Nothing was done"), ([], False, "nobody to ask"), ([], True, "nobody to ask"),
                                       (["yes"], False, "nobody to ask")):                       # nobody at the terminal: a queued yes is not read
        code, io = rig.run(*start_args(), answers=answers, interactive=interactive)
        assert code == 2 and said in io.text and rig.started == [] and rig.record_bytes() is None, (answers, interactive)


def test_the_length_of_the_round_is_the_length_asked_for(rig):
    rig.world.dataset()
    code, io = rig.run(*start_args("--minutes", "30", "--yes"))
    spec = rig.started[0]
    assert code == 0 and spec.argv[spec.argv.index("--trainer.max_time") + 1] == "00:00:30:00" and "run for about 30 minutes" in io.text
    assert rd.load(rig.paths).rounds[0].minutes == 30


@pytest.mark.parametrize("minutes", ["abc", "0", "25.5", "-5", "", "1441", "２５", "1_0", "9" * 5000])             # the last is longer than Python will turn into a number
def test_a_length_that_is_not_a_whole_number_of_minutes_from_one_to_a_day_starts_nothing(rig, minutes):
    rig.world.dataset()
    code, io = rig.run(*start_args("--minutes", minutes, "--yes"))
    assert code == 1 and "not usable" in io.text and "1440" in io.text and rig.started == [] and rig.record_bytes() is None


def test_without_a_training_set_named_the_ones_there_are_listed_and_nothing_starts(rig):
    code, io = rig.run("start", "--project", "anna")
    assert code == 2 and "no training set yet" in io.text
    code, io = rig.run("start", "--set", "dataset-1", "--project", "anna")
    assert code == 2 and "no training set yet" in io.text and "no training set called" not in io.text and rig.started == []
    rig.world.dataset("dataset-b")
    rig.world.dataset("dataset-a")
    os.makedirs(rig.world.scratch.datasets + "/.hidden")
    os.symlink(rig.world.scratch.datasets + "/dataset-a", rig.world.scratch.datasets + "/dataset-link")
    Path(rig.world.scratch.datasets, "a-file").write_text("x")
    code, io = rig.run("start", "--project", "anna")
    assert code == 2 and "The ones in this project are: dataset-a, dataset-b." in io.text and rig.started == []
    code, io = rig.run("start", "--set", "dataset-c", "--project", "anna")
    assert code == 2 and "no training set called dataset-c" in io.text and "dataset-a, dataset-b" in io.text and rig.started == []


def test_a_training_set_that_is_not_whole_is_refused_in_words_before_anything_is_written(rig):
    folder = rig.world.dataset()
    os.unlink(folder + "/wav/a.wav")
    code, io = rig.run(*start_args("--yes"))
    assert code == 1 and rig.started == [] and rig.record_bytes() is None and "training set" in io.text.lower()


def test_programs_that_are_not_ready_are_said_with_the_command_that_sets_them_up(tmp_path):
    rig = Rig(tmp_path, environment="needs_work")
    rig.world.dataset()
    code, io = rig.run(*start_args("--yes"))
    assert code == 2 and "voice_studio.buildenv training" in io.text and "not ready on this computer" in io.text and rig.started == [] and rig.record_bytes() is None
    assert CAT.t("env.state.needs_work") in io.text and "needs_work" not in io.text           # the state in words, not as the program names it


def test_with_no_round_to_continue_from_a_starting_voice_is_needed_and_is_asked_for_in_words(tmp_path):
    rig = Rig(tmp_path, voice=False)
    rig.world.dataset()
    code, io = rig.run(*start_args("--yes"))
    assert code == 2 and "no starting voice" in io.text and "voice_studio.voices choose <voice> --project anna" in io.text and rig.started == [] and rig.record_bytes() is None
    project = with_starting_voice(load_project(rig.paths), "voice-mike")
    save_project(rig.paths, project)
    code, io = rig.run(*start_args("--yes"))
    assert code == 2 and "voice-mike is not ready yet (next:" in io.text and "voices get voice-mike --project anna" in io.text and rig.started == []
    assert "(next: %s)" % CAT.t("startvoice.step.acknowledge") in io.text


def test_once_a_round_has_a_saved_point_the_starting_voice_is_no_longer_needed(tmp_path):
    rig = Rig(tmp_path, voice=False)
    rig.world.dataset()
    rig.world.base_path = rig.world.base_path
    save_project(rig.paths, with_starting_voice(load_project(rig.paths), "voice-mike"))
    sv_ack = sv.acknowledge(load_project(rig.paths), rig.registry, "voice-mike")
    save_project(rig.paths, sv_ack)
    rig.world.run_round(version=0)
    save_project(rig.paths, with_starting_voice(load_project(rig.paths), None))                    # the project forgot its starting voice
    code, io = rig.run(*start_args("--yes"))
    assert code == 0 and "continue from round 1, the chosen round" in io.text


def test_the_next_round_continues_from_the_chosen_round_not_from_the_starting_voice(rig):
    rig.finish_rounds(2)
    code, io = rig.run(*start_args("--yes"))
    spec = rig.started[0]
    assert code == 0 and "  continue from round 2, the chosen round" in io.lines and "Round 3 would:" in io.lines
    assert spec.argv[spec.argv.index("--ckpt_path") + 1] == rig.paths.run + "/lightning_logs/version_1/checkpoints/last.ckpt"
    assert [r.number for r in rd.load(rig.paths).rounds] == [1, 2, 3]


def test_after_going_back_the_next_round_continues_from_where_it_went_back_to(rig):
    rig.finish_rounds(2)
    assert rig.run("back", "--project", "anna", "--yes")[0] == 0
    code, io = rig.run(*start_args("--yes"))
    assert code == 0 and "  continue from round 1, the chosen round" in io.lines
    assert rig.started[0].argv[rig.started[0].argv.index("--ckpt_path") + 1].endswith("version_0/checkpoints/last.ckpt")


def test_a_chosen_rounds_missing_file_stops_the_round_in_words_and_nothing_else_is_used(rig):
    rig.finish_rounds(1)
    os.unlink(rig.paths.run + "/lightning_logs/version_0/checkpoints/last.ckpt")
    code, io = rig.run(*start_args("--yes"))
    assert code == 1 and "not where it should be" in io.text and "no other file was used" in io.text and rig.started == []


def test_a_round_is_not_started_while_one_runs(rig):
    rig.world.dataset()
    assert rig.run(*start_args("--yes"))[0] == 0
    code, io = rig.run(*start_args("--yes"))
    assert code == 1 and "already running" in io.text and len(rig.started) == 1


def test_a_job_that_does_not_start_is_said_in_words_and_leaves_no_round_behind(rig):
    rig.world.dataset()
    rig.start_error = jobs.JobError("gpu_busy", "20261011-000000-train-abcd")
    code, io = rig.run(*start_args("--yes"))
    assert code == 1 and "Another job is using the graphics card" in io.text and rd.load(rig.paths).rounds == ()
    rig.start_error = None
    assert rig.run(*start_args("--yes"))[0] == 0 and rd.load(rig.paths).rounds[0].number == 1


def test_a_round_that_ended_since_is_written_down_and_said_before_the_next_one_starts(rig):
    plan = rig.world.begin()
    info = rig.world.job_for(plan, "running")
    rd.attach_job(rig.paths, 1, info.id)
    rig.world.trainer_makes(0)
    end_job(info.dir, "finished", ended_at=stamp(20))
    code, io = rig.run(*start_args("--yes"))
    assert code == 0 and "Noticed: round 1 is now: Finished." in io.lines and "  continue from round 1, the chosen round" in io.lines
    assert rd.load(rig.paths).rounds[0].state == "finished"


def test_a_place_chosen_for_working_files_must_prove_it_is_the_projects_own_before_a_round_starts(tmp_path):
    rig = Rig(tmp_path)
    place = tmp_path / "usb"
    place.mkdir()
    from voice_studio.core.project import Scratch, SCRATCH_CUSTOM
    from dataclasses import replace
    save_project(rig.paths, replace(load_project(rig.paths), scratch=Scratch(SCRATCH_CUSTOM, str(place))))
    folder = place / "ack-voice-scratch" / "anna"
    custom = ScratchPaths(str(folder))
    os.makedirs(custom.datasets + "/" + DATASET + "/wav")
    Path(custom.datasets, DATASET, "wav", "a.wav").write_bytes(b"RIFFxxxx")
    Path(custom.datasets, DATASET, "metadata.csv").write_text("a.wav|hello there\n")
    code, io = rig.run(*start_args("--yes"))
    assert code == 2 and "not ready" in io.text and "plugged in" in io.text and rig.started == [] and rig.record_bytes() is None            # no marker: an unplugged drive looks like this
    (folder / MARKER_NAME).write_text(marker_text("someone-else"))
    assert rig.run(*start_args("--yes"))[0] == 2 and rig.started == []
    (folder / MARKER_NAME).write_text(marker_text("anna"))
    code, io = rig.run(*start_args("--yes"))
    spec = rig.started[0]
    assert code == 0 and spec.argv[spec.argv.index("--data.cache_dir") + 1].startswith(custom.caches + "/") and spec.argv[spec.argv.index("--data.csv_path") + 1].startswith(custom.datasets)


def test_looking_does_not_need_the_place_to_be_ready(tmp_path):
    rig = Rig(tmp_path)
    from voice_studio.core.project import Scratch, SCRATCH_CUSTOM
    from dataclasses import replace
    save_project(rig.paths, replace(load_project(rig.paths), scratch=Scratch(SCRATCH_CUSTOM, str(tmp_path / "gone"))))
    assert rig.run("list", "--project", "anna")[0] == 0 and rig.run("keep", "--project", "anna")[0] == 0


# ---------------------------------------------------------------- stop

def test_stop_with_nothing_running_says_so(rig):
    code, io = rig.run("stop", "--project", "anna", "--yes")
    assert code == 2 and "nothing to stop" in io.text


def test_stop_asks_first_and_then_asks_the_round_to_stop_once(rig):
    plan = rig.world.begin()
    info = rig.world.job_for(plan, "running")
    rd.attach_job(rig.paths, 1, info.id)
    code, io = rig.run("stop", "--project", "anna", answers=["no"])
    assert code == 2 and not os.path.exists(info.dir + "/stop.json") and "can lose the last few minutes" in io.prompts[0]
    code, io = rig.run("stop", "--project", "anna", answers=[], interactive=False)
    assert code == 2 and not os.path.exists(info.dir + "/stop.json")
    code, io = rig.run("stop", "--project", "anna", answers=["yes"])
    assert code == 0 and os.path.exists(info.dir + "/stop.json") and "Asked round 1 to stop" in io.text and json.loads(slurp(info.dir + "/stop.json"))["forced"] is False
    code, io = rig.run("stop", "--project", "anna", "--yes")
    assert code == 0 and "already asked to stop" in io.text


def test_stop_does_not_stop_a_round_it_has_no_job_for_yet(rig):
    rig.world.begin()
    code, io = rig.run("stop", "--project", "anna", "--yes")
    assert code == 2 and "no job to stop yet" in io.text


# ---------------------------------------------------------------- choose and back

def test_choose_asks_first_and_changes_only_which_round_is_chosen(rig):
    rig.finish_rounds(2)
    files = sorted(str(p) for p in Path(rig.paths.run).rglob("*") if p.is_file())
    code, io = rig.run("choose", "1", "--project", "anna", answers=["no"])
    assert code == 2 and rd.load(rig.paths).current == 2 and "Every round and all their files stay where they are" in io.prompts[0]
    code, io = rig.run("choose", "1", "--project", "anna", answers=["yes"])
    assert code == 0 and rd.load(rig.paths).current == 1 and "Done. Round 1 is chosen." in io.lines and len(rd.load(rig.paths).rounds) == 2
    assert sorted(str(p) for p in Path(rig.paths.run).rglob("*") if p.is_file()) == files
    code, io = rig.run("choose", "1", "--project", "anna", answers=[], interactive=False)
    assert code == 0 and "already the chosen round" in io.text and io.prompts == []                     # nothing to ask: nothing to change


def test_choose_without_a_usable_number_lists_the_rounds_that_can_be_chosen(rig):
    code, io = rig.run("choose", "--project", "anna")
    assert code == 2 and "No round has a saved point" in io.text
    rig.world.run_round(version=0)
    rig.world.run_round(version=1, ends="failed")
    for argv in (("choose",), ("choose", "x"), ("choose", "1.5"), ("choose", "١"), ("choose", "1" * 7)):
        code, io = rig.run(*argv, "--project", "anna")
        assert code == 2 and "The rounds that can be chosen are: 1." in io.text, argv
    code, io = rig.run("choose", "-1", "--project", "anna")                      # a minus sign makes it an option, and an option that does not exist is refused
    assert code == 2 and "I do not know the option -1" in io.text and rd.load(rig.paths).current == 1


def test_choose_says_why_a_round_cannot_be_chosen(rig):
    rig.world.run_round(version=0)
    rig.world.run_round(version=1, ends="failed")
    for number, said in (("2", "did not end with a saved point"), ("9", "no round with that number")):
        code, io = rig.run("choose", number, "--project", "anna", "--yes")
        assert code == 1 and said in io.text and rd.load(rig.paths).current == 1, number


def test_choose_is_refused_while_a_round_runs(rig):
    rig.finish_rounds(2)
    plan = rig.world.begin()
    rd.attach_job(rig.paths, 3, rig.world.job_for(plan, "running").id)
    code, io = rig.run("choose", "1", "--project", "anna", "--yes")
    assert code == 1 and "already running" in io.text and rd.load(rig.paths).current == 2


def test_back_asks_with_both_round_numbers_and_chooses_the_one_before(rig):
    rig.finish_rounds(2)
    code, io = rig.run("back", "--project", "anna", answers=["no"])
    assert code == 2 and rd.load(rig.paths).current == 2 and io.prompts[0].startswith("Go back to round 1? Round 2 is chosen now, and it continued from round 1.")
    code, io = rig.run("back", "--project", "anna", answers=["yes"])
    assert code == 0 and rd.load(rig.paths).current == 1 and any(l.startswith("Done. Round 1 is chosen now. Round 2 is still in the list") for l in io.lines)
    assert os.path.isfile(rig.paths.run + "/lightning_logs/version_1/checkpoints/last.ckpt")


def test_back_with_nowhere_to_go_says_so_and_changes_nothing(rig):
    code, io = rig.run("back", "--project", "anna", "--yes")
    assert code == 1 and "no earlier round to go back to" in io.text
    rig.finish_rounds(1)
    before = rig.record_bytes()
    code, io = rig.run("back", "--project", "anna", "--yes")
    assert code == 1 and "no earlier round to go back to" in io.text and rig.record_bytes() == before


# ---------------------------------------------------------------- note

def test_a_note_is_shown_and_asked_about_before_it_is_saved(rig):
    rig.finish_rounds(1)
    code, io = rig.run("note", "1", "--text", "  clearer\non the  S sounds ", "--project", "anna", answers=["no"])
    assert code == 2 and rd.load(rig.paths).rounds[0].note == "" and "clearer on the S sounds" in io.prompts[0]
    code, io = rig.run("note", "1", "--text", "clearer on the S sounds", "--project", "anna", answers=["yes"])
    assert code == 0 and rd.load(rig.paths).rounds[0].note == "clearer on the S sounds" and "Done. The note on round 1 is saved." in io.lines
    code, io = rig.run("note", "1", "--text", "clearer on the S sounds", "--project", "anna", answers=[], interactive=False)
    assert code == 0 and "already has exactly that note" in io.text and io.prompts == []


def test_an_empty_text_removes_the_note_after_asking(rig):
    rig.finish_rounds(1)
    rd.set_note(rig.paths, 1, "old")
    code, io = rig.run("note", "1", "--text=", "--project", "anna", answers=["yes"])
    assert code == 0 and rd.load(rig.paths).rounds[0].note == "" and io.prompts[0].startswith("Remove the note on round 1?") and "The note on round 1 is removed" in io.text
    assert os.path.exists(rig.paths.rounds_previous)                                                    # the version with the note is kept beside it


def test_a_note_needs_a_round_and_its_words_and_a_round_that_exists(rig):
    rig.finish_rounds(1)
    for argv, said, code_wanted in ((("note", "--text", "x"), "Which round?", 2), (("note", "1"), "What should the note say?", 2), (("note", "x", "--text", "y"), "Which round?", 2),
                                    (("note", "5", "--text", "y", "--yes"), "no round with that number", 1)):
        code, io = rig.run(*argv, "--project", "anna")
        assert code == code_wanted and said in io.text and rd.load(rig.paths).rounds[0].note == "", argv


def test_a_note_longer_than_the_limit_is_cut_and_shown_as_it_will_be_saved(rig):
    rig.finish_rounds(1)
    code, io = rig.run("note", "1", "--text", "y" * 600, "--project", "anna", "--yes")
    assert code == 0 and rd.load(rig.paths).rounds[0].note == "y" * rd.MAX_NOTE


# ---------------------------------------------------------------- stopping with Ctrl+C

def test_ctrl_c_at_the_question_stops_cleanly_and_changes_nothing(rig):
    rig.world.dataset()
    code, io = rig.run(*start_args(), answers=[KeyboardInterrupt()])
    assert code == 1 and "Stopped." in io.text and "keeps running by itself" in io.text and rig.started == [] and rig.record_bytes() is None


# ---------------------------------------------------------------- the front itself

def test_the_front_runs_from_a_terminal_and_reads_nothing_it_was_not_asked_to(tmp_path):
    env = dict(os.environ, HOME=str(tmp_path), PYTHONPATH=str(TOOLS), PYTHONDONTWRITEBYTECODE="1")
    done = subprocess.run([sys.executable, "-m", "voice_studio.rounds", "help"], capture_output=True, text=True, env=env, cwd=str(tmp_path), timeout=60)
    assert done.returncode == 0 and "training rounds" in done.stdout and "keep" in done.stdout and done.stderr == ""
    done = subprocess.run([sys.executable, "-m", "voice_studio.rounds", "list"], capture_output=True, text=True, env=env, cwd=str(tmp_path), timeout=60)
    assert done.returncode == 2 and "No projects" in done.stdout or "no projects" in done.stdout.lower()
    assert not os.path.exists(tmp_path / "ack-voice-studio" / "projects")


def test_the_trainings_programs_are_looked_for_without_building_anything(tmp_path):
    registry = make_registry()
    found, state = front.training_environment(DataHome(str(tmp_path / "home")), registry)()
    assert found is None and state in ("absent", "not_buildable") and not os.path.exists(tmp_path / "home")


def test_a_chosen_place_counts_as_ready_only_with_a_marker_that_names_this_very_project(tmp_path):
    from dataclasses import replace
    from vs_startvoice_helpers import make_project
    from voice_studio.core.project import SCRATCH_CUSTOM, Scratch
    place = tmp_path / "usb"
    place.mkdir()
    project = replace(make_project(id="ben", name="Ben"), scratch=Scratch(SCRATCH_CUSTOM, str(place)))
    paths = ProjectPaths(str(tmp_path / "projects" / "ben"))
    folder = place / "ack-voice-scratch" / "ben"
    assert rf.scratch_ready(project, paths) is False                                         # nothing there: an unplugged drive
    folder.mkdir(parents=True)
    assert rf.scratch_ready(project, paths) is False                                         # a folder with no marker
    (folder / MARKER_NAME).write_text(marker_text("anna"))
    assert rf.scratch_ready(project, paths) is False                                         # the marker names someone else
    (folder / MARKER_NAME).write_text("not json")
    assert rf.scratch_ready(project, paths) is False
    (folder / MARKER_NAME).write_text(marker_text("ben"))
    assert rf.scratch_ready(project, paths) is True and rf.scratch_root(project, paths).root == str(folder)
    assert rf.scratch_ready(replace(project, scratch=Scratch(SCRATCH_CUSTOM, None)), paths) is False        # custom, but no place named
    assert rf.scratch_ready(replace(project, scratch=Scratch("default", None)), paths) is True
    assert rf.scratch_root(replace(project, scratch=Scratch(SCRATCH_CUSTOM, None)), paths).root == paths.default_scratch


def test_a_marker_that_cannot_be_read_does_not_make_a_place_ready(tmp_path):
    from dataclasses import replace
    from vs_startvoice_helpers import make_project
    from voice_studio.core.project import SCRATCH_CUSTOM, Scratch
    place = tmp_path / "usb"
    folder = place / "ack-voice-scratch" / "ben"
    folder.mkdir(parents=True)
    project = replace(make_project(id="ben", name="Ben"), scratch=Scratch(SCRATCH_CUSTOM, str(place)))
    paths = ProjectPaths(str(tmp_path / "projects" / "ben"))
    (folder / MARKER_NAME).mkdir()                                                           # a folder where the file should be
    assert rf.scratch_ready(project, paths) is False
    (folder / MARKER_NAME).rmdir()
    (folder / MARKER_NAME).write_bytes(b"\xff\xfe\x00")
    assert rf.scratch_ready(project, paths) is False


def ended_since(rig):
    plan = rig.world.begin()
    info = rig.world.job_for(plan, "running")
    rd.attach_job(rig.paths, 1, info.id)
    rig.world.trainer_makes(0)
    end_job(info.dir, "finished", ended_at=stamp(20))
    assert rd.load(rig.paths).rounds[0].state == "running"


@pytest.mark.parametrize("argv", [("note", "1", "--text", "x", "--yes"), ("stop", "--yes"), ("choose", "1", "--yes"), ("back", "--yes")])
def test_every_command_that_changes_something_first_writes_down_what_has_ended_since_and_says_so(rig, argv):
    ended_since(rig)
    code, io = rig.run(*argv, "--project", "anna")
    assert "Noticed: round 1 is now: Finished." in io.lines, (argv, io.lines)
    assert rd.load(rig.paths).rounds[0].state == "finished" and rd.load(rig.paths).current == 1


def test_looking_says_nothing_about_what_it_would_have_written(rig):
    ended_since(rig)
    for argv in (("list",), ("keep",)):
        code, io = rig.run(*argv, "--project", "anna")
        assert code == 0 and "Noticed" not in io.text, argv


def test_a_round_that_has_only_started_running_is_not_announced(rig):
    plan = rig.world.begin()
    rig.world.job_for(plan, "running")                                                         # its job exists; the record does not know the name yet
    code, io = rig.run("stop", "--project", "anna", "--yes")
    assert code == 0 and "Noticed" not in io.text and "Asked round 1 to stop" in io.text


def test_keep_and_list_leave_a_record_that_is_behind_exactly_as_it_is(rig):
    ended_since(rig)
    before = rig.record_bytes()
    for argv in (("keep",), ("list",)):
        assert rig.run(*argv, "--project", "anna")[0] == 0 and rig.record_bytes() == before, argv
    assert rd.load(rig.paths).rounds[0].state == "running"


def test_a_round_with_no_saved_point_says_why_it_ended_and_does_not_also_say_it_has_no_saved_point(rig):
    rig.world.run_round(version=0, ends="failed")
    code, io = rig.run("list", "--project", "anna")
    assert "  The training program ended with an error." in io.lines and not any("saved point" in l and l.startswith("  ") for l in io.lines)


def test_the_training_time_shown_is_that_of_the_chosen_round_not_of_the_last_one(rig):
    rig.finish_rounds(2)
    assert rig.run("back", "--project", "anna", "--yes")[0] == 0
    code, io = rig.run("list", "--project", "anna")
    assert any(l.startswith("Chosen: round 1.") and "About 25 minutes of training" in l for l in io.lines), io.lines
    assert "Round 1 (chosen): Finished." in io.lines and "Round 2: Finished." in io.lines


def test_a_running_round_is_not_told_to_start_another_and_keep_gives_the_real_sizes(rig):
    rig.finish_rounds(3)
    rig.world.trainer_makes(9)                                                                 # there before the next round began
    plan = rig.world.begin()
    rd.attach_job(rig.paths, 4, rig.world.job_for(plan, "running").id)
    rig.world.trainer_makes(10)
    code, io = rig.run("list", "--project", "anna")
    assert "To train another round" not in io.text and any("Round 4 is running now" in l for l in io.lines)
    from voice_studio.core.text import size_text
    kept = rd.retention(rig.paths, rd.load(rig.paths))
    code, io = rig.run("keep", "--project", "anna")
    assert "Kept for sure (2 files, %s)" % size_text(sum(f.size for n, f in kept.keep)) in io.text and size_text(0) not in io.text
    assert "Spare (%d files, %s)" % (len(kept.spare), size_text(sum(f.size for n, f in kept.spare))) in io.text
    assert "In use by the running round (3 files): never touched." in io.lines
    assert "Not made by a round of this tool (3 files, %s): left alone and never offered." % size_text(sum(f.size for f in kept.unclaimed)) in io.lines


def test_while_the_first_round_runs_the_answer_is_that_a_round_is_running_not_that_a_voice_is_missing(tmp_path):
    rig = Rig(tmp_path, voice=False)
    plan = rig.world.begin()
    rd.attach_job(rig.paths, 1, rig.world.job_for(plan, "running").id)
    code, io = rig.run(*start_args("--yes"))
    assert code == 1 and "already running" in io.text and "no starting voice" not in io.text and rig.started == []


def test_the_training_set_named_is_the_one_the_round_trains_on_not_the_first_in_the_list(rig):
    rig.world.dataset("dataset-a")
    rig.world.dataset("dataset-b")
    code, io = rig.run(*start_args("--yes", dataset="dataset-b"))
    spec = rig.started[0]
    assert code == 0 and spec.argv[spec.argv.index("--data.csv_path") + 1] == rig.world.scratch.datasets + "/dataset-b/metadata.csv"
    assert rd.load(rig.paths).rounds[0].dataset == "dataset-b" and "dataset-b, which has 1 clips" in io.text


def test_back_with_nowhere_to_go_does_not_ask_a_question_first(rig):
    rig.finish_rounds(1)
    code, io = rig.run("back", "--project", "anna", answers=["yes"])
    assert code == 1 and io.prompts == [] and "no earlier round to go back to" in io.text


def test_a_note_goes_on_the_round_it_was_written_for(rig):
    rig.finish_rounds(2)
    assert rig.run("note", "2", "--text", "this one", "--project", "anna", "--yes")[0] == 0
    assert [r.note for r in rd.load(rig.paths).rounds] == ["", "this one"]
    assert rig.run("note", "1", "--text", "that one", "--project", "anna", "--yes")[0] == 0
    assert [r.note for r in rd.load(rig.paths).rounds] == ["that one", "this one"]


def test_a_starting_voice_the_tool_does_not_know_is_refused_in_words_and_nothing_starts(tmp_path):
    rig = Rig(tmp_path, voice=False)
    rig.world.dataset()
    save_project(rig.paths, with_starting_voice(load_project(rig.paths), "voice-zzz"))
    code, io = rig.run(*start_args("--yes"))
    assert code == 1 and rig.started == [] and rig.record_bytes() is None and "Traceback" not in io.text and "Nothing was" in io.text
