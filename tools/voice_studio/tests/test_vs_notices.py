# SPDX-License-Identifier: GPL-3.0-or-later
"""THIRD_PARTY_NOTICES.md section 7 (plan task VS-8.4): every system package the guided setup asks `apt` for is named in the notices, the rows for the ones added late say how they were
checked, and the section no longer says it is a plan."""
import re
from pathlib import Path

from voice_studio.core import preflight

ROOT = Path(__file__).resolve().parents[3]
NOTICES = (ROOT / "THIRD_PARTY_NOTICES.md").read_text(encoding="utf-8")


def section(number):
    return re.search(r"^## %s\..*?(?=^## |\Z)" % number, NOTICES, flags=re.S | re.M).group(0)


def rows(number):
    return [line for line in section(number).splitlines() if line.startswith("| ") and not line.startswith(("| Item", "| ---", "|---"))]


def test_every_package_the_setup_installs_with_apt_is_named_in_the_notices():
    names = [r.package for r in preflight.REQUIREMENTS]
    assert len(names) == 7 and {"git", "ffmpeg", "build-essential", "python3-venv", "python3-dev", "python3-gi", "gir1.2-gtk-4.0"} == set(names)
    missing = [name for name in names if "`%s`" % name not in NOTICES]          # in backticks: a bare "git" would be found inside "github.com"
    assert not missing, missing


def test_the_section_is_no_longer_called_a_plan():
    body = section(7)
    assert body.startswith("## 7. ACK Voice Studio")
    assert "being built" not in body.splitlines()[0] and "Planned dependencies" not in body
    assert "Each row says how it was checked" in body and "None of this is shipped in the repository" in body


def test_the_git_row_says_what_was_read_when_and_what_was_not():
    row = next(r for r in rows(7) if r.startswith("| `git`"))
    for claim in ("GPL-2", 'it says "GPL-2", not "or later"', "2026-10-16", "Ubuntu 24.04", "/usr/share/doc/git/copyright", "Ubuntu 22.04's package was not read", "not distributed by this project",
                  "Running a program is not linking to it"):
        assert claim in row, claim


def test_the_build_tools_row_names_each_package_its_licences_and_what_was_not_read():
    row = next(r for r in rows(7) if r.startswith("| The build tools"))
    item = re.split(r"(?<!\\)\|", row.strip().strip("|"))[0]
    for name in ("build-essential", "gcc", "g++", "make", "python3-dev", "python3-venv"):
        assert "`%s`" % name in item, name
    for claim in ("GPL-2.0-or-later", "GPL-3.0-or-later with the GCC Runtime Library Exception 3.1", "Python Software Foundation licence", "2026-10-16", "Not read:", "Ubuntu 22.04",
                  "not distributed by this project"):
        assert claim in row, claim


def test_every_row_of_the_first_table_says_its_licence_and_how_it_was_checked():
    lines = section(7).splitlines()
    start = next(i for i, line in enumerate(lines) if line.startswith("| Item | License | Checked | Note |"))
    table = []
    for line in lines[start + 2:]:
        if not line.startswith("| "):
            break
        table.append(line)
    assert len(table) >= 9
    for row in table:
        cells = re.split(r"(?<!\\)\|", row.strip().strip("|"))
        assert len(cells) == 4, row[:80]
        assert cells[1].strip() and cells[2].strip(), "a row must say its licence and how that was checked: " + row[:80]
