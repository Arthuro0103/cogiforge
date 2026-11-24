#!/usr/bin/env python3
"""memory.py: a line of `vault/memory/` is what the user said, and the hook proves it. Stdlib only.

    memory.py [--vault vault] [--root .] [--staged] [--json] [FILE ...]

Why it exists: rule 2 says a line enters `vault/memory/` only with the user's "yes", a date and the verbatim
phrase. Nothing used to check it. And the memory is the one thing every later session OBEYS: a line planted
there (an instruction that looks like a quote, or a hidden character that a reader cannot see) becomes an
instruction of every session after it. Poisoned memory is a risk measured in research of Nov 2026, and a
template that keeps memory in a file all sessions obey has to refuse an instruction and invisible text there.

THREAT MODEL (the owner's decision). The gate catches text that an agent copies into the memory from OUTSIDE (a
web page, a file, a tool output) and careless entries. It is NOT a jail. An agent with a shell can run
`git commit --no-verify` or edit the hook; rule 6 forbids it, and the hook cannot stop it. Known limits: a source
file committed in an EARLIER commit of the same session counts as earlier, and so does one joined by `--amend`,
because the hook cannot know who wrote it; and the gate proves that the words are in the source file, not WHO said
them (tool output pasted inside an imported chat counts as that chat).

PRINCIPLE: a list of what is FORBIDDEN always leaks, so in a memory file (every .md under memory/) the rule is a
list of what is ALLOWED: printable ASCII, tab, LF (CR only right before LF), letters, decimal digits, punctuation,
symbols (Sm, Sc, Sk, So) and the plain space U+0020; a combining mark (Mn, Mc) only in a line that is in NFC. Anything
else fails, and so do the circled and regional "decorative letters" (U+1F100-1F1FF, U+2460-24FF) and the invisible
characters (also the Hangul fillers, which are letters). In the OTHER files an agent loads the forbidden list stays,
widened with the unassigned code points and the default-ignorable ones, with a few narrow exceptions.

A memory file with ENTRIES is a `.md` directly in `vault/memory/` or in `vault/people/<handle>/memory/` (team
mode), except `observations.md` (where the model PROPOSES: no shape, date or source check). Paths are classified
with casefold (`vault/MEMORY/profile.md` is memory, `.MD` is `.md`). After the `Format of each line:` line only
an entry or the EXACT pointer line `tools/cool.py` leaves behind may appear (a `#` title is a failure there);
a trailing CR (CRLF files) is accepted. An entry is

    YYYY-MM-DD | "verbatim phrase" | where | stale_after: YYYY-MM-DD | superseded_by: YYYY-MM-DD

(straight or curly quotes; the last two fields are optional and a later piece reads them). The line is read by
`parse_entry`, in linear time (a regex with a nested repeat was exponential). `ENTRY.match(line)` still works: it
returns None, or an object with `.group(1..4)` and `.groups()` (date, phrase, where, the text of the final fields);
`FIELD.findall(group4)` returns the `(key, value)` pairs of the final fields.

The checks:
  shape      after the format line: only entries, the cool pointer and blank lines; the marker must exist              blocks
  date       the entry date is a real date and not after tomorrow; so are the dates of the final fields                blocks
  source     `where` is a file of the vault holding the WHOLE phrase (NFC, casefold, whitespace collapsed, and NOTHING
             else removed: a different accent, mark or symbol is a different phrase; whole words; no `[...]` or `...`
             exception: that is only for tools/citation.py --quotes). `where` must be its own normalized path (no `..`,
             `.`, `//`, or trailing slash). Not found blocks. A source that resolves outside
             `vault/`, or inside a memory folder (a memory cannot vouch for a memory, any case), blocks. `where` is not
             a file (`chat`): NOT_VERIFIED, blocking only with `memory-source: block`. With --staged the source is
             decided by HEAD and the index, never by the disk: it must be a regular blob in HEAD, no component of its
             path a symlink there, and not deleted by this commit. A source born in this commit is NOT_VERIFIED
             ("commit the source first"), never verified                                                              blocks / warns
  hidden     in a memory file (every .md under memory/, recursively): only the ALLOWED list. In every other file a
             session loads (CLAUDE.md, AGENTS.md, AGENTS.override.md, GEMINI.md and CLAUDE.local.md anywhere in the
             repo, .github/copilot-instructions.md, every file under a `.claude/`, `.agents/`, `.cursor/` or `.gemini/`
             folder at any depth, and the files a CLAUDE.md imports with `@path`, up to 5 levels, inside the repo):
             every category Cf, Co, Cn and Cc (but tab, LF, and CR right before LF), U+2028, U+2029, U+2800, the
             default-ignorable ranges and the fillers and selectors in HIDDEN_EXTRA. file:line:column and the code
             point. Fine: a BOM at the start of the file. Outside memory only: a non-ASCII space (Zs) fails except
             one NBSP/NNBSP alone between two non-space characters; one FE0E/FE0F after So, Sk, a non-ASCII Sm/Pd/Po
             or U+2139/24C2/3297/3299; a keycap; a ZWJ between two emoji bases (skin tones and non-ASCII Sm count) or
             after an Indic virama; a ZWNJ between two letters of the same Arabic block or after an Indic virama; one
             IVS after a CJK ideograph; the three RGI flags England, Scotland and Wales written with tag characters
             (any other tag spells hidden ASCII). A run of two or more invisibles stays a failure                      always blocks
  reach      a URL, a domain with a common TLD and a slash, `www.`, or a shell-looking command (curl, wget, | sh,
             | bash, git push, --no-verify, rm -rf, chmod +x, sudo/eval in backticks) on ANY line of a .md under
             memory/, the header and titles included                                                                   warns
  header     (--staged) the text above and including the format line changed against HEAD, or the memory file is
             new                                                                                                       warns
  unreadable a memory or loaded file that does not open or is not valid UTF-8 is a failure, not a pass                   blocks
  symlink    a symlink, or anything else that is not a regular file (a submodule, mode 160000), in place of a loaded
             path or of a folder above one (vault, memory, people/<x>, .claude...)                                    blocks
`reach` and `header` block with `memory-reach: block` in vault/gate.txt. With --staged the commit is judged by
the STRICTER of the gate.txt in HEAD and the one in the index (loosening only counts from the next commit, and a
loosened key prints a WARNING); absent = defaults; a BOM at the start of gate.txt is ignored.

rc: 0 clean, or only warnings / NOT_VERIFIED · 1 a check that blocks failed · 2 usage, or vault/gate.txt malformed ·
3 git did not say what is staged (the hook BLOCKS on 3: the gate never passes blind). With --staged the candidates
and their modes come from the git index and the content judged is the INDEX content, read by blob sha (`git ls-files -s` then `git cat-file blob`), never by a
revision-style path such as `:0:docs/CLAUDE.md`.
"""
from __future__ import annotations

