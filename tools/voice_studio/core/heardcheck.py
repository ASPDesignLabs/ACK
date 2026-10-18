# SPDX-License-Identifier: GPL-3.0-or-later
"""What the computer heard the voice say, set beside what the voice was asked to say (plan task VS-5.5).

After the sound files are made, the listening model (the same one that writes down recordings) can write down what it hears in each, so a person who cannot judge the sound can read
whether the words came out. This module only compares two pieces of text and cleans one for the screen; it hears nothing itself.

It is a hint, not a verdict: a listening program mishears names, numbers and unusual words, and the voice may be fine when it does. The comparison is by words only (capital letters,
punctuation and a typographic apostrophe are ignored) and says one of three things: the same words, different words, or nothing it could write down.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Tuple

SAME, DIFFERENT, NOTHING = "same", "different", "nothing"
MAX_SHOWN = 200
WORD = re.compile(r"[^\W_]+(?:'[^\W_]+)*")


def words(text: str) -> Tuple[str, ...]:
    """The words of a text for comparing: letters and digits of any script, an apostrophe inside a word kept, everything else a break."""
    return tuple(WORD.findall(unicodedata.normalize("NFKC", text).lower().replace("’", "'")))


def for_the_screen(text: str) -> str:
    """The heard text as one tidy line: control characters become spaces, then every run of white space (line breaks and no-break spaces included) becomes one space, and a very long text is cut with an ellipsis."""
    line = " ".join("".join(" " if unicodedata.category(c).startswith("C") else c for c in text).split())
    return line if len(line) <= MAX_SHOWN else line[:MAX_SHOWN - 1].rstrip() + "…"


@dataclass(frozen=True)
class Check:
    kind: str                    # SAME, DIFFERENT or NOTHING
    heard: str                   # ready to show; empty for NOTHING


def compare(wanted: str, heard: str) -> Check:
    got = words(heard)
    if not got:
        return Check(NOTHING, "")
    return Check(SAME if got == words(wanted) else DIFFERENT, for_the_screen(heard))
