# SPDX-License-Identifier: GPL-3.0-or-later
"""What the computer heard against what the voice was asked to say (plan task VS-5.5): by words only, three answers, and a heard text made safe for a screen."""
import pytest

from voice_studio.core import heardcheck as hc


@pytest.mark.parametrize("wanted, heard", [
    ("Hello, my name is Anna.", "hello my name is anna"),
    ("Hello, my name is Anna.", "  HELLO,   my name is ANNA!  "),
    ("I can't, I won't.", "I can’t I won’t"),
    ("Thank you, that is all.", "Thank you. That is all."),
    ("Café time.", "café time"),
    ("Same\nwords here.", "same words   here"),
    ("A fine day.", "A \ufb01ne day"),
])
def test_the_same_words_are_the_same_whatever_the_capitals_punctuation_apostrophe_or_spacing(wanted, heard):
    assert hc.compare(wanted, heard).kind == hc.SAME


@pytest.mark.parametrize("wanted, heard", [
    ("Hello, my name is Anna.", "hello my name is hannah"),
    ("I need some help, please.", "I need help please"),
    ("I need some help, please.", "I need some help, please, thank you"),
    ("Thank you, that is all.", "that is all thank you"),
    ("I need 3 minutes.", "I need three minutes"),
    ("A b.", "ab"),
])
def test_a_missing_extra_reordered_or_respelled_word_is_different(wanted, heard):
    assert hc.compare(wanted, heard).kind == hc.DIFFERENT


@pytest.mark.parametrize("heard", ["", "   ", ".", "...", "\n\t", "-- !!", "_"])
def test_text_with_no_word_in_it_is_nothing_heard(heard):
    check = hc.compare("Hello.", heard)
    assert (check.kind, check.heard) == (hc.NOTHING, "")


def test_an_apostrophe_only_counts_inside_a_word():
    assert hc.words("'quoted' don't") == ("quoted", "don't")
    assert hc.words("rock 'n' roll") == ("rock", "n", "roll")


def test_digits_and_other_scripts_are_words_too():
    assert hc.words("Room 12, été") == ("room", "12", "été")
    assert hc.words("مرحبا بك") == ("مرحبا", "بك")


def test_the_heard_text_is_one_tidy_line_with_nothing_that_could_move_the_cursor():
    check = hc.compare("Hello.", "hello\r\nthere\x1b[2J \x07world x")
    assert check.heard == "hello there [2J world x" and "\x1b" not in check.heard and "\n" not in check.heard


def test_a_very_long_heard_text_is_cut_with_an_ellipsis_at_the_limit():
    text = ("word " * 100).strip()
    shown = hc.for_the_screen(text)
    assert len(shown) == hc.MAX_SHOWN and shown.endswith("…")
    exact = ("w" * hc.MAX_SHOWN)
    assert hc.for_the_screen(exact) == exact and hc.for_the_screen(exact + "w").endswith("…")


def test_the_cut_is_exactly_the_limit_long_whatever_the_text_looks_like():
    assert len(hc.for_the_screen("w" * 500)) == hc.MAX_SHOWN and hc.for_the_screen("w" * 500) == "w" * (hc.MAX_SHOWN - 1) + "\u2026"


@pytest.mark.parametrize("space", ["\u00a0", "\u2003", "\u2028", "\u3000", "\t"])
def test_every_kind_of_white_space_becomes_one_plain_space(space):
    assert hc.for_the_screen("a" + space + space + "b") == "a b"


def test_comparing_never_changes_the_wanted_text_and_gives_back_what_was_heard_cleaned():
    check = hc.compare("Hello, my name is Anna.", "Hello, my name is Anna.")
    assert check == hc.Check(hc.SAME, "Hello, my name is Anna.")
