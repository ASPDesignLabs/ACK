# SPDX-License-Identifier: GPL-3.0-or-later
"""The terminal front for hearing the voice file (plan task VS-5.4): what it shows before it asks, that a no (or nobody to ask) writes nothing, what it says when something fails, and how
it plays and asks whether the sounds were heard. The speaking program is run for real as a child process; the sound players are recorded."""
import os
from pathlib import Path

import pytest

from vs_listen_helpers import VOICE_FOLDER, ListenRig
from vs_rounds_helpers import NOW
from vs_startvoice_helpers import Terminal, implies_permission, leaked_keys
from vs_voicefile_helpers import TOOLS
from voice_studio.core import listen, listen_flow as lf, text, voicefile_flow as vff
from voice_studio.core.diskbudget import DEFAULT_TABLE, floors_for
from voice_studio.core.system import CommandResult

CAT = text.load_catalog("en")
FOLDER = "%s-heard-20261011-120000" % VOICE_FOLDER


class Rig(ListenRig):
    def run(self, *argv, answers=(), interactive=True, training=None, studio=None):
        io = Terminal(answers, interactive)
        code = lf.run_listen(list(argv), self.home, NOW, training or self.training_env, studio or self.studio_env, self.system, str(TOOLS), CAT, io)
        assert leaked_keys(io.text + "\n".join(io.prompts)) == [], "a catalog key was printed instead of words"
        assert implies_permission(io.text) == [], "something printed says or implies that use is permitted"
        return code, io

    def made(self):
        folder = Path(self.paths.default_scratch, "listening")
        return sorted(os.listdir(folder)) if folder.is_dir() else []


@pytest.fixture(autouse=True)
def no_inherited_path(monkeypatch):
    monkeypatch.delenv("PYTHONPATH", raising=False)           # the speaking program must be given its path, not find it by luck in ours


@pytest.fixture
def rig(tmp_path):
    return Rig(tmp_path)


def asked(io):
    return [p for p in io.prompts]


# ---------------------------------------------------------------- the good run

def test_it_shows_the_whole_plan_before_it_asks_and_asks_once_before_anything_is_written(rig):
    code, io = rig.run(answers=["yes", "yes"])
    first_ask = next(i for i, (kind, _t) in enumerate(io.events) if kind == "ask")
    before = "\n".join(t for kind, t in io.events[:first_ask] if kind == "say")
    assert code == 0
    for part in ("would be heard like this", "1. Hello, my name is Anna.", "2. I need some help, please.", "3. Thank you, that is all.", "the same speech engine", FOLDER, "play them one after another",
                 "Checked before starting:", "Ctrl+C"):
        assert part in before, part
    assert io.prompts[0].strip() == "Make the sound files and play them now? Type yes to go on."


def test_a_yes_makes_the_files_plays_each_in_turn_and_asks_whether_they_were_heard(rig):
    code, io = rig.run(answers=["yes", "yes"])
    assert code == 0 and rig.made() == [FOLDER]
    assert [n for n, _a, _t in rig.system.played] == ["ffplay"] * 3
    for number, sentence in ((1, "Hello, my name is Anna."), (2, "I need some help, please."), (3, "Thank you, that is all.")):
        assert "Playing %d of 3: %s" % (number, sentence) in io.text
    assert io.prompts[1].strip() == "Did you hear them all? Type yes if you did."
    assert "Good. These sounds were made from the very files in the zip" in io.text and "copy the zip file to the phone" in io.text
    assert "They are small, and this tool never deletes them." in io.text
    folder = str(Path(rig.paths.default_scratch, "listening", FOLDER))
    assert "The sound files are ready in " + folder in io.text and rig.system.played[0][1][-1] == folder + "/clip-1.wav"
    assert "played with ffplay" in io.text


def test_each_clip_row_says_its_number_its_words_and_its_length(rig):
    _code, io = rig.run(answers=["yes", "yes"])
    rows = [l.strip() for l in io.lines if l.strip().startswith(("1. Hello", "2. I need", "3. Thank")) and "seconds" in l]
    assert rows == ["1. Hello, my name is Anna. (1.6 seconds)", "2. I need some help, please. (1.7 seconds)", "3. Thank you, that is all. (1.6 seconds)"]


def test_no_voice_files_or_other_files_are_changed_only_a_new_folder_is_added(rig):
    before = {str(p): p.read_bytes() for p in Path(rig.paths.root).rglob("*") if p.is_file()}
    rig.run(answers=["yes", "yes"])
    after = {str(p): p.read_bytes() for p in Path(rig.paths.root).rglob("*") if p.is_file()}
    assert {k: v for k, v in after.items() if "/listening/" not in k} == before and any("/listening/" in k for k in after)


