# SPDX-License-Identifier: GPL-3.0-or-later
"""The problem report (plan decision D22): a plain text file the helper reads *before* it is saved, and that is never sent anywhere.

It holds versions, step names, the three-part error, the results of the checks and, only if asked, the end of a job's log. It never has a
place for a recording, a transcript, a phrase or a consent note. Everything that came from the computer or the person's data goes through
the redactor first: the login name, the home folder, the computer's name, Windows profile names, every person's name and folder name,
email and network addresses and access tokens are replaced by markers such as `<person-1>` and `~`. What is shown is exactly what is saved.
"""
from __future__ import annotations

import errno
import os
import re
import tempfile
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional, Sequence, Tuple

from .. import __version__ as APP_VERSION  # the package version
from .describe import check_text, error_text
from .jobs import JobInfo
from .paths import DataHome
from .preflight import Platform, PreflightReport
from .system import System
from .text import Catalog

LABELS = ("step", "problem", "more", "time", "app", "python", "os", "platform", "gpu", "memory", "job_kind", "job_status", "exit_code", "signal")
SECTIONS = ("what", "versions", "computer", "checks", "disks", "job", "log")          # each has words in the text catalog
MAX_LOG_LINES = 60
MAX_LINE_CHARS = 300
MAX_PIECE_CHARS = 4000                # any one thing handed to the redactor is cut to this first, so no pattern can be made to run for long
MAX_REPORT_BYTES = 100_000
SHORT_NAME = 4                       # a name this short or shorter is matched only as a whole word, so "user" cannot damage "Users" or a short name blank half a word
MIN_NAME = 2                         # a one-character name is not hidden: it would blank every such letter (a known, stated limit)


@dataclass(frozen=True)
class Identity:
    """What identifies this person and this computer, to be hidden wherever it turns up."""
    user: str = ""
    home: str = ""
    hostname: str = ""
    data_home: str = ""
    windows_users: Tuple[str, ...] = ()
    people: Tuple[Tuple[str, str], ...] = ()          # (project id, display name) for every project, in a fixed order


def gather_identity(system: System, people: Sequence[Tuple[str, str]] = ()) -> Identity:
    env = system.environ()
    home = system.home()
    windows = tuple(sorted(n for n in (system.listdir("/mnt/c/Users") or []) if n.lower() not in {"public", "default", "default user", "all users", "desktop.ini"}))
    return Identity(user=env.get("USER") or env.get("LOGNAME") or os.path.basename(home.rstrip("/")), home=home, hostname=system.hostname(),
                    data_home=DataHome(home).root, windows_users=windows, people=tuple(people))


class Redactor:
    """Replaces what identifies someone with markers, and counts how many times it did.

    Each step puts a private sentinel where the marker will go and the real markers are written last, in one pass, so no later step can match
    inside an earlier marker: a login name of "user" must not turn `<windows-user>` into nonsense."""

    def __init__(self, identity: Identity):
        self.count = 0
        self._markers: List[str] = []
        self._steps: List[Tuple[re.Pattern, int, bool]] = []          # (pattern, marker index, keep group 1)

        def step(pattern: str, marker: str, flags: int = 0, keep: bool = False) -> None:
            if marker not in self._markers:
                self._markers.append(marker)
            self._steps.append((re.compile(pattern, flags), self._markers.index(marker), keep))

        paths = [(identity.data_home, "<voice-studio>"), (identity.home, "~")]
        for path, marker in sorted((p for p in paths if p[0] and p[0] != "/"), key=lambda p: -len(p[0])):
            step(re.escape(path), marker, re.IGNORECASE)
        step(r"/home/[^/\s:'\"]+", "~")
        step(r"(/mnt/[a-z]/Users/)[^/\s:'\"]+", "<windows-user>", re.IGNORECASE, keep=True)
        step(r"([A-Za-z]:\\Users\\)[^\\\s:'\"]+", "<windows-user>", keep=True)
        step(r"(/run/media/|/media/)[^/\s:'\"]+/[^/\s:'\"]+", "<user>/<drive>", keep=True)
        step(r"(/mnt/)(?![a-z](?:/|\s|$))[^/\s:'\"]+", "<drive>", keep=True)
        step(r"(?<![\w.+-])[\w.+-]{1,64}@[\w-]{1,63}(?:\.[\w-]{1,63}){1,8}", "<email>")
        step(r"(?<![\d.])(?:(?:25[0-5]|2[0-4]\d|1?\d?\d)\.){3}(?:25[0-5]|2[0-4]\d|1?\d?\d)(?![\d.])", "<address>")
        step(r"\b(?:[0-9a-fA-F]{1,4}:){2,7}[0-9a-fA-F]{1,4}\b", "<address>")
        step(r"\b(?:[0-9a-fA-F]{2}[:-]){5}[0-9a-fA-F]{2}\b", "<address>")
        step(r"(token=)[A-Za-z0-9_\-]{6,}", "<token>", re.IGNORECASE, keep=True)
        named: List[Tuple[str, str]] = []
        for index, (pid, name) in enumerate(identity.people, 1):
            named += [(pid, "<person-%d>" % index), (name, "<person-%d>" % index)]
        named += [(identity.user, "<user>"), (identity.hostname, "<computer>")] + [(w, "<windows-user>") for w in identity.windows_users]
        for name, marker in sorted(((n.strip(), m) for n, m in named if n and len(n.strip()) >= MIN_NAME), key=lambda pair: -len(pair[0])):
            for form in dict.fromkeys([name, unicodedata.normalize("NFC", name), unicodedata.normalize("NFD", name)]):
                body = re.escape(form)
                step(r"(?<![\w])%s(?![\w])" % body if len(name) <= SHORT_NAME else body, marker, re.IGNORECASE)

    def apply(self, value: str) -> str:
        text = unicodedata.normalize("NFC", str(value)[:MAX_PIECE_CHARS])
        text = re.sub("[\ue000\ue001]", "", text)                  # the sentinels themselves can never come from outside
        for pattern, index, keep in self._steps:
            sentinel = "\ue000%d\ue001" % index

            def replace(match, sentinel=sentinel, keep=keep):
                self.count += 1
                return (match.group(1) if keep else "") + sentinel
            text = pattern.sub(replace, text)
        return re.sub("\ue000(\\d+)\ue001", lambda m: self._markers[int(m.group(1))], text)


