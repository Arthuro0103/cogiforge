#!/usr/bin/env python3
"""cool.py: move the OLDER dated lines of a memory file to an archive that loads only on demand. Stdlib only.

    python3 tools/cool.py memory/decisions.md [--vault vault] [--keep 40]            plan: prints, writes nothing
    python3 tools/cool.py memory/decisions.md [--vault vault] [--keep 40] --apply    does it

A memory file (profile, patterns, decisions) is loaded in every session, so it can only grow until it crosses
the ceiling in core/budget.py. An entry is a line that starts with a date (`- 2026-08-14: ...`) plus the
indented lines under it. The `--keep` NEWEST entries stay; the older ones move, word for word, to
`memory/archive/<name>.md`, and one pointer line stays behind in the memory file, linking the archive by its
full path (so the archive is never an orphan). Nothing is reworded, merged or dropped: what the user said,
with its date and quote, is moved and never edited (rule 2 of the repo). Run it with the user's yes.
rc: 0 planned or done · 2 usage · 3 NOT_VERIFIED (the file is missing or has no dated entry, so nothing was cooled)
"""
from __future__ import annotations

import argparse
import re
import sys
from datetime import date
from pathlib import Path

ENTRY = re.compile(r"^\s*(?:[-*]\s+)?(\d{4}-\d{2}-\d{2})\b")
POINTER = re.compile(r"^.*\[\[memory/archive/[^\]]+\]\].*$")


def parse(text: str) -> list[dict]:
    """The file as items, in order: an entry (date + its lines), an old pointer line, or plain text."""
    items: list[dict] = []
    for line in text.split("\n"):
        m = ENTRY.match(line)
        if POINTER.match(line):
            items.append({"kind": "pointer", "lines": [line]})
        elif m:
            items.append({"kind": "entry", "date": m.group(1), "lines": [line]})
        elif items and items[-1]["kind"] == "entry" and line.strip() and line[:1] in " \t":
            items[-1]["lines"].append(line)  # a continuation of the entry above
        else:
            items.append({"kind": "text", "lines": [line]})
    return items


def choose(items: list[dict], keep: int) -> list[dict]:
    """The entries that move: all but the `keep` newest (ties: the later line is the newer one)."""
    entries = [i for i in items if i["kind"] == "entry"]
    newest = sorted(range(len(entries)), key=lambda k: (entries[k]["date"], k), reverse=True)[:keep]
    return [e for k, e in enumerate(entries) if k not in set(newest)]


def rebuild(items: list[dict], moved: list[dict], archive_rel: str, total: int, today: str) -> str:
    gone = {id(e) for e in moved}
    out = [i for i in items if id(i) not in gone and i["kind"] != "pointer"]
    pointer = {"kind": "pointer", "lines": [f"- [[{archive_rel}|{total} older entries, moved word for word on {today}]]"]}
    at = next((k for k, i in enumerate(out) if i["kind"] == "entry"), len(out))
    out.insert(at, pointer)
    return "\n".join(l for i in out for l in i["lines"])


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("file", help="the memory file, relative to the vault (for example memory/decisions.md)")
    ap.add_argument("--vault", default="vault")
    ap.add_argument("--keep", type=int, default=40)
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--today", help=argparse.SUPPRESS)
    a = ap.parse_args(argv)
    if a.keep < 1:
        ap.error("--keep must be at least 1")
    vault = Path(a.vault)
    path = vault / a.file
    rel = Path(a.file)
    if rel.is_absolute() or ".." in rel.parts or rel.parts[:1] != ("memory",) or "archive" in rel.parts or path.suffix != ".md":
        ap.error("the file must be a .md inside memory/ (not the archive itself), written relative to the vault")
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as e:
        print(f"NOT_VERIFIED: could not read {path} ({type(e).__name__}); nothing was cooled.")
        return 3
    items = parse(text)
    moved = choose(items, a.keep)
    kept = [i for i in items if i["kind"] == "entry" and i not in moved]
    if not kept and not moved:
        print(f"NOT_VERIFIED: {a.file} has no dated entry (a line that starts with YYYY-MM-DD), so nothing can be cooled.")
        return 3
    if not moved:
        print(f"Nothing to move: {len(kept)} dated entries, --keep {a.keep}.")
        return 0
    size = sum(len(l.encode("utf-8")) + 1 for e in moved for l in e["lines"])
    archive_rel = f"memory/archive/{path.stem}"
    print(f"{'Moving' if a.apply else 'Would move'} {len(moved)} of {len(kept) + len(moved)} dated entries "
          f"({size:,} bytes) from {a.file} to {archive_rel}.md, keeping the {len(kept)} newest.")
    if not a.apply:
        print("Plan only: nothing was written. Add --apply (with the user's yes) to do it.")
        return 0
    today = a.today or date.today().isoformat()
    archive = vault / f"{archive_rel}.md"
    archive.parent.mkdir(parents=True, exist_ok=True)
    old = archive.read_text(encoding="utf-8") if archive.is_file() else (
        f"# Older entries of {path.stem}, moved out of the memory that loads every session\n\n"
        f"These lines were moved word for word from [[memory/{path.stem}]]; none was edited.\n\n")
    body = "\n".join(l for e in sorted(moved, key=lambda e: e["date"]) for l in e["lines"]) + "\n"
    new_archive = old.rstrip("\n") + "\n" + body
    total = sum(1 for l in new_archive.split("\n") if ENTRY.match(l))
    archive.write_text(new_archive, encoding="utf-8")
    path.write_text(rebuild(items, moved, archive_rel, total, today), encoding="utf-8")
    print(f"Done: {archive_rel}.md now holds {total} entries; {a.file} keeps {len(kept)} and one pointer line.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
