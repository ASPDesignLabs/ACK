# SPDX-License-Identifier: GPL-3.0-or-later
"""The terminal front for updating the tool (plan task VS-6.2): what each command says before it contacts anything, what it asks, what it does with a yes, and what it leaves alone.
The flows are the real code, the commands are the real git against a repository on this disk, and the download module is a stand-in that checks the agreement and remembers what it was asked."""
import os
import shlex
from pathlib import Path

import pytest

from vs_refresh_helpers import CAT, TermIO
from vs_startvoice_helpers import implies_permission, leaked_keys
from vs_update_helpers import FIRST, UpdateRig, UpdateSystem
from voice_studio.core import update as up, update_flow as uf
from voice_studio.core.text import size_text


@pytest.fixture
def rig(tmp_path):
    return UpdateRig(tmp_path)


def run(rig, *argv, answers=(), interactive=True, version="1.0.0"):
    io = TermIO(answers, interactive)
    code = uf.run_update(list(argv), CAT, io, system=rig.system, source=rig.source, networked=rig.networked, tools_dir=rig.tools_dir, version=version)
    assert leaked_keys(io.text + "\n".join(io.prompts)) == [], "a catalog key was printed instead of words"
    assert implies_permission(io.text) == [], "something printed says or implies that use is permitted"
    return code, io


# ---------------------------------------------------------------- help and the command line

def test_no_command_and_help_list_the_two_commands_and_that_nothing_is_contacted_unasked(rig):
    for argv in ((), ("help",), ("--help",), ("-h",)):
        code, io = run(rig, *argv)
        assert code == 0 and io.prompts == [] and rig.calls == [] and io.lines[0] == "ACK Voice Studio: update" and "Commands:" in io.lines
        for part in ("check [--yes]:", "get release [--to folder] [--yes]:", "Nothing is contacted unless you say yes, nothing is checked in the background"):
            assert part in io.text, part


def test_an_unknown_command_is_named_and_nothing_is_contacted(rig):
    code, io = run(rig, "upgrade")
    assert code == 2 and "upgrade" in io.text and rig.calls == []


def test_the_options_each_command_publishes_are_the_options_it_accepts(rig):
    assert uf.OPTIONS == {"check": frozenset({"--yes", "-y"}), "get": frozenset({"--yes", "-y", "--to"})} and uf.COMMANDS == ("check", "get", "help")
    for command in ("check", "get"):
        code, io = run(rig, command, "--nonsense")
        assert code == 2 and "--nonsense" in io.text and rig.calls == [], command
    assert run(rig, "check", "extra", "--yes")[0] == 2 and run(rig, "get", "v1.1", "extra", "--yes")[0] == 2 and rig.calls == [], "a word too many is refused even when it was told to go ahead"


def test_every_usage_line_has_words():
    for key in uf.USAGE:
        assert CAT.has(key)


# ---------------------------------------------------------------- check: before it contacts anything

def test_check_says_where_this_copy_is_what_it_will_ask_and_what_the_request_carries_before_it_asks(rig):
    code, io = run(rig, "check", answers=["no"])
    assert code == 2 and rig.calls == [] and io.prompts == ["Look for new releases now? Type yes to go on. "] and "Nothing was done." in io.lines
    ask = io.events.index(("ask", io.prompts[0]))
    said = [t for kind, t in io.events[:ask] if kind == "say"]
    assert said[:3] == ["ACK Voice Studio: update", "This copy is version 1.0.0, in %s." % rig.here, "It contacts the internet to ask which releases of ACK Voice Studio exist, and to fetch one when you choose."]
    assert "Like any request on the internet it carries this computer's address and the name of the program asking. Nothing you recorded, typed or made is sent, and nothing is saved." in said
    assert "This asks %s for the list of tags in ACK's repository, with one command: git ls-remote --tags %s" % (rig.source.url, rig.source.url) in said


def test_with_nobody_to_ask_nothing_is_contacted(rig):
    code, io = run(rig, "check", interactive=False)
    assert code == 2 and rig.calls == [] and "There was nobody to ask. To say yes on the command line, add --yes. Nothing was done." in io.lines


