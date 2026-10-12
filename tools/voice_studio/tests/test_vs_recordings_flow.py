# SPDX-License-Identifier: GPL-3.0-or-later
"""The terminal front for a project's recordings (plan task VS-2.10): see them, bring in voice data of four kinds, let the computer listen, make a training set. Held to: looking changes nothing,
what would be added is shown before the question, a no or nobody to ask writes nothing, a chosen folder or package is only ever read, a file that cannot be read is left out without stopping
the others, a job that listens is started only after a yes and never twice, a training set goes to a new folder only after a yes, and a window's Yes and No buttons answer the very same questions."""
import hashlib
import os
import shutil
import sys
import zipfile
from dataclasses import replace
from pathlib import Path

import pytest

from freeform_studio import files_import
from vs_recordings_helpers import (Runner, Starter, TEXTS, audio_folder, builder_lines, make_package, needs_ffmpeg, pairs_folder, studio_env, table_folder, tone_wav,
                                   write_dataset, write_take)
from vs_envfind_hub import A, B, put_hub, registry_for
from vs_rounds_helpers import PROJECT, fake_job
from vs_startvoice_helpers import NOW, Terminal, leaked_keys
from voice_studio.core import commands, envfind, jobs, recordings as rec, recordings_flow as rf, text
from voice_studio.core.consent import load_consent, make_consent, save_consent
from voice_studio.core.paths import DataHome, ProjectPaths
from voice_studio.core.project import SCRATCH_CUSTOM, Scratch, create_project, load_project, save_project, with_archived
from voice_studio.core.registry import Registry, load_registry
from voice_studio.core.system import CommandResult

CAT = text.load_catalog("en")
OLD, NEW = "t20261001-100000-aaaa", "t20261002-100000-bbbb"


class Buttons(Terminal):
    """The window's side of a flow: a question is a Yes and a No button (`confirm`), never a typed word."""

    def __init__(self, answers=(), interactive=True):
        super().__init__(answers, interactive)
        self.asked = []

    def confirm(self, prompt):
        self.asked.append(prompt)
        return self.answers.pop(0) if self.answers else None


@pytest.fixture
def home(tmp_path):
    return DataHome(str(tmp_path / "home"))


@pytest.fixture
def anna(home):
    create_project(home.projects, "Anna", "own", planned_hours=1)
    return ProjectPaths(home.projects + "/anna")


def made_job(home, argv, status, **kwargs):
    os.makedirs(home.jobs, exist_ok=True)
    return fake_job(home.jobs, argv, status, **kwargs)


def tree(root):
    found = {}
    for base, _dirs, files in os.walk(root):
        for name in files:
            path = os.path.join(base, name)
            found[os.path.relpath(path, root)] = hashlib.sha256(open(path, "rb").read()).hexdigest()
    return found


def go(home, *argv, answers=(), interactive=True, io=None, studio=None, speech=None, start=None, system=None, plan_files=None, now=NOW, registry=None, fetcher=None):
    io = io or Terminal(answers, interactive)
    code = rf.run_recordings(list(argv), home, registry or load_registry(), CAT, io, studio=studio or (lambda: (None, "absent")), speech=speech or (lambda: (None, "missing")),
                             tools_dir="/tools", now=now, start=start or Starter(), system=system or Runner(), plan_files=plan_files or files_import.make_plan,
                             sleep=lambda seconds: None, clock=lambda: 0.0, fetcher=fetcher)
    assert leaked_keys(io.text + "\n".join(io.prompts) + "\n".join(getattr(io, "asked", []))) == [], "a catalog key was printed instead of words"
    return code, io


def recordings_of(paths):
    return tree(paths.recordings)


def ready_world(tmp_path):
    """The studio programs and the listening model, as far as a flow can tell."""
    env = studio_env(tmp_path)
    model = tmp_path / "speech-model"
    model.mkdir(exist_ok=True)
    return (lambda: (env, "ready")), (lambda: (str(model), "ready"))


# ---------------------------------------------------------------- help and the options

def test_help_names_the_four_commands_and_the_four_kinds(home):
    code, io = go(home, "help")
    assert code == 0 and io.prompts == []
    for command in ("show [--project name]:", "import source --kind package|pairs|table|audio", "finish [--project name]:", "set [--preview] [--max-gain-db n]"):
        assert command in io.text, command
    for kind in ("package", "pairs", "table", "audio"):
        assert kind in io.text.split("Kinds:")[1], kind


def test_every_option_each_command_takes_is_named_in_its_help_line(home):
    _code, io = go(home, "help")
    help_of = {line.split()[0]: line for line in io.lines if line.startswith("  ") and line.split()[0] in rf.OPTIONS}
    assert set(help_of) == set(rf.OPTIONS) == {"show", "import", "finish", "model", "set"}
    for command, options in rf.OPTIONS.items():
        for option in options - {"--yes", "-y"}:
            assert option in help_of[command], (command, option)
    assert "--yes" in io.text


def test_an_unknown_command_or_option_does_nothing_and_says_so(home, anna):
    code, io = go(home, "frobnicate")
    assert code == 2 and "I do not know the command frobnicate" in io.text
    code, io = go(home, "show", "--bogus")
    assert code == 2 and "I do not know the option --bogus" in io.text
    code, io = go(home, "import", "x", "y", "--kind", "pairs")
    assert code == 2 and "I did not expect y there" in io.text and tree(anna.recordings) == {}


def test_a_name_that_is_not_a_project_is_not_guessed(home, anna):
    code, io = go(home, "show", "--project", "ben")
    assert code == 2 and "ben" in io.text and tree(anna.recordings) == {}


def test_a_project_that_is_put_away_is_not_used(home, anna):
    save_project(anna, with_archived(load_project(anna), True))
    code, io = go(home, "show", "--project", "anna")
    assert code == 2 and "put away" in io.text and "unarchive anna" in io.text


# ---------------------------------------------------------------- show

def test_show_with_no_recordings_says_so_and_how_to_bring_some_in(home, anna):
    code, io = go(home, "show")
    assert code == 0 and "Recordings in Anna" in io.text and "There are no recordings in this project yet." in io.text
    assert "python3 -m voice_studio.recordings import SOURCE --kind KIND --project anna" in io.text


def test_show_counts_each_group_and_lists_each_recording_with_its_state(home, anna):
    write_take(anna.recordings, OLD, status="ready", duration=90.0, label="Morning words")
    write_take(anna.recordings, NEW, status="finishing", duration=None, label="Evening words")
    write_take(anna.recordings, "t20261003-100000-cccc", status="error", label="Broken one")
    code, io = go(home, "show")
    assert code == 0 and "3 recordings in all." in io.lines
    assert "Ready: 1. Waiting to be listened to: 1. Could not be finished: 1. Still coming in: 0." in io.lines
    assert "  Morning words: ready, about 1.5 minutes" in io.lines and "  Evening words: waiting to be listened to" in io.lines and "  Broken one: could not be finished, about 1 minutes" in io.lines
    assert "1 recording could not be finished. Look at it on the Review page." in io.lines


def test_show_gives_the_length_only_when_some_of_it_is_known(home, anna):
    write_take(anna.recordings, NEW, status="finishing", duration=None)
    _code, io = go(home, "show")
    assert not any("add up to about" in line for line in io.lines)
    write_take(anna.recordings, OLD, duration=120.0)
    _code, io = go(home, "show")
    assert "The ones the computer has listened to add up to about 2 minutes." in io.lines


@pytest.mark.parametrize("takes, expected", [
    ([], "To bring recordings in, run: python3 -m voice_studio.recordings import SOURCE --kind KIND --project anna"),
    ([("ready", 60.0)], "To make a training set, run: python3 -m voice_studio.recordings set --project anna"),
    ([("ready", 60.0), ("finishing", None)], "To let the computer listen to the waiting recordings, run: python3 -m voice_studio.recordings finish --project anna"),
    ([("error", None)], "To bring recordings in, run: python3 -m voice_studio.recordings import SOURCE --kind KIND --project anna"),
])
def test_show_ends_with_the_one_thing_to_do_next(home, anna, takes, expected):
    for n, (status, duration) in enumerate(takes):
        write_take(anna.recordings, "t20261001-10000%d-aaaa" % n, status=status, duration=duration)
    _code, io = go(home, "show")
    assert io.lines[-1] == expected


