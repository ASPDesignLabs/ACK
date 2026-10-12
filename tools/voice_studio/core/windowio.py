# SPDX-License-Identifier: GPL-3.0-or-later
"""The bridge between the window and the flows that already do the work (plan task VS-2.1): a flow runs in a worker thread with an IO whose questions are answered by the window.

The window never decides what a step does. It runs the very flow the terminal runs (`rounds`, `voicefile`), so every plan is shown, every question is asked first and every sentence
is the one the person has already seen on the command line. The only difference is how a question is answered: a confirmation is a Yes and a No button (No is where the focus starts),
not a typed word. This module imports no GTK; the window supplies a `Sink` that moves each call onto its own thread.

Nothing here keeps what the flow said beyond the run, and nothing is written to disk.
"""
from __future__ import annotations

import re
import threading
from dataclasses import dataclass
from typing import Callable, List, Optional, Protocol, Sequence, Tuple

EXIT_PROBLEM = 1
INSTRUCTION = "Type yes"
INSTRUCTION_REST = re.compile(r"Type yes[^.?!]*[.?!]?\s*")


def question_text(prompt: str) -> str:
    """The question without the instruction to type a word: a window shows 'Remove all of that, about 4.2 GB? This cannot be undone.' above a Yes and a No button.
    Only the last 'Type yes ...' is the instruction, and only if it is the end of the prompt: words the person typed (a note that says 'Type yes') are left exactly as they are."""
    at = prompt.rfind(INSTRUCTION)
    if at >= 0 and INSTRUCTION_REST.fullmatch(prompt, at):
        stripped = prompt[:at].rstrip()
        return stripped if stripped else prompt.strip()
    return prompt.strip()


class Sink(Protocol):
    """Where a run's words and questions go. Every method may be called from the worker thread; an implementation moves the call to the window's thread.
    `reply` must be called exactly once per question, from any thread, however the person closes the question."""

    def line(self, text: str) -> None: ...
    def confirm(self, lines: Tuple[str, ...], question: str, reply: Callable[[bool], None]) -> None: ...
    def ask(self, lines: Tuple[str, ...], prompt: str, reply: Callable[[Optional[str]], None]) -> None: ...
    def finished(self, code: int, lines: Tuple[str, ...]) -> None: ...


class ChannelIO:
    """The IO a flow is given. `confirm` is what makes rounds_flow ask with buttons; `ask` is for a flow that wants a typed answer."""

    interactive = True

    def __init__(self, sink: Sink, titles: Sequence[str] = ()):
        self._sink = sink
        self._titles = frozenset(titles)
        self._lines: List[str] = []
        self._since_question: List[str] = []
        self._answer: Optional[object] = None
        self._answered = threading.Event()
        self._cancelled = False

    @property
    def lines(self) -> Tuple[str, ...]:
        return tuple(self._lines)

    def say(self, text: str) -> None:
        if text in self._titles:
            return                                                    # the flow's own heading: the window has its own
        self._lines.append(text)
        self._since_question.append(text)
        self._sink.line(text)

    def _wait(self, start: Callable[[Callable[[object], None]], None]) -> Optional[object]:
        if self._cancelled:
            return None
        self._answer = None
        self._answered.clear()
        if self._cancelled:                                           # the window closed between the two lines above: its release would otherwise be lost
            return None

        def reply(value: object) -> None:
            self._answer = value
            self._answered.set()

        start(reply)
        self._answered.wait()
        self._since_question = []
        return self._answer

    def confirm(self, prompt: str) -> Optional[bool]:
        """True or False when the person answered; None when there was nobody to ask (the window was closed)."""
        shown = tuple(self._since_question)
        answer = self._wait(lambda reply: self._sink.confirm(shown, question_text(prompt), reply))
        return None if answer is None else bool(answer)

    def ask(self, prompt: str) -> Optional[str]:
        shown = tuple(self._since_question)
        answer = self._wait(lambda reply: self._sink.ask(shown, prompt.strip(), reply))
        return None if answer is None else str(answer)

    def cancel(self) -> None:
        """The window is going away: any question waiting is answered with 'nobody there', and no later one is asked."""
        self._cancelled = True
        self._answer = None
        self._answered.set()


@dataclass
class Run:
    """One flow running in a worker thread. `finished` is told the exit code and everything the flow said."""

    io: ChannelIO
    thread: threading.Thread

    @property
    def active(self) -> bool:
        return self.thread.is_alive()

    def cancel(self) -> None:
        self.io.cancel()


def start_run(flow: Callable[[ChannelIO], int], sink: Sink, titles: Sequence[str] = (), crashed: str = "") -> Run:
    """Run `flow(io)` in a daemon thread (a closed window must not keep the program alive). A flow that raises is reported as a problem with `crashed`, never left silent."""
    io = ChannelIO(sink, titles)

    def work() -> None:
        try:
            code = flow(io)
        except Exception as error:                                  # a bug must show up in the window, not vanish with the thread
            if crashed:
                io.say(crashed)
            io.say("%s: %s" % (type(error).__name__, str(error)[:200]))
            code = EXIT_PROBLEM
        sink.finished(code, io.lines)

    thread = threading.Thread(target=work, name="voice-studio-run", daemon=True)
    thread.start()
    return Run(io, thread)
