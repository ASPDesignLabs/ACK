# SPDX-License-Identifier: GPL-3.0-or-later
"""The terminal front for uninstalling the tool (plan task VS-6.3): what `show` lists, what `remove` shows and asks and does, and what it will not do. The flows are the real code on the
refresh tests' stand-in for the computer: a built set of programs, a listening model, a kept starting voice, a project and a backup to protect."""
import os
import shutil
from pathlib import Path

import pytest

from vs_refresh_helpers import CAT, VOICE_BYTES, RefreshRig, TermIO
from vs_rounds_helpers import fake_job
from vs_startvoice_helpers import implies_permission, leaked_keys
from voice_studio.core import uninstall as un, uninstall_flow as uf
from voice_studio.core.guided_flow import window_text
from voice_studio.core.project import create_project
from voice_studio.core.text import size_text

TOOLS = "/home/user/ack-tools/tools"


@pytest.fixture
def rig(tmp_path):
    return RefreshRig(tmp_path)


def run(rig, *argv, answers=(), interactive=True, tools_dir=TOOLS, remove_tree=None):
    io = TermIO(answers, interactive)
    code = uf.run_uninstall(list(argv), rig.home, CAT, io, specs=[rig.spec], tools_dir=tools_dir, remove_tree=remove_tree)
    assert leaked_keys(io.text + "\n".join(io.prompts)) == [], "a catalog key was printed instead of words"
    assert implies_permission(io.text) == [], "something printed says or implies that use is permitted"
    return code, io


def tree(root):
    found = {}
    for path in sorted(Path(root).rglob("*")):
        if path.is_file() and not path.is_symlink():
            found[str(path.relative_to(root))] = (path.read_bytes(), path.stat().st_mtime_ns)
    return found


def keep_things(rig):
    create_project(rig.home.projects, "Anna", "own")
    recording = Path(rig.home.projects, "anna", "recordings")
    recording.mkdir(parents=True, exist_ok=True)
    (recording / "take.wav").write_bytes(b"RIFF" + b"1" * 50)
    Path(rig.home.backups).mkdir(parents=True, exist_ok=True)
    (Path(rig.home.backups) / "anna.tar").write_bytes(b"backup bytes")


WINDOW = window_text(TOOLS, "--remove-launcher")
MENU = "The entry in your applications list or Start menu, if you made one, is taken away by its own command: " + WINDOW
CODE = "This tool's own files are in /home/user/ack-tools. This program cannot remove the files it is running from. To remove them, run: rm -r /home/user/ack-tools"


# ---------------------------------------------------------------- help and the command line

def test_no_command_and_help_list_the_two_commands_and_what_is_never_touched(rig):
    for argv in ((), ("help",), ("--help",), ("-h",)):
        code, io = run(rig, *argv)
        assert code == 0 and io.prompts == []
        assert io.lines[0] == "ACK Voice Studio: uninstall" and "Commands:" in io.lines
        for part in ("show:", "remove [--yes]:", "No project, recording, round, finished voice, backup or starting voice is ever touched."):
            assert part in io.text, part


def test_an_unknown_command_is_named_and_nothing_is_done(rig):
    before = tree(rig.home.root)
    code, io = run(rig, "wipe")
    assert code == 2 and "wipe" in io.text and tree(rig.home.root) == before


def test_the_options_each_command_publishes_are_the_options_it_accepts(rig):
    assert uf.OPTIONS == {"show": frozenset(), "remove": frozenset({"--yes", "-y"})} and uf.COMMANDS == ("show", "remove", "help")
    for command, options in uf.OPTIONS.items():
        code, io = run(rig, command, "--nonsense")
        assert code == 2 and "--nonsense" in io.text and io.prompts == [], command
        code, io = run(rig, command, "extra")
        assert code == 2 and io.prompts == [], command
    assert run(rig, "show", "--yes")[0] == 2, "show takes no option"


def test_every_usage_line_has_words():
    for key in uf.USAGE:
        assert CAT.has(key)


# ---------------------------------------------------------------- show

