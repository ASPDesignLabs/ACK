# SPDX-License-Identifier: GPL-3.0-or-later
"""The download module (plan task VS-1.3): nothing is requested without agreement, and what arrives is checked byte for byte.

No real connection is made anywhere in this file: the opener is a stand-in.
"""
import errno
import hashlib
import os
import stat
import sys
import urllib.error
import urllib.request
from dataclasses import replace

import pytest

from vs_fetch_helpers import PAYLOAD, FakeOpener, http_error, pinned_item
from voice_studio.core import consent as cs
from voice_studio.core import fetch as fx
from voice_studio.core.fetch import FetchError
from voice_studio.core.system import CommandResult

ROOMY = lambda path: 10**12


def code_of(call):
    with pytest.raises(FetchError) as caught:
        call()
    return caught.value.code


def run_fetch(tmp_path, item=None, opener=None, consent="auto", **kwargs):
    item = item or pinned_item()
    if consent == "auto":
        consent = cs.make_consent([item])
    opener = opener or FakeOpener()
    kwargs.setdefault("disk_free", ROOMY)
    return fx.fetch(item, tmp_path / "dl", consent, opener=opener, **kwargs), opener


# ---------------------------------------------------------------- the good path

def test_a_file_arrives_checked_and_owner_only_with_nothing_left_behind(tmp_path):
    seen = []
    path, opener = run_fetch(tmp_path, progress=lambda done, total: seen.append((done, total)))
    assert path.read_bytes() == PAYLOAD and path.name == "model.ckpt"
    assert stat.S_IMODE(os.stat(path).st_mode) == 0o600
    assert [p.name for p in path.parent.iterdir()] == ["model.ckpt"]
    assert len(opener.calls) == 1 and "Range" not in opener.calls[0][1] and opener.calls[0][1]["User-Agent"] == fx.USER_AGENT
    assert seen[-1] == (len(PAYLOAD), len(PAYLOAD)) and [d for d, _ in seen] == sorted(d for d, _ in seen)


def test_the_part_file_is_owner_only_while_it_is_still_downloading(tmp_path, monkeypatch):
    monkeypatch.setattr(fx, "CHUNK", 100)
    old_umask = os.umask(0)                      # no umask to hide a wrong creation mode
    try:
        modes = []
        part = tmp_path / "dl" / "model.ckpt.part"
        run_fetch(tmp_path, progress=lambda done, total: modes.append(stat.S_IMODE(os.stat(part).st_mode)))
    finally:
        os.umask(old_umask)
    assert modes and set(modes) == {0o600}


def test_a_file_that_is_already_here_and_right_uses_no_network(tmp_path):
    path, _ = run_fetch(tmp_path)
    again, opener = run_fetch(tmp_path)
    assert again == path and opener.calls == []


def test_a_damaged_file_is_replaced_only_once_the_new_one_is_verified(tmp_path):
    path, _ = run_fetch(tmp_path)
    path.write_bytes(b"corrupt")
    again, opener = run_fetch(tmp_path)
    assert again.read_bytes() == PAYLOAD and len(opener.calls) == 1


# ---------------------------------------------------------------- closed unless agreed

def test_without_agreement_nothing_is_requested(tmp_path):
    opener = FakeOpener()
    assert code_of(lambda: fx.fetch(pinned_item(), tmp_path, None, opener=opener, disk_free=ROOMY)) == "consent"
    assert code_of(lambda: fx.fetch(pinned_item(), tmp_path, cs.make_consent([]), opener=opener, disk_free=ROOMY)) == "consent"
    assert opener.calls == [] and list(tmp_path.iterdir()) == []


def test_agreement_for_another_file_under_the_same_name_does_not_count(tmp_path):
    agreed = pinned_item()
    changed = replace(agreed, sha256="b" * 64)
    opener = FakeOpener()
    assert code_of(lambda: fx.fetch(changed, tmp_path, cs.make_consent([agreed]), opener=opener, disk_free=ROOMY)) == "consent"
    assert opener.calls == []


def test_an_entry_that_is_not_pinned_is_refused_before_anything_else(tmp_path):
    unpinned = replace(pinned_item(), url=None, filename=None, revision=None, size_bytes=None, sha256=None)
    opener = FakeOpener()
    assert code_of(lambda: fx.fetch(unpinned, tmp_path, cs.make_consent([unpinned]), opener=opener, disk_free=ROOMY)) == "not_pinned"
    assert opener.calls == []


def test_a_name_that_leads_outside_the_folder_is_refused(tmp_path):
    outside = tmp_path / "elsewhere"
    outside.mkdir()
    dest = tmp_path / "dl"
    dest.mkdir()
    (dest / "model.ckpt").symlink_to(outside / "model.ckpt")           # a link planted where the file would go
    item = pinned_item()
    opener = FakeOpener()
    assert code_of(lambda: fx.fetch(item, dest, cs.make_consent([item]), opener=opener, disk_free=ROOMY)) == "unsafe_name"
    assert opener.calls == [] and not (outside / "model.ckpt").exists()


