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
`git commit --no-verify` or edit the hook; rule 6 forbids it, and the hook cannot stop it. Known limit: a source
file committed in an EARLIER commit of the same session counts as earlier, because the hook cannot know who wrote it.

A memory file with ENTRIES is a `.md` directly in `vault/memory/` or in `vault/people/<handle>/memory/` (team
mode), except `observations.md` (where the model PROPOSES: no shape, date or source check). Paths are classified
with casefold (`vault/MEMORY/profile.md` is memory, `.MD` is `.md`). After the `Format of each line:` line only
an entry or the EXACT pointer line `tools/cool.py` leaves behind may appear (a `#` title is a failure there);
a trailing CR (CRLF files) is accepted. An entry is

    YYYY-MM-DD | "verbatim phrase" | where | stale_after: YYYY-MM-DD | superseded_by: YYYY-MM-DD

(straight or curly quotes; the last two fields are optional and a later piece reads them).

The checks:
  shape      after the format line: only entries, the cool pointer and blank lines; the marker must exist              blocks
  date       the entry date is a real date and not after tomorrow; so are the dates of the final fields                blocks
  source     `where` is a file of the vault holding the WHOLE phrase (normalized, whole words; no `[...]` or `...`
             exception: that is only for tools/citation.py --quotes). Not found blocks. A source that resolves outside
             `vault/`, or inside a memory folder (a memory cannot vouch for a memory, any case), blocks. `where` is not
             a file (`chat`): NOT_VERIFIED, blocking only with `memory-source: block`. With --staged the source is
             decided by HEAD and the index, never by the disk: it must be a regular blob in HEAD, no component of its
             path a symlink there, and not deleted by this commit. A source born in this commit is NOT_VERIFIED
             ("commit the source first"), never verified                                                              blocks / warns
  hidden     an invisible character in ANY file a session loads (CLAUDE.md and AGENTS.md anywhere in the repo,
             CLAUDE.local.md, every .md under .claude/, every .md under memory/ recursively, team memory): every
             category Cf, Co and Cc (but tab, LF, and CR right before LF), U+2028, U+2029, U+2800, the fillers and
             selectors in HIDDEN_EXTRA. file:line:column and the code point. Fine: a BOM at the start of the file;
             FE0E/FE0F after a symbol (So, Sm, Po); a keycap; a ZWJ between two emoji (skin tones count); a flag tag
             sequence; a ZWNJ between two letters. A run of two or more invisibles stays a failure                      always blocks
  reach      a URL, a domain with a common TLD and a slash, `www.`, or a shell-looking command (curl, wget, | sh,
             | bash, git push, --no-verify, rm -rf, chmod +x, sudo/eval in backticks) on ANY line of a .md under
             memory/, the header and titles included                                                                   warns
  header     (--staged) the text above and including the format line changed against HEAD, or the memory file is
             new                                                                                                       warns
  unreadable a memory or loaded file that does not open or is not valid UTF-8 is a failure, not a pass                   blocks
  symlink    a symlink in place of a loaded path, or of a folder above one (vault, memory, people/<x>, .claude...)    blocks
`reach` and `header` block with `memory-reach: block` in vault/gate.txt. With --staged vault/gate.txt is read
from the index (absent there = defaults).

