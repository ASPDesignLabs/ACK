# SPDX-License-Identifier: GPL-3.0-or-later
"""ACK's look for the window, as decisions: the palette, the contrast every colour pair must keep, the text and scale steps, and the one function that turns a `Look` into the window's style sheet.

Plain Python with no GTK, so every rule here is tested on any computer. The GTK edge (window/theme.py) only loads the text this module makes.

Where it comes from: ACK's phone app (ui/theme/Color.kt, ui/DesignSystem.kt, ui/OverlayStyle.kt) and its website (STYLEGUIDE.md): void black and graphite surfaces, one neon accent, monospace bold
capitals for headings, buttons and labels, a 1 px accent border, and the signature cut corners (top left and bottom right). Three things are done differently here, on purpose:

* **Cut corners are drawn with CSS gradients**, not code, because GTK 4.6 (Ubuntu 22.04) has no `clip-path` and drawing them in code would need a package that Ubuntu does not install by default.
* **Capitals are `text-transform: uppercase`**, never typed into a label: a screen reader reads the words as they are written (STYLEGUIDE non-negotiable 10).
* **Every colour pair is checked against WCAG AA** here (`contrast_problems`), and the accent is lightened where it would fail as text or as a border (the website does the same with `--cyan` and `--cyan-bright`).

Two themes: `ack` (all of the above) and `system` (sizes, spacing and type only, no colours and no shapes, so the system's own theme, including a high-contrast one, decides them: plan P6).
The text size (A- and A+) and the scale (the whole window: spacing, controls and corners as well as text) are separate steps; `scale` multiplies every length this module writes.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, replace
from typing import List, Sequence, Tuple

THEMES = ("ack", "system")
TEXT_STEPS = (12, 13, 14, 16, 18, 20, 24, 28)              # points; 12 is the floor (plan P6), 14 the default
SCALE_STEPS = (100, 125, 150, 175, 200, 250, 300)          # percent of everything else
DEFAULT_THEME, DEFAULT_ACCENT, DEFAULT_TEXT_PT, DEFAULT_SCALE_PCT = "ack", 0, 14, 100
MIN_TEXT_EM = 1.0                                          # no class is drawn smaller than the base size, so the 12 pt floor holds at every step

# ACK's ten neon colours (ui/theme/Color.kt), in its order: index 0 is the default. The words for them are in the text catalog (window.display.accent_<id>).
ACCENTS: Tuple[Tuple[str, str], ...] = (
    ("cyan", "#00f3ff"), ("red", "#ff0055"), ("green", "#00ff41"), ("orange", "#ff9900"), ("purple", "#bd00ff"),
    ("yellow", "#ffd500"), ("blue", "#0055ff"), ("magenta", "#ff00ff"), ("lime", "#b7ff00"), ("pink", "#ff0099"))

VOID, GRAPHITE, GRAPHITE_2 = "#050505", "#121212", "#1a1a1a"      # window, panels, cards inside panels (the website's --void, --graphite, --graphite-2)
TEXT, TEXT_DIM, TEXT_FAINT, WHITE = "#e8e8e8", "#a8a8a8", "#8c8c8c", "#ffffff"       # the website's faint grey #808080 is 4.41:1 on a card, so it is a little lighter here
ERROR = "#ff5470"                                                  # the website's text-safe error tone
FONT_MONO = '"DejaVu Sans Mono", "Ubuntu Mono", "Liberation Mono", monospace'


# ---------------------------------------------------------------- colour arithmetic

def _rgb(color: str) -> Tuple[int, int, int]:
    text = color.lstrip("#")
    return int(text[0:2], 16), int(text[2:4], 16), int(text[4:6], 16)


def _hex(rgb: Sequence[float]) -> str:
    return "#%02x%02x%02x" % tuple(max(0, min(255, int(round(v)))) for v in rgb)


def luminance(color: str) -> float:
    """WCAG relative luminance."""
    def part(v: int) -> float:
        c = v / 255.0
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (part(v) for v in _rgb(color))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(a: str, b: str) -> float:
    """WCAG contrast ratio, 1 to 21."""
    hi, lo = sorted((luminance(a), luminance(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


def mix(a: str, b: str, amount: float) -> str:
    """`amount` of b in a (0 is a, 1 is b)."""
    ra, rb = _rgb(a), _rgb(b)
    return _hex(ra[i] + (rb[i] - ra[i]) * amount for i in range(3))


def _lighten_until(color: str, toward: str, backgrounds: Sequence[str], minimum: float) -> str:
    """The first colour on the way from `color` toward `toward` (in 2% steps) that keeps `minimum` contrast against every background. The colour itself if it already does."""
    for step in range(0, 51):
        candidate = mix(color, toward, step * 0.02)
        if all(contrast(candidate, bg) >= minimum for bg in backgrounds):
            return candidate
    return toward


@dataclass(frozen=True)
class Palette:
    accent: str          # ACK's own neon colour, for decoration only
    accent_text: str     # the accent as text: at least 4.5:1 on every surface and fill it is drawn on
    accent_ui: str       # the accent as a border or an icon: at least 3:1 on every surface
    edge_soft: str       # the quiet border of a card or a panel that is not a control: at least 3:1 on every surface
    hover_fill: str      # the accent, faintly, on graphite
    selected_fill: str   # the accent, a little stronger, on graphite


def palette(accent_index: int) -> Palette:
    accent = ACCENTS[accent_index if 0 <= accent_index < len(ACCENTS) else DEFAULT_ACCENT][1]
    hover = mix(GRAPHITE, accent, 0.14)
    selected = mix(GRAPHITE, accent, 0.24)
    surfaces = (VOID, GRAPHITE, GRAPHITE_2, hover, selected)
    ui = _lighten_until(accent, WHITE, (VOID, GRAPHITE, GRAPHITE_2), 3.0)
    soft = ui
    for step in range(0, 21):                                                  # the quietest mix of the border colour into graphite that is still a visible line
        candidate = mix(GRAPHITE, ui, step * 0.05)
        if all(contrast(candidate, bg) >= 3.0 for bg in (VOID, GRAPHITE, GRAPHITE_2)):
            soft = candidate
            break
    return Palette(accent, _lighten_until(accent, WHITE, surfaces, 4.5), ui, soft, hover, selected)


def contrast_problems(pal: Palette) -> List[str]:
    """Every colour pair the style sheet draws, and why one fails. [] when all hold. The pairs are the whole list: a pair that is not here is not drawn."""
    pairs = [
        ("text on void", TEXT, VOID, 7.0), ("text on graphite", TEXT, GRAPHITE, 7.0), ("text on a card", TEXT, GRAPHITE_2, 7.0),
        ("text on a hovered button", TEXT, pal.hover_fill, 7.0), ("text on a selected row", WHITE, pal.selected_fill, 7.0),
        ("dim text on void", TEXT_DIM, VOID, 4.5), ("dim text on graphite", TEXT_DIM, GRAPHITE, 4.5), ("dim text on a card", TEXT_DIM, GRAPHITE_2, 4.5),
        ("faint text on void", TEXT_FAINT, VOID, 4.5), ("faint text on graphite", TEXT_FAINT, GRAPHITE, 4.5), ("faint text on a card", TEXT_FAINT, GRAPHITE_2, 4.5),
        ("error on graphite", ERROR, GRAPHITE, 4.5), ("error on a card", ERROR, GRAPHITE_2, 4.5),
        ("accent text on void", pal.accent_text, VOID, 4.5), ("accent text on graphite", pal.accent_text, GRAPHITE, 4.5), ("accent text on a card", pal.accent_text, GRAPHITE_2, 4.5),
        ("accent text on a hovered button", pal.accent_text, pal.hover_fill, 4.5), ("accent text on a selected row", pal.accent_text, pal.selected_fill, 4.5),
        ("accent border on void", pal.accent_ui, VOID, 3.0), ("accent border on graphite", pal.accent_ui, GRAPHITE, 3.0), ("accent border on a card", pal.accent_ui, GRAPHITE_2, 3.0),
        ("quiet border on void", pal.edge_soft, VOID, 3.0), ("quiet border on graphite", pal.edge_soft, GRAPHITE, 3.0), ("quiet border on a card", pal.edge_soft, GRAPHITE_2, 3.0),
        ("focus ring on void", WHITE, VOID, 3.0), ("focus ring on graphite", WHITE, GRAPHITE, 3.0), ("focus ring on a card", WHITE, GRAPHITE_2, 3.0),
        ("focus ring on a selected row", WHITE, pal.selected_fill, 3.0),
    ]
    return ["%s: %.2f, needs %.1f" % (name, contrast(fg, bg), need) for name, fg, bg, need in pairs if contrast(fg, bg) < need]


# ---------------------------------------------------------------- the choices

@dataclass(frozen=True)
class Look:
    theme: str = DEFAULT_THEME
    accent: int = DEFAULT_ACCENT
    text_pt: int = DEFAULT_TEXT_PT
    scale_pct: int = DEFAULT_SCALE_PCT

    def normalised(self) -> "Look":
        """Anything that is not one of the steps becomes the default for that choice, so a damaged file or an odd value never makes an odd window."""
        return Look(self.theme if self.theme in THEMES else DEFAULT_THEME,
                    self.accent if isinstance(self.accent, int) and not isinstance(self.accent, bool) and 0 <= self.accent < len(ACCENTS) else DEFAULT_ACCENT,
                    self.text_pt if self.text_pt in TEXT_STEPS else DEFAULT_TEXT_PT,
                    self.scale_pct if self.scale_pct in SCALE_STEPS else DEFAULT_SCALE_PCT)

    @property
    def effective_pt(self) -> float:
        return self.text_pt * self.scale_pct / 100.0

    def bigger_text(self) -> "Look":
        return replace(self, text_pt=_step(TEXT_STEPS, self.text_pt, 1))

    def smaller_text(self) -> "Look":
        return replace(self, text_pt=_step(TEXT_STEPS, self.text_pt, -1))

    def bigger_scale(self) -> "Look":
        return replace(self, scale_pct=_step(SCALE_STEPS, self.scale_pct, 1))

    def smaller_scale(self) -> "Look":
        return replace(self, scale_pct=_step(SCALE_STEPS, self.scale_pct, -1))


def _step(steps: Sequence[int], value: int, direction: int) -> int:
    """The next step up or down; the end of the list stays where it is. A value that is not a step is treated as the nearest step below it."""
    index = max([i for i, s in enumerate(steps) if s <= value] or [0])
    return steps[max(0, min(len(steps) - 1, index + direction))]


# ---------------------------------------------------------------- the style sheet

def _n(value: float) -> str:
    return "%g" % round(value, 2)


def _px(value: float, scale: float) -> str:
    return _n(value * scale) + "px"


def _box(cut: float, border: float, edge: str, fill: str, behind: str, scale: float) -> str:
    """The background of a box with a `border` px line all round and the top left and bottom right corners cut `cut` px, made of gradients only: four edge lines, two corner pieces
    (the colour behind the box, then the diagonal line, with soft ends so it does not look jagged) and the fill. No real border is used, so the cut shows. Tested in GTK 4.6.9."""
    c, b = cut * scale, max(1.0, border * scale)
    stripe = b * 1.5                                          # a diagonal drawn at the same width looks thinner than a straight line
    mid = c / math.sqrt(2.0)
    outer, inner = mid - stripe / 2.0 - 0.5, mid + stripe / 2.0 + 0.5

    def piece(angle: int) -> str:
        return "linear-gradient({a}deg, {bh} 0, {bh} {o}px, {e} {o1}px, {e} {i}px, transparent {i1}px)".format(
            a=angle, bh=behind, e=edge, o=_n(outer), o1=_n(outer + 1), i=_n(inner), i1=_n(inner + 1))

    line = "linear-gradient(%s, %s)" % (edge, edge)
    corner = "%spx %spx" % (_n(c + 2 * b), _n(c + 2 * b))      # the cut and a little more, so the corner piece also covers where the straight lines end
    width = "%spx" % _n(b)
    layers = [piece(135), piece(315), line, line, line, line]
    sizes = [corner, corner, "100% " + width, "100% " + width, width + " 100%", width + " 100%"]
    where = ["top left", "bottom right", "top", "bottom", "left", "right"]
    return ("background-color: %s; background-image: %s; background-size: %s; background-position: %s; background-repeat: no-repeat;"
            % (fill, ", ".join(layers), ", ".join(sizes), ", ".join(where)))


def _square(border: float, edge: str, fill: str, scale: float) -> str:
    """A box with a plain line all round and square corners (entries, drop-downs, tick boxes: small things where a cut would only add noise)."""
    return "background-color: %s; background-image: none; border: %s solid %s; border-radius: 0; box-shadow: none;" % (fill, _px(max(1.0, border * scale), 1.0), edge)


def css_for(look: Look) -> str:
    look = look.normalised()
    return _ack_css(look) if look.theme == "ack" else _system_css(look)


def _type_rules(look: Look) -> str:
    """Sizes and type, the same in both themes: no colour in here."""
    s = look.scale_pct / 100.0
    return """
