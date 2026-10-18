# SPDX-License-Identifier: GPL-3.0-or-later
"""Hearing a finished voice on this computer (plan task VS-5.4): which voice, whether it is the very file in the zip, the pronunciation data, the plan, and the speaking run itself
against a real child process with a stand-in for the engine."""
import json
import os
import stat
from pathlib import Path

import pytest

from vs_listen_helpers import DATA_FILES, VOICE_FOLDER, ListenRig
from vs_rounds_helpers import NOW
from vs_voicefile_helpers import TOOLS
from voice_studio.core import jobs, listen, phonemes
from voice_studio.core.diskbudget import DEFAULT_TABLE, Level, floors_for

SENTENCES = ("One sentence.", "Another sentence.", "A third sentence.")
STAMP = jobs.utc_stamp(NOW)                                 # 2026-10-11T12:00:00Z


@pytest.fixture(autouse=True)
def no_inherited_path(monkeypatch):
    monkeypatch.delenv("PYTHONPATH", raising=False)           # the speaking program must be given its path, not find it by luck in ours


@pytest.fixture
def rig(tmp_path):
    return ListenRig(tmp_path)


def plan(rig, name=None, free=None, sentences=SENTENCES):
    return listen.plan_listen(rig.paths, name, sentences, rig.training, rig.system, STAMP, free)


def refused(rig, code, **kw):
    with pytest.raises(listen.ListenError) as caught:
        plan(rig, **kw)
    assert caught.value.code == code, caught.value
    return caught.value


# ---------------------------------------------------------------- which voice

def test_no_voice_file_made_yet_is_a_plain_refusal(tmp_path):
    refused(ListenRig(tmp_path, make=False), "no_voice")


def test_the_newest_voice_file_is_found_by_the_time_in_its_name_not_by_alphabetical_order(rig):
    rig.make_voice("voice-check-round-004-20261011-100000")
    rig.make_voice("voice-check-round-003-20261012-090000")          # round 3, made later: alphabetically before round 4, but newer
    assert plan(rig).voice.name == "voice-check-round-003-20261012-090000"


def test_a_named_voice_file_is_used_and_an_unknown_or_unsafe_name_is_refused(rig):
    rig.make_voice("voice-check-round-002-20261011-140000")
    assert plan(rig, name=VOICE_FOLDER).voice.name == VOICE_FOLDER
    for bad in ("nope", "../" + VOICE_FOLDER, "a/b", "", " ", VOICE_FOLDER + "/", "x" * 80):
        refused(rig, "folder_unknown", name=bad)


def test_a_folder_that_lost_its_model_or_settings_file_is_not_ready(rig):
    Path(rig.paths.exports, VOICE_FOLDER, "my_voice.onnx").unlink()
    assert "my_voice.onnx" in refused(rig, "voice_not_ready").detail


def test_a_model_that_is_a_link_is_not_followed(rig, tmp_path):
    model = Path(rig.paths.exports, VOICE_FOLDER, "my_voice.onnx")
    elsewhere = tmp_path / "elsewhere.onnx"
    elsewhere.write_bytes(model.read_bytes())
    model.unlink()
    model.symlink_to(elsewhere)
    refused(rig, "voice_not_ready")


# ---------------------------------------------------------------- is it the voice the phone will get

def test_a_voice_the_phone_would_refuse_is_not_played(tmp_path):
    rig = ListenRig(tmp_path, make=False)
    rig.make_voice(VOICE_FOLDER, patched=False)
    assert "not_patched" in refused(rig, "voice_not_ready").detail.split(",")


def test_a_folder_whose_model_is_not_the_one_in_its_zip_is_refused(rig):
    model = Path(rig.paths.exports, VOICE_FOLDER, "my_voice.onnx")
    data = bytearray(model.read_bytes())
    data[100] ^= 0xFF                                                  # one byte in the weights
    model.write_bytes(bytes(data))
    refused(rig, "differs_from_zip")


