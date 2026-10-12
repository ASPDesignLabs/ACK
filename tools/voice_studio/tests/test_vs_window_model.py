# SPDX-License-Identifier: GPL-3.0-or-later
"""What the window shows and asks for (core/windowmodel.py): plain data from the same files the terminal reads, words from the catalog, nothing written, and a button that is the words of
the terminal command. A few tests run a real flow through the bridge with a scripted Yes or No, which is exactly what the window does."""
import os
import threading
from pathlib import Path

import pytest

from vs_rounds_helpers import DATASET, NOW, slurp
from vs_voicefile_helpers import ProjectRig, TOOLS, finished_rounds, tree_of, write_settings
from voice_studio.core import freeup, rounds as rd, rounds_flow as rf, text, windowio as wio, windowmodel as wm
from voice_studio.core.project import create_project
from voice_studio.core.text import size_text

CAT = text.load_catalog("en")


@pytest.fixture
def rig(tmp_path):
    return ProjectRig(tmp_path)


def services(rig):
    return wm.Services(rig.home, None, CAT, rig.training_env, rig.system, str(TOOLS))


# ---------------------------------------------------------------- projects

def test_the_projects_are_listed_with_the_terminals_own_sentence(rig):
    view = wm.projects_view(rig.home, CAT)
    assert [i.id for i in view.items] == ["voice-check"] and view.problems == () and view.folder == rig.home.projects
    assert view.items[0].line == "voice-check: Voice check, own voice, about 1 hours planned. Starting voice: not chosen yet."


def test_a_project_file_that_cannot_be_used_is_said_and_left_alone(tmp_path):
    rig = ProjectRig(tmp_path)
    create_project(rig.home.projects, "Second one", "own")
    broken = rig.home.projects + "/second-one/project.json"
    Path(broken).write_text("{broken")
    before = tree_of(rig.home.projects)
    view = wm.projects_view(rig.home, CAT)
    assert [i.id for i in view.items] == ["voice-check"] and len(view.problems) == 1 and "second-one" in view.problems[0]
    assert tree_of(rig.home.projects) == before and Path(broken).read_text() == "{broken"


def test_no_projects_is_an_empty_view_not_an_error(tmp_path):
    from voice_studio.core.paths import DataHome
    view = wm.projects_view(DataHome(str(tmp_path / "nobody")), CAT)
    assert view.items == () and view.problems == ()


# ---------------------------------------------------------------- rounds

def test_a_project_with_no_rounds_says_so_and_cannot_start_until_it_has_a_training_set(rig):
    view = wm.rounds_view(rig.home, "voice-check", CAT)
    assert view.items == () and view.running is None and view.back_target is None and view.sets == () and not view.can_start and view.problem == ""
    assert view.summary == ("There are no rounds yet. The first round starts from the starting voice.",
                            "No round is chosen yet, so the next round starts from the starting voice.")
    rig.world.dataset()
    assert wm.rounds_view(rig.home, "voice-check", CAT).sets == (DATASET,) and wm.rounds_view(rig.home, "voice-check", CAT).can_start


def test_each_round_is_described_by_the_terminals_own_lines_and_only_a_whole_other_round_can_be_chosen(rig):
    rig.finish(3)
    view = wm.rounds_view(rig.home, "voice-check", CAT)
    record = rd.load(rig.paths)
    assert [i.number for i in view.items] == [1, 2, 3] and [i.chosen for i in view.items] == [False, False, True]
    assert [i.can_choose for i in view.items] == [True, True, False]
    for item, r in zip(view.items, record.rounds):
        assert item.lines == tuple(rf.round_lines(r, r.number == record.current, rig.paths, CAT))
    assert view.items[2].lines[0] == "Round 3 (chosen): Finished." and view.back_target == 2
    assert view.summary == ("Chosen: round 3. The next round continues from it. About %d minutes of training so far." % rd.trained_minutes(record, 3),)


def test_a_round_whose_saved_point_is_not_whole_cannot_be_chosen(rig):
    rig.finish(2)
    os.unlink(rd.checkpoint_file(rig.paths, rd.find(rd.load(rig.paths), 1)))
    assert [i.can_choose for i in wm.rounds_view(rig.home, "voice-check", CAT).items] == [False, False]


