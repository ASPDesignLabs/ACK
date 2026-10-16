# SPDX-License-Identifier: GPL-3.0-or-later
"""The checks to make before a release is tagged (plan task VS-8.6, docs/VOICE_STUDIO_RELEASE_RUNBOOK.md).

`problems()` is the rule, tested here on made-up inputs like any other code. The last test runs it on the real files, and only when the person making the release names the tag in
`ACK_VOICE_RELEASE`; otherwise it is skipped, because an ordinary commit is not a release: `ACK_VOICE_RELEASE=voice-studio-v0.1.0 ./run_tests.sh -k release_ready`.
"""
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Dict, Iterable, List, Mapping, Sequence

import pytest

from voice_studio import __version__
from voice_studio.core import registry as reg

PKG = Path(__file__).resolve().parents[1]
ROOT = PKG.parents[1]
SAYS_MAIN = re.compile(r"default(?:\s+is)?\s+`main`|`main`\s+by\s+default|commands\s+fetch\s+`main`")          # how the guides, the README and the checklist say that main is what is fetched
FIRST_ENTRY = re.compile(r"^## \[(\d+\.\d+\.\d+)\] - (Unreleased|\d{4}-\d{2}-\d{2})$", flags=re.M)


def numbers(tag: str, prefix: str):
    """The three numbers of a tag that is the prefix, a `v` and a version written the one way (no leading zeros); None for anything else (a trailing line break included)."""
    match = re.match(r"%sv(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)\Z" % re.escape(prefix), tag)
    return tuple(int(part) for part in match.groups()) if match else None


def problems(tag: str, version: str, changelog: str, get_sh: str, install_ps1: str, existing_tags: Iterable[str], prefix: str, places: Mapping[str, str] = {}) -> List[str]:
    """Everything that makes this tag the wrong one to make now, as plain sentences. An empty list means the files agree with the tag. `places` are the documents (name to text) that must
    no longer say that `main` is what is fetched."""
    found: List[str] = []
    wanted = numbers(tag, prefix)
    if wanted is None:
        return ["The tag must look like %sv1.2.3 (the registry counts only tags that begin with %s)." % (prefix, prefix)]
    name = ".".join(str(n) for n in wanted)
    if version != name:
        found.append("The package says version %s but the tag is for %s." % (version, name))
    entry = FIRST_ENTRY.search(changelog)
    if not entry or entry.group(1) != name:
        found.append("The changelog's newest entry is not for %s." % name)
    elif entry.group(2) == "Unreleased":
        found.append("The changelog entry for %s still says Unreleased: give it the date." % name)
    default = re.search(r'^DEFAULT_TAG="([^"]+)"', get_sh, flags=re.M)
    if not default or default.group(1) != tag:
        found.append("get.sh fetches %s by default, not %s." % (default.group(1) if default else "nothing", tag))
    ps1 = re.search(r"DefaultRef\s*=\s*'([^']+)'", install_ps1)
    if not ps1 or ps1.group(1) != tag:
        found.append("install.ps1 fetches %s by default, not %s." % (ps1.group(1) if ps1 else "nothing", tag))
    liner = re.search(r"OneLiner\s*=\s*'([^']*)'", install_ps1)
    if not liner or "/ASPDesignLabs/ACK/%s/" % tag not in liner.group(1):
        found.append("The one command in install.ps1 does not fetch %s." % tag)
    for name_of_place, text in places.items():
        if SAYS_MAIN.search(text):
            found.append("%s still says that main is what is fetched by default." % name_of_place)
    others = [t for t in existing_tags if numbers(t, prefix)]
    if tag in others:
        found.append("The tag %s already exists. A published tag is never moved: make the next version instead." % tag)
    higher = [t for t in others if numbers(t, prefix) > wanted]
    if higher:
        found.append("The release %s is not newer than %s." % (tag, max(higher, key=lambda t: numbers(t, prefix))))
    return found


PLACES = ("docs/ACK_Voice_Studio_Installation_Guide.MD", "docs/ACK_Voice_Studio_Installation_Guide_Ubuntu.MD", "docs/VOICE_STUDIO_IT_GUIDE.md", "docs/VOICE_STUDIO_DEVICE_TEST.md",
          "tools/voice_studio/README.md")          # where the runbook's step 4 says the default release is written in words

GOOD = dict(tag="voice-studio-v0.2.0", version="0.2.0", changelog="# x\n\n## [0.2.0] - 2026-11-01\n\n## [0.1.0] - 2026-10-20\n",
            get_sh='set -u\nDEFAULT_TAG="voice-studio-v0.2.0"   # x\n', install_ps1="DefaultRef = 'voice-studio-v0.2.0'\nOneLiner = 'irm https://raw.githubusercontent.com/ASPDesignLabs/ACK/voice-studio-v0.2.0/tools/voice_studio/install.ps1 | iex'\n",
            existing_tags=("v1.0-beta.7", "voice-studio-v0.1.0"), prefix="voice-studio-")


def check(**changes):
    return problems(**{**GOOD, **changes})


