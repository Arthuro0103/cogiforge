#!/usr/bin/env python3
"""citation.py: does the source exist, and does it say what was claimed? Stdlib only.

    python3 tools/citation.py <file.md>                 check every URL, arXiv id and DOI in the file
    python3 tools/citation.py <file.md> --no-network    form only: nothing can be better than NOT_VERIFIED
    python3 tools/citation.py <file.md> --json
    python3 tools/citation.py --quotes NOTE.md          quotes of 5+ words against the vault file linked on the same line
    python3 tools/citation.py --selftest                proves the tool in both directions, offline

A citation that was invented does not look wrong, it looks like a citation: an id with the right shape, a
plausible title, plausible authors, and a paper that does not exist. The reader cannot know which of the
hundred to open. This tool opens each one and gives one of four states:

  VERIFIED      the source opened AND every number the sentence claims appears, whole, on the page
                (an arXiv id: it exists and the real title shares words with the sentence)
  PARTIAL       the source opened, but the claim was not found, or the source only proves it exists
                (a DOI resolves; an endpoint answered 401/403/405 to a GET). It may be a legitimate
                paraphrase or an invention, and only a human eye can tell. The most useful state.
  NOT_VERIFIED  it could not be checked: no network, no answer, a server error, or a sentence with no
                number to compare. This is "I do not know", never an approval.
  BROKEN        the source does not exist: the page answered 404/410, the arXiv id has no entry, the DOI
                has no handle. This is the case of the invented arXiv.

A line that has a web link AND a quote of 5+ words in quotation marks (straight, curly, guillemets or single
curly; nested ones are each checked) is also checked word for word against THE PAGE LINKED ON THAT LINE, never
any other source. `...`, `\u2026` and `[an editorial insertion]` may sit between stretches; every stretch must be on
the page, as whole words, in the SAME ORDER. Case, quotation marks, dash style, invisible characters, markdown
emphasis and the punctuation at the edges of a stretch are ignored; words, accents and inner punctuation are not.

  VERIFIED      every quote is literally on the page (and every number of the sentence, if it claims any)
  PARTIAL       a quote was NOT found (a translation, a paraphrase, text a script builds, or an invention), or it
                was found but has an editorial insertion, or a quotation mark on the line is never closed
  NOT_VERIFIED  the quote could not be judged: the page was not read (any status but 2xx; 404 and 410 stay
                BROKEN), is truncated, larger than the tool reads or not UTF-8, or no stretch has 3+ words

With a quote and numbers on the same line, the worst of the two results wins. A line with a quote but no web link,
and a line inside a fenced code block, are not checked by this rule. With several links on a line the quote is
looked for on each page, and the note says so.

What the quote rule does not do: it does not read other quotation styles (straight single quotes, low opening
quotes, corner brackets), count words in text written without spaces, join a quote split over two lines (the
unpaired mark caps that line at PARTIAL), or look at DOI and arXiv items. It does not check what an elision cuts
nor how far apart the stretches are. It reads the page's markup, not the rendered page: hidden elements count,
two paragraphs read as one run of words, and a server that declares no length and closes early looks whole.

The idea comes from the "quote-integrity" rule of jordan-gibbs/hyperresearch (MIT). Two of its gaps are closed
here: it accepted the text from any source, and it knew only straight and curly double quotes.

--quotes is the offline sibling: a line of the note that has a link to a file of the vault (`[[path]]` or
`[text](path.md)`) and a quote of 5+ words in double quotes (straight or curly) is checked with core/quote.py
against THAT file: VERIFIED (every stretch, of any size, is there and in the SAME ORDER; `[brackets]` and `...` are
allowed between them), BROKEN (some stretch is missing or out of order), NOT_VERIFIED (no link on the line, the file does not exist or is outside `--vault` (default `vault`), or nothing in the quote is measurable).

A number is found only as a WHOLE number: `86` does not match `1986` or `860`; `77,6` and `77.6` are the
same; a number with `%` needs `%` or the word percent next to it. That the number is on the page does not
prove it supports the sentence, so every number found comes back with the page text around it, for the eye.

rc: 0 every citation VERIFIED · 1 at least one BROKEN · 2 usage · 3 NOT_VERIFIED (some citation could not
be checked, or the file has none, or it could not be read; this never counts as OK) · 4 at least one
PARTIAL and nothing worse. The worst state wins: 1, then 3, then 4.
"""
from __future__ import annotations

import argparse
import html
import json
import re
import http.client
import ipaddress
import socket
import ssl
import sys
import threading
import time
import unicodedata
import urllib.error
import urllib.request
from pathlib import Path
from typing import Callable
from urllib.parse import quote, unquote, urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "core"))
import quote as quotelib  # noqa: E402

TIMEOUT = 10          # per socket operation: a slow drip beats it, so MAX_SECONDS bounds the whole fetch
MAX_SECONDS = 15
MAX_BYTES = 400_000
MAX_REDIRECTS = 3
MAX_FETCHES = 50      # citations opened in one run; the rest stay NOT_VERIFIED
MAX_TOTAL_SECONDS = 300  # wall clock of the whole run
MAX_FILE_BYTES = 1_000_000
REFUSED = -1          # fetch status: the address is not a public web host, so it was not requested
UA = "cogiforge-citation/1.0 (reads a page to check a citation)"

VERIFIED, PARTIAL, NOT_VERIFIED, BROKEN = "VERIFIED", "PARTIAL", "NOT_VERIFIED", "BROKEN"
SEVERITY = {BROKEN: 0, NOT_VERIFIED: 1, PARTIAL: 2, VERIFIED: 3}  # print order: the worst first

Fetch = Callable[[str], "tuple[int, str]"]