def test_a_folder_whose_settings_file_is_not_the_one_in_its_zip_is_refused(rig):
    config = Path(rig.paths.exports, VOICE_FOLDER, "my_voice.onnx.json")
    config.write_text(config.read_text().replace('"quality": "medium"', '"quality": "high"'))
    refused(rig, "differs_from_zip")


def test_a_zip_that_cannot_be_read_means_it_is_not_known_to_be_the_same(rig):
    Path(rig.paths.exports, VOICE_FOLDER, VOICE_FOLDER + ".zip").write_bytes(b"not a zip")
    refused(rig, "differs_from_zip")


def test_the_same_files_in_the_zip_are_recognised(rig):
    assert listen.same_as_zip(plan(rig).voice)


# ---------------------------------------------------------------- the list of sounds

def test_a_settings_file_the_phone_could_not_use_is_a_tokens_error_not_a_crash(rig):
    # a whole new voice file (so the zip matches), whose map has an entry the phone could not sort by
    rig.make_voice("voice-check-round-009-20261013-100000", symbols={"a": []})
    with pytest.raises(phonemes.TokensError) as caught:
        plan(rig, name="voice-check-round-009-20261013-100000")
    assert caught.value.code == "bad_entry"


# ---------------------------------------------------------------- the pronunciation data

def test_the_data_is_found_in_the_training_programs_own_copy(rig):
    assert plan(rig).data_dir.endswith("/venv/lib/python3.12/site-packages/piper/espeak-ng-data")


def test_the_newest_python_folder_that_has_whole_data_is_used(rig):
    rig.write_data(version="python3.10")
    rig.write_data(version="python3.13")
    assert "/python3.13/" in plan(rig).data_dir


def test_a_python_folder_with_incomplete_data_is_passed_over_for_one_that_is_whole(tmp_path):
    rig = ListenRig(tmp_path, data=False)
    rig.write_data(version="python3.13", files=("phontab",))            # newer but incomplete
    rig.write_data(version="python3.12")
    assert "/python3.12/" in plan(rig).data_dir


@pytest.mark.parametrize("missing", DATA_FILES)
def test_data_missing_any_one_required_file_is_not_used(tmp_path, missing):
    rig = ListenRig(tmp_path, data=False)
    rig.write_data(files=tuple(f for f in DATA_FILES if f != missing))
    assert refused(rig, "no_pronunciation").code == "no_pronunciation"


def test_no_training_programs_folder_at_all_is_the_same_plain_refusal(tmp_path):
    refused(ListenRig(tmp_path, data=False), "no_pronunciation")


def test_a_voice_for_another_language_needs_that_languages_dictionary(tmp_path):
    rig = ListenRig(tmp_path, language="de", make=False, data=False)
    rig.make_voice(VOICE_FOLDER, language="de")
    rig.write_data(files=("phontab", "phondata", "phonindex", "intonations"), language="en-us")        # English dictionary only
    refused(rig, "no_pronunciation")
    rig.write_data(language="de", files=("phontab", "phondata", "phonindex", "intonations"))
    assert plan(rig).english is False and plan(rig).language == "de"


def test_the_language_is_read_from_the_settings_file_and_nothing_odd_is_believed():
    assert listen.language_of('{"espeak": {"voice": "en-us"}}') == "en-us"
    for text in ("", "{", "[]", '{"espeak": 5}', '{"espeak": {"voice": 5}}', '{"espeak": {"voice": "en us"}}', '{"espeak": {"voice": "../x"}}', '{"espeak": {"voice": ""}}', '{"espeak": {}}'):
        assert listen.language_of(text) == "", text


def test_english_voices_are_told_from_the_rest_by_their_language_name(tmp_path):
    for language, english in (("en-us", True), ("en-gb", True), ("EN-US", True), ("de", False), ("cmn", False), ("es", False), ("el", False), ("eu", False)):
        rig = ListenRig(tmp_path / language.replace("-", "_"), language=language)
        assert plan(rig).english is english, language


