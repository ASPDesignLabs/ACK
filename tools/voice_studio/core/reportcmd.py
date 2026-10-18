# SPDX-License-Identifier: GPL-3.0-or-later
"""The problem report as a command (plan task VS-6.4, decisions D22 and P22): what to ask for, which task it is about, where it may be saved, and the line a failed command ends with.

The report itself is built in core/report.py (plan task VS-1.8): it blanks names and folders and has no place for a recording, a transcript or a phrase. This module only decides the
small things around it: whether a problem name is one the tool knows, which task a person means, whether a place can take the file without replacing anything, and the sentences that
point a person at the command after something failed. Nothing here sends anything anywhere, and nothing is written except by `save`, to exactly the place the person gave.

Plain Python with no words and no network library; the words are in the text catalog under `reportcmd.*`.
"""
from __future__ import annotations

import os
import re
import shlex
from typing import Optional, Sequence, Tuple

from . import jobs
from .report import Report, write_report
from .text import Catalog

ERROR_CODES = ("bad_problem", "needs_problem", "needs_job", "no_job", "no_place", "not_absolute", "folder_missing", "file_exists", "not_a_file", "cannot_save")      # each has words in the text catalog
REPORT_COMMAND = "python3 -m voice_studio.report"
PROBLEM_NAME = re.compile(r"^[a-z][a-z0-9_]{0,30}/[a-z][a-z0-9_]{0,40}\Z")
STEP_WORD = re.compile(r"^[a-z][a-z-]{0,19}\Z")
LAST = "last"                                                    # --job last: the newest task
MAX_STEP = 200


class ReportError(Exception):
    """`code` is one of ERROR_CODES; `detail` is a short fact for the Technical detail line."""

    def __init__(self, code: str, detail: str = ""):
        super().__init__(code + (": " + detail if detail else ""))
        self.code = code
        self.detail = detail


def parse_problem(cat: Catalog, text: str) -> Tuple[str, str]:
    """`update/unreachable` as ("update", "unreachable"), when the catalog has the three-part words for it. Anything else is a problem name the tool does not know."""
    if not PROBLEM_NAME.match(text):
        raise ReportError("bad_problem", text[:80])
    namespace, code = text.split("/")
    if not cat.has("%s.error.%s.what" % (namespace, code)):
        raise ReportError("bad_problem", text)                  # the pattern has already held it to 73 letters
    return namespace, code


def pick_job(jobs_root: str, wanted: str) -> jobs.JobInfo:
    """The task named by its id, or the newest one for `last`. Looks at the tasks' own files only; nothing is changed."""
    found = jobs.list_jobs(jobs_root).jobs
    if wanted == LAST:
        if found:
            return found[-1]
    else:
        for info in found:
            if info.id == wanted:
                return info
    raise ReportError("no_job", wanted[:80])


def check_place(path: str, replace: bool) -> str:
    """The whole path of the file to write, when the place can take it: the folder exists, and nothing is there, or something is and the person said to replace it and it is a plain file.
    No folder is made. Raises ReportError('not_absolute', 'folder_missing', 'file_exists' or 'not_a_file')."""
    full = os.path.expanduser(path)
    if not os.path.isabs(full):
        raise ReportError("not_absolute", path[:200])
    full = os.path.normpath(full)
    if not os.path.isdir(os.path.dirname(full)):
        raise ReportError("folder_missing", os.path.dirname(full))
    if os.path.lexists(full):
        if not replace:
            raise ReportError("file_exists", full)
        if os.path.islink(full) or not os.path.isfile(full):
            raise ReportError("not_a_file", full)
    return full


def sync_reason(path: str) -> Optional[str]:
    """Why the folder the file would go in looks like one a cloud service copies, or None. A warning to show, never a reason to refuse: the report has names blanked."""
    from freeform_studio.privacy import sync_risk              # stdlib only; the two tools travel together in one repository
    return sync_risk(os.path.dirname(path))


def save(path: str, report: Report, replace: bool) -> int:
    """Write exactly the text that was shown, then read it back. Returns the number of bytes. A file this call made and could not finish is removed again; a file that was there
    before is never removed. Raises ReportError('cannot_save', reason)."""
    made = not os.path.lexists(path)
    try:
        write_report(path, report, overwrite=replace)
    except FileExistsError:                                    # someone made the file after the place was checked: it is theirs, so it is left alone
        raise ReportError("file_exists", path)
    except OSError as exc:
        _remove_if_ours(path, made)
        raise ReportError("cannot_save", _reason(exc))
    except BaseException:                                      # Ctrl+C half way: the half-written file is this call's own and goes
        _remove_if_ours(path, made)
        raise
    try:
        with open(path, "rb") as handle:
            held = handle.read()
    except OSError as exc:
        _remove_if_ours(path, made)
        raise ReportError("cannot_save", _reason(exc))
    if held != report.to_bytes():
        _remove_if_ours(path, made)
        raise ReportError("cannot_save", "the file did not hold what was written")
    return len(held)


def _reason(exc: OSError) -> str:
    return exc.strerror or type(exc).__name__


def _remove_if_ours(path: str, made: bool) -> None:
    if made:
        try:
            os.unlink(path)
        except OSError:
            pass


# ---------------------------------------------------------------- the line a failed command ends with

def step_of(name: str, argv: Sequence[str]) -> str:
    """What the command was doing, as the tool names it: the command and, when it is a plain lower-case word, the first thing typed after it. Never a value, a path or an option."""
    first = argv[0] if argv else ""
    return (name + " " + first) if STEP_WORD.match(first) else name


def hint_command(name: str, argv: Sequence[str], shown: Sequence[Tuple[str, str]]) -> str:
    """The command to paste. `--problem` is added only when the failed command told the person about exactly one problem, so it can never name one that was not the failure."""
    parts = [REPORT_COMMAND, "show", "--step", shlex.quote(step_of(name, argv))]
    if len(shown) == 1 and PROBLEM_NAME.match("%s/%s" % shown[0]):
        parts += ["--problem", "%s/%s" % shown[0]]
    return " ".join(parts)


def hint_lines(cat: Catalog, name: str, argv: Sequence[str], shown: Sequence[Tuple[str, str]], code: int) -> Tuple[str, ...]:
    """Nothing unless the command failed after it began (exit 1): a command that was declined, or could not be asked, has nothing to report."""
    if code != 1:
        return ()
    return (cat.t("reportcmd.hint.what"), cat.t("reportcmd.hint.command", command=hint_command(name, argv, shown)))
