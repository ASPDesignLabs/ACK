# SPDX-License-Identifier: GPL-3.0-or-later
"""The terminal front for starting voices: list, show, choose, get. What is held to here: the notes are shown before the acknowledgment is asked for, the acknowledgment
and the agreement to the download are two separate things that neither flag nor answer can merge, nothing reaches the network before both, every edit asks first and
keeps the earlier file, a stopped or failed download can be carried on by running the same command, and nothing printed says or implies that use is permitted."""
import os
import subprocess
import sys
import urllib.error
from datetime import datetime, timezone
from pathlib import Path

import pytest

from vs_env_helpers import FakeTime
from vs_fetch_helpers import FakeOpener
from vs_startvoice_helpers import LESSAC_PAGE, VOICE_A, VOICE_B, Terminal, implies_permission, leaked_keys, make_registry, make_voice
from voice_studio import voices
from voice_studio.core import fetch, startvoice as sv, text
from voice_studio.core import voices_flow as vf
from voice_studio.core.consent import load_consent
from voice_studio.core.paths import DataHome, ProjectPaths
from voice_studio.core.project import Acknowledgment, create_project, load_project
from voice_studio.core.registry import Item, Registry
from voice_studio.core.text import size_text

CAT = text.load_catalog("en")
REVISION = "0123abcd"
TOOLS = Path(__file__).resolve().parents[2]


class VoiceRig:
    def __init__(self, tmp_path, registry=None, payload=VOICE_A, projects=("Anna",), **opener_kw):
        self.home = DataHome(str(tmp_path / "home"))
        self.registry = registry or make_registry()
        self.opener = FakeOpener(payload, **opener_kw)
        self.time = FakeTime()
        for name in projects:
            create_project(self.home.projects, name, "own")

    def fetcher(self, item, dest, consent, **kw):
        return fetch.fetch(item, dest, consent, opener=self.opener, room_margin=0, **kw)

    def run(self, *argv, answers=(), interactive=True, fetcher="real"):
        io = Terminal(answers, interactive)
        code = vf.run_voices(list(argv), self.home, self.registry, CAT, io, sleep=self.time.sleep, clock=self.time.monotonic,
                             fetcher=self.fetcher if fetcher == "real" else fetcher)
        assert leaked_keys(io.text + "\n".join(io.prompts)) == [], "a catalog key was printed instead of words"
        assert implies_permission(io.text) == [], "something printed says or implies that use is permitted"
        return code, io

    def project(self, project_id="anna"):
        return load_project(ProjectPaths(self.home.projects + "/" + project_id))

    def project_bytes(self, project_id="anna"):
        return Path(self.home.projects, project_id, "project.json").read_bytes()

    def previous(self, project_id="anna"):
        return Path(self.home.projects, project_id, "project.json.previous")

    def kept(self, voice_id="voice-mike"):
        return Path(self.home.voices) / voice_id / (voice_id + ".ckpt")

    def consent(self):
        return load_consent(Path(self.home.consent_file))


@pytest.fixture
def rig(tmp_path):
    return VoiceRig(tmp_path)


def position(lines, wanted):
    return next(i for i, line in enumerate(lines) if wanted in line)


# ---------------------------------------------------------------- help and mistakes

@pytest.mark.parametrize("argv", [(), ("help",), ("-h",), ("--help",)])
def test_help_lists_the_commands_and_says_the_two_flags_are_separate(rig, argv):
    code, io = rig.run(*argv)
    assert code == 0 and io.prompts == []
    for command in ("list ", "show ", "choose ", "get "):
        assert "  " + command in io.text
    assert "--acknowledge confirms you have read the notes. --yes agrees to the download or the change. They are separate on purpose." in io.text


def test_an_unknown_command_is_refused_by_name(rig):
    code, io = rig.run("download")
    assert code == 2 and "download" in io.text and "Nothing was done" in io.text


@pytest.mark.parametrize("argv, fragment", [(("list", "mike"), "mike"), (("list", "--nope"), "--nope"), (("show", "mike", "amy"), "amy"), (("show", "--yes"), "--yes"),
                                            (("choose", "mike", "--project"), "--project"), (("get", "--acknowledge=1"), "--acknowledge=1"),
                                            (("get", "mike", "--project", "a", "--project", "b"), "--project")])
