# SPDX-License-Identifier: GPL-3.0-or-later
"""ACK's look for the window as decisions (core/windowtheme.py) and the small file that keeps the person's display choices (core/windowprefs.py). No GTK in here: the style sheet is text, and what GTK
makes of it is read by test_vs_window_gtk.py."""
import json
import os
import re
import stat
from pathlib import Path

import pytest

from voice_studio.core import windowprefs as wp
from voice_studio.core import windowtheme as wt
from voice_studio.core.paths import DataHome

PKG = Path(__file__).resolve().parents[1]
ALL_LOOKS = [wt.Look(theme, accent, pt, pct) for theme in wt.THEMES for accent in (0, 4, 6) for pt in (12, 14, 28) for pct in (100, 150, 300)]


# ---------------------------------------------------------------- colour arithmetic

def test_the_contrast_formula_gives_the_values_the_standard_gives():
    assert wt.contrast("#000000", "#ffffff") == pytest.approx(21.0)
    assert wt.contrast("#ffffff", "#ffffff") == pytest.approx(1.0)
    assert wt.contrast("#777777", "#ffffff") == pytest.approx(4.48, abs=0.01)             # the well known borderline grey
    assert wt.contrast("#595959", "#ffffff") == pytest.approx(7.0, abs=0.02)
    assert wt.contrast("#00f3ff", "#050505") == wt.contrast("#050505", "#00f3ff")
    assert wt.luminance("#000000") == 0.0 and wt.luminance("#ffffff") == pytest.approx(1.0)


def test_mixing_is_a_straight_line_between_two_colours_and_stays_inside_the_range():
    assert wt.mix("#000000", "#ffffff", 0.0) == "#000000" and wt.mix("#000000", "#ffffff", 1.0) == "#ffffff"
    assert wt.mix("#000000", "#ffffff", 0.5) in ("#7f7f7f", "#808080")
    assert wt.mix("#102030", "#102030", 0.7) == "#102030"


@pytest.mark.parametrize("index", range(len(wt.ACCENTS)))
def test_every_colour_pair_the_style_sheet_draws_keeps_its_contrast_for_every_accent(index):
    assert wt.contrast_problems(wt.palette(index)) == []


def test_the_check_itself_can_fail():
    bad = wt.Palette("#202020", "#202020", "#202020", "#202020", "#202020", "#202020")
    problems = wt.contrast_problems(bad)
    assert len(problems) >= 8 and any("accent text" in p for p in problems) and any("quiet border" in p for p in problems)
    assert wt.palette(0).accent_text == "#00f3ff"                                                     # cyan already passes: it is left exactly as ACK has it
    assert wt.palette(6).accent_text != wt.palette(6).accent and wt.contrast(wt.palette(6).accent_text, wt.GRAPHITE) >= 4.5      # deep blue would fail as text: lightened, and only as text
    assert wt.palette(6).accent_ui == wt.palette(6).accent                                            # but its border stays ACK's own blue, which is enough for a line


def test_an_accent_that_is_not_one_of_the_ten_gets_the_default_and_the_ten_are_ACKs_own():
    assert wt.palette(99) == wt.palette(0) and wt.palette(-1) == wt.palette(0)
    assert [c for _n, c in wt.ACCENTS] == ["#00f3ff", "#ff0055", "#00ff41", "#ff9900", "#bd00ff", "#ffd500", "#0055ff", "#ff00ff", "#b7ff00", "#ff0099"]
    kotlin = (PKG.parents[1] / "app/src/main/java/com/example/besu/ui/theme/Color.kt").read_text()
    for _name, color in wt.ACCENTS:
        assert "Color(0xFF%s)" % color[1:].upper() in kotlin, color                                       # the phone app's own swatches: a drift guard
    assert (wt.VOID, wt.GRAPHITE) == ("#050505", "#121212") and "VoidBlack = Color(0xFF050505)" in kotlin and "Graphite = Color(0xFF121212)" in kotlin


# ---------------------------------------------------------------- the choices

def test_the_steps_move_one_at_a_time_and_stop_at_the_ends():
    look = wt.Look()
    assert look.bigger_text().text_pt == 16 and look.smaller_text().text_pt == 13
    assert wt.Look(text_pt=12).smaller_text().text_pt == 12 and wt.Look(text_pt=28).bigger_text().text_pt == 28
    assert wt.Look(scale_pct=100).smaller_scale().scale_pct == 100 and wt.Look(scale_pct=300).bigger_scale().scale_pct == 300
    assert look.bigger_scale().scale_pct == 125 and look.bigger_scale().bigger_scale().scale_pct == 150
    assert wt.Look(text_pt=15).bigger_text().text_pt == 16 and wt.Look(text_pt=15).smaller_text().text_pt == 13      # a value between steps counts as the step below it
    assert wt.TEXT_STEPS[0] == 12 and wt.SCALE_STEPS[0] == 100 and wt.DEFAULT_TEXT_PT in wt.TEXT_STEPS


