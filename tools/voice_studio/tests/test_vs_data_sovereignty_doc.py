# SPDX-License-Identifier: GPL-3.0-or-later
"""The rows of docs/DATA_SOVEREIGNTY.md about ACK Voice Studio (plan task VS-8.3) are held to the code: the places it names are the places the tool makes, the hosts are hosts it knows, every command
that can reach the network has a row, and the tests the page cites exist."""
import re
from pathlib import Path

from voice_studio.core import areas, freeup, registry as reg, setupplan as sp
from voice_studio.core.paths import DataHome, ProjectPaths

PKG = Path(__file__).resolve().parents[1]
ROOT = PKG.parents[1]
DOC = (ROOT / "docs" / "DATA_SOVEREIGNTY.md").read_text(encoding="utf-8")


def section(number):
    return re.search(r"^## %s\..*?(?=^## |\Z)" % number, DOC, flags=re.S | re.M).group(0)


MARKERS = ("ACK Voice Studio", "listening model", "newer release of the tool", "`refresh repair`", "`voicefile send`")


def rows(number):
    """The table rows of a section that are about ACK Voice Studio."""
    return [line for line in section(number).splitlines() if line.startswith("|") and any(m in line for m in MARKERS)]


def test_the_places_section_one_names_are_the_places_the_tool_makes():
    body = "\n".join(rows(1))
    home, paths = DataHome("~"), ProjectPaths("~/ack-voice-studio/projects/x")
    assert home.root == "~/ack-voice-studio" and "`~/ack-voice-studio/projects/<name>/`" in body and "`~/ack-voice-studio/tool/`" in body and "`~/ack-voice-studio/state/`" in body
    assert paths.root.startswith(home.projects) and "`listening`" in body and "`scratch`" in body
    assert {a.id for a in areas.PROJECT_AREAS} >= {"listening", "scratch", "recordings", "rounds", "exports"} and {a.id for a in areas.HOME_AREAS} == {"projects", "backups", "tool", "state"}
    assert home.consent_file.endswith("state/consent.json") and "`state/consent.json`" in "\n".join(rows(2))
    assert freeup.OLD_AFTER_DAYS == 30 and "Offered for removal after 30 days" in body


def test_the_backup_row_says_what_the_backup_does():
    row = next(r for r in rows(1) if "a backup of one project" in r)
    for claim in ("never inside a project", "**Not encrypted.**", "never replaces or removes an earlier one", "warns when the folder looks synchronised"):
        assert claim in row, claim
    kinds = {a.id: a for a in areas.HOME_AREAS}
    assert kinds["tool"].backed_up is False and "None of it holds your recordings" in "\n".join(rows(1))


def test_the_hosts_in_section_two_are_hosts_the_code_knows():
    known = set(reg.ALLOWED_HOSTS) | set(sp.PACKAGE_HOSTS) | {"raw.githubusercontent.com", "*.hf.co"}
    body = "\n".join(rows(2))
    named = set(re.findall(r"(?<![\w.])((?:\*\.)?[a-z0-9-]+(?:\.[a-z0-9-]+)*\.(?:com|co|org|io))\b", body))
    named = {n for n in named if "." in n and n not in {"state/consent.json"}}
    assert {"github.com", "raw.githubusercontent.com", "pypi.org", "files.pythonhosted.org", "huggingface.co"} <= named, named
    assert named <= known | {"hf.co"}, named - known


def test_every_front_that_can_reach_the_network_has_a_row_in_section_two():
    body = "\n".join(rows(2))
    flows = sorted(p.stem for p in (PKG / "core").glob("*_flow.py") if re.search(r"\bnetworked\b|\bfetch\.", p.read_text(encoding="utf-8")))
    assert flows == ["buildenv_flow", "guided_flow", "recordings_flow", "refresh_flow", "update_flow", "voices_flow"], flows
    for fragment in ("Setting up ACK Voice Studio", "`recordings model`", "`voices get`", "`python3 -m voice_studio.update`", "`refresh repair`", "`refresh rebuild`"):
        assert fragment in body, fragment
    assert "`refresh check` only looks, and reaches no network" in body and "**nobody**" in body


def test_the_row_for_giving_the_voice_file_to_the_phone_says_what_the_listener_does():
    from voice_studio.core import lansend, phonecert
    row = next(r for r in rows(2) if "`voicefile send`" in r).replace("**", "")
    for claim in ("no host on the internet", "one device on your own home network", "a secret token", "a secure connection", "stops after the first complete download", "Asks first", "shows the address",
                  "ends by itself in %d minutes" % lansend.MINUTES, "nothing else on the computer can be fetched", "its secret part stays on this computer and is not in a backup", "copy the zip file by cable or USB drive"):
        assert claim in row, claim
    assert lansend.MINUTES == 10 and phonecert.folder(DataHome("~")) == "~/ack-voice-studio/state/phone-certificate"
    assert {a.id: a.backed_up for a in areas.HOME_AREAS}["state"] is False, "the certificate's secret part lives under state, which no backup holds"
    everything_else = next(r for r in rows(2) if "Everything else in ACK Voice Studio" in r)
    assert "the voice file" not in everything_else.replace("making the voice file", ""), "giving it to a phone is not 'nobody'"


def test_what_the_page_says_every_download_does_first_is_what_the_tool_does():
    body = "\n".join(rows(2))
    for claim in ("Each download is listed with its size and asked about first", "a starting voice asks twice and shows its licence", "Says first what it will ask and shows the commands; nothing is checked in the background"):
        assert claim in body.replace("**", ""), claim


def test_the_tests_the_page_cites_exist_and_the_files_it_warns_about_are_listed():
    cited = re.findall(r"`(test_vs_[a-z_]+\.py)`", section(7))
    assert len(cited) >= 6
    for name in cited:
        assert (PKG / "tests" / name).is_file(), name
    assert "ACK Voice Studio **backup** or a saved\n  **problem report**" in section(6)
    assert "ACK Voice Studio" in DOC.split("## 1.", 1)[0]
