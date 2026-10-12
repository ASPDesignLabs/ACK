# SPDX-License-Identifier: GPL-3.0-or-later
"""The terminal front for projects: list, show, new. What is held to here: nothing is made without a yes, the whole project is shown before the question,
every answer can be given as an option, a form that is not complete makes nothing and says why in words, and every sentence comes from the catalog."""
import os
import stat
from pathlib import Path

import pytest

from vs_fakes import FakeSystem
from vs_startvoice_helpers import NOW, Terminal, leaked_keys
from voice_studio import projects
from voice_studio.core import projects_flow as pf
from voice_studio.core import text
from voice_studio.core.text import size_text
from voice_studio.core.diskbudget import DEFAULT_TABLE
from voice_studio.core.paths import DataHome, ProjectPaths
from voice_studio.core.project import Consent, ProjectError, create_project, load_project
from voice_studio.core.registry import load_registry

CAT = text.load_catalog("en")
GIB = 2 ** 30
FULL = Consent("Ben's mother", "recording Ben's voice", "9 Oct 2026", "tell me and we delete it", "spoken")


@pytest.fixture
def home(tmp_path):
    return DataHome(str(tmp_path / "home"))


def system_for(home, free=500 * GIB):
    return FakeSystem(disks={home.home: (1000 * GIB, free)})


def go(home, *argv, answers=(), interactive=True, free=500 * GIB, system=None):
    io = Terminal(answers, interactive)
    code = pf.run_projects(list(argv), system or system_for(home, free), home, load_registry(), CAT, io, NOW)
    assert leaked_keys(io.text + "\n".join(io.prompts)) == [], "a catalog key was printed instead of words"
    return code, io


def made(home):
    try:
        return sorted(os.listdir(home.projects))
    except OSError:
        return []


def load(home, project_id):
    return load_project(ProjectPaths(home.projects + "/" + project_id))


# ---------------------------------------------------------------- help and mistakes

@pytest.mark.parametrize("argv", [(), ("help",), ("-h",), ("--help",)])
def test_help_lists_the_commands_and_asks_nothing(home, argv):
    code, io = go(home, *argv)
    assert code == 0 and io.prompts == []
    for command in ("list", "show", "new"):
        assert command + ":" in io.text or command + " [name]:" in io.text
    assert "--someone-else" in io.text and made(home) == []


def test_an_unknown_command_is_refused_by_name_and_nothing_is_done(home):
    code, io = go(home, "frobnicate")
    assert code == 2 and "frobnicate" in io.text and "Nothing was done" in io.text and made(home) == []
    long_name = "x" * 100
    assert "x" * 61 not in go(home, long_name)[1].text, "a pasted wall of text is not echoed back whole"


@pytest.mark.parametrize("argv, fragment", [(("list", "--nope"), "--nope"), (("list", "extra"), "extra"), (("show", "a", "b"), "b"), (("new", "--name"), "--name"),
                                            (("new", "--name", "A", "--name", "B"), "--name"), (("new", "--yes=1"), "--yes=1"), (("show", "--project", "x"), "--project")])
def test_an_option_or_word_that_is_not_understood_does_nothing_and_names_what_it_was(home, argv, fragment):
    code, io = go(home, *argv)
    assert code == 2 and fragment in io.text and "Nothing was done" in io.text and io.prompts == [] and made(home) == []


# ---------------------------------------------------------------- list

def test_list_with_no_projects_says_so_and_how_to_make_one(home):
    code, io = go(home, "list")
    assert code == 0 and "There are no projects yet." in io.text and "python3 -m voice_studio.projects new" in io.text


def test_list_shows_each_project_in_one_line(home):
    create_project(home.projects, "Anna", "own", planned_hours=1.5)
    create_project(home.projects, "Ben", "someone_else", FULL)
    code, io = go(home, "list")
    assert code == 0 and "Projects are kept in " + home.projects in io.text
    assert "  anna: Anna, own voice, about 1.5 hours planned. Starting voice: not chosen yet." in io.lines
    assert "  ben: Ben, someone else's voice, about 1 hours planned. Starting voice: not chosen yet." in io.lines


