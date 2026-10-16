# SPDX-License-Identifier: GPL-3.0-or-later
"""The tool's own changelog (plan task VS-8.4) is held to the code: its newest version is the package's `__version__`, its versions only go down, it names every command the tool has,
the tag it describes is the one the registry counts as a release, and every file it points at exists."""
import re
from pathlib import Path

from voice_studio import __version__
from voice_studio.core import registry as reg

PKG = Path(__file__).resolve().parents[1]
ROOT = PKG.parents[1]
TEXT = (PKG / "CHANGELOG.md").read_text(encoding="utf-8")
HEADING = re.compile(r"^## \[(\d+)\.(\d+)\.(\d+)\] - (Unreleased|\d{4}-\d{2}-\d{2})$", flags=re.M)
NOT_COMMANDS = ("__init__", "__main__", "hear_runner", "listen_runner")


def versions():
    return [tuple(int(part) for part in m.groups()[:3]) for m in HEADING.finditer(TEXT)]


def command_modules():
    """The top-level modules a person can run with `python3 -m voice_studio.NAME`: every .py beside `__init__` that can be run (it has a `__main__` guard), but the two background runners."""
    return sorted(p.stem for p in PKG.glob("*.py") if p.stem not in NOT_COMMANDS and 'if __name__ == "__main__":' in p.read_text(encoding="utf-8"))


def test_the_newest_entry_is_the_version_the_package_says_and_the_versions_only_go_down():
    found = versions()
    assert found and found[0] == tuple(int(part) for part in __version__.split("."))
    assert found == sorted(found, reverse=True) and len(set(found)) == len(found)
    assert len(re.findall(r"^## \[", TEXT, flags=re.M)) == len(found), "every version heading is written as '## [x.y.z] - Unreleased' or with a date"


def test_it_names_every_command_the_tool_has_and_the_guided_setup():
    modules = command_modules()
    assert len(modules) >= 12 and "report" in modules and "update" in modules, modules
    for name in modules:
        assert "`python3 -m voice_studio.%s`" % name in TEXT, name
    assert "`python3 -m voice_studio`" in TEXT


def test_it_says_which_tag_is_a_release_the_way_the_registry_counts_one():
    prefix = reg.load_release_source().tag_prefix
    assert prefix == "voice-studio-" and "`%sv` plus that version" % prefix in TEXT and "`%sv0.1.0`" % prefix in TEXT
    assert "`v1.0-beta.1`" in TEXT and "belong to the phone app" in TEXT and "begin with `%s`" % prefix in TEXT


def test_every_file_it_points_at_exists():
    named = {span for span in re.findall(r"`([^`\n]+)`", TEXT) if re.match(r"^(docs|tools)/[\w./-]+\.(md|py)$|^CHANGELOG\.md$", span)}
    assert {"docs/VOICE_STUDIO_RELEASE_RUNBOOK.md", "docs/VOICE_STUDIO_DEVICE_TEST.md", "docs/VOICE_STUDIO_GUIDE.md", "tools/voice_studio/__init__.py", "CHANGELOG.md"} <= named
    missing = sorted(name for name in named if not (ROOT / name).exists())
    assert not missing, missing


def test_it_does_not_claim_a_real_run_and_lists_what_is_not_done():
    body = " ".join(TEXT.split())
    assert "built and tested in a build sandbox" in body and "nothing here says a step works on a real computer unless that checklist records it" in body
    assert "### Not done yet" in TEXT and "sending recordings over Wi-Fi" in body
    assert "Unreleased" in TEXT.split("\n## ", 1)[1].splitlines()[0] or versions()[0] != (0, 0, 1), "a version with a date is a release that was cut"


def test_it_lists_the_window_pages_the_window_has_and_does_not_list_them_as_missing():
    from voice_studio.core import text as catalog_text, windowmodel
    cat = catalog_text.load_catalog("en")
    body = " ".join(TEXT.split())
    listed = ", ".join(cat.t("window.nav." + p) for p in windowmodel.PAGES[:-1]) + ", and " + cat.t("window.nav." + windowmodel.PAGES[-1])
    assert "The window has eleven pages: " + listed.replace(", and ", " and ") in body and len(windowmodel.PAGES) == 11
    assert "Updates and the mend and fresh-copy buttons of Check the tool can lead to the internet" in body
    assert "The window's pages for backup" not in body and "A window page for getting a starting voice" in body
