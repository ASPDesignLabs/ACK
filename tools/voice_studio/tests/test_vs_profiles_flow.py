# SPDX-License-Identifier: GPL-3.0-or-later
"""The terminal front for managing profiles: edit, archive, unarchive, delete. Held to: nothing changes without a yes, what would change is shown before the question, a delete asks twice and
the second question is never skipped by --yes, a delete names what goes and what to copy first, a task that is running stops it before any question, a profile that is put away is not used
by any command that changes things, and a window's Yes and No buttons answer the very same questions."""
import json
import os

import pytest

from vs_fakes import FakeSystem
from vs_rounds_helpers import fake_job
from vs_startvoice_helpers import NOW, Terminal, leaked_keys
from voice_studio.core import profiles as prof
from voice_studio.core import projects_flow as pf
from voice_studio.core import text
from voice_studio.core.paths import DataHome, ProjectPaths
from voice_studio.core.project import Consent, create_project, load_project, save_project, with_archived
from voice_studio.core.registry import load_registry

CAT = text.load_catalog("en")
GIB = 2 ** 30
FULL = Consent("Ben's mother", "recording Ben's voice", "9 Oct 2026", "tell me and we delete it", "spoken")


class Buttons(Terminal):
    """The window's side of a flow: a question is a Yes and a No button (`confirm`), never a typed word."""

    def __init__(self, answers=(), interactive=True):
        super().__init__(answers, interactive)
        self.asked = []
        self.before_answer = None

    def confirm(self, prompt):
        self.asked.append(prompt)
        if self.before_answer is not None:
            self.before_answer(len(self.asked))
        return self.answers.pop(0) if self.answers else None


@pytest.fixture
def home(tmp_path):
    return DataHome(str(tmp_path / "home"))


def system_for(home):
    return FakeSystem(disks={home.home: (1000 * GIB, 500 * GIB)})


def go(home, *argv, answers=(), interactive=True, io=None):
    io = io or Terminal(answers, interactive)
    code = pf.run_projects(list(argv), system_for(home), home, load_registry(), CAT, io, NOW)
    assert leaked_keys(io.text + "\n".join(io.prompts) + "\n".join(getattr(io, "asked", []))) == [], "a catalog key was printed instead of words"
    return code, io


def load(home, project_id):
    return load_project(ProjectPaths(home.projects + "/" + project_id))


def paths_of(home, project_id):
    return ProjectPaths(home.projects + "/" + project_id)


def put(path, size=10):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as handle:
        handle.write(b"x" * size)


def fill(paths):
    put(paths.recordings + "/_freeform/en-US/takes/t1/raw.wav", 2048)
    put(paths.rounds + "/rounds.json", 100)
    put(paths.exports + "/anna-round-001/anna-round-001.zip", 4096)


def exists(home, project_id):
    return os.path.isfile(paths_of(home, project_id).project_json)


# ---------------------------------------------------------------- help

def test_help_names_the_new_commands_and_their_options(home):
    code, io = go(home, "help")
    assert code == 0 and io.prompts == []
    for command in ("edit [name]:", "archive [name]:", "unarchive [name]:", "delete [name]:", "list --away:"):
        assert command in io.text, command
    assert "--how-given-other" in io.text


# ---------------------------------------------------------------- edit

def test_edit_with_nothing_to_change_says_so_and_does_nothing(home):
    create_project(home.projects, "Anna", "own")
    before = open(paths_of(home, "anna").project_json, "rb").read()
    code, io = go(home, "edit", "anna")
    assert code == 2 and "Nothing was given to change" in io.text and io.prompts == []
    assert open(paths_of(home, "anna").project_json, "rb").read() == before


def test_edit_shows_what_changes_before_it_asks_and_a_no_changes_nothing(home):
    create_project(home.projects, "Anna", "own", planned_hours=1)
    before = open(paths_of(home, "anna").project_json, "rb").read()
    code, io = go(home, "edit", "anna", "--name", "Anna B", "--hours", "2,5", answers=["no"])
    assert code == 2 and io.prompts == ["Save these changes? Type yes to save them. "]
    assert "These details of anna would change:" in io.text and "  Name: from Anna to Anna B" in io.lines and "  Planned hours: from 1 to 2.5" in io.lines
    assert io.events.index(("say", "  Name: from Anna to Anna B")) < io.events.index(("ask", io.prompts[0])) and "Nothing was changed." in io.text
    assert open(paths_of(home, "anna").project_json, "rb").read() == before


