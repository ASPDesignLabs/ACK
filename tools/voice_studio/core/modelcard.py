# SPDX-License-Identifier: GPL-3.0-or-later
"""The card that sits beside a voice file (plan task VS-5.2, decisions D21 and D27, choices P27): where the voice comes from, how it was made, and what was recorded about whose voice it is.

It is written from what the project stored and nothing else, and it says so. Three rules come from the decisions:

* **D27, declare and do not host.** It names the starting voice the training began from, the chain behind it, and the pages that state the terms, in the very words shown before the voice was
  downloaded (the catalog's `startvoice.*`), with the date and revision the person acknowledged. It gives no legal advice and never says or suggests that use is allowed; it says that sharing or
  publishing the voice is a separate decision.
* **D21, the consent note stays with the project.** The card says whether the project was set up as the person's own voice or as someone else's, and for someone else's, in which of the fixed
  ways the note says the agreement was given. It never copies a name, a date or a word of the note.
* **Nothing personal, nothing guessed.** No project name, person's name, recording, transcript, path or address of this computer. When a fact is not recorded (the starting voice, the acknowledgment,
  the training programs) the card says it is not recorded; it does not fill the gap from somewhere else.

The card is a separate file in the voice file's folder, never inside the zip (ACK takes exactly two files from the zip). This module decides and builds the text; core/voicefile.py writes it last,
after the zip has been read back as the phone would.
"""
from __future__ import annotations

import os
import re
import tempfile
from dataclasses import dataclass
from typing import Optional, Tuple

from . import project as pj, rounds as rd, startvoice
from .registry import Registry
from .text import Catalog, size_text

CARD_NAME = "MODEL_CARD.txt"
SAFE_WORD = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,59}\Z")          # an id or a revision read from a file the person could have edited: only plain words are copied into the card
MAX_LINE = 400


@dataclass(frozen=True)
class CardInput:
    zip_bytes: int
    model_sha256: str
    config_sha256: str
    made_at: str                                  # UTC, "2026-10-11T13:00:00Z"
    round_number: int
    rounds: int                                   # the rounds this voice's training is made of (core/rounds.py::lineage)
    trained_minutes: int
    recorded_voice: str                           # the starting voice the first round of that training names; "" when it names none
    start: Optional[startvoice.VoiceCard]         # what the tool knows about that voice; None when it is not one it knows
    acknowledgments: Tuple[Tuple[str, str], ...]  # (date, revision) the project recorded for that voice, oldest first
    whose_voice: str                              # core/project.py OWN or SOMEONE_ELSE
    how_given: str                                # one of core/project.py HOW_GIVEN, or "" when there is none
    note_complete: bool
    tool_version: str
    programs_id: str                              # "" when the training programs' record could not be read
    programs_build: str


@dataclass(frozen=True)
class Card:
    text: str

    def to_bytes(self) -> bytes:
        return self.text.encode("utf-8")


def _safe(value: object) -> str:
    return value if isinstance(value, str) and SAFE_WORD.match(value) else ""


def lineage_start(record: rd.Record, number: int) -> Tuple[int, str]:
    """(how many rounds the voice at round `number` is made of, the starting voice the first of them names). The voice is "" when the training does not trace back to a round that
    started from a starting voice (a broken chain, or a round that did not record one): the card then says so instead of using another source."""
    chain = rd.lineage(record, number)
    if not chain or chain[0].parent != 0:
        return len(chain), ""
    return len(chain), _safe(chain[0].voice)


def gather(record: rd.Record, number: int, the_project: pj.Project, registry: Optional[Registry], *, zip_bytes: int, model_sha256: str, config_sha256: str,
           made_at: str, tool_version: str, programs: Optional[dict]) -> CardInput:
    """Everything the card says, read from what is stored. `programs` is the training programs' record (core/envbuild.py::read_record) or None."""
    rounds, voice = lineage_start(record, number)
    start: Optional[startvoice.VoiceCard] = None
    if voice and registry is not None:
        try:
            start = startvoice.card(registry, voice)
        except startvoice.StartVoiceError:
            start = None
    acks = tuple(sorted((pj.clean_text(a.at, 10), pj.clean_text(a.revision, 64)) for a in the_project.acknowledgments if voice and a.voice == voice))
    problems = pj.consent_problems(the_project)
    fingerprint = programs.get("fingerprint") if isinstance(programs, dict) else None
    return CardInput(zip_bytes=zip_bytes, model_sha256=model_sha256, config_sha256=config_sha256, made_at=made_at, round_number=number, rounds=rounds,
                     trained_minutes=rd.trained_minutes(record, number), recorded_voice=voice, start=start, acknowledgments=acks, whose_voice=the_project.whose_voice,
                     how_given=the_project.consent.how_given if the_project.consent.how_given in pj.HOW_GIVEN else "", note_complete=not problems, tool_version=_safe(tool_version),
                     programs_id=_safe(programs.get("id")) if isinstance(programs, dict) else "", programs_build=_safe(fingerprint[:10]) if isinstance(fingerprint, str) else "")


