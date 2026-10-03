# SPDX-License-Identifier: GPL-3.0-or-later
"""The PC's own listening to a recording that came from ACK: what it flags, and that it leaves a clean clip alone."""
import wave

import numpy as np
import pytest

import ack_capture_reference as ref
import freeform_studio.ack_checks as ck
import freeform_studio.ack_import as imp
from ack_package_builder import ClipSpec, PackageBuilder
from conftest import needs_ffmpeg
from freeform_studio.audio import rms_envelope
from freeform_studio.build_dataset import CLIP_SAMPLES, Policy

RATE = 48000
NEW_FLAGS = {"no_speech", "clipped", "quiet", "noisy", "cut_off", "reads_differently", "phone_stumble", "phone_disagrees"}


def write_wav(path, samples):
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(np.asarray(samples, dtype="<i2").tobytes())
    return path


def clip(text="The tide came in.", lead=0.5, speech=2.0, tail=0.6, amp=8000, flags=(), phone_speech="auto"):
    return dict(text=text, lead=lead, speech=speech, tail=tail, amp=amp, flags=list(flags), phone_speech=phone_speech)


def make_env(tmp_path, clips, noise_floor=-62.3, gap=0.4):
    """A joined recording, the notes ACK would have written for it, and one piece per clip, as the segmenter makes them."""
    parts, notes_clips, segments = [], [], []
    t = 0.0
    for i, c in enumerate(clips):
        if i:
            parts.append({"seconds": gap, "amp": 0})
            t += gap
        total = c["lead"] + c["speech"] + c["tail"]
        parts += [{"seconds": c["lead"], "amp": 0}, {"seconds": c["speech"], "amp": c["amp"]}, {"seconds": c["tail"], "amp": 0}]
        voiced = c["amp"] > 0 and c["speech"] > 0
        speech = {"start_s": c["lead"], "end_s": c["lead"] + c["speech"]} if voiced else None
        if c["phone_speech"] != "auto":
            speech = c["phone_speech"]
        notes_clips.append({"index": i + 1, "start_s": round(t, 3), "end_s": round(t + total, 3), "text": c["text"], "speech": speech,
                            "flags": c["flags"]})
        a = max(t, t + c["lead"] - 0.12)
        b = min(t + total, t + c["lead"] + c["speech"] + 0.2)
        segments.append({"id": f"s{i + 1:03d}", "start": round(a, 3), "end": round(b, 3), "text": c["text"], "words": [], "status": "pending",
                         "tags": [], "note": "", "flags": [], "auto": {}})
        t += total
    wav = write_wav(tmp_path / "joined.wav", ref.square_samples(parts, RATE))
    db, hop = rms_envelope(wav)
    return {"wav": wav, "db": db, "hop": hop, "segments": segments, "clip_of": list(range(len(clips))),
            "notes": {"mode": "script", "noise_floor_dbfs": noise_floor, "clips": notes_clips}}


def run(env):
    report = ck.check_script(env["segments"], env["clip_of"], env["notes"], env["db"], env["hop"], env["wav"])
    return [set(s["flags"]) & NEW_FLAGS for s in env["segments"]], report


# ------------------------------------------------------------------ a clean clip is left alone
def test_a_clean_clip_gets_no_flags_and_its_measurements_are_recorded(tmp_path):
    env = make_env(tmp_path, [clip(), clip("We walked along the shore.")])
    flags, report = run(env)
    assert flags == [set(), set()]
    p = report["pieces"]["s001"]
    assert p["peak_dbfs"] == pytest.approx(-12.2, abs=0.1) and p["clipped_samples"] == 0 and p["clip"] == 1
    assert p["snr_db"] > 40 and p["voiced_fraction"] > 0.7 and report["noise_floor_dbfs"] == -62.3