def test_edit_with_a_yes_saves_and_keeps_the_version_from_before(home):
    create_project(home.projects, "Anna", "own")
    before = open(paths_of(home, "anna").project_json, "rb").read()
    code, io = go(home, "edit", "anna", "--name=Anna B", answers=["yes"])
    assert code == 0 and "Saved. The details of anna are changed." in io.text
    assert load(home, "anna").name == "Anna B" and open(paths_of(home, "anna").previous_json, "rb").read() == before
    assert "The version from before is kept as " + paths_of(home, "anna").previous_json in io.text


def test_edit_with_yes_on_the_line_does_not_ask(home):
    create_project(home.projects, "Anna", "own")
    code, io = go(home, "edit", "anna", "--hours", "3", "--yes")
    assert code == 0 and io.prompts == [] and load(home, "anna").planned_hours == 3.0


def test_edit_nobody_to_ask_changes_nothing_and_says_how_to_say_yes(home):
    create_project(home.projects, "Anna", "own")
    code, io = go(home, "edit", "anna", "--name", "Zed", interactive=False)
    assert code == 2 and "--yes" in io.text and load(home, "anna").name == "Anna"


def test_edit_that_changes_nothing_says_so(home):
    create_project(home.projects, "Anna", "own", planned_hours=2)
    code, io = go(home, "edit", "anna", "--name", "Anna", "--hours", "2")
    assert code == 2 and "already has. Nothing was changed." in io.text and io.prompts == []


def test_edit_names_every_problem_and_changes_nothing(home):
    create_project(home.projects, "Ben", "someone_else", FULL)
    code, io = go(home, "edit", "ben", "--name", "  ", "--hours", "lots", "--withdraw", " ", "--yes")
    assert code == 2 and io.prompts == [] and "The details were not changed, because:" in io.text
    assert "Please type a name." in io.text and "Please type the hours as a number" in io.text and "This is needed before recording someone else's voice." in io.text
    assert load(home, "ben").name == "Ben" and load(home, "ben").consent == FULL


def test_edit_a_note_part_by_its_option_and_the_how_given_by_its_number(home):
    create_project(home.projects, "Ben", "someone_else", FULL)
    code, io = go(home, "edit", "ben", "--withdraw", "phone me", "--how-given", "3", "--yes")
    assert code == 0 and "  How they can change their mind: from tell me and we delete it to phone me" in io.lines
    assert "  How it was given: from They said so to Their guardian or supporter agreed for them" in io.lines
    assert load(home, "ben").consent.withdraw == "phone me" and load(home, "ben").consent.how_given == "through_guardian"


def test_edit_shows_an_empty_part_as_empty_not_as_a_blank(home):
    create_project(home.projects, "Anna", "own")
    code, io = go(home, "edit", "anna", "--given-by", "me", "--yes")
    assert code == 0 and "  Who agreed: from (empty) to me" in io.lines


def test_edit_with_an_option_it_does_not_know_does_nothing(home):
    create_project(home.projects, "Anna", "own")
    code, io = go(home, "edit", "anna", "--own")
    assert code == 2 and "--own" in io.text and "Nothing was done" in io.text


def test_edit_asks_a_window_with_buttons_not_a_typed_word(home):
    create_project(home.projects, "Anna", "own")
    io = Buttons([True])
    code, _ = go(home, "edit", "anna", "--name", "Anna B", io=io)
    assert code == 0 and io.asked == ["Save these changes? Type yes to save them."] and io.prompts == [] and load(home, "anna").name == "Anna B"
    io = Buttons([False])
    code, _ = go(home, "edit", "anna", "--name", "Zed", io=io)
    assert code == 2 and load(home, "anna").name == "Anna B"


def test_edit_does_not_use_a_profile_that_is_put_away(home):
    create_project(home.projects, "Anna", "own")
    save_project(paths_of(home, "anna"), with_archived(load(home, "anna"), True))
    code, io = go(home, "edit", "anna", "--name", "Zed", "--yes")
    assert code == 2 and "put away" in io.text and "unarchive anna" in io.text and load(home, "anna").name == "Anna"


# ---------------------------------------------------------------- put away and bring back

