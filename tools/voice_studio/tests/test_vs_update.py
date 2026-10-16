# SPDX-License-Identifier: GPL-3.0-or-later
"""Updating the tool (plan task VS-6.2, decision P21): the releases a repository lists, how this copy is told apart from them, the one fetch, the checks on what came, and the comparison.
The fetches run the real git against a repository on this disk (reached by a file:// address)."""
import os
import shutil
from pathlib import Path

import pytest

from vs_update_helpers import FIRST, SECOND, UpdateRig, git
from voice_studio.core import fetch, update as up
from voice_studio.core.consent import make_consent
from voice_studio.core.system import CommandResult

COMMIT = "0123456789abcdef0123456789abcdef01234567"
OTHER = "fedcba9876543210fedcba9876543210fedcba98"


@pytest.fixture
def rig(tmp_path):
    return UpdateRig(tmp_path)


def code_of(fn, *a, **kw):
    with pytest.raises(up.UpdateError) as caught:
        fn(*a, **kw)
    return caught.value.code


def consent(*ids):
    return make_consent([], extra_ids=list(ids))


# ---------------------------------------------------------------- reading the list

def test_a_light_tag_and_an_annotated_tag_are_listed_with_the_commit_each_names():
    text = "%s\trefs/tags/v1.0\n%s\trefs/tags/v1.1\n%s\trefs/tags/v1.1^{}\n" % (COMMIT, OTHER, COMMIT[::-1])
    assert up.parse_releases(text) == (up.Release("v1.0", COMMIT), up.Release("v1.1", COMMIT[::-1]))


def test_lines_that_are_not_tags_or_are_damaged_are_left_out():
    text = "\n".join(["%s\trefs/heads/main" % COMMIT, "%s refs/tags/spaced" % COMMIT, "short\trefs/tags/v9", "%s\trefs/tags/v1.0\textra" % COMMIT, "%s\trefs/tags/ok-1" % COMMIT, "", "garbage"])
    assert up.parse_releases(text) == (up.Release("ok-1", COMMIT),)


def test_a_tag_name_that_is_not_safe_to_pass_on_or_to_make_a_folder_from_is_left_out():
    names = ["-x", ".hidden", "a b", "a/b", "a;b", "x" * 65, "ünï", "v1.0"]
    text = "".join("%s\trefs/tags/%s\n" % (COMMIT, n) for n in names)
    assert [r.name for r in up.parse_releases(text)] == ["v1.0"]
    assert [r.name for r in up.parse_releases("%s\trefs/tags/%s\n" % (COMMIT, "x" * 64))] == ["x" * 64]


def test_nothing_listed_is_an_empty_tuple():
    assert up.parse_releases("") == () and up.parse_releases("\n\n") == ()


@pytest.mark.parametrize("name, key", [("v1.2.3", (1, 2, 3)), ("1.2.3", (1, 2, 3)), ("V2", (2,)), ("v10.0", (10, 0)), ("1.2.x", None), ("v", None), ("1..2", None), ("rc1", None), ("v1.2-beta", None),
                                       ("1." + "9" * 10, None), ("1." + "9" * 9, (1, 999999999)), ("١.٢", None)])
def test_a_release_name_has_an_order_only_when_it_is_a_number_with_dots(name, key):
    assert up.version_key(name) == key


def test_releases_are_sorted_newest_first_by_number_and_the_others_by_name_after_them():
    names = ["v1.9", "v1.10", "beta", "v1.2", "alpha", "v2", "1.10"]
    assert [r.name for r in up.sort_releases(up.Release(n, COMMIT) for n in names)] == ["v2", "v1.10", "1.10", "v1.9", "v1.2", "alpha", "beta"]


def test_the_release_a_commit_is_is_found_and_the_newest_wins_when_two_tags_name_it():
    releases = [up.Release("v1.0", COMMIT), up.Release("v1.0.1", COMMIT), up.Release("v2.0", OTHER)]
    assert up.release_at(releases, COMMIT).name == "v1.0.1" and up.release_at(releases, OTHER).name == "v2.0"
    assert up.release_at(releases, "0" * 40) is None and up.release_at(releases, None) is None and up.release_at([], COMMIT) is None


def test_only_numbered_releases_can_be_newer_and_only_than_a_numbered_release():
    releases = [up.Release("v1.0", COMMIT), up.Release("v1.1", OTHER), up.Release("v0.9", "1" * 40), up.Release("beta", "2" * 40)]
    assert [r.name for r in up.newer_than(releases, releases[0])] == ["v1.1"]
    assert up.newer_than(releases, releases[1]) == () and [r.name for r in up.newer_than(releases, releases[2])] == ["v1.1", "v1.0"]
    assert up.newer_than(releases, releases[3]) == () and up.newer_than(releases, None) == ()