def test_without_git_nothing_is_asked_and_nothing_is_contacted(rig):
    rig.system.git_present = False
    code, io = run(rig, "check", "--yes")
    assert code == 2 and rig.calls == [] and io.prompts == [] and io.lines[-3:] == ["The program that fetches releases, git, is not installed on this computer.", "Nothing was contacted and nothing was changed.",
                                                                                 "The setup in the installation guide installs it, after asking. Then try again."]


def test_a_copy_that_is_not_a_git_copy_says_so_before_asking(tmp_path):
    rig = UpdateRig(tmp_path, here_at=None)
    (rig.here / "tools" / "voice_studio").mkdir(parents=True)
    code, io = run(rig, "check", answers=["no"])
    assert "It is not a plain git copy, so it cannot be compared with a release." in io.lines and code == 2


# ---------------------------------------------------------------- check: after a yes

def test_check_lists_the_releases_newest_first_marks_this_copy_and_the_newer_ones_and_says_how_to_fetch(rig):
    code, io = run(rig, "check", answers=["yes"])
    assert code == 0 and rig.calls == [(["git", "ls-remote", "--tags", rig.url], [up.LIST_ID])]
    assert io.lines[-6:] == ["It is the release v1.0.", "2 releases of ACK Voice Studio are listed:", "  v1.1: newer than this copy", "  v1.0: this copy", "1 release is newer than this copy.",
                             "To fetch one into a new folder beside this copy, run: python3 -m voice_studio.update get v1.1"]


def test_dash_dash_yes_answers_the_question_and_dash_y_too(rig):
    assert run(rig, "check", "--yes")[1].prompts == [] and run(rig, "check", "-y")[1].prompts == [] and len(rig.calls) == 2


def test_check_on_the_newest_release_says_no_release_is_newer(tmp_path):
    rig = UpdateRig(tmp_path, here_at="v1.1")
    code, io = run(rig, "check", "--yes")
    assert code == 0 and "It is the release v1.1." in io.lines and "No release is newer than this copy." in io.lines and "  v1.1: this copy" in io.lines and "  v1.0" in io.lines
    assert io.lines[-1] == "To fetch one into a new folder beside this copy, run: python3 -m voice_studio.update get v1.1"


def test_check_on_a_copy_that_is_not_at_a_release_says_none_can_be_called_newer(tmp_path):
    rig = UpdateRig(tmp_path, here_at="v1.0")
    from vs_update_helpers import git
    (rig.repo / "tools/voice_studio/core/z.py").write_text("z\n")
    git("add", "-A", cwd=rig.repo)
    git("commit", "-q", "-m", "after the releases", cwd=rig.repo)
    git("fetch", "-q", "--depth", "1", "origin", "main", cwd=rig.here)
    git("checkout", "-q", "FETCH_HEAD", cwd=rig.here)
    code, io = run(rig, "check", "--yes")
    commit = up.head_commit(str(rig.here))
    assert code == 0 and "It is not at a named release (it is at the commit %s), so it cannot be compared with one." % commit[:10] in io.lines and "This copy is not at a release, so none can be called newer." in io.lines
    assert io.lines[-1] == "To fetch one into a new folder beside this copy, run: python3 -m voice_studio.update get v1.1"


def test_check_with_no_releases_says_there_is_nothing_to_fetch(tmp_path):
    rig = UpdateRig(tmp_path, releases=("v1.0",), here_at="v1.0")
    from vs_update_helpers import git
    git("tag", "-d", "v1.0", cwd=rig.repo)
    code, io = run(rig, "check", "--yes")
    assert code == 0 and io.lines[-1] == "ACK Voice Studio has no named releases yet, so there is nothing to fetch." and not any("listed" in l for l in io.lines)


def test_only_ten_releases_are_listed_and_all_are_counted(tmp_path):
    names = tuple("v1.%d" % i for i in range(12))
    rig = UpdateRig(tmp_path, releases=names, here_at="v1.0")
    code, io = run(rig, "check", "--yes")
    rows = [l for l in io.lines if l.startswith("  v1.")]
    assert "12 releases of ACK Voice Studio are listed:" in io.lines and len(rows) == 10 and "  And 2 more." in io.lines and rows[0].startswith("  v1.11")
    assert "11 releases are newer than this copy." in io.lines and io.lines[-1] == "To fetch one into a new folder beside this copy, run: python3 -m voice_studio.update get v1.11"


