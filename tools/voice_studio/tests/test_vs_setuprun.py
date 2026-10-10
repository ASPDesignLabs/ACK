# SPDX-License-Identifier: GPL-3.0-or-later
"""Carrying out the setup plan (plan task VS-2.2): refuses unless everything is agreed and fits, stops at the first failure, and carries on from the disk next time."""
import os
import stat
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import List

import pytest

from vs_env_helpers import GIB, LOCK, BuildSystem, Doors, make_archive, make_spec, pinned_item, sha_of
from voice_studio.core import envbuild as eb
from voice_studio.core import fetch
from voice_studio.core import setupplan as sp
from voice_studio.core import setuprun as sr
from voice_studio.core.consent import ConsentEntry, ConsentRecord, load_consent, make_consent, save_consent
from voice_studio.core.paths import DataHome
from voice_studio.core.registry import Item, Registry

NOW = datetime(2026, 10, 10, 12, 0, tzinfo=timezone.utc)


def file_item(item_id, kind, path, license_id="lic"):
    return Item(item_id, kind, "fetch.why.x", license_id, approx_size_bytes=10, url="https://huggingface.co/o/r/resolve/abc123/%s" % path.name,
                filename=path.name, revision="abc123", size_bytes=path.stat().st_size, sha256=sha_of(path))


@dataclass
class Run:
    root: Path
    system: BuildSystem
    doors: Doors
    registry: Registry
    envs: tuple
    ctx: eb.Context
    plan: sp.SetupPlan
    events: List[sr.SetupEvent]
    low_events: List[eb.Event]

    def go(self, **kw):
        return sr.run(self.plan, self.ctx, self.envs, on_event=self.events.append, **kw)

    def kinds(self, kind):
        return [e.item for e in self.events if e.kind == kind]

    def agree_all(self):
        self.ctx.consent = self.plan.agreement(self.registry, NOW)


def make_run(tmp_path, *, free=500 * GIB, declined=(), agree=True, unpinned_voice=False) -> Run:
    root = Path(tmp_path)
    root.mkdir(parents=True, exist_ok=True)
    archive = make_archive(root / "src.tar.gz")
    source = pinned_item(archive)
    model_file = root / "small-en.bin"
    model_file.write_bytes(b"MODEL" * 200)
    voice_file = root / "mike.ckpt"
    voice_file.write_bytes(b"VOICE" * 50)
    voice = file_item("voice-mike", "voice", voice_file, "voice-mike-card")
    amy = Item("voice-amy", "voice", "fetch.why.x", "voice-amy-card", approx_size_bytes=846)               # not pinned
    registry = Registry((file_item("speech-model-small-en", "model", model_file, "whisper-mit"), source, voice, amy if unpinned_voice else file_item("voice-amy", "voice", voice_file)))
    envs = (make_spec(LOCK, id="training"), make_spec(LOCK, id="studio", source=None, patches=[], prelude=[]))
    system = BuildSystem()
    doors = Doors(system, archive)
    doors.files = {"speech-model-small-en": model_file}
    events: List[sr.SetupEvent] = []
    low: List[eb.Event] = []
    ctx = eb.Context(system=system, home=DataHome(str(root / "home")), registry=registry, consent=None, on_event=low.append, fetcher=doors.fetcher,
                     networked=doors.networked, read_lock=lambda s: LOCK)
    plan = sp.plan_setup(registry, envs, free={"home": free}, declined=declined)
    run = Run(root, system, doors, registry, envs, ctx, plan, events, low)
    if agree:
        run.agree_all()
    return run


@pytest.fixture
def run(tmp_path):
    return make_run(tmp_path)


def statuses(outcome):
    return [(r.id, r.status) for r in outcome.results]


def item_events(run, kind):
    """The events about whole items (no builder step named), of one kind."""
    return [e.item for e in run.events if e.kind == kind and e.step == ""]


ORDER = ["env-training", "env-studio", "speech-model-small-en", "demo-source", "voice-amy", "voice-mike"]


# ---------------------------------------------------------------- a whole run

