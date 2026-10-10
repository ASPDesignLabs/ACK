# SPDX-License-Identifier: GPL-3.0-or-later
"""Turning the answers of the other modules into sentences, through the text catalog. No decision is made here and no word is typed here.

A failed step is told in three parts (plan decision D22): what happened, whether anything was changed, and the next step.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .diskbudget import Level, Watch
from .jobs import JobStatus
from .preflight import Check, Requirement
from .registry import Item
from .text import Catalog


@dataclass(frozen=True)
class ErrorText:
    what: str
    changed: str
    next: str

    def as_paragraph(self) -> str:
        return " ".join([self.what, self.changed, self.next])


def check_text(cat: Catalog, check: Check) -> str:
    args = dict(check.args)
    if cat.is_plural(check.key):
        return cat.count(check.key, int(args.pop("count", 0)), **args)
    return cat.t(check.key, **args)


def error_text(cat: Catalog, namespace: str, code: str, **args: object) -> ErrorText:
    """`namespace` is "fetch", "job" or "project"; `code` is the error's `.code`."""
    base = "%s.error.%s." % (namespace, code)
    return ErrorText(cat.t(base + "what", **args), cat.t(base + "changed", **args), cat.t(base + "next", **args))


def refusal_text(cat: Catalog, code: str) -> str:
    return cat.t("scratch.refuse." + code)


def warning_text(cat: Catalog, code: str) -> str:
    return cat.t("scratch.warn." + code)


def speed_text(cat: Catalog, code: str) -> str:
    return cat.t("scratch.speed." + code)


def status_text(cat: Catalog, status: JobStatus) -> str:
    return cat.t("job.status." + status.value)


def level_text(cat: Catalog, level: Level) -> str:
    return cat.t("budget.level." + level.value)


def watch_text(cat: Catalog, watch: Watch) -> str:
    return cat.t("budget.watch." + watch.value)


def consent_problem_text(cat: Catalog, code: str) -> str:
    return cat.t("project.consent.missing." + code)


def how_given_text(cat: Catalog, how: str) -> str:
    return cat.t("project.how_given." + how)


def apt_reason(cat: Catalog, requirement: Requirement) -> str:
    return cat.t(requirement.why_key)


def why_text(cat: Catalog, item: Item) -> str:
    return cat.t(item.why_key)
