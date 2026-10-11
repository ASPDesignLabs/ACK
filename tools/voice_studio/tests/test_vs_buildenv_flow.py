# SPDX-License-Identifier: GPL-3.0-or-later
"""Setting up one set of programs from a terminal (core/buildenv_flow.py): what it says, what it asks, what it saves and when it refuses.

The computer and the network are the builder tests' stand-ins (tests/vs_env_helpers.py), so a whole build runs here: the flow is the real code.
"""
import dataclasses
import itertools
import re
import shutil
from pathlib import Path

import pytest

from vs_env_helpers import LOCK, NATIVE_OVER, make_rig
from vs_fakes import ALL_PACKAGES, ALL_TOOLS, SMI_6G
from voice_studio import buildenv
from voice_studio.core import buildenv_flow as bf
from voice_studio.core import envbuild as eb
from voice_studio.core.consent import load_consent
from voice_studio.core.system import CommandResult
from voice_studio.core.text import load_catalog

CAT = load_catalog("en")


class FakeIO:
    def __init__(self, answers=("yes",), interactive=True):
        self.interactive, self.answers, self.lines, self.prompts = interactive, list(answers), [], []

    def say(self, text):
        self.lines.append(text)

    def ask(self, prompt):
        self.prompts.append(prompt)
        return self.answers.pop(0) if self.answers else None

    @property
    def text(self):
        return "\n".join(self.lines)


def ticking(step=1.0):
    counter = itertools.count()
    return lambda: next(counter) * step


def go(rig, opts=bf.BuildOptions(env_id="demo"), io=None, clock=None):
    io = io or FakeIO()
    seams = {"read_lock": rig.ctx.read_lock, "read_native": rig.ctx.read_native, "fetcher": rig.ctx.fetcher}
    code = bf.run_build_env(opts, rig.system, rig.ctx.home, [rig.spec], CAT, io, rig.doors.networked, clock or ticking(), rig.registry, seams)
    return code, io


@pytest.fixture
def rig(tmp_path):
    return make_rig(tmp_path, spec_over=NATIVE_OVER)


def consent_of(rig):
    return load_consent(Path(rig.ctx.home.consent_file))


# ---------------------------------------------------------------- the options

def test_options_are_read_exactly_and_the_first_thing_not_understood_is_named():
    assert bf.parse_build_options([]) == (bf.BuildOptions(), "")
    assert bf.parse_build_options(["studio"])[0] == bf.BuildOptions(env_id="studio")
    assert bf.parse_build_options(["--check"])[0] == bf.BuildOptions(check=True)
    assert bf.parse_build_options(["--yes", "-v", "training"])[0] == bf.BuildOptions(env_id="training", yes=True, verbose=True)
    assert bf.parse_build_options(["-y"])[0].yes and bf.parse_build_options(["--verbose"])[0].verbose
    for bad, named in ((["--dry-run"], "--dry-run"), (["a", "b"], "b"), (["--check", "--nonsense", "--yes"], "--nonsense"), (["-x"], "-x"), (["--"], "--")):
        assert bf.parse_build_options(bad) == (None, named)


def test_a_bad_option_is_said_plainly_and_nothing_is_done():
    io = FakeIO()
    assert bf.refuse_build_option("--dry-run", CAT, io) == bf.EXIT_NOTHING_DONE and "--dry-run is not something this command knows" in io.text


# ---------------------------------------------------------------- a whole build

def shape(lines, rig):
    """The lines with the folder and the seconds taken replaced, so the whole run can be compared at once."""
    return [re.sub(r"\d+ s\b", "# s", l.replace(rig.env_dir, "<folder>")) for l in lines]


