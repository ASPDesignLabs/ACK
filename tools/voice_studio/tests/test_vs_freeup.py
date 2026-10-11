# SPDX-License-Identifier: GPL-3.0-or-later
"""Free up space (plan task VS-4.7): what is offered, what never is, and that only what was shown is removed.

Every test writes the files a round leaves (the record, the trainer's folders, a round's working folder) and reads the answer back from the disk.
"""
import os
from datetime import timedelta

import pytest

from voice_studio.core import freeup, rounds as rd
from vs_rounds_helpers import DATASET, NOW, PROJECT, make_world, slurp, write_checkpoint


@pytest.fixture()
def world(tmp_path):
    return make_world(tmp_path)


def spit(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb" if isinstance(data, bytes) else "w") as handle:
        handle.write(data)


def make_cache(world, number, dataset=DATASET, size=1000):
    folder = rd.cache_dir_for(world.scratch, dataset, number)
    spit(folder + "/train/a.pt", b"c" * size)
    spit(folder + "/train/b.pt", b"c" * size)
    return folder


def three_rounds(world):
    for version in range(3):
        world.run_round(version=version)
    return rd.load(world.paths)


def current(world):
    return freeup.plan(world.paths, world.scratch, rd.load(world.paths))


def code_of(fn, *a, **kw):
    with pytest.raises(freeup.FreeError) as caught:
        fn(*a, **kw)
    return caught.value.code


def exists(paths):
    return [os.path.exists(p) for p in paths]


# ---------------------------------------------------------------- what is offered

def test_nothing_is_offered_when_there_are_no_rounds(world):
    shown = current(world)
    assert shown.offers == () and shown.kept == () and shown.busy == 0 and shown.unclaimed == 0


def test_a_round_that_has_ended_offers_its_spare_files_and_the_chosen_rounds_own_saved_point_is_kept(world):
    three_rounds(world)
    shown = current(world)
    by_round = {o.round: o for o in shown.offers if o.kind == "files"}
    assert sorted(by_round) == [1, 2, 3]
    assert [len(by_round[n].paths) for n in (1, 2, 3)] == [3, 2, 2]                    # round 1 whole; rounds 2 and 3 without their last.ckpt
    assert [by_round[n].relation for n in (1, 2, 3)] == ["other", "before", "chosen"]
    assert [by_round[n].includes_saved_point for n in (1, 2, 3)] == [True, False, False]
    assert sorted((n, f.name) for n, f in shown.kept) == [(2, "last.ckpt"), (3, "last.ckpt")]
    assert all(os.path.basename(p) != "last.ckpt" for p in by_round[2].paths + by_round[3].paths)


def test_the_size_of_an_offer_is_the_sum_of_its_files_and_the_numbers_run_from_one_in_the_order_shown(world):
    three_rounds(world)
    shown = current(world)
    assert [o.number for o in shown.offers] == list(range(1, len(shown.offers) + 1))
    for offer in shown.offers:
        if offer.kind == "files":
            assert offer.bytes == sum(os.lstat(p).st_size for p in offer.paths) and offer.bytes > 0


def test_a_round_that_has_ended_offers_its_working_folder_with_its_size_and_the_running_rounds_is_not_offered(world):
    world.run_round(version=0)
    gone = make_cache(world, 1, size=700)
    plan = world.begin()
    rd.attach_job(world.paths, plan.number, world.job_for(plan, "running").id)
    busy = make_cache(world, 2, size=900)
    folders = [o for o in current(world).offers if o.kind == "folder"]
    assert [(o.round, o.paths, o.bytes) for o in folders] == [(1, (gone,), 1400)]
    assert busy not in [p for o in current(world).offers for p in o.paths]


def test_a_working_folder_of_another_name_or_a_link_is_not_offered(world, tmp_path):
    world.run_round(version=0)
    spit(world.scratch.caches + "/someone-elses-cache/x.pt", b"x")
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "keep.txt").write_text("mine")
    os.makedirs(world.scratch.caches, exist_ok=True)
    os.symlink(str(outside), rd.cache_dir_for(world.scratch, DATASET, 1))
    assert [o for o in current(world).offers if o.kind == "folder"] == []