import argparse
import json
import os
import posixpath
import re
import subprocess
import sys
import unicodedata
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import gate  # noqa: E402
import quote  # noqa: E402

Failure = gate.Failure

CHECKS = [
    ("shape", "after the format line only entries and the cool pointer"),
    ("date", "the dates are real and not in the future"),
    ("source", "the whole phrase is in the file it cites, and that file is not a memory or outside the vault"),
    ("hidden", "no invisible character in a file a session loads"),
    ("reach", "no URL or shell command in a memory file"),
    ("header", "the header above the format line did not change"),
    ("unreadable", "a memory or loaded file opens and is valid UTF-8"),
    ("symlink", "no symlink in place of a loaded path"),
]
MARKER = "Format of each line:"
# EXACTLY what tools/cool.py writes (`- [[memory/archive/<stem>|<n> older entries, moved word for word on <date>]]`), the whole line.
POINTER = re.compile(r"^- \[\[memory/archive/[A-Za-z0-9._-]+\|\d+ older entries, moved word for word on \d{4}-\d{2}-\d{2}\]\]$")


class _Parsed:
    """What ENTRY.match returns: .group(1..4) = date, phrase, where, text of the final fields; .groups()."""

    def __init__(self, groups: tuple):
        self._g = groups

    def group(self, n: int = 1) -> str:
        return self._g[n - 1]

    def groups(self) -> tuple:
        return self._g


_DATE10 = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")
_KEY = re.compile(r"\w+")


def _parse_tail(tail: str):
    """`where | key: value | key: value` (what follows the closing quote and its bar) -> (where, final fields text) or None."""
    parts = tail.split("|")
    for part in parts[1:]:
        raw, sep, _ = part.partition(":")
        if not sep or raw.strip() != raw.lstrip() or not _KEY.fullmatch(raw.strip()):
            return None
    return parts[0].strip(), ("|" + "|".join(parts[1:]) if len(parts) > 1 else "")


def parse_entry(line: str):
    """The entry of a memory line, in linear time: `YYYY-MM-DD | "phrase" | where [| key: value ...]`, optional
    bullet, straight or curly quotes. None if the line is not shaped like that. The closing quote is the RIGHTMOST
    quote character that is followed by a bar and a tail that parses (the old regex, without its nested repeat)."""
    s = line.lstrip()
    if s[:1] in ("-", "*") and s[1:2].isspace():
        s = s[1:].lstrip()
    if not _DATE10.fullmatch(s[:10]):
        return None
    d, rest = s[:10], s[10:].lstrip()
    if not rest.startswith("|"):
        return None
    rest = rest[1:].lstrip()
    if rest[:1] not in ('"', "\u201c"):
        return None
    body = rest[1:]
    k = len(body)
    while True:
        k = max(body.rfind('"', 0, k), body.rfind("\u201d", 0, k))
        if k < 0:
            return None
        tail = body[k + 1:].lstrip()
        if tail.startswith("|"):
            got = _parse_tail(tail[1:])
            if got:
                return _Parsed((d, body[:k], got[0], got[1]))


class _EntryMatcher:
    """Keeps the public name ENTRY: `ENTRY.match(line)` -> None or a match with `.group(n)` (see parse_entry)."""

    @staticmethod
    def match(line: str):
        return parse_entry(line)


class _FieldMatcher:
    """Keeps the public name FIELD: `FIELD.findall(text)` -> [(key, value), ...] of the final fields."""

    @staticmethod
    def findall(text: str) -> list:
        out = []
        for part in text.split("|")[1:]:
            key, _, value = part.partition(":")
            out.append((key.strip(), value.strip()))
        return out


ENTRY = _EntryMatcher()
FIELD = _FieldMatcher()
FIELD_KEYS = ("stale_after", "superseded_by")
ISO = re.compile(r"^\d{4}-\d{2}-\d{2}$")
REACH = re.compile(
    r"https?://|\bwww\.|\bcurl\s|\bwget\s|\|\s*(?:sh|bash)\b|\bgit\s+push\b|--no-verify|\brm\s+-rf|chmod\s+\+x"
    r"|\b[a-z0-9-]{1,63}\.(?:com|net|org|io|dev|sh|app|xyz|ru|cn|info|me)/"
    r"|`[^`\n]*(?:\bcurl\b|\bwget\b|\brm\s|\bsudo\b|\beval\b)[^`\n]*`", re.I)