# ---------------------------------------------------------------- what commit a copy is at

def make_git(tmp_path, head, refs=None, packed=None):
    root = tmp_path / "copy"
    (root / ".git" / "refs" / "heads").mkdir(parents=True, exist_ok=True)
    (root / ".git" / "HEAD").write_text(head)
    for ref, value in (refs or {}).items():
        (root / ".git" / ref).parent.mkdir(parents=True, exist_ok=True)
        (root / ".git" / ref).write_text(value)
    if packed is not None:
        (root / ".git" / "packed-refs").write_text(packed)
    return str(root)


def test_a_copy_at_a_release_has_a_detached_head_that_is_read(tmp_path):
    assert up.head_commit(make_git(tmp_path, COMMIT + "\n")) == COMMIT


def test_a_copy_on_a_branch_reads_the_branch_file_then_the_packed_refs(tmp_path):
    root = make_git(tmp_path, "ref: refs/heads/main\n", {"refs/heads/main": OTHER + "\n"})
    assert up.head_commit(root) == OTHER
    os.unlink(root + "/.git/refs/heads/main")
    assert up.head_commit(root) is None
    Path(root + "/.git/packed-refs").write_text("# pack-refs\n%s refs/heads/other\n%s refs/heads/main\n^%s\n" % (COMMIT, OTHER, COMMIT))
    assert up.head_commit(root) == OTHER


def test_a_head_that_cannot_be_trusted_is_not_a_commit(tmp_path):
    for head in ("ref: refs/heads/../../x\n", "ref: heads/main\n", "garbage\n", "", COMMIT[:39] + "\n", COMMIT.upper() + "\n", COMMIT + "0\n"):
        assert up.head_commit(make_git(tmp_path / ("c%d" % abs(hash(head))), head, {"refs/heads/main": OTHER})) is None, head
    assert up.head_commit(make_git(tmp_path / "bad", "ref: refs/heads/main\n", {"refs/heads/main": "not a commit\n"})) is None


def test_a_folder_that_is_not_a_git_copy_has_no_commit(tmp_path):
    assert up.head_commit(str(tmp_path)) is None and up.head_commit(str(tmp_path / "missing")) is None


def test_a_packed_ref_line_for_another_branch_or_with_a_bad_commit_is_not_used(tmp_path):
    root = make_git(tmp_path, "ref: refs/heads/main\n", packed="%s refs/heads/mainly\nnothex refs/heads/main\n" % COMMIT)
    assert up.head_commit(root) is None


def test_the_version_of_a_copy_is_read_from_its_package_file_without_importing_it(tmp_path):
    root = tmp_path / "c"
    (root / "tools/voice_studio").mkdir(parents=True)
    (root / up.PACKAGE_FILE).write_text('"""x"""\n__version__ = "2.3.4"\nraise SystemExit("never run")\n')
    assert up.read_version(str(root)) == "2.3.4"
    (root / up.PACKAGE_FILE).write_text("no version here\n")
    assert up.read_version(str(root)) is None
    (root / up.PACKAGE_FILE).write_bytes(b"\xff\xfe\x00")
    assert up.read_version(str(root)) is None
    assert up.read_version(str(tmp_path / "missing")) is None


# ---------------------------------------------------------------- asking, through the download module

def test_the_releases_are_listed_with_one_ls_remote_and_the_agreement_for_listing(rig):
    found = up.list_releases(rig.networked, consent(up.LIST_ID), rig.url)
    assert {r.name: r.commit for r in found} == rig.commits
    assert rig.calls == [(["git", "ls-remote", "--tags", rig.url], [up.LIST_ID])]


def test_an_annotated_tag_is_listed_with_the_commit_behind_it_not_the_tag_object(rig):
    found = {r.name: r.commit for r in up.list_releases(rig.networked, consent(up.LIST_ID), rig.url)}
    tag_object = git("rev-parse", "v1.1", cwd=rig.repo)
    assert tag_object != rig.commits["v1.1"] and found["v1.1"] == rig.commits["v1.1"]


def test_without_agreement_the_download_module_refuses_and_nothing_is_asked(rig):
    with pytest.raises(fetch.FetchError):
        fetch.run_networked(None, ["git", "ls-remote", "--tags", rig.url], [up.LIST_ID], runner=lambda argv: pytest.fail("asked"))
    with pytest.raises(fetch.FetchError):
        fetch.run_networked(consent(up.GET_ID), ["git", "ls-remote", "--tags", rig.url], [up.LIST_ID], runner=lambda argv: pytest.fail("asked"))


