# SPDX-License-Identifier: GPL-3.0-or-later
"""The setup plan as data (plan task VS-2.2): one list, one agreement, one disk verdict, and nothing fetchable that is not pinned."""
import copy
import json
from datetime import datetime, timezone

import pytest

from voice_studio.core import setupplan as sp
from voice_studio.core.diskbudget import DEFAULT_TABLE, GIB, DriveMap, Level, judge_start
from voice_studio.core.envspec import load_environments, parse_environments
from voice_studio.core.registry import Item, Registry, load_registry

H = "a" * 64
NOW = datetime(2026, 10, 10, 12, 0, tzinfo=timezone.utc)
HOME = DriveMap()


def item(item_id, kind, pinned, size=1000):
    base = dict(id=item_id, kind=kind, why_key="fetch.why.x", license_id="lic-" + item_id, approx_size_bytes=size)
    if pinned:
        base.update(url="https://huggingface.co/o/r/resolve/abc123/%s.bin" % item_id, filename="%s.bin" % item_id, revision="abc123", size_bytes=size + 5, sha256=H)
    return Item(**base)


def env(env_id, pinned, source=None, size=2000):
    raw = {"id": env_id, "why_key": "env.why.%s" % env_id, "python_min": [3, 10], "approx_size_bytes": size,
           "lock": {"filename": "%s.lock.txt" % env_id, "sha256": H if pinned else None},
           "source": ({"item_id": source, "install": True} if source else None), "prelude": [], "patches": [],
           "probes": [{"id": "ok", "code": "pass"}]}
    return parse_environments(json.dumps({"schema": 1, "environments": [raw]}))[0]


def full(pinned):
    registry = Registry((item("speech-model-small-en", "model", pinned, 480), item("piper1-gpl-source", "source", pinned, 20),
                         item("voice-mike", "voice", pinned, 846), item("voice-amy", "voice", pinned, 846)))
    return registry, (env("training", pinned, "piper1-gpl-source", 8000), env("studio", pinned, None, 1000))


def free(n):
    return {"home": n}


# ---------------------------------------------------------------- the list

def test_the_list_is_in_the_order_things_are_done_and_each_item_knows_what_it_is():
    registry, envs = full(True)
    items = sp.build_items(registry, envs)
    assert [i.id for i in items] == ["env-training", "env-studio", "speech-model-small-en", "piper1-gpl-source", "voice-amy", "voice-mike"]
    assert [i.kind for i in items] == ["packages", "packages", "model", "source", "voice", "voice"]
    assert [i.declinable for i in items] == [False, False, False, False, True, True]
    assert all(i.available for i in items) and all(i.kind in sp.KINDS for i in items)


def test_a_pinned_registry_item_shows_its_site_its_exact_size_and_its_address_for_the_details():
    registry, envs = full(True)
    mike = next(i for i in sp.build_items(registry, envs) if i.id == "voice-mike")
    assert mike.hosts == ("huggingface.co",) and mike.exact and mike.size_bytes == 851 and mike.url.startswith("https://huggingface.co/")
    assert mike.license_id == "lic-voice-mike" and mike.why_key == "fetch.why.x" and mike.agreement_id is None


def test_an_environments_packages_come_from_the_package_site_and_are_only_a_rough_size():
    registry, envs = full(True)
    training = sp.build_items(registry, envs)[0]
    assert training.hosts == sp.PACKAGE_HOSTS and not training.exact and training.size_bytes == 8000 and training.url is None
    assert training.agreement_id == "pip:training" and training.license_id is None and not training.declinable


def test_nothing_unpinned_is_available_and_the_reason_is_kept_for_the_details():
    registry, envs = full(False)
    items = sp.build_items(registry, envs)
    assert not any(i.available for i in items)
    assert next(i for i in items if i.id == "env-training").problems == ("lock_unpinned", "source_unpinned")
    assert next(i for i in items if i.id == "voice-amy").problems == ("unpinned",)
    assert all(i.not_ready_only for i in items) and all(i.hosts == () for i in items if i.kind != "packages")


