# SPDX-License-Identifier: GPL-3.0-or-later
"""Carrying out the setup plan (plan task VS-2.2): one agreement, then each item in order, stopping at the first that fails.

Resumable by nature, with no state of its own: an environment build is resumable (core/envbuild.py), a download resumes and is skipped when the right file
is already there (core/fetch.py), so closing the window, losing the connection or restarting the computer costs only the step that was running. What is
left to do is read from the disk, never from a saved "I was here" note that could disagree with it.

A starting voice is *not* fetched here. Each one is fetched when the person chooses it and makes the acknowledgment of where it came from (plan decision
D27, task VS-4.1); the plan lists them so the disk estimate and the agreement list are complete, and this run reports them as "later".
"""
from __future__ import annotations

import dataclasses
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable, Dict, List, Optional, Sequence, Tuple

from . import envbuild, fetch
from .consent import ConsentRecord, load_consent, merge_consent, save_consent
from .envspec import EnvSpec
from .paths import DataHome
from .registry import Registry
from .setupplan import SetupItem, SetupPlan, agreed

REFUSAL_CODES = ("not_available", "no_room", "tight", "no_agreement")        # why a run did not start; each has words in the text catalog
STATUSES = ("done", "kept", "later", "failed", "cancelled")                    # each has words in the text catalog
OK_STATUSES = ("done", "kept", "later")
MODELS_FOLDER = "models"


@dataclass(frozen=True)
class SetupEvent:
    kind: str                # "start", an item's end (one of STATUSES), "progress", "line", and the builder's own kinds with their step
    item: str                # the plan item this belongs to
    step: str = ""           # for an environment: which of its steps (core/envbuild.ACTION_IDS)
    done: int = 0            # for a download: bytes so far
    total: int = 0
    text: str = ""           # for a line a command printed


@dataclass(frozen=True)
class ItemResult:
    id: str
    status: str                          # one of STATUSES
    namespace: str = ""                  # for a failure: "env" or "fetch", which picks the words
    code: str = ""
    detail: str = ""
    tail: Tuple[str, ...] = ()           # the end of a failed command's output


@dataclass(frozen=True)
class SetupOutcome:
    ok: bool
    refused: Tuple[str, ...] = ()        # REFUSAL_CODES, when nothing was started
    results: Tuple[ItemResult, ...] = ()

    @property
    def failure(self) -> Optional[ItemResult]:
        return next((r for r in self.results if r.status in ("failed", "cancelled")), None)


def agree(plan: SetupPlan, registry: Registry, home: DataHome, now: Optional[datetime] = None) -> ConsentRecord:
    """The person's yes to the list as shown: saved (owner only, in one step) and merged with any earlier yes, which is never forgotten."""
    record = merge_consent(load_consent(Path(home.consent_file)), plan.agreement(registry, now))
    save_consent(Path(home.consent_file), record)
    return record


def _refusal(plan: SetupPlan, registry: Registry, consent: Optional[ConsentRecord], accept_tight: bool) -> Tuple[str, ...]:
    found = list(plan.blockers)
    if not found and plan.needs_warning and not accept_tight:
        found.append("tight")
    if not found and not agreed(plan, registry, consent):
        found.append("no_agreement")
    return tuple(found)


def run(plan: SetupPlan, ctx: envbuild.Context, envs: Sequence[EnvSpec], *, accept_tight: bool = False,
        on_event: Optional[Callable[[SetupEvent], None]] = None, cancelled: Optional[Callable[[], bool]] = None) -> SetupOutcome:
    """Do the plan. Nothing starts unless every blocker is gone, the person has accepted a tight disk if it is tight, and the agreement on the
    context covers exactly this list. Stops at the first failure (the next run carries on from there) or when `cancelled()` says so."""
    refused = _refusal(plan, ctx.registry, ctx.consent, accept_tight)
    if refused:
        return SetupOutcome(False, refused)
    say = on_event or (lambda event: None)
    specs: Dict[str, EnvSpec] = {"env-" + s.id: s for s in envs}
    results: List[ItemResult] = []
    built: Dict[str, envbuild.BuildResult] = {}
    for item in plan.items:
        if cancelled and cancelled():
            results.append(ItemResult(item.id, "cancelled"))
            break
        say(SetupEvent("start", item.id))
        result = _do(item, plan, ctx, specs, built, say, cancelled)
        results.append(result)
        say(SetupEvent(result.status, item.id))
        if result.status in ("failed", "cancelled"):
            break
    ok = bool(results) and all(r.status in OK_STATUSES for r in results) and len(results) == len(plan.items)
    return SetupOutcome(ok, (), tuple(results))


def _do(item: SetupItem, plan: SetupPlan, ctx: envbuild.Context, specs: Dict[str, EnvSpec], built: Dict[str, envbuild.BuildResult],
        say: Callable[[SetupEvent], None], cancelled: Optional[Callable[[], bool]]) -> ItemResult:
    if item.kind == "packages":
        return _build(item, ctx, specs[item.id], built, say)
    if item.kind == "source":
        return _source(item, specs, built)
    if item.kind == "voice":
        return ItemResult(item.id, "later")
    return _download(item, ctx, say, cancelled)


def _build(item: SetupItem, ctx: envbuild.Context, spec: EnvSpec, built: Dict[str, envbuild.BuildResult], say: Callable[[SetupEvent], None]) -> ItemResult:
    def bridge(event: envbuild.Event) -> None:
        say(SetupEvent("line" if event.kind == "line" else event.kind, item.id, step=event.step, text=event.text))
        ctx.on_event(event)

    result = envbuild.build(spec, dataclasses.replace(ctx, on_event=bridge))
    built[item.id] = result
    if result.ok:
        return ItemResult(item.id, "done" if result.did else "kept")
    error = result.error
    return ItemResult(item.id, "failed", "env", error.code, error.detail, error.tail)


def _source(item: SetupItem, specs: Dict[str, EnvSpec], built: Dict[str, envbuild.BuildResult]) -> ItemResult:
    """The trainer's source is fetched by the environment that uses it, as one of that environment's steps; this reports what that build did."""
    for env_id, spec in specs.items():
        if spec.source is not None and spec.source.item_id == item.id and env_id in built and built[env_id].ok:
            return ItemResult(item.id, "done" if "source_unpack" in built[env_id].did else "kept")
    return ItemResult(item.id, "failed", "env", "not_pinned", "no environment in this plan uses " + item.id)


def _download(item: SetupItem, ctx: envbuild.Context, say: Callable[[SetupEvent], None], cancelled: Optional[Callable[[], bool]]) -> ItemResult:
    pinned = ctx.registry.get(item.id)
    folder = Path(ctx.home.downloads) / MODELS_FOLDER / (pinned.folder or "")          # a model of several files keeps them together in its own folder
    if fetch.is_fetched(pinned, folder):
        return ItemResult(item.id, "kept")
    try:
        ctx.fetcher(pinned, folder, ctx.consent, progress=lambda done, total: say(SetupEvent("progress", item.id, done=done, total=total)),
                    cancelled=cancelled)
    except fetch.FetchError as error:
        if error.code == "cancelled":
            return ItemResult(item.id, "cancelled", "fetch", error.code, error.detail)
        return ItemResult(item.id, "failed", "fetch", error.code, error.detail)
    return ItemResult(item.id, "done")