MODES = ("warn", "block")
LOADED_NAMES = ("claude.md", "agents.md", "claude.local.md", "agents.override.md", "gemini.md")
IMPORTERS = ("claude.md", "claude.local.md")
AGENT_DIRS = (".claude", ".agents", ".cursor", ".gemini")
REGULAR = ("100644", "100755")
SKIP_DIRS = {".git", "node_modules", ".venv", "venv", "__pycache__", ".pytest_cache"}

# Hidden text: every character of Unicode category Cf (zero-width, bidi controls, soft hyphen, BOM, tag characters...),
# Co (private use), Cn (unassigned) and Cc (control, except tab, LF and a CR right before LF), plus these, which are
# none of those: the line and paragraph separators, the Braille blank, Hangul fillers, the combining grapheme joiner,
# Khmer inherent vowels, Mongolian selectors, the variation selectors (U+FE00-FE0F, U+E0100-E01EF) and the rest of the
# Unicode default-ignorable code points.
HIDDEN_EXTRA = ((0x034F, 0x034F), (0x115F, 0x1160), (0x2028, 0x2029), (0x2800, 0x2800), (0x3164, 0x3164),
                (0xFFA0, 0xFFA0), (0x17B4, 0x17B5), (0x180B, 0x180F), (0xFE00, 0xFE0F), (0xE0000, 0xE0FFF),
                (0x2060, 0x206F), (0xFFF0, 0xFFF8), (0x1BCA0, 0x1BCA3), (0x1D173, 0x1D17A))
ZWJ, ZWNJ, VS15, VS16, BOM, KEYCAP, BLANK = "\u200d", "\u200c", "\ufe0e", "\ufe0f", "\ufeff", "\u20e3", "\u2800"
ARABIC = ((0x0600, 0x06FF), (0x0750, 0x077F), (0xFB50, 0xFDFF), (0xFE70, 0xFEFF))
EMOJI_SELECTOR_OK = "\u2139\u24c2\u3297\u3299"


class Unreadable(Exception):
    pass


def gate_modes(vault: Path, text: str | None = ..., ) -> dict:
    """{"memory-source": mode, "memory-reach": mode} from vault/gate.txt. ValueError if the file is not understood.
    The keys of ring.py and target.py are known and skipped; anything else is an error. `text` (optional): the
    content to parse instead of the file (the staged one); None means "absent", so the defaults."""
    modes = {"memory-source": "warn", "memory-reach": "warn"}
    if text is ...:
        f = vault / "gate.txt"
        if not f.exists():
            return modes
        try:
            text = f.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as e:
            raise ValueError(f"vault/gate.txt exists but cannot be read ({type(e).__name__})")
    if text is None:
        return modes
    text = text.lstrip("\ufeff")
    for n, raw in enumerate(text.splitlines(), 1):
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        key, sep, value = line.partition(":")
        key = key.strip()
        if not sep or key not in gate.GATE_KEYS:
            raise ValueError(f"vault/gate.txt line {n}: unknown key (known keys: {', '.join(gate.GATE_KEYS)})")
        if key in modes:
            modes[key] = value.strip()
            if modes[key] not in MODES:
                raise ValueError(f"vault/gate.txt line {n}: unknown {key} value '{modes[key]}' (use warn or block)")
    return modes


# ---- which path is what (casefold: `vault/MEMORY/profile.md` is memory) ---------------------------------------------

def rel_to(p: Path, base: Path) -> str | None:
    try:
        r = Path(p).relative_to(base).as_posix()
    except ValueError:
        return None
    return "" if r == "." else r


def entries_rel(rv: str) -> bool:
    """`rv` is a casefolded path relative to the vault: a memory file WITH ENTRIES (not observations.md)."""
    if rv.rsplit("/", 1)[-1] == "observations.md":
        return False
    return bool(re.match(r"^memory/[^/]+\.md$", rv) or re.match(r"^people/[^/]+/memory/[^/]+\.md$", rv))


def memory_tree_rel(rv: str) -> bool:
    """Any .md anywhere under a memory folder (ideas/, diary/, archive/ included): scanned for hidden text and reach."""
    return bool(re.match(r"^(?:memory|people/[^/]+/memory)/.+\.md$", rv))


def in_memory_folder(rv: str) -> bool:
    return bool(re.match(r"^(?:memory|people/[^/]+/memory)(?:/|$)", rv))


def kinds(p: Path, vault: Path, root: Path) -> set:
    """{"entries", "memory", "loaded"} for a path, by the patterns only (the file need not exist)."""
    out = set()
    rv, rr = rel_to(p, vault), rel_to(p, root)
    rv = rv.casefold() if rv is not None else None
    rr = rr.casefold() if rr is not None else None
    if rv is not None:
        if entries_rel(rv):
            out.add("entries")
        if memory_tree_rel(rv):
            out.add("memory")
    if Path(p).name.casefold() in LOADED_NAMES:
        out.add("loaded")
    if rr is not None:
        parts = rr.split("/")
        if rr == ".github/copilot-instructions.md" or any(d in AGENT_DIRS for d in parts[:-1]):
            out.add("loaded")
    if out & {"entries", "memory"}:
        out.add("loaded")
    return out


