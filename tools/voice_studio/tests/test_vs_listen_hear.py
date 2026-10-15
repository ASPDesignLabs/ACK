# SPDX-License-Identifier: GPL-3.0-or-later
"""Writing down what the computer hears in the sound files of a voice (plan task VS-5.5): what is sent to the listening program (never a sentence), what is believed of its answer, what
the screen shows beside each sentence, and that no failure of this step ever stops the sounds being played. The listening program is run for real as a child process, with a stand-in
for the model behind it."""
import json
import os
import stat
from pathlib import Path

import pytest

from vs_listen_helpers import SENTENCES, VOICE_FOLDER, FlowRig
from vs_rounds_helpers import NOW
from vs_voicefile_helpers import TOOLS
from voice_studio.core import jobs, listen
from voice_studio.core.system import CommandResult

FOLDER = "%s-heard-20261011-120000" % VOICE_FOLDER


@pytest.fixture(autouse=True)
def no_inherited_path(monkeypatch):
    monkeypatch.delenv("PYTHONPATH", raising=False)


@pytest.fixture
def rig(tmp_path):
    return FlowRig(tmp_path)


def listened(rig, **kw):
    """The sound files, made by the real speaking program, for the core tests."""
    plan = listen.plan_listen(rig.paths, rig.scratch_of(), None, SENTENCES, rig.training, rig.system, jobs.utc_stamp(NOW), 10**12)
    return plan, listen.listen(plan, rig.studio, rig.system, str(TOOLS))


def _scratch(self):
    from voice_studio.core.paths import ScratchPaths
    return ScratchPaths(self.paths.default_scratch)


FlowRig.scratch_of = _scratch


# ---------------------------------------------------------------- listen.hear: what is sent and what is believed

def test_it_sends_the_listening_program_the_model_folder_and_the_sound_files_and_never_a_sentence(rig):
    rig.set_heard(SENTENCES)
    _plan, heard = listened(rig)
    texts = listen.hear(heard, str(rig.speech_ready()()[0]), rig.studio, rig.system, str(TOOLS))
    seen = rig.seen_hear()
    assert seen["job"] == {"model_dir": str(rig.speech_dir), "clips": [c.path for c in heard.clips]}
    for sentence in SENTENCES:
        assert sentence not in json.dumps(seen["job"]) and sentence not in Path(heard.folder, "hear-job.json").read_text()
    assert texts == {1: SENTENCES[0], 2: SENTENCES[1], 3: SENTENCES[2]}


def test_the_program_is_the_studios_with_the_tools_on_its_path_and_the_folder_as_its_place(rig):
    rig.set_heard(SENTENCES)
    _plan, heard = listened(rig)
    listen.hear(heard, str(rig.speech_ready()()[0]), rig.studio, rig.system, str(TOOLS))
    seen = rig.seen_hear()
    assert seen["args"] == ["-m", "voice_studio.hear_runner", heard.folder + "/hear-job.json"] and seen["pythonpath"] == str(TOOLS)
    assert os.path.realpath(seen["cwd"]) == os.path.realpath(heard.folder) and seen["offline"] == {"HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1"}


def test_the_job_file_is_for_its_owner_only(rig):
    rig.set_heard(SENTENCES)
    _plan, heard = listened(rig)
    listen.hear(heard, str(rig.speech_ready()()[0]), rig.studio, rig.system, str(TOOLS))
    assert stat.S_IMODE(os.stat(heard.folder + "/hear-job.json").st_mode) == 0o600 and rig.seen_hear()["job_mode"] == "0o600"


def test_a_silent_sound_is_not_sent_and_the_others_are_numbered_as_they_were(tmp_path):
    rig = FlowRig(tmp_path, mode="first_silent")
    rig.set_heard(["I need some help, please.", "Thank you, that is all."])
    _plan, heard = listened(rig)
    texts = listen.hear(heard, str(rig.speech_ready()()[0]), rig.studio, rig.system, str(TOOLS))
    assert rig.seen_hear()["job"]["clips"] == [heard.clips[1].path, heard.clips[2].path] and texts == {2: "I need some help, please.", 3: "Thank you, that is all."}


def test_when_every_sound_is_silent_nothing_is_run_at_all(tmp_path):
    rig = FlowRig(tmp_path, mode="silent")
    _plan, heard = listened(rig)
    assert listen.hear(heard, str(rig.speech_ready()()[0]), rig.studio, rig.system, str(TOOLS)) == {} and not rig.heard_ran()
    assert not os.path.exists(heard.folder + "/hear-job.json")


