# SPDX-License-Identifier: GPL-3.0-or-later
"""The rest of the guided setup (plan decision D3, task VS-7.1): after the system packages, the two sets of programs and the window, in that order. Held to: each step is the builder's own
terminal front (asked, refusable), a no to one step does not stop the next, a failure stops everything after it and the window is never opened on programs that are not there, the window is
started only after its own check says it can start, nobody to ask means nothing more is done, and `--no-window` opens nothing."""
import pytest

from vs_fakes import FakeSystem
from vs_startvoice_helpers import Terminal, leaked_keys
from voice_studio import __main__ as entry
from voice_studio.core import guided_flow as gf
from voice_studio.core.paths import DataHome
from voice_studio.core.setup_flow import Options
from voice_studio.core.system import CommandResult
from voice_studio.core.text import load_catalog

CAT = load_catalog("en")
TOOLS = "/home/user/ack-tools/tools"
WINDOW = ["env", "PYTHONPATH=" + TOOLS, "/usr/bin/python3", "-m", "voice_studio.window"]


class Builds:
    """Stands in for the environment builder's terminal front: remembers what it was asked for and answers from a script (0 ready, 1 problem, 2 nothing done)."""

    def __init__(self, codes=(0, 0), say=None):
        self.codes, self.calls, self.say = list(codes), [], say or {}

    def __call__(self, opts, system, home, specs, cat, io, networked, clock, registry):
        self.calls.append((opts.env_id, opts.yes))
        io.say("[%s builder]" % opts.env_id)
        return self.codes.pop(0)


class Computer(FakeSystem):
    """A computer whose window check answers as scripted: (exit code, what it printed), or None when it could not be run."""

    def __init__(self, check=(0, "ACK Voice Studio: can the window start here?\n  It can.\n"), **kwargs):
        super().__init__(**kwargs)
        self.check = check

    def run(self, argv, timeout=15.0, cwd=None, env=None):
        if argv[:1] == ["env"]:
            self.ran.append(tuple(argv))
            return None if self.check is None else CommandResult(self.check[0], self.check[1])
        return super().run(argv, timeout, cwd, env)


def go(opts=Options(), *, builds=None, system=None, io=None, interactive=True):
    builds = builds or Builds()
    system = system or Computer()
    io = io or Terminal([], interactive)
    code = gf.run_guided(opts, system, DataHome("/home/user"), (), CAT, io, None, lambda: 0.0, None, TOOLS, build=builds)
    assert leaked_keys(io.text) == [], "a catalog key was printed instead of words"
    return code, io, builds, system


def test_every_step_runs_in_order_and_the_window_opens_last():
    code, io, builds, system = go()
    assert code == 0 and builds.calls == [("studio", False), ("training", False)]
    assert system.started == [tuple(WINDOW)]
    assert io.text.index("[studio builder]") < io.text.index("[training builder]") < io.text.index("Opening the window.")


def test_each_step_says_what_it_is_before_the_builders_own_question():
    _code, io, _builds, _system = go()
    assert "Next: the programs that listen to your recordings and make training sets. They are small." in io.lines
    assert io.lines.index("Next: the programs that listen to your recordings and make training sets. They are small.") < io.lines.index("[studio builder]")
    training = [l for l in io.lines if l.startswith("Next: the programs that train the voice.")]
    assert len(training) == 1 and "You can say no now and do this later" in training[0] and io.lines.index(training[0]) < io.lines.index("[training builder]")


def test_yes_on_the_command_line_is_passed_to_each_step_and_nothing_else_is_assumed():
    _code, _io, builds, _system = go(Options(yes=True), interactive=False)
    assert builds.calls == [("studio", True), ("training", True)]


def test_the_window_is_checked_with_the_system_python_before_it_is_started():
    _code, _io, _builds, system = go()
    assert system.ran[0] == tuple(WINDOW + ["--check"]) and system.started == [tuple(WINDOW)]


def test_after_opening_it_says_how_to_open_it_again_and_how_to_have_it_in_the_menu():
    _code, io, _builds, _system = go()
    assert "To open it again later, run: PYTHONPATH=%s /usr/bin/python3 -m voice_studio.window" % TOOLS in io.lines
    assert "To have it in your menu, run: PYTHONPATH=%s /usr/bin/python3 -m voice_studio.window --install-launcher" % TOOLS in io.lines


def test_a_no_to_one_step_is_skipped_with_the_command_to_do_it_later_and_the_next_step_still_runs():
    code, io, builds, system = go(builds=Builds([2, 0]))
    assert code == 0 and builds.calls == [("studio", False), ("training", False)] and system.started == [tuple(WINDOW)]
    assert "Skipped. To do this later, run: python3 -m voice_studio.buildenv studio" in io.lines
    assert not any("buildenv training" in l for l in io.lines)


def test_a_no_to_the_large_step_alone_still_opens_the_window():
    code, io, builds, system = go(builds=Builds([0, 2]))
    assert code == 0 and system.started == [tuple(WINDOW)] and "Skipped. To do this later, run: python3 -m voice_studio.buildenv training" in io.lines


def test_a_no_to_both_still_opens_the_window():
    code, _io, _builds, system = go(builds=Builds([2, 2]))
    assert code == 0 and system.started == [tuple(WINDOW)]