def test_show_lists_what_would_go_what_is_kept_and_the_two_things_it_cannot_do_for_itself(rig):
    keep_things(rig)
    before = tree(rig.home.root)
    code, io = run(rig, "show")
    assert code == 0 and io.prompts == [] and tree(rig.home.root) == before
    plan = un.plan(rig.home, [rig.spec])
    assert io.lines[:3] == ["ACK Voice Studio: uninstall", "No project, recording, round, finished voice or backup is touched.", "An uninstall would remove these programs and downloaded files:"]
    assert "  Programs: %s, %s" % (rig.env.env_dir, size_text(plan.pieces[0].bytes)) in io.lines
    assert "  Downloaded file: %s/models, %s" % (rig.home.downloads, size_text(plan.pieces[1].bytes)) in io.lines
    assert "Together they take %s." % size_text(plan.total_bytes) in io.lines
    assert io.lines[io.lines.index("These are kept:") + 1:io.lines.index("These are kept:") + 5] == [
        "  Your 1 project, with everything in it, in %s." % rig.home.projects, "  Your backups, in %s." % rig.home.backups,
        "  The starting voices you chose, in %s. They may not be possible to download again." % rig.home.voices,
        "  The tool's small notes, such as what you agreed to and the window's choices, in %s." % rig.home.state]
    assert MENU in io.lines and CODE in io.lines
    assert io.lines[-1] == "To remove the programs and downloaded files, run: python3 -m voice_studio.uninstall remove"


def test_what_is_kept_is_named_with_no_project_and_the_projects_are_named_with_nothing_else_kept(rig):
    code, io = run(rig, "show")
    assert "These are kept:" in io.lines and not any(l.startswith("  Your") and "project" in l for l in io.lines)
    assert "  The tool's small notes, such as what you agreed to and the window's choices, in %s." % rig.home.state in io.lines
    create_project(rig.home.projects, "Anna", "own")
    for folder in (rig.home.state, rig.home.voices):
        shutil.rmtree(folder)
    code, io = run(rig, "show")
    assert io.lines[io.lines.index("These are kept:") + 1] == "  Your 1 project, with everything in it, in %s." % rig.home.projects
    assert not [l for l in io.lines if l.startswith("  The ")]


def test_show_says_how_many_projects_are_kept_in_words_that_agree(rig):
    assert not any("project" in l for l in run(rig, "show")[1].lines if l.startswith("  Your"))
    create_project(rig.home.projects, "Anna", "own")
    create_project(rig.home.projects, "Ben", "own")
    assert "  Your 2 projects, with everything in them, in %s." % rig.home.projects in run(rig, "show")[1].lines


def test_show_with_nothing_to_remove_says_so_and_gives_no_remove_command(tmp_path):
    rig = RefreshRig(tmp_path, built=False, speech=False, voice=False)
    code, io = run(rig, "show")
    assert code == 0 and "No programs or downloaded files of the tool are on the disk, so there is nothing to remove." in io.lines
    assert not any("uninstall remove" in l for l in io.lines) and MENU in io.lines and CODE in io.lines
    assert "An uninstall would remove these programs and downloaded files:" not in io.lines


def test_show_names_what_it_leaves_alone_in_words_that_agree(rig):
    Path(rig.home.environments, "somebody-elses").mkdir()
    assert "1 other item in the tool's folders was left alone, because this tool did not make it or is still building it." in run(rig, "show")[1].lines
    Path(rig.home.environments, "another").mkdir()
    assert "2 other items in the tool's folders were left alone, because this tool did not make them or is still building them." in run(rig, "show")[1].lines


def test_show_says_nothing_about_left_alone_when_there_is_nothing(rig):
    assert "left alone" not in run(rig, "show")[1].text


def test_only_ten_rows_are_listed_and_the_rest_are_counted():
    def plan_of(count):
        pieces = tuple(un.Piece("downloads", "/d/%02d" % i, 100 + i, 1) for i in range(count))
        return un.Plan(pieces, 0, 0, (), "", "x")
    from vs_refresh_helpers import TermIO as T
    from voice_studio.core.paths import DataHome
    home = DataHome("/h")
    io = T()
    uf._say_plan(plan_of(10), home, CAT, io, TOOLS)
    assert len([l for l in io.lines if l.startswith("  Downloaded file: /d/")]) == 10 and not any(l.startswith("  And") for l in io.lines)
    io = T()
    uf._say_plan(plan_of(11), home, CAT, io, TOOLS)
    assert len([l for l in io.lines if l.startswith("  Downloaded file: /d/")]) == 10 and "  And 1 more." in io.lines
    io = T()
    uf._say_plan(plan_of(14), home, CAT, io, TOOLS)
    assert "  And 4 more." in io.lines and "Together they take %s." % size_text(sum(100 + i for i in range(14))) in io.lines


def test_the_menu_entry_is_taken_away_by_the_windows_own_command_with_the_tools_folder_on_the_path():
    assert WINDOW.startswith("PYTHONPATH=%s " % TOOLS) and WINDOW.endswith(" -m voice_studio.window --remove-launcher")