def test_exactly_ten_releases_have_no_more_line(tmp_path):
    rig = UpdateRig(tmp_path, releases=tuple("v1.%d" % i for i in range(10)), here_at="v1.0")
    code, io = run(rig, "check", "--yes")
    assert len([l for l in io.lines if l.startswith("  v1.")]) == 10 and not any(l.startswith("  And") for l in io.lines)


def test_check_that_cannot_reach_the_place_says_so_in_three_parts_and_changes_nothing(rig):
    rig.offline = True
    before = rig.tree(rig.here)
    code, io = run(rig, "check", "--yes")
    assert code == 1 and io.lines[-4:] == ["The place the releases are kept could not be asked, or it did not give the release.", "Nothing was changed here, and no half-made folder was kept.",
                                           "Check the internet connection, then run the command again.", "  Technical detail: fatal: unable to access: Could not resolve host"]
    assert rig.tree(rig.here) == before


def test_the_commands_shown_use_the_host_in_the_address(rig):
    code, io = run(rig, "check", answers=["no"])
    assert "This asks %s for the list" % rig.source.host in " ".join(io.lines) and rig.source.host == rig.url


# ---------------------------------------------------------------- get: before it contacts anything

def test_get_says_where_the_copy_will_go_both_commands_and_what_is_not_touched_before_it_asks(rig):
    dest = str(rig.tmp / "ack-tools-v1.1")
    code, io = run(rig, "get", "v1.1", answers=["no"])
    assert code == 2 and rig.calls == [] and not os.path.lexists(dest) and io.prompts == ["Download the release v1.1 now? Type yes to go on. "] and "Nothing was done." in io.lines
    ask = io.events.index(("ask", io.prompts[0]))
    said = [t for kind, t in io.events[:ask] if kind == "say"]
    assert said[:3] == ["ACK Voice Studio: update", "This copy is version 1.0.0, in %s." % rig.here, "It contacts the internet to ask which releases of ACK Voice Studio exist, and to fetch one when you choose."]
    assert "Like any request on the internet it carries this computer's address and the name of the program asking. Nothing you recorded, typed or made is sent, and nothing is saved." in said
    assert "This downloads the release v1.1 of ACK Voice Studio from %s into a new folder: %s" % (rig.source.host, dest) in said
    assert "  First it looks the release up: git ls-remote --tags %s" % rig.url in said
    assert "  Then it fetches it: git clone --depth 1 --branch v1.1 %s %s" % (rig.url, dest) in said
    assert "This copy, and your projects, recordings and backups, are not touched." in said
    assert "A copy is usually under 100 MB. %s must be free beside this one, and %s is." % (size_text(up.ROOM_BYTES), size_text(10 ** 12)) in said


def test_get_says_the_room_needed_when_the_free_room_cannot_be_read(rig):
    rig.system.disk_free = lambda path: None
    code, io = run(rig, "get", "v1.1", answers=["no"])
    assert "A copy is usually under 100 MB. %s must be free beside this one." % size_text(up.ROOM_BYTES) in io.lines


def test_get_with_nobody_to_ask_contacts_nothing(rig):
    code, io = run(rig, "get", "v1.1", interactive=False)
    assert code == 2 and rig.calls == [] and io.prompts == [] and not os.path.lexists(str(rig.tmp / "ack-tools-v1.1"))


def test_get_without_a_release_says_how_to_name_one(rig):
    code, io = run(rig, "get")
    assert code == 2 and rig.calls == [] and io.lines[-1] == "Say which release to fetch, for example: python3 -m voice_studio.update get v1.0. Nothing was done."


def test_get_with_a_name_that_is_not_safe_is_refused_before_anything_else(rig):
    for name in ("a;b", "x" * 65, "a/b", "ünï"):
        code, io = run(rig, "get", name, "--yes")
        assert code == 2 and rig.calls == [] and "A release name is made of letters, numbers, dots, dashes and underscores only." in io.lines, name
        assert "  Technical detail: " + name[:64] in io.lines
    code, io = run(rig, "get", "-x", "--yes")
    assert code == 2 and rig.calls == [] and io.lines[-1] == "I do not know the option -x. Nothing was done."


