# SPDX-License-Identifier: GPL-3.0-or-later
"""Bringing a folder of voice recordings into Freeform Studio (files_import.py): the sentences come from the person's choice of kind and never from a guess, the folder is only ever read, a .zip is
unpacked only into this program's own folder and only the names it should, everything added is recognised by its content so a second run or a renamed copy adds nothing, a file that cannot be
read is left out without stopping the rest, and what is added goes through the very steps a recording from ACK goes through."""
import hashlib
import json
import os
import stat
import struct
import wave
import zipfile
from pathlib import Path

import pytest

import freeform_studio.files_import as fi
import freeform_studio.process as proc
from conftest import make_wav, needs_ffmpeg
from freeform_studio.ack_segments import usable_notes
from freeform_studio.config import Config
from freeform_studio.storage import TakeStore

TEXTS = ["The tide came in slowly.", "It rained all day long.", "Gulls circled over the pier.", "We walked along the shore.", "The lamp was left on."]


def tree(root):
    found = {}
    for base, dirs, files in os.walk(root):
        for name in files:
            path = os.path.join(base, name)
            found[os.path.relpath(path, root)] = hashlib.sha256(open(path, "rb").read()).hexdigest()
    return found


def clip(path, seconds=2.2, burst=(0.3, 1.9), f0=200.0):
    path.parent.mkdir(parents=True, exist_ok=True)
    make_wav(path, seconds, [burst], f0=f0)
    return path


def folder_of_pairs(tmp_path, count=3, name="voice"):
    root = tmp_path / name
    for i in range(count):
        clip(root / ("%03d.wav" % (i + 1)), f0=200.0 + 17 * i)
        (root / ("%03d.txt" % (i + 1))).write_text(TEXTS[i % len(TEXTS)] + "\n", encoding="utf-8")
    return root


def takes_of(out_dir):
    store = TakeStore(Config(output_dir=out_dir).takes_dir)
    return store, store.ids()


# ---------------------------------------------------------------- reading text and tables

def test_a_sentence_is_one_line_with_single_spaces_and_no_control_characters_and_nothing_else_changes():
    assert fi.clean_sentence("  The  tide\tcame\r\nin. \x00\x07") == "The tide came in."
    assert fi.clean_sentence("Café — “quoted” | pipe") == "Café — “quoted” | pipe"
    assert fi.clean_sentence("\x85line break") == "line break" and fi.clean_sentence(" \n ") == ""


def test_small_text_is_read_as_utf8_with_or_without_a_byte_order_mark_and_anything_else_is_refused(tmp_path):
    a, b, c, d = (tmp_path / n for n in "abcd")
    a.write_bytes("Café".encode("utf-8"))
    b.write_bytes(b"\xef\xbb\xbfhello")
    c.write_bytes(b"\xff\xfe\x00bad")
    d.write_bytes(b"x" * 100)
    assert fi.read_small_text(a, 50) == "Café" and fi.read_small_text(b, 50) == "hello"
    assert fi.read_small_text(c, 50) is None, "not UTF-8"
    assert fi.read_small_text(d, 99) is None and fi.read_small_text(d, 100) == "x" * 100, "exactly at the limit is fine, one over is not"
    assert fi.read_small_text(tmp_path / "missing", 50) is None


def test_a_pipe_table_with_three_columns_uses_the_second_as_the_sentence_and_quotes_are_just_text():
    rows = fi.parse_table('LJ001-0001|Printing, in the only sense with which we are at present concerned|Printing, in the only sense\nLJ001-0002|He said "yes" and left.|He said yes and left.\n')
    assert rows.delimiter == "|" and not rows.header and rows.bad_rows == 0
    assert rows.rows == (("LJ001-0001", "Printing, in the only sense with which we are at present concerned"), ("LJ001-0002", 'He said "yes" and left.'))


def test_a_pipe_table_is_still_a_pipe_table_when_every_sentence_has_commas_in_it():
    rows = fi.parse_table("001|One, two, three.\n002|Well, that was long, wasn't it?\n003|Yes, yes.\n")
    assert rows.delimiter == "|" and rows.rows == (("001", "One, two, three."), ("002", "Well, that was long, wasn't it?"), ("003", "Yes, yes."))


def test_a_pipe_table_sentence_that_starts_with_a_quote_keeps_its_quotes():
    rows = fi.parse_table('001|"Come here," she said.|x\n002|He said "no".|x\n')
    assert rows.rows == (("001", '"Come here," she said.'), ("002", 'He said "no".'))


def test_a_comma_table_may_quote_a_sentence_that_has_commas_and_its_header_row_is_not_a_row():
    rows = fi.parse_table('file,text\n001.wav,"Well, that was long, wasn\'t it?"\n002.wav,Short one.\n')
    assert rows.delimiter == "," and rows.header and rows.rows == (("001.wav", "Well, that was long, wasn't it?"), ("002.wav", "Short one."))