def test_a_yes_builds_the_programs_in_order_and_says_how_long_each_step_took(rig):
    code, io = go(rig)
    assert code == bf.EXIT_OK and rig.record()["state"] == "ready"
    assert io.prompts == ["Download and set it up now? Type yes to go on. "]
    assert shape(io.lines, rig) == [
        "ACK Voice Studio: setting up one set of programs",
        "The programs that train a voice on this computer.",
        "Looking at what is already here. Nothing is changed at this step.",
        "Now: Not set up yet.",
        "It will be set up in <folder>. Nothing outside that folder is changed.",
        "It needs about 1.0 KB of free space while it works. 537 GB is free here.",
        "The programs come from the package site (pypi.org, files.pythonhosted.org) and nowhere else.",
        "Setting up. It can take several minutes. Press Ctrl+C to stop; run the same command again to carry on from where it stopped.",
        "  Checking there is enough space ...", "  Checking there is enough space: done in # s",
        "  Creating a separate space for the programs ...", "  Creating a separate space for the programs: done in # s",
        "  Installing the programs this part needs ...", "  Installing the programs this part needs: done in # s",
        "  Building the part made for this computer ...", "  Building the part made for this computer: done in # s",
        "  Writing the helper that starts it ...", "  Writing the helper that starts it: done in # s",
        "  Checking it works ...", "  Checking it works: done in # s",
        "Ready, after # s.",
        "The programs are in <folder>.",
    ]
    assert rig.doors.fetches == [] and len(rig.doors.pip_runs) == 1


def test_the_yes_is_saved_for_exactly_this_set_of_programs_and_nothing_else(rig):
    assert consent_of(rig) is None
    go(rig)
    record = consent_of(rig)
    assert record is not None and record.covers_id("pip:demo") and not record.covers_id("pip:training") and len(record.entries) == 1


def test_a_second_run_finds_it_ready_asks_nothing_and_touches_no_network(rig):
    go(rig)
    pip_before = len(rig.doors.pip_runs)
    code, io = go(rig)
    assert code == bf.EXIT_OK and io.prompts == [] and "Nothing needs doing. It is in %s." % rig.env_dir in io.lines
    assert len(rig.doors.pip_runs) == pip_before and "Now: Ready." in io.lines


def test_yes_on_the_command_line_means_no_question(rig):
    code, io = go(rig, bf.BuildOptions(env_id="demo", yes=True), FakeIO(answers=[]))
    assert code == bf.EXIT_OK and io.prompts == []


@pytest.mark.parametrize("answer", ["y", "Y", "yes", "  YES  "])
def test_any_ordinary_way_of_saying_yes_goes_on(rig, answer):
    assert go(rig, io=FakeIO(answers=[answer]))[0] == bf.EXIT_OK


@pytest.mark.parametrize("answer", ["n", "no", "", "maybe", "yess", "yes please"])
def test_anything_else_is_a_no_and_changes_nothing(rig, answer):
    code, io = go(rig, io=FakeIO(answers=[answer]))
    assert code == bf.EXIT_NOTHING_DONE and "Nothing was done." in io.lines
    assert consent_of(rig) is None and not Path(rig.ctx.home.environments).exists() and rig.doors.pip_runs == []


def test_with_nobody_to_ask_and_no_yes_nothing_is_done_and_it_says_how_to_go_on(rig):
    code, io = go(rig, io=FakeIO(interactive=False))
    assert code == bf.EXIT_NOTHING_DONE and io.prompts == [] and any("add --yes once you have read the above" in l for l in io.lines)
    assert consent_of(rig) is None and rig.doors.pip_runs == []
    code, io = go(rig, io=FakeIO(answers=[]))                               # a terminal that closes the input
    assert code == bf.EXIT_NOTHING_DONE and consent_of(rig) is None


# ---------------------------------------------------------------- only looking

def test_check_only_looks_and_says_it_is_not_ready(rig):
    code, io = go(rig, bf.BuildOptions(env_id="demo", check=True))
    assert code == bf.EXIT_PROBLEM and io.prompts == [] and "Now: Not set up yet." in io.lines and any("without --check" in l for l in io.lines)
    assert consent_of(rig) is None and not Path(rig.ctx.home.environments).exists() and rig.doors.pip_runs == []


