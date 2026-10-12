# SPDX-License-Identifier: GPL-3.0-or-later
"""Choosing a starting voice and what comes before its download (plan task VS-4.1, decisions D25, D27, D30).

The rules under test: nothing is fetched until this project has acknowledged **this exact file** and the saved agreement names it; the acknowledgment is recorded with
the registry's own revision and a date; a re-pin asks again; a kept file is trusted only after it is read back and compared; the licence pages are shown and never
opened; and nothing the person reads says or implies that use is permitted.
"""
import json
import os
import re
import urllib.error
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

import pytest

from vs_env_helpers import FakeTime
from vs_fetch_helpers import FakeOpener
from vs_startvoice_helpers import LESSAC_PAGE, NOW, STAMP, VOICE_A, VOICE_B, implies_permission, make_project, make_registry, make_voice
from voice_studio.core import connection as cn
from voice_studio.core import fetch, startvoice as sv, text
from voice_studio.core.consent import ConsentRecord, load_consent, make_consent, save_consent
from voice_studio.core.paths import DataHome
from voice_studio.core.project import Acknowledgment, Project
from voice_studio.core.registry import Item, Registry, load_registry

REPO = Path(__file__).resolve().parents[3]
NOTICES = (REPO / "THIRD_PARTY_NOTICES.md").read_text(encoding="utf-8")
CAT = text.load_catalog("en")


class Rig:
    def __init__(self, tmp_path, registry=None, payload=VOICE_A, **opener_kw):
        self.home = DataHome(str(tmp_path / "home"))
        self.registry = registry or make_registry()
        self.project = make_project()
        self.opener = FakeOpener(payload, **opener_kw)
        self.time = FakeTime()
        self.waits, self.backs, self.progress = [], [], []

    def fetcher(self, item, dest, consent, **kw):
        return fetch.fetch(item, dest, consent, opener=self.opener, room_margin=0, **kw)

    def fetch(self, voice_id="voice-mike", project=None, **kw):
        return sv.fetch_voice(project or self.project, self.registry, voice_id, self.home, on_wait=self.waits.append, on_back=lambda: self.backs.append(1),
                              sleep=self.time.sleep, clock=self.time.monotonic, fetcher=self.fetcher, progress=lambda d, t: self.progress.append((d, t)), **kw)

    def acknowledge(self, voice_id="voice-mike"):
        self.project = sv.acknowledge(self.project, self.registry, voice_id, NOW)

    def agree(self, voice_id="voice-mike"):
        return sv.agree_to_download(self.registry, voice_id, self.home, NOW)

    def item(self, voice_id="voice-mike"):
        return self.registry.get(voice_id)

    def folder(self, voice_id="voice-mike"):
        return Path(self.home.voices) / voice_id


@pytest.fixture
def rig(tmp_path):
    return Rig(tmp_path)


def refusal(call, *args, **kw):
    with pytest.raises(sv.StartVoiceError) as caught:
        call(*args, **kw)
    return caught.value.code


# ---------------------------------------------------------------- what is known about each voice

def test_every_starting_voice_in_the_shipped_registry_has_facts_and_every_fact_names_a_voice_the_registry_has():
    registry = load_registry()
    in_registry = {i.id for i in registry.items if i.kind == "voice"}
    assert in_registry == {f.voice_id for f in sv.FACTS} == {"voice-mike", "voice-amy"}
    assert [c.voice_id for c in sv.voices(registry)] == ["voice-mike", "voice-amy"]


def test_each_link_the_facts_name_has_its_page_in_the_registry_and_the_registry_names_no_page_the_facts_do_not():
    registry = load_registry()
    for facts in sv.FACTS:
        item = registry.get(facts.voice_id)
        assert [name for name, _ in item.pages] == sorted(link.id for link in facts.links), facts.voice_id
        assert all(item.page(link.id) for link in facts.links)


def test_the_two_choices_are_the_plans_male_and_female_voices():
    by_id = {f.voice_id: f.choice for f in sv.FACTS}
    assert by_id == {"voice-mike": "male", "voice-amy": "female"} and set(by_id.values()) == set(sv.CHOICES)