def test_putting_a_profile_away_asks_first_says_nothing_is_removed_and_changes_only_a_flag(home):
    create_project(home.projects, "Anna", "own")
    fill(paths_of(home, "anna"))
    code, io = go(home, "archive", "anna", answers=["no"])
    assert code == 2 and "Put Anna away? Nothing is removed." in io.prompts[0] and load(home, "anna").archived is False
    code, io = go(home, "archive", "anna", answers=["yes"])
    assert code == 0 and "Done. anna is put away. To bring it back, run: python3 -m voice_studio.projects unarchive anna" in io.text
    assert load(home, "anna").archived is True and os.path.isfile(paths_of(home, "anna").rounds + "/rounds.json")


def test_a_profile_that_is_put_away_leaves_the_list_and_is_found_with_the_away_option(home):
    create_project(home.projects, "Anna", "own")
    create_project(home.projects, "Ben", "own")
    go(home, "archive", "anna", "--yes")
    code, io = go(home, "list")
    assert code == 0 and any(l.startswith("  ben:") for l in io.lines) and not any(l.startswith("  anna:") for l in io.lines)
    assert "1 project is put away. To see it, run: python3 -m voice_studio.projects list --away" in io.text
    code, io = go(home, "list", "--away")
    assert code == 0 and "Projects that are put away:" in io.text and any(l.startswith("  anna:") for l in io.lines) and not any(l.startswith("  ben:") for l in io.lines)
    go(home, "archive", "ben", "--yes")
    code, io = go(home, "list")
    assert "Every project is put away." in io.text and "2 projects are put away" not in io.text
    assert go(home, "list", "--away")[1].text.count("put away") >= 1


def test_list_away_with_nothing_put_away_says_so(home):
    create_project(home.projects, "Anna", "own")
    code, io = go(home, "list", "--away")
    assert code == 0 and "No project is put away." in io.text


def test_no_command_that_changes_things_uses_a_profile_that_is_put_away_but_show_and_unarchive_do(home):
    create_project(home.projects, "Anna", "own")
    go(home, "archive", "anna", "--yes")
    code, io = go(home, "show", "anna")
    assert code == 0 and "This project is put away. Bring it back with: python3 -m voice_studio.projects unarchive anna" in io.text
    code, io = go(home, "unarchive", "anna", answers=["yes"])
    assert code == 0 and "Done. anna is back in the list." in io.text and load(home, "anna").archived is False


def test_when_one_profile_is_in_use_and_another_put_away_the_one_in_use_is_the_only_one_a_command_picks(home):
    create_project(home.projects, "Anna", "own")
    create_project(home.projects, "Ben", "own")
    go(home, "archive", "anna", "--yes")
    code, io = go(home, "edit", "--name", "Benny", "--yes")
    assert code == 0 and "Using the only project: ben." in io.text and load(home, "ben").name == "Benny" and load(home, "anna").name == "Anna"


def test_archiving_twice_and_bringing_back_what_is_not_away_change_nothing(home):
    create_project(home.projects, "Anna", "own")
    code, io = go(home, "unarchive", "anna")
    assert code == 2 and "anna is not put away. Nothing was changed." in io.text and io.prompts == []
    go(home, "archive", "anna", "--yes")
    code, io = go(home, "archive", "anna")
    assert code == 2 and "anna is already put away. Nothing was changed." in io.text and io.prompts == []


def test_a_profile_with_a_task_running_is_not_put_away(home):
    create_project(home.projects, "Anna", "own")
    os.makedirs(home.jobs)
    fake_job(home.jobs, ["x"], "running", project="anna")
    code, io = go(home, "archive", "anna", "--yes")
    assert code == 2 and "A task for Anna is still running." in io.text and load(home, "anna").archived is False


def test_putting_away_and_bringing_back_ask_a_window_with_buttons(home):
    create_project(home.projects, "Anna", "own")
    io = Buttons([True])
    assert go(home, "archive", "anna", io=io)[0] == 0 and io.asked[0].startswith("Put Anna away?") and io.prompts == []
    io = Buttons([False])
    assert go(home, "unarchive", "anna", io=io)[0] == 2 and io.asked[0].startswith("Bring Anna back?") and load(home, "anna").archived is True


def test_a_note_for_someone_elses_voice_is_kept_whole_through_putting_away_and_bringing_back(home):
    create_project(home.projects, "Ben", "someone_else", FULL)
    go(home, "archive", "ben", "--yes")
    go(home, "unarchive", "ben", "--yes")
    assert load(home, "ben").consent == FULL and load(home, "ben").archived is False


# ---------------------------------------------------------------- delete