def test_get_without_git_contacts_nothing(rig):
    rig.system.git_present = False
    code, io = run(rig, "get", "v1.1", "--yes")
    assert code == 2 and rig.calls == [] and "Nothing was contacted and nothing was changed." in io.lines


def test_get_into_a_place_that_is_taken_leaves_it_alone_and_asks_nothing(rig):
    taken = rig.tmp / "ack-tools-v1.1"
    taken.mkdir()
    (taken / "mine.txt").write_text("mine")
    code, io = run(rig, "get", "v1.1", "--yes")
    assert code == 2 and rig.calls == [] and io.prompts == [] and (taken / "mine.txt").read_text() == "mine"
    assert io.lines[-4:] == ["Something is already at the folder the copy would go to.", "Nothing was downloaded, and what is there was left as it is.", "Choose another folder with --to, or remove that one yourself.",
                             "  Technical detail: %s" % taken]


def test_get_without_room_says_so_and_contacts_nothing(rig):
    rig.system.free = (10 ** 13, up.ROOM_BYTES - 1)
    code, io = run(rig, "get", "v1.1", "--yes")
    assert code == 2 and rig.calls == [] and "There is not enough room beside this copy." in io.lines and not os.path.lexists(str(rig.tmp / "ack-tools-v1.1"))


def test_get_asks_the_room_of_the_folder_the_copy_would_be_made_in(rig):
    asked = []
    rig.system.disk_free = lambda path: asked.append(path) or (10 ** 13, 10 ** 12)
    run(rig, "get", "v1.1", answers=["no"])
    assert asked == [str(rig.tmp)]


def test_get_to_a_folder_of_your_own_goes_there(rig):
    dest = str(rig.tmp / "somewhere" / "new copy")
    os.makedirs(rig.tmp / "somewhere")
    code, io = run(rig, "get", "v1.1", "--to", dest, "--yes")
    assert code == 0 and os.path.isdir(dest + "/tools/voice_studio") and "into a new folder: %s" % dest in " ".join(io.lines)
    assert "PYTHONPATH=%s" % shlex.quote(dest + "/tools") in " ".join(io.lines)


def test_get_to_a_folder_that_is_not_a_whole_path_is_refused(rig):
    code, io = run(rig, "get", "v1.1", "--to", "new-copy", "--yes")
    assert code == 2 and rig.calls == [] and io.lines[-1] == "Give the whole path after --to, starting with a slash. Nothing was done."


def test_a_folder_given_with_a_tilde_is_the_home_folder(rig, monkeypatch):
    monkeypatch.setenv("HOME", str(rig.tmp))
    code, io = run(rig, "get", "v1.1", "--to", "~/from-home", "--yes")
    assert code == 0 and os.path.isdir(str(rig.tmp / "from-home" / "tools"))


# ---------------------------------------------------------------- get: after a yes

def test_get_fetches_checks_compares_and_gives_the_commands_it_does_not_run(rig):
    dest = str(rig.tmp / "ack-tools-v1.1")
    before = rig.tree(rig.here)
    code, io = run(rig, "get", "v1.1", answers=["yes"])
    assert code == 0 and rig.tree(rig.here) == before, "this copy is not touched"
    assert [argv[:2] for argv, ids in rig.calls] == [["git", "ls-remote"], ["git", "clone"]] and rig.calls[0][1] == [up.LIST_ID] and rig.calls[1][1] == [up.GET_ID]
    assert up.head_commit(dest) == rig.commits["v1.1"]
    assert "Fetched the release v1.1 (commit %s) into %s. It is version 1.1.0." % (rig.commits["v1.1"][:10], dest) in io.lines
    assert "It was checked: it holds the commit the release was listed with, and it is a copy of this tool." in io.lines
    assert io.lines.index("Compared with this copy:") > io.lines.index("It was checked: it holds the commit the release was listed with, and it is a copy of this tool.")
    assert "  The lists of programs: 1 changed, 0 new, 0 removed." in io.lines and "    tools/voice_studio/data/locks/studio.lock.txt" in io.lines
    assert "  The tool's own program files: 1 changed, 1 new, 0 removed." in io.lines and "  The words on screen: 1 changed, 0 new, 0 removed." in io.lines
    assert "Some programs will be built again the next time you set up. The guided setup shows what, beside the ones you have now, and asks first." in io.lines
    assert io.lines[-4] == "To try it, run: PYTHONPATH=%s python3 -m voice_studio" % shlex.quote(dest + "/tools")
    assert io.lines[-3] == "  The guided setup shows what it will build, beside the programs you have now, and asks first."
    here = str(rig.here)
    assert io.lines[-2] == "To use it under the usual name once you are happy with it, run: mv %s %s && mv %s %s" % (shlex.quote(here), shlex.quote(here + ".old"), shlex.quote(dest), shlex.quote(here))
    assert io.lines[-1] == "  Neither command touches ack-voice-studio, where your projects, recordings and backups are."