def test_the_pages_shown_are_the_ones_the_notices_say_were_read_and_the_statements_say_what_the_notices_say():
    registry = load_registry()
    for facts in sv.FACTS:
        for _, address in registry.get(facts.voice_id).pages:
            assert "`%s`" % address in NOTICES, address          # the whole address between its backticks: a shortened one must not pass as a substring
    says = lambda key: CAT.t("startvoice.says." + key)
    assert "lists their licence as CC0." in says("mike_recordings") and "**CC0**" in NOTICES, "the model card's own line"
    assert "licensed under CC0 (public domain)" in says("mike_recordings") and '"These datasets are licensed under CC0 (public domain)"' in NOTICES, "the recordings' own page"
    assert "not established" in says("amy_recordings") and "See URL" in NOTICES and "**not established**" in NOTICES
    assert "Research Licence Agreement" in says("lessac_terms") and "Research Licence Agreement" in NOTICES
    assert "research purposes only" in says("lessac_terms") and "for Research Purposes only" in NOTICES
    assert "not settled" in says("lessac_unsettled") and "not settled here" in NOTICES
    assert "Blizzard 2013" in says("lessac_origin") and "from scratch" in says("lessac_origin") and '"Trained from scratch"' in NOTICES
    assert sv.FACTS_READ_ON in NOTICES


def test_the_chain_for_each_voice_is_the_voice_then_lessac_and_the_text_catalog_has_words_for_every_link_and_statement():
    for facts in sv.FACTS:
        assert [l.id for l in facts.links][-1] == "lessac" and len(facts.links) == 2
        assert "made_from_lessac" in facts.links[0].statements
    for link in sv.LINK_IDS:
        assert CAT.t("startvoice.link.%s.name" % link) != "startvoice.link.%s.name" % link
    for statement in sv.STATEMENTS:
        assert CAT.t("startvoice.says." + statement) != "startvoice.says." + statement


# ---------------------------------------------------------------- what is said never says or implies that use is permitted

def shown_texts():
    data = json.loads((text.DATA_DIR / "en.json").read_text(encoding="utf-8"))["strings"]
    return {k: v for k, v in data.items() if k.startswith("startvoice.")}


def test_no_starting_voice_text_says_or_implies_that_use_is_permitted():
    assert shown_texts()
    for key, value in shown_texts().items():
        assert implies_permission(value) == [], (key, value)


def test_the_permission_check_can_actually_fail():
    for bad in ("It is free for personal use.", "You are allowed to use it.", "Use is permitted.", "It is legal to use.", "You may use this voice.", "It is safe to use."):
        assert implies_permission(bad) == [bad], bad
    assert implies_permission("Whether your use is allowed is for you to decide.") == []
    assert implies_permission("This project gives no legal advice. Whether your use is allowed is for you to decide.") == []


def test_the_notices_say_no_legal_advice_leave_the_decision_to_the_person_and_say_nothing_is_hosted():
    advice = CAT.t("startvoice.not_advice")
    assert "no legal advice" in advice and "Whether your use is allowed is for you to decide." in advice
    hosted = CAT.t("startvoice.not_hosted")
    assert "does not host" in hosted and "mirror" in hosted and "original site" in hosted
    assert "{date}" in CAT.t("startvoice.read_on")
    assert set(sv.NOTICE_KEYS) <= set(shown_texts()) and len(sv.NOTICE_KEYS) == 5


def test_the_note_about_when_the_pages_were_read_takes_the_date_the_facts_carry():
    line = CAT.t("startvoice.read_on", date=sv.FACTS_READ_ON)
    assert sv.FACTS_READ_ON in line and "{date}" not in line and "read them yourself" in line


# ---------------------------------------------------------------- a card for the screen

def test_a_card_shows_the_choice_the_size_the_revision_the_site_the_pages_and_that_it_is_pinned():
    registry = load_registry()
    card = sv.card(registry, "voice-mike")
    item = registry.get("voice-mike")
    assert (card.voice_id, card.choice, card.size_bytes, card.exact, card.revision, card.host, card.pinned, card.problems) == \
           ("voice-mike", "male", 845891981, True, item.revision, "huggingface.co", True, ())
    assert [(l.id, l.page) for l in card.links] == [("mike", item.page("mike")), ("lessac", LESSAC_PAGE)] and card.read_on == sv.FACTS_READ_ON
    assert card.links[0].statements == ("mike_recordings", "made_from_lessac")
    assert card.links[1].statements == ("lessac_origin", "lessac_terms", "lessac_ends", "lessac_unsettled")