# ---------------------------------------------------------------- wrong or missing bytes

def test_wrong_content_is_never_kept_and_never_resumed(tmp_path):
    tampered = bytes([PAYLOAD[0] ^ 1]) + PAYLOAD[1:]
    assert code_of(lambda: run_fetch(tmp_path, opener=FakeOpener(tampered))) == "checksum"
    assert list((tmp_path / "dl").iterdir()) == []


def test_too_few_bytes_keeps_the_part_so_the_rest_can_be_fetched_later(tmp_path):
    assert code_of(lambda: run_fetch(tmp_path, opener=FakeOpener(serve=PAYLOAD[:1000]))) == "size"
    assert (tmp_path / "dl" / "model.ckpt.part").stat().st_size == 1000 and not (tmp_path / "dl" / "model.ckpt").exists()
    path, opener = run_fetch(tmp_path)
    assert path.read_bytes() == PAYLOAD and opener.calls[0][1]["Range"] == "bytes=1000-" and opener.bytes_sent == len(PAYLOAD) - 1000


def test_too_many_bytes_is_refused_and_the_part_never_grows_past_the_agreed_size(tmp_path):
    assert code_of(lambda: run_fetch(tmp_path, opener=FakeOpener(serve=PAYLOAD + b"extra"))) == "size"
    assert (tmp_path / "dl" / "model.ckpt.part").stat().st_size <= len(PAYLOAD)


# ---------------------------------------------------------------- resuming

def test_a_part_left_by_an_earlier_try_is_resumed_not_downloaded_again(tmp_path):
    dl = tmp_path / "dl"
    dl.mkdir()
    (dl / "model.ckpt.part").write_bytes(PAYLOAD[:700])
    path, opener = run_fetch(tmp_path)
    assert path.read_bytes() == PAYLOAD and opener.calls[0][1]["Range"] == "bytes=700-" and opener.bytes_sent == len(PAYLOAD) - 700


def test_a_server_that_ignores_the_range_gets_a_clean_restart(tmp_path):
    dl = tmp_path / "dl"
    dl.mkdir()
    (dl / "model.ckpt.part").write_bytes(PAYLOAD[:700])
    path, opener = run_fetch(tmp_path, opener=FakeOpener(honor_range=False))
    assert path.read_bytes() == PAYLOAD and opener.bytes_sent == len(PAYLOAD)


def test_a_server_that_answers_the_wrong_range_is_an_error_not_a_silent_corruption(tmp_path):
    dl = tmp_path / "dl"
    dl.mkdir()
    (dl / "model.ckpt.part").write_bytes(PAYLOAD[:700])

    class WrongRange(FakeOpener):
        def __call__(self, url, headers):
            response = super().__call__(url, headers)
            response.headers = {"Content-Range": "bytes 5-9/10"}
            return response
    assert code_of(lambda: run_fetch(tmp_path, opener=WrongRange())) == "http"


def test_a_range_the_server_refuses_starts_again_from_the_beginning(tmp_path):
    dl = tmp_path / "dl"
    dl.mkdir()
    (dl / "model.ckpt.part").write_bytes(PAYLOAD[:700])
    path, opener = run_fetch(tmp_path, opener=FakeOpener(raise_first=http_error(416)))
    assert path.read_bytes() == PAYLOAD and "Range" in opener.calls[0][1] and "Range" not in opener.calls[1][1]


def test_a_second_refusal_is_an_error(tmp_path):
    class AlwaysRefuses(FakeOpener):
        def __call__(self, url, headers):
            self.calls.append((url, dict(headers)))
            raise http_error(416)
    dl = tmp_path / "dl"
    dl.mkdir()
    (dl / "model.ckpt.part").write_bytes(PAYLOAD[:700])
    assert code_of(lambda: run_fetch(tmp_path, opener=AlwaysRefuses())) == "http"


def test_a_part_that_already_holds_everything_is_finished_without_the_network(tmp_path):
    dl = tmp_path / "dl"
    dl.mkdir()
    (dl / "model.ckpt.part").write_bytes(PAYLOAD)
    path, opener = run_fetch(tmp_path)
    assert path.read_bytes() == PAYLOAD and opener.calls == [] and not (dl / "model.ckpt.part").exists()


