#!/usr/bin/env python3
"""quote.py: is a quoted phrase really in the text it claims to come from? Stdlib only.

A quote is allowed to be edited in three honest ways: `[an editorial insertion]` in square brackets, an
ellipsis (`...` or the one-character form) where words were cut, and differences of case, accent or
punctuation. Everything else has to be there. So the quote is split at the brackets and the ellipses, and
EVERY remaining piece must appear in the text, as whole words (`loves all this` is not inside
`gloves all this`). A piece with fewer than 3 words proves nothing (a common word is everywhere), so it is
not measured. If no piece can be measured, the answer is "I do not know" (None), never "yes".
"""
import re
import unicodedata

MIN_WORDS = 3
CUT = re.compile(r"\[[^\]]*\]|\.\.\.|…")


def norm(s):
    """NFKD, accents removed, every run of non-word characters becomes one space, lower case."""
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return re.sub(r"\W+", " ", s).lower().strip()


def pieces(quote):
    """The normalized stretches of the quote between editorial brackets and ellipses, 3+ words each."""
    return [p for p in (norm(x) for x in CUT.split(quote)) if len(p.split()) >= MIN_WORDS]


def found(quote, text):
    """None: nothing measurable. True: every piece is in `text` as whole words. False: some piece is not."""
    ps = pieces(quote)
    if not ps:
        return None
    hay = " " + norm(text) + " "
    return all(" " + p + " " in hay for p in ps)


def _plain(s):
    """NFC, casefold, runs of whitespace collapsed to one space. Nothing else is removed: an accent, a punctuation mark
    or a symbol that differs makes the text differ (lookalike letters such as the circled or regional ones too)."""
    return re.sub(r"\s+", " ", unicodedata.normalize("NFC", s)).casefold().strip()


def _word_at(text, i, n):
    """The match at text[i:i+n] starts and ends at a word boundary."""
    before = text[i - 1] if i > 0 else ""
    after = text[i + n] if i + n < len(text) else ""
    return not (before and (before.isalnum() or before == "_")) and not (after and (after.isalnum() or after == "_"))


def found_whole(quote, text):
    """The WHOLE phrase (NFC, casefold, whitespace collapsed, nothing else removed) as whole words in the text: no
    brackets and no ellipsis exception (for memory lines). None if the phrase has fewer than 3 words."""
    n, hay = _plain(quote), _plain(text)
    if len(n.split()) < MIN_WORDS:
        return None
    i = hay.find(n)
    while i != -1:
        if _word_at(hay, i, len(n)):
            return True
        i = hay.find(n, i + 1)
    return False


def found_ordered(quote, text):
    """For `citation.py --quotes`: every piece of the quote (`[...]` and `...` split it; ANY size, one word is
    enough) must appear in the text, in the SAME ORDER, as whole words. None if the quote has no piece."""
    ps = [p for p in (norm(x) for x in CUT.split(quote)) if p]
    if not ps:
        return None
    hay = " " + norm(text) + " "
    pos = 0
    for p in ps:
        i = hay.find(" " + p + " ", pos)
        if i == -1:
            return False
        pos = i + len(p) + 1
    return True
