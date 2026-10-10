# SPDX-License-Identifier: GPL-3.0-or-later
"""The terminal step (plan task VS-1.4): what it says, what it asks, exactly which commands it runs and which things the person agreed to."""
import pytest

from vs_fakes import ALL_PACKAGES, ALL_TOOLS, FakeSystem
from voice_studio.core import setup_flow as sf
from voice_studio.core.text import load_catalog

CAT = load_catalog("en")
MISSING = ["git", "ffmpeg"]
PROGRAMS = {"git": ["git"], "ffmpeg": ["ffmpeg", "ffprobe"]}      # what each missing package puts on the computer (the preflight checks for the program itself)


def put_on_computer(system, package):
    system.installed.add(package)
    system.tools.update({name: ALL_TOOLS[name] for name in PROGRAMS.get(package, [])})


class FakeIO:
    def __init__(self, answers=("y",), interactive=True):
        self.interactive, self.answers, self.lines, self.prompts = interactive, list(answers), [], []

    def say(self, text):
        self.lines.append(text)

    def ask(self, prompt):
        self.prompts.append(prompt)
        return self.answers.pop(0) if self.answers else None

    @property
    def text(self):
        return "\n".join(self.lines)


class FakeApt:
    """Stands in for sudo apt-get: records each call, and 'installs' the packages into the fake computer when asked to."""
    def __init__(self, system, fail_on=None, installs=True):
        self.system, self.fail_on, self.installs, self.calls = system, fail_on, installs, []

    def __call__(self, consent, argv, ids):
        self.calls.append((consent, list(argv), list(ids)))
        if self.fail_on is not None and len(self.calls) == self.fail_on:
            return 100
        if self.installs and argv[:3] == ["sudo", "apt-get", "install"]:
            for package in argv[4:]:
                put_on_computer(self.system, package)
        return 0


def computer(**overrides):
    base = dict(installed=[p for p in ALL_PACKAGES if p not in MISSING],
                tools={n: path for n, path in ALL_TOOLS.items() if n not in ("git", "ffmpeg", "ffprobe")})
    base.update(overrides)
    return FakeSystem(**base)


def run(opts=sf.Options(), system=None, io=None, apt=None):
    system = system or computer()
    io = io or FakeIO()
    apt = apt or FakeApt(system)
    return sf.run_setup(opts, system, CAT, io, apt), io, apt, system


# ---------------------------------------------------------------- the options

def test_options_are_read_exactly_and_an_unknown_one_is_named():
    assert sf.parse_options([]) == (sf.Options(), "")
    assert sf.parse_options(["--check"])[0] == sf.Options(check=True)
    assert sf.parse_options(["--dry-run"])[0] == sf.Options(dry_run=True)
    assert sf.parse_options(["--yes"])[0] == sf.Options(yes=True)
    assert sf.parse_options(["-y"])[0] == sf.Options(yes=True)
    assert sf.parse_options(["--check", "--yes"])[0] == sf.Options(check=True, yes=True)
    assert sf.parse_options(["--check", "--chek"]) == (None, "--chek")
    assert sf.parse_options(["--YES"]) == (None, "--YES")
    assert sf.parse_options(["yes"]) == (None, "yes")


def test_an_unknown_option_changes_nothing_and_says_which_one():
    io = FakeIO()
    assert sf.refuse_option("--chek", CAT, io) == sf.EXIT_NOTHING_DONE
    assert "--chek" in io.text and "--check" in io.text and "--dry-run" in io.text and "--yes" in io.text


# ---------------------------------------------------------------- the commands

def test_the_commands_are_update_then_install_of_exactly_the_missing_programs():
    report = sf.run_preflight(computer())
    assert sf.apt_commands(report) == [["sudo", "apt-get", "update"], ["sudo", "apt-get", "install", "-y", "git", "ffmpeg"]]


def test_nothing_missing_means_no_commands_at_all():
    assert sf.apt_commands(sf.run_preflight(FakeSystem())) == []


# ---------------------------------------------------------------- ready, asked once, installed

def test_a_ready_computer_is_told_so_and_nothing_is_asked_or_run():
    code, io, apt, _ = run(system=FakeSystem())
    assert code == sf.EXIT_OK and apt.calls == [] and io.prompts == []
    assert CAT.t("setup.ready") in io.lines


def test_missing_programs_are_listed_with_their_reasons_before_anything_is_asked():
    code, io, apt, _ = run(io=FakeIO(answers=[None]))
    listed = io.text.index(CAT.t("setup.needs_install"))
    asked = io.text.index(CAT.t("setup.admin_note"))
    assert listed < asked and "git:" in io.text and "ffmpeg:" in io.text
    assert code == sf.EXIT_NOTHING_DONE and apt.calls == []