def protected(p: Path, vault: Path, root: Path) -> bool:
    """A loaded path, or a folder above one: a symlink here would send a loaded path somewhere else."""
    if kinds(p, vault, root):
        return True
    rv, rr = rel_to(p, vault), rel_to(p, root)
    if rv is not None and re.match(r"^(?:$|people$|people/[^/]+$|memory(?:/|$)|people/[^/]+/memory(?:/|$))", rv.casefold()):
        return True
    return rr is not None and any(d in AGENT_DIRS for d in rr.casefold().split("/"))


LENIENT_DIRS = (".agents", ".cursor", ".gemini")


def agent_link_ok(p: Path, link: str, vault: Path, root: Path) -> bool:
    """A symlink inside `.agents/`, `.cursor/` or `.gemini/` is fine when it only points to another path that is already
    scanned (for example `.agents/skills -> ../.claude/skills`, how one skills folder serves every agent). Anything that
    points outside the repo, or to a place nobody scans, still fails. `.claude/` and memory never get this."""
    rr = rel_to(p, root)
    parts = rr.casefold().split("/") if rr is not None else []
    if not any(d in LENIENT_DIRS for d in parts[:-1] + ([parts[-1]] if parts else [])) or ".claude" in parts or kinds(p, vault, root) & {"memory", "entries"}:
        return False
    if not link or link.startswith("/") or "\x00" in link:
        return False
    target = Path(os.path.normpath(os.path.join(os.path.dirname(p), link)))
    if rel_to(target, root) is None or in_memory_folder((rel_to(target, vault) or "").casefold()):
        return False
    trr = (rel_to(target, root) or "").casefold().split("/")
    return any(d in AGENT_DIRS for d in trr) and target != Path(os.path.abspath(p))


def memory_files(vault: Path) -> list[Path]:
    """The memory files with ENTRIES (vault/memory/*.md and vault/people/<h>/memory/*.md, not observations.md)."""
    def sub(d: Path, name: str) -> list[Path]:
        return [c for c in sorted(d.iterdir()) if c.name.casefold() == name and c.is_dir()] if d.is_dir() else []
    dirs = sub(vault, "memory")
    for people in sub(vault, "people"):
        for h in sorted(people.iterdir()) if people.is_dir() else []:
            dirs += sub(h, "memory")
    out = []
    for d in dirs:
        out += [p for p in sorted(d.iterdir()) if p.is_file() and p.name.casefold().endswith(".md") and p.name.casefold() != "observations.md"]
    return out


def norm_path(s) -> Path:
    """Absolute, with the parents resolved but NOT the last component (a symlinked vault must stay visible)."""
    ap = Path(os.path.abspath(s))
    return Path(os.path.realpath(ap.parent)) / ap.name


# ---- git, read from the index and HEAD -----------------------------------------------------------------------------

def git_top(root: Path) -> Path:
    return Path(subprocess.run(["git", "-C", str(root), "rev-parse", "--show-toplevel"], capture_output=True, text=True,
                               check=True).stdout.strip()).resolve()


def staged_raw(top: Path) -> list[tuple[str, Path]]:
    """(mode in the index, path) of what this commit adds or changes, read in bytes with -z (a name with a byte that
    is not UTF-8 survives through surrogateescape). Not resolved: a symlink is judged where it sits."""
    r = subprocess.run(["git", "-C", str(top), "diff", "--cached", "--raw", "-z", "--no-renames", "--diff-filter=ACMRT"],
                       capture_output=True, check=True)
    tokens = r.stdout.decode("utf-8", errors="surrogateescape").split("\0")
    out, i = [], 0
    while i < len(tokens):
        if tokens[i].startswith(":") and i + 1 < len(tokens):
            fields = tokens[i][1:].split()
            out.append((fields[1], Path(os.path.abspath(top / tokens[i + 1]))))
            i += 2
        else:
            i += 1
    return out


class Reader:
    """Reads from the disk, or (staged) from the git index and HEAD, so a clean working copy cannot hide a dirty stage.
    A path never goes into a revision expression (`:path`, `HEAD:path`): `0:docs/CLAUDE.md` would be read as stage 0 of
    another path. It is looked up with `ls-files` / `ls-tree` (literal pathspecs), and the blob is read by its sha."""

    def __init__(self, top: Path | None):
        self.top = top

    def rel(self, path: Path) -> str | None:
        if self.top is None:
            return None
        return rel_to(Path(path), self.top)

    def git(self, *args: str) -> bytes | None:
        r = subprocess.run(["git", "-C", str(self.top), *args], capture_output=True,
                           env={**os.environ, "GIT_LITERAL_PATHSPECS": "1"})
        return r.stdout if r.returncode == 0 else None

    @staticmethod
    def _records(raw: bytes | None, rel: str):
        """(meta fields, path) of each NUL-separated `meta<TAB>path` record whose path is exactly `rel`."""
        out = []
        for rec in (raw or b"").split(b"\0"):
            meta, tab, path = rec.partition(b"\t")
            if tab and path.decode("utf-8", errors="surrogateescape") == rel:
                out.append(meta.decode("utf-8", errors="replace").split())
        return out

    def index_entry(self, rel: str) -> tuple[str, str] | None:
        """(mode, sha) of the path in the index (stage 0 first), or None."""
        recs = self._records(self.git("ls-files", "-s", "-z", "--", rel), rel)
        recs = sorted((r for r in recs if len(r) >= 3), key=lambda r: r[2])
        return (recs[0][0], recs[0][1]) if recs else None

    def head_entry(self, rel: str) -> tuple[str, str, str] | None:
        """(mode, type, sha) of the path in HEAD, or None if HEAD does not have it (new file, or no commit yet)."""
        recs = [r for r in self._records(self.git("ls-tree", "-z", "HEAD", "--", rel), rel) if len(r) >= 3]
        return (recs[0][0], recs[0][1], recs[0][2]) if recs else None

    def index_mode(self, rel: str) -> str | None:
        e = self.index_entry(rel)
        return e[0] if e else None

    def blob(self, sha: str) -> bytes | None:
        return self.git("cat-file", "blob", sha)

    def index_blob(self, rel: str) -> bytes | None:
        e = self.index_entry(rel)
        return self.blob(e[1]) if e else None

    def exists(self, path: Path) -> bool:
        if self.top is None:
            return Path(path).is_file()
        rel = self.rel(path)
        e = self.index_entry(rel) if rel else None
        return bool(e) and e[0] in REGULAR

    def text(self, path: Path) -> str:
        try:
            if self.top is not None:
                rel = self.rel(path)
                raw = self.index_blob(rel) if rel else None
                if raw is None:
                    raise Unreadable("git could not show it from the index")
                return raw.decode("utf-8")
            return Path(path).read_bytes().decode("utf-8")
        except UnicodeDecodeError:
            raise Unreadable("it is not valid UTF-8")
        except OSError as e:
            raise Unreadable(f"it could not be opened ({type(e).__name__})")

    def head(self, rel: str) -> str | None:
        e = self.head_entry(rel)
        raw = self.blob(e[2]) if e and e[1] == "blob" else None
        return None if raw is None else raw.decode("utf-8", errors="replace")