def test_an_option_or_word_that_is_not_understood_does_nothing(rig, argv, fragment):
    code, io = rig.run(*argv)
    assert code == 2 and fragment in io.text and "Nothing was done" in io.text and io.prompts == []
    assert not Path(rig.home.voices).exists() and not os.path.exists(rig.home.consent_file)


def test_a_missing_or_unknown_voice_lists_the_ones_there_are(rig):
    for command in ("show", "choose", "get"):
        code, io = rig.run(command)
        assert code == 2 and "Which voice? The voices are: voice-mike, voice-amy." in io.text, command
        code, io = rig.run(command, "bob")
        assert code == 2 and "I do not know a starting voice called bob. The voices are: voice-mike, voice-amy." in io.text, command
    assert "x" * 61 not in rig.run("show", "x" * 100)[1].text


# ---------------------------------------------------------------- list

def test_list_shows_each_voice_with_its_size_and_where_it_comes_from_and_asks_nothing(rig):
    code, io = rig.run("list")
    assert code == 0 and io.prompts == []
    size = size_text(len(VOICE_A))
    assert "voice-mike: Male voice, %s from huggingface.co." % size in io.lines and "voice-amy: Female voice, %s from huggingface.co." % size_text(len(VOICE_B)) in io.lines
    assert io.lines.count("  On this computer: no.") == 2 and "To read where a voice comes from: python3 -m voice_studio.voices show voice-mike" in io.lines
    assert "For project" not in io.text, "without --project there is no project to say anything about"


def test_list_for_a_project_says_what_is_left_for_each_voice_and_marks_the_chosen_one(rig):
    rig.run("choose", "mike", "--yes", interactive=False)
    code, io = rig.run("list", "--project", "anna")
    assert code == 0
    step = CAT.t("startvoice.step.acknowledge")
    assert io.lines.count("  For project anna: " + step) == 2 and io.lines.count("  This is the starting voice of project anna.") == 1
    assert position(io.lines, "voice-mike:") < position(io.lines, "starting voice of project anna") < position(io.lines, "voice-amy:")


def test_list_does_not_pick_a_project_for_you_but_a_wrong_name_is_refused(rig):
    code, io = rig.run("list", "--project", "bob")
    assert code == 2 and "There is no project called bob. The projects are: anna." in io.text and "voice-mike" not in io.text


def test_list_follows_a_voice_through_the_steps_and_sees_it_on_the_computer(rig):
    rig.run("get", "mike", "--acknowledge", "--yes", interactive=False)
    code, io = rig.run("list", "--project", "anna")
    assert "  On this computer: yes." in io.lines and "  For project anna: " + CAT.t("startvoice.step.ready") in io.lines
    assert "  On this computer: no." in io.lines


def test_a_voice_that_cannot_be_fetched_yet_is_listed_as_such(tmp_path):
    unpinned = Registry((Item("voice-mike", "voice", "fetch.why.voice_mike", "voice-mike-card", approx_size_bytes=846_000_000),))
    code, io = VoiceRig(tmp_path, registry=unpinned).run("list", "--project", "anna")
    assert code == 0 and "  It cannot be downloaded yet." in io.lines and "On this computer" not in io.text


# ---------------------------------------------------------------- show

def test_show_prints_the_notes_in_the_order_the_chain_goes_and_writes_nothing(tmp_path):
    rig = VoiceRig(tmp_path, projects=())
    code, io = rig.run("show", "mike")
    assert code == 0 and io.prompts == []
    in_order = ["voice-mike: Male voice,", CAT.t("startvoice.intro"), "Mike", CAT.t("startvoice.says.mike_recordings"), CAT.t("startvoice.says.made_from_lessac"),
                "The page to read: https://github.com/example/recordings", "Lessac, the voice both were made from", CAT.t("startvoice.says.lessac_origin"),
                CAT.t("startvoice.says.lessac_terms"), CAT.t("startvoice.says.lessac_ends"), CAT.t("startvoice.says.lessac_unsettled"), "The page to read: " + LESSAC_PAGE,
                CAT.t("startvoice.read_on", date=sv.FACTS_READ_ON), CAT.t("startvoice.not_advice"), CAT.t("startvoice.not_hosted"), CAT.t("startvoice.head_start")]
    at = [position(io.lines, wanted) for wanted in in_order]
    assert at == sorted(at) and len(set(at)) == len(at)
    assert not os.path.exists(rig.home.root), "reading the notes creates nothing"


