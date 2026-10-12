# SPDX-License-Identifier: GPL-3.0-or-later
"""The bridge between the window and the flows (core/windowio.py): a flow's questions are answered by a sink, a closed window never leaves a flow waiting, and a crash is shown, not lost."""
import threading
import time

import pytest

from voice_studio.core import text, windowio as wio

CAT = text.load_catalog("en")


class FakeSink:
    """Answers the way the window would, but on a thread of its own so that a question really waits."""

    def __init__(self, confirms=(), asks=()):
        self.confirms, self.asks = list(confirms), list(asks)
        self.said, self.questions, self.done = [], [], threading.Event()
        self.result = None

    def line(self, text):
        self.said.append(text)

    def confirm(self, lines, question, reply):
        self.questions.append(("confirm", lines, question))
        answer = self.confirms.pop(0) if self.confirms else None
        threading.Timer(0.01, lambda: reply(answer) if answer is not wio_never else None).start()

    def ask(self, lines, prompt, reply):
        self.questions.append(("ask", lines, prompt))
        answer = self.asks.pop(0)
        threading.Timer(0.01, lambda: reply(answer)).start()

    def finished(self, code, lines):
        self.result = (code, lines)
        self.done.set()


wio_never = object()


def run(flow, sink, **kw):
    handle = wio.start_run(flow, sink, **kw)
    assert sink.done.wait(5), "the run never finished"
    return handle


# ---------------------------------------------------------------- the question

def test_the_instruction_to_type_a_word_is_dropped_from_a_question_a_window_asks_with_buttons():
    assert wio.question_text("Start round 3 now? Type yes to start.") == "Start round 3 now?"
    assert wio.question_text("Remove all of that, about 4.2 GB? This cannot be undone. Type yes to remove it.") == "Remove all of that, about 4.2 GB? This cannot be undone."
    assert wio.question_text("Set the note on round 1 to this? first try Type yes to save it.") == "Set the note on round 1 to this? first try"
    assert wio.question_text("Is this fine?") == "Is this fine?" and wio.question_text("  Type yes to go.  ") == "Type yes to go."
    assert wio.question_text("Remove the note? Type yes to remove it") == "Remove the note?"
    assert wio.question_text("Set the note on round 1 to this? Type yes now. Type yes to save it.") == "Set the note on round 1 to this? Type yes now."      # the person's words stay
    assert wio.question_text("Set the note on round 1 to this? say Type yes to save it. Type yes to save it.") == "Set the note on round 1 to this? say Type yes to save it."
    assert wio.question_text("Type yes to go. Then more words.") == "Type yes to go. Then more words."                                                  # not at the end: not the instruction
    assert wio.question_text("Is it fine? Type yes to go. Then more words.") == "Is it fine? Type yes to go. Then more words."                          # and the words after it are never lost
    assert wio.question_text("  Is this fine?  ") == "Is this fine?"                                                                                    # an untouched question is only trimmed


def test_every_question_the_flows_ask_for_a_yes_loses_only_its_instruction():
    questions = [v for k, v in __import__("json").loads((text.DATA_DIR / "en.json").read_text(encoding="utf-8"))["strings"].items()
                 if (k.startswith("rounds.") or k.startswith("voicefile.")) and k.rsplit(".", 1)[-1] in ("question", "question_clear")]
    assert len(questions) >= 8
    for question in questions:
        filled = question.replace("{number}", "3").replace("{note}", "first try").replace("{size}", "4.2 GB").replace("{round}", "3")
        shown = wio.question_text(filled)
        assert "Type yes" not in shown and shown and shown[-1] in ".?" or shown.endswith("first try"), question
        assert filled.startswith(shown) and len(shown) < len(filled), question
    assert any("{note}" in q for q in questions)


# ---------------------------------------------------------------- the IO

def test_what_the_flow_says_is_passed_on_and_its_own_heading_is_left_out():
    sink = FakeSink()
    io = wio.ChannelIO(sink, titles=["ACK Voice Studio: training rounds"])
    io.say("ACK Voice Studio: training rounds")
    io.say("hello")
    io.say("  indented")
    assert sink.said == ["hello", "  indented"] and io.lines == ("hello", "  indented")


def test_a_confirmation_waits_for_the_answer_and_is_shown_what_was_said_since_the_last_question():
    sink = FakeSink(confirms=[True, False])
    io = wio.ChannelIO(sink)
    io.say("one")
    io.say("two")
    assert io.confirm("Go on? Type yes to go.") is True
    io.say("three")
    assert io.confirm("Again? Type yes to go.") is False
    assert sink.questions == [("confirm", ("one", "two"), "Go on?"), ("confirm", ("three",), "Again?")]


def test_a_typed_question_gets_the_text_and_is_trimmed_of_its_trailing_space():
    sink = FakeSink(asks=["Anna", None])
    io = wio.ChannelIO(sink)
    assert io.ask("What name? ") == "Anna" and io.ask("Again?") is None
    assert sink.questions[0] == ("ask", (), "What name?")


def test_closing_the_window_releases_a_waiting_flow_with_nobody_there_and_no_later_question_is_asked():
    sink = FakeSink(confirms=[wio_never])
    io = wio.ChannelIO(sink)
    answers = []
    thread = threading.Thread(target=lambda: answers.append(io.confirm("Wait? Type yes.")))
    thread.start()
    time.sleep(0.1)
    assert thread.is_alive() and sink.questions
    io.cancel()
    thread.join(5)
    assert answers == [None] and not thread.is_alive()
    before = len(sink.questions)
    assert io.confirm("Later? Type yes.") is None and io.ask("Later?") is None and len(sink.questions) == before


def test_a_close_that_comes_just_before_the_wait_is_not_lost():
    io = wio.ChannelIO(FakeSink())
    io.cancel()
    assert io.confirm("Anything? Type yes.") is None


# ---------------------------------------------------------------- the run

def test_a_run_reports_the_exit_code_and_everything_that_was_said():
    sink = FakeSink(confirms=[True])

    def flow(io):
        io.say("plan")
        return 0 if io.confirm("Do it? Type yes to do it.") else 2
    handle = run(flow, sink)
    assert sink.result == (0, ("plan",)) and sink.questions == [("confirm", ("plan",), "Do it?")]
    handle.thread.join(2)
    assert not handle.active and handle.thread.daemon


def test_a_flow_that_crashes_is_reported_as_a_problem_with_the_windows_own_words_and_the_error_name():
    sink = FakeSink()

    def flow(io):
        io.say("before")
        raise KeyError("boom")
    run(flow, sink, crashed="Something went wrong inside the window.")
    code, lines = sink.result
    assert code == wio.EXIT_PROBLEM and lines[0] == "before" and lines[1] == "Something went wrong inside the window." and lines[2].startswith("KeyError: ")


def test_a_cancelled_run_finishes_instead_of_waiting_for_ever():
    sink = FakeSink(confirms=[wio_never])
    finished = threading.Event()

    def flow(io):
        answer = io.confirm("Wait? Type yes.")
        finished.set()
        return 2 if answer is None else 0
    handle = wio.start_run(flow, sink)
    time.sleep(0.1)
    assert handle.active
    handle.cancel()
    assert sink.done.wait(5) and finished.is_set() and sink.result[0] == 2
