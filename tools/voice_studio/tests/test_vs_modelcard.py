# SPDX-License-Identifier: GPL-3.0-or-later
"""The card beside a voice file (core/modelcard.py, decisions D21 and D27, choices P27). What is held to here: it says only what the project recorded and says when something is not recorded;
the starting voice comes from the training record and never from anywhere else; the chain and the acknowledgment are the ones shown before the download; the consent note's words, the project's
name and this computer's paths never reach it; nothing in it says that use is allowed; and the file is written once, owner-only, without leaving a half-written one."""
import os
import stat
from dataclasses import replace

import pytest

from vs_startvoice_helpers import LESSAC_PAGE, NOW, implies_permission, leaked_keys, make_project, make_registry, make_voice
from voice_studio.core import modelcard as mc, project as pj, rounds as rd, startvoice, text
from voice_studio.core.project import Acknowledgment, Consent
from voice_studio.core.text import size_text

CAT = text.load_catalog("en")
STAMP = "2026-10-11T13:05:09Z"


def finished(number, parent, voice="", minutes=45, state="finished"):
    return rd.Round(number, parent, voice, "set", minutes, state, "2026-10-11T10:00:00Z", "2026-10-11T11:00:00Z", has_checkpoint=True)


def record(*rounds, current=None):
    return rd.Record(tuple(rounds), current=current if current is not None else rounds[-1].number)


MIKE = record(finished(1, 0, "voice-mike"), finished(2, 1))
ACK = (Acknowledgment("voice-mike", "2026-10-09T08:00:00Z", "0123abcd"),)


def build(rec=MIKE, number=2, the_project=None, registry="default", **over):
    the_project = the_project or make_project(acknowledgments=ACK)
    registry = make_registry() if registry == "default" else registry
    kw = dict(zip_bytes=63_517_438, model_sha256="a" * 64, config_sha256="b" * 64, made_at=STAMP, tool_version="0.0.1",
              programs={"id": "training-abc", "fingerprint": "0123456789abcdef" * 4})
    kw.update(over)
    return mc.gather(rec, number, the_project, registry, **kw)


def card_text(**kw):
    return mc.build_card(build(**kw), CAT).text


# ---------------------------------------------------------------- what the card says

def test_the_card_gives_the_voice_file_with_its_size_its_time_and_both_check_codes_but_not_its_file_name():
    body = card_text()
    assert body.splitlines()[0] == "Voice file card"
    assert "  Zip file for ACK: %s" % size_text(63_517_438) in body.splitlines() and ".zip (" not in body and "anna" not in body
    assert "  Made on: 2026-10-11 13:05 UTC" in body.splitlines()
    assert "  Check code of the voice (SHA-256): " + "a" * 64 in body.splitlines()
    assert "  Check code of its settings file (SHA-256): " + "b" * 64 in body.splitlines()


def test_the_starting_voice_is_the_one_the_first_round_of_the_training_names_and_the_chain_is_the_one_shown_before_the_download():
    body = card_text()
    lines = body.splitlines()
    assert "  It was trained further from the starting voice Mike." in lines
    for link in startvoice.card(make_registry(), "voice-mike").links:
        assert "  " + CAT.t("startvoice.link.%s.name" % link.id) in lines
        for statement in link.statements:
            assert "    " + CAT.t("startvoice.says." + statement) in lines
    assert "    Page to read: " + LESSAC_PAGE in lines and "    Page to read: https://github.com/example/recordings" in lines
    assert "  " + CAT.t("startvoice.read_on", date=startvoice.FACTS_READ_ON) in lines
    assert "  " + CAT.t("startvoice.not_hosted") in lines and "  " + CAT.t("startvoice.not_advice") in lines
    assert "  The tool names huggingface.co as the place that file comes from." in lines


def test_amy_gets_her_own_chain_not_mikes():
    body = card_text(rec=record(finished(1, 0, "voice-amy"), finished(2, 1)), the_project=make_project(acknowledgments=(Acknowledgment("voice-amy", "2026-10-09T08:00:00Z", "0123abcd"),)))
    assert "the starting voice Amy." in body and CAT.t("startvoice.says.amy_recordings") in body
    assert "Mike" not in body and CAT.t("startvoice.says.mike_recordings") not in body


