# SPDX-License-Identifier: GPL-3.0-or-later
"""The phone's list of sounds, in plain Python (plan task VS-5.4): the rule, its edges, and the entries the phone never looks into."""
import json

import pytest

from voice_studio.core import phonemes as ph


def tokens(mapping):
    return ph.tokens_text(json.dumps({"phoneme_id_map": mapping}, ensure_ascii=False))


# ---------------------------------------------------------------- the shape of the file

def test_one_line_per_sound_the_sound_then_a_space_then_its_id_sorted_by_id_ending_with_a_line_break():
    found = tokens({"a": [4], "_": [0], "^": [1], "$": [2], " ": [3]})
    assert found.text == "_ 0\n^ 1\n$ 2\n  3\na 4\n" and found.kept == 5 and found.skipped == ()


def test_the_space_sound_is_written_as_two_spaces_then_its_id_like_the_phone_does():
    assert tokens({" ": [3]}).text == "  3\n"


def test_only_the_first_id_of_an_entry_is_used():
    assert tokens({"a": [9, 10, 11]}).text == "a 9\n"


def test_sounds_with_the_same_id_stay_in_the_order_they_were_written():
    assert tokens({"b": [2], "a": [2], "c": [1]}).text == "c 1\nb 2\na 2\n"


def test_a_negative_id_sorts_first_and_the_edges_of_a_whole_number_are_accepted():
    found = tokens({"a": [2 ** 31 - 1], "b": [-2 ** 31], "c": [0]})
    assert found.text == "b -2147483648\nc 0\na 2147483647\n"


def test_an_empty_map_is_a_file_with_nothing_in_it_not_an_error():
    found = tokens({})
    assert (found.text, found.kept, found.skipped) == ("", 0, ())


# ---------------------------------------------------------------- what the phone leaves out

def test_the_line_break_entry_is_left_out_and_is_not_counted_as_a_skipped_sound():
    found = tokens({"\n": [7], "a": [4]})
    assert found.text == "a 4\n" and found.skipped == ()


def test_a_sound_of_more_than_one_character_is_left_out_and_named():
    found = tokens({"e": [5], "eɪ": [7], "aɪ": [8], "oʊ": [9]})
    assert found.text == "e 5\n" and found.skipped == ("eɪ", "aɪ", "oʊ") and found.kept == 1


def test_exactly_one_unicode_character_is_kept_even_when_it_takes_two_places_in_the_phones_text_type():
    smile = "\U0001F600"                                   # one Unicode character, a surrogate pair on Android: the phone counts code points, so it stays
    assert tokens({smile: [3]}).text == smile + " 3\n"


def test_a_letter_with_a_separate_accent_is_two_characters_and_is_left_out_but_the_single_accented_letter_stays():
    assert tokens({"é": [3], "é": [4]}).text == "é 4\n"


def test_an_empty_name_is_not_one_character_and_is_left_out():
    found = tokens({"": [3], "a": [4]})
    assert found.text == "a 4\n" and found.skipped == ("",)


def test_a_carriage_return_is_one_character_and_is_not_the_line_break_the_phone_leaves_out():
    assert tokens({"\r": [3]}).text == "\r 3\n"


# ---------------------------------------------------------------- like the phone, an entry is looked into only after the others are gone

@pytest.mark.parametrize("skipped_symbol", ["\n", "eɪ", ""])
def test_a_broken_entry_on_a_sound_the_phone_leaves_out_does_not_matter(skipped_symbol):
    assert tokens({skipped_symbol: "not a list", "a": [4]}).text == "a 4\n"


@pytest.mark.parametrize("bad", [[], "5", None, [None], [True], [1.5], [5.0], ["5"], [2 ** 31], [-2 ** 31 - 1], {"x": 1}])
def test_a_kept_sound_whose_entry_has_no_whole_number_first_is_refused(bad):
    with pytest.raises(ph.TokensError) as caught:
        tokens({"a": bad})
    assert caught.value.code == "bad_entry"


def test_a_sound_that_cannot_be_written_is_refused_not_turned_into_a_question_mark():
    with pytest.raises(ph.TokensError) as caught:
        ph.tokens_text('{"phoneme_id_map": {"\\ud83d": [3]}}')
    assert caught.value.code == "bad_entry"


# ---------------------------------------------------------------- the file as a whole

@pytest.mark.parametrize("text, code", [("", "not_json"), ("{", "not_json"), ("[1, 2]", "no_map"), ("{}", "no_map"), ('{"phoneme_id_map": []}', "no_map"),
                                        ('{"phoneme_id_map": "x"}', "no_map"), ('{"phoneme_id_map": null}', "no_map"), ("null", "no_map")])
def test_a_settings_file_with_no_map_is_refused_with_the_reason(text, code):
    with pytest.raises(ph.TokensError) as caught:
        ph.tokens_text(text)
    assert caught.value.code == code


def test_a_file_nested_far_too_deep_is_refused_as_not_json_and_does_not_crash():
    with pytest.raises(ph.TokensError) as caught:
        ph.tokens_text("[" * 100000)
    assert caught.value.code == "not_json"


@pytest.mark.parametrize("symbol", ["q", "é", "\U0001F600"])
def test_the_error_is_one_fixed_sentence_and_never_carries_the_sound_itself(symbol):
    with pytest.raises(ph.TokensError) as caught:
        tokens({symbol: []})
    assert caught.value.detail == "an entry has no whole number to sort by" and symbol not in str(caught.value)


def test_the_same_settings_file_always_gives_the_same_text():
    mapping = {"a": [4], "b": [5], "eɪ": [6], "\n": [7], " ": [3]}
    assert tokens(mapping) == tokens(mapping)


def test_every_error_code_has_words_in_the_catalog():
    from voice_studio.core.text import load_catalog
    cat = load_catalog("en")
    for code in ph.ERROR_CODES:
        for part in ("what", "changed", "next"):
            assert cat.t("phonemes.error.%s.%s" % (code, part)) != "phonemes.error.%s.%s" % (code, part), (code, part)
