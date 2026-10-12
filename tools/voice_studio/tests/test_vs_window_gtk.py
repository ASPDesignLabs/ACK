# SPDX-License-Identifier: GPL-3.0-or-later
"""The GTK edge of the window. Two kinds of test: static ones that read the window's source and always run (the GTK 4.6 floor, P6, the data-sovereignty rules, the licence line), and one that
runs the real window under a virtual display and drives it (voice_studio/window/selftest.py) where a Python with GTK 4 and Xvfb exist. The second is skipped, not faked, where they do not.

Which GTK is used matters: the floor is Ubuntu 22.04's (GTK 4.6.9 with python3-gi 3.42), the developer's own computer. Set ACK_VS_GTK46_RUNNER to a command that runs a command inside a copy of
Ubuntu 22.04 (see the plan, VS-0.1 as built, for how the copy is made) and the tour runs there; the repository's `tools` folder must be visible in it at /mnt/tools and a writable folder at
/mnt/scratch (ACK_VS_GTK46_SCRATCH is that folder's path on this computer). Otherwise the system Python is used, whatever GTK 4 it has.
"""
import ast
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from vs_voicefile_helpers import ProjectRig, TOOLS

PKG = Path(__file__).resolve().parents[1]
WINDOW = sorted((PKG / "window").glob("*.py"))
RUNNER = os.environ.get("ACK_VS_GTK46_RUNNER", "")
SCRATCH = os.environ.get("ACK_VS_GTK46_SCRATCH", "")

# calls added to GTK after 4.6: using one would stop the window on the computer it is for (Ubuntu 22.04)
NEWER_THAN_4_6 = ("FileDialog", "AlertDialog", "ColorDialog", "FontDialog", "UriLauncher", "FileLauncher", "load_from_string", "Gtk.Accessible.announce", ".announce(",
                  "set_can_shrink", "set_limit_events", "get_accessible_label", "Gtk.Spinner", "Adw", "Gtk.Picture.set_content_fit", "set_content_fit", "TextureFromPaintable",
                  "Gtk.ColumnView.set_tab_behavior", "Gtk.Scale.set_", "StringFilter")
# network, a browser or anything that talks to another computer (plan section 3: nothing leaves the computer)
NETWORK = ("subprocess", "Soup", "NetworkMonitor", "GUPnP", "WebKit", "urllib", "http.client", "socket", "requests", "xdg-open http", "show_uri", "launch_default_for_uri", "AppInfo.launch")


def source(path):
    return path.read_text(encoding="utf-8")


def code_only(path):
    """The module's source without its comments and docstrings, so a rule can name a forbidden call in prose."""
    tree = ast.parse(source(path))
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)) and node.body and isinstance(node.body[0], ast.Expr) \
                and isinstance(getattr(node.body[0], "value", None), ast.Constant) and isinstance(node.body[0].value.value, str):
            node.body[0].value.value = ""
    return ast.unparse(tree)


def test_there_are_window_files_and_each_has_the_licence_line():
    assert len(WINDOW) >= 12
    for path in WINDOW:
        assert source(path).splitlines()[0] == "# SPDX-License-Identifier: GPL-3.0-or-later", path.name
    for path in (PKG / "data" / "icons" / "org.aspdesignlabs.AckVoiceStudio.svg",):
        assert "SPDX-License-Identifier: GPL-3.0-or-later" in "\n".join(source(path).splitlines()[:3]), path.name
    assert not (PKG / "data" / "style.css").exists() and not (PKG / "window" / "style.py").exists(), "the style sheet is made by core/windowtheme.py now"


@pytest.mark.parametrize("path", WINDOW, ids=lambda p: p.name)
def test_no_gtk_call_newer_than_4_6_is_used(path):
    code = code_only(path)
    used = [name for name in NEWER_THAN_4_6 if name in code]
    assert not used, "%s uses %s, which Ubuntu 22.04's GTK 4.6 does not have" % (path.name, used)


@pytest.mark.parametrize("path", WINDOW, ids=lambda p: p.name)
def test_the_window_talks_to_no_other_computer_and_opens_no_web_address(path):
    code = code_only(path)
    found = [name for name in NETWORK if name in code]
    assert not found, "%s names %s" % (path.name, found)
    assert not re.search(r"https?://", source(path)), path.name