def valid_date(s: str) -> date | None:
    if not ISO.match(s):
        return None
    try:
        return date.fromisoformat(s)
    except ValueError:
        return None


# ---- source ----------------------------------------------------------------------------------------------------------

def judge_source(at: str, where: str, phrase: str, vault: Path, reader: Reader, modes: dict):
    """(failure | None, not_verified | None) for the `where` of one entry."""
    block = modes["memory-source"] == "block"
    w = safe(where)

    def not_file():
        msg = f'{at} source "{w}" is not a file in the vault'
        if block:
            return Failure(at, "source", f'source "{w}" is not a file in the vault (vault/gate.txt: memory-source: block)'), None
        return None, f"NOT_VERIFIED: {msg}"

    def fail(why: str):
        return Failure(at, "source", f'source "{w}" {why}'), None

    def verdict(text: str):
        got = quote.found_whole(phrase, text)
        if got is False:
            return Failure(at, "source", f"the phrase is not in {w} (the whole phrase must be there, word for word)"), None
        if got is None:
            return None, f'NOT_VERIFIED: {at} source "{w}": the phrase has fewer than 3 words, nothing to compare'
        return None, None

    if where != posixpath.normpath(where) or ".." in where.split("/"):
        return fail("is not a normalized path (no `..`, `.`, `//` or trailing slash)")

    if reader.top is None:  # the disk
        cand = vault / where
        if not cand.is_file():
            return not_file()
        res, vres = Path(os.path.realpath(cand)), Path(os.path.realpath(vault))
        relv = rel_to(res, vres)
        if relv is None:
            return fail("resolves outside vault/")
        if in_memory_folder(relv.casefold()):
            return fail("is a memory file: a memory cannot vouch for a memory")
        try:
            return verdict(res.read_bytes().decode("utf-8", errors="replace"))
        except OSError as e:
            return fail(f"could not be read ({type(e).__name__})")

    # staged: HEAD and the index decide, never the disk
    vrel = reader.rel(vault)
    full = Path(os.path.normpath(where if Path(where).is_absolute() else str(vault / where)))
    frel = reader.rel(full)
    if vrel is None or frel is None:
        return not_file()
    parts = frel.split("/")
    entry = None
    for i in range(1, len(parts) + 1):
        entry = reader.head_entry("/".join(parts[:i]))
        if entry is None:
            break
        if entry[0] == "120000":
            return fail("crosses a symlink in HEAD")
    if entry is not None and entry[1] != "blob":
        return not_file()  # a folder (or a submodule) is no source
    in_index = reader.index_mode(frel)
    if entry is not None and in_index is None:
        return fail("is deleted in this commit")
    if in_index == "120000":
        return fail("is a symlink in the index")
    if entry is None:
        if in_index is not None:
            msg = f'{at} source "{w}" is new in this commit; commit the source first'
            if block:
                return Failure(at, "source", f'source "{w}" is new in this commit; commit the source first (memory-source: block)'), None
            return None, f"NOT_VERIFIED: {msg}"
        return not_file()
    relv = frel[len(vrel) + 1:] if vrel else frel
    if vrel and not (frel.casefold() + "/").startswith(vrel.casefold() + "/"):
        return fail("resolves outside vault/")
    if in_memory_folder(relv.casefold()):
        return fail("is a memory file: a memory cannot vouch for a memory")
    text = reader.head(frel)
    return verdict(text or "")


# ---- the memory file -------------------------------------------------------------------------------------------------

def reach_lines(rel: str, lines: list[str], modes: dict):
    fails, warns = [], []
    for i, line in enumerate(lines):
        if REACH.search(line):
            at = f"{rel}:{i + 1}"
            what = "a URL, a domain or a shell-looking command"
            if modes["memory-reach"] == "block":
                fails.append(Failure(at, "reach", f"{what} in a memory file (vault/gate.txt: memory-reach: block)"))
            else:
                warns.append(f"WARNING {at} :: reach :: {what} in a memory file (memory is obeyed by every session; vault/gate.txt: memory-reach: warn)")
    return fails, warns