def test_list_shows_a_chosen_starting_voice(home):
    from voice_studio.core.project import save_project, with_starting_voice
    project = create_project(home.projects, "Anna", "own")
    save_project(ProjectPaths(home.projects + "/anna"), with_starting_voice(project, "voice-amy"))
    assert "Starting voice: voice-amy." in go(home, "list")[1].text


def test_a_damaged_project_is_named_and_left_exactly_as_it_is(home):
    create_project(home.projects, "Anna", "own")
    broken = home.projects + "/broken"
    os.mkdir(broken)
    with open(broken + "/project.json", "w") as handle:
        handle.write("{ not json")
    code, io = go(home, "list")
    assert code == 0 and "anna: Anna" in io.text and "left exactly as it is" in io.text and home.projects + "/broken" in io.text
    with open(broken + "/project.json") as handle:
        assert handle.read() == "{ not json"


# ---------------------------------------------------------------- show

def test_show_uses_the_only_project_and_says_so(home):
    create_project(home.projects, "Anna", "own", planned_hours=2)
    code, io = go(home, "show")
    assert code == 0 and "Using the only project: anna." in io.text
    for line in ("Project anna: Anna", "  Whose voice: own voice", "  Folder: " + home.projects + "/anna", "  Planned recording: about 2 hours",
                 "  Starting voice: not chosen yet", "  No starting voice has been acknowledged yet."):
        assert line in io.lines, line
    assert "The agreement" not in io.text, "an own-voice project has no agreement to show"


def test_show_by_name_does_not_say_it_chose_one_for_you(home):
    create_project(home.projects, "Anna", "own")
    create_project(home.projects, "Ben", "someone_else", FULL)
    code, io = go(home, "show", "ben")
    assert code == 0 and "Using the only" not in io.text and "Project ben: Ben" in io.text


def test_show_for_someone_elses_voice_lists_the_agreement(home):
    create_project(home.projects, "Ben", "someone_else", FULL)
    io = go(home, "show", "ben")[1]
    assert "  The agreement to use this voice:" in io.lines
    for line in ("Who agreed? Ben's mother", "What did they agree to? recording Ben's voice", "When did they agree? 9 Oct 2026",
                 "How can they change their mind? tell me and we delete it", "How was it given? They said so"):
        assert "    " + line in io.lines, line


def test_show_lists_each_acknowledgment_with_a_short_revision(home):
    from voice_studio.core.project import save_project, with_acknowledgment
    project = create_project(home.projects, "Anna", "own")
    save_project(ProjectPaths(home.projects + "/anna"), with_acknowledgment(project, "voice-mike", "0123456789abcdef0123456789abcdef01234567", NOW))
    io = go(home, "show", "anna")[1]
    assert "  Starting voices this project has acknowledged:" in io.lines
    assert "    voice-mike, on 2026-10-11T12:30:00Z, file 0123456789ab" in io.lines and "0123456789abc" not in io.text


def test_a_project_is_found_by_its_whole_name_only(home):
    create_project(home.projects, "Anna", "own")
    for wrong in ("ann", "Anna", "ANNA", "anna ", "an"):
        code, io = go(home, "show", wrong)
        assert code == 2 and "There is no project called" in io.text, wrong


def test_show_with_a_name_that_is_not_there_lists_the_ones_that_are(home):
    create_project(home.projects, "Anna", "own")
    code, io = go(home, "show", "bob")
    assert code == 2 and "There is no project called bob. The projects are: anna." in io.text
    code, io = go(home.__class__(home.home + "-empty"), "show", "bob")
    assert code == 2 and "no project called bob, and there are no projects yet" in io.text


def test_show_with_no_name_and_several_projects_asks_which(home):
    create_project(home.projects, "Anna", "own")
    create_project(home.projects, "Ben", "own")
    code, io = go(home, "show")
    assert code == 2 and "There is more than one project: anna, ben. Say which one you mean." in io.text


def test_show_with_no_projects_says_so(home):
    code, io = go(home, "show")
    assert code == 2 and "There are no projects yet." in io.text and "python3 -m voice_studio.projects new" in io.text