# ------------------------------------------------------------------ each problem is found, in the right clip only
def test_each_problem_is_flagged_in_its_own_clip_and_the_others_stay_clean(tmp_path):
    env = make_env(tmp_path, [
        clip("Clean one here."),
        clip("Loud one here.", amp=32767),
        clip("Soft one here.", amp=300),
        clip("Silent one here.", amp=0),
        clip("Early one here.", lead=0.0),
        clip("Late one here.", tail=0.0),
    ])
    flags, _ = run(env)
    assert flags[0] == set()
    assert "clipped" in flags[1] and "quiet" not in flags[1]
    assert "quiet" in flags[2] and "clipped" not in flags[2]
    assert "no_speech" in flags[3] and "quiet" not in flags[3] and "noisy" not in flags[3]        # nothing to judge the level of
    assert "cut_off" in flags[4] and "cut_off" in flags[5]
    assert all("cut_off" not in f for f in flags[:4])


def test_a_noisy_room_flags_every_clip_in_it(tmp_path):
    env = make_env(tmp_path, [clip(), clip("We walked along the shore.")], noise_floor=-30.0)
    flags, report = run(env)
    assert all("noisy" in f for f in flags) and report["pieces"]["s001"]["snr_db"] < ck.MIN_SNR_DB


def test_without_a_phone_measurement_the_rooms_level_comes_from_the_recording_itself(tmp_path):
    env = make_env(tmp_path, [clip()], noise_floor=None)
    assert ck.room_level(env["db"], env["notes"]) == -60.0                                  # too little live audio to estimate: a safe default
    noisy = np.concatenate([ref.square_samples([{"seconds": 1.0, "amp": 1500}, {"seconds": 1.0, "amp": 9000}] * 4, RATE)])
    db, _hop = rms_envelope(write_wav(tmp_path / "n.wav", noisy))
    assert ck.room_level(db, {}) == pytest.approx(20 * np.log10(1500 / 32768), abs=0.5)


def test_the_phones_own_level_note_wins_over_a_guess(tmp_path):
    env = make_env(tmp_path, [clip()], noise_floor=-48.5)
    assert ck.room_level(env["db"], env["notes"]) == -48.5


def test_what_counts_as_speech_follows_the_rooms_measurement_not_the_loudest_clip(tmp_path):
    env = make_env(tmp_path, [clip(amp=32767), clip("Soft one here.", amp=300)])
    n = dict(env["notes"])
    assert ck.speech_threshold_for(env["db"], n) == pytest.approx(-52.3, abs=0.01)                    # -62.3 + 10, from the phone's measurement
    assert ck.speech_threshold_for(env["db"], dict(n, threshold_dbfs=-48.0)) == -48.0                   # the phone's own figure when it gave one
    assert ck.speech_threshold_for(env["db"], dict(n, noise_floor_dbfs=-90.0, threshold_dbfs=None)) == -55.0
    adaptive = ck.speech_threshold_for(env["db"], dict(n, noise_floor_dbfs=None))
    assert adaptive > -45.0                                                                            # a loud clip pulls the adaptive figure up


# ------------------------------------------------------------------ edges of a clip, and clips split into several pieces
def test_only_the_first_and_last_piece_of_a_clip_can_be_cut_off(tmp_path):
    env = make_env(tmp_path, [clip(lead=0.0, speech=4.0, tail=0.0)])
    s = env["segments"][0]
    win = env["notes"]["clips"][0]
    a, b, c = dict(s, id="s001", start=0.0, end=1.5), dict(s, id="s002", start=1.5, end=2.9), dict(s, id="s003", start=2.9, end=4.0)
    for piece in (a, b, c):
        piece["flags"], piece["tags"] = [], []
    env["segments"], env["clip_of"] = [a, b, c], [0, 0, 0]
    flags, _ = run(env)
    assert "cut_off" in flags[0] and "cut_off" not in flags[1] and "cut_off" in flags[2]
    assert win["start_s"] == 0.0