def test_the_notes_for_amy_say_her_licence_is_not_established(tmp_path):
    io = VoiceRig(tmp_path, projects=()).run("show", "Amy")[1]
    assert "voice-amy: Female voice," in io.lines[1] and CAT.t("startvoice.says.amy_recordings") in io.text and "not established" in io.text


def test_a_voice_with_no_page_listed_says_so(tmp_path):
    bare = Registry((make_voice("voice-mike", VOICE_A, pages=()), make_voice("voice-amy", VOICE_B)))
    io = VoiceRig(tmp_path, registry=bare, projects=()).run("show", "mike")[1]
    assert io.lines.count("  No page address is listed for this.") == 2


# ---------------------------------------------------------------- choose

def test_choose_asks_then_saves_the_voice_and_keeps_the_earlier_file(rig):
    before = rig.project_bytes()
    code, io = rig.run("choose", "mike", answers=["yes"])
    assert code == 0 and rig.project().starting_voice == "voice-mike" and rig.previous().read_bytes() == before
    assert io.prompts == ["Set the starting voice of project anna to voice-mike? Only that line of its file changes, and the earlier file is kept as project.json.previous. Type yes to do it. "]
    assert "Using the only project: anna." in io.text and "Done. Project anna now starts from voice-mike." in io.lines


@pytest.mark.parametrize("answer", ["no", "", "yess", "later"])
def test_choose_changes_nothing_on_anything_but_yes(rig, answer):
    before = rig.project_bytes()
    code, io = rig.run("choose", "mike", answers=[answer])
    assert code == 2 and rig.project_bytes() == before and not rig.previous().exists() and "Nothing was done." in io.lines


def test_choose_with_nobody_to_ask_changes_nothing_and_says_how_to_say_yes(rig):
    before = rig.project_bytes()
    code, io = rig.run("choose", "mike", interactive=False)
    assert code == 2 and rig.project_bytes() == before and "add --yes" in io.text
    assert rig.run("choose", "mike", "-y", interactive=False)[0] == 0 and rig.project().starting_voice == "voice-mike"


def test_choose_a_voice_already_chosen_changes_nothing(rig):
    rig.run("choose", "mike", "--yes", interactive=False)
    before = rig.project_bytes()
    code, io = rig.run("choose", "voice-mike", answers=[])
    assert code == 0 and rig.project_bytes() == before and "Project anna already starts from voice-mike. Nothing was changed." in io.lines and io.prompts == []


def test_choose_changes_only_the_starting_voice_and_fetches_and_acknowledges_nothing(rig):
    rig.run("choose", "amy", "--yes", interactive=False)
    project = rig.project()
    assert project.starting_voice == "voice-amy" and project.acknowledgments == () and rig.opener.calls == []
    assert not Path(rig.home.voices).exists() and not os.path.exists(rig.home.consent_file)


def test_choose_needs_a_project_and_names_the_ones_there_are(tmp_path):
    rig = VoiceRig(tmp_path, projects=("Anna", "Ben"))
    code, io = rig.run("choose", "mike", "--yes", interactive=False)
    assert code == 2 and "There is more than one project: anna, ben. Say which one you mean." in io.text
    assert rig.run("choose", "mike", "--project", "ben", "--yes", interactive=False)[0] == 0
    assert rig.project("ben").starting_voice == "voice-mike" and rig.project("anna").starting_voice is None
    assert VoiceRig(tmp_path / "none", projects=()).run("choose", "mike", "--yes", interactive=False)[0] == 2


def test_choose_that_cannot_save_says_so_and_changes_nothing(rig, monkeypatch):
    def full(*args, **kwargs):
        raise OSError(28, "No space left on device")
    monkeypatch.setattr(vf, "save_project", full)
    before = rig.project_bytes()
    code, io = rig.run("choose", "mike", "--yes", interactive=False)
    assert code == 1 and rig.project_bytes() == before
    assert "The project anna could not be saved, so nothing was changed." in io.lines and "  Technical detail: No space left on device" in io.lines