def test_a_failed_listing_is_unreachable_with_the_last_line_git_said(rig):
    rig.offline = True
    with pytest.raises(up.UpdateError) as caught:
        up.list_releases(rig.networked, consent(up.LIST_ID), rig.url)
    assert caught.value.code == "unreachable" and caught.value.detail == "fatal: unable to access: Could not resolve host"


def test_a_failed_listing_that_said_nothing_names_the_exit_number(rig):
    with pytest.raises(up.UpdateError) as caught:
        up.list_releases(lambda c, a, i: CommandResult(2, "\n  \n", ""), consent(up.LIST_ID), rig.url)
    assert caught.value.detail == "exit 2"


def test_a_refusal_or_a_program_that_cannot_start_is_unreachable_with_its_reason(rig):
    rig.refuse = fetch.FetchError("http", "No such file or directory")
    with pytest.raises(up.UpdateError) as caught:
        up.list_releases(rig.networked, consent(up.LIST_ID), rig.url)
    assert caught.value.code == "unreachable" and caught.value.detail == "No such file or directory"
    rig.refuse = fetch.FetchError("consent")
    with pytest.raises(up.UpdateError) as caught:
        up.list_releases(rig.networked, consent(up.LIST_ID), rig.url)
    assert caught.value.detail == "consent"


def test_a_long_last_line_is_cut(rig):
    with pytest.raises(up.UpdateError) as caught:
        up.list_releases(lambda c, a, i: CommandResult(1, "x" * 500, ""), consent(up.LIST_ID), rig.url)
    assert len(caught.value.detail) == 200


# ---------------------------------------------------------------- where the new copy goes

def test_a_release_goes_in_a_folder_beside_this_copy_named_for_it():
    assert up.folder_name("/home/u/ack-tools", "v1.1") == "/home/u/ack-tools-v1.1" and up.folder_name("/home/u/ack-tools/", "v1.1") == "/home/u/ack-tools-v1.1"
    assert up.folder_name("/h/ack", "a b/c") == "/h/ack-a-b-c" and up.folder_name("/h/ack", "r1_2.3-x") == "/h/ack-r1_2.3-x"


def test_a_place_that_is_taken_by_anything_is_refused_and_a_free_one_is_not(tmp_path):
    taken = tmp_path / "taken"
    taken.mkdir()
    (tmp_path / "file").write_text("x")
    os.symlink(tmp_path / "nowhere", tmp_path / "dangling")
    for path in (taken, tmp_path / "file", tmp_path / "dangling"):
        assert code_of(up.check_destination, str(path), None) == "folder_exists"
    up.check_destination(str(tmp_path / "free"), None)


def test_the_room_needed_is_exactly_the_stated_amount(tmp_path):
    dest = str(tmp_path / "new")
    up.check_destination(dest, up.ROOM_BYTES)
    up.check_destination(dest, up.ROOM_BYTES + 1)
    up.check_destination(dest, None)
    with pytest.raises(up.UpdateError) as caught:
        up.check_destination(dest, up.ROOM_BYTES - 1)
    assert caught.value.code == "no_room" and caught.value.detail == str(up.ROOM_BYTES - 1)


# ---------------------------------------------------------------- fetching one release

def release_of(rig, name):
    return up.Release(name, rig.commits[name])


def test_a_release_is_fetched_with_one_shallow_clone_and_checked(rig):
    dest = str(rig.tmp / "ack-tools-v1.1")
    fetched = up.get_release(rig.networked, consent(up.GET_ID), rig.url, release_of(rig, "v1.1"), dest)
    assert rig.calls == [(["git", "clone", "--depth", "1", "--branch", "v1.1", rig.url, dest], [up.GET_ID])]
    assert fetched == up.Fetched(release_of(rig, "v1.1"), dest, "1.1.0") and up.head_commit(dest) == rig.commits["v1.1"]
    assert rig.tree(dest)["tools/voice_studio/core/y.py"] == b"y = 1\n"


def test_a_light_tag_is_fetched_too(rig):
    dest = str(rig.tmp / "new")
    fetched = up.get_release(rig.networked, consent(up.GET_ID), rig.url, release_of(rig, "v1.0"), dest)
    assert fetched.version == "1.0.0" and up.head_commit(dest) == rig.commits["v1.0"]