# ------------------------------------------------------------------ the card against what was heard
@pytest.mark.parametrize("card,heard,expected", [
    ("The tide came in.", "The tide came in.", False),
    ("The tide came in.", "the Tide came in", False),                                  # case and punctuation do not matter
    ("The tide came in today.", "The tide came in toady.", False),                      # one word of five
    ("The tide came in.", "completely unrelated words here", True),
    ("It cost 20 dollars", "it cost twenty dollars", False),                            # a number may be spoken as words
    ("20", "twenty", False),                                                            # nothing but numbers on the card: nothing to compare
    ("The tide came in.", "", False),                                                   # nothing heard is reported by other flags
    ("Don't go.", "don’t go", False),                                                   # curly apostrophe
])
def test_reads_differently(card, heard, expected):
    assert ck.reads_differently(card, heard) is expected


def test_a_clip_that_was_misread_is_flagged_using_everything_heard_in_it(tmp_path):
    env = make_env(tmp_path, [clip("The tide came in slowly."), clip("We walked along the shore.")])
    env["segments"][0]["text"] = "an entirely different sentence appears"
    env["segments"][1]["text"] = "We walked along the shore."
    flags, _ = run(env)
    assert "reads_differently" in flags[0] and "reads_differently" not in flags[1]


# ------------------------------------------------------------------ what the person marked on the phone
def test_marks_made_on_the_phone_become_a_warning_and_review_tags(tmp_path):
    env = make_env(tmp_path, [clip(flags=["stumble", "noise", "cough", "bogus"]), clip()])
    flags, _ = run(env)
    first, second = env["segments"]
    assert "phone_stumble" in flags[0] and first["tags"] == ["cough", "noise"] and "phone_stumble" not in flags[1] and second["tags"] == []


def test_the_phone_and_this_computer_disagreeing_about_speech_is_flagged(tmp_path):
    env = make_env(tmp_path, [clip(amp=0, phone_speech={"start_s": 0.5, "end_s": 2.5}), clip(phone_speech=None), clip()])
    flags, _ = run(env)
    assert "phone_disagrees" in flags[0] and "no_speech" in flags[0]
    assert "phone_disagrees" in flags[1]
    assert "phone_disagrees" not in flags[2]


def test_flags_already_on_a_piece_are_kept_and_not_repeated(tmp_path):
    env = make_env(tmp_path, [clip(amp=32767)])
    env["segments"][0]["flags"] = ["has_digits", "clipped"]
    run(env)
    assert env["segments"][0]["flags"] == ["has_digits", "clipped"]


# ------------------------------------------------------------------ free speech
def test_free_speech_pieces_get_the_level_checks_only(tmp_path):
    parts = [{"seconds": 0.5, "amp": 0}, {"seconds": 3.0, "amp": 32767}, {"seconds": 0.5, "amp": 0},
             {"seconds": 3.0, "amp": 300}, {"seconds": 0.5, "amp": 0}, {"seconds": 2.0, "amp": 0}, {"seconds": 0.5, "amp": 8000}]
    wav = write_wav(tmp_path / "free.wav", ref.square_samples(parts, RATE))
    db, hop = rms_envelope(wav)
    segs = [{"id": "s001", "start": 0.4, "end": 3.7, "text": "a", "flags": []}, {"id": "s002", "start": 4.0, "end": 7.2, "text": "b", "flags": []},
            {"id": "s003", "start": 7.5, "end": 9.5, "text": "", "flags": []}]
    report = ck.check_free(segs, {"mode": "free", "noise_floor_dbfs": -62.0}, db, hop, wav)
    got = [set(s["flags"]) for s in segs]
    assert "clipped" in got[0] and "quiet" in got[1] and "no_speech" in got[2]
    assert all("cut_off" not in g and "reads_differently" not in g and "phone_disagrees" not in g for g in got)
    assert set(report["pieces"]) == {"s001", "s002", "s003"} and report["mode"] == "free"