def test_the_acknowledgment_is_the_projects_own_with_its_date_and_revision():
    body = card_text()
    assert "  Shown where it comes from, and acknowledged in this project on 2026-10-09, for revision 0123abcd." in body.splitlines()


def test_every_acknowledgment_of_that_voice_is_listed_oldest_first_and_another_voices_is_left_out():
    acks = (Acknowledgment("voice-mike", "2026-10-10T08:00:00Z", "ffff0000"), Acknowledgment("voice-amy", "2026-10-01T08:00:00Z", "99999999"),
            Acknowledgment("voice-mike", "2026-10-09T08:00:00Z", "0123abcd"))
    lines = card_text(the_project=make_project(acknowledgments=acks)).splitlines()
    first = "  Shown where it comes from, and acknowledged in this project on 2026-10-09, for revision 0123abcd."
    second = "  Shown where it comes from, and acknowledged in this project on 2026-10-10, for revision ffff0000."
    assert lines.index(first) + 1 == lines.index(second) and not any("99999999" in l for l in lines)


def test_a_voice_with_no_acknowledgment_says_so_instead_of_inventing_one():
    lines = card_text(the_project=make_project()).splitlines()
    assert "  This project has no acknowledgment recorded for that voice." in lines and not any("acknowledged in this project on" in l for l in lines)


def test_when_the_training_record_names_no_starting_voice_nothing_is_taken_from_anywhere_else():
    project_with_voice = make_project(starting_voice="voice-mike", acknowledgments=ACK)
    body = card_text(rec=record(finished(1, 0, ""), finished(2, 1)), the_project=project_with_voice)
    assert "  The training record does not say which starting voice this voice was trained from. Nothing is guessed." in body.splitlines()
    assert "Mike" not in body and "acknowledged in this project" not in body and "Page to read" not in body


def test_a_chain_that_does_not_reach_a_first_round_names_no_voice():
    assert mc.lineage_start(record(finished(2, 1, "voice-mike")), 2) == (1, "")


def test_a_starting_voice_this_version_does_not_know_is_named_and_nothing_more_is_said():
    body = card_text(rec=record(finished(1, 0, "voice-zed"), finished(2, 1)))
    assert "  The training record names the starting voice voice-zed. This version of the tool does not know that voice, so nothing more is said about it." in body.splitlines()
    assert "Page to read" not in body and "acknowledged in this project" not in body


def test_a_voice_the_registry_no_longer_has_reads_as_unknown():
    body = card_text(registry=make_registry(mike=None))
    assert "does not know that voice" in body and "Page to read" not in body


def test_without_a_registry_the_voice_reads_as_unknown_rather_than_failing():
    assert "does not know that voice" in card_text(registry=None)


@pytest.mark.parametrize("voice", ["../etc", "voice mike", "", "x" * 61, "-start", "voice\nmike", "voice-mike\n", "voice-mike\r\n"])
def test_a_starting_voice_that_is_not_a_plain_word_is_not_copied_into_the_card(voice):
    body = card_text(rec=record(finished(1, 0, voice), finished(2, 1)))
    assert voice.strip() == "" or voice not in body
    assert "does not say which starting voice" in body


def test_a_revision_is_kept_whole_up_to_sixty_four_characters_and_cut_after():
    for length, kept in ((63, 63), (64, 64), (65, 64)):
        revision = "r" * length
        body = card_text(the_project=make_project(acknowledgments=(Acknowledgment("voice-mike", "2026-10-09T08:00:00Z", revision),)))
        assert "for revision %s." % ("r" * kept) in body and "for revision %s." % ("r" * (kept + 1)) not in body


def test_a_page_the_registry_does_not_have_is_not_printed_as_none():
    registry = make_registry(mike=None)
    item = make_voice("voice-mike", b"voice" * 20, pages=(("lessac", LESSAC_PAGE),))
    body = card_text(registry=type(registry)(registry.items + (item,)))
    assert "Page to read: " + LESSAC_PAGE in body and "None" not in body and body.count("Page to read:") == 1