window {{ font-size: {size}pt; }}
.brand {{ font-family: {mono}; font-weight: bold; font-size: 2em; letter-spacing: {ls4}; }}
.tagline {{ font-family: {mono}; font-weight: bold; font-size: 1em; letter-spacing: {ls3}; text-transform: uppercase; }}
.page-heading {{ font-family: {mono}; font-weight: bold; font-size: 1.4em; letter-spacing: {ls2}; text-transform: uppercase; }}
.section-heading {{ font-family: {mono}; font-weight: bold; font-size: 1.15em; letter-spacing: {ls2}; text-transform: uppercase; }}
.round-head {{ font-family: {mono}; font-weight: bold; font-size: 1.05em; }}
.question-text {{ font-weight: bold; font-size: 1.1em; }}
.section-heading {{ margin-top: {m10}; }}
.page-heading {{ margin-bottom: {m4}; }}
.ack-nav row label {{ font-family: {mono}; font-weight: bold; letter-spacing: {ls2}; text-transform: uppercase; }}
button.ack-button label {{ font-family: {mono}; font-weight: bold; letter-spacing: {ls2}; text-transform: uppercase; }}
.result-text {{ padding: {p4}; }}
""".format(size="%g" % round(look.effective_pt, 2), mono=FONT_MONO, ls4=_px(4, s), ls3=_px(3, s), ls2=_px(2, s), p4=_px(4, s), m10=_px(10, s), m4=_px(4, s))


def _system_css(look: Look) -> str:
    """The system's colours and shapes are left alone; only the sizes and the type apply, and the spacing grows with the scale."""
    s = look.scale_pct / 100.0
    return _type_rules(look) + """
.ack-frame {{ padding: {frame}; }}
.ack-header {{ padding: {pad}; }}
.panel {{ padding: {pad}; }}
.row-box {{ padding: {row}; }}
button.ack-button {{ padding: {bv} {bh}; min-height: {bmin}; }}
.ack-nav row {{ padding: {nv} {nh}; }}
progressbar trough {{ min-height: {ph}; }}
""".format(frame=_px(12, s), pad=_px(12, s), row=_px(10, s), bv=_px(6, s), bh=_px(16, s), bmin=_px(28, s), nv=_px(10, s), nh=_px(14, s), ph=_px(14, s))