def test_show_of_a_damaged_project_says_so_and_does_not_touch_it(home):
    os.makedirs(home.projects + "/broken")
    with open(home.projects + "/broken/project.json", "w") as handle:
        handle.write("nope")
    code, io = go(home, "show", "broken")
    assert code == 2 and "cannot be used because its file is damaged" in io.text
    assert Path(home.projects + "/broken/project.json").read_text() == "nope"


def test_a_damaged_folder_does_not_stop_the_only_good_project_being_used(home):
    create_project(home.projects, "Anna", "own")
    os.makedirs(home.projects + "/broken")
    with open(home.projects + "/broken/project.json", "w") as handle:
        handle.write("nope")
    code, io = go(home, "show")
    assert code == 0 and "Using the only project: anna." in io.text


# ---------------------------------------------------------------- new: given as options

def test_new_with_every_answer_as_an_option_and_yes_makes_the_project(home):
    code, io = go(home, "new", "--own", "--name", "Anna Test", "--hours", "1,5", "--voice", "mike", "--yes", interactive=False)
    assert code == 0 and made(home) == ["anna-test"] and io.prompts == []
    project = load(home, "anna-test")
    assert (project.name, project.whose_voice, project.planned_hours, project.starting_voice) == ("Anna Test", "own", 1.5, "voice-mike")
    assert project.created == "2026-10-11T12:30:00Z" and project.acknowledgments == ()
    assert "Made the project anna-test." in io.lines and "Its folder is " + home.projects + "/anna-test" in io.lines
    assert "Next, see the starting voices: python3 -m voice_studio.voices list --project anna-test" in io.lines
    assert stat.S_IMODE(os.stat(home.projects + "/anna-test/project.json").st_mode) == 0o600


def test_making_a_project_does_not_acknowledge_a_voice_it_only_names_it(home):
    go(home, "new", "--own", "--name", "Anna", "--voice", "voice-amy", "--yes", interactive=False)
    project = load(home, "anna")
    assert project.starting_voice == "voice-amy" and project.acknowledgments == ()


def test_new_without_a_voice_leaves_it_for_later(home):
    go(home, "new", "--own", "--name", "Anna", "--yes", interactive=False)
    assert load(home, "anna").starting_voice is None and load(home, "anna").planned_hours == 1.0


def test_new_for_someone_else_with_the_whole_agreement_as_options(home):
    code, io = go(home, "new", "--someone-else", "--name", "Ben", "--given-by", "Ben's mother", "--agreed-to", "recording Ben's voice", "--when", "9 Oct 2026",
                  "--withdraw", "tell me and we delete it", "--how-given", "through-guardian", "--yes", interactive=False)
    assert code == 0
    assert load(home, "ben").consent == Consent("Ben's mother", "recording Ben's voice", "9 Oct 2026", "tell me and we delete it", "through_guardian", "")
    assert "    How was it given? Their guardian or supporter agreed for them" in io.lines


@pytest.mark.parametrize("typed, stored", [("1", "spoken"), ("2", "signed"), ("3", "through_guardian"), ("4", "using_aac"), ("5", "other"), ("spoken", "spoken"),
                                           ("Through-Guardian", "through_guardian"), (" using_aac ", "using_aac")])
def test_how_the_agreement_was_given_can_be_a_number_or_a_word(home, typed, stored):
    argv = ["new", "--someone-else", "--name", "Ben", "--given-by", "a", "--agreed-to", "b", "--when", "c", "--withdraw", "d", "--how-given", typed, "--yes"]
    if stored == "other":
        argv += ["--how-given-other", "by letter"]
    code, io = go(home, *argv, interactive=False)
    assert code == 0 and load(home, "ben").consent.how_given == stored


def test_the_summary_shows_the_agreement_as_it_will_be_saved(home):
    code, io = go(home, "new", "--someone-else", "--name", "Ben", "--given-by", "  Ben's   mother\n", "--agreed-to", "b", "--when", "c", "--withdraw", "d",
                  "--how-given", "spoken", "--yes", interactive=False)
    assert "    Who agreed? Ben's mother" in io.lines and load(home, "ben").consent.given_by == "Ben's mother"