@pytest.mark.parametrize("answer", ["y", "Y", "yes", "YES", " yes ", "Yes\n"])
def test_a_yes_installs_and_the_computer_is_then_ready(answer):
    code, io, apt, system = run(io=FakeIO(answers=[answer]))
    assert code == sf.EXIT_OK
    assert [c[1] for c in apt.calls] == [["sudo", "apt-get", "update"], ["sudo", "apt-get", "install", "-y", "git", "ffmpeg"]]
    assert io.prompts == [CAT.t("setup.question") + " "]                       # asked exactly once, with a space after the question
    assert CAT.t("setup.installed") in io.lines and CAT.t("setup.ready") in io.lines
    assert system.installed >= set(ALL_PACKAGES)


@pytest.mark.parametrize("answer", ["", "n", "no", "yess", "ye", "y y", "1", "sure"])
def test_anything_but_a_plain_yes_is_a_no(answer):
    code, io, apt, _ = run(io=FakeIO(answers=[answer]))
    assert code == sf.EXIT_NOTHING_DONE and apt.calls == []
    assert CAT.t("setup.declined") in io.lines and CAT.t("setup.installed") not in io.lines


def test_the_password_is_explained_before_the_question_and_never_asked_for_here():
    _, io, _, _ = run()
    assert io.text.index(CAT.t("setup.admin_note")) < io.text.index(CAT.t("setup.installing"))
    assert "password" in CAT.t("setup.admin_note").lower() and "never sees" in CAT.t("setup.admin_note")
    assert not any("password" in p.lower() for p in io.prompts)


def test_what_was_agreed_to_is_each_program_by_name_and_the_update_and_nothing_else():
    _, _, apt, _ = run()
    (consent_a, _, ids_a), (consent_b, _, ids_b) = apt.calls
    assert ids_a == ["apt:update"] and ids_b == ["apt:git", "apt:ffmpeg"]
    assert consent_a is consent_b
    assert sorted(e.id for e in consent_a.entries) == ["apt:ffmpeg", "apt:git", "apt:update"]
    assert consent_a.covers_id("apt:git") and not consent_a.covers_id("apt:cmake") and not consent_a.covers_id("pip:lock")


# ---------------------------------------------------------------- not interactive

def test_with_nobody_to_ask_nothing_is_done_and_it_says_how_to_go_ahead():
    code, io, apt, _ = run(io=FakeIO(interactive=False))
    assert code == sf.EXIT_NOTHING_DONE and apt.calls == [] and io.prompts == []
    assert "--yes" in CAT.t("setup.cannot_ask") and CAT.t("setup.cannot_ask") in io.lines


def test_a_closed_input_is_the_same_as_nobody_to_ask():
    code, io, apt, _ = run(io=FakeIO(answers=[None]))
    assert code == sf.EXIT_NOTHING_DONE and apt.calls == [] and len(io.prompts) == 1


def test_yes_on_the_command_line_skips_the_question_even_when_nobody_can_answer():
    code, io, apt, _ = run(sf.Options(yes=True), io=FakeIO(interactive=False))
    assert code == sf.EXIT_OK and io.prompts == [] and len(apt.calls) == 2


def test_yes_on_the_command_line_still_explains_the_password():
    _, io, _, _ = run(sf.Options(yes=True))
    assert CAT.t("setup.admin_note") in io.lines and CAT.t("setup.needs_install") in io.lines


# ---------------------------------------------------------------- failures

def test_a_failed_update_stops_there_and_says_files_were_not_changed():
    code, io, apt, _ = run(apt=FakeApt(computer(), fail_on=1))
    assert code == sf.EXIT_PROBLEM and len(apt.calls) == 1
    assert CAT.t("setup.install_failed") in io.lines and CAT.t("setup.ready") not in io.lines


def test_a_failed_install_is_reported_and_not_called_ready():
    system = computer()
    code, io, apt, _ = run(system=system, apt=FakeApt(system, fail_on=2))
    assert code == sf.EXIT_PROBLEM and len(apt.calls) == 2
    assert CAT.t("setup.install_failed") in io.lines and CAT.t("setup.ready") not in io.lines and CAT.t("setup.installed") not in io.lines


def test_an_install_that_reports_success_but_left_something_missing_is_not_ready():
    system = computer()
    code, io, _, _ = run(system=system, apt=FakeApt(system, installs=False))
    assert code == sf.EXIT_PROBLEM
    assert CAT.count("setup.still_missing", 2) in io.lines
    assert CAT.t("setup.ready") not in io.lines and CAT.t("setup.installed") not in io.lines