def test_a_name_that_is_not_safe_is_refused_before_anything_is_asked(rig):
    for name in ("-x", "a b", "", "x" * 65, "a/b"):
        assert code_of(up.get_release, rig.networked, consent(up.GET_ID), rig.url, up.Release(name, COMMIT), str(rig.tmp / "new")) == "bad_name"
    assert rig.calls == []


def test_a_clone_that_fails_leaves_no_folder_and_names_what_git_said(rig):
    dest = str(rig.tmp / "new")
    with pytest.raises(up.UpdateError) as caught:
        up.get_release(rig.networked, consent(up.GET_ID), rig.url, up.Release("v9.9", COMMIT), dest)
    assert caught.value.code == "unreachable" and "v9.9" in caught.value.detail and not os.path.lexists(dest)


def test_a_connection_that_drops_after_the_folder_was_begun_removes_it_again(rig):
    dest = str(rig.tmp / "new")

    def drops(consent_, argv, ids, **kw):
        os.makedirs(dest + "/half")
        return CommandResult(128, "fatal: the remote end hung up unexpectedly\n", "")
    with pytest.raises(up.UpdateError) as caught:
        up.get_release(drops, consent(up.GET_ID), rig.url, release_of(rig, "v1.1"), dest)
    assert caught.value.code == "unreachable" and caught.value.detail == "fatal: the remote end hung up unexpectedly" and not os.path.lexists(dest)


def test_a_download_module_that_refuses_after_the_folder_was_begun_removes_it_again(rig):
    dest = str(rig.tmp / "new")

    def refuses(consent_, argv, ids, **kw):
        os.makedirs(dest)
        raise fetch.FetchError("http", "Input/output error")
    with pytest.raises(up.UpdateError) as caught:
        up.get_release(refuses, consent(up.GET_ID), rig.url, release_of(rig, "v1.1"), dest)
    assert caught.value.detail == "Input/output error" and not os.path.lexists(dest)


def test_ctrl_c_in_the_middle_removes_the_half_made_folder_and_goes_on_raising(rig):
    dest = str(rig.tmp / "new")

    def interrupted(consent_, argv, ids, **kw):
        os.makedirs(dest + "/half")
        raise KeyboardInterrupt
    with pytest.raises(KeyboardInterrupt):
        up.get_release(interrupted, consent(up.GET_ID), rig.url, release_of(rig, "v1.1"), dest)
    assert not os.path.lexists(dest)


def test_a_copy_that_holds_another_commit_than_the_one_listed_is_removed_and_reported(rig):
    dest = str(rig.tmp / "new")
    wrong = up.Release("v1.1", rig.commits["v1.0"])
    with pytest.raises(up.UpdateError) as caught:
        up.get_release(rig.networked, consent(up.GET_ID), rig.url, wrong, dest)
    assert caught.value.code == "differs" and caught.value.detail == "v1.1" and not os.path.lexists(dest)


def test_a_copy_that_is_not_a_copy_of_this_tool_is_removed_and_reported(rig):
    other = rig.tmp / "other"
    other.mkdir()
    git("init", "-q", "-b", "main", cwd=other)
    (other / "readme.txt").write_text("x")
    git("add", "-A", cwd=other)
    git("commit", "-q", "-m", "x", cwd=other)
    git("tag", "v1", cwd=other)
    commit = git("rev-parse", "v1", cwd=other)
    dest = str(rig.tmp / "new")
    with pytest.raises(up.UpdateError) as caught:
        up.get_release(rig.networked, consent(up.GET_ID), "file://" + str(other), up.Release("v1", commit), dest)
    assert caught.value.code == "not_a_release" and caught.value.detail == "v1" and not os.path.lexists(dest)


def test_only_the_folder_that_was_made_is_removed_when_a_copy_fails_its_check(rig):
    sibling = rig.tmp / "ack-tools-v1.0"
    sibling.mkdir()
    (sibling / "keep.txt").write_text("keep")
    dest = str(rig.tmp / "new")
    code_of(up.get_release, rig.networked, consent(up.GET_ID), rig.url, up.Release("v1.1", rig.commits["v1.0"]), dest)
    assert (sibling / "keep.txt").read_text() == "keep" and rig.here.is_dir()


# ---------------------------------------------------------------- what is different