def test_interrupting_the_question_changes_nothing(rig):
    before = rig.project_bytes()
    code, io = rig.run("choose", "mike", answers=[KeyboardInterrupt()])
    assert code == 1 and rig.project_bytes() == before and "Stopped." in io.text


# ---------------------------------------------------------------- get: the whole journey

def test_get_shows_the_notes_then_asks_to_confirm_them_then_asks_to_download_and_only_then_downloads(rig):
    before = rig.project_bytes()
    started = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    code, io = rig.run("get", "mike", answers=["yes", "yes"])
    assert code == 0
    ev = io.events
    asked = [i for i, (kind, _) in enumerate(ev) if kind == "ask"]
    said = lambda wanted: next(i for i, (kind, line) in enumerate(ev) if kind == "say" and wanted in line)
    assert said("voice-mike: Male voice") < said(CAT.t("startvoice.intro")) < said(CAT.t("startvoice.not_advice")) < asked[0]
    assert ev[asked[0]][1] == "Have you read where this voice comes from? Type yes to confirm that you have. "
    assert asked[0] < said("Saved: project anna has acknowledged") < asked[1] < said("Saved your agreement") < said("Downloading ") < said("Done.")
    assert ev[asked[1]][1].startswith("Download this voice now? It is %s from huggingface.co and will be kept in " % size_text(len(VOICE_A)))
    # what was saved
    assert rig.kept().read_bytes() == VOICE_A and len(rig.opener.calls) == 1 and rig.opener.calls[0][0] == rig.registry.get("voice-mike").url
    project = rig.project()
    assert [(a.voice, a.revision) for a in project.acknowledgments] == [("voice-mike", REVISION)] and rig.previous().read_bytes() == before
    assert project.acknowledgments[0].at[:10] in {started, datetime.now(timezone.utc).strftime("%Y-%m-%d")}, "dated today"
    assert rig.consent().covers(rig.registry.get("voice-mike")) and not rig.consent().covers(rig.registry.get("voice-amy"))
    assert "The file: " + str(rig.kept()) in io.lines
    assert "To make it this project's starting voice: python3 -m voice_studio.voices choose voice-mike --project anna" in io.lines


def test_the_two_questions_are_separate_a_yes_to_one_is_not_a_yes_to_the_other(rig):
    code, io = rig.run("get", "mike", answers=["yes", "no"])
    assert code == 2 and rig.opener.calls == [] and not rig.kept().exists() and rig.consent() is None
    assert [a.voice for a in rig.project().acknowledgments] == ["voice-mike"], "the first yes was kept"
    assert io.lines.count("Nothing was done.") == 1


def test_running_the_same_command_again_carries_on_from_the_next_question_without_the_notes(rig):
    rig.run("get", "mike", answers=["yes", "no"])
    code, io = rig.run("get", "mike", answers=["yes"])
    assert code == 0 and rig.kept().read_bytes() == VOICE_A
    assert CAT.t("startvoice.intro") not in io.text and len(io.prompts) == 1 and io.prompts[0].startswith("Download this voice now?")


def test_declining_the_acknowledgment_saves_nothing_and_reaches_for_nothing(rig):
    before = rig.project_bytes()
    code, io = rig.run("get", "mike", answers=["no"])
    assert code == 2 and rig.project_bytes() == before and not rig.previous().exists() and rig.opener.calls == [] and rig.consent() is None
    assert CAT.t("startvoice.not_advice") in io.text, "the notes were shown before it asked"


@pytest.mark.parametrize("answer", ["", "yess", "ye", "I have", "no thanks"])
def test_anything_but_yes_to_the_acknowledgment_is_not_one(rig, answer):
    code, io = rig.run("get", "mike", answers=[answer])
    assert code == 2 and rig.project().acknowledgments == () and rig.opener.calls == []


# ---------------------------------------------------------------- get: the flags are two separate acts

