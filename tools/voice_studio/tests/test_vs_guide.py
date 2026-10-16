# SPDX-License-Identifier: GPL-3.0-or-later
"""The beginner guide and the helper handout (plan task VS-8.1) are held to the code: every command in them exists and takes the options it is given, every sentence quoted as the tool's is one the tool says,
every button named is a button, every figure is the code's, and the prose keeps to everyday words (decision D19). What they say has not been tried is checked against the checklist."""
import json
import re
import shlex
from pathlib import Path

import pytest

import test_vs_device_test_doc as device_doc
from test_vs_text import JARGON
from vs_startvoice_helpers import implies_permission
from voice_studio.core import (backup_flow, commands, preflight, projects_flow, recordings_flow, refresh_flow, registry as reg, reportcmd_flow, rounds_flow, scratchmove_flow, startvoice,
                               text as vtext, uninstall_flow, update_flow, voicefile_flow, voices_flow)
from voice_studio.core.text import size_text

ROOT = Path(__file__).resolve().parents[3]
DOCS = ROOT / "docs"
GUIDE, HANDOUT = DOCS / "VOICE_STUDIO_GUIDE.md", DOCS / "VOICE_STUDIO_HELPER_HANDOUT.md"
PAGES = {"guide": GUIDE, "handout": HANDOUT}
FLOWS = {"projects": projects_flow, "recordings": recordings_flow, "voices": voices_flow, "rounds": rounds_flow, "voicefile": voicefile_flow, "backup": backup_flow, "refresh": refresh_flow,
         "uninstall": uninstall_flow, "scratch": scratchmove_flow, "update": update_flow, "report": reportcmd_flow}
TAKES_A_VALUE = {"--project", "--name", "--kind", "--table", "--set", "--minutes", "--to", "--round", "--folder", "--text", "--step", "--problem", "--detail", "--job", "--hours", "--programs",
                 "--saved", "--working", "--copies", "--clips", "--max-gain-db", "--address", "--port"}


def text_of(path):
    return path.read_text(encoding="utf-8")


def prose(path):
    """The words a reader reads: without the code blocks and without anything in backticks."""
    body = re.sub(r"```.*?```", " ", text_of(path), flags=re.S)
    body = "\n".join(line for line in body.splitlines() if not line.startswith("|"))          # a table is not a sentence
    return re.sub(r"`[^`\n]*`", " ", body)


def catalog():
    data = json.loads((vtext.DATA_DIR / "en.json").read_text(encoding="utf-8"))
    return {**data["strings"], **{k: v["other"] for k, v in data["plurals"].items()}}


# ---------------------------------------------------------------- the commands

@pytest.mark.parametrize("name", PAGES)
def test_every_command_names_a_real_tool_and_command_and_takes_the_options_it_is_given(name):
    found = re.findall(r"python3 -m voice_studio\.([a-z]+)(?: ([a-z]+))?([^\n`]*)", text_of(PAGES[name]))
    assert found, name
    for module, command, rest in found:
        if module == "report" and command == "":
            continue
        assert module in FLOWS, module
        table = FLOWS[module].OPTIONS
        assert command in table, (module, command)
        words, i = shlex.split(rest.replace("~", "/home/x")), 0
        while i < len(words):
            if words[i].startswith("-"):
                assert words[i] in table[command], (module, command, words[i])
                i += 2 if words[i] in TAKES_A_VALUE else 1
            else:
                i += 1


def test_the_commands_in_the_guide_blocks_start_the_way_the_installation_guides_do():
    for block in re.findall(r"```bash\n(.*?)```", text_of(GUIDE), flags=re.S):
        for line in block.strip().splitlines():
            assert line.startswith("PYTHONPATH=~/ack-tools/tools python3 -m voice_studio."), line