def test_the_folder_of_the_tools_own_files_is_the_one_above_tools_unless_it_is_laid_out_differently():
    assert uf.code_folder("/home/u/ack-tools/tools") == "/home/u/ack-tools" and uf.code_folder("/home/u/ack-tools/tools/") == "/home/u/ack-tools"
    assert uf.code_folder("/opt/voice") == "/opt/voice" and uf.code_folder("/tools") == "/tools" and uf.code_folder("tools") == "tools"


def test_the_command_to_remove_the_tools_own_files_quotes_a_folder_with_a_space(rig):
    code, io = run(rig, "show", tools_dir="/home/my user/ack tools/tools")
    assert "To remove them, run: rm -r '/home/my user/ack tools'" in " ".join(io.lines)


# ---------------------------------------------------------------- remove

def test_remove_shows_the_same_list_and_asks_once_and_a_no_removes_nothing(rig):
    keep_things(rig)
    before = tree(rig.home.root)
    code, io = run(rig, "remove", answers=["no"])
    plan = un.plan(rig.home, [rig.spec])
    assert code == 2 and "Nothing was done." in io.lines and tree(rig.home.root) == before
    assert io.prompts == ["Remove these programs and downloaded files, about %s, now? Setting them up again means downloading them again. Type yes to delete them. " % size_text(plan.total_bytes)]
    assert "An uninstall would remove these programs and downloaded files:" in io.lines and MENU in io.lines and not any("uninstall remove" in l for l in io.lines)


def test_a_yes_removes_the_programs_and_downloads_and_nothing_of_the_persons(rig):
    keep_things(rig)
    protected = {n: tree(f) for n, f in (("projects", rig.home.projects), ("backups", rig.home.backups), ("state", rig.home.state), ("voices", rig.home.voices))}
    size = size_text(un.plan(rig.home, [rig.spec]).total_bytes)
    code, io = run(rig, "remove", answers=["yes"])
    assert code == 0 and not os.path.exists(rig.env.env_dir) and not os.path.exists(rig.home.environments) and not os.path.exists(rig.home.downloads + "/models")
    assert {n: tree(f) for n, f in (("projects", rig.home.projects), ("backups", rig.home.backups), ("state", rig.home.state), ("voices", rig.home.voices))} == protected
    assert rig.voice_path().read_bytes() == VOICE_BYTES
    assert io.lines[-2:] == ["Done. The programs and downloaded files were removed. About %s is free again. Nothing of yours was touched." % size,
                             "To set the tool up again later, run: python3 -m voice_studio"]
    code, again = run(rig, "show")
    assert "nothing to remove" in again.text


def test_dash_dash_yes_answers_the_question_and_dash_y_too(rig):
    code, io = run(rig, "remove", "--yes")
    assert code == 0 and io.prompts == [] and not os.path.exists(rig.env.env_dir)
    other = RefreshRig(rig.home.root and Path(rig.home.root).parent.parent / "second")
    code, io = run(other, "remove", "-y")
    assert code == 0 and io.prompts == [] and not os.path.exists(other.env.env_dir)


def test_with_nobody_to_ask_nothing_is_removed(rig):
    before = tree(rig.home.root)
    code, io = run(rig, "remove", interactive=False)
    assert code == 2 and io.prompts == [] and "There was nobody to ask. To say yes on the command line, add --yes. Nothing was done." in io.lines and tree(rig.home.root) == before


def test_remove_with_nothing_to_remove_asks_nothing_and_succeeds(tmp_path):
    rig = RefreshRig(tmp_path, built=False, speech=False, voice=False)
    code, io = run(rig, "remove")
    assert code == 0 and io.prompts == [] and "nothing to remove" in io.text and not any(l.startswith("Done.") for l in io.lines)


def test_a_running_task_stops_it_before_it_asks_and_says_so_in_three_parts(rig):
    os.makedirs(rig.home.jobs, exist_ok=True)
    fake_job(rig.home.jobs, ["x"], "running", project="voice-check")
    before = tree(rig.home.root)
    code, io = run(rig, "remove", answers=["yes"])
    assert code == 1 and io.prompts == [] and tree(rig.home.root) == before
    assert io.lines[-3:] == ["A task is running, and it may be using the programs.", "Nothing was removed.", "Wait for the task to finish, or stop it, then try again."]


def test_a_task_that_starts_after_the_question_is_still_caught(rig, monkeypatch):
    real = un.plan
    seen = {"n": 0}

    def starting(home, specs):
        seen["n"] += 1
        found = real(home, specs)
        if seen["n"] == 2:
            os.makedirs(home.jobs, exist_ok=True)
            fake_job(home.jobs, ["x"], "running", project="voice-check")
            return real(home, specs)
        return found
    monkeypatch.setattr(un, "plan", starting)
    before = tree(rig.home.root)
    code, io = run(rig, "remove", "--yes")
    assert code == 1 and io.lines[-3] == "A task is running, and it may be using the programs." and os.path.isdir(rig.env.env_dir)
    assert {k: v for k, v in tree(rig.home.root).items() if "jobs" not in k} == before


