"""quote.py: a quote is in its source when every stretch outside [brackets] and ... is there, as whole words."""
import pytest

import quote

SRC = "I never said I wanted to rest. She loves all this, but he gloves all this later."


def test_norm_drops_accents_case_and_punctuation():
    assert quote.norm("  Caf\u00e9, NA\u00cfVE   action!  ") == "cafe naive action"


def test_pieces_split_at_brackets_and_ellipses_and_drop_short_ones():
    q = "one two three [sic] four five six ... seven eight nine … ten eleven"
    assert quote.pieces(q) == ["one two three", "four five six", "seven eight nine"]


def test_found_true_when_the_whole_quote_is_there_ignoring_case_and_accent():
    assert quote.found("I NEVER said I wanted to REST", SRC) is True
    assert quote.found("i never said i wanted to rest", SRC.upper()) is True


def test_found_is_whole_word():
    assert quote.found("loves all this", "he gloves all this") is False
    assert quote.found("loves all this", "she loves all this yes") is True


def test_two_pieces_one_invented_is_false():
    assert quote.found("i never said i ... she loves nothing at all", SRC) is False
    assert quote.found("i never said i ... loves all this, but he", SRC) is True


def test_editorial_brackets_are_not_measured():
    assert quote.found("i never said [that] i wanted to rest", SRC) is True


def test_nothing_measurable_is_none_not_true():
    assert quote.found("i never", SRC) is None
    assert quote.found("[all editorial] ... [here too]", SRC) is None
    assert quote.found("", SRC) is None


@pytest.mark.parametrize("sep", ["...", "…"])
def test_both_ellipsis_forms_cut(sep):
    assert quote.found(f"i never said i {sep} later", SRC) is True