def test_the_tools_and_options_the_guide_leans_on_are_the_ones_it_names():
    body = text_of(GUIDE)
    for fragment in ("voice_studio.projects new --own --name", "voice_studio.recordings import", "--kind package", "voice_studio.recordings model", "voice_studio.recordings finish",
                     "voice_studio.recordings set", "voice_studio.voices get mike --project anna", "voice_studio.rounds start --set dataset-1", "voice_studio.rounds stop",
                     "voice_studio.voicefile listen --project anna --round 1", "voice_studio.rounds choose 2", "voice_studio.rounds back", "voice_studio.voicefile make",
                     "voice_studio.backup now --project anna --to", "voice_studio.report show", "voice_studio.report save --to"):
        assert fragment in body, fragment
    assert recordings_flow.OPTIONS["import"] >= {"--kind", "--project"} and startvoice.find_voice(reg.load_registry(), "mike") == "voice-mike"
    assert "package" in recordings_flow.KINDS if hasattr(recordings_flow, "KINDS") else True


# ---------------------------------------------------------------- what the tool says, and the buttons

@pytest.mark.parametrize("name", PAGES)
def test_every_sentence_quoted_as_the_tools_is_one_the_tool_says(name):
    spans = re.findall(r"`([^`\n]+)`", text_of(PAGES[name]))
    quoted = [(s.rstrip(" …").rstrip(), s.endswith("…")) for s in spans if " " in s and s.rstrip()[-1] in ".?…:" and not s.startswith(("PYTHONPATH", "python3", "~/", "cd "))]
    for sentence, cut in quoted:
        assert device_doc.says(sentence, cut), "quoted as the tool's, and it is not: " + sentence
    if name == "guide":
        assert len(quoted) >= 13, quoted


def test_the_two_sentences_quoted_about_progress_are_the_ones_the_screens_say():
    body = text_of(GUIDE)
    strings = catalog()
    assert "`About 20 of 60 minutes of speech you can use so far.`" in body and strings["progress.minutes"] == "About {minutes} of {target} minutes of speech you can use so far."
    assert "`Every minute helps the voice sound steadier.`" in body and "Every minute helps the voice sound steadier." in strings["progress.next.record_more"]
    assert "The plan needs at least half an hour of recording." in strings["newproject.problem.hours.too_small"] and "at least half an hour" in text_of(GUIDE)


def test_the_three_sentences_the_guide_says_are_spoken_are_the_three_the_computer_says():
    strings = catalog()
    spoken = " ".join(strings["listen.sentence.%d" % n] for n in (1, 2, 3))
    assert spoken == "Hello, my name is Anna. I need some help, please. Thank you, that is all."
    assert "*%s*" % spoken in text_of(GUIDE)


def test_every_page_and_button_named_in_the_window_column_is_one_the_window_has():
    strings = set(catalog().values())
    nav = {strings_value for key, strings_value in catalog().items() if key.startswith("window.nav.")}
    rows = [line for line in text_of(GUIDE).splitlines() if re.match(r"^\| \d+ \|", line)]
    assert len(rows) == 10
    named = 0
    for row in rows:
        cell = row.split("|")[3].strip()
        if not cell:
            continue
        page, _, buttons = cell.partition(", ")
        assert page in nav, page
        for label in re.findall(r"`([^`]+)`", buttons):
            named += 1
            bare = label.rstrip("…")
            assert any(v == label or v.startswith(bare) for v in strings), label
    assert named >= 9
    for label in ("Put away…", "Delete…", "Free up space", "Show the folder", "Stop the round that is training", "Choose this round", "Start a round…", "Make the voice file…"):
        assert label in strings or any(v.startswith(label.rstrip("…")) for v in strings), label
        assert label in text_of(GUIDE) or label in text_of(HANDOUT), label


def test_the_handouts_buttons_are_buttons():
    strings = set(catalog().values())
    for label in re.findall(r"`([^`]*…)`", text_of(HANDOUT)):
        assert label in strings, label


# ---------------------------------------------------------------- the figures