def test_an_item_with_something_wrong_with_its_entry_is_not_called_merely_not_ready():
    broken = sp.SetupItem("x", "voice", "k", None, 1, False, (), None, ("unpinned", "url_not_https"), True, None)
    assert not broken.not_ready_only and broken.problems and not broken.available
    assert sp.SetupItem("x", "voice", "k", None, 1, False, (), None, (), True, None).not_ready_only is False


@pytest.mark.parametrize("code, kind", [("unpinned", "not_ready"), ("lock_unpinned", "not_ready"), ("source_unpinned", "not_ready"),
                                        ("source_unknown", "broken"), ("url_not_https", "broken"), ("bad_sha256", "broken"), ("missing_size_bytes", "broken"), ("", "broken")])
def test_a_problem_is_either_not_ready_yet_or_broken(code, kind):
    assert sp.problem_kind(code) == kind


def test_an_item_a_registry_does_not_list_is_simply_absent_and_unknown_kinds_are_not_downloaded():
    registry = Registry((item("some-file", "file", True),))
    assert sp.build_items(registry, ()) == ()


# ---------------------------------------------------------------- what can be declined

def test_a_starting_voice_can_be_declined_and_then_is_neither_listed_nor_counted():
    registry, envs = full(True)
    both = sp.plan_setup(registry, envs, free=free(500 * GIB))
    one = sp.plan_setup(registry, envs, free=free(500 * GIB), declined=["voice-amy"])
    assert one.declined == ("voice-amy",) and [i.id for i in one.items if i.kind == "voice"] == ["voice-mike"]
    assert both.total_bytes - one.total_bytes == 851 and sum(one.verdict.need.values()) < sum(both.verdict.need.values())


def test_nothing_but_a_starting_voice_can_be_declined():
    registry, envs = full(True)
    plan = sp.plan_setup(registry, envs, free=free(500 * GIB), declined=["env-training", "speech-model-small-en", "piper1-gpl-source", "nonsense", "voice-mike"])
    assert plan.declined == ("voice-mike",)
    assert {i.id for i in plan.items} == {"env-training", "env-studio", "speech-model-small-en", "piper1-gpl-source", "voice-amy"}


def test_both_voices_can_be_declined_and_the_rest_still_stands():
    registry, envs = full(True)
    plan = sp.plan_setup(registry, envs, free=free(500 * GIB), declined=["voice-mike", "voice-amy"])
    assert plan.declined == ("voice-amy", "voice-mike") and not [i for i in plan.items if i.kind == "voice"] and plan.can_start


# ---------------------------------------------------------------- the disk

def test_the_estimate_counts_every_download_once_the_environments_by_their_own_line_and_two_people():
    registry, envs = full(True)
    plan = sp.plan_setup(registry, envs, free=free(500 * GIB))
    downloads = [(i.id, i.size_bytes) for i in plan.items if i.kind != "packages"]
    assert sp.downloads_for_disk(plan.items) == downloads and not any(d[0].startswith("env-") for d in downloads)
    assert plan.verdict == judge_start(DEFAULT_TABLE, downloads, sp.DEFAULT_HOURS, HOME, free(500 * GIB))
    assert plan.verdict.need == judge_start(DEFAULT_TABLE, downloads, sp.DEFAULT_HOURS, HOME, free(500 * GIB), people=2).need


@pytest.mark.parametrize("have, level, can", [(500 * GIB, Level.ENOUGH, True), (1 * GIB, Level.NOT_ENOUGH, False)])
def test_the_verdict_decides_whether_the_setup_may_start(have, level, can):
    registry, envs = full(True)
    plan = sp.plan_setup(registry, envs, free=free(have))
    assert plan.verdict.level is level and plan.can_start is can and (plan.blockers == () if can else plan.blockers == ("no_room",))
    assert plan.needs_warning is False, "a warning is for a disk that is tight, not one that is plainly enough or plainly not"


