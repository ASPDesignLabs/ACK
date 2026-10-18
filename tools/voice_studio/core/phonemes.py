# SPDX-License-Identifier: GPL-3.0-or-later
"""The phone's list of sounds, made the way the phone makes it, so a preview on the computer says what the phone will say (plan task VS-5.4).

ACK on the phone hands sherpa-onnx a `tokens.txt` that it writes from the voice's settings file every time the voice loads
(`PiperVoiceEngine.generateTokensFile`, app/src/main/java/com/example/besu/output/PiperVoiceEngine.kt). This is the same rule in plain Python:

* the settings file's `phoneme_id_map` is read; its entries are the sounds the voice was trained on, each with a list of ids;
* the entry for the line-break character is left out (it would break the file's one-sound-per-line shape), and so is every sound that is not exactly one Unicode
  character (sherpa-onnx's reader has no way to hold one; it stops the whole program when it meets one, which is also what the phone would do without the rule);
* what is left is sorted by the first id of each entry (entries with the same id stay in the order they were written) and written as `<sound> <id>`, one per line.

`tests/test_vs_phonemes_contract.py` reads the phone's source and fails if its rule changes, and an optional test checks the output against the real sherpa-onnx.
Nothing here reads a file or starts a program: it turns text into text.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import List, Tuple

ERROR_CODES = ("not_json", "no_map", "bad_entry")          # each has words in the text catalog
LINE_BREAK = "\n"
INT_MIN, INT_MAX = -2 ** 31, 2 ** 31 - 1                   # Kotlin's Int: a number outside it makes the phone give up


class TokensError(Exception):
    """`code` is one of ERROR_CODES; `detail` is a short fact (never a sound or a word from a person's text) for Show details."""

    def __init__(self, code: str, detail: str = ""):
        super().__init__(code + (": " + detail if detail else ""))
        self.code = code
        self.detail = detail


@dataclass(frozen=True)
class Tokens:
    text: str                           # the whole file, ready to write as UTF-8
    kept: int                           # how many sounds are in it
    skipped: Tuple[str, ...]            # the sounds the phone leaves out (the line break is not counted: it is never a sound)


def tokens_text(config_text: str) -> Tokens:
    """The `tokens.txt` the phone would write for this settings file, or a TokensError that says why there cannot be one (the phone then loads nothing)."""
    try:
        data = json.loads(config_text)
    except (ValueError, RecursionError):
        raise TokensError("not_json")
    mapping = data.get("phoneme_id_map") if isinstance(data, dict) else None
    if not isinstance(mapping, dict):
        raise TokensError("no_map")
    rows: List[Tuple[int, str]] = []
    skipped: List[str] = []
    for symbol, ids in mapping.items():
        if symbol == LINE_BREAK:
            continue
        if len(symbol) != 1:                                    # Python counts characters as the phone counts Unicode code points
            skipped.append(symbol)
            continue
        # Like the phone, an entry is only looked into after the ones it leaves out are gone. Stricter than the phone in one way: a number written as text ("5") is refused.
        if not (isinstance(ids, list) and ids and isinstance(ids[0], int) and not isinstance(ids[0], bool) and INT_MIN <= ids[0] <= INT_MAX):
            raise TokensError("bad_entry", "an entry has no whole number to sort by")
        try:
            symbol.encode("utf-8")
        except UnicodeEncodeError:
            raise TokensError("bad_entry", "a sound cannot be written")
        rows.append((ids[0], symbol))
    rows.sort(key=lambda row: row[0])                           # stable, like Kotlin's sortedBy
    return Tokens("".join("%s %d\n" % (symbol, number) for number, symbol in rows), len(rows), tuple(skipped))