def test_the_areas_of_the_files_are_told_apart():
    cat = up.category_of
    assert cat("tools/voice_studio/data/locks/studio.lock.txt") == "programs" and cat("tools/voice_studio/data/native/x.pyx") == "programs" and cat("tools/voice_studio/data/environments.json") == "programs"
    assert cat("tools/voice_studio/data/sources.json") == "downloads" and cat("tools/voice_studio/data/text/en.json") == "words"
    assert cat("tools/freeform_studio/app.py") == "recordings" and cat("docs/VOICE_STUDIO_GUIDE.md") == "docs" and cat("docs/ACK_Voice_Studio_Installation_Guide.MD") == "docs"
    assert cat("tools/voice_studio/core/x.py") == "code" and cat("tools/voice_studio/data/icons/x.svg") == "code" and cat("tools/voice_studio/data/sources.json.bak") == "code"
    assert set(up.CATEGORIES) == {cat(p) for p in ("tools/voice_studio/data/locks/a", "tools/voice_studio/data/sources.json", "tools/voice_studio/data/text/a", "tools/freeform_studio/a", "docs/VOICE_STUDIO_A", "tools/voice_studio/core/a")}


def test_two_copies_are_compared_by_area_with_what_changed_what_is_new_and_what_is_gone(rig):
    new = str(rig.tmp / "new")
    up.get_release(rig.networked, consent(up.GET_ID), rig.url, release_of(rig, "v1.1"), new)
    os.unlink(new + "/tools/voice_studio/core/x.py")                      # in the old copy, not in the new
    changes = up.compare(str(rig.here), new)
    assert changes.changed["programs"] == ("tools/voice_studio/data/locks/studio.lock.txt",) and changes.changed["code"] == ("tools/voice_studio/__init__.py",)
    assert changes.added["code"] == ("tools/voice_studio/core/y.py",) and changes.removed["code"] == ("tools/voice_studio/core/x.py",)
    assert changes.changed["words"] == ("tools/voice_studio/data/text/en.json",) and changes.changed["recordings"] == ("tools/freeform_studio/app.py",) and changes.changed["docs"] == ("docs/VOICE_STUDIO_GUIDE.md",)
    assert changes.changed["downloads"] == () and changes.any


def test_files_outside_the_compared_areas_are_not_looked_at(rig):
    new = str(rig.tmp / "new")
    up.get_release(rig.networked, consent(up.GET_ID), rig.url, release_of(rig, "v1.1"), new)
    changes = up.compare(str(rig.here), new)
    assert "docs/OTHER.md" not in sum((list(v) for v in changes.changed.values()), [])


def test_the_same_copy_has_no_differences_and_caches_links_and_git_files_do_not_count(rig, tmp_path):
    copy = str(rig.tmp / "copy2")
    shutil.copytree(rig.here, copy)
    os.makedirs(copy + "/tools/voice_studio/__pycache__")
    Path(copy + "/tools/voice_studio/__pycache__/x.pyc").write_bytes(b"x")
    Path(copy + "/tools/voice_studio/core/stale.pyc").write_bytes(b"x")
    os.symlink(tmp_path, copy + "/tools/voice_studio/link")
    os.symlink(tmp_path, copy + "/tools/voice_studio/core/linked-file")
    assert not up.compare(str(rig.here), copy).any


def test_a_link_to_a_folder_is_not_walked_into(rig, tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "x.py").write_text("x")
    copy = str(rig.tmp / "copy2")
    shutil.copytree(rig.here, copy)
    os.symlink(outside, copy + "/tools/voice_studio/core/folderlink")
    assert not up.compare(str(rig.here), copy).any


def test_a_file_too_big_to_read_is_compared_by_its_size(rig, monkeypatch):
    copy = str(rig.tmp / "copy2")
    shutil.copytree(rig.here, copy)
    monkeypatch.setattr(up, "MAX_FILE_BYTES", 5)
    Path(copy + "/tools/voice_studio/core/x.py").write_text("x = 2\n")             # the same size, so not told apart: the price of not reading a huge file
    assert not up.compare(str(rig.here), copy).changed["code"]
    Path(copy + "/tools/voice_studio/core/x.py").write_text("x = 22\n")
    assert up.compare(str(rig.here), copy).changed["code"] == ("tools/voice_studio/core/x.py",)


def test_a_file_that_cannot_be_read_counts_as_unlike_one_that_can(rig, monkeypatch):
    copy = str(rig.tmp / "copy2")
    shutil.copytree(rig.here, copy)
    real = open

    def refuse(path, *a, **kw):
        if str(path).endswith("core/x.py") and str(path).startswith(copy):
            raise OSError(13, "Permission denied")
        return real(path, *a, **kw)
    monkeypatch.setattr("builtins.open", refuse)
    assert up.compare(str(rig.here), copy).changed["code"] == ("tools/voice_studio/core/x.py",)


def test_every_error_code_has_three_parts_in_words():
    from vs_refresh_helpers import CAT
    from voice_studio.core.describe import error_text
    for code in up.ERROR_CODES:
        parts = error_text(CAT, "update", code)
        assert parts.what and parts.changed and parts.next