def test_files_that_agree_with_a_new_higher_tag_have_no_problems():
    assert check() == []
    assert check(existing_tags=()) == [] and check(existing_tags=("v9.9.9", "voice-studio-v0.1.0", "other")) == []


@pytest.mark.parametrize("tag", ["", "v0.2.0", "voice-studio-0.2.0", "voice-studio-v0.2", "voice-studio-v0.2.0.1", "voice-studio-v0.2.x", "voice-studio-v0.2.0 ", "voice-studio-v0.2.0\n", "voice-studio-V0.2.0", "voice-studio-v0.02.0", "voice-studio-v00.2.0", "voice-studio-v0.2.00", "voice-studio-v-1.2.3",
                                 "x-voice-studio-v0.2.0", "other-v0.2.0"])
def test_a_tag_that_is_not_the_tools_form_is_refused_with_the_form_it_should_have(tag):
    assert check(tag=tag) == ["The tag must look like voice-studio-v1.2.3 (the registry counts only tags that begin with voice-studio-)."]


def test_the_form_is_checked_against_the_prefix_the_registry_gives():
    assert check(tag="voice-studio-v0.2.0", prefix="studio-") == ["The tag must look like studio-v1.2.3 (the registry counts only tags that begin with studio-)."]
    other = dict(tag="a-v0.2.0", prefix="a-", get_sh='DEFAULT_TAG="a-v0.2.0"', install_ps1="DefaultRef = 'a-v0.2.0'\nOneLiner = '/ASPDesignLabs/ACK/a-v0.2.0/'", existing_tags=("a-v0.1.0", "voice-studio-v9.0.0"))
    assert check(**other) == [], "the form follows the prefix, and a tag with another prefix is not an earlier release"


def test_the_version_in_the_package_must_be_the_tags():
    assert check(version="0.1.9") == ["The package says version 0.1.9 but the tag is for 0.2.0."]
    assert check(version="0.2.0.0") == ["The package says version 0.2.0.0 but the tag is for 0.2.0."]


def test_the_changelog_must_have_the_tags_version_first_and_dated():
    assert check(changelog="## [0.1.0] - 2026-10-20\n") == ["The changelog's newest entry is not for 0.2.0."]
    assert check(changelog="") == ["The changelog's newest entry is not for 0.2.0."]
    assert check(changelog="## [0.2.0] - Unreleased\n") == ["The changelog entry for 0.2.0 still says Unreleased: give it the date."]
    assert check(changelog="## [0.2.0] - 2026-11-1\n") == ["The changelog's newest entry is not for 0.2.0."]
    assert check(changelog="## [0.3.0] - 2026-11-01\n## [0.2.0] - 2026-10-20\n") == ["The changelog's newest entry is not for 0.2.0."]


def test_both_installers_and_the_one_command_must_fetch_the_tag():
    assert check(get_sh='DEFAULT_TAG="main"\n') == ["get.sh fetches main by default, not voice-studio-v0.2.0."]
    assert check(get_sh="") == ["get.sh fetches nothing by default, not voice-studio-v0.2.0."]
    assert check(get_sh='# DEFAULT_TAG="voice-studio-v0.2.0"\nDEFAULT_TAG="main"\n') == ["get.sh fetches main by default, not voice-studio-v0.2.0."]
    ps1 = GOOD["install_ps1"]
    assert check(install_ps1=ps1.replace("DefaultRef = 'voice-studio-v0.2.0'", "DefaultRef = 'main'")) == ["install.ps1 fetches main by default, not voice-studio-v0.2.0."]
    assert check(install_ps1=ps1.split("\n")[1]) == ["install.ps1 fetches nothing by default, not voice-studio-v0.2.0."]
    assert check(install_ps1=ps1.replace("ACK/voice-studio-v0.2.0/tools", "ACK/main/tools")) == ["The one command in install.ps1 does not fetch voice-studio-v0.2.0."]
    assert check(install_ps1=ps1.split("\n")[0]) == ["The one command in install.ps1 does not fetch voice-studio-v0.2.0."]


def test_a_tag_that_exists_is_never_made_again_and_a_release_must_be_newer_than_every_earlier_one():
    assert check(existing_tags=("voice-studio-v0.2.0",)) == ["The tag voice-studio-v0.2.0 already exists. A published tag is never moved: make the next version instead."]
    assert check(existing_tags=("voice-studio-v0.3.0", "voice-studio-v0.1.0")) == ["The release voice-studio-v0.2.0 is not newer than voice-studio-v0.3.0."]
    assert check(existing_tags=("voice-studio-v0.10.0", "voice-studio-v0.9.0")) == ["The release voice-studio-v0.2.0 is not newer than voice-studio-v0.10.0."]
    assert check(existing_tags=("voice-studio-v0.2.1",)) == ["The release voice-studio-v0.2.0 is not newer than voice-studio-v0.2.1."]
    assert check(existing_tags=("voice-studio-v0.1.9", "v9.9.9")) == [], "an older release, and a tag of the phone app, do not matter"
    both = check(existing_tags=("voice-studio-v0.2.0", "voice-studio-v0.3.0"))
    assert len(both) == 2 and both[0].startswith("The tag voice-studio-v0.2.0 already exists") and both[1] == "The release voice-studio-v0.2.0 is not newer than voice-studio-v0.3.0."


