# SPDX-License-Identifier: GPL-3.0-or-later
"""The window's plain support code (no GTK): showing a folder, the menu entry, and the command line that explains why a window cannot start."""
import os
from pathlib import Path

import pytest

from vs_fakes import FakeSystem
from vs_startvoice_helpers import Terminal, implies_permission, leaked_keys
from voice_studio.core import launcher, showfolder, text, windowcli as wc
from voice_studio.core.system import CommandResult

CAT = text.load_catalog("en")
PYTHON, TOOLS = "/usr/bin/python3", "/home/anna/ack-tools/tools"
ICON = '<?xml version="1.0"?><!-- ack-voice-studio-icon --><svg/>\n'


# ---------------------------------------------------------------- showing a folder

ODD_FOLDERS = ["relative/folder", "/home/anna/fol\nder", "/home/anna/fol\x00der"]


class FolderSystem(FakeSystem):
    def __init__(self, *, wsl=False, tools=(), windows_name="\\\\wsl.localhost\\Ubuntu\\home\\anna\\folder", version=None, wslpath_fails=False, **kw):
        kw.setdefault("dirs", ["/home/anna/folder"] + ODD_FOLDERS)                       # they all "exist": it is the rule on the words that must refuse the odd ones
        super().__init__(tools={t: "/usr/bin/" + t for t in tools}, **kw)
        self.files["/proc/version"] = version or ("Linux version 5.15.0-microsoft-standard-WSL2" if wsl else "Linux version 6.8.0-generic")
        self.windows_name, self.wslpath_fails = windows_name, wslpath_fails

    def run(self, argv, timeout=15.0, cwd=None, env=None):
        if argv[0] == "wslpath":
            if self.wslpath_fails:
                return CommandResult(1, "wslpath: some error text\n", "")
            return CommandResult(0, self.windows_name + "\n") if self.windows_name is not None else CommandResult(1, "", "no")
        return super().run(argv, timeout, cwd, env)


def test_on_wsl_the_folder_is_shown_in_windows_explorer_by_its_windows_name_and_a_linux_opener_is_the_second_try():
    system = FolderSystem(wsl=True, tools=("explorer.exe", "wslpath", "xdg-open"))
    assert showfolder.attempts("/home/anna/folder", system) == [("explorer.exe", "\\\\wsl.localhost\\Ubuntu\\home\\anna\\folder"), ("xdg-open", "/home/anna/folder")]


def test_off_wsl_only_the_linux_opener_is_tried_and_with_no_program_nothing_is():
    assert showfolder.attempts("/home/anna/folder", FolderSystem(tools=("explorer.exe", "wslpath", "xdg-open"))) == [("xdg-open", "/home/anna/folder")]
    assert showfolder.attempts("/home/anna/folder", FolderSystem(tools=())) == []
    assert showfolder.attempts("/home/anna/folder", FolderSystem(wsl=True, tools=("xdg-open",))) == [("xdg-open", "/home/anna/folder")]            # Windows interop is off: explorer is not there


def test_the_older_wsl_that_writes_microsoft_with_a_capital_is_still_wsl():
    system = FolderSystem(tools=("explorer.exe", "wslpath"), version="Linux version 4.4.0-19041-Microsoft (Microsoft@Microsoft.com)")
    assert [a[0] for a in showfolder.attempts("/home/anna/folder", system)] == ["explorer.exe"]


def test_explorer_is_not_tried_without_wslpath_and_a_failed_wslpath_is_not_believed():
    assert showfolder.attempts("/home/anna/folder", FolderSystem(wsl=True, tools=("explorer.exe", "xdg-open"))) == [("xdg-open", "/home/anna/folder")]
    assert showfolder.attempts("/home/anna/folder", FolderSystem(wsl=True, tools=("explorer.exe", "wslpath"), wslpath_fails=True)) == []


def test_a_windows_name_that_cannot_be_worked_out_is_not_guessed():
    for name in (None, "", "two\nlines"):
        assert showfolder.attempts("/home/anna/folder", FolderSystem(wsl=True, tools=("explorer.exe", "wslpath"), windows_name=name)) == []


