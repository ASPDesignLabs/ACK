# SPDX-License-Identifier: GPL-3.0-or-later
"""Reading the words typed after a terminal command (the fronts for projects and starting voices).

Small and strict on purpose: an option it does not know, a value that is missing and an option given twice are all reported, never guessed at, because
guessing in a command that edits a person's files is how a typo becomes a change. `--name Anna` and `--name=Anna` mean the same. A value that begins with
`--` can only be given in the `=` form, so `--name --own` reads as "the name is missing", not as a person called "--own". Everything after a bare `--` is a
word, not an option. This decides; it prints nothing.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import FrozenSet, Mapping, Sequence, Tuple


class ArgError(Exception):
    """`code`: unknown (an option that does not exist), missing_value, repeated, extra_word (more words than the command takes)."""

    def __init__(self, code: str, arg: str):
        super().__init__(code + ": " + arg)
        self.code = code
        self.arg = arg


@dataclass(frozen=True)
class Parsed:
    flags: FrozenSet[str] = frozenset()               # names of the yes/no options that were given
    values: Mapping[str, str] = field(default_factory=dict)       # name -> what was typed after the option
    words: Tuple[str, ...] = ()                       # the words that were not options, in order


def parse_args(argv: Sequence[str], *, flags: Mapping[str, str], values: Mapping[str, str], max_words: int) -> Parsed:
    """`flags` maps an option to its name ("--yes" -> "yes"); `values` maps an option that takes a value ("--name" -> "name")."""
    found_flags = set()
    found_values = {}
    words = []
    items = list(argv)
    only_words = False
    i = 0
    while i < len(items):
        arg = items[i]
        i += 1
        if only_words or not arg.startswith("-") or arg == "-":
            words.append(arg)
        elif arg == "--":
            only_words = True
        elif arg in flags:
            found_flags.add(flags[arg])
        else:
            option, equals, attached = arg.partition("=")
            if option not in values:
                raise ArgError("unknown", arg)
            name = values[option]
            if name in found_values:
                raise ArgError("repeated", option)
            if equals:
                found_values[name] = attached
            elif i < len(items) and not items[i].startswith("--"):
                found_values[name] = items[i]
                i += 1
            else:
                raise ArgError("missing_value", option)
        if len(words) > max_words:
            raise ArgError("extra_word", words[max_words])
    return Parsed(frozenset(found_flags), found_values, tuple(words))