RE_MD_LINK = re.compile(r"\[([^\]]{0,200})\]\((https?://[^\s)`]+)\)")
RE_BARE_URL = re.compile(r"(?<![\(\]])\bhttps?://[^\s<>\")\]`]+")
RE_ARXIV = re.compile(r"\barXiv[:\s]*(\d{4}\.\d{4,5})(v\d+)?\b", re.I)
RE_DOI = re.compile(r"\b(10\.\d{4,9}/[-._;()/:A-Za-z0-9]+)\b")
# 1 to 3 digits, optional decimal, optional %. A 4-digit run (a year) never matches as a claim.
RE_NUMBER = re.compile(r"(?<![\w.,])\d{1,3}(?:[.,]\d+)?%?(?!\d)")
RE_ANY_URL = re.compile(r"https?://\S+")
RE_DATE = re.compile(r"\b\d{4}-\d{2}-\d{2}\b|\b\d{1,2}/\d{1,2}(?:/\d{2,4})?\b")
PERCENT_WORD = r"\s*(?:%|percent|per\s*cent|percentage\s+points?)"


_GLOBAL_UNICAST_V6 = ipaddress.ip_network("2000::/3")


def public_ip(ip) -> bool:
    """False for anything that is, or embeds, a non-public IPv4: the plain `is_global` lets NAT64 and
    IPv4-compatible forms of 127.0.0.1 through."""
    if ip.version == 6:
        if ip.ipv4_mapped is not None:
            return public_ip(ip.ipv4_mapped)
        if ip.sixtofour is not None:
            return public_ip(ip.sixtofour)
        if ip.teredo is not None:
            return all(public_ip(a) for a in ip.teredo)
        # A denylist keeps missing forms (SIIT ::ffff:0:a.b.c.d, site-local fec0::/10, ::/96): allow only
        # global unicast (2000::/3), after the embedded-IPv4 forms above were unwrapped. NAT64 64:ff9b::/96 is outside it, so it is refused.
        if ip not in _GLOBAL_UNICAST_V6:
            return False
    return ip.is_global and not ip.is_multicast


def allowed_url(url: str) -> bool:
    """Cheap pre-filter, no DNS: http(s) only, and an IP literal must be public. A NAME is checked where the
    connection is made (`connect_pinned`), on the very address that is then used."""
    try:
        parts = urlsplit(url)
        host = parts.hostname
    except ValueError:
        return False
    if parts.scheme not in ("http", "https") or not host:
        return False
    try:
        return public_ip(ipaddress.ip_address(host))
    except ValueError:
        return True  # a name


class Page(str):
    """The text of a response. `unread` says why it is not the whole page as sent: a quote cannot be judged then."""
    unread = ""


def read_body(raw: bytes, status: int, missing: "int | None") -> Page:
    """`raw` holds one byte more than the limit when the page is too large. `missing`: declared bytes that never came."""
    why = ""
    if len(raw) > MAX_BYTES:
        why = f"the page is larger than the {MAX_BYTES} bytes this tool reads"
    elif missing or status == 206:
        why = "the page came truncated"
    raw = raw[:MAX_BYTES]
    try:
        page = Page(raw.decode("utf-8"))
    except UnicodeDecodeError:
        page = Page(raw.decode("utf-8", errors="replace"))
        why = why or "the page is not valid UTF-8"
    page.unread = why
    return page


class Refused(OSError):
    """The address is not a public web host."""


def connect_pinned(host: str, port: int, timeout: float) -> socket.socket:
    """Resolve ONCE, refuse unless every address is public, and connect to one of those exact addresses.
    Validating one lookup and connecting by name would resolve twice, and a hostile DNS can answer
    differently the second time (rebinding)."""
    infos = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    if not infos:
        raise OSError("no address")
    for info in infos:
        try:
            ip = ipaddress.ip_address(info[4][0].split("%")[0])
        except ValueError:
            raise Refused("unreadable address") from None
        if not public_ip(ip):
            raise Refused(f"{host} resolves to a non-public address")
    last: "OSError | None" = None
    for family, kind, proto, _canon, addr in infos:
        sock = socket.socket(family, kind, proto)
        try:
            sock.settimeout(timeout)
            sock.connect(addr)
            return sock
        except OSError as e:
            sock.close()
            last = e
    raise last or OSError("could not connect")


class _PinnedHTTP(http.client.HTTPConnection):
    def connect(self) -> None:
        self.sock = connect_pinned(self.host, self.port, self.timeout)


class _PinnedHTTPS(http.client.HTTPSConnection):
    def connect(self) -> None:
        raw = connect_pinned(self.host, self.port, self.timeout)
        self.sock = self._context.wrap_socket(raw, server_hostname=self.host)


class _HTTPHandler(urllib.request.HTTPHandler):
    def http_open(self, req):
        return self.do_open(_PinnedHTTP, req)


class _HTTPSHandler(urllib.request.HTTPSHandler):
    def https_open(self, req):
        return self.do_open(_PinnedHTTPS, req, context=self._context)


class _GuardedRedirect(urllib.request.HTTPRedirectHandler):
    """Every hop is checked, not only the first URL: a public page can redirect to an internal address."""
    max_redirections = MAX_REDIRECTS

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not allowed_url(newurl):
            raise urllib.error.URLError(Refused("redirect to an address that is not a public web host"))
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _opener() -> urllib.request.OpenerDirector:
    """No proxy handler: a pinned connection must go straight to the address it validated."""
    o = urllib.request.OpenerDirector()
    for h in (urllib.request.ProxyHandler({}), _HTTPHandler(), _HTTPSHandler(context=ssl.create_default_context()),
              _GuardedRedirect(), urllib.request.HTTPDefaultErrorHandler(), urllib.request.HTTPErrorProcessor(),
              urllib.request.UnknownHandler()):
        o.add_handler(h)
    return o