def test_both_flags_do_everything_in_one_line_with_nobody_there(rig):
    code, io = rig.run("get", "mike", "--acknowledge", "--yes", interactive=False)
    assert code == 0 and io.prompts == [] and rig.kept().read_bytes() == VOICE_A
    assert CAT.t("startvoice.not_advice") in io.text, "the notes are shown even when the flag says they were read"
    assert [a.voice for a in rig.project().acknowledgments] == ["voice-mike"] and rig.consent().covers(rig.registry.get("voice-mike"))


def test_yes_alone_never_counts_as_the_acknowledgment(rig):
    before = rig.project_bytes()
    code, io = rig.run("get", "mike", "--yes", interactive=False)
    assert code == 2 and rig.project_bytes() == before and rig.opener.calls == [] and rig.consent() is None and not Path(rig.home.voices).exists()
    assert "--acknowledge was not given. Nothing was done." in io.text and CAT.t("startvoice.not_advice") in io.text


def test_yes_alone_does_not_count_as_the_acknowledgment_even_with_someone_to_ask_because_the_question_is_still_asked(rig):
    code, io = rig.run("get", "mike", "--yes", answers=["no"])
    assert code == 2 and io.prompts == ["Have you read where this voice comes from? Type yes to confirm that you have. "] and rig.project().acknowledgments == ()


def test_acknowledge_alone_saves_the_acknowledgment_but_downloads_nothing(rig):
    code, io = rig.run("get", "mike", "--acknowledge", interactive=False)
    assert code == 2 and rig.opener.calls == [] and rig.consent() is None and not rig.kept().exists()
    assert [a.voice for a in rig.project().acknowledgments] == ["voice-mike"] and "add --yes" in io.text
    code, io = rig.run("get", "mike", "--yes", interactive=False)
    assert code == 0 and rig.kept().read_bytes() == VOICE_A and CAT.t("startvoice.intro") not in io.text


def test_acknowledge_with_nobody_to_ask_still_asks_nothing_and_a_short_flag_works_for_yes(rig):
    code, io = rig.run("get", "mike", "--acknowledge", "-y", interactive=False)
    assert code == 0 and io.prompts == []


def test_a_terminal_with_nobody_at_it_is_never_asked_even_if_answers_are_lying_about(rig):
    for argv in (("choose", "mike"), ("get", "mike"), ("get", "mike", "--acknowledge")):
        code, io = rig.run(*argv, interactive=False, answers=["yes", "yes", "yes"])
        assert code == 2 and io.prompts == [], argv
    assert rig.project().starting_voice is None and rig.consent() is None and rig.opener.calls == []


# ---------------------------------------------------------------- get: what was already done

def test_when_the_voice_is_here_and_acknowledged_there_is_nothing_to_do_and_no_question(rig):
    rig.run("get", "mike", "--acknowledge", "--yes", interactive=False)
    rig.opener.calls.clear()
    before = rig.project_bytes()
    code, io = rig.run("get", "mike")
    assert code == 0 and io.prompts == [] and rig.opener.calls == [] and rig.project_bytes() == before
    assert "This voice is already on this computer, and project anna has acknowledged it. Nothing to download." in io.lines
    assert "The file: " + str(rig.kept()) in io.lines


def test_a_voice_another_project_fetched_needs_this_projects_own_acknowledgment_but_no_download(tmp_path):
    rig = VoiceRig(tmp_path, projects=("Anna", "Ben"))
    rig.run("get", "mike", "--project", "anna", "--acknowledge", "--yes", interactive=False)
    rig.opener.calls.clear()
    code, io = rig.run("get", "mike", "--project", "ben", answers=["yes"])
    assert code == 0 and rig.opener.calls == [] and io.prompts == ["Have you read where this voice comes from? Type yes to confirm that you have. "]
    assert [a.voice for a in rig.project("ben").acknowledgments] == ["voice-mike"] and "Nothing to download." in io.text
    assert CAT.t("startvoice.not_advice") in io.text, "Ben is shown the notes too"


def test_an_agreement_already_saved_is_not_asked_for_twice(rig):
    sv.agree_to_download(rig.registry, "voice-mike", rig.home)
    code, io = rig.run("get", "mike", answers=["yes"])
    assert code == 0 and len(io.prompts) == 1 and "You already agreed to download this file, so it carries on." in io.lines
    assert rig.kept().read_bytes() == VOICE_A