def test_one_program_still_missing_is_counted_in_the_singular():
    system = computer()

    class Half(FakeApt):
        def __call__(self, consent, argv, ids):
            if argv[:3] == ["sudo", "apt-get", "install"]:
                put_on_computer(self.system, "git")
                self.calls.append((consent, list(argv), list(ids)))
                return 0
            return super().__call__(consent, argv, ids)

    code, io, _, _ = run(system=system, apt=Half(system))
    assert code == sf.EXIT_PROBLEM and CAT.count("setup.still_missing", 1) in io.lines
    assert CAT.count("setup.still_missing", 1) != CAT.count("setup.still_missing", 2)


# ---------------------------------------------------------------- the computer cannot be used at all

def test_a_blocker_stops_before_any_question_and_any_command():
    code, io, apt, _ = run(system=computer(euid=0))
    assert code == sf.EXIT_PROBLEM and apt.calls == [] and io.prompts == []
    assert CAT.t("setup.problems") in io.lines and CAT.t("setup.cannot_continue") in io.lines
    assert "[FIX]" in io.text


def test_a_blocker_hides_the_install_offer_so_nothing_is_half_done():
    _, io, _, _ = run(system=computer(euid=0))
    assert CAT.t("setup.needs_install") not in io.lines and CAT.t("setup.admin_note") not in io.lines


def test_notes_are_shown_but_do_not_stop_anything():
    code, io, apt, _ = run(system=computer(smi=None), io=FakeIO(answers=["y"]))
    assert code == sf.EXIT_OK and len(apt.calls) == 2
    assert CAT.t("setup.notes") in io.lines and "[note]" in io.text


# ---------------------------------------------------------------- --check

def test_check_on_a_ready_computer_says_ready_and_exits_zero():
    code, io, apt, _ = run(sf.Options(check=True), system=FakeSystem())
    assert code == sf.EXIT_OK and CAT.t("setup.check_ready") in io.lines and apt.calls == [] and io.prompts == []


def test_check_with_programs_missing_lists_them_asks_nothing_and_exits_one():
    code, io, apt, system = run(sf.Options(check=True))
    assert code == sf.EXIT_PROBLEM and apt.calls == [] and io.prompts == []
    assert CAT.t("setup.check_not_ready") in io.lines and "git:" in io.text
    assert system.installed == set(ALL_PACKAGES) - set(MISSING)


def test_check_with_a_blocker_exits_one_and_says_not_ready():
    code, io, apt, _ = run(sf.Options(check=True), system=computer(euid=0))
    assert code == sf.EXIT_PROBLEM and apt.calls == []
    assert CAT.t("setup.check_not_ready") in io.lines and CAT.t("setup.cannot_continue") not in io.lines


def test_check_changes_nothing_even_when_yes_is_also_given():
    code, io, apt, system = run(sf.Options(check=True, yes=True))
    assert code == sf.EXIT_PROBLEM and apt.calls == [] and system.installed == set(ALL_PACKAGES) - set(MISSING)


# ---------------------------------------------------------------- --dry-run

def test_dry_run_shows_the_exact_commands_and_runs_none():
    code, io, apt, system = run(sf.Options(dry_run=True))
    assert code == sf.EXIT_OK and apt.calls == [] and io.prompts == []
    assert CAT.t("setup.dry_run_header") in io.lines
    assert "  " + CAT.t("setup.dry_run_command", command="sudo apt-get update") in io.lines
    assert "  " + CAT.t("setup.dry_run_command", command="sudo apt-get install -y git ffmpeg") in io.lines
    assert system.installed == set(ALL_PACKAGES) - set(MISSING)


def test_dry_run_on_a_ready_computer_says_nothing_needs_to_run():
    code, io, apt, _ = run(sf.Options(dry_run=True), system=FakeSystem())
    assert code == sf.EXIT_OK and apt.calls == [] and "  " + CAT.t("setup.dry_run_none") in io.lines


def test_dry_run_with_a_blocker_still_stops_there():
    code, io, apt, _ = run(sf.Options(dry_run=True), system=computer(euid=0))
    assert code == sf.EXIT_PROBLEM and apt.calls == [] and CAT.t("setup.dry_run_header") not in io.lines


# ---------------------------------------------------------------- the words

def test_lines_are_indented_in_code_and_questions_end_in_a_space_added_in_code():
    _, io, _, _ = run(io=FakeIO(answers=[None]))
    assert "  " + CAT.t("setup.package_line", package="git", reason=sf.apt_reason(CAT, next(r for r in sf.run_preflight(computer()).missing if r.package == "git"))) in io.lines
    assert not CAT.t("setup.question").endswith(" ")
    assert io.prompts[0].endswith(": ") and not io.prompts[0].endswith("  ")


def test_the_title_comes_first_and_the_run_never_prints_a_python_traceback_word():
    _, io, _, _ = run()
    assert io.lines[0] == CAT.t("setup.title") and io.lines[1] == CAT.t("setup.looking")
    assert "Traceback" not in io.text and "None" not in io.text