def test_a_card_for_a_voice_that_cannot_be_fetched_yet_says_why_and_shows_the_hosts_approximate_size():
    unpinned = Registry((Item("voice-amy", "voice", "fetch.why.voice_amy", "voice-amy-card", approx_size_bytes=846_000_000),))
    card = sv.card(unpinned, "voice-amy")
    assert (card.pinned, card.problems, card.exact, card.size_bytes, card.revision, card.host) == (False, ("unpinned",), False, 846_000_000, None, None)
    assert all(link.page is None for link in card.links)


def test_voices_lists_the_ones_the_registry_has_in_the_plans_order_and_skips_one_it_lacks():
    assert [c.voice_id for c in sv.voices(make_registry())] == ["voice-mike", "voice-amy"]
    assert [c.voice_id for c in sv.voices(make_registry(mike=None))] == ["voice-amy"]
    assert sv.voices(Registry(())) == ()


# ---------------------------------------------------------------- naming a voice

@pytest.mark.parametrize("typed", ["mike", "Mike", "MIKE", "voice-mike", "Voice-Mike", "  mike  ", "mike\n"])
def test_a_voice_can_be_named_loosely(typed):
    assert sv.find_voice(make_registry(), typed) == "voice-mike"


@pytest.mark.parametrize("typed", ["amy", "AMY", "voice-amy", " voice-amy"])
def test_the_other_voice_is_found_too(typed):
    assert sv.find_voice(make_registry(), typed) == "voice-amy"


@pytest.mark.parametrize("typed", ["", " ", "bob", "voice-", "voice", "mik", "mikey", "voice-mike2", "amy mike", "voice mike", None])
def test_a_name_that_is_not_a_voice_finds_nothing(typed):
    assert sv.find_voice(make_registry(), typed) is None


def test_a_voice_the_registry_lacks_is_not_found_by_its_name():
    assert sv.find_voice(make_registry(amy=None), "amy") is None and sv.find_voice(make_registry(amy=None), "mike") == "voice-mike"
    assert sv.find_voice(Registry(()), "mike") is None


# ---------------------------------------------------------------- choosing

def test_choosing_names_a_known_voice_and_changes_nothing_else(rig):
    chosen = sv.choose(rig.project, rig.registry, "voice-amy")
    assert chosen.starting_voice == "voice-amy" and replace(chosen, starting_voice=None) == rig.project
    assert chosen.acknowledgments == () and not (Path(rig.home.root)).exists()


def test_a_voice_the_tool_does_not_know_is_refused_by_every_door(rig):
    stranger = Registry(rig.registry.items + (replace(make_voice("voice-bob", VOICE_A), id="voice-bob"),))
    for call, args in ((sv.choose, (rig.project, stranger, "voice-bob")), (sv.acknowledged, (rig.project, stranger, "voice-bob")),
                       (sv.acknowledge, (rig.project, stranger, "voice-bob")), (sv.agree_to_download, (stranger, "voice-bob", rig.home)),
                       (sv.kept_path, (rig.home, stranger, "voice-bob")), (sv.next_step, (rig.project, stranger, "voice-bob", rig.home)),
                       (sv.card, (stranger, "voice-bob"))):
        assert refusal(call, *args) == "unknown_voice", call.__name__
    assert refusal(sv.fetch_voice, rig.project, stranger, "voice-bob", rig.home, on_wait=None, on_back=None, sleep=None, clock=None) == "unknown_voice"


def test_a_registry_entry_with_a_known_name_that_is_not_a_voice_is_not_one(rig):
    wrong_kind = Registry((replace(make_voice("voice-mike", VOICE_A), kind="model"),))
    assert refusal(sv.choose, rig.project, wrong_kind, "voice-mike") == "unknown_voice"
    assert refusal(sv.acknowledge, rig.project, wrong_kind, "voice-mike") == "unknown_voice"


def test_a_voice_missing_from_the_registry_is_unknown(rig):
    assert refusal(sv.choose, rig.project, make_registry(amy=None), "voice-amy") == "unknown_voice"