def _fetch(url: str) -> "tuple[int, str]":
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    deadline = time.monotonic() + MAX_SECONDS
    try:
        with _opener().open(req, timeout=TIMEOUT) as r:
            chunks, got = [], 0
            while got <= MAX_BYTES:  # one byte past the limit tells "too large" from "exactly the limit"
                if time.monotonic() > deadline:
                    return 0, ""
                block = r.read(min(16_384, MAX_BYTES + 1 - got))
                if not block:
                    break
                chunks.append(block)
                got += len(block)
            return r.status, read_body(b"".join(chunks), r.status, getattr(r, "length", None))
    except urllib.error.HTTPError as e:
        return e.code, ""
    except urllib.error.URLError as e:
        return (REFUSED, "") if isinstance(e.reason, Refused) else (0, "")
    except Refused:
        return REFUSED, ""
    except Exception:  # noqa: BLE001 - any failure to get an answer is "no answer"
        return 0, ""


def fetch_http(url: str) -> "tuple[int, str]":
    """(status, text). Status 0 means no answer at all (no network, DNS, TLS, timeout);
    REFUSED means the address was not public and nothing was requested. The whole fetch, DNS included,
    has a wall-clock bound: TIMEOUT is per socket operation, so a slow drip alone would hold it."""
    if not allowed_url(url):
        return REFUSED, ""
    box: list = []
    worker = threading.Thread(target=lambda: box.append(_fetch(url)), daemon=True)
    worker.start()
    worker.join(MAX_SECONDS + TIMEOUT)
    return box[0] if box else (0, "")


def clean(text: str) -> str:
    """Remote and document text reaches a terminal and an agent: control, format and bidi characters become '?'."""
    return "".join("?" if unicodedata.category(c) in ("Cc", "Cf", "Cs", "Co", "Cn", "Zl", "Zp") else c for c in str(text))


_TAG_NAME = re.compile(r"(/?)([A-Za-z][A-Za-z0-9]*)")
_END_RAW = {"script": re.compile(r"</script", re.I), "style": re.compile(r"</style", re.I)}


def visible_text(page: str, glue: "frozenset[str]" = frozenset(), unclosed: "list | None" = None) -> str:
    """One pass, linear in the input. Neither the regex (`<[^>]+>` rescans to the end from every '<') nor
    html.parser (quadratic on repeated `<a `, `<script `, `<!--`) is safe on a page this tool did not write.
    An unclosed tag, comment or <script> swallows the rest: what it hides is not evidence of anything, and
    its start is appended to `unclosed`. A tag named in `glue` vanishes without leaving a space."""
    parts: list[str] = []
    i, n = 0, len(page)
    while i < n:
        j = page.find("<", i)
        if j < 0:
            parts.append(page[i:])
            break
        parts.append(page[i:j])
        if page.startswith("<!--", j):
            k = page.find("-->", j + 4)
            if k < 0:
                if unclosed is not None:
                    unclosed.append(j)
                break
            parts.append(" ")
            i = k + 3
            continue
        m = _TAG_NAME.match(page, j + 1)
        if not m:
            parts.append("<")  # a literal '<' (a < b)
            i = j + 1
            continue
        k = page.find(">", m.end())
        if k < 0:
            if unclosed is not None:
                unclosed.append(j)
            break
        name = m.group(2).lower()
        glued = name in glue and (page[m.end()] in "/>" or page[m.end()].isspace())  # <a-card> is not <a>
        parts.append("" if glued else " ")
        i = k + 1
        if not m.group(1) and name in _END_RAW:
            close = _END_RAW[name].search(page, i)
            if close is None:
                if unclosed is not None:
                    unclosed.append(j)
                break
            i = close.start()
    return " ".join("".join(parts).split())


def extract(text: str) -> list[dict]:
    """Every citation with the sentence (line) it lives in."""
    found: list[dict] = []
    seen: set = set()
    for n, line in enumerate(text.split("\n"), 1):
        ctx = line.strip()
        for m in RE_MD_LINK.finditer(line):
            url = m.group(2).rstrip(".,;")
            if (url, n) not in seen:
                seen.add((url, n))
                found.append({"kind": "url", "target": url, "line": n, "context": ctx})
        for m in RE_BARE_URL.finditer(line):
            url = m.group(0).rstrip(".,;`")
            if (url, n) not in seen:
                seen.add((url, n))
                found.append({"kind": "url", "target": url, "line": n, "context": ctx})
        for m in RE_ARXIV.finditer(line):
            found.append({"kind": "arxiv", "target": m.group(1), "line": n, "context": ctx})
        for m in RE_DOI.finditer(line):
            found.append({"kind": "doi", "target": m.group(1), "line": n, "context": ctx})
    return found


def claimed_numbers(context: str) -> list[str]:
    """The numbers that carry the sentence. A date is a stamp, not a claim, and URL digits are not either."""
    clean = RE_DATE.sub(" ", RE_ANY_URL.sub(" ", context))
    return RE_NUMBER.findall(clean)[:6]


def _forms(n: str) -> set[str]:
    base = n.rstrip("%")
    return {base, base.replace(",", "."), base.replace(".", ",")}


def _find(n: str, page: str):
    suffix = PERCENT_WORD if n.endswith("%") else ""
    for f in sorted(_forms(n)):
        m = re.search(r"(?<![\d.,])" + re.escape(f) + r"(?!\d|[.,]\d)" + suffix, page, re.I)
        if m:
            return m
    return None


def number_on_page(n: str, page: str) -> bool:
    """The WHOLE number is on the page, not as a piece of another number."""
    return _find(n, page) is not None


def _around(n: str, page: str) -> str:
    m = _find(n, page)
    return ("..." + page[max(0, m.start() - 55):m.end() + 55].strip() + "...") if m else ""


def check_numbers(context: str, page: str) -> "tuple[str, str]":
    """VERIFIED only if EVERY claimed number is on the page, whole. Otherwise PARTIAL, saying which are missing."""
    numbers = claimed_numbers(context)
    if not numbers:
        return NOT_VERIFIED, "opened, but the sentence claims no number to compare"
    hit = [n for n in numbers if number_on_page(n, page)]
    miss = [n for n in numbers if n not in hit]
    around = " | ".join(f"{n}: {_around(n, page)}" for n in hit)
    if not miss:
        return VERIFIED, f"every number is on the page, whole -> {around}"
    if hit:
        return PARTIAL, f"found {hit} but NOT {miss} (whole, on the page) -> {around}"
    return PARTIAL, f"opened, but NOT found {numbers} (whole, on the page)"


