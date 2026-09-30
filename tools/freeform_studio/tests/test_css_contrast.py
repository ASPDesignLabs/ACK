"""Guards the accessibility of the color choices: text/background pairs must meet WCAG AA in light AND dark."""
import re
from pathlib import Path

CSS = (Path(__file__).resolve().parents[1] / "static" / "app.css").read_text()


def tokens(block):
    return dict(re.findall(r"--([a-z-]+):\s*(#[0-9a-fA-F]{6})", block))


def luminance(hex_color):
    def chan(v):
        v /= 255
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    r, g, b = (int(hex_color[i:i + 2], 16) for i in (1, 3, 5))
    return 0.2126 * chan(r) + 0.7152 * chan(g) + 0.0722 * chan(b)


def ratio(a, b):
    la, lb = sorted((luminance(a), luminance(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def themes():
    light = tokens(re.search(r":root\s*\{(.*?)\}", CSS, re.S).group(1))
    dark = {**light, **tokens(re.search(r"prefers-color-scheme: dark\)\s*\{\s*:root\s*\{(.*?)\}", CSS, re.S).group(1))}
    return {"light": light, "dark": dark}


# (foreground, background, minimum ratio): 4.5 for normal text, 3 for focus rings / large UI
PAIRS = [("text", "bg", 4.5), ("text", "surface", 4.5), ("muted", "surface", 4.5), ("muted", "bg", 4.5),
         ("accent-text", "accent", 4.5), ("danger-text", "danger", 4.5), ("ok", "surface", 4.5),
         ("danger", "surface", 4.5), ("text", "warn-bg", 4.5), ("focus", "bg", 3.0), ("focus", "surface", 3.0)]


def test_every_text_pair_meets_wcag_aa_in_both_themes():
    for name, t in themes().items():
        for fg, bg, need in PAIRS:
            got = ratio(t[fg], t[bg])
            assert got >= need, f"{name}: {fg} on {bg} is {got:.2f}:1, needs {need}:1"


def test_no_inline_styles_or_scripts_are_needed_by_the_page():
    html = (Path(__file__).resolve().parents[1] / "static" / "index.html").read_text()
    assert "<style" not in html and " style=" not in html
    assert not re.search(r"<script(?![^>]*\bsrc=)", html) and " onclick=" not in html