@pytest.mark.parametrize("path", ODD_FOLDERS + ["/home/anna/missing", ""])
def test_nothing_odd_or_missing_is_ever_handed_to_a_program(path):
    assert showfolder.attempts(path, FolderSystem(wsl=True, tools=("explorer.exe", "wslpath", "xdg-open"))) == []


def test_the_first_program_that_starts_wins_and_one_that_cannot_start_is_skipped():
    system = FolderSystem(wsl=True, tools=("explorer.exe", "wslpath", "xdg-open"))
    assert showfolder.open_folder("/home/anna/folder", system) is True and system.started == [("explorer.exe", "\\\\wsl.localhost\\Ubuntu\\home\\anna\\folder")]
    system = FolderSystem(wsl=True, tools=("explorer.exe", "wslpath", "xdg-open"))
    system.cannot_start = {"explorer.exe"}
    assert showfolder.open_folder("/home/anna/folder", system) is True and system.started == [("xdg-open", "/home/anna/folder")]


def test_with_nothing_that_starts_the_answer_is_no_and_the_window_says_the_path_instead():
    system = FolderSystem(tools=("xdg-open",))
    system.cannot_start = {"xdg-open"}
    assert showfolder.open_folder("/home/anna/folder", system) is False and system.started == []
    assert showfolder.open_folder("/home/anna/folder", FolderSystem(tools=())) is False
    assert showfolder.open_folder("/home/anna/missing", FolderSystem(tools=("xdg-open",))) is False        # nothing is started for a folder that is not there


def test_the_real_system_starts_a_program_apart_and_says_when_it_cannot_and_refuses_a_network_one(tmp_path):
    import sys as _sys
    from voice_studio.core.system import NetworkBlocked, RealSystem
    marker = tmp_path / "started"
    assert RealSystem().start([_sys.executable, "-c", "open(%r, 'w').write('x')" % str(marker)]) is True
    import time
    for _ in range(100):
        if marker.exists():
            break
        time.sleep(0.05)
    assert marker.read_text() == "x"
    assert RealSystem().start(["/nonexistent/program"]) is False
    with pytest.raises(NetworkBlocked):
        RealSystem().start(["curl", "http://example.invalid"])


# ---------------------------------------------------------------- the menu entry

def plan(home, **kw):
    return launcher.plan_install(str(home), kw.get("python", PYTHON), kw.get("tools", TOOLS), "ACK Voice Studio", "Make a voice", ICON)


def test_the_entry_runs_this_python_with_the_tools_folder_and_has_the_marker_and_the_icon_name():
    entry = launcher.desktop_text(PYTHON, TOOLS, "ACK Voice Studio", "Make a voice")
    lines = entry.splitlines()
    assert lines[0] == "[Desktop Entry]" and "Type=Application" in lines and "Terminal=false" in lines
    assert "Exec=env PYTHONPATH=%s %s -m voice_studio.window" % (TOOLS, PYTHON) in lines
    assert "Icon=" + launcher.APP_ID in lines and "StartupWMClass=" + launcher.APP_ID in lines and launcher.MARKER in lines and entry.endswith("\n")


@pytest.mark.parametrize("python, tools", [("/usr/bin/python 3", TOOLS), (PYTHON, "/home/an na/tools"), (PYTHON, "/home/anna/tools;rm"), (PYTHON, "/home/anna/$HOME"), ("python3", TOOLS),
                                           (PYTHON, "/home/anna/\ntools"), (PYTHON, '/home/anna/"tools"'), (PYTHON, "/home/anna/%u")])
def test_a_path_with_a_space_or_a_symbol_is_refused_not_quoted(python, tools):
    with pytest.raises(launcher.LauncherError) as caught:
        launcher.desktop_text(python, tools, "N", "C")
    assert caught.value.code == "odd_path"


def test_a_name_with_a_line_break_cannot_start_a_new_line_of_the_entry():
    for words in (("a\nExec=evil", "c"), ("n", "c\rExec=evil")):
        with pytest.raises(launcher.LauncherError):
            launcher.desktop_text(PYTHON, TOOLS, *words)