# ------------------------------------------------------------------ measuring audio in blocks
def test_peaks_and_clipping_are_counted_exactly_across_block_boundaries(tmp_path):
    parts = [{"seconds": 29.8, "amp": 0}, {"seconds": 0.6, "amp": 32767}, {"seconds": 34.6, "amp": 0}]       # loud part crosses the 30 s block edge
    wav = write_wav(tmp_path / "long.wav", ref.square_samples(parts, RATE))
    peaks, clipped = ck.sample_checks(wav, [(29.0, 31.0), (29.9, 30.1), (31.0, 33.0), (0.0, 29.0)])
    assert clipped == [28800, 9600, 0, 0] and peaks[0] == 32767 and peaks[1] == 32767 and peaks[2] == 0


# ------------------------------------------------------------------ agreeing with the rest of the program
def test_thresholds_match_the_dataset_builders_own_tests():
    assert ck.CLIP_SAMPLES == CLIP_SAMPLES
    assert ck.CLIP_LEVEL == int(np.ceil(0.999 * 32768))
    p = Policy()
    assert ck.QUIET_PEAK_DB == p.peak_db - p.max_gain_db                                  # softer than this cannot be brought up to full level
    assert ck.REGION_MIN_SILENCE_S == ref.C["REGION_MIN_SILENCE_S"] and ck.REGION_MIN_LEN_S == ref.C["REGION_MIN_LEN_S"]
    assert (ck.THRESH_OFFSET_DB, ck.THRESH_MIN_DB, ck.THRESH_MAX_DB) == (ref.C["THRESH_OFFSET_DB"], ref.C["THRESH_MIN_DB"], ref.C["THRESH_MAX_DB"])


def test_every_new_flag_has_words_for_the_review_page():
    from pathlib import Path
    text = (Path(__file__).resolve().parents[1] / "static" / "js" / "flags.js").read_text(encoding="utf-8")
    for f in NEW_FLAGS:
        assert text.count(f"{f}:") >= 2, f"{f} needs both a short label and a help sentence in flags.js"


# ------------------------------------------------------------------ through the real pipeline
@needs_ffmpeg
def test_checks_run_when_a_recording_is_imported_and_the_measurements_are_saved(tmp_path, out_dir):
    import asyncio
    import json
    from freeform_studio.ack_package import open_package
    from freeform_studio.app import create_app
    from freeform_studio.config import Config
    b = PackageBuilder()
    b.script_session([ClipSpec("The tide came in slowly.", speech=2.5), ClipSpec("Loud one here today.", speech=2.5, amp=32767),
                      ClipSpec("We walked along the shore.", speech=2.5, flags=["stumble", "noise"])])
    path = b.write(tmp_path / "p.zip")
    created = imp.apply_import(imp.make_plan(open_package(path), out_dir, "en-US"))
    tid = created[0].take_id

    async def main():
        app = create_app(Config(output_dir=out_dir, asr_engine="fake", asr_idle_unload_s=0))
        async with app.test_app():
            c = app.test_client()
            for _ in range(300):
                doc = await (await c.get(f"/api/takes/{tid}")).get_json()
                if doc["status"] in ("ready", "error"):
                    break
                await asyncio.sleep(0.1)
            assert doc["status"] == "ready", doc.get("error")
            return await (await c.get(f"/api/takes/{tid}/edit")).get_json()
    edit = asyncio.run(main())
    segs = edit["segments"]
    assert len(segs) == 3
    assert "clipped" in segs[1]["flags"] and "clipped" not in segs[0]["flags"]
    assert "phone_stumble" in segs[2]["flags"] and segs[2]["tags"] == ["noise"]
    saved = json.loads((Config(output_dir=out_dir).takes_dir / tid / "ack_checks.json").read_text(encoding="utf-8"))
    assert saved["mode"] == "script" and set(saved["pieces"]) == {"s001", "s002", "s003"} and saved["pieces"]["s002"]["clipped_samples"] > 5
