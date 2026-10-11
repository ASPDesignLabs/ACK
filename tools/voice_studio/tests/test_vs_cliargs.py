# SPDX-License-Identifier: GPL-3.0-or-later
"""Reading the words typed after a terminal command: strict, never guessing, because the commands edit a person's files."""
import pytest

from voice_studio.core.cliargs import ArgError, Parsed, parse_args

FLAGS = {"--yes": "yes", "-y": "yes", "--own": "own"}
VALUES = {"--name": "name", "--hours": "hours", "--project": "project"}


def parse(*argv, max_words=1, flags=FLAGS, values=VALUES):
    return parse_args(list(argv), flags=flags, values=values, max_words=max_words)


def refused(*argv, **kw):
    with pytest.raises(ArgError) as caught:
        parse(*argv, **kw)
    return caught.value.code, caught.value.arg


def test_nothing_typed_is_nothing_found():
    assert parse() == Parsed(frozenset(), {}, ())


def test_flags_values_and_words_are_told_apart_in_any_order():
    parsed = parse("mike", "--yes", "--name", "Anna", "--hours", "1.5")
    assert parsed.flags == {"yes"} and dict(parsed.values) == {"name": "Anna", "hours": "1.5"} and parsed.words == ("mike",)
    assert parse("--name", "Anna", "mike", "--own") == parse("--own", "mike", "--name", "Anna")


def test_a_short_flag_is_the_same_as_its_long_one():
    assert parse("-y").flags == parse("--yes").flags == {"yes"}


def test_a_value_may_be_attached_with_an_equals_sign_and_may_be_empty_or_hold_equals_signs():
    assert dict(parse("--name=Anna").values) == {"name": "Anna"} == dict(parse("--name", "Anna").values)
    assert dict(parse("--name=").values) == {"name": ""} and dict(parse("--name", "").values) == {"name": ""}
    assert dict(parse("--name=a=b").values) == {"name": "a=b"}


def test_a_value_that_starts_with_two_dashes_can_only_be_given_with_an_equals_sign():
    assert refused("--name", "--own") == ("missing_value", "--name")
    assert dict(parse("--name=--own").values) == {"name": "--own"}


def test_a_value_with_one_dash_is_a_value_so_that_a_negative_number_reaches_the_form_to_be_refused_there():
    assert dict(parse("--hours", "-1").values) == {"hours": "-1"} and dict(parse("--name", "-y").values) == {"name": "-y"}


def test_a_value_option_at_the_end_has_no_value():
    assert refused("--name") == ("missing_value", "--name")
    assert refused("mike", "--hours") == ("missing_value", "--hours")


def test_an_option_that_does_not_exist_is_refused_by_its_name():
    assert refused("--nope") == ("unknown", "--nope")
    assert refused("-z") == ("unknown", "-z")
    assert refused("--yes=1") == ("unknown", "--yes=1"), "a yes/no option takes no value"
    assert refused("--nam", "x") == ("unknown", "--nam"), "no abbreviations"


def test_an_option_given_twice_is_refused_so_the_second_never_quietly_wins():
    assert refused("--name", "A", "--name", "B") == ("repeated", "--name")
    assert refused("--name=A", "--name", "B") == ("repeated", "--name")
    assert parse("--yes", "-y", "--yes").flags == {"yes"}, "repeating a yes/no option changes nothing"


def test_more_words_than_the_command_takes_are_refused_by_the_first_extra():
    assert refused("mike", "amy") == ("extra_word", "amy")
    assert refused("a", max_words=0) == ("extra_word", "a")
    assert parse("mike", "--yes", max_words=1).words == ("mike",)
    assert refused("a", "b", "c", max_words=2) == ("extra_word", "c")


def test_a_bare_double_dash_makes_everything_after_it_a_word():
    parsed = parse("--", "--name", "-y", max_words=5)
    assert parsed.words == ("--name", "-y") and parsed.flags == frozenset() and dict(parsed.values) == {}
    assert refused("--", "a", "b") == ("extra_word", "b")


def test_a_single_dash_is_a_word():
    assert parse("-").words == ("-",)


def test_the_error_names_what_was_wrong():
    error = ArgError("unknown", "--x")
    assert (error.code, error.arg) == ("unknown", "--x") and "unknown" in str(error) and "--x" in str(error)