# ---------------------------------------------------------------- the address the releases are asked of

def doc_with(releases):
    import json
    return json.dumps({"schema": 1, "items": [], "releases": releases})


def test_the_shipped_registry_names_one_repository_on_an_allowed_host_for_releases():
    from voice_studio.core import registry as reg
    source = reg.load_release_source()
    assert source.url.startswith("https://github.com/") and source.host == "github.com" and source.why_key == "update.why"
    assert reg.load_registry() is not None, "the extra key does not disturb the list of downloads"


def test_a_release_address_that_is_not_https_on_an_allowed_host_without_credentials_is_refused():
    from voice_studio.core import registry as reg
    good = {"url": "https://github.com/x/y.git", "why_key": "update.why"}
    assert reg.parse_release_source(doc_with(good)).url == "https://github.com/x/y.git"
    for bad in ({**good, "url": "http://github.com/x/y.git"}, {**good, "url": "https://evil.example/x/y.git"}, {**good, "url": "https://user:pw@github.com/x/y.git"}, {**good, "url": "file:///tmp/x"},
                {**good, "url": ""}, {**good, "url": 5}, {**good, "url": "https://github.com/x y"}, {**good, "why_key": ""}, {**good, "why_key": 3}, {"url": good["url"]}, {"why_key": "update.why"}, "text", None):
        with pytest.raises(reg.RegistryError):
            reg.parse_release_source(doc_with(bad))
    with pytest.raises(reg.RegistryError):
        reg.parse_release_source("not json")
    with pytest.raises(reg.RegistryError):
        reg.parse_release_source('{"schema": 1, "items": []}')


def test_a_registry_file_that_cannot_be_read_is_a_registry_error(tmp_path):
    from voice_studio.core import registry as reg
    with pytest.raises(reg.RegistryError):
        reg.load_release_source(tmp_path / "missing.json")


def test_the_host_of_a_source_is_its_host_or_the_whole_address_when_it_has_none():
    from voice_studio.core.registry import ReleaseSource
    assert ReleaseSource("https://github.com/x/y.git", "k").host == "github.com" and ReleaseSource("file:///tmp/x", "k").host == "file:///tmp/x"


# ---------------------------------------------------------------- the exact edges (each found by breaking the code on purpose and seeing nothing fail)

def test_a_release_name_ends_exactly_at_its_last_letter_and_is_at_most_sixty_four_long():
    assert up.RELEASE_NAME.match("v1.0") and up.RELEASE_NAME.match("x" * 64) and not up.RELEASE_NAME.match("x" * 65)
    assert not up.RELEASE_NAME.match("v1.0\n") and not up.RELEASE_NAME.match("v1.0 ") and not up.RELEASE_NAME.match(".v1") and not up.RELEASE_NAME.match("a/b")


def test_a_commit_is_exactly_forty_lower_case_hex_letters(tmp_path):
    assert up.parse_releases("%s0\trefs/tags/v1\n" % COMMIT) == () and up.parse_releases("%s\trefs/tags/v1\n" % COMMIT[:39]) == ()
    assert up.head_commit(make_git(tmp_path, COMMIT + "0\n")) is None


def test_a_line_is_kept_only_when_it_is_exactly_what_git_prints():
    text = " %s\trefs/tags/pad-a\n%s\trefs/tags/pad-b \n%s\trefs/headsXv1.0\n" % (COMMIT, COMMIT, COMMIT)
    assert up.parse_releases(text) == ()                       # the third would be called "Xv1.0" if the folder in front of the name were not checked


def test_only_a_name_ending_in_caret_braces_is_the_commit_behind_a_tag():
    text = "%s\trefs/tags/v1.0\n%s\trefs/tags/v1.0xx}\n%s\trefs/tags/v1.0y{}\n" % (COMMIT, OTHER, OTHER)      # dropping the last three letters of either would give the first's name
    assert up.parse_releases(text) == (up.Release("v1.0", COMMIT),)


def test_the_same_number_written_two_ways_is_ordered_by_name_whatever_order_it_came_in():
    first, second = up.Release("1.0", COMMIT), up.Release("v1.0", OTHER)
    assert [r.name for r in up.sort_releases([first, second])] == ["v1.0", "1.0"] == [r.name for r in up.sort_releases([second, first])]