def test_the_other_voice_is_independent(rig):
    rig.run("get", "mike", "--acknowledge", "--yes", interactive=False)
    rig.opener = FakeOpener(VOICE_B)
    code, io = rig.run("get", "amy", answers=["yes", "yes"])
    assert code == 0 and rig.kept("voice-amy").read_bytes() == VOICE_B and rig.kept("voice-mike").read_bytes() == VOICE_A
    assert {a.voice for a in rig.project().acknowledgments} == {"voice-mike", "voice-amy"}
    assert rig.consent().covers(rig.registry.get("voice-mike")) and rig.consent().covers(rig.registry.get("voice-amy"))


def test_a_voice_already_chosen_is_not_offered_to_be_chosen_again(rig):
    rig.run("choose", "mike", "--yes", interactive=False)
    code, io = rig.run("get", "mike", "--acknowledge", "--yes", interactive=False)
    assert "It is already the starting voice of project anna." in io.lines and "choose voice-mike" not in io.text


# ---------------------------------------------------------------- get: the download

def test_progress_is_told_in_plain_lines_every_ten_percent_with_no_moving_bar(rig):
    def fake(item, dest, consent, **kw):
        for done in (0, 1, 5, 10, 15, 50, 99, 100, 100):
            kw["progress"](done, 100)
        kw["progress"](50, 0)
        return Path(dest) / item.filename
    code, io = rig.run("get", "mike", "--acknowledge", "--yes", interactive=False, fetcher=fake)
    lines = [l for l in io.lines if l.startswith("  ") and "%:" in l]
    assert code == 0 and [l.split("%")[0].strip() for l in lines] == ["10", "50", "99", "100"]
    assert "\r" not in io.text and all("of" in l for l in lines)


def test_a_download_that_reports_more_than_all_of_it_is_still_told_as_a_hundred_percent(rig):
    def over(item, dest, consent, **kw):
        kw["progress"](150, 100)
        return Path(dest) / item.filename
    code, io = rig.run("get", "mike", "--acknowledge", "--yes", interactive=False, fetcher=over)
    assert code == 0 and [l for l in io.lines if "%:" in l] == ["  100%: 150 B of 100 B"]


def test_a_dropped_connection_is_told_once_then_again_and_then_the_return(tmp_path):
    class Flaky(FakeOpener):
        def __call__(self, url, headers):
            if len(self.calls) < 2:
                self.calls.append((url, dict(headers)))
                raise urllib.error.URLError("network unreachable")
            return super().__call__(url, headers)
    rig = VoiceRig(tmp_path)
    rig.opener = Flaky(VOICE_A)
    code, io = rig.run("get", "mike", "--acknowledge", "--yes", interactive=False)
    assert code == 0 and rig.kept().read_bytes() == VOICE_A
    first = position(io.lines, "The internet connection stopped.")
    again = position(io.lines, "Still no connection. Trying again in 10 seconds.")
    back = position(io.lines, "The connection is back. Carrying on.")
    assert first < again < back and "It will try again in 5 seconds, and keep trying for up to 30 minutes." in io.lines[first]
    assert "It has been away for 5 s." in io.lines[again] and rig.time.slept[:5] == [1] * 5


def test_a_file_that_is_not_the_agreed_one_is_refused_in_words_and_can_be_fetched_again(tmp_path):
    rig = VoiceRig(tmp_path, payload=b"W" * len(VOICE_A))
    code, io = rig.run("get", "mike", "--acknowledge", "--yes", interactive=False)
    assert code == 1 and not rig.kept().exists() and not list((Path(rig.home.voices) / "voice-mike").glob("*.part"))
    for sentence in ("The file that arrived did not match what was agreed, so it cannot be trusted.", "The bad file was deleted. Nothing else was changed."):
        assert "  " + sentence in io.lines