def test_check_on_a_ready_environment_is_a_plain_yes(rig):
    go(rig)
    assert go(rig, bf.BuildOptions(env_id="demo", check=True))[0] == bf.EXIT_OK


def test_a_half_built_environment_is_found_and_carried_on_from_where_it_stopped(rig):
    rig.system.fail_cython = CommandResult(1, "", "stopped\n")
    assert go(rig)[0] == bf.EXIT_PROBLEM
    rig.system.fail_cython = None
    code, io = go(rig, bf.BuildOptions(env_id="demo", check=True))
    assert code == bf.EXIT_PROBLEM and "Now: The last attempt did not finish." in io.lines
    code, io = go(rig)
    assert code == bf.EXIT_OK
    kept = [l for l in io.lines if l.endswith(": already done")]
    assert kept == ["  Creating a separate space for the programs: already done", "  Installing the programs this part needs: already done"]


# ---------------------------------------------------------------- when it cannot go on

@pytest.mark.parametrize("missing", [["python3-dev"], ["python3-venv"], ["build-essential"], ["python3-venv", "python3-dev"]])
def test_a_missing_system_program_stops_before_anything_else_names_it_and_points_at_the_first_step(tmp_path, missing):
    """(the venv one is found by trying it, the compiler by looking for it, the headers by asking the package list: the fake computer is told each way)"""
    system_kw = {"installed": [p for p in ALL_PACKAGES if p not in missing]}
    if "python3-venv" in missing:
        system_kw["failing_probes"] = ["ensurepip"]
    if "build-essential" in missing:
        system_kw["tools"] = {n: path for n, path in ALL_TOOLS.items() if n not in ("gcc", "g++", "make")}
    rig = make_rig(tmp_path, spec_over=NATIVE_OVER, system_kw=system_kw)
    code, io = go(rig)
    said = "Some programs this computer needs are missing: %s. Run the first setup step again (setup.sh), then come back to this." % ", ".join(missing)
    assert code == bf.EXIT_PROBLEM and said in io.lines and io.prompts == [] and rig.doors.pip_runs == []
    assert not Path(rig.ctx.home.environments).exists() and consent_of(rig) is None


@pytest.mark.parametrize("missing", [["python3-gi"], ["gir1.2-gtk-4.0"], ["git"], ["ffmpeg"], ["python3-gi", "gir1.2-gtk-4.0"]])
def test_a_missing_library_for_the_window_or_for_recording_does_not_stop_building_programs(tmp_path, missing):
    rig = make_rig(tmp_path, spec_over=NATIVE_OVER, system_kw={"installed": [p for p in ALL_PACKAGES if p not in missing]})
    assert go(rig)[0] == bf.EXIT_OK


def test_a_set_that_cannot_be_built_yet_says_so_in_three_parts_and_asks_nothing(tmp_path):
    rig = make_rig(tmp_path, spec_over=NATIVE_OVER)
    rig.spec = dataclasses.replace(rig.spec, lock_sha256=None)
    code, io = go(rig)
    parts = (CAT.t("env.error.not_pinned.what"), CAT.t("env.error.not_pinned.changed"), CAT.t("env.error.not_pinned.next"))
    assert code == bf.EXIT_PROBLEM and io.prompts == [] and "Now: Cannot be set up yet." in io.lines
    assert all("  " + p in io.lines for p in parts) and "  Technical detail: lock_unpinned" in io.lines
    assert consent_of(rig) is None and rig.doors.pip_runs == []


def test_an_unknown_name_lists_the_ones_there_are(rig):
    code, io = go(rig, bf.BuildOptions(env_id="nonsense"))
    assert code == bf.EXIT_NOTHING_DONE and "There is no set of programs called nonsense. The ones this tool can set up are: demo." in io.lines