def test_a_head_that_leads_outside_the_refs_folder_is_not_followed(tmp_path):
    for number, head in enumerate(("ref: refs/heads/../../x\n", "ref: heads/main\n", "xxxxxrefs/heads/main\n")):
        root = make_git(tmp_path / ("h%d" % number), head, {"refs/heads/main": OTHER, "heads/main": OTHER, "x": OTHER})      # every place the head could be talked into reading holds a real commit
        assert up.head_commit(root) is None, head


def test_a_peeled_line_in_the_packed_refs_is_passed_over(tmp_path):
    root = make_git(tmp_path, "ref: refs/heads/main\n", packed="# pack-refs with: peeled\n%s refs/tags/v1\n^%s\n%s refs/heads/main\n" % (COMMIT, OTHER, OTHER))
    assert up.head_commit(root) == OTHER


def test_a_head_or_packed_refs_file_that_is_not_text_is_not_a_commit(tmp_path):
    root = make_git(tmp_path / "a", COMMIT)
    Path(root + "/.git/HEAD").write_bytes(b"\xff\xfe\x00")
    assert up.head_commit(root) is None
    root = make_git(tmp_path / "b", "ref: refs/heads/main\n")
    Path(root + "/.git/packed-refs").write_bytes(b"\xff\xfe\x00")
    assert up.head_commit(root) is None


def test_a_path_with_a_slash_on_the_end_still_finds_the_commit(tmp_path):
    assert up.head_commit(make_git(tmp_path, COMMIT + "\n") + "/") == COMMIT


def test_the_version_line_must_be_a_whole_line_of_its_own_with_a_plain_text_value(tmp_path):
    def version_of(text):
        root = tmp_path / ("v%d" % abs(hash(text)))
        (root / "tools/voice_studio").mkdir(parents=True)
        (root / up.PACKAGE_FILE).write_text(text)
        return up.read_version(str(root))
    assert version_of('# it was __version__ = "0.1.0"\n__version__ = "2.0.0"\n') == "2.0.0"
    assert version_of('# it was __version__ = "0.1.0"\n') is None
    assert version_of('__version__ = "1.0" + suffix\n') is None
    assert version_of('__version__ = "%s"\n' % ("9" * 40)) == "9" * 40 and version_of('__version__ = "%s"\n' % ("9" * 41)) is None and version_of('__version__ = ""\n') is None
    assert version_of('__version__ = "1.0"   \n') == "1.0"


def test_the_figures_the_guides_and_the_screen_state_are_these(tmp_path):
    assert up.ROOM_BYTES == 500_000_000, "the checklist and the screen say 500 MB: change them together"
    assert up.MAX_FILE_BYTES == 64 * 2 ** 20
    up.check_destination(str(tmp_path / "a"), 500_000_000)
    assert code_of(up.check_destination, str(tmp_path / "b"), 499_999_999) == "no_room"


def test_an_error_reads_as_its_code_and_its_detail():
    assert str(up.UpdateError("unreachable")) == "unreachable" and str(up.UpdateError("unreachable", "no route")) == "unreachable: no route"


def test_an_unsafe_name_is_shown_cut_to_sixty_four_letters(rig):
    with pytest.raises(up.UpdateError) as caught:
        up.get_release(rig.networked, consent(up.GET_ID), rig.url, up.Release("x" * 100 + " ", COMMIT), str(rig.tmp / "new"))
    assert caught.value.code == "bad_name" and caught.value.detail == "x" * 64


def test_a_clone_that_exits_with_one_is_a_failure_too_and_its_folder_goes(rig):
    dest = str(rig.tmp / "new")

    def fails(consent_, argv, ids, **kw):
        os.makedirs(dest + "/half")
        return CommandResult(1, "error: it did not work\n", "")
    with pytest.raises(up.UpdateError) as caught:
        up.get_release(fails, consent(up.GET_ID), rig.url, release_of(rig, "v1.1"), dest)
    assert caught.value.code == "unreachable" and caught.value.detail == "error: it did not work" and not os.path.lexists(dest)


def test_a_folder_that_is_there_before_the_clone_is_refused_and_left_alone(rig):
    dest = rig.tmp / "new"
    dest.mkdir()
    (dest / "mine.txt").write_text("mine")
    assert code_of(up.get_release, rig.networked, consent(up.GET_ID), rig.url, release_of(rig, "v1.1"), str(dest)) == "folder_exists"
    assert (dest / "mine.txt").read_text() == "mine" and rig.calls == [], "nothing was asked, and what was there was not removed"


