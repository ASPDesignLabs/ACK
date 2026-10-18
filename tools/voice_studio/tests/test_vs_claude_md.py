# SPDX-License-Identifier: GPL-3.0-or-later
"""The ACK VOICE STUDIO section of CLAUDE.md (plan task VS-8.4) is held to the code: the files and tests it names exist, the exit codes and the release tag it states are the real ones, and
the section was added to the file rather than replacing anything."""
import re
from pathlib import Path

from voice_studio.core import projects_flow as pf, registry as reg

PKG = Path(__file__).resolve().parents[1]
ROOT = PKG.parents[1]
FULL = (ROOT / "CLAUDE.md").read_text(encoding="utf-8")
HEADING = "## ACK VOICE STUDIO — rules that must stay true"


def section():
    start = FULL.index(HEADING)
    nxt = FULL.find("\n## ", start + 1)
    return FULL[start:nxt if nxt != -1 else len(FULL)]


def test_the_section_is_there_once_and_the_older_sections_are_still_there():
    assert FULL.count(HEADING) == 1
    for older in ("## The HELP System — deep analysis", "## The BACKUP & RESTORE system — deep analysis", "## DATA SOVEREIGNTY and LICENSING — rules that must stay true",
                  "## CLINICAL USE (Section 5 of the AAC Readiness Tracker) — rules that must stay true"):
        assert FULL.count(older) == 1 and FULL.index(older) < FULL.index(HEADING), older


def test_every_file_and_test_it_names_exists():
    body = section()
    spans = set(re.findall(r"`([^`\n]+)`", body))
    paths = {s for s in spans if re.match(r"^(docs|tools)/[\w./-]+\.(md|py|json)$", s)}
    assert {"docs/VOICE_STUDIO_SETUP_PLAN.md", "docs/VOICE_STUDIO_HANDOFF.md", "docs/VOICE_STUDIO_DEVICE_TEST.md", "docs/VOICE_STUDIO_RELEASE_RUNBOOK.md", "docs/DATA_SOVEREIGNTY.md"} <= paths
    assert not [p for p in sorted(paths) if not (ROOT / p).exists()]
    inside = {s for s in spans if re.match(r"^(core|data)/[\w./-]+$", s) or s in ("get.sh", "install.ps1", "run_tests.sh") or s.startswith("tools/voice_studio/") and "." in s}
    assert {"core/fetch.py", "core/reportcmd.py", "data/sources.json", "get.sh", "install.ps1", "data/text/en.json"} <= inside
    assert not [s for s in sorted(inside) if not (PKG / s).exists() and not (ROOT / s).exists()]
    tests = {s for s in spans if re.match(r"^test_vs_[\w]+\.py$", s)}
    assert len(tests) >= 6 and not [t for t in sorted(tests) if not (PKG / "tests" / t).exists()]


def test_the_exit_codes_and_the_release_tag_it_states_are_the_real_ones():
    body = " ".join(section().split())
    assert (pf.EXIT_OK, pf.EXIT_PROBLEM, pf.EXIT_NOTHING_DONE) == (0, 1, 2)
    assert "0 done, 1 failed after it started, 2 nothing was done" in body
    prefix = reg.load_release_source().tag_prefix
    assert prefix == "voice-studio-" and "`%svX.Y.Z`" % prefix in body and "`tag_prefix`" in body and "`v1.0-beta.1` to `v1.0-beta.7`" in body
    assert "nothing newer than 3.10" in body and "GIT_TERMINAL_PROMPT=0" in body


def test_it_keeps_the_rules_about_asking_deleting_and_saying_only_what_was_run():
    body = " ".join(section().split())
    for claim in ("nobody to ask means nothing is contacted", "Nothing is deleted unless the person asked", "an earlier backup is never replaced or removed",
                  "Never write that something \"works\" on a real computer unless the checklist records a real run", "Look at the real repository before writing a claim about it",
                  "Never \"fix\" a doc test by loosening it"):
        assert claim in body, claim