def test_the_same_name_twice_makes_a_second_project_and_the_summary_says_its_folder_first(home):
    go(home, "new", "--own", "--name", "Anna", "--yes", interactive=False)
    code, io = go(home, "new", "--own", "--name", "Anna", "--yes", interactive=False)
    assert code == 0 and made(home) == ["anna", "anna-2"]
    assert "  Project anna-2: Anna" in io.lines and "Made the project anna-2." in io.lines


# ---------------------------------------------------------------- new: nothing without a yes

def test_without_yes_and_nobody_to_ask_nothing_is_made_and_it_says_how_to_say_yes(home):
    code, io = go(home, "new", "--own", "--name", "Anna", interactive=False)
    assert code == 2 and made(home) == [] and "add --yes" in io.text and "Nothing was done" in io.text
    assert "This is the project that would be made:" in io.text, "it still shows what it would have made"


def test_asking_shows_the_whole_project_first_and_a_yes_makes_it(home):
    code, io = go(home, "new", "--own", "--name", "Anna", "--hours", "2", answers=["yes"])
    kinds = [kind for kind, _ in io.events]
    summary = next(i for i, (kind, line) in enumerate(io.events) if line == "This is the project that would be made:")
    asked = kinds.index("ask")
    assert code == 0 and made(home) == ["anna"] and summary < asked and io.prompts == ["Make this project? Type yes to make it. "]
    shown_after_summary = [line for kind, line in io.events[summary:asked] if kind == "say"]
    assert any("Planned recording: about 2 hours" in line for line in shown_after_summary) and any("Folder: " in line for line in shown_after_summary)


@pytest.mark.parametrize("answer", ["no", "n", "", "yess", "ye", "maybe", "y e s", "yes please"])
def test_anything_but_yes_makes_nothing(home, answer):
    code, io = go(home, "new", "--own", "--name", "Anna", "--hours", "1", answers=[answer])
    assert code == 2 and made(home) == [] and "Nothing was made." in io.lines and io.prompts == ["Make this project? Type yes to make it. "]


@pytest.mark.parametrize("answer", ["yes", "YES", " Yes ", "y", "Y"])
def test_a_yes_in_any_capitals_or_just_y_makes_it(home, answer):
    assert go(home, "new", "--own", "--name", "Anna", "--hours", "1", answers=[answer])[0] == 0 and made(home) == ["anna"]


def test_no_answer_at_all_is_not_a_yes(home):
    code, io = go(home, "new", "--own", "--name", "Anna", answers=[])
    assert code == 2 and made(home) == [] and "add --yes" in io.text


def test_a_terminal_with_nobody_at_it_is_never_asked_even_if_answers_are_lying_about(home):
    code, io = go(home, "new", "--own", "--name", "Anna", interactive=False, answers=["yes", "yes", "yes"])
    assert code == 2 and made(home) == [] and io.prompts == []


# ---------------------------------------------------------------- new: asking for what is missing

def test_it_asks_one_question_at_a_time_for_what_was_left_out_and_only_that(home):
    code, io = go(home, "new", answers=["Anna", "1", "", "yes"])
    assert code == 0 and made(home) == ["anna"]
    assert io.prompts == ["What name should the project have? ", "Whose voice is this? Type 1 for your own voice, or 2 for someone else's. ",
                          "About how many hours of recording do you expect? Press Enter for 1. ", "Make this project? Type yes to make it. "]
    assert load(home, "anna").planned_hours == 1.0 and load(home, "anna").whose_voice == "own"


def test_what_was_given_as_an_option_is_not_asked_again(home):
    code, io = go(home, "new", "--name", "Anna", "--hours", "3", answers=["2", "a", "b", "c", "d", "1", "yes"])
    assert code == 0 and "What name" not in io.text + "".join(io.prompts) and not any("About how many hours" in p for p in io.prompts)
    assert load(home, "anna").planned_hours == 3.0 and load(home, "anna").whose_voice == "someone_else"


def test_the_hours_a_person_types_are_used_and_a_decimal_comma_is_fine(home):
    go(home, "new", "--own", "--name", "Anna", answers=["2,5", "yes"])
    assert load(home, "anna").planned_hours == 2.5