def test_a_list_that_changed_after_it_was_shown_removes_nothing_and_says_so(rig, monkeypatch):
    real = un.plan
    seen = {"n": 0}

    def changing(home, specs):
        seen["n"] += 1
        if seen["n"] == 2:
            Path(home.downloads, "arrived.bin").write_bytes(b"new")
        return real(home, specs)
    monkeypatch.setattr(un, "plan", changing)
    code, io = run(rig, "remove", "--yes")
    assert code == 1 and os.path.isdir(rig.env.env_dir) and io.lines[-3:] == ["The programs and downloaded files are not the ones that were shown.", "Nothing was removed.",
                                                                            "Run the command again to see what is there now."]


def test_a_piece_that_could_not_be_removed_is_listed_and_the_command_fails_without_the_come_back_line(rig):
    refused = rig.env.env_dir
    plan = un.plan(rig.home, [rig.spec])
    freed = sum(p.bytes for p in plan.pieces if p.path != refused)

    def remove_tree(path, failed):
        if path == refused:
            failed.append((path, "Permission denied"))
            return
        shutil.rmtree(path)
    code, io = run(rig, "remove", "--yes", remove_tree=remove_tree)
    assert code == 1 and "These could not be removed:" in io.lines and "  %s: Permission denied" % refused in io.lines
    assert "Done. The programs and downloaded files were removed. About %s is free again. Nothing of yours was touched." % size_text(freed) in io.lines and freed != plan.total_bytes
    assert not any("set the tool up again" in l for l in io.lines) and os.path.isdir(refused)


def test_when_nothing_could_be_removed_there_is_no_done_line(rig):
    def remove_tree(path, failed):
        failed.append((path, "Read-only file system"))
    code, io = run(rig, "remove", "--yes", remove_tree=remove_tree)
    assert code == 1 and not any(l.startswith("Done.") for l in io.lines) and "These could not be removed:" in io.lines


def fails_on(prefixes):
    def remove_tree(path, failed):
        if os.path.basename(path).startswith(prefixes):
            failed.append((path, "Permission denied"))
            return
        shutil.rmtree(path) if os.path.isdir(path) and not os.path.islink(path) else os.unlink(path)
    return remove_tree


def test_only_ten_failures_are_listed_and_the_rest_are_counted_apart_from_the_rows_of_the_list(rig):
    for i in range(13):
        Path(rig.home.downloads, "f%02d" % i).write_text("x")                           # 15 pieces to list: 10 rows and "And 5 more."; 12 of them cannot be removed
    code, io = run(rig, "remove", "--yes", remove_tree=fails_on(tuple("f%02d" % i for i in range(12))))
    assert code == 1 and len([l for l in io.lines if l.endswith(": Permission denied")]) == 10
    assert io.lines.count("  And 5 more.") == 1 and io.lines.count("  And 2 more.") == 1


def test_exactly_ten_failures_have_no_more_line(rig):
    for i in range(8):
        Path(rig.home.downloads, "f%02d" % i).write_text("x")                           # 10 pieces: no "more" line in the list either
    code, io = run(rig, "remove", "--yes", remove_tree=fails_on(("f", "demo", "models")))
    assert len([l for l in io.lines if l.endswith(": Permission denied")]) == 10 and not any(l.startswith("  And") for l in io.lines)


def test_one_more_than_ten_failures_has_a_line_saying_one_more(rig):
    for i in range(9):
        Path(rig.home.downloads, "f%02d" % i).write_text("x")
    code, io = run(rig, "remove", "--yes", remove_tree=fails_on(("f", "demo", "models")))
    assert len([l for l in io.lines if l.endswith(": Permission denied")]) == 10 and io.lines.count("  And 1 more.") == 2, "once in the list of pieces and once in the list of failures"


def test_ctrl_c_stops_cleanly_says_so_and_is_not_a_success(rig, monkeypatch):
    def interrupt(*args, **kwargs):
        raise KeyboardInterrupt
    monkeypatch.setattr(un, "plan", interrupt)
    code, io = run(rig, "remove", "--yes")
    assert code == 1 and io.lines[-1] == "Stopped. What was removed stays removed, and the same command carries on."


def test_the_command_can_be_started_from_a_terminal(capsys):
    from voice_studio import uninstall
    assert uninstall.main(["help"]) == 0
    assert "ACK Voice Studio: uninstall" in capsys.readouterr().out