@pytest.mark.parametrize("sentence", ["The default is `main`.", "(default `main`)", "`main` by default.", "Until a release is tagged the commands fetch `main`, so", "the default `main`", "Until a release is tagged the commands fetch\n`main`, so", "The default\nis `main`.", "`main`\nby\ndefault", "`main` by\ndefault"])
def test_a_document_that_still_says_main_is_fetched_is_named(sentence):
    assert check(places={"The IT guide": "Intro. " + sentence + " More."}) == ["The IT guide still says that main is what is fetched by default."]


@pytest.mark.parametrize("sentence", ["The default is `voice-studio-v0.2.0`.", "Pin a branch such as `main` if you test.", "the main window", "(default `voice-studio-v0.2.0`)", "", "default`main`", "defaults `main`"])
def test_a_document_that_names_main_for_another_reason_is_left_alone(sentence):
    assert check(places={"The README": sentence, "The guide": sentence}) == []


def test_each_document_that_still_says_main_is_named_once_by_its_own_name():
    found = check(places={"A": "default `main`", "B": "fine", "C": "`main` by default"})
    assert found == ["A still says that main is what is fetched by default.", "C still says that main is what is fetched by default."]


def test_a_heading_with_anything_after_the_date_is_not_the_changelogs_newest_entry():
    assert check(changelog="## [0.2.0] - Unreleased (draft)\n") == ["The changelog's newest entry is not for 0.2.0."]
    assert check(changelog="## [0.2.0] - 2026-11-01 (draft)\n") == ["The changelog's newest entry is not for 0.2.0."]


def test_the_prefix_is_taken_as_letters_not_as_a_pattern():
    assert check(tag="vxs-v0.2.0", prefix="v.s-") == ["The tag must look like v.s-v1.2.3 (the registry counts only tags that begin with v.s-)."]
    assert check(tag="aab-v0.2.0", prefix="a*b-") == ["The tag must look like a*b-v1.2.3 (the registry counts only tags that begin with a*b-)."]


def test_a_default_that_is_empty_is_said_to_be_nothing():
    assert check(get_sh='DEFAULT_TAG=""\n') == ["get.sh fetches nothing by default, not voice-studio-v0.2.0."]
    assert check(install_ps1="DefaultRef = ''\n" + GOOD["install_ps1"].split("\n")[1]) == ["install.ps1 fetches nothing by default, not voice-studio-v0.2.0."]


def test_the_one_command_must_name_the_tag_where_the_repository_path_has_it_and_for_the_right_repository():
    base = GOOD["install_ps1"].split("\n")[0] + "\n"
    elsewhere = base + "OneLiner = 'irm https://raw.githubusercontent.com/ASPDesignLabs/ACK/main/tools/voice_studio/voice-studio-v0.2.0.ps1 | iex'\n"
    other_owner = base + "OneLiner = 'irm https://raw.githubusercontent.com/xASPDesignLabs/ACK/voice-studio-v0.2.0/tools/voice_studio/install.ps1 | iex'\n"
    assert check(install_ps1=elsewhere) == ["The one command in install.ps1 does not fetch voice-studio-v0.2.0."]
    assert check(install_ps1=other_owner) == ["The one command in install.ps1 does not fetch voice-studio-v0.2.0."]


def test_a_tag_with_the_prefix_that_is_not_a_version_is_not_an_earlier_release_and_does_not_stop_the_check():
    assert check(existing_tags=("voice-studio-old", "voice-studio-v0.3", "voice-studio-v0.1.0", "voice-studio-v0.9.0-rc1")) == []


def test_every_problem_is_reported_not_only_the_first():
    many = check(version="0.1.0", changelog="", get_sh="", install_ps1="", existing_tags=("voice-studio-v0.5.0",), places={"A": "default `main`"})
    assert len(many) == 7, many


@pytest.mark.skipif(not os.environ.get("ACK_VOICE_RELEASE"), reason="not making a release: name the tag in ACK_VOICE_RELEASE to check the files for it")
def test_the_real_files_agree_with_the_release_being_made():
    tag = os.environ["ACK_VOICE_RELEASE"]
    existing: Sequence[str] = ()
    if shutil.which("git") and (ROOT / ".git").exists():
        done = subprocess.run(["git", "-C", str(ROOT), "tag", "-l", "voice-studio-*"], capture_output=True, text=True, timeout=60)
        existing = tuple(done.stdout.split()) if done.returncode == 0 else ()
    places = {name: (ROOT / name).read_text(encoding="utf-8") for name in PLACES}
    found = problems(tag, __version__, (PKG / "CHANGELOG.md").read_text(encoding="utf-8"), (PKG / "get.sh").read_text(encoding="utf-8"), (PKG / "install.ps1").read_text(encoding="utf-8"),
                     existing, reg.load_release_source().tag_prefix, places)
    assert not found, "\n".join(found)