def test_hearing_changes_none_of_the_sound_files(rig):
    rig.set_heard(SENTENCES)
    _plan, heard = listened(rig)
    before = {c.path: Path(c.path).read_bytes() for c in heard.clips}
    listen.hear(heard, str(rig.speech_ready()()[0]), rig.studio, rig.system, str(TOOLS))
    assert {c.path: Path(c.path).read_bytes() for c in heard.clips} == before


# ---------------------------------------------------------------- listen.hear: failures

@pytest.mark.parametrize("mode, detail", [("hear_fail", "hear_failed RuntimeError 1"), ("hear_no_engine", "no_engine"), ("hear_load_failed", "load_failed ValueError")])
def test_a_failure_the_program_reports_is_a_hear_failed_with_only_its_code_and_kind(rig, mode, detail):
    rig.set_hear_mode(mode)
    _plan, heard = listened(rig)
    with pytest.raises(listen.ListenError) as caught:
        listen.hear(heard, str(rig.speech_ready()()[0]), rig.studio, rig.system, str(TOOLS))
    assert caught.value.code == "hear_failed" and caught.value.detail == detail and caught.value.folder == heard.folder
    assert "boom" not in str(caught.value)


def test_a_program_that_dies_gives_the_end_of_what_it_said(rig):
    rig.set_hear_mode("hear_crash")
    _plan, heard = listened(rig)
    with pytest.raises(listen.ListenError) as caught:
        listen.hear(heard, str(rig.speech_ready()()[0]), rig.studio, rig.system, str(TOOLS))
    assert caught.value.code == "hear_failed" and "fell over" in caught.value.detail


@pytest.mark.parametrize("mode", ["hear_nothing", "hear_extra", "hear_out_of_range", "hear_not_text"])
def test_an_answer_that_is_missing_repeated_out_of_range_or_not_text_is_not_believed(rig, mode):
    rig.set_hear_mode(mode)
    _plan, heard = listened(rig)
    with pytest.raises(listen.ListenError) as caught:
        listen.hear(heard, str(rig.speech_ready()()[0]), rig.studio, rig.system, str(TOOLS))
    assert caught.value.code == "hear_failed"


def test_a_program_that_could_not_be_started_or_took_too_long_is_a_hear_failed(rig, monkeypatch):
    _plan, heard = listened(rig)
    monkeypatch.setattr(rig.system, "run", lambda *a, **k: None)
    with pytest.raises(listen.ListenError) as caught:
        listen.hear(heard, str(rig.speech_ready()()[0]), rig.studio, rig.system, str(TOOLS))
    assert caught.value.code == "hear_failed" and "could not be started or took too long" in caught.value.detail


def test_it_waits_as_long_as_the_limit_says_and_no_longer(rig, monkeypatch):
    _plan, heard = listened(rig)
    seen = {}
    monkeypatch.setattr(rig.system, "run", lambda argv, timeout=15.0, cwd=None, env=None: seen.update(timeout=timeout) or CommandResult(0, ""))
    with pytest.raises(listen.ListenError):
        listen.hear(heard, str(rig.speech_ready()()[0]), rig.studio, rig.system, str(TOOLS))
    assert seen["timeout"] == listen.HEAR_TIMEOUT_S == 300.0


def test_a_job_file_that_is_already_there_is_never_written_over(rig):
    _plan, heard = listened(rig)
    Path(heard.folder, "hear-job.json").write_text("mine")
    with pytest.raises(listen.ListenError) as caught:
        listen.hear(heard, str(rig.speech_ready()()[0]), rig.studio, rig.system, str(TOOLS))
    assert caught.value.code == "hear_failed" and Path(heard.folder, "hear-job.json").read_text() == "mine" and not rig.heard_ran()


def test_the_error_code_has_its_place_in_the_list():
    assert "hear_failed" in listen.ERROR_CODES


# ---------------------------------------------------------------- the screen

def test_the_plan_says_it_will_write_down_what_it_hears_when_it_can(rig):
    _code, io = rig.run(answers=["no"], speech="ready")
    assert "write down what the computer hears in each sound" in io.text and "nothing leaves this computer" in io.text and "no model here yet" not in io.text