def _ack_css(look: Look) -> str:
    s = look.scale_pct / 100.0
    pal = palette(look.accent)
    a_text, a_ui, soft = pal.accent_text, pal.accent_ui, pal.edge_soft
    parts = [_type_rules(look)]
    add = parts.append

    add("""
window {{ background-color: {void}; color: {text}; }}
label {{ color: {text}; }}
.brand, .page-heading, .section-heading {{ color: {a_text}; }}
.tagline {{ color: {dim}; }}
.round-head, .question-text {{ color: {text}; }}
.dim-text {{ color: {dim}; }}
.error-text {{ color: {error}; }}
.ack-frame {{ padding: {frame}; }}
.ack-header {{ {head} padding: {hpad}; }}
.ack-page {{ {page} }}
.ack-page > viewport {{ background: none; }}
.panel {{ {panel} padding: {pad}; }}
list.boxed-list {{ background: none; border: none; box-shadow: none; }}
list.boxed-list > row {{ {card} margin: 0 0 {gap} 0; padding: 0; outline: none; }}
list.boxed-list > row:selected {{ {cardsel} }}
.row-box {{ padding: {row}; }}
""".format(void=VOID, text=TEXT, dim=TEXT_DIM, error=ERROR, a_text=a_text, frame=_px(12, s), pad=_px(12, s), hpad=_px(16, s), row=_px(10, s), gap=_px(8, s),
           head=_box(20, 1, a_ui, GRAPHITE, VOID, s), page=_box(12, 1, a_ui, GRAPHITE, VOID, s), panel=_box(8, 1, soft, GRAPHITE, VOID, s),
           card=_box(8, 1, soft, GRAPHITE_2, GRAPHITE, s), cardsel=_box(8, 2, a_ui, pal.selected_fill, GRAPHITE, s)))

    def button_rules(prefix: str, behind: str) -> str:
        base = "%s button.ack-button" % prefix if prefix else "button.ack-button"
        return """
{b} {{ {normal} color: {a_text}; border: none; border-radius: 0; box-shadow: none; outline: none; text-shadow: none; padding: {bv} {bh}; min-height: {bmin}; }}
{b}:hover {{ {hover} }}
{b}:active, {b}:checked {{ {pressed} }}
{b}:focus-visible {{ {focus} color: {white}; }}
{b}:disabled {{ {off} color: {faint}; }}
{b} label {{ color: {a_text}; }}
{b}:focus-visible label, {b}:checked label {{ color: {white}; }}
{b}:disabled label {{ color: {faint}; }}
""".format(b=base, normal=_box(8, 1, a_ui, behind, behind, s), hover=_box(8, 1, a_ui, pal.hover_fill, behind, s), pressed=_box(8, 1, a_ui, pal.selected_fill, behind, s),
           focus=_box(8, 3, WHITE, behind, behind, s), off=_box(8, 1, soft, behind, behind, s), a_text=a_text, faint=TEXT_FAINT, white=WHITE, bv=_px(6, s), bh=_px(16, s), bmin=_px(28, s))

    add(button_rules("", GRAPHITE))
    add(button_rules("list.boxed-list row", GRAPHITE_2))
    add("""
.ack-nav, .ack-nav scrolledwindow, .ack-nav viewport, .ack-nav list {{ background-color: {void}; background-image: none; border: none; box-shadow: none; }}
.ack-nav row label {{ color: {a_text}; }}
.ack-nav row:selected label, .ack-nav row:focus-visible label {{ color: {white}; }}
.ack-nav row {{ color: {a_text}; padding: {nv} {nh}; margin: 0 0 {gap} 0; outline: none; {rest} }}
.ack-nav row:hover {{ {hover} }}
.ack-nav row:selected {{ color: {white}; {sel} }}
.ack-nav row:focus-visible {{ {focus} color: {white}; }}
check, radio {{ background-image: none; background-color: transparent; border: {b1} solid {a_ui}; border-radius: 0; box-shadow: none; color: {void}; min-width: {ind}; min-height: {ind}; -gtk-icon-shadow: none; }}
check:checked, radio:checked {{ background-color: {a_ui}; }}
check:focus-visible, radio:focus-visible {{ outline: {b2} solid {white}; outline-offset: {b1}; }}
checkbutton:focus-visible {{ outline: none; }}
entry, spinbutton {{ {entry} color: {text}; min-height: {emin}; }}
entry:focus-within, spinbutton:focus-within {{ border-color: {white}; outline: {b2} solid {white}; outline-offset: -{b3}; }}
dropdown > button, dropdown button {{ {entry} color: {a_text}; min-height: {emin}; }}
dropdown > button:focus-visible {{ border-color: {white}; outline: {b2} solid {white}; outline-offset: -{b3}; }}
popover contents, popover.background contents {{ background-color: {card}; color: {text}; border: {b1} solid {a_ui}; border-radius: 0; box-shadow: none; }}
popover row {{ color: {text}; }}
popover row:selected, popover row:hover {{ background-color: {sel_fill}; color: {white}; }}
progressbar trough {{ background-color: {rule}; border: none; border-radius: 0; min-height: {ph}; box-shadow: none; }}
progressbar progress {{ background-color: {a_ui}; background-image: none; border: none; border-radius: 0; margin: 0; min-height: {ph}; box-shadow: none; }}
scrollbar slider {{ background-color: {soft}; border-radius: 0; min-width: {sl}; min-height: {sl}; }}
scrollbar slider:hover {{ background-color: {a_ui}; }}
scrollbar trough {{ background-color: transparent; border: none; }}
separator {{ background-color: {rule}; min-height: 1px; min-width: 1px; }}
button.ack-button:focus-visible label {{ color: {white}; }}
window.dialog, window.ack-dialog {{ background-color: {void}; }}
window.ack-dialog .dialog-action-box {{ padding: {pad}; background-color: {void}; }}
window.ack-dialog .dialog-action-area {{ background-color: {void}; }}
window.ack-dialog .dialog-action-area button {{ margin-left: {gap8}; }}
.ack-dialog-body {{ {dialog} padding: {pad}; }}
button.swatch {{ background-image: none; border: {b1} solid {soft}; border-radius: 0; box-shadow: none; padding: 0; min-width: {sw}; min-height: {sw}; outline: none; }}
button.swatch:checked {{ border: {b3} solid {white}; box-shadow: inset 0 0 0 {b2} {void}; }}
button.swatch:focus-visible {{ outline: {b2} solid {white}; outline-offset: {b2}; }}
button.swatch:disabled {{ opacity: 0.35; }}
{swatches}
""".format(void=VOID, a_text=a_text, a_ui=a_ui, white=WHITE, text=TEXT, soft=soft, card=GRAPHITE_2, rule="#2a2a2a", sel_fill=pal.selected_fill,
           nv=_px(10, s), nh=_px(14, s), gap=_px(6, s), gap8=_px(8, s), b1=_px(1, s), b2=_px(2, s), b3=_px(3, s), ind=_px(18, s), emin=_px(34, s), ph=_px(14, s), sl=_px(8, s), pad=_px(16, s), sw=_px(34, s),
           rest=_box(8, 1, soft, VOID, VOID, s), hover=_box(8, 1, a_ui, pal.hover_fill, VOID, s), sel=_box(8, 2, WHITE, pal.selected_fill, VOID, s), focus=_box(8, 3, WHITE, VOID, VOID, s),
           entry=_square(1, soft, VOID, s), dialog=_box(12, 1, a_ui, GRAPHITE, VOID, s),
           swatches="\n".join("button.swatch-%s, button.swatch-%s:hover, button.swatch-%s:checked, button.swatch-%s:disabled { background-color: %s; }" % (name, name, name, name, color) for name, color in ACCENTS)))
    return "".join(parts)
