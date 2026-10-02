# SPDX-License-Identifier: GPL-3.0-or-later
"""The package reader: a good package opens and is fully checked; every way a package can be wrong is refused with a message that
names the problem, and nothing is ever written."""
import hashlib
import json
import os
import re
import stat
import zipfile
from pathlib import Path

import pytest

import ack_capture_reference as ref
import freeform_studio.ack_package as pkg
from ack_package_builder import ClipSpec, PackageBuilder, wav_bytes, write_zip
from freeform_studio.ack_package import PackageError, open_package, validate_manifest

DATA = Path(__file__).resolve().parent / "data" / "ack_capture"


def good(tmp_path, **kw):
    b = PackageBuilder()
    b.script_session(["The tide came in.", ClipSpec("We walked along the shore.", speech=3.0), "Gulls circled overhead."], **kw)
    b.free_session([(0.4, 3.0), (0.5, 7.0), (0.4, 4.0)], topic="my morning")
    return b, tmp_path / "p.zip"


def refuses(path, *needles):
    with pytest.raises(PackageError) as err:
        open_package(path)
    text = str(err.value)
    assert text.endswith("Nothing was imported."), text
    for n in needles:
        assert n in text, f"{n!r} not in:\n{text}"
    return text


# ------------------------------------------------------------------ a good package
def test_a_good_package_opens_and_is_fully_checked(tmp_path):
    b, path = good(tmp_path)
    b.write(path)
    seen = []
    p = open_package(path, progress=lambda done, total: seen.append((done, total)))
    assert [s["mode"] for s in p.sessions] == ["script", "free"]
    assert seen and seen[-1][0] == seen[-1][1] == sum(f["bytes"] for f in p.manifest["files"])
    assert set(p.wav) == set(b.audio)
    s = p.summary()
    assert s["sessions"][0]["clips"] == 3 and s["sessions"][1]["proposed_segments"] >= 1
    assert s["seconds"] > 10 and s["app_version"] == "1.0-beta.9"
    assert p.warnings == []


def test_audio_can_be_read_back_out_of_the_package(tmp_path):
    b, path = good(tmp_path)
    b.write(path)
    p = open_package(path)
    name = p.sessions[0]["clips"][0]["file"]
    with p.open_file(name) as f:
        assert f.read() == b.audio[name]
    with pytest.raises(KeyError):
        with p.open_file("manifest.json"):
            pass


@pytest.mark.parametrize("compression", [zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED])
def test_stored_and_deflated_entries_both_work(tmp_path, compression):
    b, path = good(tmp_path)
    b.write(path, compression=compression)
    open_package(path)


def test_44100_hz_and_unknown_extra_fields_are_fine(tmp_path):
    b = PackageBuilder()
    b.script_session(["Short one here."], rate=44100, source="VOICE_RECOGNITION", device={"model": "Pixel 8", "sdk": 35})

    def edit(m):
        m["something_new"] = {"later": True}
        m["sessions"][0]["clips"][0]["extra"] = 1
    b.write(tmp_path / "p.zip", manifest_edit=edit)
    open_package(tmp_path / "p.zip")


def test_folder_entries_and_a_readme_are_allowed(tmp_path):
    b, path = good(tmp_path)
    sid = b.sessions[0]["id"]

    def edit(entries):
        entries[:0] = [("sessions/", b""), (f"sessions/{sid}/", b""), (f"sessions/{sid}/clips/", b"")]
        entries.append(("README.txt", b"made by ACK"))
    b.write(path, entries_edit=edit)
    open_package(path)


def test_extra_device_details_are_dropped_with_a_warning(tmp_path):
    b = PackageBuilder()
    b.script_session(["Short one here."], device={"model": "Pixel 8", "sdk": 35, "serial": "ABC123"})
    b.write(tmp_path / "p.zip")
    p = open_package(tmp_path / "p.zip")
    assert any("serial" in w for w in p.warnings)


def test_odd_flags_are_ignored_with_a_warning_not_refused(tmp_path):
    b = PackageBuilder()
    b.script_session([ClipSpec("Short one here.", flags=["stumble", "Not A Flag!"])])
    b.write(tmp_path / "p.zip")
    assert any("flag" in w for w in open_package(tmp_path / "p.zip").warnings)


# ------------------------------------------------------------------ not a package at all
def test_a_missing_file(tmp_path):
    refuses(tmp_path / "nope.zip", "no file")


def test_something_that_is_not_a_zip(tmp_path):
    (tmp_path / "x.zip").write_bytes(b"this is not a zip file at all")
    refuses(tmp_path / "x.zip", "not a zip", "copy it again")


def test_a_zip_without_a_manifest(tmp_path):
    write_zip(tmp_path / "x.zip", [("README.txt", b"hi")])
    refuses(tmp_path / "x.zip", "no manifest.json")