def test_a_tab_table_and_the_other_header_names_are_read_and_the_pipe_is_preferred_when_two_are_there():
    assert fi.parse_table("filename\ttranscript\na.wav\tOne.\nb.wav\tTwo.").rows == (("a.wav", "One."), ("b.wav", "Two."))
    assert fi.parse_table("id|sentence\na|Hello, world.").delimiter == "|"
    assert fi.parse_table("a.wav|Hello, world.\nb.wav|Hi.").delimiter == "|"


def test_a_header_needs_both_cells_to_look_like_one_so_a_first_row_that_happens_to_start_with_a_file_word_is_a_row():
    rows = fi.parse_table("name|Hello there.\nother|Bye.")
    assert not rows.header and len(rows.rows) == 2


def test_rows_without_a_sentence_or_a_name_are_counted_and_left_out_and_blank_lines_are_ignored():
    rows = fi.parse_table("a|One.\n\n|No name.\nb\nc|Three.\nd|Four.\ne|Five.\nf|Six.\ng|Seven.\n")
    assert [r[0] for r in rows.rows] == ["a", "c", "d", "e", "f", "g"] and rows.bad_rows == 2


def test_a_stray_line_without_the_delimiter_does_not_make_the_table_unreadable_but_a_text_that_is_no_table_is():
    many = "\n".join("f%d|Sentence %d." % (i, i) for i in range(10)) + "\njust a line\n"
    assert fi.parse_table(many).bad_rows == 1 and len(fi.parse_table(many).rows) == 10
    assert fi.parse_table("This is a story.\nIt has no table in it.\n") is None and fi.parse_table("") is None and fi.parse_table("\n\n") is None


def test_names_are_put_in_the_order_a_person_expects_with_numbers_as_numbers():
    names = ["clip10.wav", "clip2.wav", "Clip1.wav", "a/clip3.wav", "clip20.wav"]
    assert sorted(names, key=fi.natural_key) == ["a/clip3.wav", "Clip1.wav", "clip2.wav", "clip10.wav", "clip20.wav"]


# ---------------------------------------------------------------- batches

def item(text="", seconds=3.0, rel="a.wav"):
    return fi.Item(rel, Path(rel), 100, text=text, seconds=seconds, sha256=rel)


def test_files_with_a_sentence_are_joined_up_to_a_limit_and_a_file_with_none_is_its_own_recording(monkeypatch):
    items = [item("One.", rel="1.wav"), item("Two.", rel="2.wav"), item("", rel="3.wav"), item("Four.", rel="4.wav")]
    groups = fi._batches(items)
    assert [[i.rel for i in g] for g in groups] == [["3.wav"], ["1.wav", "2.wav", "4.wav"]] or [[i.rel for i in g] for g in groups] == [["1.wav", "2.wav", "4.wav"], ["3.wav"]]
    monkeypatch.setattr(fi, "BATCH_MAX_CLIPS", 2)
    texty = [g for g in fi._batches(items) if g[0].text]
    assert [[i.rel for i in g] for g in texty] == [["1.wav", "2.wav"], ["4.wav"]]
    monkeypatch.setattr(fi, "BATCH_MAX_CLIPS", 150)
    monkeypatch.setattr(fi, "BATCH_MAX_S", 7.0)
    assert [[i.rel for i in g] for g in fi._batches([item("A.", rel="1.wav"), item("B.", rel="2.wav"), item("C.", rel="3.wav")])] == [["1.wav", "2.wav"], ["3.wav"]], "3 + 0.4 each: two fit in 7 s, the third does not"


def test_the_batch_limits_are_exact_at_the_boundary(monkeypatch):
    monkeypatch.setattr(fi, "BATCH_MAX_CLIPS", 3)
    three = [item("T.", rel="%d.wav" % i) for i in range(3)]
    assert len(fi._batches(three)) == 1 and len(fi._batches(three + [item("T.", rel="9.wav")])) == 2
    monkeypatch.setattr(fi, "BATCH_MAX_CLIPS", 150)
    monkeypatch.setattr(fi, "BATCH_MAX_S", 2 * (3.0 + fi.GAP_S))
    two = [item("T.", rel="1.wav"), item("T.", rel="2.wav")]
    assert len(fi._batches(two)) == 1, "exactly at the limit still fits"
    monkeypatch.setattr(fi, "BATCH_MAX_S", 2 * (3.0 + fi.GAP_S) - 0.01)
    assert len(fi._batches(two)) == 2


# ---------------------------------------------------------------- looking at a folder

def test_looking_at_a_folder_of_pairs_matches_each_sentence_to_its_file_and_writes_nothing(tmp_path, out_dir):
    root = folder_of_pairs(tmp_path, 3)
    before, outside = tree(root), tree(out_dir)
    plan = fi.make_plan(root, "pairs", out_dir)
    assert [i.rel for i in plan.items] == ["001.wav", "002.wav", "003.wav"] and [i.text for i in plan.items] == TEXTS[:3]
    assert {i.text_from for i in plan.items} == {"sidecar"} and [i.state for i in plan.items] == ["new"] * 3 and plan.with_text == 3 and plan.problems == []
    assert all(i.seconds == pytest.approx(2.2, abs=0.01) and len(i.sha256) == 64 for i in plan.items)
    assert tree(root) == before and tree(out_dir) == outside, "looking changes nothing"
    assert plan.need_mb > 0 and plan.enough_room


