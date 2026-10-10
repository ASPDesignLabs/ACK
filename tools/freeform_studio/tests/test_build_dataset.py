# SPDX-License-Identifier: GPL-3.0-or-later
import csv
import json
import subprocess
import sys
import wave
from pathlib import Path

import numpy as np
import pytest

from conftest import make_live_webm, make_wav, needs_ffmpeg
from freeform_studio import build_dataset as bd

pytestmark = needs_ffmpeg
TOOLS = Path(__file__).resolve().parents[2]


def seg(i, a, b, text="hello there.", status="pending", flags=()):
    return {"id": f"s{i:03d}", "start": a, "end": b, "text": text, "words": [], "status": status, "tags": [],
            "note": "", "flags": list(flags), "auto": None}


def write_take(out_dir, take_id, segs, seconds=30.0, amp=0.5, status="ready"):
    d = out_dir / "_freeform" / "en-US" / "takes" / take_id
    d.mkdir(parents=True)
    make_wav(d / "audio.wav", seconds, [(0.0, seconds)], amp=amp)
    (d / "take.json").write_text(json.dumps({"id": take_id, "status": status, "duration": seconds}))
    (d / "edit.json").write_text(json.dumps({"schema": 1, "rev": 1, "segments": segs}))
    return d


def run(out_dir, dest, *extra):
    return bd.main(["--output", str(out_dir), "--out", str(dest), *extra])


def read_wav(path):
    with wave.open(str(path), "rb") as w:
        x = np.frombuffer(w.readframes(w.getnframes()), dtype="<i2").astype(np.float32) / 32768
        return x, w.getframerate(), w.getnchannels(), w.getsampwidth()


def rows(dest):
    with open(dest / "metadata.csv", encoding="utf-8") as f:
        return list(csv.reader(f, delimiter="|"))


def test_clean_policy_picks_and_explains(out_dir):
    write_take(out_dir, "t20260930-000001-aaaa", [
        seg(1, 0.0, 3.0),                                                   # plain: in
        seg(2, 3.0, 6.0, flags=["low_confidence"]),                         # shaky: out by default
        seg(3, 6.0, 9.0, flags=["has_digits"]),                             # numbers: allowed by default
        seg(4, 9.0, 12.0, status="approved", flags=["low_confidence"]),     # a person approved it: in despite flags
        seg(5, 12.0, 15.0, status="dropped"),
        seg(6, 15.0, 15.5),                                                 # too short
        seg(7, 16.0, 29.0),                                                 # too long (13 s)
        seg(8, 16.0, 19.0, text="a | b"),
        seg(9, 19.0, 22.0, text="   "),
        seg(10, 22.0, 25.0, flags=["bracket_tag"]),
    ])
    inc, exc, stats = bd.scan(out_dir / "_freeform" / "en-US" / "takes", bd.Policy())
    assert [c.seg_id for c in inc] == ["s001", "s003", "s004"]
    reasons = {e["seg"]: e["reason"] for e in exc}
    assert reasons["s002"] == "flagged: low_confidence" and reasons["s005"] == "you dropped it"
    assert reasons["s006"].startswith("too short") and reasons["s007"].startswith("too long")
    assert "break the training file" in reasons["s008"] and reasons["s009"] == "no text"
    assert reasons["s010"] == "flagged: bracket_tag"
    assert stats["takes"] == 1 and stats["segments"] == 10


def test_policies_allow_approved_only_and_everything(out_dir):
    write_take(out_dir, "t20260930-000001-aaaa", [seg(1, 0, 3), seg(2, 3, 6, flags=["low_confidence"]),
                                                  seg(3, 6, 9, status="approved")])
    td = out_dir / "_freeform" / "en-US" / "takes"
    ids = lambda p: [c.seg_id for c in bd.scan(td, p)[0]]
    assert ids(bd.Policy(allow={"has_digits", "low_confidence"})) == ["s001", "s002", "s003"]
    assert ids(bd.Policy(include="approved")) == ["s003"]
    assert ids(bd.Policy(include="all")) == ["s001", "s002", "s003"]


def test_unfinished_takes_are_skipped_and_reported(out_dir):
    write_take(out_dir, "t20260930-000001-aaaa", [seg(1, 0, 3)])
    write_take(out_dir, "t20260930-000002-bbbb", [seg(1, 0, 3)], status="transcribing")
    inc, _exc, stats = bd.scan(out_dir / "_freeform" / "en-US" / "takes", bd.Policy())
    assert len(inc) == 1 and stats["skipped_takes"] == [("t20260930-000002-bbbb", "transcribing")]