def test_a_choice_that_is_not_a_step_is_put_back_to_the_default_for_that_choice_and_the_others_are_kept():
    assert wt.Look("neon", 3, 14, 100).normalised() == wt.Look("ack", 3, 14, 100)
    assert wt.Look("system", 99, 14, 100).normalised() == wt.Look("system", 0, 14, 100)
    assert wt.Look("ack", True, 14, 100).normalised().accent == 0                                       # True is not a colour number
    assert wt.Look("ack", 2, 15, 100).normalised().text_pt == 14 and wt.Look("ack", 2, 14, 110).normalised().scale_pct == 100
    assert wt.Look(None, None, None, None).normalised() == wt.Look()                                    # type: ignore[arg-type]
    assert wt.Look("ack", 9, 28, 300).normalised() == wt.Look("ack", 9, 28, 300)


def test_the_text_never_gets_below_twelve_points_at_any_step_or_scale():
    assert min(wt.TEXT_STEPS) == 12 and min(wt.SCALE_STEPS) == 100
    assert all(wt.Look(text_pt=pt, scale_pct=pct).effective_pt >= 12 for pt in wt.TEXT_STEPS for pct in wt.SCALE_STEPS)
    assert wt.Look(text_pt=14, scale_pct=150).effective_pt == 21.0


# ---------------------------------------------------------------- the style sheet

def lengths(css):
    return [float(v) for v in re.findall(r"(-?\d+(?:\.\d+)?)px", css)]


@pytest.mark.parametrize("look", ALL_LOOKS, ids=lambda l: "%s-%d-%d-%d" % (l.theme, l.accent, l.text_pt, l.scale_pct))
def test_the_sheet_is_made_the_same_way_every_time_and_no_text_is_smaller_than_the_base_size(look):
    css = wt.css_for(look)
    assert css == wt.css_for(look) and css.strip()
    assert "window { font-size: %gpt; }" % round(look.effective_pt, 2) in css
    assert all(float(em) >= wt.MIN_TEXT_EM for em in re.findall(r"font-size: ([\d.]+)em", css))
    assert not re.search(r"font-size: [\d.]+(px|pt)", css.replace("window { font-size", "")), "only the base size is in points; every other size is relative to it"
    assert "clip-path" not in css and "@import" not in css and "url(" not in css
    assert "{{" not in css and "}}" not in css and css.count("{") == css.count("}"), "every brace is a real one"


def test_the_system_theme_sets_no_colour_and_no_shape_so_the_systems_own_theme_decides():
    for pct in (100, 200):
        css = wt.css_for(wt.Look("system", 0, 16, pct))
        assert not re.search(r"#[0-9a-fA-F]{3,8}\b|rgb|hsl|gradient|background|border|outline|color|shadow", css), re.findall(r"[^\n]*(?:#[0-9a-f]{6}|gradient|background|border|color)[^\n]*", css)[:3]
        assert "text-transform: uppercase" in css and "letter-spacing" in css                           # the type stays: it is not a colour
    assert wt.css_for(wt.Look("system", 0, 14, 100)) == wt.css_for(wt.Look("system", 5, 14, 100)), "the accent means nothing in the system theme"


def test_the_ack_theme_uses_only_the_palette_the_accent_and_the_few_fixed_greys():
    for index in range(len(wt.ACCENTS)):
        pal = wt.palette(index)
        allowed = {wt.VOID, wt.GRAPHITE, wt.GRAPHITE_2, wt.TEXT, wt.TEXT_DIM, wt.TEXT_FAINT, wt.WHITE, wt.ERROR, "#2a2a2a", pal.accent_text, pal.accent_ui, pal.edge_soft, pal.hover_fill,
                   pal.selected_fill} | {c for _n, c in wt.ACCENTS}
        used = set(re.findall(r"#[0-9a-f]{6}\b", wt.css_for(wt.Look("ack", index))))
        assert used <= allowed, sorted(used - allowed)
        assert pal.accent_ui in used and pal.accent_text in used and pal.hover_fill in used


