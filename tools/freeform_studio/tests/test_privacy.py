# SPDX-License-Identifier: GPL-3.0-or-later
"""Keeping recordings on this computer: offline model loading, who can read the files, what a browser may keep, cloud-synced folders."""
import os
import stat
import subprocess
import sys
import time
from pathlib import Path

import pytest

from conftest import needs_ffmpeg
from freeform_studio import asr, doctor, models, privacy
from freeform_studio import backup as bk
from freeform_studio.app import create_app
from freeform_studio.asr import AsrOptions, EngineError, FasterWhisperEngine, make_engine
from freeform_studio.config import Config
from test_api import make_cfg, run, upload, wait_for, webm_chunks
from test_backup import make_take
from test_netcheck_doctor import doctor_output, free_port

TOOLS = Path(__file__).resolve().parents[2]


# ---------------------------------------------------------------- the speech model is only ever loaded from this computer

def test_the_engine_loads_only_the_local_copy_unless_downloading_is_allowed(tmp_path):
    seen = []
    from conftest import fake_whisper_model
    factory = lambda name, **kw: (seen.append(kw), fake_whisper_model())[1]
    FasterWhisperEngine("small.en", model_factory=factory).transcribe(tmp_path / "x.wav", AsrOptions())
    FasterWhisperEngine("small.en", model_factory=factory, local_files_only=False).transcribe(tmp_path / "x.wav", AsrOptions())
    assert [kw["local_files_only"] for kw in seen] == [True, False]


def test_make_engine_follows_the_allow_download_setting(tmp_path):
    assert make_engine(Config(output_dir=tmp_path, asr_engine="faster-whisper")).local_files_only is True
    assert make_engine(Config(output_dir=tmp_path, asr_engine="faster-whisper", asr_allow_download=True)).local_files_only is False


def test_a_model_that_is_not_on_this_computer_gets_a_plain_message_with_the_exact_command(tmp_path):
    class LocalEntryNotFoundError(FileNotFoundError):   # the real error's name and base class, as measured
        pass

    def missing(name, **kw):
        raise LocalEntryNotFoundError("Cannot find an appropriate cached snapshot folder ... outgoing traffic has been disabled.")

    with pytest.raises(EngineError) as e:
        FasterWhisperEngine("small.en", model_factory=missing).transcribe(tmp_path / "x.wav", AsrOptions())
    msg = str(e.value)
    assert "isn't on this computer yet" in msg and "python -m freeform_studio.models fetch small.en" in msg
    assert "--allow-model-download" in msg and "nothing you recorded is sent" in msg
    assert "Traceback" not in msg and len(msg) < 450


def test_the_real_missing_model_error_is_recognised_when_the_libraries_are_installed(tmp_path, monkeypatch):
    pytest.importorskip("faster_whisper")
    monkeypatch.setenv("HF_HUB_OFFLINE", "1")
    from faster_whisper.utils import download_model
    with pytest.raises(Exception) as e:
        download_model("tiny.en", cache_dir=str(tmp_path / "empty"), local_files_only=True)
    assert "isn't on this computer yet" in asr.explain_load_error("tiny.en", "cpu", e.value)


# ---------------------------------------------------------------- fetching a model is explicit, and asks first

class Recorder:
    def __init__(self, have=False, fail=False):
        self.calls, self.have, self.fail, self.said = [], have, fail, []

    def download(self, name, local_files_only):
        self.calls.append((name, local_files_only))
        if local_files_only:
            if not self.have:
                raise FileNotFoundError("not cached")
            return "/cache/model"
        if self.fail:
            raise ConnectionError("network unreachable\nsecond line")
        self.have = True
        return "/cache/model"

    def say(self, text):
        self.said.append(text)


def test_fetch_says_what_it_will_do_and_downloads_nothing_unless_you_agree():
    r = Recorder()
    code = models.fetch("small.en", ask=lambda _q: "n", say=r.say, download=r.download)
    out = "\n".join(r.said)
    assert code == 1 and "Nothing was downloaded" in out
    assert "huggingface.co" in out and "Nothing you recorded is sent" in out and "about 480 MB" in out
    assert all(local for _name, local in r.calls), "only checked the local disk; never went online"


def test_fetch_downloads_once_when_you_say_yes_and_then_the_model_is_local():
    r = Recorder()
    assert models.fetch("small.en", ask=lambda _q: "y", say=r.say, download=r.download) == 0
    assert ("small.en", False) in r.calls
    assert "with no network" in "\n".join(r.said)
    r2 = Recorder(have=True)
    assert models.fetch("small.en", ask=lambda _q: pytest.fail("must not ask"), say=r2.say, download=r2.download) == 0
    assert ("small.en", False) not in r2.calls, "already there: nothing to download"