def test_built_dataset_is_what_the_trainer_expects(out_dir, tmp_path, capsys):
    write_take(out_dir, "t20260930-000001-aaaa", [seg(1, 0.5, 3.5, text="First piece."), seg(2, 4.0, 8.0, text="Second, longer piece.")],
               amp=0.2)
    dest = tmp_path / "ds"
    assert run(out_dir, dest) == 0
    out = capsys.readouterr().out
    assert "INCLUDED: 2 pieces" in out and "--data.cache_dir" in out and "cache-ds" in out and "--ckpt_path" in out
    # the settings that made training fast on an 8 GB card (a small dataset has tiny epochs, so validation must not run after each one)
    for option in ("--data.batch_size 12", "--data.num_workers 4", "--trainer.check_val_every_n_epoch 10", "--trainer.log_every_n_steps 1"):
        assert option in out, option
    assert "CONTINUE a voice you already trained" in out and "last.ckpt" in out
    raw = (dest / "metadata.csv").read_bytes()
    assert b"\r" not in raw and raw.endswith(b"\n")  # plain LF line endings
    r = rows(dest)
    assert r == [["ff_t20260930-000001-aaaa_s001.wav", "First piece."], ["ff_t20260930-000001-aaaa_s002.wav", "Second, longer piece."]]
    for (name, _text), want in zip(r, (3.0, 4.0)):
        x, rate, ch, width = read_wav(dest / "wav" / name)
        assert (rate, ch, width) == (22050, 1, 2)
        assert abs(len(x) / rate - want) < 0.03
        peak_db = 20 * np.log10(np.abs(x).max())
        assert abs(peak_db - (-3.0)) < 0.6  # quietly recorded (amp 0.2) and brought up to the target level
        assert abs(x[0]) < 0.01 and abs(x[-1]) < 0.01  # faded at the edges: no clicks
    manifest = json.loads((dest / "manifest.json").read_text())
    assert [c["text"] for c in manifest["clips"]] == ["First piece.", "Second, longer piece."]
    assert manifest["clips"][0]["gain_db"] > 6 and manifest["policy"]["include"] == "clean"
    assert bd.validate(dest) == []


def test_no_normalize_keeps_original_loudness(out_dir, tmp_path):
    write_take(out_dir, "t20260930-000001-aaaa", [seg(1, 0, 3)], amp=0.2)
    dest = tmp_path / "ds"
    assert run(out_dir, dest, "--no-normalize") == 0
    x, *_ = read_wav(dest / "wav" / rows(dest)[0][0])
    assert abs(20 * np.log10(np.abs(x).max()) - 20 * np.log10(0.2)) < 0.6


def test_too_quiet_and_clipped_audio_is_left_out_with_a_reason(out_dir, tmp_path):
    write_take(out_dir, "t20260930-000001-aaaa", [seg(1, 0, 3)], amp=0.0005)
    write_take(out_dir, "t20260930-000002-bbbb", [seg(1, 0, 3)], amp=1.0)
    write_take(out_dir, "t20260930-000003-cccc", [seg(1, 0, 3)], amp=0.3)
    dest = tmp_path / "ds"
    assert run(out_dir, dest) == 0
    assert [r[0] for r in rows(dest)] == ["ff_t20260930-000003-cccc_s001.wav"]
    why = (dest / "excluded.txt").read_text()
    assert "too quiet to use" in why and "clips" in why


def test_dry_run_writes_nothing_and_existing_folders_are_never_touched(out_dir, tmp_path, capsys):
    write_take(out_dir, "t20260930-000001-aaaa", [seg(1, 0, 3)])
    dest = tmp_path / "ds"
    assert run(out_dir, dest, "--dry-run") == 0
    assert not dest.exists() and "DRY RUN" in capsys.readouterr().out
    dest.mkdir()
    (dest / "mine.txt").write_text("keep me")
    assert run(out_dir, dest) == 2
    assert [p.name for p in dest.iterdir()] == ["mine.txt"] and "never overwrites" in capsys.readouterr().err


def test_takes_folder_is_never_modified(out_dir, tmp_path):
    d = write_take(out_dir, "t20260930-000001-aaaa", [seg(1, 0, 3)])
    before = {p.name: p.read_bytes() for p in d.iterdir()}
    assert run(out_dir, tmp_path / "ds") == 0
    assert {p.name: p.read_bytes() for p in d.iterdir()} == before