# ---- a quote on a line with a web link: is it literally on THAT page? -----------------------------

QUOTE_MIN_WORDS = 5       # a shorter quote is a term, not a claim (--quotes uses the same floor)
MAX_NESTING = 20          # quotation marks open at once on one line
MAX_LINE_QUOTES = 20      # quotes judged per line; the rest make the line NOT_VERIFIED
INLINE_TAGS = frozenset("a abbr b cite code del dfn em font i ins kbd mark q s samp small span strong time u var wbr".split())

_MARKS = '"\u201c\u201d\u00ab\u00bb\u2018\u2019'
_RE_LINK_LABEL = re.compile(r"""\[([^\[\]]{0,500})\]\(\s{0,9}(?:[^\s()]|\([^\s()]*\)){0,2000}"""
                            r"""(?:\s{1,9}(?:"[^"]{0,500}"|'[^']{0,500}'))?\s{0,9}\)""")
# A real tag, with attributes shaped like attributes: in `a <= b`, `<- x` or `a <b and "c" > d` nothing is a tag.
_RE_LINE_TAG = re.compile(r"""</?([A-Za-z][A-Za-z0-9-]*)(?:\s+[^\s<>"'=/]+(?:\s*=\s*(?:"[^"<>]*"|'[^'<>]*'|[^\s<>"']+))?)*"""
                          r"""\s*/?>""")
_RE_LINE_URL = re.compile(r"https?://[^\s\"\u201c\u201d\u00ab\u00bb<>]+")
_RE_CODE_SPAN = re.compile(r"`+[^`]*`+")
_RE_EMPHASIS = re.compile(r"(?<![\w*])(\*{1,3}|_{1,3})(?!\1|\s)(.{1,300}?)(?<!\s)\1(?![\w*])")
_ELLIPSIS = r"(?:\.\.\.|\u2026)"
# An elision only cuts words. Anything else in square brackets is the writer speaking, and it takes the letters
# glued to it along: in `[T]he study` the edited word is not compared.
_RE_CUT = re.compile(rf"(?P<elision>\[ ?{_ELLIPSIS} ?\]|\( ?{_ELLIPSIS} ?\)|{_ELLIPSIS})"
                     rf"|(?P<insert>(?:(?<!\w)\w+)?\[(?! ?{_ELLIPSIS} ?\])[^\[\]]*\]\w*)")
_RE_PAGE_MARKS = re.compile("(?<=\\w)(['\u2018\u2019\u02bc])(?=\\w)|[\"'\u201c\u201d\u201e\u201f\u00ab\u00bb\u2018\u2019\u201a\u201b\u2039\u203a\u02bc]")
_CHARS = {**{ord(c): None for c in "\u00ad\u200b\u200c\u200d\u2060\ufeff"}, 0x2010: "-", 0x2011: "-"}
_RE_RANGE_DASH = re.compile(r"(?<=\d)\u2013(?=\d)")
_RE_DASH = re.compile(r" ?[\u2012\u2013\u2014\u2015] ?| --? ")  # runs after whitespace is collapsed
_EDGES = " ,;:.!?\u2014"


def _words(text: str) -> int:
    return sum(1 for w in text.split() if any(c.isalnum() for c in w))


def fenced_lines(text: str) -> "set[int]":
    """Numbers of the lines inside ``` or ~~~ blocks, fences included. Only a fence of the same kind closes one."""
    inside, fence = set(), ""
    for n, line in enumerate(text.split("\n"), 1):
        m = re.match(r"\s{0,3}(`{3,}|~{3,})(.*)", line)
        if fence:
            inside.add(n)
            if m and m.group(1).startswith(fence) and not m.group(2).strip():
                fence = ""
        elif m:
            inside.add(n)
            fence = m.group(1)
    return inside


def line_quotes(line: str) -> "tuple[list[str], bool]":
    """(the quotes of 5+ words on a line, at every depth of nesting; True if a mark that may delimit 5+ words
    is never matched). Link targets, link titles, HTML tags, URLs and marks inside `code` do not quote anything."""
    line = _RE_LINK_LABEL.sub(r"\1", line)
    line = _RE_LINE_TAG.sub(lambda m: "" if m.group(1).lower() in INLINE_TAGS else " ", line)
    # a closing single quote glued to a URL stays on the line
    line = _RE_LINE_URL.sub(lambda m: " " + m.group(0)[len(m.group(0).rstrip("\u2018\u2019")):], line)
    mask = _RE_CODE_SPAN.sub(lambda m: re.sub(f"[{_MARKS}]", " ", m.group(0)), line)  # same length as `line`
    stack: "list[tuple[str, int]]" = []
    quotes: "list[str]" = []
    openers: "list[int]" = []  # opening marks nothing closed
    closers: "list[int]" = []  # closing marks nothing opened
    plural = False             # a single quote closed right after an `s`: it may have been a plural apostrophe

    def push(mark: str, at: int) -> None:
        if len(stack) < MAX_NESTING:
            stack.append((mark, at + 1))
        else:
            openers.append(at)

    def close(marks: str, at: int) -> bool:
        for j in range(len(stack) - 1, -1, -1):
            if stack[j][0] in marks:
                openers.extend(start - 1 for _, start in stack[j + 1:])
                quotes.append(line[stack[j][1]:at])
                del stack[j:]
                return True
        return False

    for i, ch in enumerate(mask):
        if ch not in _MARKS:
            continue
        before, after = mask[i - 1] if i else "", mask[i + 1:i + 2]
        if ch in "\u2018\u2019" and before.isalnum() and after.isalnum():
            continue  # an apostrophe inside a word
        if ch in "\u201c\u00ab\u2018":
            push(ch, i)
        elif ch == '"':
            if before.isdigit() and not any(m in '"\u201c' for m, _ in stack):
                continue  # inches: 13"
            starts = bool(after.strip())
            if starts and (not before or before.isspace() or before in "([{\u201c\u00ab\u2018"):
                push(ch, i)
            elif not close('"\u201c', i):
                if starts:
                    push(ch, i)
                else:
                    closers.append(i)
        elif ch == "\u201d":
            if not close('"\u201c', i):
                closers.append(i)
        elif ch == "\u00bb":
            close("\u00ab", i)  # a loose one is a breadcrumb
        elif not after.isalnum():  # the closing single quote
            if close("\u2018", i):
                plural = plural or before in ("s", "S")
            elif plural:
                closers.append(i)
    openers.extend(start - 1 for _, start in stack)
    unmatched = bool(openers and _words(line[min(openers) + 1:]) >= QUOTE_MIN_WORDS
                     or closers and _words(line[:max(closers)]) >= QUOTE_MIN_WORDS)
    unique = dict.fromkeys(q.strip() for q in quotes)
    return [q for q in unique if _words(q) >= QUOTE_MIN_WORDS], unmatched