def test_fetch_failures_are_plain_and_say_it_can_be_repeated():
    r = Recorder(fail=True)
    assert models.fetch("small.en", assume_yes=True, say=r.say, download=r.download) == 1
    out = "\n".join(r.said)
    assert "did not finish: network unreachable" in out and "second line" not in out and "resumes" in out


def test_a_model_folder_you_already_have_counts_and_a_wrong_path_is_called_out(tmp_path):
    folder = tmp_path / "my-model"
    folder.mkdir()
    assert models.resolve_local(str(folder), download=lambda *_a: pytest.fail("no lookup needed")) == str(folder)
    r = Recorder()
    assert models.fetch(str(tmp_path / "nope"), assume_yes=True, say=r.say, download=r.download) == 2
    assert "looks like a folder" in "\n".join(r.said)


def test_the_fetch_command_clears_an_offline_switch_left_in_your_shell(monkeypatch):
    monkeypatch.setenv("HF_HUB_OFFLINE", "1")
    seen = {}
    monkeypatch.setattr(models, "fetch", lambda name, assume_yes=False: seen.update(offline=os.environ.get("HF_HUB_OFFLINE")) or 0)
    assert models.main(["fetch", "small.en", "--yes"]) == 0
    assert seen["offline"] is None, "you asked to download; the switch must not silently defeat that"


def test_offline_defaults_are_set_for_the_server_but_do_not_override_your_own_choice(monkeypatch):
    for k in ("HF_HUB_OFFLINE", "HF_HUB_DISABLE_TELEMETRY", "DO_NOT_TRACK"):
        monkeypatch.delenv(k, raising=False)
    privacy.apply_offline_defaults(False)
    assert os.environ["HF_HUB_OFFLINE"] == "1" and os.environ["HF_HUB_DISABLE_TELEMETRY"] == "1" and os.environ["DO_NOT_TRACK"] == "1"
    monkeypatch.delenv("HF_HUB_OFFLINE")
    privacy.apply_offline_defaults(True)
    assert "HF_HUB_OFFLINE" not in os.environ, "when downloading is allowed the switch is not forced on"
    monkeypatch.setenv("HF_HUB_OFFLINE", "0")
    privacy.apply_offline_defaults(False)
    assert os.environ["HF_HUB_OFFLINE"] == "0", "setdefault: a deliberate choice stays"


# ---------------------------------------------------------------- who can read the files

def mode(path):
    return stat.S_IMODE(Path(path).stat().st_mode)


@pytest.mark.skipif(os.name != "posix", reason="Unix permissions")
def test_private_umask_makes_new_files_owner_only_and_puts_the_old_setting_back(tmp_path):
    before = os.umask(0o022)
    try:
        with privacy.private_umask():
            (tmp_path / "d").mkdir()
            (tmp_path / "d" / "f.txt").write_text("x")
        assert mode(tmp_path / "d") == 0o700 and mode(tmp_path / "d" / "f.txt") == 0o600
        (tmp_path / "after.txt").write_text("x")
        assert mode(tmp_path / "after.txt") == 0o644, "outside the block nothing changed"
    finally:
        os.umask(before)


@pytest.mark.skipif(os.name != "posix", reason="Unix permissions")
def test_backups_and_exports_made_by_the_commands_are_owner_only(out_dir, tmp_path):
    make_take(out_dir, "t20260930-000001-aaaa")
    before = os.umask(0o022)
    try:
        assert bk.main(["--output", str(out_dir), "--backup-dir", str(tmp_path / "bk")]) == 0
        archives = list((tmp_path / "bk").glob("*.tar.gz"))
        assert archives and mode(archives[0]) == 0o600 and mode(tmp_path / "bk") == 0o700
        assert os.umask(0o022) == 0o022, "the command put the caller's umask back"
    finally:
        os.umask(before)


def test_the_backup_command_warns_about_a_synced_folder_but_still_backs_up(out_dir, tmp_path, capsys):
    make_take(out_dir, "t20260930-000001-aaaa")
    assert bk.main(["--output", str(out_dir), "--backup-dir", str(tmp_path / "OneDrive" / "bk")]) == 0
    out = capsys.readouterr().out
    assert "WARNING: The backup folder" in out and "may be uploaded to a cloud service" in out and "Backed up 1 recordings" in out
    assert list((tmp_path / "OneDrive" / "bk").glob("*.tar.gz")), "a warning, not a refusal: the choice is yours"
    assert bk.main(["--output", str(out_dir), "--backup-dir", str(tmp_path / "plain"), "--force"]) == 0
    assert "WARNING" not in capsys.readouterr().out