def test_the_figures_the_guide_gives_are_the_codes():
    body = text_of(GUIDE)
    assert commands.ROUND_MINUTES == 25 and "rounds* of about 25 minutes" in body and "A round is about 25 minutes" in body and "About 25 minutes" not in body
    assert "about 25 minutes" in text_of(HANDOUT)
    items = {i.id: i for i in reg.load_registry().items}
    model = sum(i.size_bytes for i in reg.load_registry().items if i.folder == "speech-small-en")
    assert abs(model - 485_000_000) < 2_000_000 and "(about 485 MB)" in body and size_text(model) in ("485 MB", "486 MB")
    assert abs(items["voice-mike"].size_bytes - 846_000_000) < 1_000_000 and abs(items["voice-amy"].size_bytes - 846_000_000) < 1_000_000 and "about 846 MB" in body
    assert preflight.GPU_MIN_MIB == 7900 and "8 GB of its own memory" in body and "about 25 GB of free room" in body
    for guide in ("ACK_Voice_Studio_Installation_Guide.MD", "ACK_Voice_Studio_Installation_Guide_Ubuntu.MD"):
        installation = text_of(DOCS / guide)
        assert "At least 25 GB free" in installation or "at least 25 GB free" in installation.lower(), guide
        assert "8 GB or more of its own memory" in installation


def test_the_300_megabytes_the_handout_gives_are_the_phones():
    kotlin = (ROOT / "app/src/main/java/com/example/besu/capture/TrainingData.kt").read_text(encoding="utf-8")
    assert "MIN_FREE_TO_START_BYTES = 300L * 1024 * 1024" in kotlin and "about 300 MB of free room" in text_of(HANDOUT)


def test_the_free_speech_warning_is_in_both_pages_and_in_the_app():
    for page in (GUIDE, HANDOUT):
        assert "records anyone who is nearby" in text_of(page) or "records everyone nearby" in text_of(page)
    assert "FREE SPEECH RECORDS EV" in (ROOT / "CHANGELOG.md").read_text(encoding="utf-8").upper()


# ---------------------------------------------------------------- everyday words (D19)

@pytest.mark.parametrize("name", PAGES)
def test_the_prose_uses_no_jargon_and_no_long_sentences_and_implies_no_permission(name):
    body = prose(PAGES[name])
    for term in JARGON:
        assert not re.search(r"\b%s\b" % re.escape(term), body, re.IGNORECASE), (name, term)
    plain = re.sub(r"[#*|>_-]+", " ", body)
    for sentence in re.split(r"(?<=[.!?:])\s+", plain):
        assert len(sentence.split()) <= 40, (name, sentence)
    assert implies_permission(plain) == [], (name, implies_permission(plain))


# ---------------------------------------------------------------- the pages hold together

def test_the_guide_has_its_eight_sections_and_names_the_files_it_points_at():
    headings = re.findall(r"^## (\d+)\. (.*)$", text_of(GUIDE), flags=re.M)
    assert [int(n) for n, _ in headings] == list(range(1, 9)) and headings[0][1].startswith("What it does") and headings[7][1] == "What has been tried"
    for page in PAGES.values():
        for name in set(re.findall(r"`([A-Za-z_]+\.(?:md|MD))`", text_of(page))):
            assert (DOCS / name).is_file(), (page.name, name)
    assert "VOICE_STUDIO_HELPER_HANDOUT.md" in text_of(GUIDE) and "VOICE_STUDIO_GUIDE.md" in text_of(HANDOUT)
    for number in re.findall(r"\bsection (\d+)\b", text_of(GUIDE)):
        assert 1 <= int(number) <= 11, number


def test_the_section_numbers_the_guide_points_at_are_the_sections_that_say_those_things():
    body = text_of(GUIDE)
    sections = dict(re.findall(r"^## (\d+)\. (.*)$", body, flags=re.M))
    assert "special meaning" in body and "section 7 explains each one" in body and sections["7"] == "Words used here"
    assert "Section 8 says what has been tried" in body and sections["8"] == "What has been tried"
    assert "(section 5 says how)" in body and sections["5"] == "Looking after your work"
    assert "the rounds in section 4" in body and sections["4"].startswith("The path")