def test_a_new_install_writes_two_files_in_the_persons_own_folders_and_nothing_else(tmp_path):
    p = plan(tmp_path)
    assert [t.state for t in p.targets] == ["new", "new"] and p.changes and not p.refused
    launcher.install(p)
    assert Path(launcher.desktop_path(str(tmp_path))).read_text() == p.entry.text and Path(launcher.icon_path(str(tmp_path))).read_text() == ICON
    assert launcher.desktop_path(str(tmp_path)).startswith(str(tmp_path) + "/.local/share/applications/") and launcher.icon_path(str(tmp_path)).startswith(str(tmp_path) + "/.local/share/icons/")
    assert sorted(str(f.relative_to(tmp_path)) for f in tmp_path.rglob("*") if f.is_file()) == [".local/share/applications/%s.desktop" % launcher.APP_ID,
                                                                                                ".local/share/icons/hicolor/scalable/apps/%s.svg" % launcher.APP_ID]
    assert [t.state for t in plan(tmp_path).targets] == ["same", "same"] and not plan(tmp_path).changes


def test_a_file_that_is_already_right_is_not_written_again(tmp_path):
    launcher.install(plan(tmp_path))
    stale = 1_000_000_000
    for path in (launcher.desktop_path(str(tmp_path)), launcher.icon_path(str(tmp_path))):
        os.utime(path, (stale, stale))
    again = plan(tmp_path)
    assert [t.state for t in again.targets] == ["same", "same"]
    launcher.install(again)
    assert all(os.stat(p).st_mtime == stale for p in (launcher.desktop_path(str(tmp_path)), launcher.icon_path(str(tmp_path))))
    assert not Path(launcher.desktop_path(str(tmp_path)) + ".previous").exists()


def test_an_icon_that_someone_else_made_is_not_ours_even_though_it_is_an_svg(tmp_path):
    path = Path(launcher.icon_path(str(tmp_path)))
    path.parent.mkdir(parents=True)
    path.write_text("<svg>someone else's</svg>")
    p = plan(tmp_path)
    assert p.icon.state == "foreign" and p.refused and launcher.plan_remove(str(tmp_path)).foreign == (str(path),)
    with pytest.raises(launcher.LauncherError):
        launcher.install(p)
    assert path.read_text() == "<svg>someone else's</svg>" and not Path(launcher.desktop_path(str(tmp_path))).exists()


def test_a_file_this_tool_made_is_updated_and_the_old_one_is_kept_beside_it(tmp_path):
    launcher.install(plan(tmp_path))
    newer = plan(tmp_path, tools="/home/anna/other/tools")
    assert [t.state for t in newer.targets] == ["update", "same"]
    old = Path(launcher.desktop_path(str(tmp_path))).read_text()
    launcher.install(newer)
    assert Path(launcher.desktop_path(str(tmp_path)) + ".previous").read_text() == old and "other/tools" in Path(launcher.desktop_path(str(tmp_path))).read_text()


def test_a_file_of_the_same_name_that_this_tool_did_not_make_is_never_touched(tmp_path):
    path = Path(launcher.desktop_path(str(tmp_path)))
    path.parent.mkdir(parents=True)
    path.write_text("[Desktop Entry]\nName=Mine\n")
    p = plan(tmp_path)
    assert p.entry.state == "foreign" and p.refused
    with pytest.raises(launcher.LauncherError) as caught:
        launcher.install(p)
    assert caught.value.code == "foreign_file" and path.read_text() == "[Desktop Entry]\nName=Mine\n" and not Path(launcher.icon_path(str(tmp_path))).exists()


def test_removing_takes_only_the_files_with_the_marker_and_leaves_the_previous_copies(tmp_path):
    launcher.install(plan(tmp_path))
    launcher.install(plan(tmp_path, tools="/home/anna/other/tools"))
    before = launcher.plan_remove(str(tmp_path))
    assert len(before.paths) == 2 and before.foreign == ()
    launcher.remove(before)
    assert not Path(launcher.desktop_path(str(tmp_path))).exists() and not Path(launcher.icon_path(str(tmp_path))).exists()
    assert Path(launcher.desktop_path(str(tmp_path)) + ".previous").exists()
    mine = Path(launcher.desktop_path(str(tmp_path)))
    mine.write_text("[Desktop Entry]\nName=Mine\n")
    after = launcher.plan_remove(str(tmp_path))
    assert after.paths == () and after.foreign == (str(mine),)
    launcher.remove(after)
    assert mine.exists()