@pytest.mark.parametrize("target", ["real", "dangling"])
def test_a_link_where_the_copy_should_be_is_unlinked_never_followed(rig, tmp_path, target):
    dest = str(rig.tmp / "new")
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "keep.txt").write_text("keep")

    def links(consent_, argv, ids, **kw):
        os.symlink(outside if target == "real" else tmp_path / "nowhere", dest)
        return CommandResult(0, "", "")
    assert code_of(up.get_release, links, consent(up.GET_ID), rig.url, release_of(rig, "v1.1"), dest) == "differs"
    assert not os.path.lexists(dest) and (outside / "keep.txt").read_text() == "keep"


def test_a_package_file_that_is_a_folder_is_not_a_copy_of_this_tool(rig):
    other = rig.tmp / "other2"
    (other / up.PACKAGE_FILE).mkdir(parents=True)
    git("init", "-q", "-b", "main", cwd=other)
    (other / up.PACKAGE_FILE / "inner.txt").write_text("x")
    git("add", "-A", cwd=other)
    git("commit", "-q", "-m", "x", cwd=other)
    git("tag", "v1", cwd=other)
    dest = str(rig.tmp / "new")
    assert code_of(up.get_release, rig.networked, consent(up.GET_ID), "file://" + str(other), up.Release("v1", git("rev-parse", "v1", cwd=other)), dest) == "not_a_release" and not os.path.lexists(dest)


@pytest.mark.parametrize("kind", ["changed", "added", "removed"])
def test_a_copy_that_differs_in_only_one_way_still_differs(rig, kind):
    copy = str(rig.tmp / "copy2")
    shutil.copytree(rig.here, copy)
    if kind == "changed":
        Path(copy + "/tools/voice_studio/core/x.py").write_text("x = 2\n")
    elif kind == "added":
        Path(copy + "/tools/voice_studio/core/new.py").write_text("n\n")
    else:
        os.unlink(copy + "/tools/voice_studio/core/x.py")
    changes = up.compare(str(rig.here), copy)
    assert changes.any and [bool(any(getattr(changes, k).values())) for k in ("changed", "added", "removed")] == [k == kind for k in ("changed", "added", "removed")]


def test_only_this_tools_guides_are_compared(rig):
    copy = str(rig.tmp / "copy2")
    shutil.copytree(rig.here, copy)
    Path(copy + "/docs/ACK_Voices_notes.md").write_text("not ours\n")
    Path(copy + "/docs/VOICE_STUDIO_NEW.md").write_text("ours\n")
    assert up.compare(str(rig.here), copy).added["docs"] == ("docs/VOICE_STUDIO_NEW.md",)
    assert up.category_of("docs/VOICE_STUDIO_NEW.md") == "docs"
    Path(copy + "/docs/ACK_Voice_Studio_Installation_Guide.MD").write_text("two\n")                    # the installation guides are named differently from the other guides
    assert up.compare(str(rig.here), copy).changed["docs"] == ("docs/ACK_Voice_Studio_Installation_Guide.MD",)


def test_a_cache_folder_is_skipped_whatever_is_in_it_and_so_is_a_link_to_a_file(rig, tmp_path):
    copy = str(rig.tmp / "copy2")
    shutil.copytree(rig.here, copy)
    os.makedirs(copy + "/tools/voice_studio/core/__pycache__")
    Path(copy + "/tools/voice_studio/core/__pycache__/notes.txt").write_text("x")
    target = tmp_path / "target.py"
    target.write_text("elsewhere")
    os.symlink(target, copy + "/tools/voice_studio/core/linked.py")
    assert not up.compare(str(rig.here), copy).any


def test_a_file_exactly_as_big_as_the_limit_is_still_read(rig, monkeypatch):
    copy = str(rig.tmp / "copy2")
    shutil.copytree(rig.here, copy)
    monkeypatch.setattr(up, "MAX_FILE_BYTES", 6)                                    # "x = 1\n" is six bytes
    Path(copy + "/tools/voice_studio/core/x.py").write_text("x = 2\n")
    assert up.compare(str(rig.here), copy).changed["code"] == ("tools/voice_studio/core/x.py",)


def test_a_registry_that_cannot_be_used_says_which_part_is_wrong():
    from voice_studio.core import registry as reg
    with pytest.raises(reg.RegistryError) as caught:
        reg.parse_release_source('{"schema": 1, "items": []}')
    assert "releases" in str(caught.value)
    with pytest.raises(reg.RegistryError) as caught:
        reg.parse_release_source(doc_with({"url": "http://github.com/x/y.git", "why_key": "update.why"}))
    assert "not_https" in str(caught.value)
    with pytest.raises(reg.RegistryError) as caught:
        reg.parse_release_source(doc_with({"url": "https://evil.example/x/y.git", "why_key": "update.why"}))
    assert "host" in str(caught.value)