def test_a_failed_install_says_what_happened_what_was_kept_and_what_to_do_and_shows_the_end_of_the_output(rig):
    rig.doors.pip_fail["lock"] = 1
    code, io = go(rig)
    parts = (CAT.t("env.error.pip_failed.what"), CAT.t("env.error.pip_failed.changed"), CAT.t("env.error.pip_failed.next"))
    assert code == bf.EXIT_PROBLEM and all("  " + p in io.lines for p in parts)
    assert any(l.startswith("It did not finish, after ") for l in io.lines) and "  The last lines it printed:" in io.lines
    assert any("ERROR: No matching distribution" in l for l in io.lines)
    assert "  Everything it printed is saved in %s/build.log." % rig.env_dir in io.lines
    assert consent_of(rig) is not None, "the yes was given, and stays given: running again does not need it to be repeated for the record"


def test_an_error_with_a_technical_detail_shows_it_last_and_one_without_shows_none(rig):
    rig.system.fail_cython = CommandResult(1, "", "gcc: error\n")
    code, io = go(rig)
    assert "  Technical detail: exit 1" in io.lines and io.lines.index("  Technical detail: exit 1") < io.lines.index("  The last lines it printed:")


def test_nvidia_libraries_are_named_only_when_the_lock_holds_them(tmp_path):
    plain = go(make_rig(tmp_path / "a", spec_over=NATIVE_OVER), io=FakeIO(answers=["no"]))[1]
    assert not any("Nvidia" in l for l in plain.lines)
    lock = LOCK + b"nvidia-cublas==13.1.1.3 --hash=sha256:" + b"a" * 64 + b"\n"
    with_nvidia = go(make_rig(tmp_path / "b", spec_over=NATIVE_OVER, lock=lock), io=FakeIO(answers=["no"]))[1]
    assert "It includes Nvidia's libraries for the graphics card, which come under Nvidia's own licence." in with_nvidia.lines


def test_the_nvidia_sentence_comes_before_the_question(tmp_path):
    lock = LOCK + b"nvidia-cublas==13.1.1.3 --hash=sha256:" + b"a" * 64 + b"\n"
    io = FakeIO(answers=["no"])
    go(make_rig(tmp_path, spec_over=NATIVE_OVER, lock=lock), io=io)
    assert io.prompts and any("Nvidia" in l for l in io.lines)


# ---------------------------------------------------------------- what it prints while it works

def test_a_quiet_step_gives_a_sign_of_life_now_and_then_and_not_every_line(rig):
    rig.doors.pip_lines = ["Collecting package-%d" % n for n in range(12)]
    code, io = go(rig, clock=ticking(8.0))
    signs = [l for l in io.lines if l.strip().startswith("still working:")]
    assert code == bf.EXIT_OK and 1 <= len(signs) < 12 and all(len(l) < 130 for l in signs)
    assert not any(l.strip() == "Collecting package-1" for l in io.lines)


def test_verbose_prints_every_line_the_installer_printed(rig):
    rig.doors.pip_lines = ["Collecting package-%d" % n for n in range(5)]
    code, io = go(rig, bf.BuildOptions(env_id="demo", verbose=True))
    assert code == bf.EXIT_OK and [l for l in io.lines if l.strip().startswith("Collecting")] == ["    Collecting package-%d" % n for n in range(5)]


def test_the_time_a_step_took_is_from_its_own_start_and_reads_in_minutes_when_long(rig):
    code, io = go(rig, clock=ticking(70.0))
    assert code == bf.EXIT_OK and any(": done in 1 min 10 s" in l for l in io.lines)


@pytest.mark.parametrize("seconds, words", [(0, "0 s"), (0.4, "0 s"), (59.4, "59 s"), (59.6, "1 min 0 s"), (60, "1 min 0 s"), (125, "2 min 5 s"), (3725, "62 min 5 s"), (-3, "0 s")])
def test_how_long_is_said_in_plain_units(seconds, words):
    assert bf.duration_text(CAT, seconds) == words


