# SPDX-License-Identifier: GPL-3.0-or-later
"""Choosing a starting voice, and what has to happen before it is downloaded (plan task VS-4.1, decisions D25, D27, D30).

A starting voice is a checkpoint another person trained, offered by its original host. This project hosts, mirrors and sublicenses none of it and
says nothing about whether anyone's use of it is allowed (D27). What it does is make sure a person has been shown where the voice comes from before
the file is fetched, and keep a dated record of that:

  1. **Acknowledge** (per project): the person has been shown the chain (the voice, then lessac, then the Blizzard 2013 recordings) and each licence
     as its own page states it, and says so. It is recorded in the project with the date and the **exact revision** of the file (core/project.py), so a
     later re-pin to a different file asks again.
  2. **Agree to the download** (per computer): the saved agreement (core/consent.py) names this exact address, size and checksum. The setup run lists
     the voices but fetches none (D30); a voice that was declined there is agreed to here, and either way nothing is fetched on a yes that does not name it.
  3. **Fetch**: only when both of the above hold, into a kept folder of its own. A voice already on the disk and byte for byte right needs no network.

This file decides; it opens no page. The licence pages are *shown* (their addresses are in the registry, data/sources.json, where the person sees every
address before it is used) and are never fetched: the only network door is core/fetch.py, which only takes a pinned registry file. It says no words
either: statements are named by id and the words are in the text catalog (`startvoice.*`).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional, Tuple
from urllib.parse import urlparse

from . import connection, fetch
from .consent import ConsentRecord, load_consent, make_consent, merge_consent, save_consent
from .paths import DataHome
from .project import Project, with_acknowledgment, with_starting_voice
from .registry import Item, Registry

ERROR_CODES = ("unknown_voice", "not_pinned", "not_acknowledged", "not_agreed")          # each has words in the text catalog
STEPS = ("acknowledge", "agree", "download", "ready")                                    # what is left to do for a voice, in the order it is done; each has words
CHOICES = ("male", "female")                                                             # the plain choice a person makes (D25); each has words
FACTS_READ_ON = "2026-10-11"             # when the pages behind the statements below were read (THIRD_PARTY_NOTICES.md section 7); the screen says so
NOTICE_KEYS = ("startvoice.intro", "startvoice.head_start", "startvoice.read_on", "startvoice.not_advice", "startvoice.not_hosted")        # shown with every voice


class StartVoiceError(Exception):
    """`code` is a short word the screens turn into a plain sentence: unknown_voice, not_pinned, not_acknowledged, not_agreed."""

    def __init__(self, code: str, detail: str = ""):
        super().__init__(code + (": " + detail if detail else ""))
        self.code = code
        self.detail = detail


# ---------------------------------------------------------------- what is said about each voice

@dataclass(frozen=True)
class Link:
    id: str                          # `startvoice.link.<id>.name`, and the name of the registry page (Item.pages) that states its licence
    statements: Tuple[str, ...]      # `startvoice.says.<statement>`, in the order they are shown


@dataclass(frozen=True)
class VoiceFacts:
    voice_id: str                    # the registry entry
    choice: str                      # one of CHOICES
    links: Tuple[Link, ...]          # where it comes from, nearest first


LESSAC = Link("lessac", ("lessac_origin", "lessac_terms", "lessac_ends", "lessac_unsettled"))
FACTS = (
    VoiceFacts("voice-mike", "male", (Link("mike", ("mike_recordings", "made_from_lessac")), LESSAC)),
    VoiceFacts("voice-amy", "female", (Link("amy", ("amy_recordings", "made_from_lessac")), LESSAC)),
)
LINK_IDS = tuple(sorted({link.id for facts in FACTS for link in facts.links}))
STATEMENTS = tuple(sorted({s for facts in FACTS for link in facts.links for s in link.statements}))


@dataclass(frozen=True)
class CardLink:
    id: str
    page: Optional[str]              # the address of the page that states the licence, to read; None if the registry has none (never opened by this tool)
    statements: Tuple[str, ...]


@dataclass(frozen=True)
class VoiceCard:
    """Everything a screen needs to show one starting voice before anything is fetched."""
    voice_id: str
    choice: str
    size_bytes: int                  # exact once pinned, otherwise what the host shows
    exact: bool
    revision: Optional[str]
    host: Optional[str]              # the site the file comes from, by name
    pinned: bool
    problems: Tuple[str, ...]
    links: Tuple[CardLink, ...]
    read_on: str


def _facts(voice_id: str) -> VoiceFacts:
    for facts in FACTS:
        if facts.voice_id == voice_id:
            return facts
    raise StartVoiceError("unknown_voice", str(voice_id)[:80])


def _voice(registry: Registry, voice_id: str) -> Item:
    _facts(voice_id)
    try:
        item = registry.get(voice_id)
    except KeyError:
        raise StartVoiceError("unknown_voice", str(voice_id)[:80])
    if item.kind != "voice":
        raise StartVoiceError("unknown_voice", str(voice_id)[:80])
    return item


def _pinned_voice(registry: Registry, voice_id: str) -> Item:
    item = _voice(registry, voice_id)
    problems = item.pin_problems()
    if problems:
        raise StartVoiceError("not_pinned", ",".join(problems))          # nothing exact to acknowledge or agree to yet
    return item


def card(registry: Registry, voice_id: str) -> VoiceCard:
    item = _voice(registry, voice_id)
    facts = _facts(voice_id)
    host = urlparse(item.url).hostname if item.url else None
    links = tuple(CardLink(link.id, item.page(link.id), link.statements) for link in facts.links)
    return VoiceCard(item.id, facts.choice, item.size_for_budget or 0, item.size_bytes is not None, item.revision, host, item.pinned,
                     tuple(item.pin_problems()), links, FACTS_READ_ON)


def voices(registry: Registry) -> Tuple[VoiceCard, ...]:
    """The starting voices this registry has, in the order the plan lists them. The order is not a recommendation."""
    present = {item.id for item in registry.items if item.kind == "voice"}
    return tuple(card(registry, facts.voice_id) for facts in FACTS if facts.voice_id in present)


def find_voice(registry: Registry, typed: str) -> Optional[str]:
    """The voice a person means by "mike", "Mike" or "voice-mike": its id, or None if it is none of the voices this registry has."""
    word = " ".join(str(typed).split()).lower()
    for entry in voices(registry):
        if word in (entry.voice_id, entry.voice_id[len("voice-"):]):
            return entry.voice_id
    return None


# ---------------------------------------------------------------- choosing, and the two yeses

def choose(project: Project, registry: Registry, voice_id: str) -> Project:
    """Name the voice this project starts from. Only a voice the tool knows; choosing fetches nothing and acknowledges nothing."""
    return with_starting_voice(project, _voice(registry, voice_id).id)


def acknowledged(project: Project, registry: Registry, voice_id: str) -> bool:
    """True only for an acknowledgment of **this** file: the same voice at the same revision the registry names now."""
    item = _voice(registry, voice_id)
    return item.revision is not None and any(a.voice == item.id and a.revision == item.revision for a in project.acknowledgments)


def acknowledge(project: Project, registry: Registry, voice_id: str, now: Optional[datetime] = None) -> Project:
    """Record, with the date and the registry's exact revision, that the person was shown where this voice comes from. The revision is never typed in:
    it is the one the file will be fetched at. A second acknowledgment of the same revision adds nothing."""
    item = _pinned_voice(registry, voice_id)
    return with_acknowledgment(project, item.id, item.revision, now)


def agree_to_download(registry: Registry, voice_id: str, home: DataHome, now: Optional[datetime] = None) -> ConsentRecord:
    """The person's yes to downloading this one file (its exact address, size and checksum), saved owner-only and merged with every earlier yes."""
    item = _pinned_voice(registry, voice_id)
    record = merge_consent(load_consent(Path(home.consent_file)), make_consent([item], now=now))
    save_consent(Path(home.consent_file), record)
    return record