def judge_memory(rel: str, text: str, vault: Path, reader: Reader, today: date, modes: dict):
    """(failures, warnings, not_verified) for one memory file with entries."""
    fails, warns, nv = [], [], []
    lines = text.split("\n")
    f, w = reach_lines(rel, lines, modes)  # every line, the header and the titles included
    fails += f
    warns += w
    start = next((i for i, l in enumerate(lines) if l.startswith(MARKER)), None)
    if start is None:
        fails.append(Failure(rel, "shape", f"the file has no line starting with `{MARKER}`, so no line can be judged"))
        return fails, warns, nv
    for i in range(start + 1, len(lines)):
        line, at = lines[i], f"{rel}:{i + 1}"
        if line.endswith("\r"):
            line = line[:-1]
        if not line.strip() or POINTER.match(line):
            continue
        m = parse_entry(line)
        fields = FIELD.findall(m.group(4)) if m else []
        if not m or any(k not in FIELD_KEYS for k, _ in fields):
            hint = "a final field other than stale_after / superseded_by" if m else \
                'expected `YYYY-MM-DD | "verbatim phrase" | where` (only entries, the exact pointer line of tools/cool.py and blank lines may follow the format line; a title may not)'
            fails.append(Failure(at, "shape", f"line is not an entry: {hint}"))
            continue
        d, phrase, where = m.group(1), m.group(2), m.group(3).strip()
        if not where:
            fails.append(Failure(at, "shape", "the entry says nowhere where it was said (the third field is empty)"))
            continue
        parsed = valid_date(d)
        if parsed is None:
            fails.append(Failure(at, "date", f"'{d}' is not a real date"))
        elif parsed > today + timedelta(days=1):
            fails.append(Failure(at, "date", f"'{d}' is in the future (today is {today.isoformat()})"))
        for k, v in fields:
            if valid_date(v) is None:
                fails.append(Failure(at, "date", f"{k}: '{v}' is not a real date (YYYY-MM-DD)"))
        f1, n1 = judge_source(at, where, phrase, vault, reader, modes)
        if f1:
            fails.append(f1)
        if n1:
            nv.append(n1)
    return fails, warns, nv


def header_of(text: str) -> str:
    lines = text.split("\n")
    start = next((i for i, l in enumerate(lines) if l.startswith(MARKER)), None)
    return "\n".join(lines if start is None else lines[:start + 1])


def judge_header(rel: str, text: str, frel: str | None, reader: Reader, modes: dict):
    """Staged only: the text above (and on) the format line is loaded in every session; a new file or a change deserves a look."""
    old = reader.head(frel) if frel else None
    if old is None:
        msg = f"{rel}: new memory file; its header loads in every session"
    elif header_of(old) == header_of(text):
        return None, None
    else:
        msg = f"{rel}: the header above the format line changed; memory files take dated entries only"
    if modes["memory-reach"] == "block":
        return Failure(rel, "header", msg + " (vault/gate.txt: memory-reach: block)"), None
    return None, f"WARNING: {msg}"


# ---- hidden text -----------------------------------------------------------------------------------------------------

FLAGS = tuple("\U0001f3f4" + "".join(chr(0xE0000 + ord(c)) for c in name) + "\U000e007f" for name in ("gbeng", "gbsct", "gbwls"))
MEMORY_HINT = " (memory takes plain text only; an emoji with a selector, for example U+2764 U+FE0F, does not fit in it: take it out)"


def _tag_sequence_ok(line: str, i: int) -> bool:
    """A tag character is fine only inside one of the three RGI subdivision flags (England, Scotland, Wales):
    U+1F3F4, the tags of gbeng / gbsct / gbwls letter by letter, U+E007F. Any other tag spells hidden ASCII."""
    s = i
    while s > 0 and 0xE0000 <= ord(line[s - 1]) <= 0xE007F:
        s -= 1
    e = i
    while e < len(line) and 0xE0000 <= ord(line[e]) <= 0xE007F:
        e += 1
    return line[s - 1:e] in FLAGS


def base_hidden(c: str) -> bool:
    """Invisible by category (Cf, Co, Cn, Cc) or by the default-ignorable and filler lists, before any exception."""
    o = ord(c)
    return unicodedata.category(c) in ("Cf", "Co", "Cn", "Cc") or any(lo <= o <= hi for lo, hi in HIDDEN_EXTRA)


def _emoji_base(c: str) -> bool:
    if not c or c == BLANK:
        return False
    cat = unicodedata.category(c)
    return cat == "So" or 0x1F3FB <= ord(c) <= 0x1F3FF or (cat == "Sm" and ord(c) > 0x7F)


def _virama(c: str) -> bool:
    return bool(c) and 0x0900 <= ord(c) <= 0x0DFF and unicodedata.combining(c) == 9


def _selector_base(c: str) -> bool:
    if not c or c == BLANK:
        return False
    cat = unicodedata.category(c)
    return cat in ("So", "Sk") or (cat in ("Sm", "Pd", "Po") and ord(c) > 0x7F) or c in EMOJI_SELECTOR_OK


def _same_arabic_block(a: str, b: str) -> bool:
    return any(lo <= ord(a) <= hi and lo <= ord(b) <= hi for lo, hi in ARABIC)


def _cjk(c: str) -> bool:
    return bool(c) and (0x3400 <= ord(c) <= 0x9FFF or 0x20000 <= ord(c) <= 0x3134F)