# ---------------------------------------------------------------- a no, and nobody to ask

def test_a_no_writes_nothing_and_plays_nothing(rig):
    code, io = rig.run(answers=["no"])
    assert code == 2 and "Nothing was done." in io.text and rig.made() == [] and rig.system.played == []


@pytest.mark.parametrize("answer", ["", "YES please", "no", "maybe", "yes!"])
def test_anything_but_a_yes_is_a_no(rig, answer):
    code, io = rig.run(answers=[answer])
    assert code == 2 and rig.made() == [], answer


def test_a_terminal_with_nobody_at_it_is_never_asked_and_writes_nothing(rig):
    code, io = rig.run(interactive=False)
    assert code == 2 and io.prompts == [] and "There was nobody to ask" in io.text and "Nothing was done." in io.text and rig.made() == []


def test_yes_on_the_command_line_skips_the_first_question_but_not_the_one_about_hearing(rig):
    code, io = rig.run("--yes", answers=["yes"])
    assert code == 0 and [p.strip() for p in io.prompts] == ["Did you hear them all? Type yes if you did."]


def test_with_yes_and_nobody_to_ask_it_runs_plays_and_asks_nothing(rig):
    code, io = rig.run("-y", interactive=False)
    assert code == 0 and io.prompts == [] and rig.made() == [FOLDER] and len(rig.system.played) == 3 and "copy the zip file to the phone" in io.text


# ---------------------------------------------------------------- what was heard

def test_not_hearing_them_points_at_the_folder_and_does_not_claim_the_voice_is_wrong(rig):
    code, io = rig.run(answers=["yes", "no"])
    assert code == 0 and "Open one with any player to check your speakers" in io.text and "Good. These sounds" not in io.text and FOLDER in io.text


def test_a_player_that_does_not_work_hands_over_to_the_next_and_the_clips_still_play(tmp_path):
    rig = Rig(tmp_path, installed=("ffplay", "paplay", "pw-play"))
    rig.system.results = {"pw-play": CommandResult(1)}
    code, io = rig.run("--yes", answers=["yes"])
    assert code == 0 and [n for n, _a, _t in rig.system.played] == ["pw-play", "paplay", "paplay", "paplay"] and "played with paplay" in io.text


def test_when_no_way_of_playing_works_it_says_where_the_files_are_and_keeps_them(tmp_path):
    rig = Rig(tmp_path, installed=())
    code, io = rig.run("--yes", answers=[])
    assert code == 1 and "No way of playing sound worked on this computer" in io.text and "tried: " in io.text and rig.made() == [FOLDER]
    assert "If this is Ubuntu inside Windows" not in io.text and rig.system.played == []
    assert "Playing 1 of 3" in io.text and "Playing 2 of 3" not in io.text, "it stops trying at the first clip when nothing plays"


def test_under_wsl_the_same_failure_adds_the_hint_about_opening_the_folder_from_windows(tmp_path):
    rig = Rig(tmp_path, installed=(), wsl=True)
    code, io = rig.run("--yes")
    assert code == 1 and "If this is Ubuntu inside Windows, open that folder from Windows and play the files there." in io.text


def test_under_wsl_a_failing_sound_server_falls_back_to_windows_own_player(tmp_path):
    rig = Rig(tmp_path, installed=("ffplay", "powershell.exe", "wslpath"), wsl=True)
    rig.system.results = {"ffplay": CommandResult(1, "", "Could not initialize SDL - No such audio device")}
    code, io = rig.run("--yes", answers=["yes"])
    assert code == 0 and [n for n, _a, _t in rig.system.played] == ["ffplay", "powershell.exe", "powershell.exe", "powershell.exe"] and "played with windows" in io.text


def test_sounds_that_all_came_out_silent_are_said_so_and_not_played(tmp_path):
    rig = Rig(tmp_path, mode="silent")
    code, io = rig.run("--yes")
    assert code == 1 and "Every sound came out silent, so nothing was played" in io.text and rig.system.played == [] and "this one came out silent" in io.text
    assert "Nothing was sent anywhere." in io.text


# ---------------------------------------------------------------- the plan's warnings

def test_a_voice_for_another_language_is_warned_that_the_sentences_are_english(tmp_path):
    rig = Rig(tmp_path, language="de", make=False)
    rig.make_voice(VOICE_FOLDER, language="de")
    _code, io = rig.run(answers=["no"])
    assert "These sentences are in English. A voice made for another language will not say them well." in io.text


def test_an_english_voice_gets_no_such_warning(rig):
    _code, io = rig.run(answers=["no"])
    assert "These sentences are in English" not in io.text