# ---------------------------------------------------------------- the kept file

def voice_folder(home: DataHome, item: Item) -> Path:
    return Path(home.voices) / item.id


def kept_path(home: DataHome, registry: Registry, voice_id: str) -> Optional[Path]:
    """The file if it is on this computer and is byte for byte what the registry names (read from the disk, never the network); otherwise None."""
    item = _voice(registry, voice_id)
    folder = voice_folder(home, item)
    return folder / item.filename if fetch.is_fetched(item, folder) and item.filename else None


def next_step(project: Project, registry: Registry, voice_id: str, home: DataHome) -> str:
    """What is left to do for this voice, one of STEPS. The acknowledgment comes first and is needed in every project, even when the file is already
    here from another one; the download agreement is needed only when the file still has to be fetched."""
    item = _pinned_voice(registry, voice_id)
    if not acknowledged(project, registry, voice_id):
        return "acknowledge"
    if kept_path(home, registry, voice_id) is not None:
        return "ready"
    consent = load_consent(Path(home.consent_file))
    return "download" if consent is not None and consent.covers(item) else "agree"


def fetch_voice(project: Project, registry: Registry, voice_id: str, home: DataHome, *, on_wait: Callable[[connection.Wait], None],
                on_back: Callable[[], None], sleep: Callable[[float], None], clock: Callable[[], float],
                patience: connection.Patience = connection.DEFAULT_PATIENCE, cancelled: Optional[Callable[[], bool]] = None,
                fetcher: Optional[Callable] = None, progress: Optional[Callable[[int, int], None]] = None) -> Path:
    """The kept file, fetching it first if it is not already here. Refuses (nothing requested, nothing written) unless this project has acknowledged
    this exact revision, and, when the file has to be downloaded, the saved agreement names this exact file. A dropped connection is waited out by
    core/fetch.py; any other failure is raised as the download module's own error."""
    item = _pinned_voice(registry, voice_id)
    if not acknowledged(project, registry, voice_id):
        raise StartVoiceError("not_acknowledged", item.id)
    folder = voice_folder(home, item)
    if fetch.is_fetched(item, folder):
        return folder / item.filename
    consent = load_consent(Path(home.consent_file))
    if consent is None or not consent.covers(item):
        raise StartVoiceError("not_agreed", item.id)
    return fetch.fetch_patiently(item, folder, consent, on_wait=on_wait, on_back=on_back, sleep=sleep, clock=clock, patience=patience,
                                 cancelled=cancelled, fetcher=fetcher, progress=progress)