def test_a_failed_download_keeps_the_acknowledgment_and_the_agreement_so_the_same_command_finishes_it(tmp_path):
    rig = VoiceRig(tmp_path, payload=b"W" * len(VOICE_A))
    rig.run("get", "mike", "--acknowledge", "--yes", interactive=False)
    assert [a.voice for a in rig.project().acknowledgments] == ["voice-mike"] and rig.consent().covers(rig.registry.get("voice-mike"))
    rig.opener = FakeOpener(VOICE_A)
    code, io = rig.run("get", "mike", interactive=False)
    assert code == 0 and rig.kept().read_bytes() == VOICE_A and "You already agreed to download this file, so it carries on." in io.lines


def test_no_room_is_told_in_three_parts(rig):
    def full(item, dest, consent, **kw):
        raise fetch.FetchError("room", "5000000000 bytes needed")
    code, io = rig.run("get", "mike", "--acknowledge", "--yes", interactive=False, fetcher=full)
    assert code == 1
    for sentence in ("There is not enough free space for this download.", "Nothing was downloaded or changed.", "Free up space on this drive or choose another drive, then try again."):
        assert "  " + sentence in io.lines
    assert "  Technical detail: 5000000000 bytes needed" in io.lines


def test_the_connection_giving_out_is_told_and_what_arrived_is_kept(rig):
    def gone(item, dest, consent, **kw):
        raise fetch.FetchError("connection_lost", "away for 30 minutes (x)")
    code, io = rig.run("get", "mike", "--acknowledge", "--yes", interactive=False, fetcher=gone)
    assert code == 1 and "  The internet connection did not come back in time, so the download stopped." in io.lines and "  When the connection is back, start it again. It carries on from where it stopped." in io.lines


def test_ctrl_c_during_the_download_says_what_is_kept_and_the_same_command_carries_on(rig):
    def stopped(item, dest, consent, **kw):
        raise KeyboardInterrupt
    code, io = rig.run("get", "mike", "--acknowledge", "--yes", interactive=False, fetcher=stopped)
    assert code == 1 and "Stopped. Anything already saved above is kept, and so is what had arrived of a download. Run the same command again to carry on." in io.lines
    assert [a.voice for a in rig.project().acknowledgments] == ["voice-mike"] and rig.consent() is not None
    assert rig.run("get", "mike", interactive=False)[0] == 0 and rig.kept().read_bytes() == VOICE_A


def test_a_voice_that_cannot_be_fetched_yet_is_told_in_three_parts_and_nothing_is_saved(tmp_path):
    unpinned = Registry((Item("voice-mike", "voice", "fetch.why.voice_mike", "voice-mike-card", approx_size_bytes=846_000_000), make_voice("voice-amy", VOICE_B)))
    rig = VoiceRig(tmp_path, registry=unpinned)
    before = rig.project_bytes()
    code, io = rig.run("get", "mike", "--acknowledge", "--yes", interactive=False)
    assert code == 1 and rig.project_bytes() == before and not os.path.exists(rig.home.consent_file)
    for sentence in ("This starting voice cannot be downloaded yet, because its exact file has not been fixed in place.", "Nothing was downloaded or changed."):
        assert "  " + sentence in io.lines


def test_an_acknowledgment_that_cannot_be_saved_stops_everything_before_the_network(rig, monkeypatch):
    def full(*args, **kwargs):
        raise OSError(28, "No space left on device")
    monkeypatch.setattr(vf, "save_project", full)
    code, io = rig.run("get", "mike", "--acknowledge", "--yes", interactive=False)
    assert code == 1 and rig.opener.calls == [] and rig.consent() is None
    assert "The acknowledgment could not be saved, so nothing was downloaded." in io.lines and "  Technical detail: No space left on device" in io.lines


def test_an_agreement_that_cannot_be_saved_stops_everything_before_the_network(rig, monkeypatch):
    def full(*args, **kwargs):
        raise OSError(13, "Permission denied")
    monkeypatch.setattr(sv, "agree_to_download", full)
    code, io = rig.run("get", "mike", "--acknowledge", "--yes", interactive=False)
    assert code == 1 and rig.opener.calls == [] and "Your agreement could not be saved, so nothing was downloaded." in io.lines
    assert [a.voice for a in rig.project().acknowledgments] == ["voice-mike"], "the acknowledgment had already been saved"


# ---------------------------------------------------------------- get: which project