def is_hidden(line: str, i: int, first_line: bool, before_nl: bool = False) -> bool:
    """For the files a session loads that are NOT memory: the forbidden list, with its narrow exceptions."""
    c = line[i]
    o, cat = ord(c), unicodedata.category(c)
    if c == "\t":
        return False
    if c == "\r":
        return not (before_nl and i == len(line) - 1)
    if c == BOM and first_line and i == 0:
        return False  # how some editors save UTF-8
    prev = line[i - 1] if i > 0 else ""
    nxt = line[i + 1] if i + 1 < len(line) else ""
    if cat == "Zs" and c != " ":
        return not (c in ("\u00a0", "\u202f") and prev and nxt and not prev.isspace() and not nxt.isspace())
    if not base_hidden(c):
        return False
    if 0xE0100 <= o <= 0xE01EF:
        return not _cjk(prev)  # one ideographic variation selector, right after its ideograph
    if 0xE0000 <= o <= 0xE007F:
        return not _tag_sequence_ok(line, i)
    if c in (VS15, VS16):
        if c == VS16 and prev and prev in "0123456789#*" and nxt == KEYCAP:
            return False
        return not _selector_base(prev)
    if c == ZWJ:
        if prev in (VS15, VS16) and i > 1:
            prev = line[i - 2]  # a heart + emoji selector + ZWJ + fire is one legitimate sequence
        return not ((_emoji_base(prev) and _emoji_base(nxt)) or _virama(prev))
    if c == ZWNJ:
        letters = prev and nxt and unicodedata.category(prev).startswith("L") and unicodedata.category(nxt).startswith("L")
        return not ((letters and _same_arabic_block(prev, nxt)) or _virama(prev))
    return True


def memory_char_ok(c: str, line_is_nfc: bool) -> bool:
    """The ALLOWED list of a memory file."""
    o = ord(c)
    if 0x20 <= o <= 0x7E or c == "\t":
        return True
    if 0x1F100 <= o <= 0x1F1FF or 0x2460 <= o <= 0x24FF:
        return False
    cat = unicodedata.category(c)
    if cat in ("Mn", "Mc"):
        return line_is_nfc
    return cat[0] == "L" or cat == "Nd" or cat[0] == "P" or cat in ("Sm", "Sc", "Sk", "So")


def judge_hidden(rel: str, text: str, memory: bool = False) -> list:
    out = []
    lines = text.split("\n")
    for n, line in enumerate(lines, 1):
        nfc = unicodedata.is_normalized("NFC", line) if memory else True
        for i in range(len(line)):
            c = line[i]
            at = f"{rel}:{n}:{i + 1}"
            if not memory:
                if is_hidden(line, i, n == 1, before_nl=n < len(lines)):
                    out.append(Failure(at, "hidden", f"invisible character U+{ord(c):04X}"))
                continue
            if c == "\t" or (c == "\r" and n < len(lines) and i == len(line) - 1):
                continue
            if c == BOM and n == 1 and i == 0:
                continue
            if base_hidden(c):
                out.append(Failure(at, "hidden", f"invisible character U+{ord(c):04X}{MEMORY_HINT}"))
            elif not memory_char_ok(c, nfc):
                out.append(Failure(at, "hidden", f"character U+{ord(c):04X} is not allowed in a memory file{MEMORY_HINT}"))
    return out


TEACH = """
How to fix: a memory line is `YYYY-MM-DD | "what the user said, word for word" | where`. If `where` is a file of
the vault (for example a chat imported by tools/import_chats.py), the whole phrase has to be in that file, and the
file has to be committed BEFORE the memory line that cites it. Delete an invisible character (the output says the
file, line and column), and keep URLs and commands out of the memory.
Deliberate bypass: git commit --no-verify
"""


IMPORT = re.compile(r"(?:^|(?<=[\s(]))@([^\s)\]>\"'`]+)")
MAX_IMPORT_DEPTH = 5


def imports_of(text: str, importer: Path, root: Path) -> list[Path]:
    """The files a CLAUDE.md pulls in with `@path` (relative to the importing file, or absolute) that stay inside the repo."""
    out = []
    for line in text.split("\n"):
        for m in IMPORT.finditer(line):
            t = m.group(1).rstrip(".,;:!?")
            if not t or t.startswith("~") or t.startswith("@"):
                continue
            target = Path(os.path.normpath(t if os.path.isabs(t) else os.path.join(os.path.dirname(importer), t)))
            if rel_to(target, root) is not None:
                out.append(target)
    return out