def test_show_says_what_the_listening_is_on_while_it_runs_and_asks_to_wait(home, anna):
    write_take(anna.recordings, OLD, status="transcribing", duration=None, label="Long one")
    job = made_job(home, ["x"], "running", kind="process", project="anna")
    with open(job.dir + "/log.txt", "w") as handle:
        handle.write('{"take": "t1", "status": "transcribing", "label": "Long one", "progress": 0.37}\n')
    _code, io = go(home, "show")
    assert "The computer is listening to the recordings now." in io.lines and "  It is on Long one: 37 percent done." in io.lines
    assert io.lines[-1] == "Run this again in a little while to see how it is going."


def test_show_tells_when_the_last_listening_stopped_before_it_finished(home, anna):
    write_take(anna.recordings, OLD, status="transcribing", duration=None)
    made_job(home, ["x"], "interrupted", kind="process", project="anna")
    _code, io = go(home, "show")
    assert "The last time the computer listened, it did not finish (" in io.text and "finish --project anna" in io.lines[-1]


def test_show_cuts_a_long_list_and_says_how_many_more(home, anna):
    for n in range(rf.MAX_ROWS_SHOWN + 5):
        write_take(anna.recordings, "t20261001-1%05d-aaaa" % n, label="rec %02d" % n)
    _code, io = go(home, "show")
    assert sum(1 for line in io.lines if line.startswith("  rec ")) == rf.MAX_ROWS_SHOWN and "  And 5 more." in io.lines


@pytest.mark.parametrize("status, words", [("ready", "ready"), ("finishing", "waiting to be listened to"), ("queued", "waiting to be listened to"), ("transcribing", "waiting to be listened to"),
                                           ("error", "could not be finished"), ("importing", "still coming in"), ("recording", "still coming in"), ("something-new", "still coming in"), ("", "still coming in")])
def test_every_status_is_shown_as_one_of_four_plain_words(home, anna, status, words):
    write_take(anna.recordings, OLD, status=status, duration=None, label="Words")
    _code, io = go(home, "show")
    assert "  Words: " + words in io.lines


def test_a_list_that_just_fits_does_not_say_there_are_more(home, anna):
    for n in range(rf.MAX_ROWS_SHOWN):
        write_take(anna.recordings, "t20261001-1%05d-aaaa" % n, label="rec %02d" % n)
    _code, io = go(home, "show")
    assert sum(1 for line in io.lines if line.startswith("  rec ")) == rf.MAX_ROWS_SHOWN and not any(line.startswith("  And ") for line in io.lines)


def test_an_earlier_listening_that_stopped_is_not_mentioned_when_nothing_is_waiting_any_more(home, anna):
    write_take(anna.recordings, OLD, status="ready", duration=60.0)
    made_job(home, ["x"], "interrupted", kind="process", project="anna")
    _code, io = go(home, "show")
    assert not any("did not finish" in line for line in io.lines)


def test_show_changes_nothing(home, anna):
    write_take(anna.recordings, OLD)
    made_job(home, ["x"], "failed", kind="process", project="anna")
    before = (tree(home.home), os.listdir(home.jobs))
    go(home, "show")
    assert (tree(home.home), os.listdir(home.jobs)) == before


def test_show_counts_notes_that_cannot_be_read_and_leaves_them(home, anna):
    write_take(anna.recordings, OLD, raw=b"{broken")
    before = tree(anna.recordings)
    _code, io = go(home, "show")
    assert "The notes of 1 recording could not be read, so it was left alone." in io.lines and tree(anna.recordings) == before


# ---------------------------------------------------------------- import: asking, choosing, stopping early

def test_import_without_a_source_says_what_to_give(home, anna):
    code, io = go(home, "import")
    assert code == 2 and "Say what to bring in. For example: python3 -m voice_studio.recordings import ~/Documents/voice-files --kind pairs" in io.text


def test_import_without_a_kind_lists_the_four_to_choose_from_and_never_guesses(home, anna, tmp_path):
    folder = pairs_folder(tmp_path)
    code, io = go(home, "import", str(folder))
    assert code == 2 and "Say what kind of data it is, with --kind." in io.text and io.prompts == []
    for kind, name in (("package", "An ACK package"), ("pairs", "Audio files, each with a text file"), ("table", "Audio files with one table of sentences"), ("audio", "Audio files only")):
        assert any(line.startswith("  %s: %s " % (kind, name)) for line in io.lines), kind
    assert tree(anna.recordings) == {}


def test_import_with_a_kind_it_does_not_know_does_nothing(home, anna, tmp_path):
    code, io = go(home, "import", str(pairs_folder(tmp_path)), "--kind", "zip")
    assert code == 2 and "I do not know the kind zip. The choices are package, pairs, table, audio. Nothing was done." in io.text and tree(anna.recordings) == {}


def test_a_table_name_only_goes_with_the_table_kind(home, anna, tmp_path):
    code, io = go(home, "import", str(pairs_folder(tmp_path)), "--kind", "pairs", "--table", "metadata.csv")
    assert code == 2 and "--table only goes with --kind table. Nothing was done." in io.text and tree(anna.recordings) == {}


@pytest.mark.parametrize("make, code_words", [
    (lambda tmp: tmp / "missing", "The place you chose is not a folder"),
    (lambda tmp: (tmp / "empty").mkdir() or tmp / "empty", "No audio files were found there."),
])
def test_a_place_that_cannot_be_imported_is_explained_in_three_parts_and_nothing_is_written(home, anna, tmp_path, make, code_words):
    code, io = go(home, "import", str(make(tmp_path)), "--kind", "audio")
    assert code == 1 and code_words in io.text and "Nothing was copied or changed." in io.text and io.prompts == []
    assert tree(anna.recordings) == {}


def test_a_file_that_is_not_a_zip_is_not_a_folder_of_files(home, anna, tmp_path):
    notzip = tmp_path / "notes.txt"
    notzip.write_text("hello")
    code, io = go(home, "import", str(notzip), "--kind", "audio")
    assert code == 1 and "is not a folder, or a zip file that holds one" in io.text and tree(anna.recordings) == {}


# ---------------------------------------------------------------- import: a folder of audio with a text file each

@needs_ffmpeg
def test_the_plan_is_shown_before_the_question_and_a_no_writes_nothing(home, anna, tmp_path):
    folder = pairs_folder(tmp_path, 3)
    source_before = tree(folder)
    code, io = go(home, "import", str(folder), "--kind", "pairs", answers=["no"])
    assert code == 2 and io.prompts == ["Add 3 files to Anna? Type yes to go on. "] and "Nothing was done." in io.text
    assert io.events.index(("say", "3 of them come with a sentence.")) < io.events.index(("ask", io.prompts[0]))
    assert "Looked at voice (Audio files, each with a text file)." in io.lines and "Found 3 audio files." in io.lines
    assert not any("no sentence" in line for line in io.lines), "every file came with its sentence, so none is said to lack one"
    assert tree(anna.recordings) == {} and tree(folder) == source_before


@needs_ffmpeg
def test_a_yes_adds_the_files_as_recordings_to_be_listened_to_and_leaves_the_folder_alone(home, anna, tmp_path):
    folder = pairs_folder(tmp_path, 3)
    source_before = tree(folder)
    code, io = go(home, "import", str(folder), "--kind", "pairs", answers=["yes"])
    assert code == 0 and "3 audio files were added." in io.lines and "1 recording was made from them." in io.lines
    assert io.lines[-1] == "Next, let the computer listen to them. Run: python3 -m voice_studio.recordings finish --project anna"
    view = rec.read_takes(anna.recordings)
    assert (view.total, view.waiting, view.rows[0].origin) == (1, 1, "files")
    assert tree(folder) == source_before, "the folder that was chosen is only ever read"
    assert set(os.listdir(anna.recordings)) == {"_freeform"}, "nothing was written anywhere but the recordings"


@needs_ffmpeg
def test_the_same_folder_again_adds_nothing_and_does_not_ask(home, anna, tmp_path):
    folder = pairs_folder(tmp_path, 2)
    go(home, "import", str(folder), "--kind", "pairs", "--yes")
    before = tree(anna.recordings)
    code, io = go(home, "import", str(folder), "--kind", "pairs")
    assert code == 0 and io.prompts == [] and "2 files are already in this project and will be skipped." in io.lines
    assert "There is nothing new to add. Nothing was done." in io.lines and tree(anna.recordings) == before