def test_the_files_of_the_running_round_and_of_an_unknown_folder_are_counted_but_never_offered(world):
    world.run_round(version=0)
    world.trainer_makes(7)                                             # there before the round began, and not made by any round
    plan = world.begin()
    rd.attach_job(world.paths, plan.number, world.job_for(plan, "running").id)
    world.trainer_makes(1)
    shown = current(world)
    assert shown.busy == 3 and shown.unclaimed == 3
    offered = [p for o in shown.offers for p in o.paths]
    assert not any("version_1" in p or "version_7" in p for p in offered)


def test_a_link_in_a_checkpoint_folder_is_never_offered(world, tmp_path):
    world.run_round(version=0)
    precious = tmp_path / "precious.ckpt"
    write_checkpoint(str(precious))
    link = "%s/lightning_logs/version_0/checkpoints/epoch=9-val_mel=0.1.ckpt" % world.paths.run
    os.symlink(str(precious), link)
    assert link not in [p for o in current(world).offers for p in o.paths]


def test_nothing_in_the_project_but_saved_files_and_working_folders_is_ever_offered(world):
    three_rounds(world)
    make_cache(world, 1)
    spit(world.paths.root + "/recordings/a.wav", b"RIFF")
    shown = current(world)
    for offer in shown.offers:
        for path in offer.paths:
            assert path.endswith(".ckpt") or path.startswith(world.scratch.caches + os.sep)
    assert all("lightning_logs/version_" in p or world.scratch.caches in p for o in shown.offers for p in o.paths)


# ---------------------------------------------------------------- removing

def test_removing_an_offer_removes_exactly_its_files_and_nothing_else(world):
    three_rounds(world)
    shown = current(world)
    target = next(o for o in shown.offers if o.kind == "files" and o.round == 2)
    others = [p for o in shown.offers if o is not target for p in o.paths]
    kept = [f.path for _n, f in shown.kept]
    result = freeup.remove(world.paths, world.scratch, shown, [target.number])
    assert result.removed_files == len(target.paths) and result.removed_folders == 0 and result.removed_bytes == target.bytes and result.failed == ()
    assert exists(target.paths) == [False] * len(target.paths)
    assert all(exists(others)) and all(exists(kept))


def test_removing_a_working_folder_removes_the_whole_folder_and_counts_it_once(world):
    world.run_round(version=0)
    folder = make_cache(world, 1, size=500)
    shown = current(world)
    target = next(o for o in shown.offers if o.kind == "folder")
    result = freeup.remove(world.paths, world.scratch, shown, [target.number])
    assert not os.path.exists(folder) and os.path.isdir(world.scratch.caches)
    assert (result.removed_files, result.removed_folders, result.removed_bytes) == (0, 1, 1000) and result.failed == ()


def test_removing_everything_shown_keeps_the_chosen_rounds_saved_point_and_the_one_before_it(world):
    three_rounds(world)
    make_cache(world, 1)
    shown = current(world)
    freeup.remove(world.paths, world.scratch, shown, [o.number for o in shown.offers])
    record = rd.load(world.paths)
    assert rd.checkpoint_status(world.paths, rd.chosen(record)) == "ok"
    assert rd.checkpoint_status(world.paths, rd.find(record, 2)) == "ok"
    assert current(world).offers == ()
    assert not os.path.exists(rd.cache_dir_for(world.scratch, DATASET, 1))


def test_the_version_folders_stay_so_the_trainers_numbers_are_never_reused(world):
    three_rounds(world)
    shown = current(world)
    freeup.remove(world.paths, world.scratch, shown, [o.number for o in shown.offers])
    assert rd.version_dirs(world.paths) == (0, 1, 2)
    assert os.path.isfile("%s/lightning_logs/version_0/hparams.yaml" % world.paths.run)


