# SPDX-License-Identifier: GPL-3.0-or-later
"""Playing a sound file (plan task VS-5.4): which ways are tried and in what order, what counts as a way that failed, and that a path never becomes part of a command it could break."""
import base64
import os

import pytest

from voice_studio.core import playback as pb
from voice_studio.core.system import CommandResult

WSL = "Linux version 5.15.0-microsoft-standard-WSL2"
NATIVE = "Linux version 6.8.0-generic"


class Fake:
    """Answers for the players by name; records every command and its time limit. `installed` is what `which` finds."""

    def __init__(self, installed, version=NATIVE, results=None, windows_path="C:\\Users\\anna\\clip-1.wav"):
        self.installed, self.version, self.results, self.windows_path = tuple(installed), version, dict(results or {}), windows_path
        self.ran = []

    def read_text(self, path):
        return self.version if path == "/proc/version" else None

    def which(self, name):
        return "/usr/bin/" + name if name in self.installed else None

    def run(self, argv, timeout=15.0, cwd=None, env=None):
        name = os.path.basename(argv[0])
        self.ran.append((name, tuple(argv), timeout))
        if name == "wslpath":
            return CommandResult(0, self.windows_path + "\n") if self.windows_path is not None else CommandResult(1)
        return self.results.get(name, CommandResult(0))


def names(fake):
    return [n for n, _a, _t in fake.ran if n != "wslpath"]


# ---------------------------------------------------------------- order

def test_a_native_desktop_tries_the_sound_server_players_before_ffplay_and_aplay_last():
    assert pb.Playback(Fake(())).order() == ("pw-play", "paplay", "ffplay", "aplay")


def test_under_wsl_ffplay_and_paplay_go_first_then_windows_own_player_then_aplay():
    assert pb.Playback(Fake((), WSL)).order() == ("ffplay", "paplay", "windows", "aplay")


def test_the_way_that_worked_goes_first_next_time():
    player = pb.Playback(Fake((), WSL))
    player.worked = "windows"
    assert player.order() == ("windows", "ffplay", "paplay", "aplay")


def test_a_way_that_is_not_installed_is_skipped_without_being_counted_as_failed():
    fake = Fake(("paplay",))
    player = pb.Playback(fake)
    assert player.play("/tmp/a.wav", 1.0) == "paplay" and names(fake) == ["paplay"] and player.tried() == ()


def test_nothing_installed_plays_nothing_and_runs_nothing():
    fake = Fake(())
    player = pb.Playback(fake)
    assert player.play("/tmp/a.wav", 1.0) is None and fake.ran == [] and player.worked is None


# ---------------------------------------------------------------- the commands

def test_each_player_gets_exactly_the_arguments_that_make_it_play_one_file_and_stop():
    fake = Fake(("pw-play", "paplay", "ffplay", "aplay"))
    player = pb.Playback(fake)
    assert player.argv("pw-play", "/tmp/a b.wav") == ("/usr/bin/pw-play", "/tmp/a b.wav")
    assert player.argv("paplay", "/tmp/a.wav") == ("/usr/bin/paplay", "/tmp/a.wav")
    assert player.argv("ffplay", "/tmp/a.wav") == ("/usr/bin/ffplay", "-nodisp", "-autoexit", "-loglevel", "error", "-i", "/tmp/a.wav")
    assert player.argv("aplay", "/tmp/a.wav") == ("/usr/bin/aplay", "-q", "/tmp/a.wav")


def test_a_path_with_spaces_and_symbols_is_one_argument_never_part_of_a_shell_line():
    fake = Fake(("ffplay",))
    pb.Playback(fake).play("/tmp/my voice; rm -rf x/$HOME/clip-1.wav", 1.0)
    assert fake.ran[0][1][-1] == "/tmp/my voice; rm -rf x/$HOME/clip-1.wav" and len(fake.ran[0][1]) == 7


def test_a_player_may_take_the_clips_length_plus_twenty_seconds_and_no_more():
    fake = Fake(("ffplay",))
    pb.Playback(fake).play("/tmp/a.wav", 2.5)
    assert fake.ran[0][2] == pytest.approx(22.5)


# ---------------------------------------------------------------- what counts as a failure

def test_a_nonzero_exit_is_a_failure_and_the_next_way_is_tried():
    fake = Fake(("pw-play", "paplay"), results={"pw-play": CommandResult(1, "", "boom")})
    player = pb.Playback(fake)
    assert player.play("/tmp/a.wav", 1.0) == "paplay" and player.tried() == ("pw-play",)


def test_a_player_that_runs_but_says_it_has_no_audio_device_is_a_failure_even_with_exit_zero():
    for said in ("Could not initialize SDL - No such audio device", "audio open failed", "Connection refused", "pulseaudio: Unable to connect"):
        fake = Fake(("ffplay", "paplay"), WSL, results={"ffplay": CommandResult(0, "", said)})
        player = pb.Playback(fake)
        assert player.play("/tmp/a.wav", 1.0) == "paplay", said