def test_a_failed_write_says_so_and_leaves_no_half_written_file(tmp_path, monkeypatch):
    real = os.replace

    def broken(src, dst):
        raise OSError(28, "No space left on device")
    monkeypatch.setattr(os, "replace", broken)
    with pytest.raises(launcher.LauncherError) as caught:
        launcher.install(plan(tmp_path))
    assert caught.value.code == "write_failed" and "No space" in caught.value.detail
    monkeypatch.setattr(os, "replace", real)


# ---------------------------------------------------------------- the command line

def cli(tmp_path, *argv, toolkit=None, answers=(), interactive=True, started=None, tools=TOOLS, python=PYTHON):
    io = Terminal(answers, interactive)
    tk = toolkit or wc.Toolkit(True, version="4.6.9")
    code = wc.run_window_cli(list(argv), str(tmp_path), python, tools, ICON, CAT, io, toolkit=lambda: tk, start=lambda: (started.append(1) if started is not None else None) or 0,
                             selftest=lambda: 7)
    assert leaked_keys(io.text + "\n".join(io.prompts)) == [] and implies_permission(io.text) == []
    return code, io


def test_check_says_the_program_and_the_gtk_version_and_how_to_start(tmp_path):
    code, io = cli(tmp_path, "--check")
    assert code == 0 and io.lines == ["ACK Voice Studio: can the window start here?", "  The program running this check: /usr/bin/python3", "  GTK: 4.6.9",
                                      "Yes. Start the window with: /usr/bin/python3 -m voice_studio.window"]


@pytest.mark.parametrize("reason, said", [("no_gi", "This program cannot find the GTK bindings. Use the system one, or install them with: sudo apt install python3-gi gir1.2-gtk-4.0"),
                                          ("no_gtk4", "GTK 4 is not installed. Install it with: sudo apt install python3-gi gir1.2-gtk-4.0"),
                                          ("gtk_too_old", "GTK 4.2 is older than the window needs. It needs 4.6 or newer."),
                                          ("no_display", "There is no desktop to show a window on.")])
def test_every_reason_the_window_cannot_start_is_said_in_plain_words_with_the_way_to_fix_it(tmp_path, reason, said):
    for argv in (("--check",), ()):
        started = []
        code, io = cli(tmp_path, *argv, toolkit=wc.Toolkit(False, reason, "4.2"), started=started)
        assert code == 1 and started == [] and any(l.strip().startswith(said) for l in io.lines) and "The window cannot start here yet." in io.lines


def test_no_option_starts_the_window_only_when_gtk_can(tmp_path):
    started = []
    assert cli(tmp_path, started=started)[0] == 0 and started == [1]


def test_only_one_of_the_options_at_a_time_and_an_unknown_one_does_nothing(tmp_path):
    for argv in (("--check", "--install-launcher"), ("--install-launcher", "--remove-launcher"), ("--selftest", "--check")):
        code, io = cli(tmp_path, *argv)
        assert code == 2 and "Give only one of" in io.text and not (tmp_path / ".local").exists()
    code, io = cli(tmp_path, "--bogus")
    assert code == 2 and "--bogus" in io.text and "Nothing was done" in io.text


def test_selftest_is_handed_to_the_caller(tmp_path):
    assert cli(tmp_path, "--selftest")[0] == 7


def test_install_shows_exactly_what_it_will_write_before_it_asks_and_writes_nothing_on_a_no(tmp_path):
    code, io = cli(tmp_path, "--install-launcher", answers=["no"])
    assert code == 2 and not (tmp_path / ".local").exists() and "Nothing was done." in io.lines
    asked = next(i for i, e in enumerate(io.events) if e[0] == "ask")
    said = [e[1] for e in io.events[:asked] if e[0] == "say"]
    assert "This would write, in your own folders:" in said and "  a new file: " + launcher.desktop_path(str(tmp_path)) in said and "  a new file: " + launcher.icon_path(str(tmp_path)) in said
    assert "It changes nothing else and needs no administrator rights." in said and io.prompts == ["Write these files now? Type yes to write them. "]