def test_a_file_with_no_sentence_beside_it_comes_without_one_and_the_audio_kind_ignores_sentences_that_are_there(tmp_path, out_dir):
    root = folder_of_pairs(tmp_path, 2)
    clip(root / "003.wav")
    plan = fi.make_plan(root, "pairs", out_dir)
    assert [i.text for i in plan.items] == [TEXTS[0], TEXTS[1], ""] and plan.with_text == 2
    audio_only = fi.make_plan(root, "audio", out_dir)
    assert [i.text for i in audio_only.items] == ["", "", ""] and audio_only.with_text == 0


def test_a_sentence_file_that_is_not_utf8_or_is_too_long_is_reported_and_never_used(tmp_path, out_dir):
    root = folder_of_pairs(tmp_path, 3)
    (root / "001.txt").write_bytes(b"\xff\xfe broken")
    (root / "002.txt").write_text("x " * 400, encoding="utf-8")
    plan = fi.make_plan(root, "pairs", out_dir)
    by = {i.rel: i for i in plan.items}
    assert by["001.wav"].state == "new" and by["001.wav"].text == "", "the file is still imported, with no sentence"
    assert by["002.wav"].state == "unusable" and by["002.wav"].reason == "text_too_long", "a sentence is never cut to fit"
    assert [(p.code, p.what) for p in plan.problems] == [("text_unreadable", "001.wav"), ("text_too_long", "002.wav")]


def test_files_that_cannot_be_used_are_named_with_the_reason_and_the_rest_are_still_offered(tmp_path, out_dir):
    root = folder_of_pairs(tmp_path, 2)
    clip(root / "short.wav", seconds=0.3, burst=(0.05, 0.2))
    (root / "empty.wav").write_bytes(b"")
    plan = fi.make_plan(root, "audio", out_dir)
    states = {i.rel: (i.state, i.reason) for i in plan.items}
    assert states["short.wav"] == ("unusable", "too_short") and states["empty.wav"] == ("unusable", "unreadable") and states["001.wav"][0] == "new"
    assert {(p.code, p.what) for p in plan.problems} == {("too_short", "short.wav"), ("unreadable", "empty.wav")}


def test_a_file_that_is_too_big_is_refused_before_it_is_read(tmp_path, out_dir, monkeypatch):
    root = folder_of_pairs(tmp_path, 1)
    monkeypatch.setattr(fi, "MAX_FILE_BYTES", 100)
    plan = fi.make_plan(root, "audio", out_dir)
    assert plan.items[0].state == "unusable" and plan.items[0].reason == "too_big" and plan.items[0].sha256 == ""


def test_links_hidden_files_and_system_files_are_left_out_and_a_link_is_said(tmp_path, out_dir):
    root = folder_of_pairs(tmp_path, 1)
    clip(root / ".hidden.wav")
    clip(root / "__MACOSX" / "x.wav")
    outside = clip(tmp_path / "outside.wav")
    os.symlink(str(outside), str(root / "linked.wav"))
    os.symlink(str(tmp_path), str(root / "linked-folder"))
    plan = fi.make_plan(root, "audio", out_dir)
    assert [i.rel for i in plan.items] == ["001.wav"] and {(p.code, p.what) for p in plan.problems} == {("link_skipped", "linked.wav"), ("link_skipped", "linked-folder")}


def test_folders_below_are_searched_to_a_depth_and_files_come_in_natural_order(tmp_path, out_dir, monkeypatch):
    root = tmp_path / "set"
    for rel in ("clip10.wav", "clip2.wav", "sub/clip1.wav", "sub/deeper/clip3.wav"):
        clip(root / rel)
    plan = fi.make_plan(root, "audio", out_dir)
    assert [i.rel for i in plan.items] == ["clip2.wav", "clip10.wav", "sub/clip1.wav", "sub/deeper/clip3.wav"]
    monkeypatch.setattr(fi, "MAX_DEPTH", 1)
    assert [i.rel for i in fi.make_plan(root, "audio", out_dir).items] == ["clip2.wav", "clip10.wav", "sub/clip1.wav"]


def test_the_same_recording_twice_in_a_folder_is_offered_once(tmp_path, out_dir):
    root = tmp_path / "set"
    clip(root / "a.wav")
    (root / "copy-of-a.wav").write_bytes((root / "a.wav").read_bytes())
    clip(root / "b.wav", f0=300.0)
    plan = fi.make_plan(root, "audio", out_dir)
    assert [(i.rel, i.state) for i in plan.items] == [("a.wav", "new"), ("b.wav", "new"), ("copy-of-a.wav", "duplicate")]


