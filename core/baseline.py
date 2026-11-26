#!/usr/bin/env python3
"""baseline.py: the old debt that `tools/adopt.py` measured and saved in `.cogiforge/baseline.json`. Stdlib only.

ring.py (--gate --stage) and gate.py (when it is given files, which is how the hook calls it) look for that file
in the root of the vault by themselves. Without it nothing changes: a workbench has no baseline. With it, the
debt the baseline lists blocks nobody, and anything NEW still does:

  orphans              a listed note with no link does not fail ring.py
  dead_links           a listed `[[target]]` in a listed note does not fail gate.py (line numbers are ignored: editing
                       the note moves them; the same target may repeat only as many times as the baseline counts)
  area_missing         a listed note without `area:` does not fail the gate area check (any other area failure does)
  frontmatter_errors   a listed note whose frontmatter does not parse does not fail the gate frontmatter check

The list is read from git, never from the disk, and the STRICTER of two copies wins (the same idea as vault/gate.txt in
core/memory.py): what the baseline in HEAD lists AND what the one in the index lists, the intersection of both. A commit
that adds a note to the list gets no exemption for it. With no commit yet (the first one) the index decides. A baseline
that is not in the index (untracked, or removed by this commit), one that HEAD does not have while HEAD exists, one that
is not a regular file, or one that cannot be read or understood, exempts nothing: it is the behavior without a baseline.
Outside a git repository the file on the disk is read.
"""
import collections
import json
import re
import subprocess
import unicodedata
from pathlib import Path

BASELINE = ".cogiforge/baseline.json"
DEAD_MSG = re.compile(r"^\[\[(.*)\]\] does not resolve \(line \d+\)$", re.S)
AREA_MSG = "missing area: field"  # the only area failure the baseline's `area_missing` describes (gate.chk_area)


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
                ok = file in self.area_missing and f.msg.startswith(AREA_MSG)
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


def load(vault):
    """The Exempt for this vault: from the index and HEAD when the vault is in a git repository, else from the disk."""
    vault = Path(vault).resolve()
    top = _git_top(vault)
    if top is None:
        f = vault / BASELINE
        try:
            ok = f.is_file() and not f.is_symlink()
            return (parse(f.read_bytes()) if ok else None) or Exempt()
        except OSError:
            return Exempt()
    from memory import Reader, REGULAR  # late: memory imports gate, and gate imports this module
    reader = Reader(top)
    rel = reader.rel(vault / BASELINE)
    entry = reader.index_entry(rel) if rel else None
    if entry is None or entry[0] not in REGULAR:
        return Exempt()
    raw = reader.blob(entry[1])
    now = parse(raw) if raw is not None else None
    if now is None:
        return Exempt()
    if not reader.has_head():
        return now
    head_entry = reader.head_entry(rel)
    if head_entry is None or head_entry[1] != "blob":
        return Exempt()
    head_raw = reader.blob(head_entry[2])
    before = parse(head_raw) if head_raw is not None else None
    return now.intersect(before) if before is not None else Exempt()