def test_get_says_when_the_programs_lists_and_the_download_list_did_not_change(tmp_path):
    rig = UpdateRig(tmp_path, releases=("v1.0", "v1.1"), here_at="v1.0")
    from vs_update_helpers import git
    git("checkout", "-q", "v1.0", cwd=rig.repo)
    (rig.repo / "tools/voice_studio/core/q.py").write_text("q\n")
    git("add", "-A", cwd=rig.repo)
    git("commit", "-q", "-m", "only code", cwd=rig.repo)
    git("tag", "v1.0.1", cwd=rig.repo)
    rig.commits["v1.0.1"] = git("rev-parse", "v1.0.1", cwd=rig.repo)
    code, io = run(rig, "get", "v1.0.1", "--yes")
    assert code == 0 and "  The tool's own program files: 0 changed, 1 new, 0 removed." in io.lines
    assert not any(l.startswith("Some programs will be built again") for l in io.lines) and not any("list of what can be downloaded" in l for l in io.lines)
    assert not any("The lists of programs" in l for l in io.lines)


def test_get_says_when_the_download_list_changed(tmp_path):
    rig = UpdateRig(tmp_path, releases=("v1.0",), here_at="v1.0")
    from vs_update_helpers import git
    (rig.repo / "tools/voice_studio/data/sources.json").write_text('{"items": [1]}\n')
    git("add", "-A", cwd=rig.repo)
    git("commit", "-q", "-m", "new download", cwd=rig.repo)
    git("tag", "v1.2", cwd=rig.repo)
    rig.commits["v1.2"] = git("rev-parse", "v1.2", cwd=rig.repo)
    code, io = run(rig, "get", "v1.2", "--yes")
    assert "  What can be downloaded: 1 changed, 0 new, 0 removed." in io.lines and "    tools/voice_studio/data/sources.json" in io.lines
    assert "The list of what can be downloaded changed, so anything new is asked about again." in io.lines
    assert not any(l.startswith("Some programs will be built again") for l in io.lines)


def test_only_ten_names_of_changed_lists_are_shown(tmp_path):
    rig = UpdateRig(tmp_path, releases=("v1.0",), here_at="v1.0")
    from vs_update_helpers import git
    for i in range(13):
        (rig.repo / ("tools/voice_studio/data/locks/extra%02d.lock.txt" % i)).write_text("x\n")
    git("add", "-A", cwd=rig.repo)
    git("commit", "-q", "-m", "many lists", cwd=rig.repo)
    git("tag", "v1.2", cwd=rig.repo)
    rig.commits["v1.2"] = git("rev-parse", "v1.2", cwd=rig.repo)
    code, io = run(rig, "get", "v1.2", "--yes")
    assert "  The lists of programs: 0 changed, 13 new, 0 removed." in io.lines and len([l for l in io.lines if l.startswith("    tools/voice_studio/data/locks/")]) == 10


def test_a_release_with_no_other_difference_says_nothing_differs(tmp_path):
    rig = UpdateRig(tmp_path, releases=("v1.0",), here_at="v1.0")
    from vs_update_helpers import git
    (rig.repo / "docs").mkdir(exist_ok=True)
    (rig.repo / "docs" / "OTHER.md").write_text("changed but not compared\n")
    git("add", "-A", cwd=rig.repo)
    git("commit", "-q", "-m", "not compared", cwd=rig.repo)
    git("tag", "v1.0.0", cwd=rig.repo)
    rig.commits["v1.0.0"] = git("rev-parse", "v1.0.0", cwd=rig.repo)
    code, io = run(rig, "get", "v1.0.0", "--yes")
    assert code == 0 and "  Nothing differs in the files that were compared." in io.lines