def test_a_folder_without_audio_or_with_too_many_files_or_that_is_not_a_folder_is_refused_in_a_word(tmp_path, out_dir, monkeypatch):
    empty = tmp_path / "empty"
    empty.mkdir()
    (empty / "notes.txt").write_text("hello")
    for source, code in ((empty, "no_audio"), (tmp_path / "missing", "not_a_folder")):
        with pytest.raises(fi.FilesImportProblem) as caught:
            fi.make_plan(source, "audio", out_dir)
        assert caught.value.code == code
    with pytest.raises(fi.FilesImportProblem) as caught:
        fi.make_plan(folder_of_pairs(tmp_path, 1), "nonsense", out_dir)
    assert caught.value.code == "bad_kind"
    monkeypatch.setattr(fi, "MAX_FILES", 2)
    with pytest.raises(fi.FilesImportProblem) as caught:
        fi.make_plan(folder_of_pairs(tmp_path, 3, "many"), "audio", out_dir)
    assert caught.value.code == "too_many_files"


# ---------------------------------------------------------------- one table

def folder_with_table(tmp_path, table_text, name="tabled", files=("001", "002", "003")):
    root = tmp_path / name
    for i, stem in enumerate(files):
        clip(root / "wavs" / (stem + ".wav"), f0=200.0 + 11 * i)
    (root / "metadata.csv").write_text(table_text, encoding="utf-8")
    return root


def test_a_table_row_finds_its_file_by_name_with_or_without_the_extension_and_by_path(tmp_path, out_dir):
    root = folder_with_table(tmp_path, "001|One.\n002.wav|Two.\nwavs/003.wav|Three.\n")
    plan = fi.make_plan(root, "table", out_dir)
    assert [(i.rel, i.text, i.text_from) for i in plan.items] == [("wavs/001.wav", "One.", "table"), ("wavs/002.wav", "Two.", "table"), ("wavs/003.wav", "Three.", "table")]
    assert plan.table == "metadata.csv" and plan.problems == []


def test_a_row_for_a_file_that_is_not_there_a_file_named_twice_and_a_name_in_two_folders_are_each_said(tmp_path, out_dir):
    root = folder_with_table(tmp_path, "001|One.\n001|One again.\nghost|Nobody.\n", files=("001", "002"))
    clip(root / "other" / "002.wav", f0=250.0)
    root.joinpath("metadata.csv").write_text("001|One.\n001|One again.\nghost|Nobody.\n002|Which one?\n", encoding="utf-8")
    plan = fi.make_plan(root, "table", out_dir)
    by = {i.rel: i.text for i in plan.items}
    assert by["wavs/001.wav"] == "One." and by["wavs/002.wav"] == "" and by["other/002.wav"] == ""
    assert sorted((p.code, p.what) for p in plan.problems) == [("table_row_ambiguous", "002"), ("table_row_no_audio", "ghost"), ("table_row_repeated", "001")]


def test_a_missing_or_unreadable_table_is_said_and_the_files_still_come_without_sentences(tmp_path, out_dir):
    root = folder_with_table(tmp_path, "")
    root.joinpath("metadata.csv").write_bytes(b"\xff\xfe")
    plan = fi.make_plan(root, "table", out_dir)
    assert [i.text for i in plan.items] == ["", "", ""] and [(p.code, p.what) for p in plan.problems] == [("table_unreadable", "metadata.csv")]
    os.unlink(root / "metadata.csv")
    plan = fi.make_plan(root, "table", out_dir)
    assert [(p.code, p.what) for p in plan.problems] == [("table_missing", "")]


def test_more_than_one_table_uses_the_one_nearest_the_top_and_says_so_and_a_named_table_is_used_as_named(tmp_path, out_dir):
    root = folder_with_table(tmp_path, "001|From the top.\n")
    (root / "wavs" / "metadata.csv").write_text("001|From below.\n", encoding="utf-8")
    (root / "transcripts.csv").write_text("001|From the second.\n", encoding="utf-8")
    plan = fi.make_plan(root, "table", out_dir)
    assert plan.table == "metadata.csv" and [i.text for i in plan.items][0] == "From the top." and [p.code for p in plan.problems] == ["table_many"]
    named = fi.make_plan(root, "table", out_dir, table="transcripts.csv")
    assert named.table == "transcripts.csv" and named.items[0].text == "From the second." and named.problems == []
    assert [p.code for p in fi.make_plan(root, "table", out_dir, table="nothing.csv").problems] == ["table_missing"]


def test_a_table_nearer_the_top_beats_one_that_sorts_first_by_name(tmp_path, out_dir):
    root = folder_with_table(tmp_path, "001|From the top.\n")
    (root / "a").mkdir()
    (root / "a" / "metadata.csv").write_text("001|From a folder that sorts first.\n", encoding="utf-8")
    plan = fi.make_plan(root, "table", out_dir)
    assert plan.table == "metadata.csv" and plan.items[0].text == "From the top." and [p.code for p in plan.problems] == [], "one at the top and one below are not 'many at the same level'"