def test_a_full_size_part_with_wrong_content_and_an_oversized_part_are_thrown_away(tmp_path):
    dl = tmp_path / "dl"
    dl.mkdir()
    (dl / "model.ckpt.part").write_bytes(b"x" * len(PAYLOAD))
    path, opener = run_fetch(tmp_path)
    assert path.read_bytes() == PAYLOAD and "Range" not in opener.calls[0][1]
    path.unlink()
    (dl / "model.ckpt.part").write_bytes(PAYLOAD + b"more")
    path, opener = run_fetch(tmp_path)
    assert path.read_bytes() == PAYLOAD and "Range" not in opener.calls[0][1]


def test_cancelling_stops_at_once_and_keeps_the_part_to_resume(tmp_path, monkeypatch):
    monkeypatch.setattr(fx, "CHUNK", 100)
    blocks = []
    code = code_of(lambda: run_fetch(tmp_path, progress=lambda d, t: blocks.append(d), cancelled=lambda: len(blocks) >= 3))
    assert code == "cancelled" and blocks == [100, 200, 300]
    assert (tmp_path / "dl" / "model.ckpt.part").stat().st_size == 300
    path, opener = run_fetch(tmp_path)
    assert path.read_bytes() == PAYLOAD and opener.calls[0][1]["Range"] == "bytes=300-"


# ---------------------------------------------------------------- room and failures

def test_without_room_for_the_file_and_the_margin_nothing_is_requested(tmp_path):
    item = pinned_item()
    margin = 500
    opener = FakeOpener()
    needed = item.size_bytes + margin
    assert code_of(lambda: run_fetch(tmp_path, item, opener, room_margin=margin, disk_free=lambda p: needed - 1)) == "room"
    assert opener.calls == []
    path, _ = run_fetch(tmp_path, item, FakeOpener(), room_margin=margin, disk_free=lambda p: needed)         # exactly enough is enough
    assert path.exists()


def test_room_is_counted_for_what_is_still_to_come_not_what_is_already_kept(tmp_path):
    dl = tmp_path / "dl"
    dl.mkdir()
    (dl / "model.ckpt.part").write_bytes(PAYLOAD[:1000])
    path, _ = run_fetch(tmp_path, room_margin=0, disk_free=lambda p: len(PAYLOAD) - 1000)
    assert path.exists()


def test_a_disk_that_cannot_be_read_does_not_stop_the_download(tmp_path):
    path, _ = run_fetch(tmp_path, disk_free=lambda p: None)
    assert path.exists()


def test_the_disk_filling_up_mid_download_is_its_own_error(tmp_path, monkeypatch):
    real = os.fdopen

    class Full:
        def __init__(self, handle):
            self.handle = handle

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            self.handle.close()

        def write(self, data):
            raise OSError(errno.ENOSPC, "No space left on device")
    monkeypatch.setattr(fx.os, "fdopen", lambda fd, mode: Full(real(fd, mode)))
    assert code_of(lambda: run_fetch(tmp_path)) == "disk"


@pytest.mark.parametrize("raised, expected", [(http_error(404), "http"), (urllib.error.URLError("no route"), "http"), (OSError("reset"), "http")])
def test_connection_trouble_is_one_plain_error(tmp_path, raised, expected):
    assert code_of(lambda: run_fetch(tmp_path, opener=FakeOpener(raise_first=raised))) == expected


def test_an_unexpected_status_is_an_error(tmp_path):
    assert code_of(lambda: run_fetch(tmp_path, opener=FakeOpener(status=500))) == "http"


def test_a_redirect_to_plain_http_is_refused_and_one_to_https_is_followed():
    handler = fx._HttpsOnlyRedirects()
    request = urllib.request.Request("https://huggingface.co/x")
    with pytest.raises(urllib.error.HTTPError):
        handler.redirect_request(request, None, 302, "Found", {}, "http://cdn.example/x")
    assert handler.redirect_request(request, None, 302, "Found", {}, "https://cdn.example/x").full_url == "https://cdn.example/x"


# ---------------------------------------------------------------- door two: commands that reach the network

def test_a_networked_command_is_refused_without_agreement_by_name(tmp_path):
    calls = []
    runner = lambda argv: calls.append(argv) or CommandResult(0, "ok\n")
    assert code_of(lambda: fx.run_networked(None, ["pip", "install", "x"], ["pip:lock"], runner=runner)) == "consent"
    assert code_of(lambda: fx.run_networked(cs.make_consent([], ["apt:git"]), ["pip", "install", "x"], ["pip:lock"], runner=runner)) == "consent"
    assert code_of(lambda: fx.run_networked(cs.make_consent([], ["pip:lock"]), ["pip", "install", "x"], [], runner=runner)) == "consent"
    assert code_of(lambda: fx.run_networked(cs.make_consent([], ["apt:git"]), ["apt-get", "install"], ["apt:git", "apt:cmake"], runner=runner)) == "consent"
    assert calls == []