def test_get_of_the_release_this_copy_already_is_fetches_nothing(rig):
    code, io = run(rig, "get", "v1.0", "--yes")
    assert code == 2 and [argv[:2] for argv, ids in rig.calls] == [["git", "ls-remote"]] and io.lines[-1] == "This copy is already the release v1.0. Nothing was fetched."
    assert not os.path.lexists(str(rig.tmp / "ack-tools-v1.0"))


def test_get_of_a_release_that_is_not_listed_says_so_and_fetches_nothing(rig):
    code, io = run(rig, "get", "v9.9", "--yes")
    assert code == 1 and [argv[:2] for argv, ids in rig.calls] == [["git", "ls-remote"]] and not os.path.lexists(str(rig.tmp / "ack-tools-v9.9"))
    assert io.lines[-4:] == ["That is not one of the releases that are listed.", "Nothing was downloaded.", "Run the check command to see the names.", "  Technical detail: v9.9"]


def test_get_that_cannot_reach_the_place_says_so_and_leaves_no_folder(rig):
    rig.offline = True
    code, io = run(rig, "get", "v1.1", "--yes")
    assert code == 1 and "Nothing was changed here, and no half-made folder was kept." in io.lines and not os.path.lexists(str(rig.tmp / "ack-tools-v1.1"))


def test_get_of_a_copy_that_is_not_the_release_listed_deletes_it_again_and_says_so(rig):
    def swap(argv):
        dest = argv[-1]
        from vs_update_helpers import git
        git("-C", dest, "checkout", "-q", "--detach", "HEAD")           # still a copy of the same release: make the commit differ below
        (Path(dest) / ".git" / "HEAD").write_text("0" * 40 + "\n")
    rig.after_clone = swap
    code, io = run(rig, "get", "v1.1", "--yes")
    assert code == 1 and not os.path.lexists(str(rig.tmp / "ack-tools-v1.1"))
    assert "The copy that came is not the release that was listed." in io.lines and "The folder it was put in was deleted again. Nothing else was touched." in io.lines


def test_ctrl_c_during_get_says_so_and_removes_the_half_made_folder(rig):
    dest = rig.tmp / "ack-tools-v1.1"
    calls = {"n": 0}
    real = rig.networked

    def interrupting(consent, argv, ids, **kw):
        calls["n"] += 1
        if argv[:2] == ["git", "clone"]:
            os.makedirs(dest / "half")
            raise KeyboardInterrupt
        return real(consent, argv, ids, **kw)
    rig.networked = interrupting
    code, io = run(rig, "get", "v1.1", "--yes")
    assert code == 1 and io.lines[-1] == "Stopped. A copy that was being fetched was removed again, and this copy was not touched." and not dest.exists() and rig.here.is_dir()


def test_ctrl_c_during_check_stops_cleanly(rig):
    def interrupting(consent, argv, ids, **kw):
        raise KeyboardInterrupt
    rig.networked = interrupting
    code, io = run(rig, "check", "--yes")
    assert code == 1 and io.lines[-1].startswith("Stopped.")


def test_the_agreement_is_for_this_run_only_and_names_what_it_covers(rig):
    seen = []
    real = rig.networked

    def watching(consent, argv, ids, **kw):
        seen.append((sorted(e.id for e in consent.entries), list(ids)))
        return real(consent, argv, ids, **kw)
    rig.networked = watching
    run(rig, "check", "--yes")
    run(rig, "get", "v1.1", "--yes")
    assert seen == [([up.LIST_ID], [up.LIST_ID]), ([up.GET_ID, up.LIST_ID], [up.LIST_ID]), ([up.GET_ID, up.LIST_ID], [up.GET_ID])]
    import inspect
    assert "home" not in inspect.signature(uf.run_update).parameters, "the front is given no place to save an agreement in"


def test_the_command_can_be_started_from_a_terminal(capsys):
    from voice_studio import update
    assert update.main(["help"]) == 0
    assert "ACK Voice Studio: update" in capsys.readouterr().out


# ---------------------------------------------------------------- the exact edges (each found by breaking the code on purpose and seeing nothing fail)