def test_a_round_whose_saved_point_was_offered_and_removed_cannot_be_chosen_any_more_but_everything_else_works(world):
    three_rounds(world)
    shown = current(world)
    first = next(o for o in shown.offers if o.kind == "files" and o.round == 1)
    assert first.includes_saved_point
    freeup.remove(world.paths, world.scratch, shown, [first.number])
    assert rd.checkpoint_status(world.paths, rd.find(rd.load(world.paths), 1)) in ("none", "missing")
    assert rd.checkpoint_status(world.paths, rd.chosen(rd.load(world.paths))) == "ok"


def test_nothing_chosen_removes_nothing(world):
    three_rounds(world)
    before = current(world)
    assert code_of(freeup.remove, world.paths, world.scratch, before, []) == "nothing_to_remove"
    assert all(exists([p for o in before.offers for p in o.paths]))


def test_a_number_that_was_not_shown_removes_nothing_even_when_others_were_chosen_with_it(world):
    three_rounds(world)
    shown = current(world)
    assert code_of(freeup.remove, world.paths, world.scratch, shown, [1, 99]) == "unknown_choice"
    assert code_of(freeup.remove, world.paths, world.scratch, shown, [0]) == "unknown_choice"
    assert code_of(freeup.remove, world.paths, world.scratch, shown, [-1]) == "unknown_choice"
    assert all(exists([p for o in shown.offers for p in o.paths]))


def test_choosing_the_same_number_twice_removes_it_once(world):
    three_rounds(world)
    shown = current(world)
    target = shown.offers[0]
    result = freeup.remove(world.paths, world.scratch, shown, [target.number, target.number])
    assert result.removed_files == len(target.paths) and result.failed == ()


# ---------------------------------------------------------------- the list must still be the one that was shown

def test_a_file_that_appeared_after_the_list_was_shown_makes_the_removal_refuse_and_remove_nothing(world):
    three_rounds(world)
    shown = current(world)
    write_checkpoint("%s/lightning_logs/version_0/checkpoints/epoch=999-val_mel=0.1.ckpt" % world.paths.run)
    assert code_of(freeup.remove, world.paths, world.scratch, shown, [o.number for o in shown.offers]) == "changed"
    assert all(exists([p for o in shown.offers for p in o.paths]))


def test_a_file_that_grew_after_the_list_was_shown_makes_the_removal_refuse(world):
    three_rounds(world)
    shown = current(world)
    victim = shown.offers[0].paths[0]
    with open(victim, "ab") as handle:
        handle.write(b"more")
    assert code_of(freeup.remove, world.paths, world.scratch, shown, [shown.offers[0].number]) == "changed"
    assert os.path.exists(victim)


def test_a_round_that_started_after_the_list_was_shown_does_not_change_the_list_and_its_files_are_left_alone(world):
    world.run_round(version=0)
    shown = current(world)
    plan = world.begin()
    rd.attach_job(world.paths, plan.number, world.job_for(plan, "running").id)
    busy = world.trainer_makes(1)
    busy_files = sorted(os.listdir(busy))
    result = freeup.remove(world.paths, world.scratch, shown, [o.number for o in shown.offers])
    assert result.removed_files == sum(len(o.paths) for o in shown.offers) and result.failed == ()
    assert sorted(os.listdir(busy)) == busy_files and all(exists([f.path for _n, f in current(world).kept]))
    assert rd.checkpoint_status(world.paths, rd.chosen(rd.load(world.paths))) == "ok"


def test_choosing_a_different_round_after_the_list_was_shown_makes_the_removal_refuse_so_a_saved_point_is_never_taken(world):
    three_rounds(world)
    shown = current(world)
    rd.choose(world.paths, 1)
    assert code_of(freeup.remove, world.paths, world.scratch, shown, [o.number for o in shown.offers]) == "changed"
    assert rd.checkpoint_status(world.paths, rd.find(rd.load(world.paths), 1)) == "ok"