def test_a_whole_run_builds_both_environments_fetches_the_model_and_leaves_the_voices_for_later(run):
    outcome = run.go()
    assert outcome.ok and outcome.refused == () and outcome.failure is None
    assert statuses(outcome) == [("env-training", "done"), ("env-studio", "done"), ("speech-model-small-en", "done"), ("demo-source", "done"),
                                 ("voice-amy", "later"), ("voice-mike", "later")]


def test_the_items_are_done_in_the_plans_order_and_each_gets_a_start_and_an_end(run):
    outcome = run.go()
    assert [r.id for r in outcome.results] == ORDER == [i.id for i in run.plan.items] and item_events(run, "start") == ORDER
    ends = [(e.kind, e.item) for e in run.events if e.kind in sr.STATUSES and e.step == ""]
    assert ends == [(r.status, r.id) for r in outcome.results]


def test_the_model_goes_into_the_models_folder_and_the_voices_are_never_fetched_here(run):
    run.go()
    assert (Path(run.ctx.home.downloads) / "models" / "small-en.bin").read_bytes() == b"MODEL" * 200 and sr.MODELS_FOLDER == "models"
    assert "voice-mike" not in run.doors.fetches and "voice-amy" not in run.doors.fetches and run.doors.fetches.count("speech-model-small-en") == 1
    assert not (Path(run.ctx.home.downloads) / "models" / "mike.ckpt").exists() and not (Path(run.ctx.home.downloads) / "mike.ckpt").exists()


def test_a_second_run_changes_nothing_and_asks_the_network_for_nothing(run):
    run.go()
    run.doors.fetches.clear()
    run.doors.pip_runs.clear()
    again = run.go()
    assert again.ok and statuses(again) == [("env-training", "kept"), ("env-studio", "kept"), ("speech-model-small-en", "kept"), ("demo-source", "kept"),
                                           ("voice-amy", "later"), ("voice-mike", "later")]
    assert run.doors.fetches == [] and run.doors.pip_runs == []


def test_the_download_reports_its_progress_and_the_builders_lines_and_steps_come_through(run):
    run.go()
    progress = [e for e in run.events if e.kind == "progress"]
    assert progress and progress[-1].item == "speech-model-small-en" and progress[-1].done == progress[-1].total > 0
    steps = {(e.item, e.step) for e in run.events if e.step}
    assert ("env-training", "pip_lock") in steps and ("env-studio", "venv") in steps and ("env-studio", "source_unpack") not in steps
    assert any(e.kind == "line" and e.text == "Collecting x" for e in run.events)
    assert run.low_events, "the context's own listener still hears the builder"


def test_a_declined_voice_is_not_in_the_run(tmp_path):
    run = make_run(tmp_path, declined=["voice-amy"])
    outcome = run.go()
    assert outcome.ok and [r.id for r in outcome.results] == ["env-training", "env-studio", "speech-model-small-en", "demo-source", "voice-mike"]


# ---------------------------------------------------------------- when it will not start

def test_it_does_not_start_while_something_cannot_be_fetched_yet(tmp_path):
    run = make_run(tmp_path, unpinned_voice=True)
    run.agree_all()
    outcome = run.go()
    assert not outcome.ok and outcome.refused == ("not_available",) and outcome.results == () and run.doors.fetches == [] and run.doors.pip_runs == []
    assert run.events == [] and not Path(run.ctx.home.environments).exists()


def test_it_does_not_start_when_there_is_no_room(tmp_path):
    run = make_run(tmp_path, free=1 * GIB)
    outcome = run.go()
    assert outcome.refused == ("no_room",) and outcome.results == () and run.doors.fetches == []


def test_a_tight_disk_needs_a_yes_and_with_it_the_run_goes(tmp_path):
    probe = make_run(tmp_path / "probe")
    middle = (probe.plan.verdict.need_tight["home"] + probe.plan.verdict.need["home"]) // 2
    run = make_run(tmp_path / "tight", free=middle)
    assert run.plan.needs_warning
    refused = run.go()
    assert refused.refused == ("tight",) and refused.results == () and run.doors.pip_runs == []
    assert run.go(accept_tight=True).ok