@needs_ffmpeg
def test_yes_on_the_line_does_not_ask(home, anna, tmp_path):
    code, io = go(home, "import", str(pairs_folder(tmp_path, 1)), "--kind", "pairs", "--yes")
    assert code == 0 and io.prompts == [] and rec.read_takes(anna.recordings).total == 1


@needs_ffmpeg
def test_with_nobody_to_ask_nothing_is_added_and_the_way_to_say_yes_is_given(home, anna, tmp_path):
    code, io = go(home, "import", str(pairs_folder(tmp_path, 1)), "--kind", "pairs", interactive=False)
    assert code == 2 and "--yes" in io.text and tree(anna.recordings) == {}


@needs_ffmpeg
def test_the_windows_buttons_answer_the_same_question(home, anna, tmp_path):
    folder = pairs_folder(tmp_path, 2)
    io = Buttons([False])
    code, io = go(home, "import", str(folder), "--kind", "pairs", io=io)
    assert code == 2 and io.asked == ["Add 2 files to Anna? Type yes to go on."] and io.prompts == [] and tree(anna.recordings) == {}
    io = Buttons([True])
    code, io = go(home, "import", str(folder), "--kind", "pairs", io=io)
    assert code == 0 and rec.read_takes(anna.recordings).total == 1


@needs_ffmpeg
def test_one_file_is_asked_about_in_the_singular(home, anna, tmp_path):
    code, io = go(home, "import", str(pairs_folder(tmp_path, 1)), "--kind", "pairs", answers=["no"])
    assert io.prompts == ["Add 1 file to Anna? Type yes to go on. "] and "Found 1 audio file." in io.lines and "1 audio file would be added, about " in io.text
    assert "1 of them comes with a sentence." in io.lines


@needs_ffmpeg
def test_files_with_no_text_file_at_all_are_called_out_so_a_wrong_kind_is_noticed(home, anna, tmp_path):
    folder = audio_folder(tmp_path, 2)
    code, io = go(home, "import", str(folder), "--kind", "pairs", answers=["no"])
    assert "None of them came with a sentence, so the computer will write them all itself. Check that you chose the right kind." in io.lines
    assert not any("comes with a sentence" in line or "come with a sentence" in line for line in io.lines)


@needs_ffmpeg
def test_some_files_without_a_text_file_are_counted_apart(home, anna, tmp_path):
    folder = pairs_folder(tmp_path, 3)
    os.remove(folder / "002.txt")
    _code, io = go(home, "import", str(folder), "--kind", "pairs", answers=["no"])
    assert "2 of them come with a sentence." in io.lines and "1 of them has no sentence, so the computer will write it." in io.lines


@needs_ffmpeg
def test_a_text_file_that_cannot_be_read_is_noted_by_name_and_the_audio_still_comes_in(home, anna, tmp_path):
    folder = pairs_folder(tmp_path, 2)
    (folder / "001.txt").write_bytes(b"\xff\xfe\x00 not utf8")
    code, io = go(home, "import", str(folder), "--kind", "pairs", "--yes")
    assert code == 0 and "  The text file for 001.wav could not be read, so that file has no sentence." in io.lines and "2 audio files were added." in io.lines


# ---------------------------------------------------------------- import: a table, audio only

@needs_ffmpeg
def test_a_table_of_sentences_gives_them_to_the_files_it_names(home, anna, tmp_path):
    folder = table_folder(tmp_path, 3)
    code, io = go(home, "import", str(folder), "--kind", "table", answers=["no"])
    assert "3 of them come with a sentence." in io.lines and "Looked at tabled (Audio files with one table of sentences)." in io.lines


@needs_ffmpeg
def test_a_table_that_is_not_there_is_said_and_the_files_come_without_sentences(home, anna, tmp_path):
    folder = audio_folder(tmp_path, 2)
    _code, io = go(home, "import", str(folder), "--kind", "table", answers=["no"])
    assert "  The table of sentences was not found. The files will be added without sentences." in io.lines
    assert "None of them came with a sentence, so the computer will write them all itself. Check that you chose the right kind." in io.lines


@needs_ffmpeg
def test_a_table_line_for_a_file_that_is_not_there_is_noted(home, anna, tmp_path):
    folder = table_folder(tmp_path, 2)
    with open(folder / "metadata.csv", "a", encoding="utf-8") as handle:
        handle.write("999|No such file here.|no such file here\n")
    _code, io = go(home, "import", str(folder), "--kind", "table", answers=["no"])
    assert "  The table has a line for 999, but there is no audio file with that name." in io.lines


@needs_ffmpeg
def test_a_named_table_that_is_missing_is_noted_and_the_table_kind_takes_a_name(home, anna, tmp_path):
    folder = table_folder(tmp_path, 2)
    _code, io = go(home, "import", str(folder), "--kind", "table", "--table", "other.csv", answers=["no"])
    assert "  The table of sentences was not found. The files will be added without sentences." in io.lines


@needs_ffmpeg
def test_audio_only_says_the_computer_will_write_the_sentences_and_makes_a_recording_for_each_file(home, anna, tmp_path):
    folder = audio_folder(tmp_path, 2)
    _code, io = go(home, "import", str(folder), "--kind", "audio", answers=["yes"])
    assert "The computer will listen to them and write down what it hears." in io.lines and "2 recordings were made from them." in io.lines
    assert "The sentences you give are kept as a check." not in io.text, "there are no sentences to keep as a check"
    view = rec.read_takes(anna.recordings)
    assert (view.total, view.waiting) == (2, 2)


@needs_ffmpeg
def test_a_zip_of_audio_files_is_unpacked_only_inside_the_project_and_the_zip_is_left_alone(home, anna, tmp_path):
    folder = audio_folder(tmp_path, 2)
    archive = tmp_path / "files.zip"
    with zipfile.ZipFile(archive, "w") as handle:
        for name in sorted(os.listdir(folder)):
            handle.write(folder / name, "set/" + name)
    before = archive.read_bytes()
    code, io = go(home, "import", str(archive), "--kind", "audio", "--yes")
    assert code == 0 and rec.read_takes(anna.recordings).total == 2 and archive.read_bytes() == before
    assert set(os.listdir(tmp_path)) >= {"files.zip", "plain", "home"} and not any(p.name.startswith("set") for p in tmp_path.iterdir())


# ---------------------------------------------------------------- import: what cannot be used, and not enough room

@needs_ffmpeg
def test_a_file_that_cannot_be_decoded_is_left_out_by_name_and_the_others_still_come_in(home, anna, tmp_path):
    folder = pairs_folder(tmp_path, 2)
    (folder / "003.wav").write_bytes(b"RIFF this is not really audio at all " * 50)
    (folder / "003.txt").write_text("A sentence for a broken file.\n")
    code, io = go(home, "import", str(folder), "--kind", "pairs", "--yes")
    assert code == 0 and "2 audio files were added." in io.lines and "1 file was left out." in io.lines
    assert any(line.startswith("  003.wav: ") for line in io.lines)


@needs_ffmpeg
def test_when_every_file_fails_nothing_is_added_and_it_is_an_error(home, anna, tmp_path):
    folder = tmp_path / "broken"
    folder.mkdir()
    (folder / "a.wav").write_bytes(b"not audio " * 400)
    (folder / "b.wav").write_bytes(b"not audio either " * 400)
    code, io = go(home, "import", str(folder), "--kind", "audio", "--yes")
    assert code == 1 and "No file could be added." in io.lines and rec.read_takes(anna.recordings).total == 0


@needs_ffmpeg
def test_a_file_too_short_to_use_is_named_in_the_plan_and_skipped(home, anna, tmp_path):
    folder = pairs_folder(tmp_path, 1)
    tone_wav(folder / "tiny.wav", seconds=0.2, bursts=((0.0, 0.2),))
    _code, io = go(home, "import", str(folder), "--kind", "pairs", answers=["no"])
    assert "1 file cannot be used and will be skipped. The reasons are below." in io.lines and "  tiny.wav is too short to use." in io.lines