def test_for_someone_elses_voice_it_asks_each_part_of_the_agreement_then_how_it_was_given(home):
    answers = ["Ben", "2", "Ben's mother", "recording Ben's voice", "9 Oct 2026", "tell me and we delete it", "5", "by letter", "2", "yes"]
    code, io = go(home, "new", answers=answers)
    assert code == 0
    assert load(home, "ben").consent == Consent("Ben's mother", "recording Ben's voice", "9 Oct 2026", "tell me and we delete it", "other", "by letter")
    assert io.prompts[2:7] == ["Who agreed? ", "What did they agree to? ", "When did they agree? ", "How can they change their mind? ", "Type the number of the answer. "]
    for number, words in enumerate(("They said so", "They signed", "Their guardian or supporter agreed for them", "They said so using their communication device", "Another way"), 1):
        assert "  %d. %s" % (number, words) in io.lines
    assert io.prompts[7] == "Describe how it was given. "


def test_a_part_of_the_agreement_given_as_an_option_is_not_asked_for(home):
    answers = ["2", "recording Ben's voice", "9 Oct 2026", "tell me and we delete it", "1", "", "yes"]
    code, io = go(home, "new", "--name", "Ben", "--given-by", "Ben's mother", answers=answers)
    assert code == 0 and "Who agreed? " not in io.prompts and load(home, "ben").consent.given_by == "Ben's mother"


def test_how_it_was_given_is_not_asked_when_it_was_given_as_an_option(home):
    answers = ["recording Ben's voice", "9 Oct 2026", "tell me and we delete it", "2", "yes"]
    code, io = go(home, "new", "--name", "Ben", "--someone-else", "--given-by", "Ben's mother", "--how-given", "using-aac", answers=answers)
    assert code == 0 and "Type the number of the answer. " not in io.prompts and load(home, "ben").consent.how_given == "using_aac"
    assert "How was it given?" not in io.text.split("This is the project that would be made:")[0]


@pytest.mark.parametrize("answer, expected", [("1", "own"), ("own", "own"), ("Mine", "own"), ("2", "someone_else"), ("someone else", "someone_else"), ("Someone", "someone_else")])
def test_whose_voice_can_be_answered_with_a_number_or_a_word(home, answer, expected):
    answers = [answer] + (["a", "b", "c", "d", "1"] if expected == "someone_else" else []) + ["", "yes"]
    code, io = go(home, "new", "--name", "Pat", answers=answers)
    assert code == 0 and load(home, "pat").whose_voice == expected


def test_an_answer_that_is_not_one_of_the_choices_leaves_it_missing_and_makes_nothing(home):
    code, io = go(home, "new", "--name", "Pat", answers=["banana", ""])
    assert code == 2 and made(home) == [] and "Please choose whose voice this is." in io.text and "Nothing was made." in io.lines
    assert len(io.prompts) == 2, "it asked whose voice and the hours, once each, and did not keep asking"


def test_a_blank_name_when_asked_makes_nothing_and_does_not_ask_again(home):
    code, io = go(home, "new", answers=["", "1", ""])
    assert code == 2 and "Please type a name." in io.text and made(home) == [] and io.prompts.count("What name should the project have? ") == 1


def test_interrupting_a_question_makes_nothing_and_says_how_to_look(home):
    code, io = go(home, "new", answers=[KeyboardInterrupt()])
    assert code == 1 and made(home) == [] and "Stopped. To see what exists now, run: python3 -m voice_studio.projects list" in io.lines


# ---------------------------------------------------------------- new: a form that is not complete

def test_with_nobody_to_ask_every_problem_is_listed_in_words_and_nothing_is_made(home):
    code, io = go(home, "new", "--someone-else", "--hours", "abc", "--voice", "bob", interactive=False)
    assert code == 2 and made(home) == [] and io.prompts == []
    for sentence in ("Please type a name.", "Who agreed? This is needed before recording someone else's voice.",
                     "What did they agree to? This is needed before recording someone else's voice.", "When did they agree? This is needed before recording someone else's voice.",
                     "How can they change their mind? This is needed before recording someone else's voice.", "How was it given? This is needed before recording someone else's voice.",
                     "Please type the hours as a number, for example 2 or 1.5.", "That starting voice is not one this tool offers."):
        assert "  " + sentence in io.lines, sentence
    assert "To give the answers on the command line instead, run: python3 -m voice_studio.projects help" in io.lines and "Nothing was made." in io.lines