def test_while_a_round_trains_nothing_can_be_chosen_or_started_and_the_window_says_which_round(rig):
    rig.finish(2)
    rig.world.dataset()
    plan = rig.world.begin()
    rd.attach_job(rig.paths, plan.number, rig.world.job_for(plan, "running").id)
    view = wm.rounds_view(rig.home, "voice-check", CAT)
    assert view.running == 3 and not any(i.can_choose for i in view.items) and view.back_target is None and not view.can_start
    assert "Round 3 is training now." in view.summary


def test_a_round_cannot_start_while_the_chosen_place_for_working_files_is_not_ready(rig, tmp_path):
    from voice_studio.core.project import load_project, save_project, with_scratch_place
    from voice_studio.core.scratch import MARKER_NAME, marker_text
    folder = tmp_path / "usb" / "ack-voice-scratch" / "voice-check"
    (folder / "datasets" / "dataset-x").mkdir(parents=True)
    save_project(rig.paths, with_scratch_place(load_project(rig.paths), str(tmp_path / "usb")))
    view = wm.rounds_view(rig.home, "voice-check", CAT)
    assert view.sets == ("dataset-x",) and view.can_start is False                                   # a training set is there, but nothing says the drive is this project's
    (folder / MARKER_NAME).write_text(marker_text("voice-check"))
    assert wm.rounds_view(rig.home, "voice-check", CAT).can_start is True


def test_the_training_sets_are_the_real_folders_with_safe_names_and_links_are_left_out(rig, tmp_path):
    rig.world.dataset("dataset-b")
    rig.world.dataset("dataset-a")
    outside = tmp_path / "outside"
    outside.mkdir()
    os.symlink(str(outside), rig.world.scratch.datasets + "/linked")
    os.makedirs(rig.world.scratch.datasets + "/has space")
    open(rig.world.scratch.datasets + "/loose-file", "w").close()
    assert wm.rounds_view(rig.home, "voice-check", CAT).sets == ("dataset-a", "dataset-b")


def test_a_record_that_cannot_be_read_is_said_in_plain_words_and_nothing_else_is_shown(rig):
    rig.finish(1)
    Path(rig.paths.rounds_file).write_text("{broken")
    view = wm.rounds_view(rig.home, "voice-check", CAT)
    assert view.problem and view.items == () and not view.can_start and Path(rig.paths.rounds_file).read_text() == "{broken"
    assert wm.free_view(rig.home, "voice-check", CAT).problem == view.problem


def test_looking_at_the_rounds_writes_nothing_even_when_a_round_has_ended_since(rig):
    rig.finish(1)
    plan = rig.world.begin()
    info = rig.world.job_for(plan, "running")
    rd.attach_job(rig.paths, plan.number, info.id)
    rig.world.trainer_makes(1)
    from vs_rounds_helpers import end_job, stamp
    end_job(info.dir, "finished", ended_at=stamp(20))
    before = {p: slurp(p) for p in tree_of(rig.paths.root)}
    view = wm.rounds_view(rig.home, "voice-check", CAT, now=NOW)
    assert view.running is None and view.items[-1].lines[0] == "Round 2 (chosen): Finished."          # shown as it really is now (a whole saved point is chosen), in memory only
    assert {p: slurp(p) for p in tree_of(rig.paths.root)} == before and rd.load(rig.paths).rounds[1].state == "running"


def test_an_unknown_project_is_none_everywhere(rig):
    assert wm.rounds_view(rig.home, "nobody", CAT) is None and wm.voicefiles_view(rig.home, "nobody", CAT) is None and wm.free_view(rig.home, "nobody", CAT) is None
    assert wm.open_project(rig.home, "nobody") is None and wm.find_project(rig.home, "nobody") is None


# ---------------------------------------------------------------- voice files and freeing space