def test_tight_room_is_said_and_it_can_go_on(rig):
    floors = floors_for(DEFAULT_TABLE, holds_recordings=True)
    rig.system.free = (10 ** 12, listen.NEED_BYTES + floors.stop)
    code, io = rig.run(answers=["yes", "yes"])
    assert code == 0 and "Free space is getting tight" in io.text


def test_not_enough_room_stops_before_asking(rig):
    floors = floors_for(DEFAULT_TABLE, holds_recordings=True)
    rig.system.free = (10 ** 12, listen.NEED_BYTES + floors.stop - 1)
    code, io = rig.run(answers=["yes"])
    assert code == 1 and "not enough free space to make the sound files" in io.text and io.prompts == [] and rig.made() == []


def test_an_unreadable_disk_is_said_not_guessed(rig):
    rig.system.free = None
    real = rig.system.disk_free
    rig.system.disk_free = lambda path: None
    code, io = rig.run(answers=["no"])
    assert "could not be read, so it was not checked" in io.text


# ---------------------------------------------------------------- things that are not ready

def test_with_no_voice_file_it_says_so_and_writes_nothing(tmp_path):
    rig = Rig(tmp_path, make=False)
    code, io = rig.run("--yes")
    assert code == 1 and "There is no voice file to listen to yet." in io.text and rig.made() == []


def test_an_unknown_folder_name_is_refused_with_what_to_do(rig):
    code, io = rig.run("--folder", "nope", "--yes")
    assert code == 1 and "That voice file folder was not found." in io.text and rig.made() == []


def test_a_named_folder_is_listened_to(rig):
    rig.make_voice("voice-check-round-002-20261011-150000")
    code, io = rig.run("--folder", "voice-check-round-002-20261011-150000", "--yes", answers=["yes"])
    assert code == 0 and rig.made() == ["voice-check-round-002-20261011-150000-heard-20261011-120000"]


def test_a_voice_the_phone_would_refuse_lists_why_in_plain_words(tmp_path):
    rig = Rig(tmp_path, make=False)
    rig.make_voice(VOICE_FOLDER, patched=False)
    code, io = rig.run("--yes")
    assert code == 1 and "The voice file is not ready for the phone, so it was not played." in io.text and "    - " in io.text and rig.made() == []


def test_a_folder_that_is_not_the_zip_is_refused_in_plain_words(rig):
    model = Path(rig.paths.exports, VOICE_FOLDER, "my_voice.onnx")
    data = bytearray(model.read_bytes())
    data[100] ^= 0xFF
    model.write_bytes(bytes(data))
    code, io = rig.run("--yes")
    assert code == 1 and "not the same as the ones in its zip file" in io.text and "Do not use that zip file." in io.text and rig.made() == []


def test_no_studio_programs_names_the_command_that_sets_them_up(rig):
    code, io = rig.run("--yes", studio=lambda: (None, "absent"))
    assert code == 1 and "The studio programs are not ready on this computer (Not set up yet)." in io.text and "Set them up first with: python3 -m voice_studio.buildenv studio" in io.text and rig.made() == []


def test_no_training_programs_names_the_command_that_sets_them_up(rig):
    code, io = rig.run("--yes", training=lambda: (None, "absent"))
    assert code == 1 and "The training programs are not ready on this computer (Not set up yet)" in io.text and "python3 -m voice_studio.buildenv training" in io.text and rig.made() == []


def test_no_pronunciation_data_is_a_plain_refusal(tmp_path):
    rig = Rig(tmp_path, data=False)
    code, io = rig.run("--yes")
    assert code == 1 and "pronunciation data for this voice's language was not found" in io.text and rig.made() == []


def test_a_working_place_that_is_not_ready_stops_before_anything(rig, monkeypatch):
    monkeypatch.setattr(lf, "scratch_ready", lambda project, paths: False)
    code, io = rig.run("--yes")
    assert code == 2 and "is not ready, and nothing was started" in io.text and rig.made() == []


def test_a_project_that_does_not_exist_is_named(rig):
    code, io = rig.run("--project", "nobody", "--yes")
    assert code == 2 and "nobody" in io.text and rig.made() == []


@pytest.mark.parametrize("argv, said", [(("--bogus",), "--bogus"), (("extra",), "extra"), (("--folder",), "--folder"), (("--project", "a", "--project", "b"), "--project")])
def test_a_mistake_in_the_options_does_nothing_and_says_so(rig, argv, said):
    code, io = rig.run(*argv)
    assert code == 2 and said in io.text and "Nothing was done" in io.text and rig.made() == []


# ---------------------------------------------------------------- when the run fails