# ---------------------------------------------------------------- the plan

def test_a_plan_names_where_everything_goes_and_writes_nothing(rig):
    before = sorted(str(p) for p in rig.tmp.rglob("*"))
    made = plan(rig)
    assert made.folder == "%s/listening/%s/heard-20261011-120000" % (rig.paths.root, VOICE_FOLDER)
    assert made.sentences == SENTENCES and made.skipped_symbols == 1 and made.room is Level.ENOUGH and made.language == "en-us"
    assert sorted(str(p) for p in rig.tmp.rglob("*")) == before
    assert not os.path.exists(rig.paths.listening)


def test_the_room_check_has_its_edges_at_the_floors(rig):
    floors = floors_for(DEFAULT_TABLE, holds_recordings=True)
    need = listen.NEED_BYTES
    refused(rig, "no_room", free=need + floors.stop - 1)
    assert plan(rig, free=need + floors.stop).room is Level.TIGHT
    assert plan(rig, free=need + floors.low - 1).room is Level.TIGHT
    assert plan(rig, free=need + floors.low).room is Level.ENOUGH
    assert plan(rig, free=None).room is Level.ENOUGH                   # a drive that cannot be read is not judged on a guess


def test_the_folder_name_needs_a_whole_time_stamp_and_a_safe_voice_name(rig):
    from voice_studio.core import commands
    for stamp in ("", "2026-10-11", "x"):
        with pytest.raises(commands.CommandError):
            listen.listening_folder(rig.paths, VOICE_FOLDER, stamp)
    with pytest.raises(commands.CommandError):
        listen.listening_folder(rig.paths, "../x", STAMP)


# ---------------------------------------------------------------- the run

def run(rig, **kw):
    return listen.listen(plan(rig, **kw), rig.studio, rig.system, str(TOOLS))


def test_the_run_makes_a_new_private_folder_with_the_list_of_sounds_the_job_and_one_sound_file_per_sentence(rig):
    heard = run(rig)
    folder = Path(heard.folder)
    assert sorted(os.listdir(folder)) == ["clip-1.wav", "clip-2.wav", "clip-3.wav", "job.json", "tokens.txt"]
    assert [c.number for c in heard.clips] == [1, 2, 3] and [c.text for c in heard.clips] == list(SENTENCES) and all(c.seconds > 0 and not c.silent for c in heard.clips)
    assert stat.S_IMODE(os.stat(folder).st_mode) == 0o700
    for name in os.listdir(folder):
        assert stat.S_IMODE(os.stat(folder / name).st_mode) & 0o077 == 0, name


def test_the_list_of_sounds_the_speaking_program_was_given_is_exactly_the_phones(rig):
    run(rig)
    config = Path(rig.paths.exports, VOICE_FOLDER, "my_voice.onnx.json").read_text()
    seen = rig.seen()
    assert seen["tokens"] == phonemes.tokens_text(config).text and seen["tokens"] == "_ 0\n^ 1\n$ 2\n  3\na 4\nb 5\ne 6\n"
    assert seen["data_dir_exists"] is True


def test_the_speaking_program_is_run_as_a_module_with_the_tools_folder_on_its_path_in_the_new_folder(rig):
    heard = run(rig)
    seen = rig.seen()
    assert seen["args"][:2] == ["-m", "voice_studio.listen_runner"] and seen["args"][2] == heard.folder + "/job.json"
    assert seen["pythonpath"] == str(TOOLS) and os.path.realpath(seen["cwd"]) == os.path.realpath(heard.folder)
    assert seen["model"] == str(Path(rig.paths.exports, VOICE_FOLDER, "my_voice.onnx"))


def test_the_job_file_holds_the_sentences_and_the_places_and_nothing_about_the_person(rig):
    heard = run(rig)
    job = json.loads(Path(heard.folder, "job.json").read_text())
    assert sorted(job) == ["data_dir", "model", "out_dir", "sentences", "tokens"] and job["sentences"] == list(SENTENCES)