def test_every_length_grows_with_the_scale_except_the_hairline_of_a_separator():
    def without_hairlines(css):
        css = re.sub(r"separator \{[^}]*\}", "", css)
        return re.sub(r"linear-gradient\(\d+deg[^)]*\)", "PIECE", css)                       # the soft ends of a diagonal are a pixel wide whatever the scale: checked below
    base, big = without_hairlines(wt.css_for(wt.Look("ack", 0, 14, 100))), without_hairlines(wt.css_for(wt.Look("ack", 0, 14, 200)))
    shape = lambda css: re.sub(r"-?\d+(?:\.\d+)?(px|pt)", "N", css)
    assert shape(base) == shape(big), "the same rules, only the numbers differ"
    pairs = list(zip(lengths(base), lengths(big)))
    assert pairs and all(b == pytest.approx(a * 2, abs=0.02) for a, b in pairs), [p for p in pairs if p[1] != pytest.approx(p[0] * 2, abs=0.02)][:5]
    assert "font-size: 14pt" in base and "font-size: 28pt" in big
    one, two = wt._box(8, 1, "#00f3ff", "#121212", "#050505", 1.0), wt._box(8, 1, "#00f3ff", "#121212", "#050505", 2.0)
    first = lambda box: [float(v) for v in re.findall(r"([\d.]+)px", box.split("linear-gradient(")[1].split(")")[0])]
    assert first(two)[0] == pytest.approx(first(one)[0] * 2, abs=1.6) and first(two)[2] > first(one)[2] * 1.5


def test_the_cut_corner_is_two_corner_pieces_four_lines_and_a_fill_and_scales_with_the_box():
    box = wt._box(8, 1, "#00f3ff", "#121212", "#050505", 1.0)
    assert box.count("linear-gradient(") == 6 and "135deg" in box and "315deg" in box
    assert box.count("top left") == 1 and box.count("bottom right") == 1 and "background-color: #121212" in box and "no-repeat" in box
    stripe = [float(v) for v in re.findall(r"([\d.]+)px", box.split("linear-gradient(")[1].split(")")[0])]
    outer, edge_in, edge_out, soft_end = stripe
    assert 0 < outer < edge_in < edge_out < soft_end <= 8 * 1.4143 + 3, stripe                          # the diagonal sits inside the corner piece
    assert stripe == [4.41, 5.41, 6.91, 7.91], "the cut line is 8 / sqrt(2) = 5.66 px from the corner along the diagonal, drawn 1.5 px wide with a half pixel of soft edge each side"
    assert [float(v) for v in re.findall(r"([\d.]+)px", wt._box(20, 1, "#00f3ff", "#121212", "#050505", 1.0).split("linear-gradient(")[1].split(")")[0])] == [12.89, 13.89, 15.39, 16.39]      # 20 / sqrt(2) = 14.14, minus or plus 0.75 and 0.5
    assert "background-size: 10px 10px, 10px 10px, 100% 1px, 100% 1px, 1px 100%, 1px 100%;" in box
    assert "background-size: 20px 20px, 20px 20px, 100% 2px, 100% 2px, 2px 100%, 2px 100%;" in wt._box(8, 1, "#00f3ff", "#121212", "#050505", 2.0)
    assert "background-position: top left, bottom right, top, bottom, left, right;" in box


def test_the_focus_ring_is_white_and_thick_on_every_kind_of_control_and_a_nav_row_and_a_disabled_button_have_their_own_looks():
    css = wt.css_for(wt.Look())
    for selector in ("button.ack-button:focus-visible", ".ack-nav row:focus-visible", "list.boxed-list row button.ack-button:focus-visible", "entry:focus-within", "check:focus-visible"):
        assert selector in css, selector
    focus = css.split("button.ack-button:focus-visible {")[1].split("}")[0]
    assert "#ffffff" in focus and "3px" in focus
    assert "button.ack-button:disabled" in css and "button.ack-button:hover" in css and "button.ack-button:checked" in css


def test_each_of_the_ten_accents_has_a_swatch_class_for_the_display_page():
    css = wt.css_for(wt.Look())
    for name, color in wt.ACCENTS:
        assert "button.swatch-%s," % name in css and color in css.split("button.swatch-%s," % name)[1].split("}")[0]


def _blocks(css, selector):
    """Every rule whose whole selector is exactly `selector`: the text between its braces."""
    return re.findall(r"(?:^|\})\s*" + re.escape(selector) + r"\s*\{([^}]*)\}", css)


def test_the_floor_for_text_is_one_em_of_a_twelve_point_base():
    assert wt.MIN_TEXT_EM == 1.0 and wt.TEXT_STEPS[0] == 12