def test_a_second_removal_from_the_same_list_refuses_because_the_list_has_changed(world):
    three_rounds(world)
    shown = current(world)
    freeup.remove(world.paths, world.scratch, shown, [shown.offers[0].number])
    assert code_of(freeup.remove, world.paths, world.scratch, shown, [shown.offers[0].number]) == "changed"


def test_a_file_that_was_renamed_to_another_name_of_the_same_size_after_the_list_was_shown_makes_the_removal_refuse(world):
    three_rounds(world)
    shown = current(world)
    target = shown.offers[0]
    old = target.paths[0]
    os.rename(old, os.path.join(os.path.dirname(old), "epoch=999-val_mel=0.1.ckpt"))
    assert code_of(freeup.remove, world.paths, world.scratch, shown, [target.number]) == "changed"
    assert all(os.path.exists(p) for p in target.paths[1:])


def test_a_file_that_is_swapped_for_a_link_after_the_list_was_shown_is_not_followed(world, tmp_path):
    three_rounds(world)
    shown = current(world)
    target = shown.offers[0]
    victim = target.paths[0]
    precious = tmp_path / "precious.ckpt"
    write_checkpoint(str(precious))
    os.unlink(victim)
    os.symlink(str(precious), victim)
    assert code_of(freeup.remove, world.paths, world.scratch, shown, [target.number]) == "changed"
    assert precious.exists()


# ---------------------------------------------------------------- failures are reported and the rest goes on

def test_a_file_that_cannot_be_removed_is_reported_and_the_others_are_still_removed(world, monkeypatch):
    three_rounds(world)
    shown = current(world)
    target = next(o for o in shown.offers if o.kind == "files" and o.round == 1)
    stuck = target.paths[1]
    real = os.unlink

    def unlink(path, *a, **kw):
        if path == stuck:
            raise PermissionError(13, "Permission denied", path)
        return real(path, *a, **kw)

    monkeypatch.setattr(os, "unlink", unlink)
    result = freeup.remove(world.paths, world.scratch, shown, [target.number])
    assert result.failed == ((stuck, "Permission denied"),) and result.removed_files == len(target.paths) - 1
    assert os.path.exists(stuck) and not any(os.path.exists(p) for p in target.paths if p != stuck)
    assert result.removed_bytes == target.bytes - os.lstat(stuck).st_size


def test_a_working_folder_that_cannot_be_fully_removed_is_not_counted_as_removed(world, monkeypatch):
    world.run_round(version=0)
    folder = make_cache(world, 1)
    shown = current(world)
    target = next(o for o in shown.offers if o.kind == "folder")
    real = os.unlink

    def unlink(path, *a, **kw):
        if os.path.basename(path) == "a.pt":
            raise PermissionError(13, "Permission denied", path)
        return real(path, *a, **kw)

    monkeypatch.setattr(os, "unlink", unlink)
    result = freeup.remove(world.paths, world.scratch, shown, [target.number])
    assert result.removed_folders == 0 and any(reason == "Permission denied" for _p, reason in result.failed)
    assert os.path.isdir(folder) and os.path.exists(folder + "/train/a.pt") and not os.path.exists(folder + "/train/b.pt")
    assert result.removed_bytes == 1000                                                                     # what really went, not the whole folder


# ---------------------------------------------------------------- the removal looks at what it removes, not at what it was told

def test_a_forged_list_cannot_make_it_remove_a_recording(world):
    three_rounds(world)
    recording = world.paths.root + "/recordings/a.wav"
    spit(recording, b"RIFFdata")
    real = current(world)
    forged = freeup.Plan((freeup.Offer(1, "files", 1, "other", False, (recording,), 8),), real.kept, 0, 0)
    assert code_of(freeup.remove, world.paths, world.scratch, forged, [1]) == "changed"
    assert slurp(recording) == b"RIFFdata"