def test_a_manifest_that_is_not_json(tmp_path):
    write_zip(tmp_path / "x.zip", [("manifest.json", b"{not json")])
    refuses(tmp_path / "x.zip", "manifest.json could not be read")


def test_an_oversized_manifest_is_refused_without_reading_it_all(tmp_path, monkeypatch):
    monkeypatch.setattr(pkg, "MAX_MANIFEST_BYTES", 1000)
    write_zip(tmp_path / "x.zip", [("manifest.json", b" " * 5000)])
    refuses(tmp_path / "x.zip", "larger than")


def test_a_package_from_a_different_format_version_says_which_it_reads(tmp_path):
    b, path = good(tmp_path)
    b.write(path, manifest_edit=lambda m: m.update(schema="ack-training-capture/2"))
    refuses(path, "ack-training-capture/2", "ack-training-capture/1", "Update Freeform Studio")


def test_a_manifest_that_is_not_ours(tmp_path):
    write_zip(tmp_path / "x.zip", [("manifest.json", b'{"schema": "something-else"}')])
    refuses(tmp_path / "x.zip", "does not say it is an ACK training capture")


# ------------------------------------------------------------------ names inside the zip
@pytest.mark.parametrize("name,needle", [
    ("../evil.wav", "outside the import folder"),
    ("/etc/passwd", "outside the import folder"),
    ("sessions/../../x", "outside the import folder"),
    ("sessions\\s20261002-180100-a3fa\\clips\\0001.wav", "backslash"),
    ("notes.txt", "not a file the format allows"),
    ("sessions/s20261002-180100-a3fa/clips/1.wav", "not a file the format allows"),
    ("sessions/other/session.wav", "not a file the format allows"),
])
def test_entry_names_the_format_does_not_allow_are_refused(tmp_path, name, needle):
    b, path = good(tmp_path)
    b.write(path, entries_edit=lambda e: e.append((name, b"x")))
    refuses(path, needle)


def test_a_folder_the_format_does_not_use_is_refused(tmp_path):
    b, path = good(tmp_path)
    b.write(path, entries_edit=lambda e: e.append(("extras/", b"")))
    refuses(path, "folder the format does not use")


def test_a_name_that_appears_twice_is_refused(tmp_path):
    b, path = good(tmp_path)
    b.write(path, entries_edit=lambda e: e.append(e[1]))
    refuses(path, "more than once")


def test_too_many_entries_are_refused(tmp_path, monkeypatch):
    b, path = good(tmp_path)
    b.write(path)
    monkeypatch.setattr(pkg, "MAX_ENTRIES", 3)
    refuses(path, "the most a package may hold is 3")


def set_flag_bits(path, name, bits):
    """Set general-purpose flag bits on one entry in the zip's central directory (the writer resets them on its own)."""
    raw = bytearray(path.read_bytes())
    pos = raw.find(b"PK\x01\x02")
    while pos != -1:
        n = int.from_bytes(raw[pos + 28:pos + 30], "little")
        if raw[pos + 46:pos + 46 + n].decode() == name:
            flags = int.from_bytes(raw[pos + 8:pos + 10], "little") | bits
            raw[pos + 8:pos + 10] = flags.to_bytes(2, "little")
            path.write_bytes(bytes(raw))
            return
        pos = raw.find(b"PK\x01\x02", pos + 4)
    raise AssertionError(f"{name} not found in the zip")


def test_encrypted_entries_are_refused(tmp_path):
    b, path = good(tmp_path)
    first = sorted(b.audio)[0]
    b.write(path)
    set_flag_bits(path, first, 0x1)
    refuses(path, first, "password-protected")


def test_link_entries_are_refused(tmp_path):
    b, path = good(tmp_path)
    first = sorted(b.audio)[0]

    def link(name, zi):
        if name == first:
            zi.external_attr = (stat.S_IFLNK | 0o777) << 16
    b.write(path, zipinfo_edit=link)
    refuses(path, first, "is a link")


def test_an_unsupported_compression_method_is_refused(tmp_path):
    b, path = good(tmp_path)
    b.write(path, compression=zipfile.ZIP_BZIP2)
    refuses(path, "compression method")


def test_a_total_size_over_the_limit_is_refused(tmp_path, monkeypatch):
    b, path = good(tmp_path)
    b.write(path)
    monkeypatch.setattr(pkg, "MAX_TOTAL_BYTES", 1000)
    refuses(path, "more than the")


# ------------------------------------------------------------------ the audio files
def test_a_changed_audio_file_fails_its_checksum_and_the_message_names_it(tmp_path):
    b, path = good(tmp_path)
    name = sorted(b.audio)[1]

    def edit(entries):
        for i, (n, d) in enumerate(entries):
            if n == name:
                flipped = bytearray(d)
                flipped[-5] ^= 0xFF
                entries[i] = (n, bytes(flipped))
    b.write(path, entries_edit=edit)
    refuses(path, name, "checksum")