@pytest.mark.skipif(os.name != "posix", reason="Unix permissions")
def test_the_token_file_is_born_owner_only_and_is_kept(tmp_path):
    from freeform_studio.__main__ import resolve_token
    (tmp_path / "out").mkdir()
    first = resolve_token("auto", tmp_path / "out", "en-US")
    path = tmp_path / "out" / "_freeform" / "token"
    assert mode(path) == 0o600 and first and path.read_text().strip() == first
    assert resolve_token("auto", tmp_path / "out", "en-US") == first


@pytest.mark.skipif(os.name != "posix", reason="Unix permissions")
def test_loose_permissions_finds_what_other_accounts_could_read(tmp_path):
    lib = tmp_path / "_freeform"
    (lib / "takes").mkdir(parents=True)
    f = lib / "takes" / "raw.webm"
    f.write_bytes(b"x")
    os.chmod(lib, 0o700), os.chmod(lib / "takes", 0o700), os.chmod(f, 0o600)
    assert privacy.loose_permissions(lib) == []
    os.chmod(f, 0o644)
    assert privacy.loose_permissions(lib) == [str(f)]
    assert privacy.loose_permissions(tmp_path / "missing") == []


@pytest.mark.skipif(os.name != "posix", reason="Unix permissions")
def test_the_doctor_reports_readable_by_others_and_says_how_to_tighten_it_without_changing_anything(tmp_path, capsys):
    out_dir = tmp_path / "out"
    take = make_take(out_dir, "t20260930-000001-aaaa")
    os.chmod(take / "raw.webm", 0o644)
    before = mode(take / "raw.webm")
    code, text = doctor_output(capsys, "--output", str(out_dir), "--backup-dir", str(tmp_path / "bk"), "--port", str(free_port()))
    assert "other accounts on this computer can read your recordings folder" in text and "chmod -R go-rwx" in text
    assert mode(take / "raw.webm") == before, "the doctor only looks"
    for p in [out_dir / "_freeform", *(out_dir / "_freeform").rglob("*")]:
        os.chmod(p, 0o700 if p.is_dir() else 0o600)
    code, text = doctor_output(capsys, "--output", str(out_dir), "--backup-dir", str(tmp_path / "bk"), "--port", str(free_port()))
    assert "other accounts" not in text


# ---------------------------------------------------------------- folders a cloud service may be uploading

@pytest.mark.parametrize("path,expected", [
    ("/mnt/c/Users/me/OneDrive/freeform-backups", "OneDrive"),
    ("/mnt/c/Users/me/OneDrive - Some Clinic/x", "OneDrive"),
    ("/mnt/c/Users/me/Documents/voice", "Windows 'Documents' folder"),
    ("/mnt/d/Users/me/Desktop/voice", "Windows 'Desktop' folder"),
    ("C:\\Users\\me\\Pictures\\voice", "Windows 'Pictures' folder"),
    ("/home/me/Dropbox/voice", "Dropbox"),
    ("/home/me/Google Drive/voice", "Google Drive"),
    ("/home/me/iCloudDrive/voice", "iCloud Drive"),
    ("/home/me/Nextcloud/voice", "file-sync program"),
])
def test_folders_that_look_cloud_synced_are_flagged(path, expected):
    assert expected in (privacy.sync_risk(path) or "")


@pytest.mark.parametrize("path", [
    "/home/me/backups/freeform-studio", "/mnt/c/Users/me/freeform-backups", "/home/me/drive", "/mnt/c/Users/me",
    "/home/me/piper-recording-studio/output", "/mnt/c/Users/me/AppData/Local/x",
])
def test_ordinary_folders_are_not_flagged(path):
    assert privacy.sync_risk(path) is None


def test_the_sync_warning_is_one_plain_sentence_with_the_way_out():
    text = privacy.sync_warning("/mnt/c/Users/me/OneDrive/backups", "Your backup folder")
    assert text.startswith("Your backup folder /mnt/c/Users/me/OneDrive/backups may be uploaded to a cloud service")
    assert "not synced" in text and privacy.sync_warning("/home/me/backups", "x") is None


def test_the_doctor_flags_a_synced_backup_folder(tmp_path, capsys):
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    code, text = doctor_output(capsys, "--output", str(out_dir), "--backup-dir", str(tmp_path / "OneDrive" / "backups"), "--port", str(free_port()))
    assert "Your backup folder" in text and "may be uploaded to a cloud service" in text


def test_the_doctor_reports_whether_the_model_is_on_this_computer(tmp_path, capsys, monkeypatch):
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    monkeypatch.setattr(doctor, "_has_module", lambda _name: True)
    monkeypatch.setattr(models, "is_available", lambda _name: False)
    code, text = doctor_output(capsys, "--output", str(out_dir), "--backup-dir", str(tmp_path / "bk"), "--port", str(free_port()))
    assert "speech model 'small.en' isn't on this computer yet" in text and "models fetch small.en" in text
    monkeypatch.setattr(models, "is_available", lambda _name: True)
    code, text = doctor_output(capsys, "--output", str(out_dir), "--backup-dir", str(tmp_path / "bk"), "--port", str(free_port()))
    assert "speech model 'small.en' is on this computer" in text and "isn't on this computer yet" not in text