def test_a_voice_with_no_known_host_does_not_get_a_host_line():
    registry = make_registry(mike=None)
    item = make_voice("voice-mike", b"voice" * 20, url=None)
    body = card_text(registry=type(registry)(registry.items + (item,)))
    assert "the place that file comes from" not in body and "None" not in body and "trained further from the starting voice Mike" in body


def test_a_complete_note_with_no_known_way_is_called_incomplete_never_left_out():
    inp = replace(build(the_project=else_project()), how_given="", note_complete=True)
    lines = mc.build_card(inp, CAT).text.splitlines()
    assert "  The consent note in the project is not complete." in lines and not any("records how the agreement" in l for l in lines)
    assert leaked_keys("\n".join(lines)) == []


def test_the_training_line_counts_the_rounds_behind_the_chosen_one_and_the_minutes():
    rec = record(finished(1, 0, "voice-mike", 30), finished(2, 1, "", 45), finished(3, 2, "", 20), finished(4, 2, "", 99), current=3)
    assert "  Taken from round 3. The rounds behind it number 3, about 95 minutes of training in all." in card_text(rec=rec, number=3).splitlines()
    assert mc.lineage_start(rec, 3) == (3, "voice-mike")


def test_the_training_line_says_the_recordings_are_not_described_and_not_part_of_the_file():
    assert "  Training used recordings made in this project. They are not part of the voice file and are not described here." in card_text().splitlines()


# ---------------------------------------------------------------- whose voice, and what must never be copied

NOTE = Consent("Zebedee Quux", "to train a voice for AAC", "on a Tuesday in March", "tell Wilhelmina by letter", "spoken", "")


def else_project(**over):
    fields = dict(whose_voice="someone_else", consent=NOTE, acknowledgments=ACK, name="Quentin Zorg", id="quentin-zorg")
    fields.update(over)
    return make_project(**fields)


def test_an_own_voice_project_says_so_and_that_nothing_checks_it():
    lines = card_text().splitlines()
    assert "  The project was set up as the person's own voice." in lines and "  Nothing checks this. It is what the project recorded." in lines
    assert not any(l.startswith("  A consent note is kept") for l in lines)


@pytest.mark.parametrize("how, words", [("spoken", "They said so"), ("signed", "They signed"), ("through_guardian", "Their guardian or supporter agreed for them"),
                                        ("using_aac", "They said so using their communication device"), ("other", "Another way")])
def test_someone_elses_voice_says_in_which_fixed_way_the_note_records_the_agreement_and_nothing_else(how, words):
    the_project = else_project(consent=replace(NOTE, how_given=how, how_given_other="by interpretive dance"))
    lines = card_text(the_project=the_project).splitlines()
    assert "  The project was set up as someone else's voice." in lines
    assert "  A consent note is kept in the project. It records how the agreement was given: %s. The note itself is not copied here." % words in lines
    assert "  Nothing checks this. It is what the project recorded." in lines


def test_none_of_the_notes_words_or_the_projects_name_reach_the_card():
    body = card_text(the_project=else_project(consent=replace(NOTE, how_given="other", how_given_other="Hieronymus gesture")))
    for private in ("Zebedee", "Quux", "Tuesday", "March", "Wilhelmina", "Hieronymus", "Quentin", "Zorg", "quentin-zorg", "train a voice for AAC"):
        assert private not in body, private


def test_this_computers_paths_and_the_users_name_are_not_in_the_card(tmp_path):
    body = card_text(the_project=else_project())
    assert str(tmp_path) not in body and "/home/" not in body and "/mnt/" not in body and "\\" not in body


def test_an_incomplete_note_is_called_incomplete_not_summarised():
    lines = card_text(the_project=else_project(consent=replace(NOTE, withdraw=""))).splitlines()
    assert "  The consent note in the project is not complete." in lines and not any("records how the agreement" in l for l in lines)


def test_a_note_with_no_known_way_is_called_incomplete_and_an_unknown_way_is_never_printed():
    body = card_text(the_project=else_project(consent=replace(NOTE, how_given="telepathy")))
    assert "not complete" in body and "telepathy" not in body


# ---------------------------------------------------------------- made with, and what the card holds

def test_the_tool_version_and_the_training_programs_are_given_as_recorded():
    lines = card_text().splitlines()
    assert "  ACK Voice Studio, version 0.0.1" in lines and "  Training programs: training-abc, build 0123456789" in lines