def test_without_the_agreement_nothing_starts(tmp_path):
    run = make_run(tmp_path, agree=False)
    outcome = run.go()
    assert outcome.refused == ("no_agreement",) and run.doors.fetches == [] and run.doors.pip_runs == [] and run.events == []


def test_an_agreement_to_an_older_list_does_not_cover_a_changed_file(tmp_path):
    run = make_run(tmp_path)
    model = run.registry.get("speech-model-small-en")
    old = make_consent([model], extra_ids=["pip:training", "pip:studio"], now=NOW)
    changed = Item(**{**model.__dict__, "sha256": "f" * 64})
    run.ctx.registry = Registry(tuple(changed if i.id == model.id else i for i in run.registry.items))
    run.plan = sp.plan_setup(run.ctx.registry, run.envs, free={"home": 500 * GIB})
    run.ctx.consent = old
    assert run.go().refused == ("no_agreement",)


def test_the_first_reason_wins_and_the_reasons_are_all_listed_codes(tmp_path):
    run = make_run(tmp_path, free=1 * GIB, agree=False)
    assert run.go().refused == ("no_room",)
    assert set(sr.REFUSAL_CODES) >= {"not_available", "no_room", "tight", "no_agreement"}


# ---------------------------------------------------------------- failures

def test_a_failed_environment_stops_the_run_and_says_why(run):
    run.doors.pip_fail["lock"] = 1
    outcome = run.go()
    assert not outcome.ok and statuses(outcome) == [("env-training", "failed")]
    failure = outcome.failure
    assert (failure.namespace, failure.code, failure.detail) == ("env", "pip_failed", "exit 1") and "ERROR: No matching distribution" in failure.tail
    assert run.doors.fetches.count("speech-model-small-en") == 0, "nothing after the failed item ran"
    assert item_events(run, "start") == ["env-training"] and item_events(run, "failed") == ["env-training"]


def test_the_next_run_carries_on_from_the_failed_item_and_keeps_what_was_done(run):
    run.doors.pip_fail["lock"] = 1
    run.go()
    run.doors.pip_fail.clear()
    outcome = run.go()
    assert outcome.ok and statuses(outcome)[0] == ("env-training", "done")
    run.doors.fetches.clear()
    assert run.go().ok and run.doors.fetches == []


def test_a_failed_download_is_a_fetch_failure_with_its_code(run):
    run.doors.fetch_error = "http"
    outcome = run.go()
    assert statuses(outcome)[-1] == ("env-training", "failed"), "the first fetch is the trainer's source, inside its environment"
    run.doors.fetch_error = None
    original = run.doors.fetcher

    def model_fails(item, dest, consent, **kwargs):
        if item.id == "speech-model-small-en":
            raise fetch.FetchError("checksum", "x")
        return original(item, dest, consent, **kwargs)

    run.ctx.fetcher = model_fails
    outcome = run.go()
    failure = outcome.failure
    assert (failure.id, failure.namespace, failure.code, failure.detail) == ("speech-model-small-en", "fetch", "checksum", "x") and outcome.ok is False


def test_cancelling_during_a_download_stops_and_says_stopped(run):
    original = run.doors.fetcher

    def cancelling(item, dest, consent, **kwargs):
        if item.id == "speech-model-small-en":
            raise fetch.FetchError("cancelled")
        return original(item, dest, consent, **kwargs)

    run.ctx.fetcher = cancelling
    outcome = run.go()
    assert not outcome.ok and outcome.results[-1].status == "cancelled" and outcome.results[-1].id == "speech-model-small-en"
    assert outcome.failure is outcome.results[-1] and len(outcome.results) == 3


def test_cancelling_between_items_stops_before_the_next_one(run):
    calls = {"n": 0}

    def cancelled():
        calls["n"] += 1
        return calls["n"] > 1                               # the first item starts, the second is not started

    outcome = run.go(cancelled=cancelled)
    assert statuses(outcome) == [("env-training", "done"), ("env-studio", "cancelled")] and not outcome.ok
    assert run.doors.fetches == ["demo-source"], "only the first environment's own source was fetched"