# ---------------------------------------------------------------- the acknowledgment

def test_acknowledging_records_the_voice_the_date_and_the_registrys_own_revision(rig):
    rig.acknowledge()
    assert rig.project.acknowledgments == (Acknowledgment("voice-mike", STAMP, rig.item().revision),)
    assert sv.acknowledged(rig.project, rig.registry, "voice-mike")


def test_a_voice_is_not_acknowledged_until_it_is_and_the_other_voice_is_not_covered_by_it(rig):
    assert not sv.acknowledged(rig.project, rig.registry, "voice-mike")
    rig.acknowledge("voice-mike")
    assert not sv.acknowledged(rig.project, rig.registry, "voice-amy")


def test_a_second_acknowledgment_of_the_same_file_adds_nothing(rig):
    rig.acknowledge()
    again = sv.acknowledge(rig.project, rig.registry, "voice-mike", datetime(2027, 1, 1, tzinfo=timezone.utc))
    assert again == rig.project and len(again.acknowledgments) == 1 and again.acknowledgments[0].at == STAMP


def test_an_acknowledgment_does_not_cover_a_file_the_registry_now_names_at_another_revision(rig):
    rig.acknowledge()
    repinned = make_registry(revision="fedc4321")
    assert not sv.acknowledged(rig.project, repinned, "voice-mike")
    again = sv.acknowledge(rig.project, repinned, "voice-mike", datetime(2026, 12, 1, 8, 0, tzinfo=timezone.utc))
    assert [a.revision for a in again.acknowledgments] == ["0123abcd", "fedc4321"] and sv.acknowledged(again, repinned, "voice-mike")
    assert sv.acknowledged(again, rig.registry, "voice-mike"), "the earlier one is kept, not replaced"


def test_a_voice_that_cannot_be_fetched_yet_cannot_be_acknowledged_or_agreed_to_and_is_not_acknowledged(rig):
    unpinned = Registry((Item("voice-mike", "voice", "fetch.why.voice_mike", "voice-mike-card", approx_size_bytes=846_000_000),))
    assert refusal(sv.acknowledge, rig.project, unpinned, "voice-mike") == "not_pinned"
    assert refusal(sv.agree_to_download, unpinned, "voice-mike", rig.home) == "not_pinned"
    assert refusal(sv.next_step, rig.project, unpinned, "voice-mike", rig.home) == "not_pinned"
    assert refusal(sv.fetch_voice, rig.project, unpinned, "voice-mike", rig.home, on_wait=None, on_back=None, sleep=None, clock=None) == "not_pinned"
    assert not sv.acknowledged(rig.project, unpinned, "voice-mike")
    assert not Path(rig.home.root).exists(), "refusing writes nothing"


def test_a_voice_that_cannot_be_fetched_yet_is_never_read_as_acknowledged_even_by_an_acknowledgment_with_no_revision(rig):
    unpinned = Registry((Item("voice-mike", "voice", "fetch.why.voice_mike", "voice-mike-card", approx_size_bytes=846_000_000),))
    hand_made = replace(rig.project, acknowledgments=(Acknowledgment("voice-mike", STAMP, None),))
    assert not sv.acknowledged(hand_made, unpinned, "voice-mike")


# ---------------------------------------------------------------- the agreement to download

def test_agreeing_saves_a_record_that_names_this_exact_file_and_only_its_owner_can_read_it(rig):
    record = rig.agree()
    saved = load_consent(Path(rig.home.consent_file))
    assert saved == record and record.covers(rig.item()) and not record.covers(rig.item("voice-amy"))
    assert os.stat(rig.home.consent_file).st_mode & 0o777 == 0o600


def test_agreeing_keeps_every_earlier_yes(rig):
    earlier = make_consent([rig.item("voice-amy")], extra_ids=["pip:training"], now=datetime(2026, 10, 1, tzinfo=timezone.utc))
    save_consent(Path(rig.home.consent_file), earlier)
    record = rig.agree()
    assert record.covers(rig.item("voice-amy")) and record.covers_id("pip:training") and record.covers(rig.item("voice-mike"))
    assert record.given_at == "2026-10-11T12:30:00Z"