def test_the_plan_says_why_when_the_listening_model_is_not_here_and_how_to_get_it(rig):
    _code, io = rig.run(answers=["no"])
    assert "skip writing down what the computer hears, because the program that does it has no model here yet." in io.text
    assert "To get it, run: python3 -m voice_studio.recordings model" in io.text


def test_the_plan_says_why_when_the_voice_is_not_english(tmp_path):
    rig = FlowRig(tmp_path, language="es-es")
    _code, io = rig.run(answers=["no"], speech="ready")
    assert "skip writing down what the computer hears, because that only works for English" in io.text and "no model here yet" not in io.text


def test_nothing_is_written_down_when_the_voice_is_not_english_even_if_the_model_is_here(tmp_path):
    rig = FlowRig(tmp_path, language="es-es")
    code, io = rig.run("--yes", answers=["yes"], speech="ready")
    assert code == 0 and not rig.heard_ran() and "The computer heard" not in io.text


def test_the_same_words_are_shown_under_each_sentence(rig):
    rig.set_heard(SENTENCES)
    code, io = rig.run("--yes", answers=["yes"], speech="ready")
    assert code == 0
    assert io.lines.count('      The computer heard: "' + SENTENCES[0] + '" The same words.') == 1
    rows = [i for i, l in enumerate(io.lines) if "seconds)" in l]
    for position, row in enumerate(rows):
        assert io.lines[row + 1].startswith('      The computer heard: "' + SENTENCES[position]), io.lines[row:row + 2]
    assert "This is a hint, not a verdict." not in io.text


def test_capitals_and_punctuation_do_not_make_words_different(rig):
    rig.set_heard(["hello my name is anna", "I NEED SOME HELP PLEASE", "Thank you. That is all"])
    _code, io = rig.run("--yes", answers=["yes"], speech="ready")
    assert io.text.count("The same words.") == 3 and "Different words." not in io.text


def test_different_words_are_shown_as_heard_with_the_hint(rig):
    rig.set_heard(["Hello, my name is Hannah.", SENTENCES[1], SENTENCES[2]])
    _code, io = rig.run("--yes", answers=["yes"], speech="ready")
    assert 'The computer heard: "Hello, my name is Hannah." Different words.' in io.text and io.text.count("The same words.") == 2
    assert "This is a hint, not a verdict. The listening program can mishear names and unusual words. What you hear matters more." in io.text


def test_nothing_written_down_is_said_plainly_and_gets_the_hint(rig):
    rig.set_heard(["", "...", SENTENCES[2]])
    _code, io = rig.run("--yes", answers=["yes"], speech="ready")
    assert io.text.count("The computer could not write down any words here.") == 2 and "This is a hint, not a verdict." in io.text


def test_the_hint_is_said_once_however_many_differ(rig):
    rig.set_heard(["a", "b", "c"])
    _code, io = rig.run("--yes", answers=["yes"], speech="ready")
    assert io.text.count("This is a hint, not a verdict.") == 1 and io.text.count("Different words.") == 3


def test_what_is_heard_is_shown_before_any_sound_is_played(rig):
    rig.set_heard(SENTENCES)
    _code, io = rig.run("--yes", answers=["yes"], speech="ready")
    said = io.lines
    assert said.index("Writing down what the computer hears in them. This takes up to a minute.") < next(i for i, l in enumerate(said) if l.startswith("Playing 1 of 3"))
    assert next(i for i, l in enumerate(said) if "The computer heard" in l) < next(i for i, l in enumerate(said) if l.startswith("Playing 1 of 3"))


def test_the_steps_are_not_numbered_so_a_step_that_is_skipped_never_leaves_a_gap(rig):
    _code, io = rig.run("--yes", answers=["yes"], speech="ready")
    assert "Getting the voice ready." in io.lines and "Making the sounds. This takes a few seconds." in io.lines and "Step 1" not in io.text


def test_a_silent_sound_gets_no_row_of_what_was_heard(tmp_path):
    rig = FlowRig(tmp_path, mode="first_silent")
    rig.set_heard(["I need some help, please.", "Thank you, that is all."])
    _code, io = rig.run("--yes", answers=["yes"], speech="ready")
    assert io.text.count("The computer heard") == 2 and "1. Hello, my name is Anna.: this one came out silent." in io.text
    row = next(i for i, l in enumerate(io.lines) if "1. Hello, my name is Anna.: this one came out silent." in l)
    assert "The computer heard" not in io.lines[row + 1]