def test_the_voice_files_made_before_are_listed_with_their_size_and_place(rig):
    rig.finish(2)
    assert wm.voicefiles_view(rig.home, "voice-check", CAT).items == ()
    from voice_studio.core import voicefile as vf
    made = vf.make_voice(vf.plan_voice(rig.paths, rd.load(rig.paths), "voice-check", "2026-10-11T13:00:00Z", None), rig.training, str(TOOLS), rig.system)
    view = wm.voicefiles_view(rig.home, "voice-check", CAT)
    item = view.items[0]
    assert item.zip_path == made.zip_path and item.folder == made.folder and item.line == "%s: %s" % (os.path.basename(made.folder), size_text(made.zip_bytes))
    assert view.exports == rig.paths.exports


def test_what_could_be_freed_is_the_terminals_list_with_the_option_each_row_goes_under(rig):
    rig.finish(3)
    folder = rd.cache_dir_for(rig.world.scratch, DATASET, 1)
    os.makedirs(folder + "/train")
    Path(folder + "/train/a.pt").write_bytes(b"c" * 100)
    view = wm.free_view(rig.home, "voice-check", CAT)
    plan = freeup.plan(rig.paths, rig.world.scratch, rd.load(rig.paths))
    assert [(i.kind, i.round, i.bytes, i.gives_up_saved_point) for i in view.items] == [("saved", 1, plan.offers[0].bytes, True), ("saved", 2, plan.offers[1].bytes, False),
                                                                                         ("saved", 3, plan.offers[2].bytes, False), ("working", 1, 100, False)]
    assert [i.line for i in view.items] == [rf.free_row_text(o, CAT) for o in plan.offers]
    assert view.notes[-1] == "Recordings, notes, the project file, backups, exports and the starting voices are never on this list."
    assert any(n.startswith("Kept for sure, never on this list: 2 files") for n in view.notes) and view.problem == ""


def test_what_is_in_use_and_what_is_not_ours_is_counted_in_the_notes_and_never_offered(rig):
    rig.finish(1)
    rig.world.trainer_makes(7)                                                   # a folder no round made
    rig.world.dataset()
    plan = rig.world.begin()
    rd.attach_job(rig.paths, plan.number, rig.world.job_for(plan, "running").id)
    rig.world.trainer_makes(1)                                                   # the running round's own
    view = wm.free_view(rig.home, "voice-check", CAT)
    assert "Not touched: 3 files of the round that is running." in view.notes and "Not touched: 3 files in a folder that no round of this tool made." in view.notes
    assert not any(i.round == 2 for i in view.items)


def test_with_nothing_to_free_the_list_is_empty_and_still_says_what_is_never_offered(rig):
    view = wm.free_view(rig.home, "voice-check", CAT)
    assert view.items == () and view.notes == ("Recordings, notes, the project file, backups, exports and the starting voices are never on this list.",)


# ---------------------------------------------------------------- what the buttons ask for

def test_each_button_is_the_words_of_a_terminal_command():
    assert wm.choose_args("anna", 2) == ("rounds", ["choose", "2", "--project", "anna"])
    assert wm.back_args("anna") == ("rounds", ["back", "--project", "anna"])
    assert wm.stop_args("anna") == ("rounds", ["stop", "--project", "anna"])
    assert wm.start_args("anna", "dataset-1") == ("rounds", ["start", "--set", "dataset-1", "--project", "anna"])
    assert wm.start_args("anna", "dataset-1", 25) == ("rounds", ["start", "--set", "dataset-1", "--minutes", "25", "--project", "anna"])
    assert wm.make_args("anna") == ("voicefile", ["make", "--project", "anna"])
    assert wm.note_args("anna", 3, "first try") == ("rounds", ["note", "3", "--text=first try", "--project", "anna"])
    assert wm.note_args("anna", 3, "-starts with a dash") == ("rounds", ["note", "3", "--text=-starts with a dash", "--project", "anna"])
    assert wm.note_args("anna", 3, "") == ("rounds", ["note", "3", "--text=", "--project", "anna"])