def test_rows_with_no_sentence_are_counted(tmp_path, out_dir):
    names = ("001", "002", "003", "004", "005", "006", "007", "008")
    root = folder_with_table(tmp_path, "001|One.\n002\n|x\n003|Three.\n004|Four.\n005|Five.\n006|Six.\n007|Seven.\n008|Eight.\n", files=names)
    plan = fi.make_plan(root, "table", out_dir)
    assert [p.code for p in plan.problems] == ["table_bad_rows"] and plan.problems[0].detail == "2"
    assert [i.text for i in plan.items][:4] == ["One.", "", "Three.", "Four."]


# ---------------------------------------------------------------- a .zip

def zip_of(path, entries):
    with zipfile.ZipFile(path, "w") as zf:
        for name, data in entries:
            info = zipfile.ZipInfo(name)
            if isinstance(data, tuple):                                  # ("link", target)
                info.external_attr = (stat.S_IFLNK | 0o777) << 16
                data = data[1].encode()
            zf.writestr(info, data)
    return path


def wav_bytes(tmp_path, name="x.wav", f0=200.0):
    return clip(tmp_path / "_made" / name, f0=f0).read_bytes()


def test_a_zip_is_unpacked_only_into_this_programs_own_folder_and_only_the_names_it_should(tmp_path, out_dir):
    data = wav_bytes(tmp_path)
    archive = zip_of(tmp_path / "voice.zip", [("set/001.wav", data), ("set/001.txt", b"One."), ("../escape.wav", data), ("/abs.wav", data), ("set/link.wav", ("link", "/etc/passwd")),
                                              ("set/.hidden.wav", data), ("__MACOSX/set/001.wav", data), ("set/readme.exe", b"MZ"), ("set\\win.wav", data), ("set/sub/002.wav", data)])
    before = archive.read_bytes()
    absolute_before = os.stat("/abs.wav").st_mtime_ns if os.path.exists("/abs.wav") else None
    plan = fi.make_plan(archive, "pairs", out_dir)
    assert plan.unpacked and plan.source.parent == Config(output_dir=out_dir).root / "incoming" and plan.source.name.startswith("files-")
    assert sorted(i.rel for i in plan.items) == ["set/001.wav", "set/sub/002.wav", "set/win.wav"], "a backslash in a name is a folder separator, and nothing else gets through"
    names = sorted(os.path.relpath(os.path.join(b, f), plan.source) for b, _d, fs in os.walk(plan.source) for f in fs)
    assert ".complete" in names and "set/001.wav" in names and "set/001.txt" in names and "set/sub/002.wav" in names
    assert not any(f == "escape.wav" for _b, _d, fs in os.walk(tmp_path) for f in fs), "a name that climbs out is written nowhere at all, not even beside the unpacked folder"
    assert (os.stat("/abs.wav").st_mtime_ns if os.path.exists("/abs.wav") else None) == absolute_before, "an absolute name is not written at the root of the disk (and a file that was already there is not touched)"
    assert not any("link" in n or "hidden" in n or "MACOSX" in n or n.endswith(".exe") for n in names)
    assert archive.read_bytes() == before, "the .zip itself is only read"
    assert [i.text for i in plan.items if i.rel == "set/001.wav"] == ["One."]
    again = fi.make_plan(archive, "pairs", out_dir)
    assert again.source == plan.source, "an earlier complete unpacking is reused"


def test_a_zip_that_is_not_a_zip_has_no_audio_or_is_a_bomb_is_refused(tmp_path, out_dir, monkeypatch):
    plain = tmp_path / "plain.zip"
    plain.write_bytes(b"not a zip at all")
    with pytest.raises(fi.FilesImportProblem) as caught:
        fi.make_plan(plain, "audio", out_dir)
    assert caught.value.code == "not_a_folder"
    with pytest.raises(fi.FilesImportProblem) as caught:
        fi.make_plan(zip_of(tmp_path / "text.zip", [("a.txt", b"hello")]), "audio", out_dir)
    assert caught.value.code == "no_audio"
    big = zip_of(tmp_path / "big.zip", [("a.wav", wav_bytes(tmp_path))])
    monkeypatch.setattr(fi, "MAX_UNPACKED_BYTES", 1000)
    with pytest.raises(fi.FilesImportProblem) as caught:
        fi.make_plan(big, "audio", out_dir)
    assert caught.value.code == "too_big"


def test_an_entry_whose_real_size_is_more_than_its_header_says_stops_the_unpacking(tmp_path, out_dir):
    data = wav_bytes(tmp_path)
    archive = zip_of(tmp_path / "lying.zip", [("a.wav", data)])
    raw = bytearray(archive.read_bytes())
    # the uncompressed size is written twice (local header and central directory); make both smaller than the data
    for marker in (b"PK\x03\x04", b"PK\x01\x02"):
        at = raw.index(marker)
        offset = at + (22 if marker == b"PK\x03\x04" else 24)
        struct.pack_into("<I", raw, offset, 10)
    archive.write_bytes(bytes(raw))
    with pytest.raises((fi.FilesImportProblem, zipfile.BadZipFile)):
        fi.make_plan(archive, "audio", out_dir)


# ---------------------------------------------------------------- adding