@pytest.mark.parametrize("programs", [None, {}, {"id": "../x", "fingerprint": "0123"}, {"id": 5, "fingerprint": 7}, "text"])
def test_programs_whose_record_cannot_be_read_are_not_guessed(programs):
    body = card_text(programs=programs)
    assert "  Training programs: their record could not be read." in body.splitlines() and "Training programs: training" not in body


def test_programs_with_an_id_but_no_readable_build_say_so_with_a_question_mark():
    assert "  Training programs: training-abc, build ?" in card_text(programs={"id": "training-abc"}).splitlines()


def test_a_missing_tool_version_is_a_question_mark_not_a_blank():
    assert "  ACK Voice Studio, version ?" in card_text(tool_version="").splitlines()


def test_the_card_ends_by_saying_what_it_holds_where_it_sits_and_that_publishing_is_separate():
    lines = card_text().splitlines()
    tail = lines[lines.index("What this card holds"):]
    assert tail == ["What this card holds", "  " + CAT.t("modelcard.holds.not"), "  " + CAT.t("modelcard.holds.where"), "  " + CAT.t("modelcard.holds.publish")]
    assert "not inside it" in tail[2] and "separate decision" in tail[3] and "does not name the project or the person" in tail[1]


def test_sections_come_in_a_fixed_order_with_a_blank_line_between():
    lines = card_text().splitlines()
    heads = ["The voice file", "Where it comes from", "How it was trained", "Whose voice it is", "Made with", "What this card holds"]
    at = [lines.index(h) for h in heads]
    assert at == sorted(at) and all(lines[i - 1] == "" for i in at)


def test_nothing_in_the_card_is_a_catalog_key_or_says_that_use_is_allowed():
    for kw in ({}, {"the_project": else_project()}, {"rec": record(finished(1, 0, ""), finished(2, 1))}, {"registry": None}, {"programs": None}):
        body = card_text(**kw)
        assert leaked_keys(body) == [] and implies_permission(body) == []


def test_both_starting_voices_give_a_card_that_says_nothing_about_permission():
    for voice in ("voice-mike", "voice-amy"):
        body = card_text(rec=record(finished(1, 0, voice), finished(2, 1)), the_project=make_project(acknowledgments=(Acknowledgment(voice, "2026-10-09T08:00:00Z", "0123abcd"),)))
        assert implies_permission(body) == [] and "no legal advice" in body


def test_the_same_input_gives_the_same_bytes():
    assert mc.build_card(build(), CAT).to_bytes() == mc.build_card(build(), CAT).to_bytes()
    assert mc.build_card(build(), CAT).to_bytes().endswith(b"\n") and not mc.build_card(build(), CAT).to_bytes().endswith(b"\n\n")


def registry_with_lessac_page(address):
    registry = make_registry()
    return type(registry)(tuple(replace(i, pages=tuple(sorted((name, address if name == "lessac" else other) for name, other in i.pages))) for i in registry.items))


def test_a_line_is_cut_at_exactly_four_hundred_characters_and_not_before():
    prefix = "    Page to read: "                               # four spaces of indent, then the words
    for extra, kept in ((0, True), (1, False), (-1, True)):
        address = "h" * (400 - len(prefix) + extra)
        body = card_text(registry=registry_with_lessac_page(address))
        line = next(l for l in body.splitlines() if l.startswith(prefix + "hhh"))
        assert len(line) == min(400, len(prefix) + len(address)) and (line.endswith(address) is kept)
    assert mc.MAX_LINE == 400


def test_the_cards_name_is_the_one_the_documents_name():
    assert mc.CARD_NAME == "MODEL_CARD.txt"


def test_the_card_opens_with_its_title_and_the_two_sentences_that_say_what_it_is_and_what_it_rests_on():
    lines = card_text().splitlines()
    assert lines[:5] == ["Voice file card", "", "This card describes one voice file made with ACK Voice Studio. It says where the voice comes from and how it was made.",
                         "It is written from what the project recorded. Nothing here has been checked against anything else.", ""]