@pytest.mark.parametrize("answers, interactive", [([], True), ([], False), ([""], True)])
def test_install_asks_first_and_nobody_to_ask_writes_nothing(tmp_path, answers, interactive):
    code, io = cli(tmp_path, "--install-launcher", answers=answers, interactive=interactive)
    assert code == 2 and not (tmp_path / ".local").exists()


def test_a_terminal_with_nobody_at_it_is_never_asked_even_if_answers_are_waiting(tmp_path):
    for flag in ("--install-launcher", "--remove-launcher"):
        code, io = cli(tmp_path, flag, answers=["yes", "yes"], interactive=False)
        assert code in (0, 2) and io.prompts == [] and not (tmp_path / ".local" / "share" / "applications" / (launcher.APP_ID + ".desktop")).exists()
    cli(tmp_path, "--install-launcher", "--yes")
    code, io = cli(tmp_path, "--remove-launcher", answers=["yes"], interactive=False)
    assert code == 2 and Path(launcher.desktop_path(str(tmp_path))).exists() and io.prompts == []


def test_install_with_yes_or_a_typed_yes_writes_and_a_second_run_changes_nothing(tmp_path):
    code, io = cli(tmp_path, "--install-launcher", answers=["yes"])
    assert code == 0 and Path(launcher.desktop_path(str(tmp_path))).exists() and "Done. The menu entry is in place." in io.lines
    assert any(l.startswith("On Windows with WSL it appears in the Start menu") for l in io.lines)
    code, io = cli(tmp_path, "--install-launcher", "--yes")
    assert code == 0 and "The menu entry is already in place and up to date. Nothing was changed." in io.lines and io.prompts == []


def test_install_refuses_a_file_it_did_not_make_and_says_which(tmp_path):
    path = Path(launcher.desktop_path(str(tmp_path)))
    path.parent.mkdir(parents=True)
    path.write_text("mine")
    code, io = cli(tmp_path, "--install-launcher", "--yes")
    assert code == 1 and "A file that this tool did not make is already at %s." % path in io.lines and "Nothing was written." in io.lines and path.read_text() == "mine"


def test_install_with_an_odd_folder_name_says_what_to_do_instead(tmp_path):
    code, io = cli(tmp_path, "--install-launcher", "--yes", tools="/home/an na/tools")
    assert code == 1 and "  A folder name has a space or a symbol that a menu entry cannot hold safely." in io.lines and "  Nothing was written." in io.lines and not (tmp_path / ".local").exists()


def test_remove_lists_what_it_will_remove_asks_and_leaves_what_it_did_not_make(tmp_path):
    cli(tmp_path, "--install-launcher", "--yes")
    code, io = cli(tmp_path, "--remove-launcher", answers=["no"])
    assert code == 2 and Path(launcher.desktop_path(str(tmp_path))).exists() and "This would remove these files that this tool made:" in io.lines
    code, io = cli(tmp_path, "--remove-launcher", answers=["yes"])
    assert code == 0 and not Path(launcher.desktop_path(str(tmp_path))).exists() and "Done. The menu entry is removed. Nothing else was changed." in io.lines
    code, io = cli(tmp_path, "--remove-launcher")
    assert code == 0 and "There is no menu entry made by this tool to remove." in io.lines


def test_remove_leaves_a_file_of_the_same_name_that_is_not_ours_and_says_so(tmp_path):
    path = Path(launcher.desktop_path(str(tmp_path)))
    path.parent.mkdir(parents=True)
    path.write_text("mine")
    code, io = cli(tmp_path, "--remove-launcher", "--yes")
    assert code == 0 and "Left alone, because this tool did not make it: %s" % path in io.lines and path.read_text() == "mine"


def test_the_options_the_checklist_may_use_are_the_options_that_exist():
    assert wc.OPTIONS == {"--check", "--install-launcher", "--remove-launcher", "--yes", "-y", "--selftest"}