def test_the_style_sheet_is_text_made_in_core_and_loaded_as_bytes_which_gtk_4_6_and_4_14_both_accept():
    code = code_only(PKG / "window" / "theme.py")
    assert "load_from_data(text.encode('utf-8'))" in code and "css_for(self.look)" in code
    for path in WINDOW:
        assert "load_from_string" not in code_only(path) and "load_from_file" not in code_only(path), path.name


def test_the_window_files_hold_no_colour_of_their_own_every_colour_comes_from_the_core_palette():
    for path in WINDOW:
        code = code_only(path)
        assert not re.search(r"#[0-9a-fA-F]{6}\b|Gdk\.RGBA|rgb\(", code), path.name
        assert "set_property('gtk-application-prefer-dark-theme'" not in code or path.name == "theme.py", path.name


def test_every_pixel_size_set_from_python_goes_through_the_scale():
    for name in ("pages.py", "shell.py", "dialogs.py"):
        code = code_only(PKG / "window" / name)
        loose = re.findall(r"Gtk\.\w+\([^()]*\b(?:spacing|margin_\w+|width_request|height_request|min_content_height|max_content_height)=\d+", code)
        assert loose == [], (name, loose)


def test_the_only_timers_are_the_progress_bar_and_a_read_only_refresh_and_nothing_starts_by_itself():
    found = {}
    for path in WINDOW:
        for node in ast.walk(ast.parse(source(path))):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr in ("timeout_add", "timeout_add_seconds", "idle_add"):
                found.setdefault(path.name, []).append(node.func.attr)
    assert found == {"pages.py": ["timeout_add_seconds"], "shell.py": ["idle_add", "idle_add", "idle_add", "idle_add", "timeout_add"]}, found
    pages = code_only(PKG / "window" / "pages.py")
    assert "self.refresh" in pages and "shell.run" not in pages.split("def _tick")[1].split("\n    def ")[0]          # the tick only reads again


def test_every_change_goes_through_a_flow_and_the_window_itself_writes_no_file():
    for path in WINDOW:
        code = code_only(path)
        assert not re.search(r"\bopen\([^)]*['\"][wa]b?['\"]", code) and "os.remove" not in code and "os.unlink" not in code and "shutil" not in code and "rmtree" not in code, path.name


def test_the_one_file_the_window_keeps_is_written_by_the_core_only_after_a_yes_and_removed_only_after_a_yes():
    shell = code_only(PKG / "window" / "shell.py")
    theme = code_only(PKG / "window" / "theme.py")
    pages = code_only(PKG / "window" / "pages.py")
    # saving: only the theme's own save(), and that is called only when the keeper says write, or straight after a yes
    assert theme.count("wp.save(") == 1 and "wp.save(" not in shell and "wp.save(" not in pages
    change = theme.split("def change(")[1].split("\n    def ")[0]
    assert change.index("action = self.keeper.on_change()") < change.index("if action == 'write'") < change.index("return self.save()")
    ask = shell.split("def ask_to_keep(")[1].split("\n    def ")[0]
    assert ask.index("if not yes:") < ask.index("appearance.keeper.said_yes()") < ask.index("appearance.save()") and "said_no" in ask.split("if not yes:")[1].split("return")[0]
    assert "self.show_confirm(" in ask and ask.index("def reply") < ask.index("self.show_confirm(")
    # removing: listed first, and only inside the answer to the question, after a No has returned
    forget = shell.split("def ask_to_forget(")[1].split("\n    def ")[0]
    assert forget.index("shown = wp.plan_forget(") < forget.index("def reply") < forget.index("if not yes:") < forget.index("wp.forget(shown)") < forget.index("self.show_confirm(")
    assert shell.count("wp.forget(") == 1 and "wp.forget(" not in pages and "wp.forget(" not in theme
    # a change never writes by itself in the page code
    assert "appearance.change(" not in pages and "shell.change_look(" in pages


def test_no_control_is_icon_only_and_there_is_no_sound_call():
    for path in WINDOW:
        code = code_only(path)
        assert "icon_name" not in code and "Gtk.Image" not in code and "beep" not in code.lower() and "play_" not in code, path.name


# ---------------------------------------------------------------- the real window, driven

def _system_python():
    found = sorted(str(p) for p in Path("/usr/bin").glob("python3*") if re.fullmatch(r"python3(\.\d+)?", p.name))      # the Python that Ubuntu's python3-gi belongs to is not always `python3`
    for candidate in found + [shutil.which("python3") or ""]:
        if candidate and os.path.exists(candidate):
            probe = subprocess.run([candidate, "-c", "import gi; gi.require_version('Gtk','4.0'); from gi.repository import Gtk"], capture_output=True, timeout=60)
            if probe.returncode == 0:
                return candidate
    return None