@needs_ffmpeg
def test_not_enough_room_is_said_in_words_and_nothing_is_written_even_with_yes(home, anna, tmp_path):
    folder = pairs_folder(tmp_path, 1)
    real = files_import.make_plan

    def tight(*args, **kwargs):
        plan = real(*args, **kwargs)
        plan.free_mb = 1.0
        return plan

    code, io = go(home, "import", str(folder), "--kind", "pairs", "--yes", plan_files=tight)
    assert code == 2 and "There is not enough free space. Adding this needs about " in io.text and "Nothing was added." in io.text
    assert tree(anna.recordings) == {}


@needs_ffmpeg
def test_more_notes_than_fit_are_counted_not_dropped_silently(home, anna, tmp_path):
    folder = tmp_path / "many"
    folder.mkdir()
    for n in range(files_import.PROBLEM_CODES.__len__() + rf.MAX_NOTES_SHOWN):
        (folder / ("f%02d.wav" % n)).write_bytes(b"")            # empty files cannot be used: one note each
    tone_wav(folder / "good.wav")
    _code, io = go(home, "import", str(folder), "--kind", "audio", answers=["no"])
    assert sum(1 for line in io.lines if line.endswith("could not be read.")) == rf.MAX_NOTES_SHOWN
    assert "  And %d more." % (len(files_import.PROBLEM_CODES) + rf.MAX_NOTES_SHOWN - rf.MAX_NOTES_SHOWN) in io.lines


# ---------------------------------------------------------------- import: an ACK package

def test_a_package_is_shown_session_by_session_before_anything_is_asked(home, anna, tmp_path):
    package = make_package(tmp_path)
    before = package.read_bytes()
    code, io = go(home, "import", str(package), "--kind", "package", answers=["no"])
    assert code == 2 and "This package holds 2 sessions." in io.lines and io.prompts == ["Add 2 sessions to Anna? Type yes to go on. "]
    assert any("(Script, about " in line and line.endswith("Will be added") for line in io.lines) and any("(Free speech, about " in line for line in io.lines)
    assert io.events.index(("say", "This package holds 2 sessions.")) < io.events.index(("ask", io.prompts[0]))
    assert package.read_bytes() == before and rec.read_takes(anna.recordings).total == 0


def test_saying_no_to_a_package_takes_away_the_checked_copy_this_run_made(home, anna, tmp_path):
    package = make_package(tmp_path)
    go(home, "import", str(package), "--kind", "package", answers=["no"])
    assert not os.path.exists(rec.takes_dir(anna.recordings).parent / "incoming") or os.listdir(rec.takes_dir(anna.recordings).parent / "incoming") == []
    assert package.exists()


def test_a_yes_adds_the_sessions_and_keeps_the_checked_copy(home, anna, tmp_path):
    package = make_package(tmp_path)
    code, io = go(home, "import", str(package), "--kind", "package", answers=["yes"])
    assert code == 0 and "2 recordings were made from them." in io.lines and "finish --project anna" in io.lines[-1]
    view = rec.read_takes(anna.recordings)
    assert (view.total, view.waiting) == (2, 2) and {r.origin for r in view.rows} == {"phone"}
    assert os.listdir(rec.takes_dir(anna.recordings).parent / "incoming") == ["p.zip"]


def test_the_same_package_again_has_nothing_new_and_asks_nothing(home, anna, tmp_path):
    package = make_package(tmp_path)
    go(home, "import", str(package), "--kind", "package", "--yes")
    before = tree(anna.recordings)
    code, io = go(home, "import", str(package), "--kind", "package")
    assert code == 0 and io.prompts == [] and "There is nothing new to add. Nothing was done." in io.lines
    assert tree(anna.recordings) == before


def test_a_copy_of_a_package_under_another_name_adds_nothing_and_leaves_no_second_copy(home, anna, tmp_path):
    package = make_package(tmp_path)
    go(home, "import", str(package), "--kind", "package", "--yes")
    other = tmp_path / "phone" / "renamed.zip"
    shutil.copy(package, other)
    before = tree(anna.recordings)
    code, io = go(home, "import", str(other), "--kind", "package")
    assert code == 0 and "Already added" in io.text and tree(anna.recordings) == before


def test_a_file_that_is_not_a_package_is_explained_and_nothing_is_written(home, anna, tmp_path):
    bad = tmp_path / "bad.zip"
    bad.write_bytes(b"this is not a zip file at all")
    code, io = go(home, "import", str(bad), "--kind", "package", "--yes")
    assert code == 1 and "The file you chose is not a zip file, so it cannot be an ACK package." in io.text and "Nothing was copied or changed." in io.text
    assert tree(anna.recordings) == {}


def test_a_zip_that_is_not_an_ack_package_lists_what_is_wrong_and_leaves_no_copy(home, anna, tmp_path):
    bad = tmp_path / "other.zip"
    with zipfile.ZipFile(bad, "w") as handle:
        handle.writestr("hello.txt", "hi")
    code, io = go(home, "import", str(bad), "--kind", "package", "--yes")
    assert code == 1 and "This file is not a complete ACK package, so it was not used." in io.text
    assert not list(Path(anna.recordings).rglob("*.zip")), "a package that failed its checks leaves no copy"


def test_not_enough_room_for_a_package_is_said_and_the_copy_is_taken_away(home, anna, tmp_path, monkeypatch):
    package = make_package(tmp_path)
    real = rf.ackimport.prepare

    def tight(*args, **kwargs):
        prepared = real(*args, **kwargs)
        prepared.summary = replace(prepared.summary, enough_room=False, free_mb=1.0)
        return prepared

    monkeypatch.setattr(rf.ackimport, "prepare", tight)
    code, io = go(home, "import", str(package), "--kind", "package", "--yes")
    assert code == 2 and "There is not enough free space." in io.text and rec.read_takes(anna.recordings).total == 0
    assert not list(Path(anna.recordings).rglob("*.zip"))


# ---------------------------------------------------------------- finish

def test_finish_with_nothing_waiting_says_so_and_mentions_what_failed(home, anna):
    write_take(anna.recordings, OLD, status="ready")
    code, io = go(home, "finish")
    assert code == 0 and "No recording is waiting to be listened to." in io.lines
    write_take(anna.recordings, NEW, status="error")
    _code, io = go(home, "finish")
    assert "1 recording could not be finished. Look at it on the Review page." in io.lines


def test_finish_without_the_studio_programs_says_what_to_run_and_starts_nothing(home, anna):
    write_take(anna.recordings, OLD, status="finishing", duration=None)
    start = Starter()
    code, io = go(home, "finish", "--yes", start=start, studio=lambda: (None, "absent"))
    assert code == 2 and "The studio programs are not ready (Not set up yet). Set them up with: python3 -m voice_studio.buildenv studio" in io.lines
    assert start.calls == []


@pytest.fixture
def plain_places(monkeypatch):
    """Where the listening model is looked for does not depend on the machine the tests run on."""
    for name in ("HF_HUB_CACHE", "HUGGINGFACE_HUB_CACHE", "HF_HOME", "XDG_CACHE_HOME"):
        monkeypatch.delenv(name, raising=False)


def test_finish_without_the_listening_model_says_what_to_run_where_it_looked_and_starts_nothing(home, anna, tmp_path, plain_places):
    write_take(anna.recordings, OLD, status="finishing", duration=None)
    studio, _speech = ready_world(tmp_path)
    start = Starter()
    code, io = go(home, "finish", "--yes", start=start, studio=studio, speech=lambda: (None, "missing"))
    own = home.downloads + "/models/speech-small-en"
    hub = home.home + "/.cache/huggingface/hub/models--Systran--faster-whisper-small.en"
    assert code == 2 and "The listening model is not on this computer yet. To get it, run: python3 -m voice_studio.recordings model" in io.lines
    assert "It was looked for in %s and in %s." % (own, hub) in io.lines
    assert start.calls == []


def test_finish_with_a_listening_model_that_is_not_complete_names_its_folder_and_says_nothing_was_changed(home, anna, tmp_path, plain_places):
    write_take(anna.recordings, OLD, status="finishing", duration=None)
    studio, _speech = ready_world(tmp_path)
    start = Starter()
    code, io = go(home, "finish", "--yes", start=start, studio=studio, speech=lambda: (None, "incomplete"))
    own = home.downloads + "/models/speech-small-en"
    assert code == 2
    assert ("The listening model in %s is not complete, or a file in it is not what was agreed to. Nothing was changed or deleted. "
            "To fetch what is missing, run: python3 -m voice_studio.recordings model") % own in io.lines
    assert "not on this computer yet" not in io.text and "looked for in" not in io.text
    assert start.calls == []