def test_delete_shows_exactly_what_goes_and_what_to_copy_first_before_it_asks(home):
    create_project(home.projects, "Anna", "own")
    fill(paths_of(home, "anna"))
    code, io = go(home, "delete", "anna", answers=["no"])
    assert code == 2 and io.prompts == ["Delete the project Anna for good? Type yes to go on. "]
    assert "This would remove the project anna: Anna. It cannot be brought back." in io.text
    assert "  Recordings: 2.0 KB in 1 file" in io.lines and any(l.startswith("  Training rounds and their saved points:") for l in io.lines)
    assert "  Finished voice files: 4.1 KB in 1 file" in io.lines and sum(1 for l in io.lines if l.startswith("  The project's own record:")) == 1
    assert "Finished voice files that would go: anna-round-001. Copy any you want to keep somewhere else first." in io.text
    assert "Before you go on, copy anything you may want later. Nothing here can be brought back." in io.text
    assert io.events.index(("say", "Before you go on, copy anything you may want later. Nothing here can be brought back.")) < io.events.index(("ask", io.prompts[0]))
    assert "Nothing was removed." in io.text and exists(home, "anna") and os.path.isfile(paths_of(home, "anna").rounds + "/rounds.json")


def test_delete_with_no_finished_voice_file_says_so(home):
    create_project(home.projects, "Anna", "own")
    code, io = go(home, "delete", "anna", answers=["no"])
    assert "No finished voice file would go." in io.text


def test_delete_asks_twice_and_a_no_to_the_second_removes_nothing(home):
    create_project(home.projects, "Anna", "own")
    fill(paths_of(home, "anna"))
    code, io = go(home, "delete", "anna", answers=["yes", "no"])
    assert code == 2 and len(io.prompts) == 2 and io.prompts[1].startswith("Last question. Remove Anna, ") and "in 4 files, for good? Type yes to delete it." in io.prompts[1]
    assert exists(home, "anna") and os.path.isfile(paths_of(home, "anna").exports + "/anna-round-001/anna-round-001.zip")


def test_delete_after_two_yes_answers_removes_the_profile_and_no_other(home):
    create_project(home.projects, "Anna", "own")
    create_project(home.projects, "Ben", "own")
    fill(paths_of(home, "anna"))
    fill(paths_of(home, "ben"))
    code, io = go(home, "delete", "anna", answers=["yes", "yes"])
    assert code == 0 and "Done. The project anna is deleted. About " in io.text
    assert not os.path.lexists(paths_of(home, "anna").root) and exists(home, "ben") and os.path.isfile(paths_of(home, "ben").rounds + "/rounds.json")


def test_the_second_question_is_not_skipped_by_yes_on_the_line(home):
    create_project(home.projects, "Anna", "own")
    fill(paths_of(home, "anna"))
    code, io = go(home, "delete", "anna", "--yes", answers=["no"])
    assert code == 2 and len(io.prompts) == 1 and io.prompts[0].startswith("Last question.") and exists(home, "anna")
    code, io = go(home, "delete", "anna", "--yes", interactive=False)
    assert code == 2 and io.prompts == [] and "There was nobody to ask" in io.text and exists(home, "anna")
    code, io = go(home, "delete", "anna", "--yes", answers=["yes"])
    assert code == 0 and not os.path.lexists(paths_of(home, "anna").root)


def test_a_one_file_profile_reads_as_one_file(home):
    create_project(home.projects, "Anna", "own")
    os.unlink(paths_of(home, "anna").project_json + ".previous") if os.path.exists(paths_of(home, "anna").project_json + ".previous") else None
    code, io = go(home, "delete", "anna", answers=["yes", "no"])
    assert "in 1 file, for good?" in io.prompts[1] and "In all: " in io.text and " in 1 file." in io.text


def test_delete_stops_before_any_question_while_a_task_runs(home):
    create_project(home.projects, "Anna", "own")
    fill(paths_of(home, "anna"))
    os.makedirs(home.jobs)
    fake_job(home.jobs, ["x"], "running", project="anna")
    code, io = go(home, "delete", "anna", answers=["yes", "yes"])
    assert code == 2 and io.prompts == [] and "A task for this project is still running." in io.text and "Nothing was removed." in io.text and exists(home, "anna")