@needs_ffmpeg
def test_files_with_sentences_become_one_recording_joined_with_a_gap_and_each_sentence_travels_with_its_file(tmp_path, out_dir):
    root = folder_of_pairs(tmp_path, 3)
    original = tree(root)
    plan = fi.make_plan(root, "pairs", out_dir)
    result = fi.apply_import(plan)
    assert tree(root) == original, "the folder is only ever read"
    assert len(result.created) == 1 and result.clips == 3 and result.skipped == []
    store, ids = takes_of(out_dir)
    assert ids == [result.created[0].take_id]
    take = store.get(ids[0])
    assert take["status"] == "finishing" and take["mime"] == "audio/wav" and take["client"]["source"] == "files" and take["client"]["files_kind"] == "pairs"
    assert take["reference_text"] == "\n".join(TEXTS[:3]) and take["label"] == "voice"
    notes = store.read(ids[0], "ack_clips.json")
    assert notes["mode"] == "files" and [c["text"] for c in notes["clips"]] == TEXTS[:3] and usable_notes(notes)
    clips = notes["clips"]
    assert clips[0]["start_s"] == 0.0 and clips[0]["duration_s"] == pytest.approx(2.2, abs=0.01)
    for before, after in zip(clips, clips[1:]):
        assert after["start_s"] - before["end_s"] == pytest.approx(fi.GAP_S, abs=0.002)
    assert [c["source_name"] for c in clips] == ["001.wav", "002.wav", "003.wav"] and all(len(c["source_sha256"]) == 64 and "/" not in c["source_name"] for c in clips)
    joined = store.path(ids[0], "parts", "000000.bin").read_bytes()
    assert joined[:4] == b"RIFF" and struct.unpack("<I", joined[4:8])[0] == len(joined) - 8 and struct.unpack("<I", joined[40:44])[0] == len(joined) - 44
    assert (len(joined) - 44) // 2 == round(clips[-1]["end_s"] * 48000)


@needs_ffmpeg
def test_a_file_with_no_sentence_is_its_own_recording_cut_the_usual_way_and_remembered_by_its_content(tmp_path, out_dir):
    root = folder_of_pairs(tmp_path, 1)
    clip(root / "loose.wav", f0=330.0)
    plan = fi.make_plan(root, "pairs", out_dir)
    result = fi.apply_import(plan)
    assert len(result.created) == 2
    store, ids = takes_of(out_dir)
    modes = sorted(store.read(i, "ack_clips.json")["mode"] for i in ids)
    assert modes == ["files", "free"]
    free = [i for i in ids if store.read(i, "ack_clips.json")["mode"] == "free"][0]
    take = store.get(free)
    assert take["label"] == "loose" and take["reference_text"] == "" and take["client"]["source_sha256"] == hashlib.sha256((root / "loose.wav").read_bytes()).hexdigest()
    assert usable_notes(store.read(free, "ack_clips.json"))


@needs_ffmpeg
def test_a_second_run_and_a_renamed_copy_add_nothing_and_one_new_file_adds_one(tmp_path, out_dir):
    root = folder_of_pairs(tmp_path, 2)
    fi.apply_import(fi.make_plan(root, "pairs", out_dir))
    store, ids = takes_of(out_dir)
    again = fi.make_plan(root, "pairs", out_dir)
    assert [i.state for i in again.items] == ["already", "already"] and again.to_import == []
    renamed = tmp_path / "renamed"
    renamed.mkdir()
    for src in ("001.wav", "002.wav"):
        (renamed / ("copy-" + src)).write_bytes((root / src).read_bytes())
    assert [i.state for i in fi.make_plan(renamed, "audio", out_dir).items] == ["already", "already"]
    clip(root / "004.wav", f0=410.0)
    plan = fi.make_plan(root, "audio", out_dir)
    assert [(i.rel, i.state) for i in plan.items] == [("001.wav", "already"), ("002.wav", "already"), ("004.wav", "new")]
    fi.apply_import(plan)
    assert len(takes_of(out_dir)[1]) == len(ids) + 1


@needs_ffmpeg
def test_a_file_that_cannot_be_decoded_is_left_out_and_said_and_the_rest_are_added(tmp_path, out_dir):
    root = folder_of_pairs(tmp_path, 3)
    (root / "002.wav").write_bytes(b"this is not audio at all, only text pretending")
    plan = fi.make_plan(root, "pairs", out_dir)
    result = fi.apply_import(plan)
    assert [(s.rel, s.reason) for s in result.skipped] == [("002.wav", "unreadable")] and result.clips == 2
    store, ids = takes_of(out_dir)
    notes = store.read(ids[0], "ack_clips.json")
    assert [c["source_name"] for c in notes["clips"]] == ["001.wav", "003.wav"] and notes["clips"][1]["start_s"] == pytest.approx(notes["clips"][0]["end_s"] + fi.GAP_S, abs=0.002)
    assert fi.make_plan(root, "pairs", out_dir).count("already") == 2, "the one that failed is tried again next time"