def test_finish_uses_the_model_the_lookup_finds_when_no_answer_is_given_for_it(home, anna, tmp_path, monkeypatch):
    """The default wiring: a complete copy in the Hugging Face folder is what the job is started with; a copy one byte short is not."""
    write_take(anna.recordings, OLD, status="finishing", duration=None)
    studio, _speech = ready_world(tmp_path)
    monkeypatch.setenv("HF_HUB_CACHE", str(tmp_path / "hub"))
    monkeypatch.delenv("HUGGINGFACE_HUB_CACHE", raising=False)

    def run(hub_files, name):
        start = Starter()
        snapshot = put_hub(tmp_path / name, hub_files)
        monkeypatch.setenv("HF_HUB_CACHE", str(tmp_path / name))
        io = Terminal([])
        code = rf.run_recordings(["finish", "--yes"], home, registry_for(), CAT, io, studio=studio, tools_dir="/tools", now=NOW, start=start, system=Runner(),
                                 plan_files=files_import.make_plan)
        return code, io, start, snapshot

    code, io, start, snapshot = run({"a.bin": A, "b.bin": B}, "good")
    argv = list(start.calls[0][1].argv)
    assert code == 0 and argv[argv.index("--asr-model") + 1] == snapshot
    code, io, start, _snapshot = run({"a.bin": A, "b.bin": B[:-1]}, "short")
    assert code == 2 and start.calls == [] and "The listening model is not on this computer yet" in io.text


# ---------------------------------------------------------------- model: get the listening model

class Fetcher:
    """A stand-in for fetch.fetch: it puts the agreed bytes (or others) in place, tells how far it is, and remembers what it was asked for."""

    def __init__(self, payloads, wrong=(), error=None):
        self.payloads, self.wrong, self.error, self.calls = payloads, set(wrong), error, []

    def __call__(self, item, dest_dir, consent, cancelled=None, progress=None, **kwargs):
        self.calls.append((item.filename, str(dest_dir), consent.covers(item)))
        if self.error:
            raise self.error
        data = self.payloads[item.filename]
        if item.filename in self.wrong:
            data = data[:-1] + bytes([data[-1] ^ 1])
        os.makedirs(str(dest_dir), exist_ok=True)
        with open(os.path.join(str(dest_dir), item.filename), "wb") as handle:
            for start in range(0, len(data), 500):
                handle.write(data[start:start + 500])
                if progress:
                    progress(min(len(data), start + 500), len(data))
        return Path(str(dest_dir)) / item.filename


def model_world(home, monkeypatch):
    """A registry of two small model files and the lookup that reads the disk, with the machine's own Hugging Face settings out of the way."""
    for name in ("HF_HUB_CACHE", "HUGGINGFACE_HUB_CACHE", "HF_HOME", "XDG_CACHE_HOME"):
        monkeypatch.delenv(name, raising=False)
    registry = registry_for()
    return registry, (lambda: envfind.speech_model(home, registry)), Fetcher({"a.bin": A, "b.bin": B}), home.downloads + "/models/speech-small-en"


def test_model_shows_where_it_comes_from_and_how_big_and_a_no_downloads_and_saves_nothing(home, monkeypatch):
    registry, speech, fetcher, folder = model_world(home, monkeypatch)
    code, io = go(home, "model", answers=["no"], registry=registry, speech=speech, fetcher=fetcher)
    assert code == 2 and fetcher.calls == [] and not os.path.exists(home.consent_file) and not os.path.exists(folder)
    assert ("The listening model lets the computer write down what it hears in your recordings. It is %s in all, from huggingface.co, and will be kept in %s. "
            "Your recordings are not sent anywhere.") % (text.size_text(len(A) + len(B)), folder) in io.lines
    assert io.prompts == ["Download the listening model now? Type yes to go on. "] and "Nothing was done." in io.text


def test_model_with_nobody_to_ask_downloads_nothing_and_says_how_to_say_yes(home, monkeypatch):
    registry, speech, fetcher, folder = model_world(home, monkeypatch)
    code, io = go(home, "model", interactive=False, registry=registry, speech=speech, fetcher=fetcher)
    assert code == 2 and fetcher.calls == [] and not os.path.exists(home.consent_file) and "--yes" in io.text


def test_model_after_a_yes_saves_the_agreement_then_fetches_each_file_into_the_tools_folder_and_says_it_is_there(home, monkeypatch):
    registry, speech, fetcher, folder = model_world(home, monkeypatch)
    code, io = go(home, "model", answers=["yes"], registry=registry, speech=speech, fetcher=fetcher)
    assert code == 0
    assert fetcher.calls == [("a.bin", folder, True), ("b.bin", folder, True)], "each file is fetched, only after the agreement that names it was saved"
    assert open(os.path.join(folder, "a.bin"), "rb").read() == A and open(os.path.join(folder, "b.bin"), "rb").read() == B
    assert "Saved your agreement to download these files." in io.lines
    assert "Done. The listening model is on this computer, in %s. Every file was checked against the one that was agreed to." % folder in io.lines
    assert io.lines[-1] == "To let the computer listen to a project's recordings, run: python3 -m voice_studio.recordings finish --project PROJECT"
    assert envfind.speech_model(home, registry, {}) == (folder, "ready")
    consent = load_consent(Path(home.consent_file))
    assert all(consent.covers(item) for item in registry.items)


def test_model_says_how_far_it_is_over_both_files_in_plain_lines_that_end_at_a_hundred_percent(home, monkeypatch):
    registry, speech, fetcher, folder = model_world(home, monkeypatch)
    _code, io = go(home, "model", "--yes", registry=registry, speech=speech, fetcher=fetcher)
    steps = [line for line in io.lines if line.startswith("  ") and "%:" in line]
    percents = [int(line.split("%")[0]) for line in steps]
    assert percents == sorted(percents) and percents[-1] == 100 and len(set(percents)) == len(percents) and len(percents) >= 5
    total = text.size_text(len(A) + len(B))
    assert all(line.endswith("of " + total) for line in steps), "the figure is over both files together, not each file alone"


def test_model_with_yes_on_the_line_does_not_ask(home, monkeypatch):
    registry, speech, fetcher, folder = model_world(home, monkeypatch)
    code, io = go(home, "model", "--yes", registry=registry, speech=speech, fetcher=fetcher)
    assert code == 0 and io.prompts == [] and len(fetcher.calls) == 2


def test_model_when_it_is_already_there_downloads_nothing_and_asks_nothing(home, monkeypatch):
    registry, speech, fetcher, folder = model_world(home, monkeypatch)
    put_hub(os.path.join(home.home, ".cache", "huggingface", "hub"), {"a.bin": A, "b.bin": B})
    code, io = go(home, "model", registry=registry, speech=speech, fetcher=fetcher)
    assert code == 0 and fetcher.calls == [] and io.prompts == [] and not os.path.exists(home.consent_file)
    assert "The listening model is already on this computer, in " in io.text and "Nothing was downloaded." in io.text


def test_model_fetches_only_the_files_that_are_not_already_right(home, monkeypatch):
    registry, speech, fetcher, folder = model_world(home, monkeypatch)
    os.makedirs(folder)
    open(os.path.join(folder, "a.bin"), "wb").write(A)
    open(os.path.join(folder, "b.bin"), "wb").write(B[:-3])                    # cut short
    code, io = go(home, "model", answers=["yes"], registry=registry, speech=speech, fetcher=fetcher)
    assert code == 0 and [call[0] for call in fetcher.calls] == ["b.bin"]
    assert ("It is %s in all," % text.size_text(len(B))) in io.text
    assert envfind.speech_model(home, registry, {})[1] == "ready"


def test_model_keeps_an_earlier_agreement_when_it_saves_this_one(home, monkeypatch):
    registry, speech, fetcher, folder = model_world(home, monkeypatch)
    other = replace(registry.items[0], id="voice-other", kind="voice", folder=None, filename="v.ckpt")
    os.makedirs(os.path.dirname(home.consent_file), exist_ok=True)
    save_consent(Path(home.consent_file), make_consent([other]))
    go(home, "model", "--yes", registry=Registry(registry.items + (other,)), speech=speech, fetcher=fetcher)
    consent = load_consent(Path(home.consent_file))
    assert consent.covers(other) and all(consent.covers(item) for item in registry.items)


