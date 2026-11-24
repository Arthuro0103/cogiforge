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


def found_whole(quote, text):
    """The WHOLE phrase, normalized, as whole words: no brackets and no ellipsis exception (for memory lines).
    None if the phrase has fewer than 3 words, so nothing can be measured."""
    n = norm(quote)
    if len(n.split()) < MIN_WORDS:
        return None
    return " " + n + " " in " " + norm(text) + " "
