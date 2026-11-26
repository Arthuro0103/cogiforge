#!/usr/bin/env python3
"""baseline.py: the old debt that `tools/adopt.py` measured and saved in `.cogiforge/baseline.json`. Stdlib only.

ring.py (--gate --stage) and gate.py (when it is given files, which is how the hook calls it) look for that file
in the root of the vault by themselves. Without it nothing changes: a workbench has no baseline. With it, the
debt the baseline lists blocks nobody, and anything NEW still does:

  orphans              a listed note with no link does not fail ring.py
  dead_links           a listed `[[target]]` in a listed note does not fail gate.py (line numbers are ignored: editing
                       the note moves them; the same target may repeat only as many times as the baseline counts)
  area_missing         a listed note does not fail the gate area check, whatever the failure is: adopt lists the notes
                       that sit under an area folder with no `area:`, and in a vault with `notes/` the same note is also
                       "loose in notes/" or in a folder that belongs to no area, which the adopt-written areas.txt
                       does not settle
  frontmatter_errors   a listed note whose frontmatter does not parse does not fail the gate frontmatter check

Which copy of the list counts:
  HEAD has it and the index has it   the STRICTER of the two (the idea of vault/gate.txt in core/memory.py): the
                                     intersection. A commit that adds a note to the list gets no exemption for it.
  HEAD has it, the index does not    nothing (this commit removes it).
  HEAD does not have it              the one in the index; if it is not there either (untracked), the one on the disk.
                                     That is the usual case: notes committed first, adopt after, baseline not committed yet.
  no commit yet (the first one)      the index, else the disk.
When HEAD exists the exemption is also RESTRICTED to notes that HEAD already has: a note that was already committed is old
debt, a note that arrives in this commit never is, whatever the list says. Without HEAD (the first commit) every note is new
to git and the restriction is off.
The exemption is NOT a lock. Once the baseline is committed, a commit cannot add an entry to it (the committed version is
the ceiling). Before that, and in the first commit, whoever edits `.cogiforge/baseline.json` on the disk, or takes it out of
git in a separate commit, can widen the exemption, the same way `--no-verify` skips the hook: it takes wanting to get
around it. On a filesystem that tells them apart, two note names that differ only in NFC/NFD count as the same note (every
name is compared in NFC).
A baseline that cannot be read or understood exempts nothing and says so (`Exempt.problem`; ring.py and gate.py print one
line). No baseline at all is not a problem: it is the behavior without one. Outside a git repository the disk is read.
"""
import collections
import json
import re
import subprocess
import unicodedata
from pathlib import Path

BASELINE = ".cogiforge/baseline.json"
DEAD_MSG = re.compile(r"^\[\[(.*)\]\] does not resolve \(line \d+\)$", re.S)


def nfc(s):
    return unicodedata.normalize("NFC", s)


class Exempt:
    """What the baseline lets through. Empty (the default) exempts nothing."""

    def __init__(self, orphans=(), dead_links=(), area_missing=(), frontmatter_errors=()):
        self.orphans = {nfc(x) for x in orphans}
        self.area_missing = {nfc(x) for x in area_missing}
        self.frontmatter_errors = {nfc(x) for x in frontmatter_errors}
        self.dead_links = collections.Counter()  # (note, target) -> how many times the baseline lists it
        for entry in dead_links:
            m = re.match(r"^(.*?):\d+ \[\[(.*)\]\]$", entry, re.S)
            if m:
                self.dead_links[(nfc(m.group(1)), m.group(2))] += 1

    problem = None  # why a baseline that exists could not be used (None: nothing wrong)

    def restrict(self, notes):
        """The same debt, only for the notes in `notes` (the ones HEAD already has)."""
        out = Exempt()
        out.orphans = self.orphans & notes
        out.area_missing = self.area_missing & notes
        out.frontmatter_errors = self.frontmatter_errors & notes
        out.dead_links = collections.Counter({k: v for k, v in self.dead_links.items() if k[0] in notes})
        return out

    def __bool__(self):
        return bool(self.orphans or self.dead_links or self.area_missing or self.frontmatter_errors)

    def intersect(self, other):
        out = Exempt()
        out.orphans = self.orphans & other.orphans
        out.area_missing = self.area_missing & other.area_missing
        out.frontmatter_errors = self.frontmatter_errors & other.frontmatter_errors
        out.dead_links = self.dead_links & other.dead_links  # Counter: the smaller count of each key
        return out

    def failures(self, failures):
        """(kept, exempted): `failures` is a list of gate.Failure. Order is kept; a dead link is exempted up to its count."""
        left = collections.Counter(self.dead_links)
        kept, exempted = [], []
        for f in failures:
            file = nfc(f.file)
            ok = False
            if f.check == "frontmatter":
                ok = file in self.frontmatter_errors
            elif f.check == "area":
                ok = file in self.area_missing  # ANY area failure of a listed note (adopt lists it for notes/ too)
            elif f.check == "dead-link":
                m = DEAD_MSG.match(f.msg)
                key = (file, m.group(1)) if m else None
                if key and left[key] > 0:
                    left[key] -= 1
                    ok = True
            (exempted if ok else kept).append(f)
        return kept, exempted