def test_same_input_gives_identical_metadata_so_row_numbers_are_stable(out_dir, tmp_path):
    write_take(out_dir, "t20260930-000002-bbbb", [seg(1, 0, 3, text="b one."), seg(2, 4, 7, text="b two.")])
    write_take(out_dir, "t20260930-000001-aaaa", [seg(1, 0, 3, text="a one.")])
    assert run(out_dir, tmp_path / "x") == 0 and run(out_dir, tmp_path / "y") == 0
    assert (tmp_path / "x" / "metadata.csv").read_bytes() == (tmp_path / "y" / "metadata.csv").read_bytes()
    assert [r[1] for r in rows(tmp_path / "x")] == ["a one.", "b one.", "b two."]  # oldest take first


def test_existing_dataset_can_be_merged_in_without_name_clashes(out_dir, tmp_path, capsys):
    write_take(out_dir, "t20260930-000001-aaaa", [seg(1, 0, 3, text="New one.")])
    old = tmp_path / "old"
    (old / "wav").mkdir(parents=True)
    good = old / "wav" / "ff_t20260930-000001-aaaa_s001.wav"  # deliberately the same name as the new clip
    make_wav(good, 2.0, [(0, 2.0)], rate=22050)
    make_wav(old / "wav" / "other.wav", 2.0, [(0, 2.0)], rate=22050)
    make_wav(old / "wav" / "wrongrate.wav", 2.0, [(0, 2.0)], rate=44100)
    (old / "metadata.csv").write_text("ff_t20260930-000001-aaaa_s001.wav|Old one.\nother.wav|Other.\nwrongrate.wav|Bad.\n")
    dest = tmp_path / "ds"
    assert run(out_dir, dest, "--also", str(old)) == 0
    r = rows(dest)
    assert len(r) == 3 and len({row[0] for row in r}) == 3  # nothing overwritten
    assert [row[1] for row in r] == ["New one.", "Old one.", "Other."]
    out = capsys.readouterr().out
    assert "MERGED IN from other datasets: 2 rows" in out and "wrongrate.wav is not 22050 Hz mono" in out
    assert bd.validate(dest) == []


def test_report_points_at_what_was_left_out(out_dir, tmp_path, capsys):
    write_take(out_dir, "t20260930-000001-aaaa", [seg(1, 0, 3), seg(2, 3, 6, text="Shaky words.", flags=["low_confidence"]),
                                                  seg(3, 6, 9, status="dropped")])
    assert run(out_dir, tmp_path / "ds") == 0
    out = capsys.readouterr().out
    assert "LEFT OUT: 2 pieces" in out and "low_confidence 1" in out and "--allow low_confidence" in out
    assert "[flagged: low_confidence] Shaky words." in out and "under about 10 minutes" in out
    assert "Shaky words." in (tmp_path / "ds" / "excluded.txt").read_text()


def test_nothing_qualifying_writes_no_dataset_and_says_why(out_dir, tmp_path, capsys):
    write_take(out_dir, "t20260930-000001-aaaa", [seg(1, 0, 3, flags=["low_confidence"])])
    assert run(out_dir, tmp_path / "ds") == 1
    assert "Nothing qualified" in capsys.readouterr().out and not (tmp_path / "ds" / "metadata.csv").exists()


def test_missing_takes_folder_is_a_plain_error(tmp_path, capsys):
    assert bd.main(["--output", str(tmp_path), "--out", str(tmp_path / "ds")]) == 2
    assert "no takes folder" in capsys.readouterr().err


def test_end_to_end_from_a_real_take_made_by_the_server(tmp_path, out_dir):
    import asyncio
    from freeform_studio.app import create_app
    from freeform_studio.config import Config
    wav = make_wav(tmp_path / "in.wav", 9.0, [(0.5, 3.5), (5.0, 8.0)], rate=44100)
    data = make_live_webm(wav, tmp_path / "in.webm").read_bytes()

    async def record():
        app = create_app(Config(output_dir=out_dir, asr_engine="fake", asr_idle_unload_s=0))
        async with app.test_app():
            c = app.test_client()
            tid = (await (await c.post("/api/takes", json={"reference_text": "so here is a thing I wanted to say out loud today"})).get_json())["id"]
            await c.put(f"/api/takes/{tid}/chunks/0", data=data)
            await c.post(f"/api/takes/{tid}/finish")
            for _ in range(300):
                if (await (await c.get(f"/api/takes/{tid}")).get_json())["status"] == "ready":
                    return tid
                await asyncio.sleep(0.1)
            raise AssertionError("take never became ready")

    tid = asyncio.run(record())
    dest = tmp_path / "ds"
    assert run(out_dir, dest, "--include", "all", "--min-seconds", "0.5") == 0
    r = rows(dest)
    assert r and all(row[0].startswith(f"ff_{tid}_") for row in r)
    assert bd.validate(dest) == []