def test_check_from_a_copy_that_is_not_a_git_copy_lists_the_releases_and_cannot_call_any_newer(tmp_path):
    rig = UpdateRig(tmp_path, here_at=None)
    (rig.here / "tools" / "voice_studio").mkdir(parents=True)
    code, io = run(rig, "check", "--yes")
    assert code == 0 and "2 releases of ACK Voice Studio are listed:" in io.lines and "This copy is not at a release, so none can be called newer." in io.lines
    assert "  v1.1" in io.lines and "  v1.0" in io.lines and not any("it is at the commit" in l or l.startswith("It is the release") for l in io.lines)


def test_a_folder_given_with_dots_in_it_is_tidied_before_it_is_shown_and_used(rig):
    (rig.tmp / "a").mkdir()
    tidy = str(rig.tmp / "tidy")
    code, io = run(rig, "get", "v1.1", "--to", str(rig.tmp / "a" / ".." / "tidy"), "--yes")
    assert code == 0 and os.path.isdir(tidy + "/tools") and "into a new folder: %s" % tidy in " ".join(io.lines) and ".." not in " ".join(io.lines)


def test_a_release_with_no_version_line_is_fetched_and_the_sentence_has_no_version(tmp_path):
    rig = UpdateRig(tmp_path, releases=(), here_at=None)
    (rig.here / "tools" / "voice_studio").mkdir(parents=True)
    rig.release("v1.0", {**FIRST, "tools/voice_studio/__init__.py": "x = 1\n"})
    code, io = run(rig, "get", "v1.0", "--yes")
    assert code == 0 and "Fetched the release v1.0 (commit %s) into %s." % (rig.commits["v1.0"][:10], rig.tmp / "ack-tools-v1.0") in io.lines
    assert not any("It is version" in l for l in io.lines)


def test_the_commands_it_prints_quote_a_folder_name_with_a_space(tmp_path):
    base = tmp_path / "my folder"
    base.mkdir()
    rig = UpdateRig(base)
    code, io = run(rig, "get", "v1.1", "--yes")
    here, dest = str(rig.here), str(base / "ack-tools-v1.1")
    assert code == 0 and io.lines[-4] == "To try it, run: PYTHONPATH='%s/tools' python3 -m voice_studio" % dest
    assert io.lines[-2] == "To use it under the usual name once you are happy with it, run: mv '%s' '%s.old' && mv '%s' '%s'" % (here, here, dest, here)


def changes_of(**kinds):
    empty = {c: () for c in up.CATEGORIES}
    return up.Changes(*({**empty, **kinds.get(kind, {})} for kind in ("changed", "added", "removed")))


def said_about(changes):
    io = TermIO((), True)
    uf._say_changes(changes, CAT, io)
    return io.lines


def test_the_comparison_counts_changed_new_and_gone_alike_and_names_the_files_of_the_lists_only():
    lines = said_about(changes_of(changed={"code": ("c.py",)}, added={"programs": ("p-new.lock",)}, removed={"downloads": ("d-gone.json",), "programs": ("p-gone.lock",)}))
    assert lines == ["Compared with this copy:", "  The lists of programs: 0 changed, 1 new, 1 removed.", "    p-new.lock", "    p-gone.lock", "  What can be downloaded: 0 changed, 0 new, 1 removed.",
                     "    d-gone.json", "  The tool's own program files: 1 changed, 0 new, 0 removed.",
                     "Some programs will be built again the next time you set up. The guided setup shows what, beside the ones you have now, and asks first.",
                     "The list of what can be downloaded changed, so anything new is asked about again."]


@pytest.mark.parametrize("kind", ["changed", "added", "removed"])
@pytest.mark.parametrize("part, sentence", [("programs", "Some programs will be built again the next time you set up. The guided setup shows what, beside the ones you have now, and asks first."),
                                            ("downloads", "The list of what can be downloaded changed, so anything new is asked about again.")])
def test_the_sentence_about_programs_and_downloads_follows_any_kind_of_difference(kind, part, sentence):
    lines = said_about(changes_of(**{kind: {part: ("a-file",)}}))
    assert sentence in lines and "    a-file" in lines
    assert not said_about(changes_of(**{kind: {"code": ("a-file",)}})).count(sentence)


# ---------------------------------------------------------------- the phone app's tags are not releases of the tool

PREFIX = "voice-studio-"