def parse(raw):
    """Exempt from the bytes of a baseline.json, or None when they are not a baseline this module understands."""
    try:
        data = json.loads(raw.decode("utf-8") if isinstance(raw, bytes) else raw)
    except (ValueError, UnicodeDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    lists = {}
    for key in ("orphans", "dead_links", "area_missing", "frontmatter_errors"):
        v = data.get(key, [])
        if not isinstance(v, list) or not all(isinstance(x, str) for x in v):
            return None
        lists[key] = v
    return Exempt(**lists)


def _git_top(vault):
    try:
        r = subprocess.run(["git", "-C", str(vault), "rev-parse", "--show-toplevel"], capture_output=True, text=True)
    except OSError:
        return None
    return Path(r.stdout.strip()).resolve() if r.returncode == 0 and r.stdout.strip() else None


def unreadable(why):
    out = Exempt()
    out.problem = why
    return out


def warning(exempt):
    """One line for the hook output when the baseline exists but could not be used, else None."""
    p = getattr(exempt, "problem", None)
    return f"WARNING: {BASELINE} could not be read ({p}): the old debt is NOT exempted in this commit." if p else None


def _disk(vault):
    f = vault / BASELINE
    if not f.exists() and not f.is_symlink():
        return Exempt()
    try:
        if f.is_symlink() or not f.is_file():
            return unreadable("not a regular file")
        got = parse(f.read_bytes())
    except OSError:
        return unreadable("it could not be opened")
    return got if got is not None else unreadable("it is not a baseline.json this version understands")


def _head_notes(reader, vault):
    """The paths HEAD has, RELATIVE TO THE VAULT (the baseline, the gate and ring.py all speak vault-relative paths; git
    speaks repo-relative ones, and the vault may be a folder inside the repo). What is outside the vault is dropped."""
    raw = reader.git("ls-tree", "-r", "-z", "--name-only", "HEAD")
    if raw is None:
        return None
    prefix = vault.relative_to(reader.top).as_posix()
    prefix = "" if prefix == "." else prefix + "/"
    out = set()
    for x in raw.decode("utf-8", errors="surrogateescape").split("\0"):
        if x and nfc(x).startswith(nfc(prefix)):
            out.add(nfc(x)[len(nfc(prefix)):])
    return out


def load(vault):
    """The Exempt for this vault (see the docstring for which copy of the list counts)."""
    vault = Path(vault).resolve()
    top = _git_top(vault)
    if top is None:
        return _disk(vault)
    from memory import Reader, REGULAR  # late: memory imports gate, and gate imports this module
    reader = Reader(top)
    rel = reader.rel(vault / BASELINE)
    if not rel:
        return Exempt()
    has_head = reader.has_head()
    head_entry = reader.head_entry(rel) if has_head else None
    entry = reader.index_entry(rel)
    if head_entry is not None:
        if entry is None:
            return Exempt()  # this commit removes it
        if entry[0] not in REGULAR or head_entry[1] != "blob":
            return unreadable("not a regular file")
        now, before = reader.blob(entry[1]), reader.blob(head_entry[2])
        now = parse(now) if now is not None else None
        before = parse(before) if before is not None else None
        if now is None or before is None:
            return unreadable("it is not a baseline.json this version understands")
        cand = now.intersect(before)
    elif entry is not None:
        if entry[0] not in REGULAR:
            return unreadable("not a regular file")
        raw = reader.blob(entry[1])
        cand = parse(raw) if raw is not None else None
        if cand is None:
            return unreadable("it is not a baseline.json this version understands")
    else:
        cand = _disk(vault)
    if has_head and cand:
        known = _head_notes(reader, vault)
        if known is None:
            return unreadable("git could not list HEAD")
        cand = cand.restrict(known)
    return cand