rc: 0 clean, or only warnings / NOT_VERIFIED · 1 a check that blocks failed · 2 usage, or vault/gate.txt malformed ·
3 git did not say what is staged (the hook BLOCKS on 3: the gate never passes blind). With --staged the candidates
and their modes come from the git index and the content judged is the INDEX content (`git show :path`).
"""
from __future__ import annotations

import argparse
import json
import os
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
ENTRY = re.compile(r"^\s*(?:[-*]\s+)?(\d{4}-\d{2}-\d{2})\s*\|\s*[\"“](.*)[\"”]\s*\|\s*([^|]*?)\s*((?:\|\s*\w+:\s*[^|]*?\s*)*)$")
FIELD = re.compile(r"\|\s*(\w+):\s*([^|]*?)\s*(?=\||$)")
FIELD_KEYS = ("stale_after", "superseded_by")
ISO = re.compile(r"^\d{4}-\d{2}-\d{2}$")
REACH = re.compile(
    r"https?://|\bwww\.|\bcurl\s|\bwget\s|\|\s*(?:sh|bash)\b|\bgit\s+push\b|--no-verify|\brm\s+-rf|chmod\s+\+x"
    r"|\b[a-z0-9-]+\.(?:com|net|org|io|dev|sh|app|xyz|ru|cn|info|me)/"
    r"|`[^`\n]*(?:\bcurl\b|\bwget\b|\brm\s|\bsudo\b|\beval\b)[^`\n]*`", re.I)
MODES = ("warn", "block")
LOADED_NAMES = ("claude.md", "agents.md", "claude.local.md")
SKIP_DIRS = {".git", "node_modules", ".venv", "venv", "__pycache__", ".pytest_cache"}

# Hidden text: every character of Unicode category Cf (zero-width, bidi controls, soft hyphen, BOM, tag characters...),
# Co (private use) and Cc (control, except tab, LF and a CR right before LF), plus these, which are none of those:
# the line and paragraph separators, the Braille blank, Hangul fillers, the combining grapheme joiner, Khmer inherent
# vowels, Mongolian selectors, and the variation selectors (U+FE00-FE0F, U+E0100-E01EF).
HIDDEN_EXTRA = ((0x034F, 0x034F), (0x115F, 0x1160), (0x2028, 0x2029), (0x2800, 0x2800), (0x3164, 0x3164),
                (0xFFA0, 0xFFA0), (0x17B4, 0x17B5), (0x180B, 0x180F), (0xFE00, 0xFE0F), (0xE0100, 0xE01EF))
ZWJ, ZWNJ, VS15, VS16, BOM, KEYCAP, BLANK = "‍", "‌", "︎", "️", "﻿", "⃣", "⠀"


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
    name = Path(p).name.casefold()
    if name in LOADED_NAMES:
        out.add("loaded")
    if rr is not None and rr.startswith(".claude/") and rr.endswith(".md"):
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
    return rr is not None and bool(re.match(r"^\.claude(?:/|$)", rr.casefold()))


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
    """Reads from the disk, or (staged) from the git index and HEAD, so a clean working copy cannot hide a dirty stage."""

    def __init__(self, top: Path | None):
        self.top = top

    def rel(self, path: Path) -> str | None:
        if self.top is None:
            return None
        r = rel_to(Path(path), self.top)
        return r

    def git(self, *args: str) -> bytes | None:
        r = subprocess.run(["git", "-C", str(self.top), *args], capture_output=True)
        return r.stdout if r.returncode == 0 else None

    def git_show(self, spec: str) -> bytes | None:
        return self.git("show", spec)

    def text(self, path: Path) -> str:
        try:
            if self.top is not None:
                rel = self.rel(path)
                raw = self.git_show(f":{rel}") if rel else None
                if raw is None:
                    raise Unreadable("git could not show it from the index")
                return raw.decode("utf-8")
            return Path(path).read_bytes().decode("utf-8")
        except UnicodeDecodeError:
            raise Unreadable("it is not valid UTF-8")
        except OSError as e:
            raise Unreadable(f"it could not be opened ({type(e).__name__})")

    def head_entry(self, rel: str) -> tuple[str, str] | None:
        """(mode, type) of the path in HEAD, or None if HEAD does not have it (new file, or no commit yet)."""
        raw = self.git("ls-tree", "-z", "HEAD", "--", rel)
        if not raw:
            return None
        meta = raw.split(b"\t", 1)[0].decode("utf-8", errors="replace").split()
        return (meta[0], meta[1]) if len(meta) >= 2 else None

    def index_mode(self, rel: str) -> str | None:
        raw = self.git("ls-files", "-s", "-z", "--", rel)
        if not raw:
            return None
        return raw.split(b"\t", 1)[0].decode("utf-8", errors="replace").split()[0]

    def head(self, rel: str) -> str | None:
        raw = self.git_show(f"HEAD:{rel}")
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

    def not_file():
        msg = f'{at} source "{where}" is not a file in the vault'
        if block:
            return Failure(at, "source", f'source "{where}" is not a file in the vault (vault/gate.txt: memory-source: block)'), None
        return None, f"NOT_VERIFIED: {msg}"

    def fail(why: str):
        return Failure(at, "source", f'source "{where}" {why}'), None

    def verdict(text: str):
        got = quote.found_whole(phrase, text)
        if got is False:
            return Failure(at, "source", f"the phrase is not in {where} (the whole phrase must be there, word for word)"), None
        if got is None:
            return None, f'NOT_VERIFIED: {at} source "{where}": the phrase has fewer than 3 words, nothing to compare'
        return None, None

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
    if vrel is None or frel is None or frel.startswith(".."):
        return not_file()
    parts = frel.split("/")
    entry = None
    for i in range(1, len(parts) + 1):
        entry = reader.head_entry("/".join(parts[:i]))
        if entry is None:
            break
        if entry[0] == "120000":
            return fail("crosses a symlink in HEAD")
    in_index = reader.index_mode(frel)
    if entry is not None and in_index is None:
        return fail("is deleted in this commit")
    if in_index == "120000":
        return fail("is a symlink in the index")
    if entry is None:
        if in_index is not None:
            msg = f'{at} source "{where}" is new in this commit; commit the source first'
            if block:
                return Failure(at, "source", f'source "{where}" is new in this commit; commit the source first (memory-source: block)'), None
            return None, f"NOT_VERIFIED: {msg}"
        return not_file()
    if entry[1] != "blob":
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
        m = ENTRY.match(line)
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

def _tag_sequence_ok(line: str, i: int) -> bool:
    """A flag written with tag characters: U+1F3F4, tags U+E0020-E007E, closed by U+E007F."""
    s = i
    while s > 0 and 0xE0020 <= ord(line[s - 1]) <= 0xE007F:
        s -= 1
    e = i
    while e < len(line) and 0xE0020 <= ord(line[e]) <= 0xE007F:
        e += 1
    run = line[s:e]
    return (s > 0 and line[s - 1] == "\U0001f3f4" and len(run) >= 2 and ord(run[-1]) == 0xE007F
            and all(0xE0020 <= ord(c) <= 0xE007E for c in run[:-1]))


def _emoji_base(c: str) -> bool:
    return bool(c) and c != BLANK and (unicodedata.category(c) == "So" or 0x1F3FB <= ord(c) <= 0x1F3FF)


def is_hidden(line: str, i: int, first_line: bool, before_nl: bool = False) -> bool:
    c = line[i]
    o, cat = ord(c), unicodedata.category(c)
    if c == "\t":
        return False
    if c == "\r":
        return not (before_nl and i == len(line) - 1)
    if c == BOM and first_line and i == 0:
        return False  # how some editors save UTF-8
    if cat not in ("Cf", "Co", "Cc") and not any(lo <= o <= hi for lo, hi in HIDDEN_EXTRA):
        return False
    prev = line[i - 1] if i > 0 else ""
    nxt = line[i + 1] if i + 1 < len(line) else ""
    if 0xE0000 <= o <= 0xE007F:
        return not _tag_sequence_ok(line, i)
    if c in (VS15, VS16):
        if c == VS16 and prev and prev in "0123456789#*" and nxt == KEYCAP:
            return False
        return not (prev and prev != BLANK and unicodedata.category(prev) in ("So", "Sm", "Po"))
    if c == ZWJ:
        if prev == VS16 and i > 1:
            prev = line[i - 2]  # a heart + emoji selector + ZWJ + fire is one legitimate sequence
        return not (_emoji_base(prev) and _emoji_base(nxt))
    if c == ZWNJ:
        return not (prev and nxt and unicodedata.category(prev).startswith("L") and unicodedata.category(nxt).startswith("L"))
    return True


def judge_hidden(rel: str, text: str) -> list:
    out = []
    lines = text.split("\n")
    for n, line in enumerate(lines, 1):
        for i in range(len(line)):
            if is_hidden(line, i, n == 1, before_nl=n < len(lines)):
                out.append(Failure(f"{rel}:{n}:{i + 1}", "hidden", f"invisible character U+{ord(line[i]):04X}"))
    return out


TEACH = """
How to fix: a memory line is `YYYY-MM-DD | "what the user said, word for word" | where`. If `where` is a file of
the vault (for example a chat imported by tools/import_chats.py), the whole phrase has to be in that file, and the
file has to be committed BEFORE the memory line that cites it. Delete an invisible character (the output says the
file, line and column), and keep URLs and commands out of the memory.
Deliberate bypass: git commit --no-verify
"""


def safe(s: str) -> str:
    return s.encode("utf-8", "backslashreplace").decode("utf-8")


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
    try:
        if top is not None:
            grel = reader.rel(vault / "gate.txt")
            blob = reader.git_show(f":{grel}") if grel else None
            modes = gate_modes(vault, blob.decode("utf-8") if blob is not None else None)
        else:
            modes = gate_modes(vault)
    except (ValueError, UnicodeDecodeError) as e:
        print(f"ERROR: {e}. The memory check judged nothing, so the commit is blocked until it is fixed.")
        return 2

    fails, warns, nv = [], [], []

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
            if mode == "120000" and (k or protected(p, vault, root)):
                fails.append(Failure(rel(p), "symlink", "symlink in place of a loaded path"))
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
                    if dp.is_symlink() and protected(dp, vault, root):
                        fails.append(Failure(rel(dp), "symlink", "symlink in place of a loaded path"))
                for fn in sorted(filenames):
                    fp = Path(dirpath) / fn
                    k = kinds(fp, vault, root)
                    if not k:
                        continue
                    if fp.is_symlink():
                        fails.append(Failure(rel(fp), "symlink", "symlink in place of a loaded path"))
                    else:
                        items[fp] = k
    if a.files:
        want = {Path(os.path.abspath(f if Path(f).exists() else vault / f)) for f in a.files}
        items = {p: k for p, k in items.items() if Path(os.path.abspath(p)) in want}

    for p, k in sorted(items.items()):
        r = rel(p)
        try:
            text = reader.text(p)
        except Unreadable as e:
            fails.append(Failure(r, "unreadable", f"{e}; a memory or loaded file that cannot be read is not a pass"))
            continue
        fails += judge_hidden(r, text)
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
    by = {c: [f for f in fails if f.check == c] for c, _ in CHECKS}
    if a.json:
        print(json.dumps({"files": len(items), "failures": [f._asdict() for f in fails], "warnings": warns,
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
        print(f"{len(items)} file(s) judged, {len(fails)} failure(s), {len(warns)} warning(s), {len(nv)} not verified")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