def test_get_with_one_project_uses_it_and_says_so(rig):
    io = rig.run("get", "mike", "--acknowledge", "--yes", interactive=False)[1]
    assert "Using the only project: anna." in io.lines


def test_get_with_several_projects_and_no_name_asks_which_and_shows_nothing(tmp_path):
    rig = VoiceRig(tmp_path, projects=("Anna", "Ben"))
    code, io = rig.run("get", "mike", "--acknowledge", "--yes", interactive=False)
    assert code == 2 and "There is more than one project: anna, ben. Say which one you mean." in io.text and CAT.t("startvoice.intro") not in io.text
    assert rig.opener.calls == []


def test_get_with_no_projects_says_how_to_make_one(tmp_path):
    rig = VoiceRig(tmp_path, projects=())
    code, io = rig.run("get", "mike", "--acknowledge", "--yes", interactive=False)
    assert code == 2 and "python3 -m voice_studio.projects new" in io.text and rig.opener.calls == []


def test_get_names_the_project_when_asked_to_and_leaves_the_others_alone(tmp_path):
    rig = VoiceRig(tmp_path, projects=("Anna", "Ben"))
    ben_before = rig.project_bytes("ben")
    rig.run("get", "mike", "--project", "anna", "--acknowledge", "--yes", interactive=False)
    assert rig.project_bytes("ben") == ben_before and rig.project("anna").acknowledgments != ()


# ---------------------------------------------------------------- the front itself

def test_the_front_reads_the_real_home_and_prints(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("HOME", str(tmp_path))
    assert voices.main(["list"]) == 0
    out = capsys.readouterr().out
    assert "voice-mike: Male voice," in out and "voice-amy: Female voice," in out and "huggingface.co" in out
    assert voices.main(["show", "mike"]) == 0 and "Research Licence Agreement" in capsys.readouterr().out


def test_the_front_finds_the_projects_in_the_real_home(tmp_path, monkeypatch, capsys):
    from voice_studio import projects
    monkeypatch.setenv("HOME", str(tmp_path))
    assert projects.main(["new", "--own", "--name", "Anna", "--yes"]) == 0
    capsys.readouterr()
    assert voices.main(["list", "--project", "anna"]) == 0
    assert "For project anna:" in capsys.readouterr().out
    assert voices.main(["choose", "mike", "--yes"]) == 0 and "Done. Project anna now starts from voice-mike." in capsys.readouterr().out


def test_the_front_gives_the_flow_the_real_clock_and_the_real_way_to_wait(tmp_path, monkeypatch):
    import time
    seen = {}

    def spy(argv, home, registry, cat, io, **kw):
        seen.update(kw, home=home.home)
        return 0
    monkeypatch.setattr(voices, "run_voices", spy)
    monkeypatch.setenv("HOME", str(tmp_path))
    assert voices.main(["list"]) == 0
    assert seen["sleep"] is time.sleep and seen["clock"] is time.monotonic and seen["home"] == str(tmp_path)


def test_the_front_runs_as_a_module(tmp_path):
    done = subprocess.run([sys.executable, "-m", "voice_studio.voices", "help"], cwd=str(TOOLS), env=dict(os.environ, HOME=str(tmp_path), PYTHONDONTWRITEBYTECODE="1"),
                          text=True, capture_output=True, timeout=60, stdin=subprocess.DEVNULL)
    assert done.returncode == 0 and "Commands:" in done.stdout and "Traceback" not in done.stderr


# ---------------------------------------------------------------- the options each command takes

def test_the_options_the_commands_publish_are_exactly_the_ones_they_accept(rig):
    """The checklist is held to `OPTIONS`; so `OPTIONS` is held to what the commands really do."""
    every = {"--project", "--yes", "-y", "--acknowledge", "--nope"}
    assert set(vf.OPTIONS) == {"list", "show", "choose", "get"}
    for command, accepted in vf.OPTIONS.items():
        for option in sorted(every):
            argv = [command, "mike", option] + (["anna"] if option == "--project" else [])
            if command == "list":
                argv = [command, option] + (["anna"] if option == "--project" else [])
            code, io = rig.run(*argv, interactive=False)
            understood = "I do not know the option" not in io.text
            assert understood == (option in accepted), (command, option, io.text)
