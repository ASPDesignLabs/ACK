# SPDX-License-Identifier: GPL-3.0-or-later
"""The export folder works with the existing training routine (split_long_takes.py) unchanged apart from its marker."""
import subprocess
import sys
from pathlib import Path

import pytest

pytest.importorskip("pydub")

from conftest import make_wav, needs_ffmpeg
from freeform_studio import build_dataset as bd
from freeform_studio import export as ex
from test_build_dataset import rows, seg, write_take

pytestmark = needs_ffmpeg
SPLITTER = Path(__file__).resolve().parents[2] / "split_long_takes.py"
TAKE = "t20260930-000001-aaaa"


def split(input_dir, dest, *extra):
    r = subprocess.run([sys.executable, str(SPLITTER), "--input-dir", str(input_dir), "--output-dir", str(dest), *extra],
                       capture_output=True, text=True, timeout=120)
    return r.returncode, r.stderr + r.stdout


def long_group(root, name, marker):
    g = root / name
    g.mkdir(parents=True)
    make_wav(g / "0.wav", 13.0, [(0.0, 13.0)], rate=22050)       # one unbroken burst: silence detection would find one segment
    (g / "0.txt").write_text("First sentence here. Second sentence follows.\n")   # ...but the text has two sentences
    if marker:
        (g / ex.MARKER).write_text("finished clips\n")
    return g


def test_a_marked_folder_is_copied_through_even_when_a_low_min_duration_would_split_it(tmp_path):
    root = tmp_path / "en-US"
    long_group(root, "plain", marker=False)
    long_group(root, "freeform", marker=True)
    code, log = split(root, tmp_path / "ds", "--min-duration", "2")
    assert code == 0, log
    assert "already a finished clip" in log
    assert "MISMATCH" in log                                       # the control: unmarked, the same audio is sent to needs_review
    names = [row[0] for row in rows(tmp_path / "ds")]
    assert names == ["freeform_0.wav"]
    assert (tmp_path / "ds" / "needs_review" / "plain_0.wav").exists()


def test_exported_clips_flow_through_the_splitter_into_a_valid_dataset_and_are_not_counted_twice(out_dir, tmp_path):
    write_take(out_dir, TAKE, [seg(1, 0, 3, "Exported one.", status="approved"), seg(2, 3, 6, "Exported two.", status="approved"),
                               seg(3, 6, 9, "Still pending.")], seconds=12.0)
    ex.apply(out_dir, "en-US")
    ds = tmp_path / "split"
    code, log = split(out_dir / "en-US", ds)                         # the guide's own command: no special options
    assert code == 0, log
    assert sorted(r[1] for r in rows(ds)) == ["Exported one.", "Exported two."]
    assert sorted(r[0] for r in rows(ds)) == [f"freeform_{TAKE}_s001.wav", f"freeform_{TAKE}_s002.wav"]
    assert bd.validate(ds) == []                                       # 22050 Hz mono 16-bit, every row present, no empty text
    assert not list((ds / "needs_review").iterdir())
    out = tmp_path / "combined"
    assert bd.main(["--output", str(out_dir), "--out", str(out), "--also", str(ds), "--include", "all"]) == 0
    texts = [r[1] for r in rows(out)]
    assert texts.count("Exported one.") == texts.count("Exported two.") == 1     # from the export, not again from the recording
    assert "Still pending." in texts
    assert "already in split" in (out / "excluded.txt").read_text()