@pytest.mark.parametrize("mode", ["hear_fail", "hear_no_engine", "hear_crash", "hear_nothing"])
def test_a_failure_of_this_step_is_said_in_three_parts_and_the_sounds_are_still_played(rig, mode):
    rig.set_hear_mode(mode)
    code, io = rig.run("--yes", answers=["yes"], speech="ready")
    assert code == 0 and [n for n, _a, _t in rig.system.played] == ["ffplay"] * 3
    assert "The computer could not write down what it heard." in io.text and "The sound files were kept as they are." in io.text and "You can still play them." in io.text
    assert "The computer heard" not in io.text and "This is a hint" not in io.text and "boom" not in io.text


def test_a_stop_while_it_writes_down_what_it_hears_goes_on_to_the_sounds(rig, monkeypatch):
    def interrupted(*_a, **_k):
        raise KeyboardInterrupt()
    monkeypatch.setattr(listen, "hear", interrupted)
    code, io = rig.run("--yes", answers=["yes"], speech="ready")
    assert code == 0 and "Stopped writing down what the computer hears. The sound files were kept as they are, and can still be played." in io.text
    assert [n for n, _a, _t in rig.system.played] == ["ffplay"] * 3


def test_with_no_model_the_run_is_exactly_what_it_was_before(rig):
    code, io = rig.run("--yes", answers=["yes"])
    assert code == 0 and not rig.heard_ran() and "The computer heard" not in io.text and "Writing down" not in io.text


def test_nothing_the_voice_said_or_the_computer_heard_is_ever_written_to_a_log_line_or_file_name(rig):
    rig.set_heard(["secret words one", "secret words two", "secret words three"])
    _code, io = rig.run("--yes", answers=["yes"], speech="ready")
    folder = rig.folder_of(FOLDER)
    for name in os.listdir(folder):
        assert "secret" not in name
    assert "secret words one" in io.text                                    # shown to the person, on the screen
    assert "secret" not in Path(folder, "hear-job.json").read_text()


# ---------------------------------------------------------------- the voice file command passes the lookup on

def test_the_voice_file_command_hands_listen_the_listening_model_lookup_it_was_given(rig):
    from vs_startvoice_helpers import Terminal
    from voice_studio.core import text, voicefile_flow as vff
    rig.set_heard(SENTENCES)
    io = Terminal(["yes"])
    code = vff.run_voicefile(["listen", "--yes"], rig.home, None, text.load_catalog("en"), io, training=rig.training_env, now=NOW, system=rig.system, tools_dir=str(TOOLS),
                             studio=rig.studio_env, speech=rig.speech_ready())
    assert code == 0 and rig.heard_ran() and io.text.count("The same words.") == 3


def test_by_default_it_looks_where_the_recordings_commands_look_and_finds_nothing_in_a_new_home(rig, monkeypatch, tmp_path):
    from vs_startvoice_helpers import Terminal
    from voice_studio.core import text, voicefile_flow as vff
    from voice_studio.core.registry import load_registry
    for name in ("HF_HUB_CACHE", "HUGGINGFACE_HUB_CACHE", "XDG_CACHE_HOME"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("HF_HOME", str(tmp_path / "no-hf-home"))
    io = Terminal(["no"])
    code = vff.run_voicefile(["listen"], rig.home, load_registry(), text.load_catalog("en"), io, training=rig.training_env, now=NOW, system=rig.system, tools_dir=str(TOOLS),
                             studio=rig.studio_env)
    assert code == 2 and "has no model here yet" in io.text and not rig.heard_ran() and rig.made() == []


def test_by_default_the_lookup_it_uses_is_the_one_the_recordings_commands_use(rig, monkeypatch):
    from vs_startvoice_helpers import Terminal
    from voice_studio.core import envfind, text, voicefile_flow as vff
    rig.set_heard(SENTENCES)
    rig.speech_dir.mkdir()
    asked = []
    monkeypatch.setattr(envfind, "speech_model", lambda home, registry: asked.append((home, registry)) or (str(rig.speech_dir), "ready"))
    io = Terminal(["yes"])
    code = vff.run_voicefile(["listen", "--yes"], rig.home, "the registry", text.load_catalog("en"), io, training=rig.training_env, now=NOW, system=rig.system, tools_dir=str(TOOLS),
                             studio=rig.studio_env)
    assert code == 0 and asked == [(rig.home, "the registry")] and io.text.count("The same words.") == 3