def test_a_list_that_matches_but_names_a_file_outside_the_run_folder_removes_nothing(world, monkeypatch):
    three_rounds(world)
    outside = world.paths.root + "/recordings/a.ckpt"
    spit(outside, b"mine")
    real = freeup.plan

    def lying(paths, scratch, record):
        honest = real(paths, scratch, record)
        offer = honest.offers[0]
        return freeup.Plan((freeup.Offer(offer.number, offer.kind, offer.round, offer.relation, False, (outside,), 4),) + honest.offers[1:], honest.kept, honest.busy, honest.unclaimed)

    shown = lying(world.paths, world.scratch, rd.load(world.paths))
    monkeypatch.setattr(freeup, "plan", lying)
    result = freeup.remove(world.paths, world.scratch, shown, [1])
    assert result.removed_files == 0 and result.failed and slurp(outside) == b"mine"


def test_a_list_that_matches_but_names_a_folder_outside_the_caches_removes_nothing(world, monkeypatch):
    world.run_round(version=0)
    make_cache(world, 1)
    outside = world.paths.root + "/recordings"
    spit(outside + "/a.wav", b"RIFF")
    real = freeup.plan

    def lying(paths, scratch, record):
        honest = real(paths, scratch, record)
        return freeup.Plan(tuple(freeup.Offer(o.number, o.kind, o.round, o.relation, False, (outside,) if o.kind == "folder" else o.paths, 4) for o in honest.offers),
                           honest.kept, honest.busy, honest.unclaimed)

    shown = lying(world.paths, world.scratch, rd.load(world.paths))
    monkeypatch.setattr(freeup, "plan", lying)
    result = freeup.remove(world.paths, world.scratch, shown, [o.number for o in shown.offers if o.kind == "folder"])
    assert result.removed_folders == 0 and result.failed and slurp(outside + "/a.wav") == b"RIFF"


def forged(world, monkeypatch, name_for):
    """A plan whose offers name what `name_for(offer)` says, that the removal itself will also work out (so the fingerprint matches): the removal must look at what it removes, not trust the list."""
    real = freeup.plan

    def lying(paths, scratch, record):
        honest = real(paths, scratch, record)
        return freeup.Plan(tuple(freeup.Offer(o.number, o.kind, o.round, o.relation, False, name_for(o), 4) for o in honest.offers), honest.kept, honest.busy, honest.unclaimed)

    shown = lying(world.paths, world.scratch, rd.load(world.paths))
    monkeypatch.setattr(freeup, "plan", lying)
    return shown


@pytest.mark.parametrize("inside", [False, True])
def test_a_link_to_a_saved_file_is_not_removed_even_if_a_list_names_it(world, monkeypatch, tmp_path, inside):
    three_rounds(world)
    target = current(world).offers[-1].paths[0] if inside else str(tmp_path / "precious.ckpt")        # a file in the run folder itself, or one outside it
    if not inside:
        write_checkpoint(target)
    link = "%s/lightning_logs/version_0/checkpoints/epoch=777-val_mel=0.1.ckpt" % world.paths.run
    os.symlink(target, link)
    shown = forged(world, monkeypatch, lambda o: (link,) if o.kind == "files" else o.paths)
    result = freeup.remove(world.paths, world.scratch, shown, [o.number for o in shown.offers if o.kind == "files"][:1])
    assert result.removed_files == 0 and result.failed == ((link, "not a file this may remove"),) and os.path.islink(link) and os.path.exists(target)


def test_only_saved_files_are_removed_even_if_a_list_names_another_kind_of_file_in_the_run_folder(world, monkeypatch):
    three_rounds(world)
    other = "%s/lightning_logs/version_0/hparams.yaml" % world.paths.run
    shown = forged(world, monkeypatch, lambda o: (other,) if o.kind == "files" else o.paths)
    result = freeup.remove(world.paths, world.scratch, shown, [o.number for o in shown.offers if o.kind == "files"][:1])
    assert result.removed_files == 0 and result.failed == ((other, "not a file this may remove"),) and os.path.isfile(other)