@pytest.mark.parametrize("hours, sentence", [("0", "The plan needs at least half an hour of recording."), ("0.4", "The plan needs at least half an hour of recording."),
                                             ("101", "That is more than this tool plans for. Please type a smaller number."), ("-2", "The plan needs at least half an hour of recording."),
                                             ("nan", "Please type the hours as a number, for example 2 or 1.5."), ("", "Please type roughly how many hours of recording you expect.")])
def test_hours_outside_what_the_plan_takes_are_refused_with_their_own_sentence(home, hours, sentence):
    code, io = go(home, "new", "--own", "--name", "Anna", "--hours", hours, "--yes", interactive=False)
    assert code == 2 and made(home) == [] and "  " + sentence in io.lines


def test_the_boundary_hours_are_accepted(home):
    assert go(home, "new", "--own", "--name", "A", "--hours", "0.5", "--yes", interactive=False)[0] == 0
    assert go(home, "new", "--own", "--name", "B", "--hours", "100", "--yes", interactive=False)[0] == 0


def test_a_name_that_is_too_long_is_refused_not_cut(home):
    code, io = go(home, "new", "--own", "--name", "n" * 81, "--yes", interactive=False)
    assert code == 2 and made(home) == [] and "  This name is too long. Please use a shorter one." in io.lines
    assert go(home, "new", "--own", "--name", "n" * 80, "--yes", interactive=False)[0] == 0


def test_a_part_of_the_agreement_that_is_too_long_is_refused_not_cut(home):
    code, io = go(home, "new", "--someone-else", "--name", "Ben", "--given-by", "g" * 501, "--agreed-to", "b", "--when", "c", "--withdraw", "d", "--how-given", "spoken",
                  "--yes", interactive=False)
    assert code == 2 and made(home) == [] and "  This is too long. Please shorten it; nothing was cut for you." in io.lines


def test_how_it_was_given_that_is_not_one_of_the_ways_is_missing(home):
    code, io = go(home, "new", "--someone-else", "--name", "Ben", "--given-by", "a", "--agreed-to", "b", "--when", "c", "--withdraw", "d", "--how-given", "telepathy",
                  "--yes", interactive=False)
    assert code == 2 and made(home) == [] and "How was it given? This is needed" in io.text


def test_how_it_was_given_as_another_way_needs_the_words(home):
    code, io = go(home, "new", "--someone-else", "--name", "Ben", "--given-by", "a", "--agreed-to", "b", "--when", "c", "--withdraw", "d", "--how-given", "other",
                  "--yes", interactive=False)
    assert code == 2 and made(home) == [] and "Describe how it was given. This is needed" in io.text


def test_both_whose_options_at_once_is_refused(home):
    code, io = go(home, "new", "--own", "--someone-else", "--name", "A", "--yes", interactive=False)
    assert code == 2 and made(home) == [] and "not both" in io.text


def test_an_own_voice_project_does_not_need_an_agreement(home):
    assert go(home, "new", "--own", "--name", "Anna", "--yes", interactive=False)[0] == 0
    assert load(home, "anna").consent == Consent()


# ---------------------------------------------------------------- new: the disk

def test_the_disk_the_plan_needs_is_told_beside_what_is_free(home):
    code, io = go(home, "new", "--own", "--name", "Anna", "--yes", interactive=False, free=500 * GIB)
    plan = [l for l in io.lines if l.startswith("The whole plan for this project needs about ")]
    assert code == 0 and len(plan) == 1 and plan[0].endswith(" free on this computer. %s is free." % size_text(500 * GIB))
    assert "That is less than the plan needs" not in io.text
    assert ("These sizes are still rough estimates." in io.lines) == (not DEFAULT_TABLE.all_measured)