def test_a_yes_does_not_cover_a_different_file_under_the_same_name(rig):
    record = rig.agree()
    changed = replace(rig.item(), sha256="b" * 64)
    assert record.covers(rig.item()) and not record.covers(changed)


# ---------------------------------------------------------------- fetching needs both yeses

def test_nothing_is_fetched_without_the_acknowledgment_even_when_the_download_was_agreed_to(rig):
    rig.agree()
    assert refusal(rig.fetch) == "not_acknowledged"
    assert rig.opener.calls == [] and not Path(rig.home.voices).exists()


def test_nothing_is_fetched_without_the_agreement_even_when_the_voice_was_acknowledged(rig):
    rig.acknowledge()
    assert refusal(rig.fetch) == "not_agreed"
    assert rig.opener.calls == [] and not Path(rig.home.voices).exists()


def test_the_acknowledgment_is_asked_for_first_when_neither_has_been_given(rig):
    assert refusal(rig.fetch) == "not_acknowledged"


def test_an_acknowledgment_of_the_other_voice_does_not_let_this_one_be_fetched(rig):
    rig.acknowledge("voice-amy")
    rig.agree("voice-mike")
    assert refusal(rig.fetch, "voice-mike") == "not_acknowledged" and rig.opener.calls == []


def test_an_agreement_for_the_other_voice_does_not_let_this_one_be_fetched(rig):
    rig.acknowledge("voice-mike")
    rig.agree("voice-amy")
    assert refusal(rig.fetch, "voice-mike") == "not_agreed" and rig.opener.calls == []


def test_both_yeses_fetch_the_file_into_the_voices_folder_checked_and_readable_only_by_its_owner(rig):
    rig.acknowledge()
    rig.agree()
    path = rig.fetch()
    assert path == rig.folder() / "voice-mike.ckpt" == Path(rig.home.root) / "tool" / "downloads" / "voices" / "voice-mike" / "voice-mike.ckpt"
    assert path.read_bytes() == VOICE_A and os.stat(path).st_mode & 0o777 == 0o600
    assert [url for url, _ in rig.opener.calls] == [rig.item().url], "the one address the registry names, and no page"
    assert rig.progress[-1] == (len(VOICE_A), len(VOICE_A)) and not list(rig.folder().glob("*.part"))
    assert sv.kept_path(rig.home, rig.registry, "voice-mike") == path


def test_the_licence_pages_are_shown_and_never_opened(rig):
    rig.acknowledge()
    rig.agree()
    rig.fetch()
    requested = " ".join(url for url, _ in rig.opener.calls)
    assert all(address not in requested for _, address in rig.item().pages) and len(rig.opener.calls) == 1


def test_a_kept_file_needs_no_network_and_no_agreement_but_still_the_projects_own_acknowledgment(rig):
    rig.acknowledge()
    rig.agree()
    path = rig.fetch()
    os.unlink(rig.home.consent_file)
    rig.opener.calls.clear()
    assert rig.fetch() == path and rig.opener.calls == [], "kept: no network, no saved agreement needed"
    other_project = make_project(id="ben", name="Ben")
    assert refusal(rig.fetch, project=other_project) == "not_acknowledged", "another project has not acknowledged it"
    assert rig.opener.calls == []


def test_a_damaged_kept_file_is_not_trusted_and_is_fetched_again(rig):
    rig.acknowledge()
    rig.agree()
    path = rig.fetch()
    path.write_bytes(VOICE_A[:-1] + b"X")
    assert sv.kept_path(rig.home, rig.registry, "voice-mike") is None and sv.next_step(rig.project, rig.registry, "voice-mike", rig.home) == "download"
    rig.opener.calls.clear()
    assert rig.fetch().read_bytes() == VOICE_A and len(rig.opener.calls) == 1


def test_a_download_that_is_not_the_agreed_file_is_refused_and_nothing_wrong_is_kept(tmp_path):
    wrong = Rig(tmp_path, payload=b"W" * len(VOICE_A))
    wrong.acknowledge()
    wrong.agree()
    with pytest.raises(fetch.FetchError) as caught:
        wrong.fetch()
    assert caught.value.code == "checksum" and sv.kept_path(wrong.home, wrong.registry, "voice-mike") is None
    assert not (wrong.folder() / "voice-mike.ckpt").exists() and not list(wrong.folder().glob("*.part"))