@pytest.mark.parametrize("stamp, shown", [("2026-10-11T13:05:09Z", "2026-10-11 13:05 UTC"), ("2026-10-11T13:05:09", "2026-10-11T13:05:09"), ("x" * 50, "x" * 30),
                                          ("2026-10-11T13:05:09Z\n", "2026-10-11T13:05:09Z\n")])
def test_the_time_is_shown_in_utc_and_an_odd_stamp_is_cut_not_trusted(stamp, shown):
    assert mc._when(stamp) == shown


def test_gather_cleans_what_it_reads_from_the_projects_file():
    acks = (Acknowledgment("voice-mike", "2026-10-09T08:00:00Z\nINJECTED", "0123abcd\n\nline two"),)
    body = card_text(the_project=make_project(acknowledgments=acks))
    assert "INJECTED" not in body and "line two" in body and "\n\n  Shown" not in body
    assert mc.gather(MIKE, 2, make_project(acknowledgments=acks), make_registry(), zip_bytes=1, model_sha256="a", config_sha256="b", made_at=STAMP,
                     tool_version="0.0.1", programs=None).acknowledgments == (("2026-10-09", "0123abcd line two"),)


# ---------------------------------------------------------------- writing the file

def test_the_card_is_written_once_owner_only_with_exactly_its_bytes(tmp_path):
    card = mc.build_card(build(), CAT)
    path = mc.write_card(str(tmp_path), card)
    assert path == str(tmp_path / mc.CARD_NAME) and (tmp_path / mc.CARD_NAME).read_bytes() == card.to_bytes()
    assert stat.S_IMODE(os.stat(path).st_mode) == 0o600 and sorted(os.listdir(tmp_path)) == [mc.CARD_NAME]


def test_an_existing_card_is_never_replaced(tmp_path):
    (tmp_path / mc.CARD_NAME).write_text("the person's own edit")
    with pytest.raises(FileExistsError):
        mc.write_card(str(tmp_path), mc.build_card(build(), CAT))
    assert (tmp_path / mc.CARD_NAME).read_text() == "the person's own edit" and sorted(os.listdir(tmp_path)) == [mc.CARD_NAME]


def test_a_link_where_the_card_goes_counts_as_a_file_that_is_there(tmp_path):
    target = tmp_path / "elsewhere.txt"
    target.write_text("keep")
    os.symlink(target, tmp_path / mc.CARD_NAME)
    with pytest.raises(FileExistsError):
        mc.write_card(str(tmp_path), mc.build_card(build(), CAT))
    assert target.read_text() == "keep"


def test_while_it_is_being_written_the_card_is_a_hidden_temporary_file_and_never_a_half_card(tmp_path, monkeypatch):
    seen = []
    real = os.fsync

    def look(fd):
        seen.append(sorted(os.listdir(tmp_path)))
        real(fd)

    monkeypatch.setattr(os, "fsync", look)
    mc.write_card(str(tmp_path), mc.build_card(build(), CAT))
    assert len(seen) == 1 and len(seen[0]) == 1 and seen[0][0].startswith(".card-") and seen[0][0].endswith(".tmp") and mc.CARD_NAME not in seen[0]


def test_a_write_that_fails_part_way_leaves_no_card_and_no_temporary_file(tmp_path, monkeypatch):
    def broken(_fd):
        raise OSError(28, "No space left on device")
    monkeypatch.setattr(os, "fsync", broken)
    with pytest.raises(OSError):
        mc.write_card(str(tmp_path), mc.build_card(build(), CAT))
    assert os.listdir(tmp_path) == []


def test_a_stop_while_writing_leaves_nothing_behind(tmp_path, monkeypatch):
    def stop(_fd):
        raise KeyboardInterrupt()
    monkeypatch.setattr(os, "fsync", stop)
    with pytest.raises(KeyboardInterrupt):
        mc.write_card(str(tmp_path), mc.build_card(build(), CAT))
    assert os.listdir(tmp_path) == []


def test_the_card_sits_where_the_folder_is_and_nowhere_else(tmp_path):
    folder = tmp_path / "voice"
    folder.mkdir()
    mc.write_card(str(folder), mc.build_card(build(), CAT))
    assert sorted(os.listdir(tmp_path)) == ["voice"] and os.listdir(folder) == [mc.CARD_NAME]