def test_a_computer_with_no_usable_graphics_card_names_the_checks_it_could_not_do(tmp_path):
    from vs_fakes import SMI_DRIVER_DOWN
    rig = make_rig(tmp_path, spec_over=NATIVE_OVER, system_kw={"smi": CommandResult(9, SMI_DRIVER_DOWN)})
    code, io = go(rig)
    assert code == bf.EXIT_OK and io.lines[-1] == "Not tried, because this computer has no graphics card the training can use: card."
    assert go(make_rig(tmp_path / "b", spec_over=NATIVE_OVER))[1].lines[-1].startswith("The programs are in ")


# ---------------------------------------------------------------- the command itself

def test_the_command_refuses_an_unknown_option_without_touching_anything(capsys, monkeypatch):
    monkeypatch.setattr(bf, "run_build_env", lambda *a, **k: pytest.fail("must not run"))
    assert buildenv.main(["--dry-run"]) == bf.EXIT_NOTHING_DONE
    assert "--dry-run is not something this command knows" in capsys.readouterr().out


def test_stopping_with_ctrl_c_while_it_works_keeps_what_was_done_and_the_same_command_carries_on(rig):
    original = rig.doors.networked

    def stopped(*args, **kwargs):
        raise KeyboardInterrupt

    rig.doors.networked = stopped
    code, io = go(rig)
    assert code == bf.EXIT_PROBLEM and io.lines[-1] == "Stopped. Run the same command again to carry on from where it stopped."
    assert rig.record()["state"] == "building" and "venv" in rig.record()["steps"] and "pip_lock" not in rig.record()["steps"]
    rig.doors.networked = original
    code, io = go(rig)
    assert code == bf.EXIT_OK and "  Creating a separate space for the programs: already done" in io.lines


def test_stopping_with_ctrl_c_at_the_question_does_nothing_at_all(rig):
    class Interrupted(FakeIO):
        def ask(self, prompt):
            raise KeyboardInterrupt

    code, io = go(rig, io=Interrupted())
    assert code == bf.EXIT_PROBLEM and io.lines[-1].startswith("Stopped.") and consent_of(rig) is None and rig.doors.pip_runs == []


def test_the_command_passes_the_real_pieces_to_the_flow(monkeypatch):
    seen = {}

    def fake_flow(opts, system, home, specs, cat, io, networked, clock, registry):
        seen.update(opts=opts, home=home.home, ids=[s.id for s in specs], networked=networked, clock=clock, registry_ids=[i.id for i in registry.items])
        return 0

    monkeypatch.setattr(buildenv, "run_build_env", fake_flow)
    assert buildenv.main(["--check"]) == 0
    from voice_studio.core import fetch
    import time
    assert seen["opts"] == bf.BuildOptions(check=True) and seen["ids"] == ["training", "studio"] and seen["networked"] is fetch.run_networked and seen["clock"] is time.monotonic
    assert "speech-model-small-en" in seen["registry_ids"] and seen["home"] == str(Path("~").expanduser())


# ---------------------------------------------------------------- the progress lines, one at a time

def scripted(times):
    values = iter(times)
    return lambda: next(values)


def progress(clock_times, verbose=False):
    io = FakeIO()
    return bf._Progress(CAT, io, scripted(clock_times), verbose), io


def ev(kind, step="pip_lock", text=""):
    return eb.Event(kind, step, text)


def test_a_sign_of_life_comes_exactly_when_twenty_seconds_have_passed_and_not_before():
    p, io = progress([0.0, 19.999, 20.0, 39.9, 40.0])
    p(ev("start"))
    p(ev("line", text="a")); assert io.lines[1:] == []
    p(ev("line", text="b")); assert io.lines[1:] == ["    still working: b"]
    p(ev("line", text="c")); assert len(io.lines) == 2, "the wait starts again after a sign"
    p(ev("line", text="d")); assert io.lines[-1] == "    still working: d"