@pytest.mark.parametrize("theme", wt.THEMES)
def test_headings_labels_and_buttons_show_capitals_by_style_and_sentences_do_not(theme):
    css = wt.css_for(wt.Look(theme=theme))
    for selector in (".tagline", ".page-heading", ".section-heading", ".ack-nav row label", "button.ack-button label"):
        assert any("text-transform: uppercase" in b and "letter-spacing" in b for b in _blocks(css, selector)), (theme, selector)
    for selector in (".question-text", ".round-head"):
        assert not any("text-transform" in b for b in _blocks(css, selector)), (theme, selector)


def test_an_error_is_drawn_in_the_error_tone_and_a_dialog_has_a_void_black_background():
    css = wt.css_for(wt.Look())
    assert [b.strip() for b in _blocks(css, ".error-text")] == ["color: %s;" % wt.ERROR]
    assert any("background-color: %s;" % wt.VOID in b for b in _blocks(css, "window.dialog, window.ack-dialog"))
    assert any("background-color: %s;" % wt.VOID in b for b in _blocks(css, "window.ack-dialog .dialog-action-box"))


def test_every_kind_of_control_shows_a_white_focus_ring_of_at_least_two_pixels():
    css = wt.css_for(wt.Look())
    for selector in ("button.ack-button:focus-visible", "list.boxed-list row button.ack-button:focus-visible", ".ack-nav row:focus-visible"):
        block = " ".join(_blocks(css, selector))
        assert "#ffffff" in block and "3px" in block, selector                                                    # a three pixel white line, drawn into the cut-corner background
    for selector in ("entry:focus-within, spinbutton:focus-within", "dropdown > button:focus-visible", "check:focus-visible, radio:focus-visible", "button.swatch:focus-visible"):
        block = " ".join(_blocks(css, selector))
        assert "outline: 2px solid #ffffff" in block, selector
    doubled = wt.css_for(wt.Look(scale_pct=200))
    assert "outline: 4px solid #ffffff" in " ".join(_blocks(doubled, "entry:focus-within, spinbutton:focus-within")), "the ring grows with the scale"


# ---------------------------------------------------------------- the file

def test_the_file_lives_in_the_tools_state_folder_beside_the_consent_record():
    home = DataHome("/home/anna")
    assert home.window_file == "/home/anna/ack-voice-studio/state/window.json" and home.window_file.startswith(home.state + "/")


def test_there_is_no_file_until_something_is_saved_and_nothing_is_made_by_looking(tmp_path):
    path = str(tmp_path / "state" / "window.json")
    assert wp.load(path) is None and not (tmp_path / "state").exists()
    assert wp.plan_forget(path) == ()
    assert wp.Keeper.for_file(path).state == "undecided"


def test_a_saved_choice_reads_back_the_same_and_the_file_is_owner_only_and_small(tmp_path):
    path = str(tmp_path / "state" / "window.json")
    look = wt.Look("system", 6, 18, 175)
    wp.save(path, look)
    assert wp.load(path) == look
    assert stat.S_IMODE(os.stat(path).st_mode) == 0o600 and stat.S_IMODE(os.stat(os.path.dirname(path)).st_mode) == 0o700
    data = json.loads(Path(path).read_text())
    assert data == {"schema": 1, "theme": "system", "accent": 6, "text_pt": 18, "scale_pct": 175} and len(Path(path).read_bytes()) < 200
    assert sorted(p.name for p in (tmp_path / "state").iterdir()) == ["window.json"], "no temporary file is left behind"


def test_the_file_that_is_replaced_is_kept_beside_it_and_a_save_that_changes_nothing_writes_nothing(tmp_path):
    path = str(tmp_path / "state" / "window.json")
    wp.save(path, wt.Look(accent=1))
    first = Path(path).read_bytes()
    wp.save(path, wt.Look(accent=1))
    assert not Path(wp.previous_path(path)).exists(), "the same choices again is not a change"
    wp.save(path, wt.Look(accent=2))
    assert Path(wp.previous_path(path)).read_bytes() == first and wp.load(path).accent == 2 and wp.load(wp.previous_path(path)).accent == 1
    assert stat.S_IMODE(os.stat(wp.previous_path(path)).st_mode) == 0o600
    wp.save(path, wt.Look(accent=3))
    assert wp.load(wp.previous_path(path)).accent == 2, "only the one before is kept"


@pytest.mark.parametrize("content", [None, "", "not json", "[]", "null", "42", '{"schema": 2, "accent": 1}', '{"accent": 1}', '{"schema": 1', "x" * 5000, '{"schema": 1, "a": ' + "[" * 5000])
def test_a_missing_damaged_or_foreign_file_is_no_file_and_never_an_error(tmp_path, content):
    path = tmp_path / "window.json"
    if content is not None:
        path.write_text(content)
    assert wp.load(str(path)) is None