def test_a_file_cut_short_is_refused(tmp_path):
    b, path = good(tmp_path)
    name = sorted(b.audio)[0]

    def edit(entries):
        for i, (n, d) in enumerate(entries):
            if n == name:
                entries[i] = (n, d[:-1000])
    b.write(path, entries_edit=edit)
    refuses(path, name, "zip says")


def test_a_file_bigger_than_the_manifest_says_is_refused(tmp_path):
    b, path = good(tmp_path)
    name = sorted(b.audio)[0]

    def manifest(m):
        for f in m["files"]:
            if f["path"] == name:
                f["bytes"] -= 100
    b.write(path, manifest_edit=manifest)
    refuses(path, name)


def test_a_wav_whose_header_lies_about_its_length_is_refused_as_interrupted(tmp_path):
    b = PackageBuilder()
    sid = b.script_session(["Short one here."])
    name = f"sessions/{sid}/clips/0001.wav"
    data = bytearray(b.audio[name])
    data[40:44] = (0xFFFFFFFF).to_bytes(4, "little")                    # a recording that was never finished
    b.audio[name] = bytes(data)
    b.write(tmp_path / "p.zip")
    refuses(tmp_path / "p.zip", name, "interrupted")


def test_audio_that_is_not_16_bit_mono_is_refused(tmp_path):
    b = PackageBuilder()
    sid = b.script_session(["Short one here."])
    name = f"sessions/{sid}/clips/0001.wav"
    data = bytearray(b.audio[name])
    data[22:24] = (2).to_bytes(2, "little")                              # claims two channels
    b.audio[name] = bytes(data)
    b.write(tmp_path / "p.zip")
    refuses(tmp_path / "p.zip", name, "16-bit mono")


def test_a_file_that_is_not_a_wav_is_refused(tmp_path):
    b = PackageBuilder()
    sid = b.script_session(["Short one here."])
    name = f"sessions/{sid}/clips/0001.wav"
    b.audio[name] = b"not a wav file at all" * 10
    b.write(tmp_path / "p.zip")
    refuses(tmp_path / "p.zip", name, "not a WAV")


def test_a_sample_rate_that_differs_from_the_session_is_refused(tmp_path):
    b = PackageBuilder()
    b.script_session(["Short one here."])
    b.write(tmp_path / "p.zip", manifest_edit=lambda m: m["sessions"][0]["audio"].update(sample_rate=44100))
    refuses(tmp_path / "p.zip", "48000 Hz but its session says 44100")


def test_a_duration_that_differs_from_the_audio_is_refused(tmp_path):
    b = PackageBuilder()
    b.script_session(["Short one here."])
    b.write(tmp_path / "p.zip", manifest_edit=lambda m: m["sessions"][0]["clips"][0].update(duration_s=9.0))
    refuses(tmp_path / "p.zip", "long but the manifest says 9.00")


def test_a_listed_file_that_is_missing_and_an_unlisted_file_are_both_named(tmp_path):
    b, path = good(tmp_path)
    gone = sorted(b.audio)[0]
    sid = b.sessions[0]["id"]
    extra = f"sessions/{sid}/clips/0099.wav"

    def edit(entries):
        entries[:] = [e for e in entries if e[0] != gone]
        entries.append((extra, wav_bytes(__import__("numpy").zeros(100, dtype="int16"), 48000)))
    b.write(path, entries_edit=edit)
    refuses(path, f"{gone} is listed but missing", f"{extra} is in the zip but not listed")


# ------------------------------------------------------------------ the manifest's own rules
def broken(tmp_path, edit, *needles):
    b = PackageBuilder()
    b.script_session(["The tide came in.", "We walked along the shore."])
    b.free_session([(0.4, 3.0), (0.5, 7.0)])
    b.write(tmp_path / "p.zip", manifest_edit=edit)
    return refuses(tmp_path / "p.zip", *needles)


def test_manifest_rules(tmp_path):
    broken(tmp_path, lambda m: m.update(created="yesterday"), "created should be a UTC time")
    broken(tmp_path, lambda m: m.update(sessions=[]), "1 to 200 sessions")
    broken(tmp_path, lambda m: m["sessions"][0].update(id="s1"), "its id is not in the form")
    broken(tmp_path, lambda m: m["sessions"][0].update(mode="live"), "mode must be")
    broken(tmp_path, lambda m: m["sessions"][0].update(label="x" * 121), "label must be text up to 120")
    broken(tmp_path, lambda m: m["sessions"][0].update(started="2026-13-40T99:00:00Z"), "started should be a UTC time")
    broken(tmp_path, lambda m: m["sessions"][0].update(language="english"), "language should look like en-US")
    broken(tmp_path, lambda m: m["sessions"][0]["audio"].update(sample_rate=8000), "sample_rate must be")
    broken(tmp_path, lambda m: m["sessions"][0]["audio"].update(source="mic one"), "short upper-case word")
    broken(tmp_path, lambda m: m["sessions"][0].update(noise_floor_dbfs=5), "noise_floor_dbfs")
    broken(tmp_path, lambda m: m["sessions"][0].update(device={"model": "x" * 61}), "device should be only")
    broken(tmp_path, lambda m: m["sessions"][0]["script"].update(id="bad id!"), "script details")