def test_a_tight_disk_goes_on_only_after_a_warning():
    registry, envs = full(True)
    probe = sp.plan_setup(registry, envs, free=free(500 * GIB))
    middle = (probe.verdict.need_tight["home"] + probe.verdict.need["home"]) // 2
    plan = sp.plan_setup(registry, envs, free=free(middle))
    assert plan.verdict.level is Level.TIGHT and plan.needs_warning and plan.can_start and plan.blockers == ()


def test_a_drive_that_cannot_be_read_is_not_judged_and_does_not_block():
    registry, envs = full(True)
    plan = sp.plan_setup(registry, envs, free={"home": None})
    assert plan.verdict.unknown_drives == ("home",) and plan.can_start


def test_scratch_on_another_drive_is_judged_on_that_drive():
    registry, envs = full(True)
    drives = DriveMap(scratch="usb")
    plan = sp.plan_setup(registry, envs, free={"home": 500 * GIB, "usb": 1 * GIB}, drives=drives)
    assert plan.verdict.level is Level.NOT_ENOUGH and plan.verdict.short_by["usb"] > 0 and plan.verdict.short_by["home"] == 0


def test_the_planned_hours_change_the_estimate():
    registry, envs = full(True)
    small = sp.plan_setup(registry, envs, free=free(500 * GIB), hours=1.0)
    large = sp.plan_setup(registry, envs, free=free(500 * GIB), hours=10.0)
    assert large.verdict.need["home"] > small.verdict.need["home"] and large.hours == 10.0


def test_the_estimate_is_called_rough_while_the_table_is_unmeasured():
    registry, envs = full(True)
    assert sp.plan_setup(registry, envs, free=free(500 * GIB)).verdict.rough is True


# ---------------------------------------------------------------- when it can start

def test_a_plan_with_anything_unavailable_cannot_start_whatever_the_disk_says():
    registry, envs = full(False)
    plan = sp.plan_setup(registry, envs, free=free(500 * GIB))
    assert not plan.can_start and plan.blockers == ("not_available",) and len(plan.unavailable) == len(plan.items)


def test_both_blockers_are_reported_together():
    registry, envs = full(False)
    plan = sp.plan_setup(registry, envs, free=free(1 * GIB))
    assert plan.blockers == ("not_available", "no_room") and set(plan.blockers) <= set(sp.BLOCKER_CODES)


def test_one_unavailable_item_is_enough_to_stop_it_even_if_the_rest_are_fine():
    registry, envs = full(True)
    registry = Registry(tuple(i if i.id != "voice-amy" else item("voice-amy", "voice", False, 846) for i in registry.items))
    plan = sp.plan_setup(registry, envs, free=free(500 * GIB))
    assert [i.id for i in plan.unavailable] == ["voice-amy"] and not plan.can_start
    declined = sp.plan_setup(registry, envs, free=free(500 * GIB), declined=["voice-amy"])
    assert declined.can_start, "declining the unavailable starting voice leaves a plan that can go"


def test_a_plan_with_an_unavailable_item_is_agreed_when_everything_that_can_be_fetched_is():
    registry, envs = full(True)
    registry = Registry(tuple(i if i.id != "voice-amy" else item("voice-amy", "voice", False, 846) for i in registry.items))
    plan = sp.plan_setup(registry, envs, free=free(500 * GIB))
    assert [i.id for i in plan.unavailable] == ["voice-amy"]
    assert sp.agreed(plan, registry, plan.agreement(registry, NOW)), "the unavailable one cannot be agreed to yet, and does not stop the rest being agreed"


