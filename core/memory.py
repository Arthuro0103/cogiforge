#!/usr/bin/env python3
"""memory.py: a line of `vault/memory/` is what the user said, and the hook proves it. Stdlib only.

    memory.py [--vault vault] [--root .] [--staged] [--json] [FILE ...]

Why it exists: rule 2 says a line enters `vault/memory/` only with the user's "yes", a date and the verbatim
phrase. Nothing used to check it. And the memory is the one thing every later session OBEYS: a line planted
there (an instruction that looks like a quote, or a hidden character that a reader cannot see) becomes an
instruction of every session after it. Poisoned memory is a risk measured in research of Nov 2026, and a
template that keeps memory in a file all sessions obey has to refuse an instruction and invisible text there.

A memory file is a `.md` directly in `vault/memory/`, except `observations.md` (where the model PROPOSES, so
the hook does not judge it) and the `archive/` folder. A line after the `Format of each line:` line must be an
entry, a `#` title, or the pointer line `tools/cool.py` leaves behind. An entry is

    YYYY-MM-DD | "verbatim phrase" | where | stale_after: YYYY-MM-DD | superseded_by: YYYY-MM-DD

(straight or curly quotes; the last two fields are optional and a later piece reads them).

The 5 checks:
  shape    every line after `Format of each line:` is an entry, a title or a pointer; the marker must exist     blocks
  date     the entry date is a real date and not after tomorrow; so are the dates of the final fields           blocks
  source   `where` is a file of the vault: the phrase has to be in it (core/quote.py: `[...]` and `...` allowed,
           whole words). Not found blocks. `where` is not a file (`chat`): NOT_VERIFIED, and blocks only with
           `memory-source: block` in vault/gate.txt. Nothing measurable in the phrase is NOT_VERIFIED too    blocks / warns
  hidden   an invisible or direction-changing character in ANY file a session loads (CLAUDE.md, AGENTS.md,
           vault/CLAUDE.md, memory, skills): file:line:column and the code point. A BOM at the very start of a
           file and the emoji selectors U+FE0E/U+FE0F are fine                                                   always blocks
  reach    a URL or a shell-looking command (in backticks: curl, wget, rm, sudo, | sh, | bash, eval,
           chmod +x) inside an entry: a warning, and blocks with `memory-reach: block`                           warns

rc: 0 clean, or only warnings / NOT_VERIFIED · 1 a check that blocks failed (it wins over rc 3, so a found
problem is never hidden by a file that could not be read) · 2 usage, or vault/gate.txt malformed ·
3 could not read (an unreadable file, or git did not say what is staged).
With --staged, only the files in the git index are judged, and they are read FROM the index.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import budget  # noqa: E402
import gate  # noqa: E402
import quote  # noqa: E402

Failure = gate.Failure

CHECKS = [
    ("shape", "every line is an entry, a title or a pointer"),
    ("date", "the dates are real and not in the future"),
    ("source", "the phrase is in the file it cites"),
    ("hidden", "no invisible character in a file a session loads"),
    ("reach", "no URL or shell command inside an entry"),
]
MARKER = "Format of each line:"
POINTER = re.compile(r"^.*\[\[memory/archive/[^\]]+\]\].*$")  # tools/cool.py leaves this line behind
ENTRY = re.compile(r"^\s*(?:[-*]\s+)?(\d{4}-\d{2}-\d{2})\s*\|\s*[\"“](.*)[\"”]\s*\|\s*([^|]*?)\s*((?:\|\s*\w+:\s*[^|]*?\s*)*)$")
FIELD = re.compile(r"\|\s*(\w+):\s*([^|]*?)\s*(?=\||$)")
FIELD_KEYS = ("stale_after", "superseded_by")
STARTS_WITH_DATE = re.compile(r"^\s*(?:[-*]\s+)?\d{4}-\d{2}-\d{2}\b")
ISO = re.compile(r"^\d{4}-\d{2}-\d{2}$")
SHELL = re.compile(r"`[^`\n]*(?:\bcurl\b|\bwget\b|\brm\s|\bsudo\b|\|\s*(?:sh|bash)\b|\beval\b|chmod\s+\+x)[^`\n]*`")
URL = re.compile(r"https?://", re.I)
MODES = ("warn", "block")

# U+FE0E and U+FE0F (emoji selectors) are NOT here: they are ordinary in text with emoji.
HIDDEN = re.compile("[​-‏‪-‮⁠-⁤⁦-⁩؜᠎­ㅤ﻿"
                    "\U000e0000-\U000e007f\U000e0100-\U000e01ef]")


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


def memory_files(vault: Path) -> list[Path]:
    d = vault / "memory"
    return sorted(p for p in d.glob("*.md") if p.is_file() and p.name != "observations.md") if d.is_dir() else []


def loaded(vault: Path, root: Path) -> list[Path]:
    seen, out = set(), []
    for p in budget.loaded_files(vault, root) + budget.skill_files(root) + [root / "AGENTS.md"] + memory_files(vault):
        if p.is_file() and p.resolve() not in seen:
            seen.add(p.resolve())
            out.append(p)
    return out


def git_top(root: Path) -> Path:
    return Path(subprocess.run(["git", "-C", str(root), "rev-parse", "--show-toplevel"], capture_output=True, text=True,
                               check=True).stdout.strip()).resolve()


def staged_set(top: Path) -> set[Path]:
    r = subprocess.run(["git", "-C", str(top), "diff", "--cached", "--name-only", "--diff-filter=ACMR", "-z"],
                       capture_output=True, check=True)
    return {(top / c).resolve() for c in r.stdout.decode("utf-8").split("\0") if c}


class Reader:
    """Reads a file from the disk, or (with --staged) from the git index, so a clean working copy cannot hide a dirty stage."""

    def __init__(self, top: Path | None):
        self.top = top

    def text(self, path: Path, worktree_ok: bool = False) -> str:
        try:
            if self.top is not None:
                rel = path.resolve().relative_to(self.top).as_posix()
                r = subprocess.run(["git", "-C", str(self.top), "show", f":{rel}"], capture_output=True)
                if r.returncode == 0:
                    return r.stdout.decode("utf-8")
                if not worktree_ok:
                    raise Unreadable(f"{rel}: git could not show it from the index")
            return path.read_bytes().decode("utf-8")
        except (OSError, UnicodeDecodeError, ValueError) as e:
            raise Unreadable(f"{path.name}: {type(e).__name__}")


def valid_date(s: str) -> date | None:
    if not ISO.match(s):
        return None
    try:
        return date.fromisoformat(s)
    except ValueError:
        return None


def judge_memory(rel: str, text: str, vault: Path, reader: Reader, today: date, modes: dict):
    """(failures, warnings, not_verified) for one memory file."""
    fails, warns, nv = [], [], []
    lines = text.split("\n")
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
                'expected `YYYY-MM-DD | "verbatim phrase" | where` (title, pointer line and blank lines are allowed)'
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
        # source
        target = None
        if where and not Path(where).is_absolute() and ".." not in Path(where).parts:
            c = vault / where
            if c.is_file():
                target = c
        if target is None:
            msg = f'{at} source "{where}" is not a file in the vault'
            if modes["memory-source"] == "block":
                fails.append(Failure(at, "source", f'source "{where}" is not a file in the vault (vault/gate.txt: memory-source: block)'))
            else:
                nv.append(f"NOT_VERIFIED: {msg}")
        else:
            try:
                got = quote.found(phrase, reader.text(target, worktree_ok=True))
            except Unreadable as e:
                raise Unreadable(f"{at} source {where}: {e}")
            if got is False:
                fails.append(Failure(at, "source", f'the phrase is not in {where} (every stretch outside [brackets] and ... must be)'))
            elif got is None:
                nv.append(f'NOT_VERIFIED: {at} source "{where}": no stretch of 3+ words in the phrase to compare')
        # reach
        if URL.search(line) or SHELL.search(line):
            what = "a URL" if URL.search(line) else "a shell-looking command"
            if modes["memory-reach"] == "block":
                fails.append(Failure(at, "reach", f"{what} inside an entry (vault/gate.txt: memory-reach: block)"))
            else:
                warns.append(f"WARNING {at} :: reach :: {what} inside an entry (memory is obeyed by every session; vault/gate.txt: memory-reach: warn)")
    return fails, warns, nv


def judge_hidden(rel: str, text: str) -> list:
    out = []
    for n, line in enumerate(text.split("\n"), 1):
        for m in HIDDEN.finditer(line):
            if m.group(0) == "﻿" and n == 1 and m.start() == 0:
                continue  # a BOM at the very start of the file is how some editors save UTF-8
            out.append(Failure(f"{rel}:{n}:{m.start() + 1}", "hidden", f"invisible character U+{ord(m.group(0)):04X}"))
    return out


TEACH = """
How to fix: a memory line is `YYYY-MM-DD | "what the user said, word for word" | where`. If `where` is a file of
the vault (for example a chat imported by tools/import_chats.py), the phrase has to be in that file. Delete an
invisible character (the output says the file, line and column), and keep URLs and commands out of the memory.
Deliberate bypass: git commit --no-verify
"""


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("files", nargs="*")
    ap.add_argument("--vault", default="vault")
    ap.add_argument("--root", help="the repo root with CLAUDE.md, AGENTS.md and .claude/ (default: the vault's parent folder)")
    ap.add_argument("--staged", action="store_true", help="only the files in the git index, read from the index")
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
    mem, load = memory_files(vault), loaded(vault, root)
    top = None
    if a.staged:
        try:
            top = git_top(root)
            staged = staged_set(top)
        except (subprocess.CalledProcessError, OSError, UnicodeDecodeError):
            print("NOT_VERIFIED: could not read the git stage (git missing, or the repo root is not in a repo).")
            return 3
        mem, load = [p for p in mem if p.resolve() in staged], [p for p in load if p.resolve() in staged]
    if a.files:
        want = set()
        for f in a.files:
            p = Path(f) if Path(f).exists() else vault / f
            want.add(p.resolve())
        mem, load = [p for p in mem if p.resolve() in want], [p for p in load if p.resolve() in want]
    reader = Reader(top)

    def rel(p: Path) -> str:
        r = p.resolve()
        for base in (root, vault):
            try:
                return r.relative_to(base.resolve()).as_posix()
            except ValueError:
                pass
        return p.name

    fails, warns, nv, unreadable = [], [], [], []
    for p in mem:
        try:
            f, w, n = judge_memory(rel(p), reader.text(p), vault, reader, today, modes)
        except Unreadable as e:
            unreadable.append(str(e))
            continue
        fails += f
        warns += w
        nv += n
    for p in load:
        try:
            fails += judge_hidden(rel(p), reader.text(p))
        except Unreadable as e:
            unreadable.append(str(e))
    judged = len({p.resolve() for p in mem + load})
    by = {c: [f for f in fails if f.check == c] for c, _ in CHECKS}
    if a.json:
        print(json.dumps({"files": judged, "failures": [f._asdict() for f in fails], "warnings": warns,
                          "not_verified": nv, "unreadable": unreadable,
                          "checks": {c: len(v) for c, v in by.items()}}, ensure_ascii=False, indent=2))
    else:
        for u in unreadable:
            print(f"NOT_VERIFIED: could not read {u}")
        for f in fails:
            print(f"FAILS {f.file} :: {f.check} :: {f.msg}")
        for w in warns:
            print(w)
        for n in nv:
            print(n)
        if fails:
            print(TEACH)
        print(f"{judged} file(s) judged, {len(fails)} failure(s), {len(warns)} warning(s), {len(nv)} not verified, {len(unreadable)} unreadable")
    if fails:
        return 1
    return 3 if unreadable else 0


if __name__ == "__main__":
    sys.exit(main())