def test_cli_entry_point_runs(tmp_path):
    r = subprocess.run([sys.executable, "-m", "freeform_studio.build_dataset", "--help"], cwd=TOOLS, capture_output=True, text=True)
    assert r.returncode == 0 and "--include" in r.stdout and "--dry-run" in r.stdout


def test_one_stray_full_scale_sample_is_not_clipping_but_a_run_of_them_is(out_dir, tmp_path):
    d1 = write_take(out_dir, "t20260930-000001-aaaa", [seg(1, 0, 3)], amp=0.3)
    with wave.open(str(d1 / "audio.wav"), "rb") as w:
        x = np.frombuffer(w.readframes(w.getnframes()), dtype="<i2").copy()
    x[24000] = 32767  # a single full-scale sample in the middle of the piece
    with wave.open(str(d1 / "audio.wav"), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(48000); w.writeframes(x.tobytes())
    write_take(out_dir, "t20260930-000002-bbbb", [seg(1, 0, 3)], amp=1.0)  # sustained clipping
    dest = tmp_path / "ds"
    assert run(out_dir, dest) == 0
    assert [r[0] for r in rows(dest)] == ["ff_t20260930-000001-aaaa_s001.wav"]
    assert "repeatedly" in (dest / "excluded.txt").read_text()


def test_dry_run_applies_the_same_audio_checks_as_the_real_build(out_dir, tmp_path, capsys):
    write_take(out_dir, "t20260930-000001-aaaa", [seg(1, 0, 3)], amp=0.3)
    write_take(out_dir, "t20260930-000002-bbbb", [seg(1, 0, 3)], amp=0.0005)  # too quiet
    assert run(out_dir, tmp_path / "ds", "--dry-run") == 0
    out = capsys.readouterr().out
    assert "INCLUDED: 1 piece," in out and "too quiet to use" in out and not (tmp_path / "ds").exists()


def test_a_build_that_qualifies_nothing_leaves_no_empty_folders(out_dir, tmp_path):
    write_take(out_dir, "t20260930-000001-aaaa", [seg(1, 0, 3)], amp=0.0005)
    dest = tmp_path / "ds"
    assert run(out_dir, dest) == 1
    assert not dest.exists()  # so the same name can be used again after fixing the cause


def test_allow_none_holds_back_pieces_with_numbers_and_is_otherwise_parsed_plainly():
    assert bd.parse_allow(None) == {"has_digits"} and bd.parse_allow("") == {"has_digits"}     # the default
    assert bd.parse_allow("none") == set() and bd.parse_allow(" None ") == set()
    assert bd.parse_allow("low_confidence, has_digits,,") == {"low_confidence", "has_digits"}
    base = {"start": 0.0, "end": 3.0, "text": "She paid 20 dollars.", "flags": ["has_digits"], "tags": [], "status": "pending"}
    assert bd.why_excluded(base, bd.Policy(allow=bd.parse_allow(None))) is None
    assert "has_digits" in bd.why_excluded(base, bd.Policy(allow=bd.parse_allow("none")))
    assert bd.why_excluded({**base, "status": "approved"}, bd.Policy(allow=bd.parse_allow("none"))) is None   # you approved it


def test_pieces_already_in_a_merged_dataset_made_from_the_export_are_not_counted_twice(out_dir, tmp_path, capsys):
    take = "t20260930-000001-aaaa"
    write_take(out_dir, take, [seg(1, 0, 3, text="Already exported."), seg(2, 3, 6, text="Not exported yet.")])
    old = tmp_path / "split"
    (old / "wav").mkdir(parents=True)
    make_wav(old / "wav" / f"freeform_{take}_s001.wav", 2.0, [(0, 2.0)], rate=22050)     # what split_long_takes.py makes from the export
    make_wav(old / "wav" / "01_prompt_3.wav", 2.0, [(0, 2.0)], rate=22050)               # an ordinary prompted recording
    (old / "metadata.csv").write_text(f"freeform_{take}_s001.wav|Already exported.\n01_prompt_3.wav|Prompted.\n")
    dest = tmp_path / "ds"
    assert run(out_dir, dest, "--also", str(old)) == 0
    r = rows(dest)
    assert [row[1] for row in r] == ["Not exported yet.", "Already exported.", "Prompted."]    # the exported piece appears once
    assert (dest / "excluded.txt").read_text().count("already in split") == 1
    assert "already in split" in capsys.readouterr().out
    assert bd.validate(dest) == []


# ---------------------------------------------------------------- --json: the same facts as one object, for a program

def json_run(capsys, out_dir, dest, *extra):
    code = run(out_dir, dest, "--json", *extra)
    out = capsys.readouterr().out.strip().splitlines()
    assert len(out) == 1, "exactly one line of JSON and nothing else"
    return code, json.loads(out[0])


def standard_take(out_dir):
    write_take(out_dir, "t20260930-000001-aaaa", [seg(1, 0.0, 3.0), seg(2, 3.0, 6.0, flags=["low_confidence"]), seg(3, 6.0, 9.0, flags=["has_digits", "x"]),
                                                  seg(4, 9.0, 12.0, status="dropped"), seg(5, 12.0, 12.4)])


def test_json_for_a_build_gives_the_counts_the_report_prints_and_writes_the_same_files(out_dir, tmp_path, capsys):
    standard_take(out_dir)
    dest = tmp_path / "ds"
    code, result = json_run(capsys, out_dir, dest)
    assert code == 0 and result["result"] == "built" and result["out"] == str(dest)
    assert result["takes"] == 1 and result["pieces_considered"] == 5 and result["skipped_takes"] == []
    assert result["included"]["pieces"] == 1 and abs(result["included"]["minutes"] - 0.05) < 0.001 and result["included"]["shortest"] == result["included"]["longest"]
    assert result["left_out"]["pieces"] == 4
    assert result["left_out"]["by_reason"] == {"flagged": 2, "you dropped it": 1, "too short": 1}
    assert result["left_out"]["by_flag"] == {"low_confidence": 1, "x": 1}
    assert result["policy"]["include"] == "clean" and result["policy"]["allow"] == ["has_digits"] and result["problems"] == [] and result["merged"] == 0
    assert (dest / "metadata.csv").exists() and len(rows(dest)) == 1


def test_json_for_a_dry_run_writes_nothing(out_dir, tmp_path, capsys):
    standard_take(out_dir)
    dest = tmp_path / "ds"
    code, result = json_run(capsys, out_dir, dest, "--dry-run")
    assert code == 0 and result["result"] == "dry_run" and result["included"]["pieces"] == 1 and not dest.exists()


def test_json_says_so_when_nothing_qualified_and_creates_nothing(out_dir, tmp_path, capsys):
    write_take(out_dir, "t20260930-000001-aaaa", [seg(1, 0.0, 0.4)])
    dest = tmp_path / "ds"
    code, result = json_run(capsys, out_dir, dest)
    assert code == 1 and result["result"] == "nothing_qualified" and result["included"]["pieces"] == 0 and result["left_out"]["by_reason"] == {"too short": 1}
    assert not dest.exists()


def test_json_refuses_an_existing_dataset_and_a_missing_takes_folder(out_dir, tmp_path, capsys):
    standard_take(out_dir)
    dest = tmp_path / "ds"
    dest.mkdir()
    (dest / "keep.txt").write_text("mine")
    code, result = json_run(capsys, out_dir, dest)
    assert code == 2 and result == {"result": "refused_existing", "out": str(dest)} and (dest / "keep.txt").read_text() == "mine"
    other = tmp_path / "empty-output"
    other.mkdir()
    code = bd.main(["--output", str(other), "--out", str(tmp_path / "ds2"), "--json"])
    printed = json.loads(capsys.readouterr().out)
    assert code == 2 and printed["result"] == "no_takes_folder" and printed["out"].endswith("takes")


def test_json_lists_the_takes_that_were_skipped_because_they_are_not_finished(out_dir, tmp_path, capsys):
    standard_take(out_dir)
    write_take(out_dir, "t20260930-000002-bbbb", [seg(1, 0.0, 3.0)], status="transcribing")
    code, result = json_run(capsys, out_dir, tmp_path / "ds")
    assert code == 0 and result["skipped_takes"] == [["t20260930-000002-bbbb", "transcribing"]] and result["takes"] == 2


def test_without_json_the_report_is_exactly_what_it_was(out_dir, tmp_path, capsys):
    standard_take(out_dir)
    assert run(out_dir, tmp_path / "ds") == 0
    text = capsys.readouterr().out
    assert "INCLUDED: 1 piece" in text and "LEFT OUT: 4 pieces" in text and "Train on it" in text and not text.lstrip().startswith("{")


def test_the_summary_counts_a_flag_once_per_piece_that_carries_it(out_dir):
    excluded = [{"reason": "flagged: low_confidence, has_digits"}, {"reason": "flagged: low_confidence"}, {"reason": "too short (0.4s)"}]
    by_reason, by_flag = bd._reasons(excluded)
    assert by_reason == {"flagged": 2, "too short": 1} and by_flag == {"low_confidence": 2, "has_digits": 1}
