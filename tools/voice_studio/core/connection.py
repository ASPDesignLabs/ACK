# SPDX-License-Identifier: GPL-3.0-or-later
"""Carrying on by itself when the internet connection drops for a while (plan finding F20, decision D35).

Plain Python: no network and no clock of its own. Time and sleeping are handed in, so every rule here is tested without waiting.

What was measured (a local package server that misbehaves on purpose, against pip 22.0.2 and 24.0, the two that Ubuntu 22.04 and 24.04 ship, and 26.2.1):

* **A download cut off half way is reported as a checksum mismatch**, the message that reads like tampering ("THESE PACKAGES DO NOT MATCH THE HASHES"),
  because pip's own copy of the HTTP library does not check the length. This is the most likely thing a dropped connection looks like, so a mismatch
  is treated as "maybe the connection" and tried again; **pip itself never installs a file that does not match**, so trying again can only cost time.
  A wrong file that arrives the same way twice is not the connection: the tries stop and say so.
* A connection that is reset, or goes quiet, in the middle of a file ends in a Python traceback and exit code 2; one that cannot be made at all
  ends in "No matching distribution found" after pip's own five quick tries. Both name the cause in the last lines.
* A certificate problem prints the same "Retrying" lines as a dropped connection. Waiting cannot fix it, so it is never waited for.
* pip 25.1 and later pick an interrupted download up again on their own, and name it ("incomplete-download ... an issue with network connectivity"). The loop
  here is for what they cannot mend and for the older pip that Ubuntu's own Python brings.
* A second run of the same command reuses every file that finished downloading and discards the one that did not, so trying again costs only the
  file that was in flight.

So the rule is: run the same command again, after a pause, for as long as the evidence says the connection is the problem and is still within the
patience; say plainly what is happening; give up with a clear message when the patience runs out.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable, Optional, Tuple, TypeVar

T = TypeVar("T")

PATIENCE_S = 30 * 60               # how long the connection may stay away before this stops trying
PAUSES_S = (5, 10, 20, 30, 60)     # the waits between tries; the last one repeats
PROGRESS_S = 60                    # a try that ran this long before it failed got somewhere, so the waiting starts afresh
WINDOW_LINES = 80                  # the end of a command's output is where the cause is; a traceback is about 40 lines

# What a dropped connection prints, lower case. Taken from real runs (see the docstring); each is held by a test.
LOST_MARKERS = (
    "retrying (retry(",                          # pip's own quick tries, printed before it gives up
    "failed to establish a new connection",
    "max retries exceeded",
    "connection broken",                         # urllib3's ProtocolError, from a reset or a short body
    "connection reset",
    "connection aborted",
    "remote end closed connection",
    "timed out",                                 # a read, a connect or a quiet server; one phrase covers pip, urllib3 and the system's own
    "protocolerror",
    "connection interrupted while downloading",   # pip 25.1 and later say it outright, and can pick the download up again themselves
    "incomplete-download",
    "issue with network connectivity",
    "chunkedencodingerror",
    "incompleteread",
    "temporary failure in name resolution",
    "name or service not known",
    "network is unreachable",
    "no route to host",
)

# Things that look like the connection but that waiting cannot fix. Checked before the markers above.
NOT_A_DROP_MARKERS = (
    "certificate verify failed",                 # a proxy or a login page in the way: pip prints the same "Retrying" lines for it
    "problem confirming the ssl certificate",
    "no space left on device",
    "disk quota exceeded",
    "read-only file system",
    "permission denied",
    "404 client error",
    "403 client error",
    "401 client error",
    "proxy authentication required",
    "in --require-hashes mode",                  # the list itself is wrong
    "is not a supported wheel",
)

MISMATCH_MARKER = "these packages do not match the hashes"
_GOT = re.compile(r"^\s*Got\s+([0-9a-fA-F]{64})\s*$", re.MULTILINE)


@dataclass(frozen=True)
class PipOutcome:
    kind: str                                    # "lost" (the connection), "mismatch" (a file came out wrong) or "other"
    signature: Optional[Tuple[str, ...]] = None  # for a mismatch: what came out, so the same wrong file twice can be told from a cut-off one


def classify_pip(output: str) -> PipOutcome:
    """What a failed `pip install` was about, from the end of what it printed."""
    text = "\n".join(output.splitlines()[-WINDOW_LINES:])
    lower = text.lower()
    if MISMATCH_MARKER in lower:
        got = tuple(sorted(m.lower() for m in _GOT.findall(text)))
        return PipOutcome("mismatch", got or ("unreadable",))
    if any(marker in lower for marker in NOT_A_DROP_MARKERS):
        return PipOutcome("other")
    if any(marker in lower for marker in LOST_MARKERS):
        return PipOutcome("lost")
    return PipOutcome("other")


def raise_if_connection(returncode: int, output: str) -> None:
    """After a failed `pip install`: raise ConnectionLost if the output says the connection (or a file cut off on the way) was the reason. Otherwise
    return, and the caller reports an ordinary failure."""
    outcome = classify_pip(output)
    if outcome.kind in ("lost", "mismatch"):
        raise ConnectionLost("exit %d" % returncode, outcome.signature)           # only a mismatch has one


def fetch_lost(code: str, detail: str) -> bool:
    """Whether a failed download (core/fetch.py's error code and detail) is the connection, or a server having a bad moment, rather than the file or the disk."""
    if code == "size":
        return True                              # fewer bytes than expected: the rest can be asked for, the part already kept is resumed
    if code != "http":
        return False
    if detail.isdigit():
        return detail == "429" or detail.startswith("5")      # too many requests, or the server's own trouble; 403 and 404 are real answers
    return True                                  # no answer at all: a refused or reset connection, a timeout, a name that did not resolve


@dataclass(frozen=True)
class Patience:
    total_s: int = PATIENCE_S
    pauses_s: Tuple[int, ...] = PAUSES_S
    progress_s: int = PROGRESS_S

    def pause(self, tries: int) -> int:
        return self.pauses_s[min(tries, len(self.pauses_s) - 1)]


DEFAULT_PATIENCE = Patience()


@dataclass(frozen=True)
class Wait:
    """One pause, as the screen should tell it."""
    pause_s: int          # until the next try
    waited_s: int         # how long the connection has been away in this spell
    budget_s: int         # how long in all this will keep trying
    first: bool           # the first pause of a spell (it gets the longer explanation)


class ConnectionLost(Exception):
    """Raised by an attempt that failed because of the connection. `signature` is set for a file that came out wrong."""

    def __init__(self, detail: str = "", signature: Optional[Tuple[str, ...]] = None):
        super().__init__(detail)
        self.detail = detail
        self.signature = signature


class ConnectionGaveUp(Exception):
    """The connection did not come back within the patience."""

    def __init__(self, detail: str, waited_s: int):
        super().__init__(detail)
        self.detail = detail
        self.waited_s = waited_s


class NotTheConnection(Exception):
    """The same wrong file came out twice in a row: that is not a connection that dropped."""

    def __init__(self, detail: str):
        super().__init__(detail)
        self.detail = detail


def keep_trying(attempt: Callable[[], T], *, on_wait: Callable[[Wait], None], on_back: Callable[[], None], sleep: Callable[[float], None],
                clock: Callable[[], float], patience: Patience = DEFAULT_PATIENCE) -> T:
    """Run `attempt` until it returns. It raises ConnectionLost when the connection is the reason it failed (anything else it raises is passed on
    untouched, and ends this). Between tries it says so (`on_wait`), waits (`sleep`), and says when it is over (`on_back`).
    Raises ConnectionGaveUp once the connection has been away for `patience.total_s`, and NotTheConnection if the same wrong file comes out twice.
    Ctrl+C during a wait goes straight through."""
    spell_began: Optional[float] = None
    tries = 0
    last_signature: Optional[Tuple[str, ...]] = None
    while True:
        started = clock()
        try:
            value = attempt()
        except ConnectionLost as lost:
            now = clock()
            if spell_began is not None and now - started >= patience.progress_s:
                on_back()                                  # it was back for a good while and got somewhere; this is a new spell
                spell_began, tries, last_signature = None, 0, None
            if lost.signature is not None and lost.signature == last_signature:
                raise NotTheConnection(lost.detail)
            last_signature = lost.signature
            if spell_began is None:
                spell_began = now
            waited = now - spell_began
            if waited >= patience.total_s:
                raise ConnectionGaveUp(lost.detail, int(waited))
            pause = patience.pause(tries)
            on_wait(Wait(pause, int(waited), patience.total_s, tries == 0))
            sleep(pause)
            tries += 1
        else:
            if spell_began is not None:
                on_back()
            return value