def test_model_that_cannot_save_the_agreement_downloads_nothing(home, monkeypatch):
    registry, speech, fetcher, folder = model_world(home, monkeypatch)
    os.makedirs(home.root, exist_ok=True)
    open(home.state, "w").close()                                               # the place for the agreement is a file, so it cannot be written
    code, io = go(home, "model", "--yes", registry=registry, speech=speech, fetcher=fetcher)
    assert code == 1 and fetcher.calls == [] and "Your agreement could not be saved, so nothing was downloaded." in io.lines


def test_model_when_a_download_fails_says_why_in_three_parts_and_says_nothing_is_there(home, monkeypatch):
    from voice_studio.core.fetch import FetchError
    registry, speech, _fetcher, folder = model_world(home, monkeypatch)
    code, io = go(home, "model", "--yes", registry=registry, speech=speech, fetcher=Fetcher({}, error=FetchError("checksum", "a.bin")))
    assert code == 1 and "The file that arrived did not match what was agreed, so it cannot be trusted." in io.text
    assert "Done." not in io.text and envfind.speech_model(home, registry, {}) == (None, "missing")


def test_model_that_cannot_confirm_what_it_fetched_does_not_claim_success(home, monkeypatch):
    registry, speech, _fetcher, folder = model_world(home, monkeypatch)
    code, io = go(home, "model", "--yes", registry=registry, speech=speech, fetcher=Fetcher({"a.bin": A, "b.bin": B}, wrong={"b.bin"}))
    assert code == 1 and "still does not check out in %s. Nothing was deleted." % folder in io.text and "Done." not in io.text


def test_model_stopped_with_ctrl_c_keeps_what_arrived_and_says_to_run_it_again(home, monkeypatch):
    registry, speech, _fetcher, folder = model_world(home, monkeypatch)
    code, io = go(home, "model", "--yes", registry=registry, speech=speech, fetcher=Fetcher({}, error=KeyboardInterrupt()))
    assert code == 1 and "Run the same command again to carry on." in io.text and "listening that had started" not in io.text


def test_model_with_files_that_are_not_fixed_yet_does_nothing_and_says_so(home, monkeypatch):
    registry, speech, fetcher, folder = model_world(home, monkeypatch)
    unpinned = Registry(tuple(replace(item, sha256=None) for item in registry.items))
    code, io = go(home, "model", "--yes", registry=unpinned, speech=lambda: (None, "missing"), fetcher=fetcher)
    assert code == 2 and fetcher.calls == [] and "its files are not fixed in this version of the tool. Nothing was done." in io.text


def test_the_windows_buttons_answer_the_model_question(home, monkeypatch):
    registry, speech, fetcher, folder = model_world(home, monkeypatch)
    code, io = go(home, "model", io=Buttons([False]), registry=registry, speech=speech, fetcher=fetcher)
    assert code == 2 and io.asked == ["Download the listening model now? Type yes to go on."] and io.prompts == [] and fetcher.calls == []
    code, io = go(home, "model", io=Buttons([True]), registry=registry, speech=speech, fetcher=fetcher)
    assert code == 0 and len(fetcher.calls) == 2


def test_model_with_a_stray_word_or_option_does_nothing(home, monkeypatch):
    registry, speech, fetcher, folder = model_world(home, monkeypatch)
    code, _io = go(home, "model", "extra", registry=registry, speech=speech, fetcher=fetcher)
    assert code == 2 and fetcher.calls == []
    code, _io = go(home, "model", "--project", "anna", registry=registry, speech=speech, fetcher=fetcher)
    assert code == 2 and fetcher.calls == []


def test_every_command_the_messages_name_is_one_a_front_really_runs(tmp_path, monkeypatch):
    """The setup command once stood in a message as the way to get the model and could not do it. Each command a message names is checked here by running its front."""
    import subprocess
    import sys as _sys
    for name in ("HF_HUB_CACHE", "HUGGINGFACE_HUB_CACHE", "HF_HOME", "XDG_CACHE_HOME"):
        monkeypatch.delenv(name, raising=False)
    tools = str(Path(rf.__file__).resolve().parents[2])
    env = dict(os.environ, PYTHONPATH=tools, HOME=str(tmp_path), PYTHONDONTWRITEBYTECODE="1")
    for command in (rf.RECORDINGS_COMMAND, rf.MODEL_COMMAND, rf.ROUNDS_COMMAND, rf.BUILDENV_STUDIO_COMMAND):
        assert command.startswith("python3 -m voice_studio."), command
    verb = rf.MODEL_COMMAND.split()[-1]
    assert verb in rf.COMMANDS and verb in rf.OPTIONS
    helped = subprocess.run([_sys.executable, "-m", rf.RECORDINGS_COMMAND.split()[2], "help"], capture_output=True, text=True, env=env, cwd=str(tmp_path), timeout=120)
    assert helped.returncode == 0 and "model [--yes]: get the listening model" in helped.stdout
    asked = subprocess.run([_sys.executable, "-m", rf.RECORDINGS_COMMAND.split()[2], verb], capture_output=True, text=True, env=env, cwd=str(tmp_path), stdin=subprocess.DEVNULL, timeout=120)
    assert asked.returncode == 2 and "--yes" in asked.stdout and "The listening model lets the computer write down what it hears" in asked.stdout
    assert not (tmp_path / "ack-voice-studio" / "tool" / "downloads").exists() and not (tmp_path / "ack-voice-studio" / "state").exists(), "nobody to ask: nothing downloaded, nothing saved"


def test_finish_shows_what_it_will_do_then_asks_and_a_no_starts_nothing(home, anna, tmp_path):
    write_take(anna.recordings, OLD, status="finishing", duration=None)
    studio, speech = ready_world(tmp_path)
    start = Starter()
    code, io = go(home, "finish", answers=["no"], start=start, studio=studio, speech=speech)
    assert code == 2 and io.prompts == ["Start listening now? Type yes to go on. "] and start.calls == [] and "Nothing was done." in io.text
    assert "1 recording is waiting to be listened to." in io.lines
    assert io.events.index(("say", "1 recording is waiting to be listened to.")) < io.events.index(("ask", io.prompts[0]))


def test_finish_with_a_yes_starts_one_job_for_this_project_on_the_processor_with_the_right_words(home, anna, tmp_path):
    write_take(anna.recordings, OLD, status="finishing", duration=None)
    write_take(anna.recordings, NEW, status="queued", duration=None)
    studio, speech = ready_world(tmp_path)
    start = Starter()
    code, io = go(home, "finish", answers=["yes"], start=start, studio=studio, speech=speech)
    assert code == 0 and len(start.calls) == 1 and "2 recordings are waiting to be listened to." in io.lines
    jobs_root, spec, when = start.calls[0]
    assert jobs_root == home.jobs and when == NOW and spec.kind == "process" and spec.project == "anna" and spec.gpu is False and spec.cwd == "/tools"
    argv = list(spec.argv)
    assert argv[1:3] == ["-m", "freeform_studio.process"] and argv[argv.index("--output") + 1] == anna.recordings
    assert argv[argv.index("--asr-model") + 1] == str(tmp_path / "speech-model") and argv[argv.index("--asr-device") + 1] == "cpu" and "--json" in argv
    assert "Listening has started (20261011-123000-process-abcd)." in io.lines and io.lines[-1].endswith("show --project anna")


def test_finish_with_yes_on_the_line_does_not_ask_and_nobody_to_ask_starts_nothing(home, anna, tmp_path):
    write_take(anna.recordings, OLD, status="finishing", duration=None)
    studio, speech = ready_world(tmp_path)
    start = Starter()
    code, io = go(home, "finish", "--yes", start=start, studio=studio, speech=speech)
    assert code == 0 and io.prompts == [] and len(start.calls) == 1
    start = Starter()
    code, io = go(home, "finish", interactive=False, start=start, studio=studio, speech=speech)
    assert code == 2 and "--yes" in io.text and start.calls == []


