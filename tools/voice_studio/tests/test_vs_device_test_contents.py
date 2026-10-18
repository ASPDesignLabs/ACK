# SPDX-License-Identifier: GPL-3.0-or-later
"""The contents table at the top of docs/VOICE_STUDIO_DEVICE_TEST.md (plan task VS-8.5) lists every section of the checklist once, in the order they are written, with the title exactly as the
section's own heading has it, so a section added, renamed or moved without the table fails here."""
import re
from pathlib import Path

DOC = (Path(__file__).resolve().parents[3] / "docs" / "VOICE_STUDIO_DEVICE_TEST.md").read_text(encoding="utf-8")
HEADING = re.compile(r"^## ([0A-Z][0-9]*)\. (.+)$", flags=re.M)
START = "**Contents.**"


def headings():
    return HEADING.findall(DOC)


def table_rows():
    start = DOC.index(START)
    lines = DOC[start:].splitlines()
    head = next(i for i, line in enumerate(lines) if line.startswith("| Section | Title | In a few words |"))
    rows = []
    for line in lines[head + 2:]:
        if not line.startswith("| "):
            break
        cells = [c.strip() for c in line.strip().strip("|").split(" | ")]
        rows.append(cells)
    return rows


def test_the_table_lists_every_section_once_in_the_order_they_are_written_with_their_own_titles():
    rows = table_rows()
    assert len(headings()) >= 29
    assert [(r[0], r[1]) for r in rows] == headings()
    assert len({r[0] for r in rows}) == len(rows), "a section is listed once"


def test_the_table_is_before_the_first_section_and_every_row_has_words_of_its_own():
    assert DOC.index(START) < DOC.index("\n## 0. ")
    for cells in table_rows():
        assert len(cells) == 3 and cells[2].endswith(".") and 3 <= len(cells[2].split()) <= 20, cells
    words = [cells[2] for cells in table_rows()]
    assert len(set(words)) == len(words), "two sections are not described by the same words"


def test_it_says_nothing_about_the_order_it_cannot_promise():
    intro = DOC[DOC.index(START):DOC.index(START) + 220]
    assert "A section says when it needs an earlier one." in intro and "Do them in this order" not in intro