def test_nothing_that_was_there_is_changed_only_a_new_folder_appears(rig):
    voice = Path(rig.paths.exports)
    before = {str(p): p.read_bytes() for p in voice.rglob("*") if p.is_file()}
    run(rig)
    assert {str(p): p.read_bytes() for p in voice.rglob("*") if p.is_file()} == before


def test_a_run_stages_are_announced_in_order(rig):
    told = []
    listen.listen(plan(rig), rig.studio, rig.system, str(TOOLS), told.append)
    assert told == ["sounds", "speaking"]


def test_a_folder_that_is_already_there_is_never_used(rig):
    made = plan(rig)
    os.makedirs(made.folder)
    with pytest.raises(listen.ListenError) as caught:
        listen.listen(made, rig.studio, rig.system, str(TOOLS))
    assert caught.value.code == "exists" and os.listdir(made.folder) == []


@pytest.mark.parametrize("mode, code", [("no_engine", "no_engine"), ("load_failed", "runner_failed"), ("crash", "runner_failed"), ("nothing", "no_clips"), ("short", "no_clips")])
def test_each_way_the_run_can_fail_is_named_and_the_folder_is_left_as_it_is(rig, mode, code):
    rig.set_mode(mode)
    with pytest.raises(listen.ListenError) as caught:
        run(rig)
    assert caught.value.code == code and caught.value.folder and os.path.isdir(caught.value.folder)


def test_a_crash_shows_the_end_of_what_the_program_said_as_the_technical_detail(rig):
    rig.set_mode("crash")
    with pytest.raises(listen.ListenError) as caught:
        run(rig)
    assert "size: 2" in caught.value.detail


def test_a_load_failure_says_what_kind_and_never_a_sentence(rig):
    rig.set_mode("load_failed")
    with pytest.raises(listen.ListenError) as caught:
        run(rig, sentences=("ZEBRA-CANARY-SENTENCE", "b", "c"))
    assert caught.value.detail == "load_failed ValueError" and "ZEBRA" not in str(caught.value)


def test_a_studio_program_that_cannot_be_started_is_a_plain_failure(rig):
    os.unlink(rig.studio.python)
    with pytest.raises(listen.ListenError) as caught:
        run(rig)
    assert caught.value.code == "runner_failed" and "could not be started" in caught.value.detail


def test_a_clip_that_came_out_silent_is_reported_not_hidden(rig):
    rig.set_mode("silent")
    heard = run(rig)
    assert all(c.silent for c in heard.clips) and len(heard.clips) == 3


def test_a_sound_file_that_is_really_a_link_is_not_trusted(rig, monkeypatch):
    real = listen._events

    def tamper(text):
        events = real(text)
        for e in events:
            if e.get("event") == "clip" and e["n"] == 1:
                path = Path(plan_folder[0], "clip-1.wav")
                target = path.with_name("elsewhere.wav")
                path.rename(target)
                path.symlink_to(target)
        return events
    made = plan(rig)
    plan_folder = [made.folder]
    monkeypatch.setattr(listen, "_events", tamper)
    with pytest.raises(listen.ListenError) as caught:
        listen.listen(made, rig.studio, rig.system, str(TOOLS))
    assert caught.value.code == "runner_failed"


def test_every_error_code_the_module_can_raise_is_listed():
    assert set(listen.ERROR_CODES) == {"no_voice", "folder_unknown", "voice_not_ready", "differs_from_zip", "no_pronunciation", "no_room", "exists", "no_engine", "runner_failed", "no_clips", "hear_failed"}


# ---------------------------------------------------------------- more edges

def test_a_folder_whose_name_is_not_one_the_tool_gives_is_never_used_even_when_it_looks_newest(rig):
    rig.make_voice("my voice-20271011-130000")                          # a space: not a name this tool makes
    assert plan(rig).voice.name == VOICE_FOLDER
    refused(rig, "folder_unknown", name="my voice-20271011-130000")