def test_the_cancel_check_is_handed_to_the_download(run):
    seen = {}
    original = run.doors.fetcher

    def watching(item, dest, consent, progress=None, cancelled=None, **kwargs):
        if item.id == "speech-model-small-en":
            seen["cancelled"] = cancelled
        return original(item, dest, consent, progress=progress, cancelled=cancelled, **kwargs)

    run.ctx.fetcher = watching
    flag = lambda: False
    run.go(cancelled=flag)
    assert seen["cancelled"] is flag


def test_the_source_reports_failure_if_no_environment_in_the_plan_uses_it(tmp_path):
    run = make_run(tmp_path)
    run.envs = (run.envs[1],)                                # only the studio environment, which uses no source
    run.plan = sp.plan_setup(run.registry, run.envs, free={"home": 500 * GIB})
    run.agree_all()
    outcome = run.go()
    assert outcome.failure.id == "demo-source" and (outcome.failure.namespace, outcome.failure.code) == ("env", "not_pinned")


def test_an_environment_built_earlier_but_with_the_source_missing_reports_the_source_as_done_again(run):
    run.go()
    import shutil
    shutil.rmtree(eb.EnvPaths(eb.environment_dir(run.envs[0], run.ctx)).source)
    again = run.go()
    assert again.ok and dict(statuses(again))["demo-source"] == "done" and dict(statuses(again))["env-training"] == "done"


# ---------------------------------------------------------------- the person's yes

def test_the_yes_is_saved_owner_only_and_covers_exactly_the_plan(tmp_path):
    run = make_run(tmp_path, agree=False)
    record = sr.agree(run.plan, run.registry, run.ctx.home, NOW)
    path = Path(run.ctx.home.consent_file)
    assert stat.S_IMODE(path.stat().st_mode) == 0o600 and stat.S_IMODE(path.parent.stat().st_mode) & 0o077 == 0
    assert load_consent(path) == record and sp.agreed(run.plan, run.registry, record)
    assert not record.covers_id("pip:other")


def test_a_saved_yes_is_enough_to_run_and_a_new_yes_keeps_the_old_one(tmp_path):
    run = make_run(tmp_path, agree=False)
    path = Path(run.ctx.home.consent_file)
    save_consent(path, ConsentRecord((ConsentEntry("apt:git"),), "2026-01-01T00:00:00Z"))
    record = sr.agree(run.plan, run.registry, run.ctx.home, NOW)
    assert record.covers_id("apt:git") and record.covers_id("pip:training") and record.given_at == "2026-10-10T12:00:00Z"
    run.ctx.consent = load_consent(path)
    assert run.go().ok


def test_a_damaged_saved_yes_counts_as_no_yes_and_is_replaced(tmp_path):
    run = make_run(tmp_path, agree=False)
    path = Path(run.ctx.home.consent_file)
    path.parent.mkdir(parents=True)
    path.write_text("not json")
    record = sr.agree(run.plan, run.registry, run.ctx.home, NOW)
    assert load_consent(path) == record and record.covers_id("pip:studio")


def test_agreeing_when_nothing_can_be_fetched_yet_agrees_to_nothing(tmp_path):
    run = make_run(tmp_path, unpinned_voice=True, agree=False)
    record = sr.agree(run.plan, run.registry, run.ctx.home, NOW)
    assert "voice-amy" not in {e.id for e in record.entries}


def test_agreed_is_false_without_a_record_and_for_a_record_missing_one_item(tmp_path):
    run = make_run(tmp_path, agree=False)
    assert not sp.agreed(run.plan, run.registry, None)
    full = run.plan.agreement(run.registry, NOW)
    for gone in ("pip:training", "speech-model-small-en", "demo-source", "voice-mike"):
        part = ConsentRecord(tuple(e for e in full.entries if e.id != gone), full.given_at)
        assert not sp.agreed(run.plan, run.registry, part), gone
    assert sp.agreed(run.plan, run.registry, full)


def test_a_plan_whose_only_unavailable_item_is_declined_is_agreed_without_it(tmp_path):
    run = make_run(tmp_path, unpinned_voice=True, declined=["voice-amy"], agree=False)
    assert sp.agreed(run.plan, run.registry, run.plan.agreement(run.registry, NOW))