def test_a_step_starting_restarts_the_wait_for_a_sign():
    p, io = progress([0.0, 19.0, 21.0, 25.0])
    p(ev("start", "venv")); p(ev("start", "pip_lock"))
    p(ev("line", text="late")); p(ev("line", text="later"))
    assert [l for l in io.lines if "still working" in l] == [], "21 s after the first start, but only 2 s after this step began"


def test_a_long_line_is_cut_for_the_sign_and_a_blank_one_is_never_said():
    p, io = progress([0.0, 30.0, 61.0])
    p(ev("start")); p(ev("line", text="x" * 200)); p(ev("line", text="   "))
    assert io.lines[1] == "    still working: " + "x" * 90 and len(io.lines) == 2
    v, vio = progress([0.0, 1.0, 2.0], verbose=True)
    v(ev("start")); v(ev("line", text="   ")); v(ev("line", text="shown  "))
    assert vio.lines[1:] == ["    shown"]


def test_each_step_is_timed_from_its_own_start_not_from_an_earlier_one():
    p, io = progress([0.0, 10.0, 15.0])
    p(ev("start", "venv")); p(ev("start", "pip_lock")); p(ev("done", "pip_lock"))
    assert io.lines[-1] == "  Installing the programs this part needs: done in 5 s"


def test_a_step_the_tool_has_no_words_for_is_named_as_it_is_and_a_skipped_probe_says_nothing_yet():
    p, io = progress([0.0, 1.0, 2.0])
    p(ev("start", "mystery")); p(ev("skipped", "card")); p(ev("kept", "venv"))
    assert io.lines == ["  mystery ...", "  Creating a separate space for the programs: already done"]


# ---------------------------------------------------------------- the rest of the choices

class TimedIO(FakeIO):
    """Every line said costs ten seconds on the clock this shares, so how long the whole build took is worked out from how much was said."""
    def __init__(self, clock_box, **kw):
        super().__init__(**kw)
        self.box = clock_box

    def say(self, text):
        super().say(text)
        self.box[0] += 10.0


def test_the_whole_build_is_timed_from_when_it_began_to_when_it_ended(rig):
    box = [0.0]
    code, io = go(rig, io=TimedIO(box), clock=lambda: box[0])
    working = io.lines.index("Setting up. It can take several minutes. Press Ctrl+C to stop; run the same command again to carry on from where it stopped.")
    said_while_building = len(io.lines) - working - 1 - 2                      # minus the "Ready" and "The programs are in" lines said after
    assert code == bf.EXIT_OK and io.lines[-2] == "Ready, after %s." % bf.duration_text(CAT, said_while_building * 10)


def test_a_failure_with_nothing_to_show_has_no_empty_list_of_last_lines(tmp_path):
    rig = make_rig(tmp_path, spec_over=NATIVE_OVER, system_kw={"free": 1000})
    code, io = go(rig)
    assert code == bf.EXIT_PROBLEM and "  The last lines it printed:" not in io.lines
    assert any(l.startswith("  Everything it printed is saved in") for l in io.lines)


def test_the_three_parts_of_an_error_come_in_the_order_what_happened_what_changed_what_to_do(rig):
    rig.doors.pip_fail["lock"] = 1
    lines = go(rig)[1].lines
    at = [lines.index("  " + CAT.t("env.error.pip_failed." + part)) for part in ("what", "changed", "next")]
    assert at == sorted(at) and at[1] == at[0] + 1 and at[2] == at[1] + 1


def test_when_the_free_space_cannot_be_read_it_says_so_in_a_sentence_that_reads_properly(rig):
    rig.system.disk_free = lambda path: None
    code, io = go(rig, io=FakeIO(answers=["no"]))
    assert "It needs about 1.0 KB of free space while it works. How much is free here could not be read." in io.lines


