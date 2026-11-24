#!/usr/bin/env python3
"""memory.py: a line of `vault/memory/` is what the user said, and the hook proves it. Stdlib only.

    memory.py [--vault vault] [--root .] [--staged] [--json] [FILE ...]

Why it exists: rule 2 says a line enters `vault/memory/` only with the user's "yes", a date and the verbatim
phrase. Nothing used to check it. And the memory is the one thing every later session OBEYS: a line planted
there (an instruction that looks like a quote, or a hidden character that a reader cannot see) becomes an
instruction of every session after it. Poisoned memory is a risk measured in research of Nov 2026, and a
template that keeps memory in a file all sessions obey has to refuse an instruction and invisible text there.

A memory file is a `.md` directly in `vault/memory/` or in `vault/people/<handle>/memory/` (team mode), except
`observations.md` (where the model PROPOSES, so the hook does not judge it) and the `archive/` folders. A line
after the `Format of each line:` line must be an entry, a `#` title, or the EXACT pointer line `tools/cool.py`
leaves behind (nothing else may share its line). An entry is

    YYYY-MM-DD | "verbatim phrase" | where | stale_after: YYYY-MM-DD | superseded_by: YYYY-MM-DD

(straight or curly quotes; the last two fields are optional and a later piece reads them).

The 7 checks:
  shape      every line after `Format of each line:` is an entry, a title or the cool pointer; the marker must exist   blocks
  date       the entry date is a real date and not after tomorrow; so are the dates of the final fields                blocks
  source     `where` is a file of the vault: the phrase has to be in it (core/quote.py: `[...]` and `...` allowed,
             whole words). Not found blocks. A source that resolves outside `vault/`, or inside a memory folder
             (a memory cannot vouch for a memory), blocks. `where` is not a file (`chat`): NOT_VERIFIED, and blocks
             only with `memory-source: block`. With --staged the source is read from HEAD: a source born in this
             very commit is NOT_VERIFIED ("commit the source first"), never verified                                    blocks / warns
  hidden     an invisible character in ANY file a session loads (CLAUDE.md, AGENTS.md, vault/CLAUDE.md, memory,
             skills): every Unicode category Cf plus the fillers and selectors listed in HIDDEN_EXTRA, with file:line:
             column and the code point. A BOM at the start of the file is fine; an emoji selector (U+FE0E/F) after a
             symbol (category So), and a ZWJ between two symbols, are fine                                              always blocks
  reach      a URL or a shell-looking command (in backticks: curl, wget, rm, sudo, | sh, | bash, eval, chmod +x) on
             ANY line of a memory file, header and titles included                                                      warns
  header     (--staged) the text above and including the format line changed against HEAD; a new file does not warn   warns
  unreadable a memory or loaded file that does not open or is not valid UTF-8 is a failure, not a pass                   blocks
`reach` and `header` block with `memory-reach: block` in vault/gate.txt.

rc: 0 clean, or only warnings / NOT_VERIFIED · 1 a check that blocks failed · 2 usage, or vault/gate.txt malformed ·
3 git did not say what is staged. With --staged the candidates come from the git index (a path that matches the
patterns above) and the content judged is the INDEX content (`git show :path`), never the disk.
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
import budget  # noqa: E402
import gate  # noqa: E402
import quote  # noqa: E402

Failure = gate.Failure

CHECKS = [
    ("shape", "every line is an entry, a title or the cool pointer"),
    ("date", "the dates are real and not in the future"),
    ("source", "the phrase is in the file it cites, and that file is not a memory or outside the vault"),
    ("hidden", "no invisible character in a file a session loads"),
    ("reach", "no URL or shell command in a memory file"),
    ("header", "the header above the format line did not change"),
    ("unreadable", "a memory or loaded file opens and is valid UTF-8"),
]
MARKER = "Format of each line:"
# EXACTLY what tools/cool.py writes (`- [[memory/archive/<stem>|<n> older entries, moved word for word on <date>]]`), the whole line.
POINTER = re.compile(r"^- \[\[memory/archive/[^\]|/\n]+\|\d+ older entries, moved word for word on \d{4}-\d{2}-\d{2}\]\]$")
ENTRY = re.compile(r"^\s*(?:[-*]\s+)?(\d{4}-\d{2}-\d{2})\s*\|\s*[\"\u201c](.*)[\"\u201d]\s*\|\s*([^|]*?)\s*((?:\|\s*\w+:\s*[^|]*?\s*)*)$")
FIELD = re.compile(r"\|\s*(\w+):\s*([^|]*?)\s*(?=\||$)")
FIELD_KEYS = ("stale_after", "superseded_by")
ISO = re.compile(r"^\d{4}-\d{2}-\d{2}$")
SHELL = re.compile(r"`[^`\n]*(?:\bcurl\b|\bwget\b|\brm\s|\bsudo\b|\|\s*(?:sh|bash)\b|\beval\b|chmod\s+\+x)[^`\n]*`")
URL = re.compile(r"https?://", re.I)
MODES = ("warn", "block")
PEOPLE_MEMORY = re.compile(r"^people/[^/]+/memory/[^/]+\.md$")
SKILL = re.compile(r"^\.claude/skills/[^/]+/SKILL\.md$")

# Hidden text: every character of Unicode category Cf (zero-width, bidi controls, soft hyphen, BOM, tag characters...)
# plus these, which are not Cf: Hangul and Braille fillers that draw nothing, the combining grapheme joiner, Khmer
# inherent vowels, Mongolian selectors, and the variation selectors (U+FE00-FE0F, U+E0100-E01EF).
HIDDEN_EXTRA = ((0x034F, 0x034F), (0x115F, 0x1160), (0x3164, 0x3164), (0xFFA0, 0xFFA0), (0x17B4, 0x17B5),
                (0x180B, 0x180F), (0xFE00, 0xFE0F), (0xE0100, 0xE01EF))
ZWJ, VS15, VS16, BOM = "\u200d", "\ufe0e", "\ufe0f", "\ufeff"


class Unreadable(Exception):
    pass


def gate_modes(vault: Path) -> dict:
    """{"memory-source": mode, "memory-reach": mode} from vault/gate.txt. ValueError if the file is not understood.
    The keys of ring.py and target.py are known and skipped; anything else is an error."""
    modes = {"memory-source": "warn", "memory-reach": "warn"}
    f = vault / "gate.txt"
    if not f.exists():
        return modes
    try:
        lines = f.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError) as e:
        raise ValueError(f"vault/gate.txt exists but cannot be read ({type(e).__name__})")
    for n, raw in enumerate(lines, 1):
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


def is_memory_rel(relv: str) -> bool:
    """`relv` is a path relative to the vault: a memory file is vault/memory/*.md or vault/people/<h>/memory/*.md, not observations.md."""
    if relv.rsplit("/", 1)[-1] == "observations.md":
        return False
    return bool(re.match(r"^memory/[^/]+\.md$", relv) or PEOPLE_MEMORY.match(relv))


def in_memory_folder(relv: str) -> bool:
    return relv.startswith("memory/") or bool(re.match(r"^people/[^/]+/memory/", relv))


def memory_files(vault: Path) -> list[Path]:
    out = []
    for pattern in ("memory/*.md", "people/*/memory/*.md"):
        out += [p for p in vault.glob(pattern) if p.is_file() and p.name != "observations.md"]
    return sorted(out)


def loaded(vault: Path, root: Path) -> list[Path]:
    seen, out = set(), []
    for p in budget.loaded_files(vault, root) + budget.skill_files(root) + [root / "AGENTS.md"] + memory_files(vault):
        if p.is_file() and os.path.abspath(p) not in seen:
            seen.add(os.path.abspath(p))
            out.append(p)
    return out


def git_top(root: Path) -> Path:
    return Path(subprocess.run(["git", "-C", str(root), "rev-parse", "--show-toplevel"], capture_output=True, text=True,
                               check=True).stdout.strip()).resolve()


def staged_list(top: Path) -> list[Path]:
    """Paths in the git index that this commit adds or changes. Not resolved: a symlink is judged where it sits."""
    r = subprocess.run(["git", "-C", str(top), "diff", "--cached", "--name-only", "--diff-filter=ACMRT", "-z"],
                       capture_output=True, check=True)
    return [Path(os.path.abspath(top / c)) for c in r.stdout.decode("utf-8").split("\0") if c]


class Reader:
    """Reads from the disk, or (staged) from the git index, so a clean working copy cannot hide a dirty stage."""

    def __init__(self, top: Path | None):
        self.top = top

    def rel(self, path: Path) -> str | None:
        try:
            return Path(path).relative_to(self.top).as_posix()
        except (ValueError, TypeError):
            return None

    def git_show(self, spec: str) -> bytes | None:
        r = subprocess.run(["git", "-C", str(self.top), "show", spec], capture_output=True)
        return r.stdout if r.returncode == 0 else None

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

    def head(self, path: Path) -> str | None:
        """The content at HEAD, or None if HEAD does not have the file (a new file, or no commit yet)."""
        rel = self.rel(path) if self.top is not None else None
        raw = self.git_show(f"HEAD:{rel}") if rel else None
        return None if raw is None else raw.decode("utf-8", errors="replace")

    def in_index(self, path: Path) -> bool:
        rel = self.rel(path) if self.top is not None else None
        return bool(rel) and self.git_show(f":{rel}") is not None


def valid_date(s: str) -> date | None:
    if not ISO.match(s):
        return None
    try:
        return date.fromisoformat(s)
    except ValueError:
        return None


def judge_source(at: str, where: str, phrase: str, vault: Path, reader: Reader, modes: dict):
    """(failure | None, not_verified | None) for the `where` of one entry."""
    cand = vault / where
    res = Path(os.path.realpath(cand))
    staged = reader.top is not None
    exists = cand.is_file() or (staged and (reader.head(res) is not None or reader.in_index(res)))
    if not exists:
        msg = f'{at} source "{where}" is not a file in the vault'
        if modes["memory-source"] == "block":
            return Failure(at, "source", f'source "{where}" is not a file in the vault (vault/gate.txt: memory-source: block)'), None
        return None, f"NOT_VERIFIED: {msg}"
    try:
        relv = res.relative_to(vault).as_posix()
    except ValueError:
        return Failure(at, "source", f'source "{where}" resolves outside vault/'), None
    if in_memory_folder(relv):
        return Failure(at, "source", f'source "{where}" is a memory file: a memory cannot vouch for a memory'), None
    if staged:
        text = reader.head(res)
        if text is None:
            msg = f'{at} source "{where}" is new in this commit; commit the source first'
            if modes["memory-source"] == "block":
                return Failure(at, "source", f'source "{where}" is new in this commit; commit the source first (memory-source: block)'), None
            return None, f"NOT_VERIFIED: {msg}"
    else:
        try:
            text = res.read_bytes().decode("utf-8", errors="replace")
        except OSError as e:
            return Failure(at, "source", f'source "{where}" could not be read ({type(e).__name__})'), None
    got = quote.found(phrase, text)
    if got is False:
        return Failure(at, "source", f"the phrase is not in {where} (every stretch outside [brackets] and ... must be)"), None
    if got is None:
        return None, f'NOT_VERIFIED: {at} source "{where}": no stretch of 3+ words in the phrase to compare'
    return None, None


def judge_memory(rel: str, text: str, vault: Path, reader: Reader, today: date, modes: dict):
    """(failures, warnings, not_verified) for one memory file."""
    fails, warns, nv = [], [], []
    lines = text.split("\n")
    # reach: every line of the file, the header and the titles included
    for i, line in enumerate(lines):
        if URL.search(line) or SHELL.search(line):
            what = "a URL" if URL.search(line) else "a shell-looking command"
            at = f"{rel}:{i + 1}"
            if modes["memory-reach"] == "block":
                fails.append(Failure(at, "reach", f"{what} in a memory file (vault/gate.txt: memory-reach: block)"))
            else:
                warns.append(f"WARNING {at} :: reach :: {what} in a memory file (memory is obeyed by every session; vault/gate.txt: memory-reach: warn)")
    start = next((i for i, l in enumerate(lines) if l.startswith(MARKER)), None)
    if start is None:
        fails.append(Failure(rel, "shape", f"the file has no line starting with `{MARKER}`, so no line can be judged"))
        return fails, warns, nv
    for i in range(start + 1, len(lines)):
        line, at = lines[i], f"{rel}:{i + 1}"
        if not line.strip() or line.lstrip().startswith("#") or POINTER.match(line):
            continue
        m = ENTRY.match(line)
        fields = FIELD.findall(m.group(4)) if m else []
        if not m or any(k not in FIELD_KEYS for k, _ in fields):
            hint = "a final field other than stale_after / superseded_by" if m else \
                'expected `YYYY-MM-DD | "verbatim phrase" | where` (a title, the exact pointer line of tools/cool.py and blank lines are allowed)'
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
        f, n = judge_source(at, where, phrase, vault, reader, modes)
        if f:
            fails.append(f)
        if n:
            nv.append(n)
    return fails, warns, nv


def header_of(text: str) -> str:
    lines = text.split("\n")
    start = next((i for i, l in enumerate(lines) if l.startswith(MARKER)), None)
    return "\n".join(lines if start is None else lines[:start + 1])


def judge_header(rel: str, text: str, path: Path, reader: Reader, modes: dict):
    """Staged only: the text above (and on) the format line is what the user wrote once; a change deserves a look."""
    old = reader.head(path)
    if old is None or header_of(old) == header_of(text):
        return None, None
    msg = f"{rel}: the header above the format line changed; memory files take dated entries only"
    if modes["memory-reach"] == "block":
        return Failure(rel, "header", msg + " (vault/gate.txt: memory-reach: block)"), None
    return None, f"WARNING: {msg}"


def is_hidden(line: str, i: int, first_line: bool) -> bool:
    c = line[i]
    if c == BOM and first_line and i == 0:
        return False  # how some editors save UTF-8
    o = ord(c)
    if unicodedata.category(c) != "Cf" and not any(lo <= o <= hi for lo, hi in HIDDEN_EXTRA):
        return False
    prev = line[i - 1] if i > 0 else ""
    nxt = line[i + 1] if i + 1 < len(line) else ""
    if c in (VS15, VS16):
        return not (prev and unicodedata.category(prev) == "So")
    if c == ZWJ:
        if prev == VS16 and i > 1:
            prev = line[i - 2]  # a heart + emoji selector + ZWJ + fire is one legitimate sequence
        return not (prev and nxt and unicodedata.category(prev) == "So" and unicodedata.category(nxt) == "So")
    return True


def judge_hidden(rel: str, text: str) -> list:
    out = []
    for n, line in enumerate(text.split("\n"), 1):
        for i in range(len(line)):
            if is_hidden(line, i, n == 1):
                out.append(Failure(f"{rel}:{n}:{i + 1}", "hidden", f"invisible character U+{ord(line[i]):04X}"))
    return out


TEACH = """
How to fix: a memory line is `YYYY-MM-DD | "what the user said, word for word" | where`. If `where` is a file of
the vault (for example a chat imported by tools/import_chats.py), the phrase has to be in that file, and the file
has to be committed BEFORE the memory line that cites it. Delete an invisible character (the output says the file,
line and column), and keep URLs and commands out of the memory.
Deliberate bypass: git commit --no-verify
"""


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("files", nargs="*")
    ap.add_argument("--vault", default="vault")
    ap.add_argument("--root", help="the repo root with CLAUDE.md, AGENTS.md and .claude/ (default: the vault's parent folder)")
    ap.add_argument("--staged", action="store_true", help="only what is in the git index, read from the index")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--today", help=argparse.SUPPRESS)
    a = ap.parse_args(argv)
    vault = Path(a.vault).resolve()
    root = Path(a.root).resolve() if a.root else vault.parent
    if not vault.is_dir():
        print(f"ERROR: the vault '{vault}' does not exist.", file=sys.stderr)
        return 2
    try:
        modes = gate_modes(vault)
    except ValueError as e:
        print(f"ERROR: {e}. The memory check judged nothing, so the commit is blocked until it is fixed.")
        return 2
    try:
        today = date.fromisoformat(a.today) if a.today else date.today()
    except ValueError:
        print("ERROR: --today must be YYYY-MM-DD", file=sys.stderr)
        return 2

    def memory_kind(p: Path) -> bool:
        try:
            return is_memory_rel(Path(p).relative_to(vault).as_posix())
        except ValueError:
            return False

    top = None
    items: dict[Path, bool] = {}   # path -> is a memory file (every item is a loaded file)
    if a.staged:
        try:
            top = git_top(root)
            staged = staged_list(top)
        except (subprocess.CalledProcessError, OSError, UnicodeDecodeError):
            print("NOT_VERIFIED: could not read the git stage (git missing, or the repo root is not in a repo).")
            return 3
        fixed = {Path(os.path.abspath(p)) for p in budget.loaded_files(vault, root) + [root / "AGENTS.md"]}
        for p in staged:
            is_mem = memory_kind(p)
            try:
                is_skill = bool(SKILL.match(p.relative_to(root).as_posix()))
            except ValueError:
                is_skill = False
            if is_mem or p in fixed or is_skill:
                items[p] = is_mem
    else:
        for p in loaded(vault, root):
            items[Path(os.path.abspath(p))] = memory_kind(p)
    if a.files:
        want = {Path(os.path.abspath(f if Path(f).exists() else vault / f)) for f in a.files}
        items = {p: m for p, m in items.items() if p in want}
    reader = Reader(top)

    def rel(p: Path) -> str:
        for base in (root, vault):
            try:
                return p.relative_to(base).as_posix()
            except ValueError:
                pass
        return p.name

    fails, warns, nv = [], [], []
    for p, is_mem in sorted(items.items()):
        r = rel(p)
        try:
            text = reader.text(p)
        except Unreadable as e:
            fails.append(Failure(r, "unreadable", f"{e}; a memory or loaded file that cannot be read is not a pass"))
            continue
        fails += judge_hidden(r, text)
        if is_mem:
            f, w, n = judge_memory(r, text, vault, reader, today, modes)
            fails += f
            warns += w
            nv += n
            if a.staged:
                hf, hw = judge_header(r, text, p, reader, modes)
                if hf:
                    fails.append(hf)
                if hw:
                    warns.append(hw)
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