def test_a_player_that_could_not_be_started_or_took_too_long_is_a_failure():
    class Slow(Fake):
        def run(self, argv, timeout=15.0, cwd=None, env=None):
            self.ran.append((os.path.basename(argv[0]), tuple(argv), timeout))
            return None if os.path.basename(argv[0]) == "ffplay" else CommandResult(0)
    fake = Slow(("ffplay", "paplay"), WSL)
    assert pb.Playback(fake).play("/tmp/a.wav", 1.0) == "paplay"


def test_every_way_failing_returns_none_and_lists_them_in_the_order_tried():
    fake = Fake(("pw-play", "paplay", "ffplay", "aplay"), results={n: CommandResult(1) for n in ("pw-play", "paplay", "ffplay", "aplay")})
    player = pb.Playback(fake)
    assert player.play("/tmp/a.wav", 1.0) is None and player.tried() == ("pw-play", "paplay", "ffplay", "aplay")


def test_a_way_that_failed_is_not_tried_again_for_the_next_clips_and_the_one_that_worked_is_used_first():
    fake = Fake(("pw-play", "paplay"), results={"pw-play": CommandResult(1)})
    player = pb.Playback(fake)
    player.play("/tmp/1.wav", 1.0)
    player.play("/tmp/2.wav", 1.0)
    player.play("/tmp/3.wav", 1.0)
    assert names(fake) == ["pw-play", "paplay", "paplay", "paplay"]


# ---------------------------------------------------------------- Windows' own player, under WSL

def decode(argv):
    assert argv[1:5] == ("-NoLogo", "-NoProfile", "-NonInteractive", "-EncodedCommand")
    return base64.b64decode(argv[5]).decode("utf-16-le")


def test_windows_own_player_is_given_the_windows_path_of_the_file_in_one_encoded_command():
    fake = Fake(("powershell.exe", "wslpath"), WSL)
    command = pb.Playback(fake).argv("windows", "/home/anna/listening/clip-1.wav")
    assert command[0] == "/usr/bin/powershell.exe" and decode(command) == "$p = 'C:\\Users\\anna\\clip-1.wav'; (New-Object System.Media.SoundPlayer $p).PlaySync()"
    assert fake.ran[0][1] == ("/usr/bin/wslpath", "-w", "/home/anna/listening/clip-1.wav")


def test_a_network_share_path_is_accepted_because_that_is_what_a_wsl_folder_looks_like_from_windows():
    fake = Fake(("powershell.exe", "wslpath"), WSL, windows_path="\\\\wsl.localhost\\Ubuntu\\home\\anna\\clip-1.wav")
    assert pb.Playback(fake).argv("windows", "/home/anna/clip-1.wav") is not None


@pytest.mark.parametrize("bad", ["C:\\Users\\o'brien\\a.wav", "C:\\a$b\\a.wav", "C:\\a`b\\a.wav", 'C:\\a"b\\a.wav', "C:\\a\nb\\a.wav", "relative\\a.wav", "", "/mnt/c/x.wav"])
def test_a_windows_path_that_could_break_out_of_the_quoted_string_is_never_used(bad):
    fake = Fake(("powershell.exe", "wslpath"), WSL, windows_path=bad)
    assert pb.Playback(fake).argv("windows", "/home/anna/clip-1.wav") is None


def test_windows_own_player_is_not_offered_on_a_native_computer_or_without_its_two_helpers():
    assert pb.Playback(Fake(("powershell.exe", "wslpath"), NATIVE)).argv("windows", "/tmp/a.wav") is None
    assert pb.Playback(Fake(("wslpath",), WSL)).argv("windows", "/tmp/a.wav") is None
    assert pb.Playback(Fake(("powershell.exe",), WSL)).argv("windows", "/tmp/a.wav") is None


def test_when_the_path_cannot_be_converted_windows_own_player_is_skipped_and_the_next_way_tried():
    fake = Fake(("powershell.exe", "wslpath", "aplay"), WSL, windows_path=None)
    assert pb.Playback(fake).play("/tmp/a.wav", 1.0) == "aplay"


def test_under_wsl_when_the_sound_server_cannot_be_reached_windows_own_player_is_the_one_that_plays():
    fake = Fake(("ffplay", "paplay", "powershell.exe", "wslpath"), WSL, results={"ffplay": CommandResult(1), "paplay": CommandResult(1, "", "Connection refused")})
    player = pb.Playback(fake)
    assert player.play("/tmp/a.wav", 1.0) == "windows" and player.tried() == ("ffplay", "paplay")


def test_wsl_is_told_from_native_by_the_kernel_name():
    assert pb.is_wsl(Fake((), WSL)) and not pb.is_wsl(Fake((), NATIVE))
    assert pb.is_wsl(Fake((), "Linux version 4.4.0-19041-Microsoft")) and not pb.is_wsl(Fake((), None))
