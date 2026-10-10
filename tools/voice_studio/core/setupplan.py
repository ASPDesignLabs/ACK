# SPDX-License-Identifier: GPL-3.0-or-later
"""What the guided setup is about to do, as data (plan task VS-2.2, decisions D5, D26, D27).

One list of everything that will be downloaded or built, with its size, where it comes from, why, and whether it can be fetched yet. The window
shows that list once, the person agrees to it once, and the agreement is a `ConsentRecord` that names each item (core/consent.py), so nothing outside
the list can ever be fetched. The same data gives the disk the whole path will need, judged against the free space on each drive (core/diskbudget.py,
D26: always room for at least two people, and for both starting voices unless one is declined).

This file decides; it starts no program, reads no disk and says no words. Running the plan is core/setuprun.py.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import FrozenSet, Iterable, List, Mapping, Optional, Sequence, Tuple
from urllib.parse import urlparse

from .consent import ConsentRecord, make_consent
from .diskbudget import DEFAULT_TABLE, DriveMap, Level, SizeTable, Verdict, judge_start
from .envspec import EnvSpec
from .registry import Registry

PACKAGE_HOSTS = ("pypi.org", "files.pythonhosted.org")      # where pip looks, unless the person has set up pip otherwise; shown, never used as an address
DEFAULT_HOURS = 1.0                                          # the planned recording time used for the start estimate until a project says otherwise
KINDS = ("voice", "model", "source", "packages")
# why an item cannot be fetched yet, grouped for the screens
NOT_READY_CODES = frozenset({"unpinned", "lock_unpinned", "source_unpinned"})
BLOCKER_CODES = ("not_available", "no_room")                 # each has words in the text catalog


@dataclass(frozen=True)
class SetupItem:
    id: str                          # a registry id (voice-mike), or env-<id> for an environment's packages
    kind: str                        # one of KINDS
    why_key: str                     # text catalog key: one plain line on why
    license_id: Optional[str]        # key into the license texts shown before a download; packages carry theirs in the lock
    size_bytes: int                  # exact once pinned, otherwise what the host shows or a guess
    exact: bool
    hosts: Tuple[str, ...]           # site names only; the full address is under Show details
    url: Optional[str]
    problems: Tuple[str, ...]        # why it cannot be fetched or built yet; empty means it can
    declinable: bool                 # a starting voice may be declined and fetched later (D25)
    agreement_id: Optional[str]      # the extra name the agreement needs (pip:<env>); None when the registry entry itself is the agreement

    @property
    def available(self) -> bool:
        return not self.problems

    @property
    def not_ready_only(self) -> bool:
        """Cannot be fetched *yet* (its exact files are not fixed in place), as opposed to something being wrong with its entry."""
        return bool(self.problems) and all(p in NOT_READY_CODES for p in self.problems)


def problem_kind(code: str) -> str:
    """"not_ready" or "broken": all the screens say about a problem code. The exact codes are under Show details."""
    return "not_ready" if code in NOT_READY_CODES else "broken"


def build_items(registry: Registry, envs: Sequence[EnvSpec]) -> Tuple[SetupItem, ...]:
    """Every download and build the setup can do, in the order it does them: the environments first (they hold the tools that check the rest),
    then the speech model, the trainer's source, and the starting voices."""
    items: List[SetupItem] = []
    for spec in envs:
        items.append(SetupItem("env-" + spec.id, "packages", spec.why_key, None, spec.approx_size_bytes, False, PACKAGE_HOSTS, None,
                               tuple(spec.pin_problems(registry)), False, "pip:" + spec.id))
    order = {"model": 0, "source": 1, "voice": 2}
    for item in sorted((i for i in registry.items if i.kind in order), key=lambda i: (order[i.kind], i.id)):
        host = urlparse(item.url).hostname if item.url else None
        items.append(SetupItem(item.id, item.kind, item.why_key, item.license_id, item.size_for_budget or 0, item.size_bytes is not None,
                               (host,) if host else (), item.url, tuple(item.pin_problems()), item.kind == "voice", None))
    return tuple(items)


@dataclass(frozen=True)
class SetupPlan:
    items: Tuple[SetupItem, ...]             # everything that will be done, minus what was declined
    declined: Tuple[str, ...]                # ids the person said no to (starting voices only)
    verdict: Verdict
    hours: float

    @property
    def unavailable(self) -> Tuple[SetupItem, ...]:
        return tuple(i for i in self.items if not i.available)

    @property
    def total_bytes(self) -> int:
        return sum(i.size_bytes for i in self.items)

    @property
    def exact(self) -> bool:
        """True only when every size is a real one: a total made partly of guesses says so."""
        return all(i.exact for i in self.items)

    @property
    def blockers(self) -> Tuple[str, ...]:
        found = []
        if self.unavailable:
            found.append("not_available")
        if self.verdict.level is Level.NOT_ENOUGH:
            found.append("no_room")
        return tuple(found)

    @property
    def can_start(self) -> bool:
        return not self.blockers

    @property
    def needs_warning(self) -> bool:
        """Room for the minimum but not for the full plan: go on only after being told."""
        return self.verdict.level is Level.TIGHT

    def agreement_ids(self) -> Tuple[str, ...]:
        """The extra names the agreement must carry (the registry entries carry themselves)."""
        return tuple(i.agreement_id for i in self.items if i.agreement_id and i.available)

    def agreement(self, registry: Registry, now: Optional[datetime] = None) -> ConsentRecord:
        """What the person's one yes covers: each pinned registry entry in this plan, exact address, size and checksum, and each environment's packages by name.
        An entry that cannot be fetched yet is not in it, so agreeing to a plan with such entries agrees to nothing about them."""
        wanted = {i.id for i in self.items if i.available and i.agreement_id is None}
        entries = [registry.get(item_id) for item_id in sorted(wanted)]
        return make_consent(entries, extra_ids=self.agreement_ids(), now=now)


def agreed(plan: SetupPlan, registry: Registry, consent: Optional[ConsentRecord]) -> bool:
    """Has the person already agreed to every item of this plan that can be fetched? False when the list changed since (a different file under the same
    name is not covered), so the list is shown again instead of anything being fetched on an old yes."""
    if consent is None:
        return False
    for item in plan.items:
        if not item.available:
            continue
        if item.agreement_id is not None:
            if not consent.covers_id(item.agreement_id):
                return False
        elif not consent.covers(registry.get(item.id)):
            return False
    return True


def downloads_for_disk(items: Iterable[SetupItem]) -> List[Tuple[str, int]]:
    """What the disk estimate counts as a download. The environments are counted by the estimate's own tool line, so they are not repeated here."""
    return [(i.id, i.size_bytes) for i in items if i.kind != "packages"]


def plan_setup(registry: Registry, envs: Sequence[EnvSpec], *, free: Mapping[str, Optional[int]], table: SizeTable = DEFAULT_TABLE,
               hours: float = DEFAULT_HOURS, drives: DriveMap = DriveMap(), declined: Iterable[str] = ()) -> SetupPlan:
    """Build the list and judge the disk. `declined` can only name starting voices; anything else named is ignored, because nothing else may be skipped."""
    everything = build_items(registry, envs)
    skip = frozenset(declined) & frozenset(i.id for i in everything if i.declinable)
    kept = tuple(i for i in everything if i.id not in skip)
    verdict = judge_start(table, downloads_for_disk(kept), hours, drives, free)
    return SetupPlan(kept, tuple(sorted(skip)), verdict, hours)