def test_the_handout_is_one_page():
    body = text_of(HANDOUT)
    assert len(body.split()) <= 520 and len(body.splitlines()) <= 60 and body.startswith("# ACK Voice Studio: a page for the helper")
    for heading in ("Before you start", "While recording on the phone", "After the session", "Looking after it", "Who decides"):
        assert "## " + heading in body, heading


def test_the_pages_keep_the_promises_the_tool_keeps():
    body, handout = text_of(GUIDE), text_of(HANDOUT)
    for claim in ("the tool never sends it", "Everything is kept in the folder `ack-voice-studio` in your home folder", "never uploaded, and there is no account", "it asks before each download",
                  "It is not encrypted", "asks twice", "It never touches a project, a recording"[:0] or "Neither touches a project, a recording, a backup or a starting voice",
                  "Nothing is deleted when you choose or go back", "It never replaces the copy you are using"):
        assert claim.lower() in body.lower() or claim.lower() in handout.lower(), claim
    assert "Never send recordings by chat or email." in handout and "the tool never sends it" in handout.lower()


# ---------------------------------------------------------------- honesty: what the guide says has not been run

def test_what_the_guide_says_has_not_been_run_is_what_the_checklist_says_has_not_been_run():
    body = text_of(GUIDE).split("## 8. What has been tried", 1)[1]
    for part in ("backup", "refresh", "uninstall", "move", "update", "problem report"):
        assert part in body, part
    for number in ("I9", "I10", "I11", "I12", "I13", "I14"):
        assert "**New, and not yet run on a real computer.**" in device_doc.section(number + "."), number
    assert "RTX 4060" in body and "WSL2" in body and "three training rounds" in body.lower()
    it_guide = text_of(DOCS / "VOICE_STUDIO_IT_GUIDE.md")
    assert "RTX 4060" in it_guide and "WSL2" in it_guide and "Native Ubuntu (no WSL)" in it_guide and "A normal Ubuntu desktop on its own hardware has not been tried either" in body
    assert "**not** been run on a real computer" in body


# ---------------------------------------------------------------- the older guides become the manual route (plan task VS-8.2, decision D23)

@pytest.mark.parametrize("name", ["VOICE_TRAINING_GUIDE.md", "VOICE_DATA_WSL_GUIDE.md"])
def test_the_older_guides_say_they_are_the_manual_route_near_the_top_and_point_at_the_guide(name):
    top = "\n".join(text_of(DOCS / name).splitlines()[:20])
    assert "> **This is the manual route.**" in top and "(VOICE_STUDIO_GUIDE.md)" in top and "Start with" in top
    assert text_of(DOCS / name).count("This is the manual route.") == 1


def test_what_the_manual_route_notes_say_about_the_tool_is_true():
    training = text_of(DOCS / "VOICE_TRAINING_GUIDE.md")
    assert "its own pinned copy of the trainer under `~/ack-voice-studio/tool`" in training
    from voice_studio.core.paths import DataHome
    assert DataHome("~").environments == "~/ack-voice-studio/tool/environments"
    naming = [p.name for p in sorted((ROOT / "tools/voice_studio/core").glob("*.py")) if "~/piper1-gpl" in p.read_text(encoding="utf-8")]
    assert naming == ["legacy.py"], "only the code that finds an older hand-made setup names a clone of the trainer in the home folder"
    assert re.search(r"^piper-tts==", text_of(ROOT / "tools/voice_studio/data/locks/training.lock.txt"), re.M), "the trainer is the published wheel in the training lock"
    assert "leave the `~/ack-voice-studio` folder alone" in text_of(DOCS / "VOICE_DATA_WSL_GUIDE.md")