def test_a_package_whose_name_only_starts_like_nvidia_is_not_one_of_theirs(tmp_path):
    lock = LOCK + b"nvidiafoo==1.0 --hash=sha256:" + b"a" * 64 + b"\n"
    io = FakeIO(answers=["no"])
    go(make_rig(tmp_path, spec_over=NATIVE_OVER, lock=lock), io=io)
    assert not any("Nvidia" in l for l in io.lines)


@pytest.mark.parametrize("smi, tried", [(CommandResult(0, SMI_6G), True), (CommandResult(0, "NVIDIA GeForce RTX 4060, [N/A], 560.35.03\n"), True), (None, False)])
def test_a_small_or_unmeasured_card_is_still_a_card_to_try_and_no_card_at_all_is_not(tmp_path, smi, tried):
    rig = make_rig(tmp_path, spec_over=NATIVE_OVER, system_kw={"smi": smi})
    code, io = go(rig)
    assert code == bf.EXIT_OK and (not any(l.startswith("Not tried") for l in io.lines)) is tried


def test_a_yes_that_cannot_be_saved_downloads_nothing_and_says_why(rig):
    Path(rig.ctx.home.root).mkdir(parents=True)
    Path(rig.ctx.home.state).write_text("a file where a folder is needed")
    code, io = go(rig)
    assert code == bf.EXIT_PROBLEM and "Your yes could not be saved, so nothing was downloaded." in io.lines
    assert any(l.startswith("  Technical detail: ") for l in io.lines) and rig.doors.pip_runs == [] and not Path(rig.ctx.home.environments).exists()


def test_a_sign_of_life_names_the_last_thing_in_words_never_the_installers_moving_bar():
    p, io = progress([0.0, 5.0, 10.0, 25.0, 30.0, 50.0])
    p(ev("start"))
    p(ev("line", text="Downloading torch-2.14.1-cp310.whl (555 MB)"))
    p(ev("line", text="     ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 34.1/34.1 MB 10.4 MB/s eta 0:00:00"))
    p(ev("line", text="     ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 34.1/34.1 MB 10.4 MB/s eta 0:00:00"))
    p(ev("line", text="Successfully installed Cython-3.3.0"))
    assert [l for l in io.lines if "still working" in l] == ["    still working: Downloading torch-2.14.1-cp310.whl (555 MB)"]
    p(ev("line", text="   eta 0:00:03"))
    assert io.lines[-1] == "    still working: Successfully installed Cython-3.3.0"


def test_when_only_a_moving_bar_has_been_seen_the_sign_just_says_it_is_still_working():
    p, io = progress([0.0, 30.0])
    p(ev("start")); p(ev("line", text="━━━━━━━━ 1.0/9.0 MB eta 0:01:00"))
    assert io.lines[1:] == ["    still working"]


@pytest.mark.parametrize("line, is_bar", [("━━━━ 3/9 MB", True), ("╸━━ 3/9 MB", True), ("downloading, eta 0:00:07", True), ("eta 1:02:03", True),
                                           ("Downloading torch (555 MB)", False), ("Collecting numpy==2.2.6", False), ("Installing collected packages: eta", False),
                                           ("meta 10:20 is a name", False)])
def test_which_lines_are_the_installers_moving_bar(line, is_bar):
    assert bool(bf.PROGRESS_BAR.search(line)) is is_bar


# ---------------------------------------------------------------- finishing only the small local steps