@needs_ffmpeg
def test_a_recording_that_ends_up_with_nothing_in_it_is_moved_aside_not_left_waiting(tmp_path, out_dir):
    root = tmp_path / "bad"
    root.mkdir()
    (root / "a.wav").write_bytes(b"not audio " * 50)
    result = fi.apply_import(fi.make_plan(root, "audio", out_dir))
    assert result.created == [] and [s.reason for s in result.skipped] == ["unreadable"]
    assert takes_of(out_dir)[1] == [] and any((Config(output_dir=out_dir).root / "retired" / "aborted-imports").iterdir())


@needs_ffmpeg
def test_nothing_is_written_when_there_is_not_room(tmp_path, out_dir):
    root = folder_of_pairs(tmp_path, 2)
    plan = fi.make_plan(root, "pairs", out_dir)
    plan.free_mb = 1.0
    with pytest.raises(fi.NotEnoughRoom):
        fi.apply_import(plan)
    assert takes_of(out_dir)[1] == []


@needs_ffmpeg
def test_many_files_become_several_recordings_numbered_in_their_label(tmp_path, out_dir, monkeypatch):
    monkeypatch.setattr(fi, "BATCH_MAX_CLIPS", 2)
    result = fi.apply_import(fi.make_plan(folder_of_pairs(tmp_path, 5), "pairs", out_dir))
    store, ids = takes_of(out_dir)
    assert len(result.created) == 3 and sorted(store.get(i)["label"] for i in ids) == ["voice (1 of 3)", "voice (2 of 3)", "voice (3 of 3)"]
    assert sorted(len(store.read(i, "ack_clips.json")["clips"]) for i in ids) == [1, 2, 2]


@needs_ffmpeg
def test_an_import_that_was_cut_short_is_moved_aside_and_redone_and_other_recordings_are_left_alone(tmp_path, out_dir):
    root = folder_of_pairs(tmp_path, 2)
    store = TakeStore(Config(output_dir=out_dir).takes_dir)
    mine = store.create({"status": "importing", "client": {"source": "files"}})["id"]
    other = store.create({"status": "importing", "client": {"source": "ack", "ack_session": "x"}})["id"]
    fi.apply_import(fi.make_plan(root, "pairs", out_dir))
    ids = store.ids()
    assert mine not in ids and other in ids
    assert (Config(output_dir=out_dir).root / "retired" / "aborted-imports" / mine).is_dir()


@needs_ffmpeg
def test_other_audio_formats_are_decoded_and_a_table_import_carries_its_sentences(tmp_path, out_dir):
    import subprocess
    root = folder_with_table(tmp_path, "001|One.\n002|Two.\n003|Three.\n")
    subprocess.run(["ffmpeg", "-nostdin", "-y", "-loglevel", "error", "-i", str(root / "wavs" / "002.wav"), str(root / "wavs" / "002.mp3")], check=True)
    os.unlink(root / "wavs" / "002.wav")
    plan = fi.make_plan(root, "table", out_dir)
    assert [i.rel for i in plan.items] == ["wavs/001.wav", "wavs/002.mp3", "wavs/003.wav"] and plan.items[1].seconds is not None
    result = fi.apply_import(plan)
    notes = TakeStore(Config(output_dir=out_dir).takes_dir).read(result.created[0].take_id, "ack_clips.json")
    assert [c["text"] for c in notes["clips"]] == ["One.", "Two.", "Three."] and [c["text_from"] for c in notes["clips"]] == ["table"] * 3
    assert notes["clips"][1]["duration_s"] == pytest.approx(2.2, abs=0.15)


# ---------------------------------------------------------------- through the steps a recording from ACK goes through

def process(out_dir):
    return proc.main(["--output", str(out_dir), "--asr-engine", "fake", "--json"])


@pytest.fixture(autouse=True)
def keep_the_environment(monkeypatch):
    for name in ("HF_HUB_OFFLINE", "HF_HUB_DISABLE_TELEMETRY", "DO_NOT_TRACK"):
        monkeypatch.delenv(name, raising=False)


@needs_ffmpeg
def test_imported_files_are_finished_and_each_file_is_one_piece_with_no_phone_flags(tmp_path, out_dir, capsys):
    root = folder_of_pairs(tmp_path, 3)
    clip(root / "004.wav", seconds=2.2, burst=(0.0, 2.2), f0=380.0)                      # speech from the very first sample to the very last: how a trimmed file is
    (root / "004.txt").write_text(TEXTS[3], encoding="utf-8")
    fi.apply_import(fi.make_plan(root, "pairs", out_dir))
    assert process(out_dir) == 0
    store, ids = takes_of(out_dir)
    take = store.get(ids[0])
    assert take["status"] == "ready"
    edit = store.read(ids[0], "edit.json")
    assert len(edit["segments"]) == 4, "one piece for each file, cut where the files were joined"
    flags = {f for s in edit["segments"] for f in s["flags"]}
    assert not flags & {"cut_off", "phone_disagrees", "phone_stumble"}, flags
    checks = store.read(ids[0], "ack_checks.json")
    assert checks["mode"] == "files" and len(checks["pieces"]) == 4