def test_finish_while_the_computer_is_already_listening_starts_nothing_and_does_not_ask(home, anna, tmp_path):
    write_take(anna.recordings, OLD, status="transcribing", duration=None)
    made_job(home, ["x"], "running", kind="process", project="anna")
    studio, speech = ready_world(tmp_path)
    start = Starter()
    code, io = go(home, "finish", "--yes", start=start, studio=studio, speech=speech)
    assert code == 2 and io.prompts == [] and start.calls == []
    assert "The computer is already listening to this project's recordings. To see how it is going, run: " in io.text


def test_finish_after_an_earlier_listening_ended_is_allowed_to_start_again(home, anna, tmp_path):
    write_take(anna.recordings, OLD, status="transcribing", duration=None)
    made_job(home, ["x"], "interrupted", kind="process", project="anna")
    studio, speech = ready_world(tmp_path)
    start = Starter()
    code, _io = go(home, "finish", "--yes", start=start, studio=studio, speech=speech)
    assert code == 0 and len(start.calls) == 1


def test_a_job_that_could_not_start_is_explained_in_three_parts(home, anna, tmp_path):
    write_take(anna.recordings, OLD, status="finishing", duration=None)
    studio, speech = ready_world(tmp_path)
    code, io = go(home, "finish", "--yes", start=Starter(error=jobs.JobError("launch_failed", "exit 1")), studio=studio, speech=speech)
    assert code == 1 and "The job could not be started." in io.text and "Nothing is running, and your files were not changed." in io.text


def test_finish_leaves_the_recordings_exactly_as_they_are(home, anna, tmp_path):
    write_take(anna.recordings, OLD, status="finishing", duration=None)
    studio, speech = ready_world(tmp_path)
    before = tree(anna.recordings)
    go(home, "finish", "--yes", start=Starter(), studio=studio, speech=speech)
    assert tree(anna.recordings) == before


# ---------------------------------------------------------------- set

def world_with_ready(home, anna, tmp_path):
    write_take(anna.recordings, OLD, status="ready", duration=120.0)
    return ready_world(tmp_path)


def test_set_with_a_bad_gain_does_nothing_and_says_the_limit(home, anna, tmp_path):
    studio, _ = world_with_ready(home, anna, tmp_path)
    for bad in ("loud", "-1", "61", "nan", "inf", "١٢", "1e999"):
        runner = Runner()
        code, io = go(home, "set", "--max-gain-db", bad, studio=studio, system=runner)
        assert code == 2 and "must be a number from 0 to 60. Nothing was done." in io.text and runner.calls == [], bad


@pytest.mark.parametrize("good", ["0", "6", "12.5", "60"])
def test_a_good_gain_is_handed_to_the_builder(home, anna, tmp_path, good):
    studio, _ = world_with_ready(home, anna, tmp_path)
    runner = Runner(build=write_dataset)
    go(home, "set", "--preview", "--max-gain-db", good, studio=studio, system=runner)
    assert runner.previews[0]["argv"][runner.previews[0]["argv"].index("--max-gain-db") + 1] == "%g" % float(good)


def test_without_a_gain_the_builders_own_default_is_left_alone(home, anna, tmp_path):
    studio, _ = world_with_ready(home, anna, tmp_path)
    runner = Runner()
    go(home, "set", "--preview", studio=studio, system=runner)
    assert "--max-gain-db" not in runner.previews[0]["argv"]


def test_set_with_no_recording_ready_says_what_to_do_first(home, anna, tmp_path):
    studio, _ = ready_world(tmp_path)
    write_take(anna.recordings, OLD, status="finishing", duration=None)
    runner = Runner()
    code, io = go(home, "set", studio=studio, system=runner)
    assert code == 2 and "No recording is ready to use yet. Let the computer listen to them first: " in io.text and runner.calls == []


def test_set_without_the_studio_programs_says_what_to_run(home, anna):
    write_take(anna.recordings, OLD, status="ready")
    runner = Runner()
    code, io = go(home, "set", system=runner)
    assert code == 2 and "The studio programs are not ready (Not set up yet)." in io.text and runner.calls == []


def test_set_with_a_working_place_that_is_not_there_does_nothing(home, anna, tmp_path):
    studio, _ = world_with_ready(home, anna, tmp_path)
    save_project(anna, replace(load_project(anna), scratch=Scratch(SCRATCH_CUSTOM, str(tmp_path / "unplugged"))))
    runner = Runner()
    code, io = go(home, "set", studio=studio, system=runner)
    assert code == 2 and "This project's working place is not available." in io.text and runner.calls == []


def test_set_notes_the_recordings_that_will_not_be_included_yet(home, anna, tmp_path):
    studio, _ = world_with_ready(home, anna, tmp_path)
    write_take(anna.recordings, NEW, status="finishing", duration=None)
    _code, io = go(home, "set", "--preview", studio=studio, system=Runner())
    assert "1 recording is still waiting to be listened to, so it will not be included." in io.lines


def test_the_preview_says_what_the_set_would_hold_what_is_left_out_and_why_and_writes_nothing(home, anna, tmp_path):
    studio, _ = world_with_ready(home, anna, tmp_path)
    runner = Runner(preview=CommandResult(0, builder_lines(pieces=12, minutes=7.4, reasons={"you dropped it": 3, "no text": 1}, flags={"noisy": 2, "odd_new_flag": 1})))
    before = tree(home.home)
    code, io = go(home, "set", "--preview", studio=studio, system=runner)
    assert code == 0 and io.prompts == [] and len(runner.calls) == 1 and runner.calls[0]["argv"][-1] == "--dry-run"
    assert "This is what the training set would hold. Nothing was written." in io.lines and "Pieces in it: 12. Speech in it: about 7.4 minutes." in io.lines
    assert "Pieces left out: 4." in io.lines and "  3 left out, because you dropped them in Review" in io.lines and "  1 left out, because they have no words" in io.lines
    assert "  2 of them: there is background noise" in io.lines and "  1 of them: odd new flag" in io.lines
    assert "About 7.4 of 60 minutes of speech you can use so far." in io.lines
    assert "Under about ten minutes of speech tends to give an uneven voice. More recording will help." in io.lines
    assert "That was only a preview. Nothing was written. To make the training set, run: python3 -m voice_studio.recordings set --project anna" in io.lines
    assert tree(home.home) == before and not os.path.exists(ProjectPaths(home.projects + "/anna").default_scratch + "/datasets")


def test_the_preview_runs_the_builder_of_the_studio_programs_on_this_projects_recordings_into_a_name_made_from_the_time(home, anna, tmp_path):
    studio, _ = world_with_ready(home, anna, tmp_path)
    runner = Runner()
    go(home, "set", "--preview", studio=studio, system=runner)
    argv = list(runner.calls[0]["argv"])
    assert argv[1:3] == ["-m", "freeform_studio.build_dataset"] and argv[argv.index("--output") + 1] == anna.recordings
    assert argv[argv.index("--out") + 1] == anna.root + "/scratch/datasets/dataset-20261011-123000" and runner.calls[0]["cwd"] == "/tools"
    assert runner.calls[0]["timeout"] == rf.PREVIEW_TIMEOUT_S


def test_set_asks_after_the_preview_and_a_no_builds_nothing(home, anna, tmp_path):
    studio, _ = world_with_ready(home, anna, tmp_path)
    runner = Runner(build=write_dataset)
    code, io = go(home, "set", answers=["no"], studio=studio, system=runner)
    assert code == 2 and io.prompts == ["Make this training set now? It is written to a new folder. Type yes to go on. "] and len(runner.calls) == 1 and runner.builds == []
    assert io.events.index(("say", "Pieces in it: 2. Speech in it: about 1.5 minutes.")) < io.events.index(("ask", io.prompts[0]))
    assert not os.path.exists(anna.root + "/scratch/datasets")


def test_a_yes_builds_into_a_new_folder_checks_it_and_says_how_to_train_on_it(home, anna, tmp_path):
    studio, _ = world_with_ready(home, anna, tmp_path)
    runner = Runner(build=write_dataset)
    code, io = go(home, "set", answers=["yes"], studio=studio, system=runner)
    folder = anna.root + "/scratch/datasets/dataset-20261011-123000"
    assert code == 0 and len(runner.builds) == 1 and runner.builds[0]["timeout"] == rf.BUILD_TIMEOUT_S
    assert "The training set is ready." in io.lines and "The training set is in %s." % folder in io.lines and "It holds 2 pieces and takes up " in io.text
    assert io.lines[-1] == "To train on it, run: python3 -m voice_studio.rounds start --set dataset-20261011-123000 --project anna"
    assert os.path.isfile(folder + "/metadata.csv") and os.listdir(anna.root + "/scratch/datasets") == ["dataset-20261011-123000"]