def test_when_only_a_small_step_is_left_it_says_so_asks_a_different_question_and_downloads_nothing(rig):
    go(rig)
    pip_before, consent_before = len(rig.doors.pip_runs), Path(rig.ctx.home.consent_file).read_bytes()
    Path(rig.paths.launcher).write_text("# an older helper\n")                  # the helper's workarounds changed since it was written
    code, io = go(rig)
    assert code == bf.EXIT_OK and io.prompts == ["Finish it now? Type yes to go on. "]
    assert "Now: Needs to be finished or repaired." in io.lines
    assert "Only small steps on this computer are left: Writing the helper that starts it. Nothing will be downloaded." in io.lines
    assert not any("package site" in l or "free space" in l or "Nvidia" in l for l in io.lines)
    assert len(rig.doors.pip_runs) == pip_before and Path(rig.ctx.home.consent_file).read_bytes() == consent_before, "no network command, no new agreement"
    assert Path(rig.paths.launcher).read_text() == eb.launcher_text(rig.spec)
    assert go(rig)[1].lines.count("Nothing needs doing. It is in %s." % rig.env_dir) == 1


def test_several_small_steps_are_listed_in_the_order_they_will_run(rig):
    go(rig)
    Path(rig.paths.launcher).write_text("# older\n")
    next(Path(rig.paths.venv).glob("lib/python3.12/site-packages/demo/pkg/inner/core*.so")).unlink()
    code, io = go(rig)
    assert code == bf.EXIT_OK
    assert "Only small steps on this computer are left: Building the part made for this computer, Writing the helper that starts it. Nothing will be downloaded." in io.lines


def test_a_build_that_is_waiting_only_for_its_last_check_says_that(rig):
    go(rig)
    record = rig.record()
    record["state"] = "failed"
    Path(rig.paths.record).write_text(__import__("json").dumps(record))
    code, io = go(rig)
    assert code == bf.EXIT_OK and "Only small steps on this computer are left: Checking it works. Nothing will be downloaded." in io.lines


def test_a_missing_download_step_still_asks_the_download_question_with_everything_that_goes_with_it(rig):
    rig.doors.pip_fail["lock"] = 1
    go(rig)
    rig.doors.pip_fail.clear()
    code, io = go(rig)
    assert code == bf.EXIT_OK and io.prompts == ["Download and set it up now? Type yes to go on. "]
    assert any("package site" in l for l in io.lines) and not any("Only small steps" in l for l in io.lines)


def test_the_small_steps_question_can_be_declined_and_then_nothing_changes(rig):
    go(rig)
    Path(rig.paths.launcher).write_text("# older\n")
    code, io = go(rig, io=FakeIO(answers=["no"]))
    assert code == bf.EXIT_NOTHING_DONE and Path(rig.paths.launcher).read_text() == "# older\n" and "Nothing was done." in io.lines


def test_the_small_steps_need_no_agreement_so_none_is_made(rig):
    go(rig)
    Path(rig.ctx.home.consent_file).unlink()
    Path(rig.paths.launcher).write_text("# older\n")
    assert go(rig)[0] == bf.EXIT_OK and consent_of(rig) is None


def test_the_steps_are_listed_in_the_order_the_builder_reports_them_not_alphabetically(rig, monkeypatch):
    go(rig)
    real = eb.inspect
    monkeypatch.setattr(bf.envbuild, "inspect", lambda spec, ctx: dataclasses.replace(real(spec, ctx), state="needs_work", stale=("wrapper", "native_build")))
    code, io = go(rig, io=FakeIO(answers=["no"]))
    assert "Only small steps on this computer are left: Writing the helper that starts it, Building the part made for this computer. Nothing will be downloaded." in io.lines


@pytest.mark.parametrize("what", ["pip_source", "source_unpack"])
def test_a_missing_installed_source_or_unpacked_source_is_a_download_step_too(tmp_path, what):
    rig = make_rig(tmp_path)                                                  # the stand-in environment that has a source archive
    assert go(rig)[0] == bf.EXIT_OK
    if what == "pip_source":
        rig.system.dists(rig.paths.venv).pop("demo-dist")
    else:
        shutil.rmtree(rig.paths.source)
    code, io = go(rig)
    assert code == bf.EXIT_OK and io.prompts == ["Download and set it up now? Type yes to go on. "], what
    assert not any("Only small steps" in l for l in io.lines)