def test_a_field_that_is_not_a_step_falls_back_alone_and_unknown_keys_are_ignored(tmp_path):
    path = tmp_path / "window.json"
    path.write_text(json.dumps({"schema": 1, "theme": "neon", "accent": 4, "text_pt": 15, "scale_pct": 200, "extra": {"x": 1}}))
    assert wp.load(str(path)) == wt.Look("ack", 4, 14, 200)
    path.write_text(json.dumps({"schema": 1, "theme": "system", "accent": "red", "text_pt": None, "scale_pct": [100]}))
    assert wp.load(str(path)) == wt.Look("system", 0, 14, 100)


def test_a_failed_write_raises_leaves_the_old_file_whole_and_no_temporary_file(tmp_path, monkeypatch):
    path = str(tmp_path / "state" / "window.json")
    wp.save(path, wt.Look(accent=1))
    before = Path(path).read_bytes()
    real = os.replace

    def broken(src, dst):
        raise OSError(28, "No space left on device")
    monkeypatch.setattr(os, "replace", broken)
    with pytest.raises(OSError):
        wp.save(path, wt.Look(accent=5))
    monkeypatch.setattr(os, "replace", real)
    assert Path(path).read_bytes() == before and sorted(p.name for p in (tmp_path / "state").iterdir()) == ["window.json"]


def test_forgetting_lists_the_file_and_its_older_copy_first_and_removes_only_those(tmp_path):
    path = str(tmp_path / "state" / "window.json")
    wp.save(path, wt.Look(accent=1))
    wp.save(path, wt.Look(accent=2))
    (tmp_path / "state" / "consent.json").write_text("{}")
    shown = wp.plan_forget(path)
    assert shown == (path, wp.previous_path(path))
    wp.forget(shown)
    assert sorted(p.name for p in (tmp_path / "state").iterdir()) == ["consent.json"]
    wp.forget(shown)                                                                                    # already gone: not an error
    link = tmp_path / "state" / "window.json"
    link.symlink_to(tmp_path / "state" / "consent.json")
    assert wp.plan_forget(path) == (), "a link is not one of our files and is never offered"


def test_a_file_bigger_than_a_few_short_fields_is_not_ours_even_if_it_is_valid(tmp_path):
    path = tmp_path / "window.json"
    body = json.dumps({"schema": 1, "theme": "system", "accent": 4, "text_pt": 16, "scale_pct": 150})
    path.write_text(body)
    assert wp.load(str(path)) == wt.Look("system", 4, 16, 150)
    path.write_text(body + " " * wp.MAX_BYTES)
    assert path.stat().st_size > wp.MAX_BYTES and wp.load(str(path)) is None


def test_the_data_is_flushed_to_disk_before_a_file_is_moved_into_place(tmp_path, monkeypatch):
    path = str(tmp_path / "state" / "window.json")
    calls = []
    real = os.fsync
    monkeypatch.setattr(os, "fsync", lambda fd: (calls.append(fd), real(fd))[1])
    wp.save(path, wt.Look(accent=1))
    assert len(calls) == 1
    wp.save(path, wt.Look(accent=2))
    assert len(calls) == 3, "the older copy and the new file are each flushed"


def test_forgetting_something_that_cannot_be_removed_is_an_error_the_caller_can_report(tmp_path):
    folder = tmp_path / "state" / "window.json"
    folder.mkdir(parents=True)
    with pytest.raises(OSError):
        wp.forget((str(folder),))
    assert folder.is_dir()


def test_the_keeper_asks_once_writes_after_a_yes_and_stays_quiet_after_a_no(tmp_path):
    path = str(tmp_path / "window.json")
    keeper = wp.Keeper.for_file(path)
    assert keeper.on_change() == "ask"
    keeper.said_yes()
    assert keeper.on_change() == "write" and keeper.on_change() == "write"
    other = wp.Keeper.for_file(path)
    other.said_no()
    assert other.on_change() == "nothing" and other.on_change() == "nothing"
    wp.save(path, wt.Look())
    assert wp.Keeper.for_file(path).on_change() == "write", "a file that is already there means the person agreed before"
    keeper.forgot()
    assert keeper.on_change() == "ask"


def test_the_modules_start_no_program_use_no_network_and_name_no_person_or_path():
    for name in ("windowprefs.py", "windowtheme.py"):
        source = (PKG / "core" / name).read_text()
        assert not re.search(r"subprocess|os\.system|socket|urllib|http", source), name
    assert not re.search(r"expanduser|getpass|gethostname|environ", (PKG / "core" / "windowprefs.py").read_text())