def test_the_total_is_exact_only_when_every_size_is():
    registry, envs = full(True)
    plan = sp.plan_setup(registry, envs, free=free(500 * GIB))
    assert not plan.exact, "the environments' sizes are rough"
    assert plan.total_bytes == 8000 + 1000 + 485 + 25 + 851 + 851
    only_registry = sp.SetupPlan(tuple(i for i in plan.items if i.kind != "packages"), (), plan.verdict, 1.0)
    assert only_registry.exact


# ---------------------------------------------------------------- the agreement

def test_the_agreement_names_each_pinned_entry_exactly_and_each_environments_packages():
    registry, envs = full(True)
    plan = sp.plan_setup(registry, envs, free=free(500 * GIB))
    record = plan.agreement(registry, NOW)
    ids = sorted(e.id for e in record.entries)
    assert ids == ["pip:studio", "pip:training", "piper1-gpl-source", "speech-model-small-en", "voice-amy", "voice-mike"]
    for entry in record.entries:
        if not entry.id.startswith("pip:"):
            pinned = registry.get(entry.id)
            assert (entry.url, entry.size_bytes, entry.sha256) == (pinned.url, pinned.size_bytes, pinned.sha256) and record.covers(pinned)
    assert record.covers_id("pip:training") and not record.covers_id("pip:other") and record.given_at == "2026-10-10T12:00:00Z"


def test_a_declined_voice_is_not_in_the_agreement_and_so_cannot_be_fetched():
    registry, envs = full(True)
    plan = sp.plan_setup(registry, envs, free=free(500 * GIB), declined=["voice-amy"])
    record = plan.agreement(registry, NOW)
    assert not record.covers(registry.get("voice-amy")) and record.covers(registry.get("voice-mike"))


def test_an_item_that_cannot_be_fetched_yet_is_in_no_agreement():
    registry, envs = full(False)
    plan = sp.plan_setup(registry, envs, free=free(500 * GIB))
    assert plan.agreement(registry, NOW).entries == () and plan.agreement_ids() == ()


def test_a_half_ready_plan_agrees_only_to_what_is_ready():
    registry, envs = full(True)
    registry = Registry(tuple(i if i.id != "voice-amy" else item("voice-amy", "voice", False, 846) for i in registry.items))
    plan = sp.plan_setup(registry, envs, free=free(500 * GIB))
    assert "voice-amy" not in {e.id for e in plan.agreement(registry, NOW).entries}


def test_an_environment_whose_lock_is_not_pinned_gets_no_package_agreement():
    registry, envs = full(True)
    envs = (env("training", False, "piper1-gpl-source"), envs[1])
    plan = sp.plan_setup(registry, envs, free=free(500 * GIB))
    assert plan.agreement_ids() == ("pip:studio",)


# ---------------------------------------------------------------- the shipped data

def test_the_shipped_plan_today_lists_everything_and_says_what_can_and_cannot_be_fetched_yet():
    plan = sp.plan_setup(load_registry(), load_environments(), free=free(500 * GIB))
    assert [i.id for i in plan.items] == ["env-training", "env-studio", "speech-model-small-en", "voice-amy", "voice-mike"]
    by_id = {i.id: i for i in plan.items}
    assert by_id["env-training"].problems == () and by_id["env-training"].available, "the training environment is pinned: lock, native part and no source archive"
    assert by_id["env-studio"].problems == () and by_id["env-studio"].available, "and so is the studio environment"
    assert all(i.not_ready_only for i in plan.items if i.kind != "packages"), "the model and the voices still wait for their exact files"
    assert sorted(e.id for e in plan.agreement(load_registry(), NOW).entries) == ["pip:studio", "pip:training"], "the only things that could be agreed to today"
    assert plan.blockers == ("not_available",), "so the whole plan still cannot run"
    assert plan.verdict.need["home"] > 20 * GIB, "both voices, the environments and two people"


def test_every_shipped_item_has_words_for_why():
    from voice_studio.core.text import load_catalog
    cat = load_catalog("en")
    for i in sp.build_items(load_registry(), load_environments()):
        assert cat.t(i.why_key) != i.why_key, i.id