def test_the_free_command_names_each_kind_by_its_rounds_once_and_in_order():
    items = [wm.FreeItem("saved", 3, "", 1, False), wm.FreeItem("working", 2, "", 1, False), wm.FreeItem("saved", 1, "", 1, True), wm.FreeItem("saved", 3, "", 1, False)]
    assert wm.free_args("anna", items) == ("rounds", ["free", "--saved", "1,3", "--working", "2", "--project", "anna"])
    assert wm.free_args("anna", items[1:2]) == ("rounds", ["free", "--working", "2", "--project", "anna"])
    assert wm.free_args("anna", items[2:3]) == ("rounds", ["free", "--saved", "1", "--project", "anna"])


# ---------------------------------------------------------------- a real flow, asked the way the window asks

class Script:
    """A sink that answers like a person: the next Yes or No in the list, on a thread of its own."""

    def __init__(self, *answers):
        self.answers, self.questions, self.said, self.done = list(answers), [], [], threading.Event()
        self.result = None

    def line(self, text):
        self.said.append(text)

    def confirm(self, lines, question, reply):
        self.questions.append((lines, question))
        answer = self.answers.pop(0)
        threading.Timer(0.01, lambda: reply(answer)).start()

    def ask(self, lines, prompt, reply):
        raise AssertionError("no typed answer is expected")

    def finished(self, code, lines):
        self.result = (code, lines)
        self.done.set()


def press(rig, button, sink):
    tool, argv = button
    svc = services(rig)
    wio.start_run(lambda io: svc.run(tool, argv, io), sink, svc.titles())
    assert sink.done.wait(10)
    return sink.result


def test_choosing_a_round_shows_the_question_with_buttons_and_only_a_yes_changes_the_record(rig):
    rig.finish(3)
    before = slurp(rig.paths.rounds_file)
    sink = Script(False)
    code, lines = press(rig, wm.choose_args("voice-check", 1), sink)
    assert code == 2 and slurp(rig.paths.rounds_file) == before and lines[-1] == "Nothing was done."
    assert sink.questions == [((), "Choose round 1? The next round will continue from it. Nothing is deleted.")]
    sink = Script(True)
    code, lines = press(rig, wm.choose_args("voice-check", 1), sink)
    assert code == 0 and rd.load(rig.paths).current == 1 and "Done." in " ".join(lines)


def test_freeing_space_shows_what_it_will_remove_in_the_question_and_removes_only_that(rig):
    rig.finish(3)
    files = [f.path for n, f in rd.retention(rig.paths, rd.load(rig.paths)).spare if n == 1]
    items = wm.free_view(rig.home, "voice-check", CAT).items
    sink = Script(True)
    code, lines = press(rig, wm.free_args("voice-check", [i for i in items if i.round == 1]), sink)
    assert code == 0 and not any(os.path.exists(p) for p in files)
    assert sink.questions[0][0][0] == "This removes:" and sink.questions[0][1].startswith("Remove all of that, about ") and "Type yes" not in sink.questions[0][1]
    assert rd.checkpoint_status(rig.paths, rd.chosen(rd.load(rig.paths))) == "ok"


def test_making_the_voice_file_asks_with_the_plan_in_view_and_a_no_makes_nothing(rig):
    rig.finish(2)
    sink = Script(False)
    code, lines = press(rig, wm.make_args("voice-check"), sink)
    assert code == 2 and rig.exports() == [] and sink.questions[0][0][0] == "The voice file would be made like this:" and sink.questions[0][1] == "Make the voice file from round 2 now?"
    sink = Script(True)
    code, lines = press(rig, wm.make_args("voice-check"), sink)
    assert code == 0 and len(rig.exports()) == 1 and any(l.startswith("Done. The file to give to ACK is: ") for l in lines)
    assert wm.voicefiles_view(rig.home, "voice-check", CAT).items[0].name == rig.exports()[0]


def test_a_refusal_comes_back_as_words_and_asks_nothing(rig):
    sink = Script()
    code, lines = press(rig, wm.make_args("voice-check"), sink)
    assert code == 1 and sink.questions == [] and "No round is chosen yet, so there is no voice to make a file from." in " ".join(lines)


def test_an_unknown_tool_is_refused_loudly(rig):
    with pytest.raises(ValueError):
        services(rig).run("nothing", [], wio.ChannelIO(Script()))