def start_server_and_read_banner(out_dir, *extra, seconds=6):
    proc = subprocess.Popen([sys.executable, "-m", "freeform_studio", "--output", str(out_dir), "--port", str(free_port()),
                             "--token", "none", *extra], cwd=TOOLS, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    lines, deadline = [], time.time() + seconds
    try:
        while time.time() < deadline:
            line = proc.stdout.readline()
            if not line:
                break
            lines.append(line)
            if "Running on" in line:      # the server logs this only after the whole start-up message has been printed
                break
    finally:
        proc.terminate()
        proc.wait(timeout=10)
    return "".join(lines)


def test_the_start_up_message_says_the_server_never_uses_the_internet_and_warns_about_synced_folders(tmp_path):
    out_dir = tmp_path / "OneDrive" / "output"
    out_dir.mkdir(parents=True)
    text = start_server_and_read_banner(out_dir, "--backup-dir", str(tmp_path / "bk"))
    assert "loaded from this computer only; the server never uses the internet" in text
    assert "Your recordings folder" in text and "may be uploaded to a cloud service" in text
    (tmp_path / "plain").mkdir()
    allowed = start_server_and_read_banner(tmp_path / "plain", "--allow-model-download")
    assert "may be downloaded by the server on first use" in allowed


# ---------------------------------------------------------------- what a browser may keep, and what stays in the address bar

@needs_ffmpeg
def test_recordings_and_api_answers_are_not_kept_by_the_browser(out_dir, tmp_path):
    chunks, _ = webm_chunks(tmp_path)

    async def main():
        app = create_app(make_cfg(out_dir))
        async with app.test_app():
            c = app.test_client()
            tid = await upload(c, chunks)
            await c.post(f"/api/takes/{tid}/finish")
            await wait_for(c, tid, ("ready",))
            for path in ("/api/takes", f"/api/takes/{tid}", f"/api/takes/{tid}/edit", f"/api/takes/{tid}/audio",
                         f"/api/takes/{tid}/peaks", "/api/status", "/api/backup"):
                r = await c.get(path)
                assert r.status_code == 200, path
                assert r.headers["cache-control"] == "private, no-store", (path, r.headers.get("cache-control"))
            ranged = await c.get(f"/api/takes/{tid}/audio", headers={"Range": "bytes=0-99"})
            assert ranged.status_code == 206 and ranged.headers["cache-control"] == "private, no-store", "seeking still works"
            page = await c.get("/")
            assert "no-store" not in page.headers.get("cache-control", ""), "the page's own files may be cached; they hold nothing personal"

    run(main())


def test_the_link_with_the_token_is_replaced_by_a_clean_address(out_dir):
    async def main():
        app = create_app(make_cfg(out_dir, token="s3cret-token"))
        async with app.test_app():
            browser = app.test_client()
            r = await browser.get("/review?token=s3cret-token&keep=this")
            assert r.status_code == 303 and r.headers["location"] == "/review?keep=this"
            assert "token" not in r.headers["location"] and r.headers["cache-control"] == "no-store"
            assert "fs_token=s3cret-token" in r.headers["set-cookie"], "the login moves into the cookie on this same response"
            # a person who already has the cookie and opens the old link again is also tidied
            again = await app.test_client().get("/?token=s3cret-token", headers={"Cookie": "fs_token=s3cret-token"})
            assert again.status_code == 303 and "set-cookie" not in again.headers

            # nothing else about the token changes
            assert (await app.test_client().get("/?token=wrong")).status_code == 401
            assert (await app.test_client().get("/api/takes?token=s3cret-token")).status_code == 200      # scripts keep working
            assert (await app.test_client().get("/static/app.css", headers={"Cookie": "fs_token=s3cret-token"})).status_code == 200
            assert (await app.test_client().get("/healthz")).status_code == 200

    run(main())


def test_the_redirect_cannot_be_turned_into_a_jump_to_another_site():
    from freeform_studio.app import address_without_token as clean
    # the web framework already merges leading slashes today; this guard keeps it safe even if that ever changes
    for hostile in ("//evil.example/", "///evil.example/x", "////", "//evil.example//a"):
        out = clean(hostile, [("token", "t")])
        assert out.startswith("/") and not out.startswith("//"), (hostile, out)
    assert clean("/review/t1", [("token", "t"), ("a", "1"), ("a", "2"), ("b", "x y")]) == "/review/t1?a=1&a=2&b=x+y"
    assert clean("/", [("token", "t")]) == "/"