def _tour(tmp_path):
    """Run `--selftest` on a copy of a project made for it; returns (completed process, home on this computer)."""
    folder = Path(SCRATCH if RUNNER else str(tmp_path))
    work = folder / ("gtk-tour-%d" % os.getpid())
    work.mkdir()
    rig = ProjectRig(work)
    rig.finish(3)
    from vs_rounds_helpers import DATASET
    from voice_studio.core import rounds as rd
    working = rd.cache_dir_for(rig.world.scratch, DATASET, 1)
    os.makedirs(working + "/train")
    Path(working + "/train/a.pt").write_bytes(b"c" * 2000)
    home = work / "home"
    if RUNNER:
        inside = "/mnt/scratch/" + work.name + "/home"
        argv = RUNNER.split() + ["env", "HOME=" + inside, "PYTHONPATH=/mnt/tools", "PYTHONDONTWRITEBYTECODE=1", "G_DEBUG=fatal-criticals", "xvfb-run", "-a", "python3", "-m", "voice_studio.window", "--selftest"]
        return subprocess.run(argv, capture_output=True, text=True, timeout=240), home
    python = _system_python()
    env = dict(os.environ, HOME=str(home), PYTHONPATH=str(TOOLS), PYTHONDONTWRITEBYTECODE="1", G_DEBUG="fatal-criticals")
    return subprocess.run(["xvfb-run", "-a", python, "-m", "voice_studio.window", "--selftest"], capture_output=True, text=True, timeout=240, env=env, cwd=str(TOOLS)), home


@pytest.mark.skipif(not RUNNER and not (shutil.which("xvfb-run") and _system_python()), reason="needs a Python with GTK 4 and a virtual display (xvfb-run)")
def test_the_real_window_passes_its_own_tour_on_a_virtual_display(tmp_path):
    done, home = _tour(tmp_path)
    assert done.returncode == 0, done.stdout[-1500:] + done.stderr[-1500:]
    report = json.loads(done.stdout.strip().splitlines()[-1])
    assert report["failed"] == [] and report["unnamed_controls"] == {} and report["smallest_text_pt"] >= 12.0 and report["animations_off"] is True
    assert report["pages"] == ["Projects", "Training rounds", "Voice file", "Free up space", "Display"] and report["project_opened"] == "voice-check"
    for key in ("the_chosen_round_has_no_choose_button", "no_is_the_default_widget", "pages_locked_while_a_question_waits", "a_second_task_is_refused_while_busy", "pages_unlocked_after",
                "result_head_for_nothing", "result_head_for_done", "remove_button_off_when_nothing_is_ticked", "free_question_names_only_the_ticked", "result_head_for_a_problem",
                "no_is_where_the_focus_starts", "yes_is_not_the_default", "question_has_no_typed_instruction", "choose_question_shown", "no_answered", "no_changed_nothing", "yes_answered", "yes_chose_it", "free_question_shown", "free_no_answered", "make_finished", "make_said_why",
                "not_busy_at_the_end", "every_look_is_a_sheet_gtk_accepts", "scale_reaches_python_sizes", "scale_goes_back", "no_file_before_any_choice", "theme_buttons_are_named",
                "accent_buttons_are_named", "first_change_asks", "question_names_the_file_and_what_it_holds", "keep_question_starts_on_no", "the_change_is_shown_though_not_kept",
                "a_no_is_said_in_the_result", "after_a_no_nothing_asks_and_nothing_is_written", "smaller_text_is_off_at_the_smallest_step", "asks_again_after_a_fresh_start",
                "a_yes_writes_the_small_file", "the_file_is_owner_only_and_small", "a_yes_is_said_in_the_result", "later_changes_are_written_without_asking", "the_page_says_where_they_are_kept",
                "removing_lists_the_files_first", "removing_names_both_files", "a_no_to_removing_keeps_both", "a_yes_removes_them_and_the_window_asks_again_next_time",
                "the_window_keeps_its_look_after_removing", "standard_look_comes_back"):
        assert report[key] is True, key
    assert "Gtk-CRITICAL" not in done.stderr and "Gtk-WARNING" not in done.stderr
    if RUNNER:
        assert report["gtk"].startswith("4.6.")