def test_clip_rules(tmp_path):
    broken(tmp_path, lambda m: m["sessions"][0]["clips"][1].update(index=1), "increasing order")
    broken(tmp_path, lambda m: m["sessions"][0]["clips"][0].update(card=0), "card should be a whole number")
    broken(tmp_path, lambda m: m["sessions"][0]["clips"][0].update(text="two\nlines"), "on one line")
    broken(tmp_path, lambda m: m["sessions"][0]["clips"][0].update(text="x" * 601), "1 to 600 characters")
    broken(tmp_path, lambda m: m["sessions"][0]["clips"][0].update(text="  "), "1 to 600 characters")
    broken(tmp_path, lambda m: m["sessions"][0]["clips"][0].update(file="sessions/x/clips/0001.wav"), "its file should be named")
    broken(tmp_path, lambda m: m["sessions"][0]["clips"][0]["speech"].update(start_s=5.0, end_s=4.0), "speech start and end")
    broken(tmp_path, lambda m: m["sessions"][0]["clips"][0]["metrics"].update(rms_dbfs=-300), "rms_dbfs")
    broken(tmp_path, lambda m: m["sessions"][0]["clips"][0]["metrics"].update(clipped_samples=-1), "clipped_samples")
    broken(tmp_path, lambda m: m["sessions"][0].update(clips=[]), "1 to 5000 clips")


def test_free_session_rules(tmp_path):
    broken(tmp_path, lambda m: m["sessions"][1]["recording"].update(duration_s=9999), "at most 5400")
    broken(tmp_path, lambda m: m["sessions"][1]["recording"]["proposed_segments"][0].update(end_kind="maybe"), "end_kind should be")
    broken(tmp_path, lambda m: m["sessions"][1]["recording"]["proposed_segments"][0].update(start_s=0.0, end_s=14.0), "longer than 11.5")
    broken(tmp_path, lambda m: m["sessions"][1].update(topic="t" * 201), "topic must be")


def test_files_list_rules(tmp_path):
    broken(tmp_path, lambda m: m["files"].append(dict(m["files"][0])), "listed twice")
    broken(tmp_path, lambda m: m["files"][0].update(sha256="ABC"), "64 lower-case hex")
    broken(tmp_path, lambda m: m["files"].append({"path": "x/y.wav", "bytes": 100, "sha256": "0" * 64}), "name the format does not allow")
    broken(tmp_path, lambda m: m["sessions"].append(m["sessions"][0]), "appears twice")


def test_the_example_manifest_from_the_shared_test_cases_passes_the_structure_checks():
    m = json.loads((DATA / "manifest_example.json").read_text(encoding="utf-8"))
    problems, warnings = validate_manifest(m)
    assert problems == [] and warnings == []


def test_the_reader_uses_the_same_limits_as_the_document():
    c = ref.CONSTANTS
    assert pkg.MAX_ENTRIES == c["MAX_ENTRIES"] and pkg.MAX_MANIFEST_BYTES == c["MAX_MANIFEST_BYTES"]
    assert pkg.MAX_SESSIONS == c["MAX_SESSIONS"] and pkg.MAX_CLIPS_PER_SESSION == c["MAX_CLIPS_PER_SESSION"]
    assert pkg.MAX_FREE_SESSION_S == c["MAX_FREE_SESSION_S"] and pkg.MAX_CARD_CHARS == c["MAX_CARD_CHARS"] and pkg.MAX_CLIP_S == c["MAX_CLIP_S"]


# ------------------------------------------------------------------ reading never writes
def test_refusing_a_package_leaves_the_folder_exactly_as_it_was(tmp_path):
    b, path = good(tmp_path)
    b.write(path, manifest_edit=lambda m: m.update(created="yesterday"))
    before = sorted(os.listdir(tmp_path))
    with pytest.raises(PackageError):
        open_package(path)
    assert sorted(os.listdir(tmp_path)) == before


def test_opening_a_good_package_does_not_modify_it(tmp_path):
    b, path = good(tmp_path)
    b.write(path)
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    open_package(path)
    assert hashlib.sha256(path.read_bytes()).hexdigest() == digest
