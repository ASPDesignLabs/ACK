# SPDX-License-Identifier: GPL-3.0-or-later
"""docs/VOICE_STUDIO_RELEASE_RUNBOOK.md (plan task VS-8.6) is held to the code: the files, commands and tests it names exist, the tag form is the one the registry counts, the places it says to
change are the places the release check reads, and the rules it states about published tags are said."""
import re
from pathlib import Path

from voice_studio.core import registry as reg

import test_vs_release_ready as ready

PKG = Path(__file__).resolve().parents[1]
ROOT = PKG.parents[1]
DOC = (ROOT / "docs" / "VOICE_STUDIO_RELEASE_RUNBOOK.md").read_text(encoding="utf-8")
BODY = " ".join(DOC.split())


def spans():
    return set(re.findall(r"`([^`\n]+)`", DOC))


def test_every_file_test_and_script_it_names_exists():
    named = {s for s in spans() if re.match(r"^(docs|tools)/[\w./-]+\.(md|MD|py|json|sh|ps1|txt)$|^CHANGELOG\.md$", s)}
    assert {"docs/VOICE_STUDIO_DEVICE_TEST.md", "docs/VOICE_STUDIO_SETUP_PLAN.md", "docs/VOICE_STUDIO_IT_GUIDE.md", "docs/ACK_Voice_Studio_Installation_Guide.MD", "docs/ACK_Voice_Studio_Installation_Guide_Ubuntu.MD",
            "tools/voice_studio/__init__.py", "tools/voice_studio/CHANGELOG.md", "tools/voice_studio/get.sh", "tools/voice_studio/install.ps1", "tools/voice_studio/README.md", "tools/voice_studio/data/sources.json",
            "tools/voice_studio/data/environments.json"} <= named
    for script in ("tools/voice_studio_maint/make_lock.py", "tools/voice_studio_maint/make_pins.py"):
        assert "`python3 %s`" % script in DOC and (ROOT / script).exists(), script
    assert not [n for n in sorted(named) if not (ROOT / n).exists()]
    assert "`THIRD_PARTY_NOTICES.md`" in DOC and (ROOT / "THIRD_PARTY_NOTICES.md").exists()
    assert "`test_vs_changelog.py`" in DOC and (PKG / "tests" / "test_vs_changelog.py").exists() and (PKG / "run_tests.sh").exists()
    assert not [t for t in sorted(spans()) if re.match(r"^test_vs_[\w]+\.py$", t) and not (PKG / "tests" / t).exists()]


def test_the_tag_form_and_the_prefix_are_the_ones_the_registry_counts():
    prefix = reg.load_release_source().tag_prefix
    assert prefix == "voice-studio-" and "`%sv` plus the version" % prefix in DOC and "`%sv0.1.0`" % prefix in DOC
    assert "`tag_prefix`" in DOC and "begin with `%s`" % prefix in DOC and "`v1.0-beta.1` to `v1.0-beta.7`" in DOC
    assert ready.numbers(prefix + "v0.1.0", prefix) == (0, 1, 0) and ready.numbers("v1.0-beta.1", prefix) is None


def test_the_steps_are_numbered_in_order_and_the_check_is_the_one_that_exists():
    numbers = [int(n) for n in re.findall(r"^(\d+)\. \*\*", DOC, flags=re.M)]
    assert numbers == list(range(1, len(numbers) + 1)) and len(numbers) == 9
    assert "`ACK_VOICE_RELEASE=voice-studio-vX.Y.Z ./tools/voice_studio/run_tests.sh -k release_ready`" in BODY
    source = (PKG / "tests" / "test_vs_release_ready.py").read_text(encoding="utf-8")
    assert 'os.environ.get("ACK_VOICE_RELEASE")' in source and "-k release_ready" in source


def test_the_places_it_says_to_change_are_the_places_the_release_check_reads_and_what_it_says_is_checked():
    for place in ready.PLACES:
        assert place.rsplit("/", 1)[-1] in DOC or place in DOC, place
    for word in ("`DEFAULT_TAG` in `tools/voice_studio/get.sh`", "`DefaultRef` and `OneLiner` in `tools/voice_studio/install.ps1`", "\"The default is `main`.\"", "section I7", "decision D39", "the \"Release.\" bullet"):
        assert word in BODY, word
    for claim in ("the version", "the changelog's date", "the two installers", "the one command", "that the tag does not exist yet and is higher than every earlier one"):
        assert claim in BODY, claim


def test_it_says_a_published_tag_is_never_moved_that_a_tag_is_not_signed_and_that_nothing_checks_by_itself():
    for claim in ("**Never move or delete a published tag.**", "A tag is **not signed**", "does not make anything check for updates by itself",
                  "**A release must not say a step works when the checklist has no real run of it.**", "A lock or a pin is **not** remade only because time has passed",
                  "Make the next version instead"):
        assert claim in BODY, claim
    assert "git tag -a voice-studio-vX.Y.Z" in DOC and "git push origin voice-studio-vX.Y.Z" in DOC and "git ls-remote --tags https://github.com/ASPDesignLabs/ACK.git 'voice-studio-*'" in DOC
    assert reg.load_release_source().url == "https://github.com/ASPDesignLabs/ACK.git"