def test_the_scratch_folder_has_to_be_owner_only_when_it_is_made(home, anna, tmp_path):
    studio, _ = world_with_ready(home, anna, tmp_path)
    go(home, "set", "--yes", studio=studio, system=Runner(build=write_dataset))
    assert (os.stat(anna.root + "/scratch/datasets").st_mode & 0o077) == 0


def test_the_windows_buttons_answer_the_training_set_question(home, anna, tmp_path):
    studio, _ = world_with_ready(home, anna, tmp_path)
    io = Buttons([True])
    code, io = go(home, "set", io=io, studio=studio, system=Runner(build=write_dataset))
    assert code == 0 and io.asked == ["Make this training set now? It is written to a new folder. Type yes to go on."] and io.prompts == []


def test_set_with_yes_on_the_line_does_not_ask_and_with_nobody_to_ask_writes_nothing(home, anna, tmp_path):
    studio, _ = world_with_ready(home, anna, tmp_path)
    code, io = go(home, "set", "--yes", studio=studio, system=Runner(build=write_dataset))
    assert code == 0 and io.prompts == []
    shutil.rmtree(anna.root + "/scratch")
    runner = Runner(build=write_dataset)
    code, io = go(home, "set", interactive=False, studio=studio, system=runner)
    assert code == 2 and "--yes" in io.text and runner.builds == [] and not os.path.exists(anna.root + "/scratch/datasets")


def test_a_gain_is_passed_to_the_build_as_well_as_the_preview(home, anna, tmp_path):
    studio, _ = world_with_ready(home, anna, tmp_path)
    runner = Runner(build=write_dataset)
    go(home, "set", "--yes", "--max-gain-db", "9", studio=studio, system=runner)
    for call in runner.calls:
        assert call["argv"][call["argv"].index("--max-gain-db") + 1] == "9"


def test_nothing_that_qualifies_is_said_with_its_reasons_and_nothing_is_asked_or_built(home, anna, tmp_path):
    studio, _ = world_with_ready(home, anna, tmp_path)
    runner = Runner(preview=CommandResult(0, builder_lines(pieces=0, minutes=0, result="nothing_qualified", reasons={"not approved yet": 5}, flags={})))
    code, io = go(home, "set", "--yes", studio=studio, system=runner)
    assert code == 2 and io.prompts == [] and runner.builds == []
    assert "Nothing qualified, so no training set was made. The reasons are listed." in io.lines and "  5 left out, because they are not approved yet" in io.lines


def test_a_builder_that_gives_no_answer_is_a_failure_that_shows_the_end_of_what_it_said(home, anna, tmp_path):
    studio, _ = world_with_ready(home, anna, tmp_path)
    runner = Runner(preview=CommandResult(1, "", "Traceback\nValueError: something broke\n"))
    code, io = go(home, "set", "--yes", studio=studio, system=runner)
    assert code == 1 and "The studio program did not give an answer that can be read, so no training set was made." in io.lines
    assert "  Technical detail: Traceback ValueError: something broke" in io.lines and runner.builds == []
    runner = Runner(preview=None)
    runner.preview = None
    code, io = go(home, "set", "--yes", studio=studio, system=runner)
    assert code == 1 and "did not give an answer" in io.text


def test_a_build_that_fails_its_own_checks_is_not_called_ready_and_the_folder_is_named_and_kept(home, anna, tmp_path):
    studio, _ = world_with_ready(home, anna, tmp_path)

    def bad(argv):
        out = argv[argv.index("--out") + 1]
        os.makedirs(out)
        return CommandResult(1, builder_lines(pieces=1, result="problems", problems=["a clip is missing"], out=out))

    runner = Runner(build=bad)
    code, io = go(home, "set", "--yes", studio=studio, system=runner)
    folder = anna.root + "/scratch/datasets/dataset-20261011-123000"
    assert code == 1 and "The training set was made but failed its checks, so it should not be used." in io.lines and "Note: a clip is missing" in io.lines
    assert "Whatever was written was left in %s. Nothing was deleted." % folder in io.lines and "The training set is ready." not in io.text and os.path.isdir(folder)


def test_a_build_that_says_nothing_qualified_after_a_good_preview_is_not_an_error(home, anna, tmp_path):
    studio, _ = world_with_ready(home, anna, tmp_path)
    runner = Runner(build=CommandResult(0, builder_lines(pieces=0, result="nothing_qualified", reasons={"no text": 2}, flags={})))
    code, io = go(home, "set", "--yes", studio=studio, system=runner)
    assert code == 2 and "Nothing qualified" in io.text


def test_a_build_that_leaves_an_incomplete_folder_is_refused_in_words(home, anna, tmp_path):
    studio, _ = world_with_ready(home, anna, tmp_path)

    def hollow(argv):
        out = argv[argv.index("--out") + 1]
        os.makedirs(out)
        return CommandResult(0, builder_lines(pieces=1, result="built", out=out))

    code, io = go(home, "set", "--yes", studio=studio, system=Runner(build=hollow))
    folder = anna.root + "/scratch/datasets/dataset-20261011-123000"
    assert code == 1 and "The training set was made but failed its checks, so it should not be used." in io.lines
    assert "Whatever was written was left in %s. Nothing was deleted." % folder in io.lines and "  Technical detail: dataset-20261011-123000" in io.lines and "The training set is ready." not in io.text


def test_a_name_already_taken_is_never_written_over(home, anna, tmp_path):
    studio, _ = world_with_ready(home, anna, tmp_path)
    taken = anna.root + "/scratch/datasets/dataset-20261011-123000"
    os.makedirs(taken)
    open(taken + "/precious.txt", "w").write("mine")
    runner = Runner(build=write_dataset)
    code, io = go(home, "set", "--yes", studio=studio, system=runner)
    assert code == 1 and runner.builds == [] and open(taken + "/precious.txt").read() == "mine"


def test_set_does_not_touch_the_recordings(home, anna, tmp_path):
    studio, _ = world_with_ready(home, anna, tmp_path)
    before = tree(anna.recordings)
    go(home, "set", "--yes", studio=studio, system=Runner(build=write_dataset))
    assert tree(anna.recordings) == before


# ---------------------------------------------------------------- the whole way, with real jobs

def wait_until_ended(root, timeout=90.0):
    import time
    deadline = time.time() + timeout
    while time.time() < deadline:
        found = jobs.list_jobs(root).jobs
        if found and found[-1].status not in jobs.ACTIVE:
            return found[-1]
        time.sleep(0.1)
    raise AssertionError("the job did not end")


@needs_ffmpeg
def test_from_a_folder_of_files_to_a_training_set_with_a_real_job_and_the_real_builder(home, anna, tmp_path):
    pytest.importorskip("numpy", reason="Freeform Studio's processor and builder need numpy")
    studio, speech = ready_world(tmp_path)

    def real(*argv, answers=()):
        io = Terminal(answers)
        code = rf.run_recordings(list(argv), home, load_registry(), CAT, io, studio=studio, speech=speech, now=NOW)
        return code, io

    code, io = real("import", str(pairs_folder(tmp_path, 4)), "--kind", "pairs", "--yes")
    assert code == 0 and rec.read_takes(anna.recordings).waiting == 1
    code, io = real("finish", "--yes")
    assert code == 0 and "Listening has started (" in io.text
    ended = wait_until_ended(home.jobs)
    assert ended.status == jobs.JobStatus.FINISHED, ended
    view = rec.read_takes(anna.recordings)
    assert (view.ready, view.waiting, view.failed) == (1, 0, 0) and view.minutes > 0
    code, io = real("show")
    assert code == 0 and "Ready: 1. Waiting to be listened to: 0." in io.text and io.lines[-1].startswith("To make a training set, run:")
    code, io = real("set", answers=["yes"])
    assert code == 0 and "The training set is ready." in io.lines, io.text
    rows, size = commands.dataset_size(anna.root + "/scratch/datasets/dataset-20261011-123000")
    assert rows >= 1 and size > 0