def test_a_link_to_a_working_folder_is_not_removed_even_if_a_list_names_it(world, monkeypatch):
    world.run_round(version=0)
    world.run_round(version=1)
    real_folder = make_cache(world, 2)
    link = world.scratch.caches + "/linked-to-round-two"
    os.symlink(real_folder, link)
    shown = forged(world, monkeypatch, lambda o: (link,) if o.kind == "folder" else o.paths)
    result = freeup.remove(world.paths, world.scratch, shown, [o.number for o in shown.offers if o.kind == "folder"])
    assert result.removed_folders == 0 and result.failed == ((link, "not a folder this may remove"),) and os.path.islink(link) and os.path.isdir(real_folder)


def test_a_folder_beside_the_caches_whose_name_starts_the_same_is_not_removed_even_if_a_list_names_it(world, monkeypatch):
    world.run_round(version=0)
    make_cache(world, 1)
    sibling = world.scratch.caches + "-backup"
    spit(sibling + "/keep.txt", "mine")
    real = freeup.plan

    def lying(paths, scratch, record):
        honest = real(paths, scratch, record)
        return freeup.Plan(tuple(freeup.Offer(o.number, o.kind, o.round, o.relation, False, (sibling,) if o.kind == "folder" else o.paths, 4) for o in honest.offers),
                           honest.kept, honest.busy, honest.unclaimed)

    shown = lying(world.paths, world.scratch, rd.load(world.paths))
    monkeypatch.setattr(freeup, "plan", lying)
    result = freeup.remove(world.paths, world.scratch, shown, [o.number for o in shown.offers if o.kind == "folder"])
    assert result.removed_folders == 0 and result.failed and slurp(sibling + "/keep.txt") == b"mine"


def test_the_size_of_a_working_folder_does_not_follow_links_out_of_it(world, tmp_path):
    world.run_round(version=0)
    folder = make_cache(world, 1, size=100)
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "big.bin").write_bytes(b"x" * 100_000)
    os.symlink(str(outside), folder + "/linked")
    os.symlink(str(outside / "big.bin"), folder + "/linked.bin")
    offer = next(o for o in current(world).offers if o.kind == "folder")
    assert offer.bytes < 1000
    freeup.remove(world.paths, world.scratch, current(world), [offer.number])
    assert (outside / "big.bin").read_bytes() == b"x" * 100_000 and not os.path.exists(folder)


def test_the_kept_saved_points_are_never_removed_even_if_a_list_names_them(world, monkeypatch):
    three_rounds(world)
    keep = [f.path for _n, f in current(world).kept]
    real = freeup.plan

    def lying(paths, scratch, record):
        honest = real(paths, scratch, record)
        offer = honest.offers[0]
        return freeup.Plan((freeup.Offer(offer.number, offer.kind, offer.round, offer.relation, False, tuple(keep), 4),) + honest.offers[1:], honest.kept, honest.busy, honest.unclaimed)

    shown = lying(world.paths, world.scratch, rd.load(world.paths))
    monkeypatch.setattr(freeup, "plan", lying)
    result = freeup.remove(world.paths, world.scratch, shown, [1])
    assert result.removed_files == 0 and len(result.failed) == len(keep) and all(exists(keep))


# ---------------------------------------------------------------- the lock

def test_removal_waits_for_the_lock_that_keeps_a_round_from_beginning(world):
    three_rounds(world)
    shown = current(world)
    seen = []
    real = rd.exclusive

    class Spy:
        def __init__(self, paths):
            self.inner = real(paths)

        def __enter__(self):
            seen.append("in")
            return self.inner.__enter__()

        def __exit__(self, *a):
            seen.append("out")
            return self.inner.__exit__(*a)

    import voice_studio.core.freeup as module
    original = module.rd.exclusive
    module.rd.exclusive = Spy
    try:
        freeup.remove(world.paths, world.scratch, shown, [shown.offers[0].number])
    finally:
        module.rd.exclusive = original
    assert seen == ["in", "out"]


def test_the_working_folder_name_for_a_round_is_the_one_the_round_used(world):
    plan = world.begin()
    assert plan.cache_dir == rd.cache_dir_for(world.scratch, DATASET, plan.number)