def literal(text: str) -> str:
    """The form in which a quote and a page are compared. Entities are decoded; case, quotation marks, dash style,
    invisible characters and runs of space are leveled. An apostrophe inside a word, accents and punctuation stay."""
    s = unicodedata.normalize("NFC", html.unescape(text)).translate(_CHARS)
    s = _RE_PAGE_MARKS.sub(lambda m: "'" if m.group(1) else "", s)
    s = _RE_RANGE_DASH.sub("-", " ".join(s.split()))
    return _RE_DASH.sub(" \u2014 ", s).casefold()


def split_quote(text: str) -> "tuple[list[str], bool, bool]":
    """(the stretches to find, in order; has an elision; has an editorial insertion)."""
    text = _RE_EMPHASIS.sub(r"\2", _RE_EMPHASIS.sub(r"\2", text.replace("`", "")))
    parts, last, elided, inserted = [], 0, False, False
    for m in _RE_CUT.finditer(text):
        parts.append(text[last:m.start()])
        last = m.end()
        elided = elided or m.group("elision") is not None
        inserted = inserted or m.group("insert") is not None
    parts.append(text[last:])
    stretches = [literal(p).strip(_EDGES) for p in parts]
    return [s for s in stretches if any(c.isalnum() for c in s)], elided, inserted


def _word_char(c: str) -> bool:
    return bool(c) and (c.isalnum() or c == "_" or unicodedata.category(c).startswith("M"))


def _cuts(edge: str, near: str, far: str) -> bool:
    """A match ending in `edge` cuts a word or a number that goes on through `near`, then `far`."""
    if _word_char(near):
        return True
    if near in "-\u2212" and edge.isdigit() and (not far or far.isspace() or far in "(["):
        return True  # a minus sign: 5 is not -5
    if not far:
        return False
    if near in "'-":
        return _word_char(edge) and _word_char(far)  # well-known, John's
    return near in ".," and edge.isdigit() and far.isdigit()  # 3.5


def in_order(stretches: "list[str]", page: str) -> bool:
    """Every stretch is on the page as whole words, each one after the end of the one before it."""
    pos = 0
    for s in stretches:
        i = page.find(s, pos)
        while i != -1:
            j = i + len(s)
            left = page[max(0, i - 2):i]
            if not _cuts(s[0], left[-1:], left[:-1]) and not _cuts(s[-1], page[j:j + 1], page[j + 1:j + 2]):
                break
            i = page.find(s, i + 1)
        if i == -1:
            return False
        pos = i + len(s)
    return True


def _shown(text: str) -> str:
    return f'"{text[:70]}{"..." if len(text) > 70 else ""}"'


def check_page_quotes(quotes: "list[str]", status: int, body: str) -> "tuple[str, str]":
    """The quotes of one line against one response. A page that was not read whole never says "not found"."""
    def unjudged(why: str) -> "tuple[str, str]":
        return NOT_VERIFIED, f"quote NOT checked: {why}"

    if not 200 <= status < 300:
        return unjudged("the page was not read" + (f" (status {status})" if status > 0 else ""))
    why = getattr(body, "unread", "")
    if why:
        return unjudged(why)
    unclosed: list = []
    try:
        page = literal(visible_text(body, INLINE_TAGS, unclosed))
    except Exception:  # noqa: BLE001 - e.g. a numeric entity with thousands of digits
        return unjudged("the page could not be parsed")
    if unclosed:
        return unjudged("the page ends inside a tag, a comment or a script, so part of it was not read")
    if not page:
        return unjudged("the page has no readable text")

    results: "list[tuple[str, str]]" = []
    any_elision = False
    for q in quotes[:MAX_LINE_QUOTES]:
        stretches, elided, inserted = split_quote(q)
        any_elision = any_elision or elided
        if not any(_words(s) >= quotelib.MIN_WORDS for s in stretches):
            results.append(unjudged(f"no stretch of {_shown(q)} has {quotelib.MIN_WORDS}+ words, too little to prove anything"))
        elif not in_order(stretches, page):
            results.append((PARTIAL, f"quote NOT found literally on this page: {_shown(q)} (a translation, a paraphrase, "
                                     "text a script builds, or an invention: check by hand)"))
        elif inserted:
            results.append((PARTIAL, f"quote found, but it has an editorial insertion in [brackets]: check {_shown(q)} by hand"))
        else:
            results.append((VERIFIED, ""))
    if len(quotes) > MAX_LINE_QUOTES:
        results.append(unjudged(f"only the first {MAX_LINE_QUOTES} quotes of a line are judged"))
    state = min((s for s, _ in results), key=SEVERITY.__getitem__)
    notes = [n for _, n in sorted(results, key=lambda r: SEVERITY[r[0]]) if n]
    if state == VERIFIED:
        notes = [f"every quote ({len(results)}) is literally on the page"]
    if any_elision:
        notes.append("what an elision cuts is not checked")
    return state, "; ".join(notes)