@pytest.mark.parametrize("mode, says", [("no_engine", "is not installed with the studio programs"), ("load_failed", "could not be turned into sound"), ("crash", "could not be turned into sound"),
                                       ("nothing", "did not all get made")])
def test_a_failed_run_says_what_happened_what_was_left_and_what_to_do(tmp_path, mode, says):
    rig = Rig(tmp_path, mode=mode)
    code, io = rig.run("--yes")
    assert code == 1 and says in io.text and "The new folder was left as it is, and nothing was deleted." in io.text and "What was made so far is in " in io.text
    assert rig.system.played == []


def test_the_technical_detail_of_a_crash_is_shown_for_whoever_helps(tmp_path):
    rig = Rig(tmp_path, mode="crash")
    _code, io = rig.run("--yes")
    assert "size: 2" in io.text


def test_stopping_with_ctrl_c_leaves_the_folder_and_says_so(rig, monkeypatch):
    real = rig.system.run

    def stop(argv, timeout=15.0, cwd=None, env=None):
        if "voice_studio.listen_runner" in argv:
            raise KeyboardInterrupt()
        return real(argv, timeout=timeout, cwd=cwd, env=env)
    monkeypatch.setattr(rig.system, "run", stop)
    code, io = rig.run("--yes")
    assert code == 1 and "Stopped. What was made so far is in " in io.text and "Nothing was deleted." in io.text


# ---------------------------------------------------------------- the command as a whole

def test_help_lists_listen_with_its_options(tmp_path):
    rig = Rig(tmp_path)
    io = Terminal()
    assert vff.run_voicefile(["help"], rig.home, None, CAT, io, training=rig.training_env, system=rig.system, tools_dir=str(TOOLS)) == 0
    assert "listen [--yes] [--project name] [--folder name]: hear the voice file on this computer before it goes to the phone." in io.text


def test_the_voice_file_command_reaches_listen_and_a_missing_studio_lookup_means_not_ready(tmp_path):
    rig = Rig(tmp_path)
    io = Terminal()
    code = vff.run_voicefile(["listen", "--yes"], rig.home, None, CAT, io, training=rig.training_env, now=NOW, system=rig.system, tools_dir=str(TOOLS))
    assert code == 1 and "The studio programs are not ready on this computer (Not set up yet)" in io.text


def test_the_command_runs_end_to_end_through_the_voice_file_command_with_a_studio_lookup(tmp_path):
    rig = Rig(tmp_path)
    io = Terminal(["yes"])
    code = vff.run_voicefile(["listen", "--yes"], rig.home, None, CAT, io, training=rig.training_env, now=NOW, system=rig.system, tools_dir=str(TOOLS), studio=rig.studio_env)
    assert code == 0 and rig.made() == [FOLDER]


def test_the_options_listen_publishes_are_the_options_it_accepts():
    assert lf.OPTIONS == {"--yes", "-y", "--project", "--folder"} and vff.OPTIONS["listen"] == lf.OPTIONS


def test_a_bare_y_counts_as_a_yes_like_everywhere_else_in_the_tool(rig):
    code, _io = rig.run(answers=["y", "y"])
    assert code == 0 and rig.made() == [FOLDER]


def test_a_state_with_no_words_reads_as_itself_never_as_a_catalog_key(rig):
    code, io = rig.run("--yes", studio=lambda: (None, "some_new_state"))
    assert code == 1 and "(some_new_state)" in io.text


def test_a_run_where_only_one_sound_came_out_silent_plays_the_others_and_says_so(tmp_path):
    rig = Rig(tmp_path, mode="first_silent")
    code, io = rig.run("--yes", answers=["yes"])
    assert code == 0 and len(rig.system.played) == 2 and "Some of the sounds came out silent." in io.text and "1. Hello, my name is Anna.: this one came out silent." in io.text
    assert "Playing 1 of 3" not in io.text and "Playing 2 of 3" in io.text and "Playing 3 of 3" in io.text


def test_the_room_that_matters_is_the_one_where_the_sound_files_go(rig):
    floors = floors_for(DEFAULT_TABLE, holds_recordings=True)
    short, plenty = (10 ** 12, 1), (10 ** 12, 10 ** 12)
    rig.system.free = {rig.paths.rounds: plenty, rig.paths.default_scratch: short}
    code, io = rig.run(answers=["yes"])
    assert code == 1 and "not enough free space" in io.text and rig.made() == []
    rig.system.free = {rig.paths.rounds: short, rig.paths.default_scratch: plenty}
    code, io = rig.run(answers=["yes", "yes"])
    assert code == 0 and rig.made() == [FOLDER]