def test_a_dropped_connection_is_waited_out_by_the_download_and_reported(tmp_path):
    rig = Rig(tmp_path, raise_first=urllib.error.URLError("network unreachable"))
    rig.acknowledge()
    rig.agree()
    assert rig.fetch().read_bytes() == VOICE_A
    assert len(rig.waits) == 1 and rig.backs == [1] and rig.time.slept == [1] * cn.PAUSES_S[0], "waited the first pause, one second at a time, then carried on"
    assert len(rig.opener.calls) == 2


def test_the_patience_the_caller_gives_is_the_patience_the_download_keeps(tmp_path):
    class Down:
        calls = 0

        def __call__(self, url, headers):
            self.calls += 1
            raise urllib.error.URLError("network unreachable")

    rig = Rig(tmp_path)
    rig.opener = Down()
    rig.acknowledge()
    rig.agree()
    with pytest.raises(fetch.FetchError) as caught:
        rig.fetch(patience=cn.Patience(total_s=12, pauses_s=(5,), progress_s=60))
    assert caught.value.code == "connection_lost" and rig.time.now < 60 < cn.PATIENCE_S, "gave up on its own schedule, not the default half hour"
    assert sv.kept_path(rig.home, rig.registry, "voice-mike") is None


def test_stop_ends_the_download_and_keeps_what_arrived_so_that_it_can_carry_on(rig):
    rig.acknowledge()
    rig.agree()
    with pytest.raises(fetch.FetchError) as caught:
        rig.fetch(cancelled=lambda: True)
    assert caught.value.code == "cancelled" and sv.kept_path(rig.home, rig.registry, "voice-mike") is None


# ---------------------------------------------------------------- what is left to do

def test_the_steps_go_acknowledge_then_agree_then_download_then_ready_in_that_order(rig):
    step = lambda: sv.next_step(rig.project, rig.registry, "voice-mike", rig.home)
    assert step() == "acknowledge"
    rig.agree()
    assert step() == "acknowledge", "agreeing first does not skip the acknowledgment"
    os.unlink(rig.home.consent_file)
    rig.acknowledge()
    assert step() == "agree"
    rig.agree()
    assert step() == "download"
    rig.fetch()
    assert step() == "ready" and set(sv.STEPS) == {"acknowledge", "agree", "download", "ready"}


def test_a_voice_already_on_the_disk_is_ready_for_a_project_once_that_project_has_acknowledged_it(rig):
    rig.acknowledge()
    rig.agree()
    rig.fetch()
    os.unlink(rig.home.consent_file)
    other = make_project(id="ben", name="Ben")
    assert sv.next_step(other, rig.registry, "voice-mike", rig.home) == "acknowledge"
    other = sv.acknowledge(other, rig.registry, "voice-mike", NOW)
    assert sv.next_step(other, rig.registry, "voice-mike", rig.home) == "ready"


def test_a_changed_pin_means_the_kept_file_is_not_the_one_named_and_the_steps_start_again_from_the_acknowledgment(rig):
    rig.acknowledge()
    rig.agree()
    rig.fetch()
    repinned = make_registry(mike=VOICE_B, revision="fedc4321")
    assert sv.next_step(rig.project, repinned, "voice-mike", rig.home) == "acknowledge"
    acknowledged = sv.acknowledge(rig.project, repinned, "voice-mike", NOW)
    assert sv.next_step(acknowledged, repinned, "voice-mike", rig.home) == "agree"


# ---------------------------------------------------------------- places and the network door

def test_kept_voices_live_under_the_tools_downloads_one_folder_each():
    home = DataHome("/home/anna")
    assert home.voices == "/home/anna/ack-voice-studio/tool/downloads/voices"
    item = make_voice("voice-mike", VOICE_A)
    assert sv.voice_folder(home, item) == Path("/home/anna/ack-voice-studio/tool/downloads/voices/voice-mike")


def test_this_module_has_no_way_to_reach_the_network_of_its_own():
    source = (Path(sv.__file__)).read_text()
    for needle in ("urllib.request", "import socket", "import http", "subprocess", "urlopen", "http://", "https://"):
        assert needle not in source, needle