@dataclass(frozen=True)
class ReportInput:
    now: datetime
    identity: Identity
    step: str = ""                                          # what the tool was doing, as the tool names it ("download voice-mike")
    error: Optional[Tuple[str, str, str]] = None            # (namespace, code, detail) of a FetchError, JobError or ProjectError
    preflight: Optional[PreflightReport] = None
    job: Optional[JobInfo] = None
    log_lines: Tuple[str, ...] = ()                         # offered; only used when include_log is set
    app_version: str = APP_VERSION
    python_version: Tuple[int, int, int] = (0, 0, 0)


@dataclass(frozen=True)
class Report:
    text: str
    hidden: int
    included_log: bool

    def to_bytes(self) -> bytes:
        return self.text.encode("utf-8")


def _gib(n: int) -> str:
    return "%.1f GiB" % (n / 2**30)


def build_report(inp: ReportInput, cat: Catalog, include_log: bool = False) -> Report:
    red = Redactor(inp.identity)
    out: List[str] = []

    def line(text: str = "") -> None:
        out.append(text)

    def labelled(key: str, value: str) -> None:
        line("  %s: %s" % (cat.t("report.label." + key), value))

    def section(key: str) -> None:
        line()
        line(cat.t("report.section." + key))

    line(cat.t("report.title"))
    line(cat.t("report.intro"))
    line("%s: %s" % (cat.t("report.label.time"), inp.now.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")))

    section("what")
    if inp.step:
        labelled("step", red.apply(inp.step))
    if inp.error:
        namespace, code, detail = inp.error
        labelled("problem", red.apply("%s / %s" % (namespace, code)))
        parts = error_text(cat, namespace, code)
        line("  " + parts.as_paragraph())
        if detail:
            labelled("more", red.apply(detail))
    elif not inp.step:
        line("  " + cat.t("report.no_error"))

    section("versions")
    labelled("app", inp.app_version)
    labelled("python", "%d.%d.%d" % inp.python_version)
    if inp.preflight:
        pre = inp.preflight
        section("computer")
        labelled("os", red.apply(pre.os.name or pre.os.id or "?"))
        labelled("platform", cat.t("report.platform." + pre.platform.value))
        best = pre.gpu.best
        labelled("gpu", ("%s, %s MiB, %s" % (red.apply(best.name), best.memory_mib if best.memory_mib is not None else "?", red.apply(best.driver))) if best
                 else cat.t("report.no_gpu"))
        if pre.ram_mib is not None:
            labelled("memory", "%d MiB" % pre.ram_mib)
        section("checks")
        for check in pre.checks:
            args = ", ".join("%s=%s" % (k, red.apply(str(v))) for k, v in sorted(check.args.items()))
            line("  %-5s %-9s %s%s" % (check.status.value, check.id, check.key, (" (" + args + ")") if args else ""))
        if pre.disks:
            section("disks")
            for path, (total, free) in sorted(pre.disks.items()):
                line("  %s: %s" % (red.apply(path), cat.t("report.free_of", free=_gib(free), total=_gib(total))))

    if inp.job:
        section("job")
        labelled("job_kind", red.apply(inp.job.spec.kind))
        labelled("job_status", inp.job.status.value)
        if inp.job.exit_code is not None:
            labelled("exit_code", str(inp.job.exit_code))
        if inp.job.signal is not None:
            labelled("signal", str(inp.job.signal))
        if inp.job.error:
            labelled("more", red.apply(inp.job.error))

    included = bool(include_log and inp.log_lines)
    if inp.job and inp.log_lines:
        section("log")
        if included:
            line("  " + cat.t("report.log_note"))
            for raw in inp.log_lines[-MAX_LOG_LINES:]:
                line("  | " + red.apply(raw[:MAX_LINE_CHARS]))
        else:
            line("  " + cat.t("report.log_left_out"))

    line()
    line(cat.t("report.not_included"))
    line(cat.t("report.hidden", count=red.count))
    text = "\n".join(out) + "\n"
    if len(text.encode("utf-8")) > MAX_REPORT_BYTES:
        text = text.encode("utf-8")[:MAX_REPORT_BYTES].decode("utf-8", errors="ignore") + "\n"
    return Report(text, red.count, included)


def write_report(path: str, report: Report, overwrite: bool = False) -> None:
    """Save exactly the text that was shown, owner-only, to the place the person chose. An existing file is never replaced unless the person said so."""
    directory = os.path.dirname(os.path.abspath(path))
    if not overwrite:
        try:
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError:
            raise FileExistsError(errno.EEXIST, "already exists", path)
        with os.fdopen(fd, "wb") as handle:
            handle.write(report.to_bytes())
            handle.flush()
            os.fsync(handle.fileno())
        return
    fd, temp = tempfile.mkstemp(dir=directory, prefix=".report-", suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(report.to_bytes())
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temp, 0o600)
        os.replace(temp, path)
    except BaseException:
        try:
            os.unlink(temp)
        except OSError:
            pass
        raise