def safe(s: str) -> str:
    """Text for a message: an invisible or odd character becomes <U+XXXX>, so the message cannot carry hidden text."""
    out = []
    for c in s:
        if c in ("\n", "\r", "\t") or base_hidden(c) or (unicodedata.category(c) == "Zs" and c != " "):
            out.append(f"<U+{ord(c):04X}>")
        else:
            out.append(c)
    return "".join(out).encode("utf-8", "backslashreplace").decode("utf-8")


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(errors="backslashreplace")
        except (AttributeError, ValueError):
            pass
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("files", nargs="*")
    ap.add_argument("--vault", default="vault")
    ap.add_argument("--root", help="the repo root with CLAUDE.md, AGENTS.md and .claude/ (default: the vault's parent folder)")
    ap.add_argument("--staged", action="store_true", help="only what is in the git index, read from the index")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--today", help=argparse.SUPPRESS)
    a = ap.parse_args(argv)
    vault = norm_path(a.vault)
    root = norm_path(a.root) if a.root else vault.parent
    if not vault.is_dir():
        print(f"ERROR: the vault '{vault}' does not exist.", file=sys.stderr)
        return 2
    try:
        today = date.fromisoformat(a.today) if a.today else date.today()
    except ValueError:
        print("ERROR: --today must be YYYY-MM-DD", file=sys.stderr)
        return 2

    top = None
    raw: list[tuple[str, Path]] = []
    if a.staged:
        try:
            top = git_top(root)
            raw = staged_raw(top)
        except (subprocess.CalledProcessError, OSError, UnicodeDecodeError):
            print("NOT_VERIFIED: could not read the git stage (git missing, or the repo root is not in a repo).")
            return 3
    reader = Reader(top)
    warns: list[str] = []
    try:
        if top is not None:
            grel = reader.rel(vault / "gate.txt")
            blob = reader.index_blob(grel) if grel else None
            modes = gate_modes(vault, blob.decode("utf-8") if blob is not None else None)
            try:
                old = reader.head(grel) if grel else None
                before = gate_modes(vault, old)
            except ValueError:
                before = gate_modes(vault, None)  # a malformed gate.txt in HEAD cannot be the stricter one
            loosened = [k for k in modes if before[k] == "block" and modes[k] != "block"]
            modes = {k: "block" if "block" in (modes[k], before[k]) else "warn" for k in modes}
            if loosened:
                warns.append("WARNING: vault/gate.txt loosens the memory gate; this commit is still judged by the stricter setting")
        else:
            modes = gate_modes(vault)
    except (ValueError, UnicodeDecodeError) as e:
        print(f"ERROR: {e}. The memory check judged nothing, so the commit is blocked until it is fixed.")
        return 2

    fails, nv = [], []

    def rel(p: Path) -> str:
        for base in (root, vault):
            r = rel_to(p, base)
            if r is not None:
                return safe(r)
        return safe(p.name)

    items: dict[Path, set] = {}
    if a.staged:
        for mode, p in raw:
            k = kinds(p, vault, root)
            if mode == "120000" and (k or protected(p, vault, root)) and agent_link_ok(
                    p, (reader.index_blob(reader.rel(p) or "") or b"").decode("utf-8", errors="replace"), vault, root):
                continue
            if mode not in REGULAR and (k or protected(p, vault, root)):
                fails.append(Failure(rel(p), "symlink", "symlink in place of a loaded path" if mode == "120000"
                                     else "not a regular file in place of a loaded path"))
            elif k:
                items[p] = k
    else:
        if Path(os.path.abspath(a.vault)).is_symlink():
            fails.append(Failure(rel(vault), "symlink", "symlink in place of a loaded path"))
        bases = [root] if rel_to(vault, root) is not None else [root, vault]
        for base in bases:
            for dirpath, dirnames, filenames in os.walk(base):
                dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS)
                for d in dirnames:
                    dp = Path(dirpath) / d
                    if dp.is_symlink() and protected(dp, vault, root) and not agent_link_ok(dp, os.readlink(dp), vault, root):
                        fails.append(Failure(rel(dp), "symlink", "symlink in place of a loaded path"))
                for fn in sorted(filenames):
                    fp = Path(dirpath) / fn
                    k = kinds(fp, vault, root)
                    if not k:
                        continue
                    if fp.is_symlink() and agent_link_ok(fp, os.readlink(fp), vault, root):
                        continue
                    if fp.is_symlink():
                        fails.append(Failure(rel(fp), "symlink", "symlink in place of a loaded path"))
                    else:
                        items[fp] = k
    if a.files:
        want = {Path(os.path.abspath(f if Path(f).exists() else vault / f)) for f in a.files}
        items = {p: k for p, k in items.items() if Path(os.path.abspath(p)) in want}

    queue = [(p, k, 0) for p, k in sorted(items.items())]
    seen = {Path(os.path.abspath(p)) for p in items}
    n_items = 0
    while queue:
        p, k, depth = queue.pop(0)
        n_items += 1
        r = rel(p)
        try:
            text = reader.text(p)
        except Unreadable as e:
            fails.append(Failure(r, "unreadable", f"{e}; a memory or loaded file that cannot be read is not a pass"))
            continue
        fails += judge_hidden(r, text, memory="memory" in k)
        if "entries" in k:
            f1, w1, n1 = judge_memory(r, text, vault, reader, today, modes)
            fails += f1
            warns += w1
            nv += n1
            if a.staged:
                hf, hw = judge_header(r, text, reader.rel(p), reader, modes)
                if hf:
                    fails.append(hf)
                if hw:
                    warns.append(hw)
        elif "memory" in k:
            f1, w1 = reach_lines(r, text.split("\n"), modes)
            fails += f1
            warns += w1
        if depth < MAX_IMPORT_DEPTH and (depth > 0 or p.name.casefold() in IMPORTERS):
            for target in imports_of(text, p, root):
                ap_ = Path(os.path.abspath(target))
                if ap_ in seen or not reader.exists(ap_):
                    continue
                seen.add(ap_)
                queue.append((ap_, kinds(ap_, vault, root) | {"loaded"}, depth + 1))
    by = {c: [f for f in fails if f.check == c] for c, _ in CHECKS}
    if a.json:
        print(json.dumps({"files": n_items, "failures": [f._asdict() for f in fails], "warnings": warns,
                          "not_verified": nv, "checks": {c: len(v) for c, v in by.items()}}, ensure_ascii=False, indent=2))
    else:
        for f in fails:
            print(f"FAILS {f.file} :: {f.check} :: {f.msg}")
        for w in warns:
            print(w)
        for n in nv:
            print(n)
        if fails:
            print(TEACH)
        print(f"{n_items} file(s) judged, {len(fails)} failure(s), {len(warns)} warning(s), {len(nv)} not verified")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