def test_if_something_changes_between_the_questions_nothing_is_removed(home):
    create_project(home.projects, "Anna", "own")
    fill(paths_of(home, "anna"))

    def add_a_recording(n):
        if n == 2:
            put(paths_of(home, "anna").recordings + "/_freeform/en-US/takes/t2/raw.wav", 5)
    io = Buttons([True, True])
    io.before_answer = add_a_recording
    code, io = go(home, "delete", "anna", io=io)
    assert code == 2 and "The project changed after the list was made." in io.text and "Nothing was removed." in io.text
    assert os.path.isfile(paths_of(home, "anna").recordings + "/_freeform/en-US/takes/t1/raw.wav") and exists(home, "anna")


def test_a_task_that_starts_between_the_questions_stops_the_delete(home):
    create_project(home.projects, "Anna", "own")
    fill(paths_of(home, "anna"))
    os.makedirs(home.jobs, exist_ok=True)

    def start_a_task(n):
        if n == 2:
            fake_job(home.jobs, ["x"], "running", project="anna")
    io = Buttons([True, True])
    io.before_answer = start_a_task
    code, io = go(home, "delete", "anna", io=io)
    assert code == 2 and "A task for this project is still running." in io.text and exists(home, "anna")


def test_delete_asks_a_window_with_buttons_twice(home):
    create_project(home.projects, "Anna", "own")
    fill(paths_of(home, "anna"))
    io = Buttons([True, True])
    code, _ = go(home, "delete", "anna", io=io)
    assert code == 0 and len(io.asked) == 2 and io.prompts == [] and not os.path.lexists(paths_of(home, "anna").root)


def test_a_delete_that_could_not_finish_says_what_is_left_and_the_profile_stays_listed(home, monkeypatch):
    create_project(home.projects, "Anna", "own")
    fill(paths_of(home, "anna"))
    real = prof._remove_tree

    def busy(path, failed):
        if path.endswith("/rounds"):
            failed.append((path, "Device or resource busy"))
            return
        real(path, failed)
    monkeypatch.setattr(prof, "_remove_tree", busy)
    code, io = go(home, "delete", "anna", answers=["yes", "yes"])
    assert code == 1 and "The project could not be removed completely. These could not be removed:" in io.text
    assert "  " + paths_of(home, "anna").rounds + ": Device or resource busy" in io.lines and "the project is still in the list" in io.text and exists(home, "anna")
    monkeypatch.setattr(prof, "_remove_tree", real)
    code, io = go(home, "delete", "anna", answers=["yes", "yes"])
    assert code == 0 and not os.path.lexists(paths_of(home, "anna").root)


def test_delete_can_remove_a_profile_that_is_put_away(home):
    create_project(home.projects, "Anna", "own")
    go(home, "archive", "anna", "--yes")
    code, io = go(home, "delete", "anna", answers=["yes", "yes"])
    assert code == 0 and not os.path.lexists(paths_of(home, "anna").root)


def test_delete_of_a_profile_that_is_not_there_names_the_ones_that_are(home):
    create_project(home.projects, "Anna", "own")
    code, io = go(home, "delete", "nobody", answers=["yes", "yes"])
    assert code == 2 and "There is no project called nobody. The projects are: anna." in io.text and io.prompts == [] and exists(home, "anna")


def test_delete_of_a_folder_that_is_a_link_is_refused_and_the_target_is_left(home, tmp_path):
    other = tmp_path / "elsewhere"
    put(str(other / "a.wav"), 5)
    create_project(home.projects, "Anna", "own")
    root = paths_of(home, "anna").root
    moved = tmp_path / "moved"
    os.rename(root, str(moved))
    os.symlink(str(moved), root)
    code, io = go(home, "delete", "anna", answers=["yes", "yes"])
    assert code == 2 and "not an ordinary project folder of this tool" in io.text and io.prompts == [] and (moved / "project.json").exists() and (other / "a.wav").exists()


def test_delete_names_a_scratch_folder_it_will_not_remove(home, tmp_path):
    project = create_project(home.projects, "Anna", "own")
    place = tmp_path / "bigdisk"
    place.mkdir()
    folder = str(place / "ack-voice-scratch" / "anna")
    put(folder + "/x", 3)
    open(folder + "/.ack-voice-scratch", "w").write(json.dumps({"schema": 1, "project": "someone-else"}) + "\n")
    from voice_studio.core.project import with_scratch_place
    save_project(paths_of(home, "anna"), with_scratch_place(project, str(place)))
    code, io = go(home, "delete", "anna", answers=["yes", "yes"])
    assert "This folder is not removed, because it does not carry this project's mark: " + folder in io.text and os.path.isfile(folder + "/x")