@pytest.fixture
def mixed(tmp_path):
    return UpdateRig(tmp_path, releases=("v0.1.0", "v0.2.0"), here_at="v0.1.0", tag_prefix=PREFIX, app_tags=("v1.0-beta.1", "v1.0-beta.2", "v1.0-beta.7"))


def test_check_lists_only_the_tools_releases_and_never_the_phone_apps(mixed):
    code, io = run(mixed, "check", "--yes")
    assert code == 0 and "2 releases of ACK Voice Studio are listed:" in io.lines and "  v0.2.0: newer than this copy" in io.lines and "  v0.1.0: this copy" in io.lines
    assert not any("beta" in line for line in io.lines)
    assert io.lines[-1] == "To fetch one into a new folder beside this copy, run: python3 -m voice_studio.update get v0.2.0"


def test_check_says_which_tags_count_before_it_asks_and_not_when_there_is_no_prefix(mixed, tmp_path):
    code, io = run(mixed, "check", answers=["no"])
    ask = io.events.index(("ask", io.prompts[0]))
    said = [t for kind, t in io.events[:ask] if kind == "say"]
    assert "Only tags whose names begin with %s are releases of this tool. ACK's repository also holds the phone app's tags, and those are left out." % PREFIX in said
    (tmp_path / "plain").mkdir()
    plain = UpdateRig(tmp_path / "plain")
    code, io = run(plain, "check", answers=["no"])
    assert not any("Only tags whose names begin with" in line for line in io.lines)


def test_a_repository_with_only_the_apps_tags_has_no_releases_of_the_tool(tmp_path):
    rig = UpdateRig(tmp_path, releases=(), here_at=None, tag_prefix=PREFIX, app_tags=("v1.0-beta.1", "v1.0-beta.7"))
    (rig.here / "tools" / "voice_studio").mkdir(parents=True)
    code, io = run(rig, "check", "--yes")
    assert code == 0 and io.lines[-1] == "ACK Voice Studio has no named releases yet, so there is nothing to fetch." and not any("listed" in line for line in io.lines)


def test_get_shows_the_whole_tag_in_the_commands_and_fetches_it_into_a_folder_named_for_the_short_name(mixed):
    dest = str(mixed.tmp / "ack-tools-v0.2.0")
    code, io = run(mixed, "get", "v0.2.0", answers=["no"])
    ask = io.events.index(("ask", io.prompts[0]))
    said = [t for kind, t in io.events[:ask] if kind == "say"]
    assert "  Then it fetches it: git clone --depth 1 --branch %sv0.2.0 %s %s" % (PREFIX, mixed.url, dest) in said and "This downloads the release v0.2.0 of ACK Voice Studio from %s into a new folder: %s" % (mixed.source.host, dest) in said
    code, io = run(mixed, "get", "v0.2.0", "--yes")
    assert code == 0 and up.head_commit(dest) == mixed.commits["v0.2.0"] and [argv for argv, ids in mixed.calls if argv[1] == "clone"] == [["git", "clone", "--depth", "1", "--branch", PREFIX + "v0.2.0", mixed.url, dest]]
    assert "Fetched the release v0.2.0 (commit %s) into %s. It is version 1.1.0." % (mixed.commits["v0.2.0"][:10], dest) in io.lines


def test_naming_a_phone_app_tag_is_an_unknown_release_and_fetches_nothing(mixed):
    code, io = run(mixed, "get", "v1.0-beta.7", "--yes")
    assert code == 1 and [argv[:2] for argv, ids in mixed.calls] == [["git", "ls-remote"]] and not os.path.lexists(str(mixed.tmp / "ack-tools-v1.0-beta.7"))
    assert io.lines[-4] == "That is not one of the releases that are listed."
    code, io = run(mixed, "get", PREFIX + "v0.2.0", "--yes")
    assert code == 1 and io.lines[-4] == "That is not one of the releases that are listed.", "the whole tag is not a name the tool knows; the name is shown without the prefix"


def test_the_copy_that_is_already_the_release_is_recognised_with_a_prefix(mixed):
    code, io = run(mixed, "get", "v0.1.0", "--yes")
    assert code == 2 and io.lines[-1] == "This copy is already the release v0.1.0. Nothing was fetched."