def test_only_such_folders_means_there_is_no_voice_to_listen_to(tmp_path):
    rig = ListenRig(tmp_path, make=False)
    rig.make_voice("my voice")
    refused(rig, "no_voice")


def tamper_events(monkeypatch, change):
    real = listen._events
    monkeypatch.setattr(listen, "_events", lambda text: change(real(text)))


def test_a_sound_file_the_program_names_must_be_the_numbered_clip_not_any_file_in_the_folder(rig, monkeypatch):
    def change(events):
        for e in events:
            if e.get("event") == "clip" and e["n"] == 1:
                e["file"] = "tokens.txt"
        return events
    tamper_events(monkeypatch, change)
    with pytest.raises(listen.ListenError) as caught:
        run(rig)
    assert caught.value.code == "runner_failed"


def test_a_clip_line_that_does_not_say_it_is_not_silent_is_treated_as_silent(rig, monkeypatch):
    def change(events):
        for e in events:
            e.pop("silent", None)
        return events
    tamper_events(monkeypatch, change)
    assert all(c.silent for c in run(rig).clips)


def test_the_same_clip_reported_twice_is_not_three_clips(rig, monkeypatch):
    def change(events):
        first = next(e for e in events if e.get("event") == "clip")
        return [e for e in events if e.get("event") != "clip"] + [first, dict(first), dict(first)]
    tamper_events(monkeypatch, change)
    with pytest.raises(listen.ListenError) as caught:
        run(rig)
    assert caught.value.code == "no_clips"


def test_the_listening_folders_above_the_new_one_are_private_too(rig):
    made = run(rig)
    for folder in (rig.paths.listening, os.path.dirname(made.folder), made.folder):
        assert stat.S_IMODE(os.stat(folder).st_mode) & 0o077 == 0, folder


# ---------------------------------------------------------------- where the sound files are kept (decision D43)

@pytest.mark.parametrize("source, number", [("round-003", 3), ("round-12", 12), ("round-000001", 1), ("voice-check-round-003-20261011-130000", 3), ("a-round-7-20261011-130000", 7),
                                            ("round-3x", 0), ("round--3", 0), ("round-1234567", 0), ("my-round-3", 0), ("voice-round-003-2026-130000", 0), ("round-003-20261011-130000x", 0),
                                            ("", 0), ("something-else", 0)])
def test_the_round_a_listening_belongs_to_is_told_from_its_source_folder_name(source, number):
    assert listen.round_of_source(source) == number


def test_the_sound_files_go_in_the_projects_own_listening_folder_grouped_by_what_they_were_made_from(rig):
    made = run(rig)
    assert made.folder == "%s/listening/%s/heard-20261011-120000" % (rig.paths.root, VOICE_FOLDER)
    assert os.path.isdir(rig.paths.listening) and not os.path.exists(rig.paths.default_scratch + "/listening")


def test_listening_again_adds_a_second_folder_beside_the_first_under_the_same_source(rig):
    first = run(rig).folder
    later = listen.plan_listen(rig.paths, None, SENTENCES, rig.training, rig.system, "2026-10-12T08:30:00Z", 10**12)
    second = listen.listen(later, rig.studio, rig.system, str(TOOLS)).folder
    assert os.path.dirname(first) == os.path.dirname(second) and first != second
    assert sorted(os.listdir(os.path.dirname(first))) == ["heard-20261011-120000", "heard-20261012-083000"]
    assert os.path.exists(first + "/clip-1.wav")                                    # the first is untouched


def test_the_scratch_place_is_not_used_at_all(rig):
    before = sorted(str(p) for p in Path(rig.paths.default_scratch).rglob("*"))
    run(rig)
    assert sorted(str(p) for p in Path(rig.paths.default_scratch).rglob("*")) == before
