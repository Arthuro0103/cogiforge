"""quote.py: a quote is in its source when every stretch outside [brackets] and ... is there, as whole words."""
import pytest

import quote

SRC = "Eu nunca disse que queria descansar. A mmulher ama tudo isso, mas ela reclama tudo isso depois."


def test_norm_drops_accents_case_and_punctuation():
    assert quote.norm("  Não, É   AÇÃO!  ") == "nao e acao"


def test_pieces_split_at_brackets_and_ellipses_and_drop_short_ones():
    q = "one two three [sic] four five six ... seven eight nine … ten eleven"
    assert quote.pieces(q) == ["one two three", "four five six", "seven eight nine"]


def test_found_true_when_the_whole_quote_is_there_ignoring_case_and_accent():
    assert quote.found("EU NUNCA disse que queria DESCANSAR", SRC) is True
    assert quote.found("eu nunca disse que queria descansar", SRC.upper()) is True


def test_found_is_whole_word():
    assert quote.found("ama tudo isso", "ele reclama tudo isso") is False
    assert quote.found("ama tudo isso", "ele ama tudo isso sim") is True


def test_two_pieces_one_invented_is_false():
    assert quote.found("eu nunca disse que ... ela ama coisa nenhuma disso", SRC) is False
    assert quote.found("eu nunca disse que ... ama tudo isso, mas ela", SRC) is True


def test_editorial_brackets_are_not_measured():
    assert quote.found("eu nunca disse [that] que queria descansar", SRC) is True


def test_nothing_measurable_is_none_not_true():
    assert quote.found("eu nunca", SRC) is None
    assert quote.found("[all editorial] ... [here too]", SRC) is None
    assert quote.found("", SRC) is None


@pytest.mark.parametrize("sep", ["...", "…"])
def test_both_ellipsis_forms_cut(sep):
    assert quote.found(f"eu nunca disse que {sep} depois", SRC) is True