def test_with_agreement_the_command_runs_and_its_output_is_passed_on_line_by_line():
    lines = []
    result = fx.run_networked(cs.make_consent([], ["pip:lock"]), ["pip", "install", "x"], ["pip:lock"], on_line=lines.append,
                              runner=lambda argv: CommandResult(0, "one\ntwo\n"))
    assert result.returncode == 0 and lines == ["one", "two"]


def test_a_real_process_is_run_and_streamed_and_its_exit_status_is_kept():
    consent = cs.make_consent([], ["pip:lock"])
    lines = []
    ok = fx.run_networked(consent, [sys.executable, "-c", "print('a'); print('b')"], ["pip:lock"], on_line=lines.append)
    assert ok.returncode == 0 and lines == ["a", "b"] and ok.stdout == "a\nb\n"
    assert fx.run_networked(consent, [sys.executable, "-c", "import sys; sys.exit(3)"], ["pip:lock"]).returncode == 3
    assert code_of(lambda: fx.run_networked(consent, ["/definitely/not/a/program"], ["pip:lock"])) == "http"


def test_a_command_run_in_the_persons_own_terminal_is_still_refused_without_agreement(capfd):
    consent = cs.make_consent([], ["apt:git"])
    code = code_of(lambda: fx.run_networked(None, [sys.executable, "-c", "print('ran')"], ["apt:git"], inherit_stdio=True))
    assert code == "consent"
    assert code_of(lambda: fx.run_networked(consent, [sys.executable, "-c", "print('ran')"], ["apt:cmake"], inherit_stdio=True)) == "consent"
    assert code_of(lambda: fx.run_networked(consent, [sys.executable, "-c", "print('ran')"], [], inherit_stdio=True)) == "consent"
    assert "ran" not in capfd.readouterr().out


def test_with_inherited_terminal_the_output_goes_straight_to_the_person_and_this_program_never_sees_it(capfd):
    consent = cs.make_consent([], ["apt:git"])
    result = fx.run_networked(consent, [sys.executable, "-c", "import sys; print('shown to you'); print('also', file=sys.stderr); sys.exit(4)"],
                              ["apt:git"], inherit_stdio=True)
    shown = capfd.readouterr()
    assert "shown to you" in shown.out and "also" in shown.err
    assert (result.returncode, result.stdout, result.stderr) == (4, "", "")


def test_with_inherited_terminal_the_program_can_read_what_the_person_types(tmp_path):
    consent = cs.make_consent([], ["apt:git"])
    script = tmp_path / "ask.py"
    script.write_text("import sys\nsys.exit(0 if sys.stdin.readline().strip() == 'typed' else 7)\n")
    stdin_path = tmp_path / "stdin.txt"
    stdin_path.write_text("typed\n")
    fd = os.open(str(stdin_path), os.O_RDONLY)
    saved = os.dup(0)
    try:
        os.dup2(fd, 0)
        assert fx.run_networked(consent, [sys.executable, str(script)], ["apt:git"], inherit_stdio=True).returncode == 0
    finally:
        os.dup2(saved, 0)
        os.close(saved)
        os.close(fd)


def test_with_inherited_terminal_a_program_that_is_not_there_is_a_plain_error():
    consent = cs.make_consent([], ["apt:git"])
    assert code_of(lambda: fx.run_networked(consent, ["/definitely/not/a/program"], ["apt:git"], inherit_stdio=True)) == "http"


# ---------------------------------------------------------------- is it already here

def test_a_finished_file_that_is_what_was_agreed_counts_as_fetched(tmp_path):
    item = pinned_item()
    (tmp_path / item.filename).write_bytes(PAYLOAD)
    assert fx.is_fetched(item, tmp_path)


def test_a_file_that_is_not_there_or_is_wrong_or_is_only_part_of_it_is_not_fetched(tmp_path):
    item = pinned_item()
    assert not fx.is_fetched(item, tmp_path)
    (tmp_path / item.filename).write_bytes(PAYLOAD[:-1])
    assert not fx.is_fetched(item, tmp_path)
    (tmp_path / item.filename).write_bytes(PAYLOAD[:-1] + b"X")
    assert not fx.is_fetched(item, tmp_path)
    (tmp_path / item.filename).unlink()
    (tmp_path / (item.filename + ".part")).write_bytes(PAYLOAD)
    assert not fx.is_fetched(item, tmp_path)


def test_an_unpinned_item_is_never_fetched_and_a_missing_folder_is_not_an_error(tmp_path):
    unpinned = replace(pinned_item(), url=None, filename=None, revision=None, size_bytes=None, sha256=None)
    assert not fx.is_fetched(unpinned, tmp_path)
    assert not fx.is_fetched(pinned_item(), tmp_path / "nowhere")


def test_a_folder_in_place_of_the_file_is_not_a_fetched_file(tmp_path):
    item = pinned_item()
    (tmp_path / item.filename).mkdir()
    assert not fx.is_fetched(item, tmp_path)