def apply_quotes(out: dict, status: int, body: str) -> None:
    """Adds the quote rule to the result of one web link. A line with no quote of 5+ words is left untouched."""
    quotes, unmatched = line_quotes(out["context"])
    if out["state"] == BROKEN or not (quotes or unmatched):
        return
    if quotes:
        state, note = check_page_quotes(quotes, status, body)
        if 200 <= status < 300 and not claimed_numbers(out["context"]):
            out.update(state=state, note=note)  # no number was claimed: the quote is the whole check
        else:
            out.update(state=min(out["state"], state, key=SEVERITY.__getitem__), note=f"{note}; {out['note']}")
        pages = len({i["target"] for i in extract(out["context"]) if i["kind"] == "url"})
        if pages > 1:
            out["note"] += f"; the line links {pages} pages and each is searched alone: the quote may be from another"
    if unmatched:
        out["state"] = min(out["state"], PARTIAL, key=SEVERITY.__getitem__)
        out["note"] += "; a quotation mark on this line has no pair, so check the quoted text by hand"


def check_one(item: dict, fetch: "Fetch | None", read_quotes: bool = True) -> dict:
    """One citation -> the same dict plus `state` and `note`. `fetch=None` is the no-network mode.
    `read_quotes=False` skips the quote rule (a line of code is not quoting anyone)."""
    out = dict(item, state=NOT_VERIFIED, note="")
    if fetch is None:
        out["note"] = "no network: the form was read, the content was not"
        return out

    if item["kind"] == "arxiv":
        status, body = fetch(f"https://export.arxiv.org/api/query?id_list={item['target']}")
        if status != 200 or not body:
            out["note"] = f"the arXiv API did not answer (status {status}): cannot tell if the id exists"
            return out
        total = re.search(r"totalResults[^>]*>(\d+)<", body)
        entry = re.search(r"<entry>(.*?)</entry>", body, re.S)
        if (total and total.group(1) == "0") or not entry:
            out.update(state=BROKEN, note="the arXiv id has no entry: it does NOT exist")
            return out
        t = re.search(r"<title>(.*?)</title>", entry.group(1), re.S)
        title = " ".join(t.group(1).split()) if t else ""
        words = re.findall(r"\w{4,}", title.lower())[:8]
        if not words:
            out["note"] = f"it exists, but the title has no word to compare: {title[:70]!r}"
            return out
        ctx = item["context"].lower()
        hits = sum(1 for w in words if w in ctx)
        need = min(2, len(words)) if len(words) <= 3 else max(2, len(words) // 3)
        out["real_title"] = title
        if hits >= need:
            out.update(state=VERIFIED, note=f"the title matches: {title[:70]}")
        else:
            out.update(state=PARTIAL, note=f"it EXISTS, but the real title is: {title[:70]}")
        return out

    if item["kind"] == "doi":
        if ".." in item["target"]:
            out["note"] = "the DOI has a '..' segment: not a handle, not requested"
            return out
        status, body = fetch(f"https://doi.org/api/handles/{quote(item['target'], safe='/')}")
        if status == 200 and '"responseCode":1' in body.replace(" ", ""):
            out.update(state=PARTIAL, note="the DOI resolves; what the sentence claims was not checked")
        elif status in (404, 410):
            out.update(state=BROKEN, note=f"the DOI has no handle (status {status})")
        else:
            out["note"] = f"the DOI service did not settle it (status {status})"
        return out

    status, body = fetch(item["target"])
    if status == REFUSED:
        out["note"] = "not requested: the address is not a public web host (local, private, link-local or not http/https)"
    elif status == 0:
        out["note"] = "no answer (network down or host gone): cannot say the page is broken"
    elif status in (401, 403, 405):
        # A POST-only or authenticated endpoint answers like this to a GET. That is the wrong verb,
        # not an invented citation: calling it BROKEN would be a false alarm, and false alarms kill trust.
        out.update(state=PARTIAL, note=f"answered {status} to a GET: probably a POST-only or authenticated endpoint")
    elif status in (404, 410):
        out.update(state=BROKEN, note=f"does not exist (status {status})")
    elif status >= 400:
        out["note"] = f"answered {status}: the server could not settle it, which is not proof it is gone"
    else:
        try:
            page = visible_text(body)
        except Exception:  # noqa: BLE001 - a page the parser chokes on is "could not check", not a verdict
            out["note"] = f"opened (status {status}), but the page could not be parsed"
            return out
        out["state"], out["note"] = check_numbers(item["context"], page)
        if out["state"] == NOT_VERIFIED:
            out["note"] = f"opened (status {status}), but the sentence claims no number to compare"
    if read_quotes:
        apply_quotes(out, status, body)
    return out


def exit_code(results: list[dict]) -> int:
    """Typed and worst-wins. No citation at all is NOT_VERIFIED, not clean: nothing was touched."""
    states = {r["state"] for r in results}
    if BROKEN in states:
        return 1
    if NOT_VERIFIED in states or not results:
        return 3
    if PARTIAL in states:
        return 4
    return 0


def check_text(text: str, fetch: "Fetch | None") -> list[dict]:
    results, opened, start = [], 0, time.monotonic()
    code = fenced_lines(text)
    for item in extract(text):
        if fetch is not None and time.monotonic() - start > MAX_TOTAL_SECONDS:
            results.append(dict(item, state=NOT_VERIFIED,
                                note=f"the {MAX_TOTAL_SECONDS}-second budget of one run is used up: run again for the rest"))
            continue
        if fetch is not None and opened >= MAX_FETCHES:
            results.append(dict(item, state=NOT_VERIFIED,
                                note=f"over the {MAX_FETCHES}-fetch limit of one run: split the file and run again"))
            continue
        if fetch is not None:
            opened += 1
        results.append(check_one(item, fetch, item["line"] not in code))
    return results


def read_text(path: Path) -> str:
    """Read UTF-8 and compare with the size on disk: a short read is an error, never a clean file."""
    expected = path.stat().st_size
    if expected > MAX_FILE_BYTES:
        raise OSError(f"{path} has {expected} bytes, over the {MAX_FILE_BYTES} limit")
    raw = path.read_bytes()
    if expected > 0 and len(raw) != expected:
        raise OSError(f"short read of {path}: {len(raw)} of {expected} bytes")
    return raw.decode("utf-8", errors="replace")


RE_QUOTE = re.compile(r"\"([^\"\n]+)\"|\u201c([^\u201d\n]+)\u201d")
RE_VAULT_LINK = re.compile(r"\[\[([^\[\]\n|#^]+)(?:[#^][^\[\]\n|]*)?(?:\|[^\[\]\n]*)?\]\]|(?<!!)\[[^\]\n]*\]\(([^)\s#]+)(?:#[^)\s]*)?\)")


def resolve_link(note: Path, target: str, vault: "Path | None" = None) -> "tuple[Path | None, bool]":
    """(file, outside): the file a vault link points to, looking relative to the note and then to each folder above
    it. A file that resolves outside the vault is never returned: `outside` is True and the quote stays NOT_VERIFIED."""
    target = unquote(target).strip().replace("\\", "/")
    if not target or re.match(r"[a-z][a-z0-9+.-]*:", target, re.I):
        return None, False
    vroot = (vault if vault is not None else Path("vault")).resolve()
    names = [target] if target.lower().endswith(".md") else [target + ".md", target]
    here = note.resolve().parent
    outside = False
    for base in [here, *here.parents]:
        for n in names:
            c = base / n
            if c.is_file():
                try:
                    c.resolve().relative_to(vroot)
                except ValueError:
                    outside = True
                    continue
                return c, False
    return None, outside


def check_quotes(text: str, note: Path, vault: "Path | None" = None) -> list[dict]:
    """One result per quote of 5+ words, judged against the vault file(s) linked on the same line."""
    results = []
    in_fence = False
    for ln, line in enumerate(text.split("\n"), 1):
        if re.match(r"^\s{0,3}(```|~~~)", line):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        quotes = [m.group(1) or m.group(2) for m in RE_QUOTE.finditer(line)]
        quotes = [q for q in quotes if len(q.split()) >= QUOTE_MIN_WORDS]
        if not quotes:
            continue
        resolved = [resolve_link(note, m.group(1) or m.group(2), vault) for m in RE_VAULT_LINK.finditer(line)]
        files = [f for f, _ in resolved if f]
        outside = any(o for _, o in resolved)
        has_link = bool(RE_VAULT_LINK.search(line))
        for q in quotes:
            item = dict(kind="quote", target=q, line=ln, context=line.strip(), note="")
            if not has_link:
                item.update(state=NOT_VERIFIED, note="no link to a vault file on this line, so there is no source to open")
            elif not files:
                item.update(state=NOT_VERIFIED, note="the linked file is outside the vault, so it is not a source" if outside
                            else "the linked file does not exist or is not a vault file")
            else:
                verdicts = []
                for f in files:
                    try:
                        verdicts.append(quotelib.found_ordered(q, f.read_bytes().decode("utf-8", errors="replace")))
                    except OSError:
                        verdicts.append(None)
                if any(v is True for v in verdicts):
                    item.update(state=VERIFIED, note=f"every stretch is in {files[0].name}" if len(files) == 1 else "every stretch is in a linked file")
                elif any(v is False for v in verdicts):
                    item.update(state=BROKEN, note="a stretch of the quote is not in the linked file")
                else:
                    item.update(state=NOT_VERIFIED, note="nothing to compare in the quote (every stretch is inside [brackets] or empty) or the file could not be read")
            results.append(item)
    return results


def render(path: str, results: list[dict], what: str = "external citation") -> str:
    if not results:
        return (f"{path}: no {what} found.\n"
                "NOT_VERIFIED: nothing was checked, and that is not an approval (the text may be missing its sources).")
    lines = []
    for r in sorted(results, key=lambda x: (SEVERITY[x["state"]], x["line"])):
        lines.append(f"{r['state']:<13} L{r['line']:<5} {r['kind']:<6} {r['target'][:72]}")
        if r["note"]:
            lines.append(f"{'':<13}   {r['note']}")
    counts = {s: sum(1 for r in results if r["state"] == s) for s in SEVERITY}
    lines.append("-" * 78)
    lines.append("  ".join(f"{s}={n}" for s, n in counts.items()))
    if counts[BROKEN]:
        lines.append("BROKEN is the invented-citation case: check by hand before publishing.")
    if counts[NOT_VERIFIED]:
        lines.append("NOT_VERIFIED is NOT OK: it means 'I do not know'.")
    return "\n".join(lines)


def selftest() -> int:
    """Both directions, with a scripted fetch: no network is touched, so it runs anywhere."""
    bad: list[str] = []

    def expect(label: str, got, want) -> None:
        if got != want:
            bad.append(f"{label}: got {got!r}, wanted {want!r}")

    kinds = sorted(i["kind"] for i in extract("see [x](https://example.com/a) and arXiv:2401.12345 and 10.1000/xyz123\nplain line\n"))
    expect("extraction", kinds, ["arxiv", "doi", "url"])
    expect("a line with no citation yields none", [i for i in extract("a\nplain line\n") if i["line"] == 2], [])

    page = "In 1986 a total of 860 people; the system wins 77.6% of the time (46.875 Hz floor) with 20 trials"
    for n, want in [("86%", False), ("86", False), ("77,6%", True), ("77.6%", True), ("46,875", True), ("20", True), ("2", False), ("77", False)]:
        expect(f"number_on_page({n})", number_on_page(n, page), want)
    expect("a wrong number is PARTIAL", check_numbers("the rate was 86% on 02/10", page)[0], PARTIAL)
    expect("all numbers right is VERIFIED", check_numbers("the rate was 77,6% with 20 trials", page)[0], VERIFIED)
    expect("one right and one wrong is PARTIAL", check_numbers("the rate was 77,6% with 14 trials", page)[0], PARTIAL)
    expect("no number is NOT_VERIFIED", check_numbers("it is a fine source", page)[0], NOT_VERIFIED)
    expect("a date is not a claim", claimed_numbers("on 02/10 and 2026-10-02, 86%"), ["86%"])

    arxiv_ok = ("<feed><opensearch:totalResults>1</opensearch:totalResults><entry>"
                "<title>Attention Is All You Need</title></entry></feed>")
    arxiv_none = "<feed><opensearch:totalResults>0</opensearch:totalResults></feed>"
    script = {
        "export.arxiv.org/api/query?id_list=1706.03762": (200, arxiv_ok),
        "export.arxiv.org/api/query?id_list=2401.99999": (200, arxiv_none),
        "export.arxiv.org/api/query?id_list=2401.00001": (503, ""),
        "doi.org/api/handles/10.1000/real": (200, '{"responseCode": 1}'),
        "doi.org/api/handles/10.1000/fake": (404, '{"responseCode":100}'),
        "example.test/page": (200, "<html><body><p>The system wins 77.6% of the time.</p><script>999</script></body></html>"),
        "example.test/gone": (404, ""),
        "example.test/post": (405, ""),
        "example.test/down": (0, ""),
        "example.test/error": (500, ""),
    }

    def fake(url: str) -> "tuple[int, str]":
        return script.get(url.split("://", 1)[1], (0, ""))

    def state(kind, target, context):
        return check_one({"kind": kind, "target": target, "line": 1, "context": context}, fake)["state"]

    expect("invented arXiv", state("arxiv", "2401.99999", "a paper"), BROKEN)
    expect("real arXiv, title matches", state("arxiv", "1706.03762", "the Attention Is All You Need paper"), VERIFIED)
    expect("real arXiv, other subject", state("arxiv", "1706.03762", "a study of free range hens"), PARTIAL)
    expect("arXiv API down is not BROKEN", state("arxiv", "2401.00001", "x"), NOT_VERIFIED)
    expect("DOI that resolves is only PARTIAL", state("doi", "10.1000/real", "x"), PARTIAL)
    expect("DOI with no handle", state("doi", "10.1000/fake", "x"), BROKEN)
    expect("page with the number", state("url", "https://example.test/page", "it won 77,6% [s](https://example.test/page)"), VERIFIED)
    expect("page without the number", state("url", "https://example.test/page", "it won 41% of trials"), PARTIAL)
    expect("a number only inside <script> does not count", state("url", "https://example.test/page", "it was 999"), PARTIAL)
    expect("404", state("url", "https://example.test/gone", "x 5"), BROKEN)
    expect("405 to a GET", state("url", "https://example.test/post", "x 5"), PARTIAL)
    expect("no answer is not BROKEN", state("url", "https://example.test/down", "x 5"), NOT_VERIFIED)
    expect("500 is not BROKEN", state("url", "https://example.test/error", "x 5"), NOT_VERIFIED)
    said = '"the system wins 77.6% of the time"'
    expect("a quote that is on the page", state("url", "https://example.test/page", said), VERIFIED)
    expect("a quote that is not on the page", state("url", "https://example.test/page", said.replace("wins", "loses")), PARTIAL)
    expect("a quote against a dead page stays BROKEN", state("url", "https://example.test/gone", said), BROKEN)
    expect("a quote against a page nobody read", state("url", "https://example.test/post", said), NOT_VERIFIED)

    for kind, target in (("url", "https://example.test/page"), ("arxiv", "1706.03762"), ("doi", "10.1000/real")):
        expect(f"--no-network never approves ({kind})",
               check_one({"kind": kind, "target": target, "line": 1, "context": "77.6%"}, None)["state"], NOT_VERIFIED)

    def r(*states):
        return [{"state": s} for s in states]
    expect("rc all VERIFIED", exit_code(r(VERIFIED)), 0)
    expect("rc BROKEN wins", exit_code(r(VERIFIED, PARTIAL, NOT_VERIFIED, BROKEN)), 1)
    expect("rc NOT_VERIFIED beats PARTIAL", exit_code(r(PARTIAL, NOT_VERIFIED)), 3)
    expect("rc PARTIAL", exit_code(r(VERIFIED, PARTIAL)), 4)
    expect("rc with no citation is 3, not 0", exit_code([]), 3)

    if bad:
        for b in bad:
            print(f"FAILED: {b}")
        return 1
    print("selftest OK: invented arXiv=BROKEN, real=VERIFIED, wrong subject=PARTIAL, dead page=BROKEN,")
    print("             no answer=NOT_VERIFIED, --no-network never approves, whole-number matching, typed rc,")
    print("             a quote is looked for on the linked page")
    return 0


def main(argv: "list[str] | None" = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("file", nargs="?")
    ap.add_argument("--no-network", action="store_true", help="read the form only; every citation is NOT_VERIFIED")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--vault", default="vault", help="with --quotes: the only folder a link may resolve into (default: vault)")
    ap.add_argument("--quotes", metavar="NOTE.md", help="check quotes of 5+ words against the vault file linked on the same line")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args(argv)

    if args.selftest:
        return selftest()
    if args.quotes and args.file:
        ap.error("give either a file or --quotes NOTE.md, not both")
    if not args.file and not args.quotes:
        ap.error("give a file, or use --quotes NOTE.md, or --selftest")  # rc 2

    path = Path(args.quotes or args.file)
    try:
        text = read_text(path)
    except OSError as e:
        print(f"NOT_VERIFIED: could not read {path} ({e})")
        return 3
    results = check_quotes(text, path, Path(args.vault)) if args.quotes else check_text(text, None if args.no_network else fetch_http)
    shown = [{k: (clean(v) if isinstance(v, str) else v) for k, v in r.items()} for r in results]
    if args.json:
        print(json.dumps({"file": clean(str(path)), "citations": shown}, ensure_ascii=False, indent=2))
    else:
        print(render(clean(str(path)), shown, "quote with a link" if args.quotes else "external citation"))
    return exit_code(results)


if __name__ == "__main__":
    sys.exit(main())