@needs_ffmpeg
def test_a_file_whose_sentence_does_not_match_what_was_heard_is_flagged_so_it_stays_out_of_an_unreviewed_set(tmp_path, out_dir):
    root = folder_of_pairs(tmp_path, 2)
    fi.apply_import(fi.make_plan(root, "pairs", out_dir))
    store, ids = takes_of(out_dir)
    notes = store.read(ids[0], "ack_clips.json")
    notes["clips"][1]["text"] = "Completely different words about volcanoes and bicycles."
    store.write(ids[0], "ack_clips.json", notes)
    store.update(ids[0], reference_text="Six odd words nobody said here.")                  # what the fake listener will "hear"
    assert process(out_dir) == 0
    segments = store.read(ids[0], "edit.json")["segments"]
    assert len(segments) == 2
    assert "reads_differently" in segments[1]["flags"] or "reads_differently" in segments[0]["flags"]


def test_notes_for_files_are_usable_only_when_the_clips_are_in_order_and_do_not_overlap():
    good = {"mode": "files", "clips": [{"start_s": 0, "end_s": 1}, {"start_s": 1.4, "end_s": 2.5}]}
    assert usable_notes(good)
    assert not usable_notes({"mode": "files", "clips": [{"start_s": 0, "end_s": 1}, {"start_s": 0.5, "end_s": 2}]})
    assert not usable_notes({"mode": "files", "clips": []}) and not usable_notes({"mode": "files"}) and not usable_notes({"mode": "other", "clips": good["clips"]})


# ---------------------------------------------------------------- the command

def test_the_command_looks_without_writing_and_asks_nothing_when_asked_only_to_look(tmp_path, out_dir, capsys):
    root = folder_of_pairs(tmp_path, 2)
    before = tree(out_dir)
    assert fi.main([str(root), "--kind", "pairs", "--output", str(out_dir), "--dry-run"]) == 0
    printed = capsys.readouterr().out
    assert "Found 2 audio file(s)" in printed and "Would add 1 recording(s)" in printed and tree(out_dir) == before


def test_the_command_will_not_write_without_a_yes_when_nobody_can_be_asked(tmp_path, out_dir, capsys, monkeypatch):
    root = folder_of_pairs(tmp_path, 1)
    monkeypatch.setattr("sys.stdin", open(os.devnull))
    assert fi.main([str(root), "--kind", "audio", "--output", str(out_dir)]) == 2
    assert "add --yes" in capsys.readouterr().err and takes_of(out_dir)[1] == []


@needs_ffmpeg
def test_the_command_adds_with_yes_and_says_what_to_do_next(tmp_path, out_dir, capsys):
    root = folder_of_pairs(tmp_path, 2)
    assert fi.main([str(root), "--kind", "pairs", "--output", str(out_dir), "--yes"]) == 0
    printed = capsys.readouterr().out
    assert "Added 2 file(s) as 1 recording(s)" in printed and "freeform_studio.process" in printed and len(takes_of(out_dir)[1]) == 1


def test_a_refusal_is_said_in_a_sentence_and_exits_two(tmp_path, out_dir, capsys):
    assert fi.main([str(tmp_path / "nope"), "--kind", "audio", "--output", str(out_dir), "--dry-run"]) == 2
    assert "Can't continue" in capsys.readouterr().err


def test_every_code_the_importer_uses_is_listed():
    import re
    source = Path(fi.__file__).read_text()
    used_problems = set(re.findall(r'Problem\("([a-z_]+)"', source)) - {"bad_kind", "not_a_folder", "no_audio", "too_many_files"}
    used_stops = set(re.findall(r'FilesImportProblem\("([a-z_]+)"', source))
    assert used_problems <= set(fi.PROBLEM_CODES) | {"unreadable"} and used_stops <= set(fi.STOP_CODES), (used_problems - set(fi.PROBLEM_CODES), used_stops - set(fi.STOP_CODES))
    assert {i.reason for i in []} == set()


def test_the_importer_needs_no_numpy_so_the_window_can_use_it_and_its_rate_is_freeform_studios_own():
    import subprocess
    import sys
    probe = "import sys; sys.modules['numpy'] = None; import freeform_studio.files_import as f; print(f.WORK_RATE)"
    done = subprocess.run([sys.executable, "-c", probe], capture_output=True, text=True, cwd=str(Path(fi.__file__).resolve().parents[1]))
    assert done.returncode == 0 and done.stdout.strip() == "48000", done.stderr
    from freeform_studio import audio
    assert fi.WORK_RATE == audio.WORK_RATE


def test_a_missing_ffmpeg_is_said_in_a_word_and_leaves_the_file_out(tmp_path, out_dir, monkeypatch):
    root = folder_of_pairs(tmp_path, 1)
    plan = fi.make_plan(root, "audio", out_dir)
    monkeypatch.setattr(fi.shutil, "which", lambda name: None)
    result = fi.apply_import(plan)
    assert result.created == [] and [s.reason for s in result.skipped] == ["unreadable"]