@pytest.mark.parametrize("failing", [0, 1])
def test_a_step_that_fails_stops_everything_after_it_and_the_window_is_not_opened(failing):
    codes = [0, 0]
    codes[failing] = 1
    code, io, builds, system = go(builds=Builds(codes))
    assert code == 1 and system.started == [] and system.ran == []
    assert len(builds.calls) == failing + 1, "nothing after the step that failed is attempted"
    assert "It stopped at this step, and what was finished is kept. Run the same command again to carry on from here." in io.lines


def test_with_nobody_to_ask_and_no_yes_nothing_more_is_done():
    code, io, builds, system = go(interactive=False)
    assert code == 2 and builds.calls == [] and system.started == [] and system.ran == []
    assert "There is nobody here to ask, so only the first step was done. To go on without being asked, run it again and add --yes." in io.lines


def test_with_a_yes_on_the_line_nobody_needs_to_be_there():
    code, _io, builds, system = go(Options(yes=True), interactive=False)
    assert code == 0 and len(builds.calls) == 2 and system.started == [tuple(WINDOW)]


def test_no_window_sets_the_programs_up_and_opens_nothing_and_says_how_to_open_it_later():
    code, io, builds, system = go(Options(no_window=True))
    assert code == 0 and len(builds.calls) == 2 and system.started == [] and system.ran == []
    assert "The window was not opened. To open it later, run: PYTHONPATH=%s /usr/bin/python3 -m voice_studio.window" % TOOLS in io.lines


def test_a_window_that_cannot_start_here_says_why_in_the_checks_own_words_and_is_not_started():
    said = "ACK Voice Studio: can the window start here?\n  GTK 4 or its Python library is missing.\n  Install them with: sudo apt install python3-gi gir1.2-gtk-4.0\n"
    code, io, _builds, system = go(system=Computer(check=(1, said)))
    assert code == 1 and system.started == []
    assert "  GTK 4 or its Python library is missing." in io.lines and "  Install them with: sudo apt install python3-gi gir1.2-gtk-4.0" in io.lines
    assert "Everything above was set up, but the window cannot open here. The reason is above." in io.lines


def test_a_check_that_could_not_even_run_says_how_to_run_it_by_hand():
    code, io, _builds, system = go(system=Computer(check=None))
    assert code == 1 and system.started == []
    assert "The window could not be started. To see why, run: PYTHONPATH=%s /usr/bin/python3 -m voice_studio.window --check" % TOOLS in io.lines


def test_a_window_that_passes_its_check_but_will_not_start_says_so():
    system = Computer()
    system.cannot_start.add("env")
    code, io, _builds, _system = go(system=system)
    assert code == 1 and "The window could not be started. To see why, run:" in io.text and "Opening the window." not in io.text


def test_the_window_is_not_started_when_its_check_failed_even_if_the_programs_were_all_skipped():
    code, _io, _builds, system = go(builds=Builds([2, 2]), system=Computer(check=(1, "no\n")))
    assert code == 1 and system.started == []


def test_blank_lines_from_the_check_are_not_echoed():
    _code, io, _builds, _system = go(system=Computer(check=(1, "one\n\n   \ntwo\n")))
    assert io.lines[io.lines.index("one") + 1] == "two"


def test_the_step_list_is_the_small_programs_then_the_large():
    assert gf.GUIDED_ENVS == ("studio", "training")
    assert set(gf.INTRO_WORDS) == set(gf.GUIDED_ENVS)


# ---------------------------------------------------------------- the entry point wires it

def test_main_goes_on_to_the_programs_and_the_window_only_after_the_packages_are_ready(monkeypatch):
    seen = {}
    monkeypatch.setattr(entry, "RealSystem", lambda: FakeSystem())
    monkeypatch.setattr(entry, "run_guided", lambda *a, **k: seen.setdefault("guided", a) and 0)
    assert entry.main([]) == 0
    opts, system, home, specs, cat, io, networked, clock, registry, tools = seen["guided"]
    assert opts == Options() and networked is entry.fetch.run_networked and tools == str(entry.jobs.TOOLS_DIR) and any(s.id == "studio" for s in specs) and registry is not None


@pytest.mark.parametrize("args", [["--check"], ["--dry-run"]])
def test_main_with_check_or_dry_run_only_looks_and_never_goes_on(monkeypatch, args):
    monkeypatch.setattr(entry, "RealSystem", lambda: FakeSystem())
    monkeypatch.setattr(entry, "run_guided", lambda *a, **k: pytest.fail("looking must not set anything up"))
    assert entry.main(args) == 0


def test_main_does_not_go_on_when_the_first_step_did_not_finish(monkeypatch):
    system = FakeSystem(installed=[], tools={})
    monkeypatch.setattr(entry, "RealSystem", lambda: system)
    monkeypatch.setattr(entry.sys, "stdin", __import__("io").StringIO(""))
    monkeypatch.setattr(entry, "run_guided", lambda *a, **k: pytest.fail("the packages are not in, so nothing after them may start"))
    assert entry.main([]) != 0


def test_main_passes_no_window_on(monkeypatch):
    seen = {}
    monkeypatch.setattr(entry, "RealSystem", lambda: FakeSystem())
    monkeypatch.setattr(entry, "run_guided", lambda opts, *a, **k: seen.setdefault("opts", opts) and 0)
    entry.main(["--no-window", "--yes"])
    assert seen["opts"] == Options(yes=True, no_window=True)