def test_a_short_disk_is_said_but_never_stops_the_project(home):
    code, io = go(home, "new", "--own", "--name", "Anna", "--yes", interactive=False, free=1 * GIB)
    assert code == 0 and made(home) == ["anna"]
    assert "That is less than the plan needs. The project can still be made; nothing is reserved." in io.lines


def test_a_disk_that_cannot_be_read_is_said_and_does_not_stop_the_project(home):
    code, io = go(home, "new", "--own", "--name", "Anna", "--yes", interactive=False, system=FakeSystem(disks={}))
    assert code == 0 and made(home) == ["anna"] and "How much is free could not be read." in io.text and "That is less than" not in io.text


def test_more_hours_planned_means_more_room_asked_for(home):
    def need(hours):
        text_ = go(DataHome(home.home + "-" + hours), "new", "--own", "--name", "A", "--hours", hours, interactive=False)[1].text
        return next(l for l in text_.splitlines() if l.startswith("The whole plan"))
    assert need("1") != need("40")


# ---------------------------------------------------------------- new: when making it fails

def test_a_project_that_cannot_be_made_says_so_in_three_parts_and_exits_with_a_problem(home, monkeypatch):
    def refuse(*args, **kwargs):
        raise ProjectError("exists", "anna")
    monkeypatch.setattr(pf, "create", refuse)
    code, io = go(home, "new", "--own", "--name", "Anna", "--yes", interactive=False)
    assert code == 1 and "Made the project" not in io.text
    assert any(line.startswith("  ") and "already" in line.lower() for line in io.lines)


def test_a_disk_error_while_making_it_is_said_with_its_technical_detail(home, monkeypatch):
    def full(*args, **kwargs):
        raise OSError(28, "No space left on device")
    monkeypatch.setattr(pf, "create", full)
    code, io = go(home, "new", "--own", "--name", "Anna", "--yes", interactive=False)
    assert code == 1 and "The project could not be made, because of a problem with the disk." in io.lines and "  Technical detail: No space left on device" in io.lines


# ---------------------------------------------------------------- the front itself

def test_the_front_reads_the_real_home_and_prints(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("HOME", str(tmp_path))
    assert projects.main(["list"]) == 0
    assert "There are no projects yet." in capsys.readouterr().out
    assert projects.main(["new", "--own", "--name", "Anna", "--yes"]) == 0
    assert os.path.isfile(str(tmp_path / "ack-voice-studio" / "projects" / "anna" / "project.json"))
    assert projects.main(["show"]) == 0 and "Project anna: Anna" in capsys.readouterr().out


def test_the_front_runs_as_a_module(tmp_path):
    import subprocess
    import sys
    tools = Path(__file__).resolve().parents[2]
    done = subprocess.run([sys.executable, "-m", "voice_studio.projects", "list"], cwd=str(tools), env=dict(os.environ, HOME=str(tmp_path), PYTHONDONTWRITEBYTECODE="1"),
                          text=True, capture_output=True, timeout=60, stdin=subprocess.DEVNULL)
    assert done.returncode == 0 and "There are no projects yet." in done.stdout and "Traceback" not in done.stderr


# ---------------------------------------------------------------- the options each command takes

def test_the_options_the_commands_publish_are_exactly_the_ones_they_accept(home):
    """The checklist is held to `OPTIONS`; so `OPTIONS` is held to what the commands really do."""
    values = {"--name": "Anna", "--given-by": "a", "--agreed-to": "b", "--when": "c", "--withdraw": "d", "--how-given": "spoken", "--how-given-other": "e",
              "--hours": "1", "--voice": "mike"}
    every = set(values) | {"--own", "--someone-else", "--yes", "-y", "--away", "--nope"}
    assert set(pf.OPTIONS) == {"list", "show", "new", "edit", "archive", "unarchive", "delete"}
    for command, accepted in pf.OPTIONS.items():
        for option in sorted(every):
            code, io = go(home, command, option, *([values[option]] if option in values else []), interactive=False)
            understood = "I do not know the option" not in io.text
            assert understood == (option in accepted), (command, option, io.text)
    assert made(home) == [], "a single option never makes a project"