def _when(stamp: str) -> str:
    """`2026-10-11 13:00 UTC` from `2026-10-11T13:00:00Z`; a stamp in any other shape is shown as it is (cut short)."""
    match = re.match(r"^(\d{4}-\d{2}-\d{2})T(\d{2}:\d{2}):\d{2}Z\Z", stamp)
    return "%s %s UTC" % match.groups() if match else stamp[:30]


def _origin(inp: CardInput, cat: Catalog) -> list:
    lines = []
    if not inp.recorded_voice:
        return [cat.t("modelcard.origin.not_recorded")]
    if inp.start is None:
        return [cat.t("modelcard.origin.unknown", voice=inp.recorded_voice)]
    first = inp.start.links[0]
    lines.append(cat.t("modelcard.origin.voice", name=cat.t("startvoice.link.%s.name" % first.id)))
    if inp.start.host:
        lines.append(cat.t("modelcard.origin.host", host=inp.start.host))
    for link in inp.start.links:
        lines.append("")
        lines.append(cat.t("startvoice.link.%s.name" % link.id))
        for statement in link.statements:
            lines.append("  " + cat.t("startvoice.says." + statement))
        if link.page:
            lines.append("  " + cat.t("modelcard.origin.page", address=link.page))
    lines.append("")
    lines.append(cat.t("startvoice.read_on", date=inp.start.read_on))
    if inp.acknowledgments:
        for date, revision in inp.acknowledgments:
            lines.append(cat.t("modelcard.origin.acknowledged", date=date, revision=revision))
    else:
        lines.append(cat.t("modelcard.origin.not_acknowledged"))
    lines.append(cat.t("startvoice.not_hosted"))
    lines.append(cat.t("startvoice.not_advice"))
    return lines


def _whose(inp: CardInput, cat: Catalog) -> list:
    if inp.whose_voice != pj.SOMEONE_ELSE:
        return [cat.t("modelcard.whose.own"), cat.t("modelcard.whose.unchecked")]
    lines = [cat.t("modelcard.whose.else")]
    if not inp.note_complete or not inp.how_given:                  # a note whose way is not one of the fixed ones is not summarised, whatever else is filled in
        lines.append(cat.t("modelcard.whose.note_incomplete"))
    else:
        lines.append(cat.t("modelcard.whose.note", how=cat.t("project.how_given." + inp.how_given)))
    lines.append(cat.t("modelcard.whose.unchecked"))
    return lines


def build_card(inp: CardInput, cat: Catalog) -> Card:
    """The card's text, in plain words, one fact to a line. Pure: it reads nothing."""
    lines = [cat.t("modelcard.title"), "", cat.t("modelcard.intro"), cat.t("modelcard.basis"), ""]
    lines += [cat.t("modelcard.head.file"),
              "  " + cat.t("modelcard.file.name", size=size_text(inp.zip_bytes)),
              "  " + cat.t("modelcard.file.made", when=_when(inp.made_at)),
              "  " + cat.t("modelcard.file.voice_code", code=inp.model_sha256),
              "  " + cat.t("modelcard.file.settings_code", code=inp.config_sha256), ""]
    lines += [cat.t("modelcard.head.origin")] + ["  " + l if l else "" for l in _origin(inp, cat)] + [""]
    lines += [cat.t("modelcard.head.training"),
              "  " + cat.t("modelcard.training.rounds", round=inp.round_number, rounds=inp.rounds, minutes=inp.trained_minutes),
              "  " + cat.t("modelcard.training.recordings"), ""]
    lines += [cat.t("modelcard.head.whose")] + ["  " + l for l in _whose(inp, cat)] + [""]
    lines += [cat.t("modelcard.head.made_with"), "  " + cat.t("modelcard.made.tool", version=inp.tool_version or "?")]
    if inp.programs_id:
        lines.append("  " + cat.t("modelcard.made.programs", id=inp.programs_id, build=inp.programs_build or "?"))
    else:
        lines.append("  " + cat.t("modelcard.made.programs_unknown"))
    lines += ["", cat.t("modelcard.head.holds"), "  " + cat.t("modelcard.holds.not"), "  " + cat.t("modelcard.holds.where"), "  " + cat.t("modelcard.holds.publish")]
    return Card("\n".join(line[:MAX_LINE] for line in lines) + "\n")


def write_card(folder: str, card: Card) -> str:
    """Save the card in `folder` as MODEL_CARD.txt, owner-only, through a temporary file so a stop leaves no half-written card. Never replaces a file: one already there raises
    FileExistsError. Returns the path. Any other failure raises OSError, with nothing of the card left behind."""
    path = folder + "/" + CARD_NAME
    if os.path.lexists(path):
        raise FileExistsError(path)
    fd, temp = tempfile.mkstemp(dir=folder, prefix=".card-", suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(card.to_bytes())
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temp, 0o600)
        os.rename(temp, path)
    except BaseException:
        try:
            os.unlink(temp)
        except OSError:
            pass
        raise
    return path
