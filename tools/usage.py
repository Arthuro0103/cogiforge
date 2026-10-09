#!/usr/bin/env python3
"""usage.py: which notes were USED, and which sit still, by area. Stdlib only.

    python3 tools/usage.py [--vault vault] [--days 90] [--today YYYY-MM-DD] [--json]
    python3 tools/usage.py idle --project NAME [--top 3] [--vault vault] [--days 90] [--today YYYY-MM-DD]

A note in `notes/` is USED when at least one of these is true (the definition is in WHY.md, mistake 11):
  output   a project file (anything under `projects/`) or a note whose `type:` is article, brief or
           routine links to it: it went into something that leaves the notes;
  asked    a /cf-ask answer that passed `ask.py cite --log` (date and cited notes only, never the question) cited it (vault/memory/ask-log.jsonl).
Anything else is UNUSED. An unused note is STALE when its `date:` is `--days` days old or more, and
IDLE when it is younger. A note with no readable `date:` is UNDATED: it is counted, never guessed.

With no notes under `notes/` it prints NOT_VERIFIED and exits 3: "0% idle" of nothing is not a result.
`idle --project NAME` lists up to --top unused notes of that project, oldest first: what the
open/close-session skills bring back into view. rc: 0 report · 2 usage · 3 NOT_VERIFIED
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "core"))
import gate  # noqa: E402
import ring  # noqa: E402
sys.path.insert(0, str(Path(__file__).resolve().parent))
import ask  # noqa: E402  (the one that writes the log, so the path cannot drift)

OUTPUT_TYPES = ("article", "brief", "routine")
ASK_LOG = ask.ASK_LOG.as_posix()
H1 = re.compile(r"^#\s+(.+?)\s*$", re.M)


def read_log(vault: Path) -> tuple[dict[str, str], int]:
    """({note path without .md: date of the last time an answer cited it}, malformed lines)."""
    cited: dict[str, str] = {}
    bad = 0
    f = vault / ASK_LOG
    if not f.is_file():
        return cited, bad
    for line in f.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
            when, paths = str(row["date"]), row["cited"]
            if not isinstance(paths, list):
                raise TypeError
        except (ValueError, KeyError, TypeError):
            bad += 1
            continue
        for p in paths:
            p = str(p).removesuffix(".md")
            if when >= cited.get(p, ""):
                cited[p] = when
    return cited, bad


def front(text: str) -> dict:
    block, _ = gate.split_frontmatter(text.split("\n"))
    return gate.parse_fm(block)[0] if block is not None else {}


def parse_day(value) -> date | None:
    try:
        return date.fromisoformat(str(value).strip()[:10])
    except ValueError:
        return None


def scan(vault: Path, today: date, days: int) -> dict:
    idx = gate.Index(vault, areas={})
    md = sorted(r for r in idx.paths.values() if r.endswith(".md"))
    subjects = [r for r in md if r.startswith("notes/")]
    used: dict[str, set[str]] = {}
    meta: dict[str, dict] = {}
    for rel in md:
        text = Path(vault, rel).read_bytes().decode("utf-8", errors="replace")
        fm = front(text) if rel.startswith("notes/") or rel.startswith("projects/") else {}
        title = H1.search(text)
        meta[rel] = {"fm": fm, "title": title.group(1) if title else Path(rel).stem}
        is_output = rel.startswith("projects/") or str(fm.get("type", "")).strip() in OUTPUT_TYPES
        for a in ring.link_targets(vault, rel):
            r = idx.find(a, rel)
            if r and r != rel and r.startswith("notes/") and is_output:
                used.setdefault(r, set()).add("output")
    cited, bad_log = read_log(vault)
    for rel in subjects:
        if rel.removesuffix(".md") in cited:
            used.setdefault(rel, set()).add("asked")
    rows = []
    for rel in subjects:
        parts = rel.split("/")
        d = parse_day(meta[rel]["fm"].get("date")) if meta[rel]["fm"].get("date") else None
        age = (today - d).days if d else None
        if rel in used:
            state = "used"
        elif age is None:
            state = "undated"
        else:
            state = "stale" if age >= days else "idle"
        rows.append({"note": rel, "area": parts[1] if len(parts) > 2 else "(root of notes/)", "state": state,
                     "age": age, "title": meta[rel]["title"], "project": str(meta[rel]["fm"].get("project") or ""),
                     "why": sorted(used.get(rel, []))})
    outputs = sum(1 for r in md if r.startswith("projects/"))
    return {"rows": rows, "outputs": outputs, "asked": len(cited), "bad_log_lines": bad_log}


def summarize(rows: list[dict]) -> dict:
    by = {}
    for r in rows:
        a = by.setdefault(r["area"], {"notes": 0, "used": 0, "idle": 0, "stale": 0, "undated": 0})
        a["notes"] += 1
        a[r["state"]] += 1
    return dict(sorted(by.items()))


def pct(n: int, total: int) -> str:
    return f"{100 * n / total:.0f}%" if total else "-"


def render(data: dict, days: int, today: date) -> str:
    rows = data["rows"]
    by = summarize(rows)
    total = len(rows)
    sums = {k: sum(a[k] for a in by.values()) for k in ("used", "idle", "stale", "undated")}
    out = [f"Usage on {today.isoformat()}: {total} note(s) under notes/; stale = unused and {days}+ days old.", "",
           f"| area | notes | used | idle | stale | undated |", "|---|---|---|---|---|---|"]
    for name, a in by.items():
        out.append(f"| {name} | {a['notes']} | {a['used']} ({pct(a['used'], a['notes'])}) | {a['idle']} | "
                   f"{a['stale']} ({pct(a['stale'], a['notes'])}) | {a['undated']} |")
    out.append(f"| **all** | {total} | {sums['used']} ({pct(sums['used'], total)}) | {sums['idle']} | "
               f"{sums['stale']} ({pct(sums['stale'], total)}) | {sums['undated']} |")
    out.append("")
    out.append(f"Read from: {data['outputs']} project file(s); {data['asked']} distinct note(s) cited in vault/{ASK_LOG}.")
    if data["bad_log_lines"]:
        out.append(f"WARNING: {data['bad_log_lines']} malformed line(s) in vault/{ASK_LOG} were ignored.")
    if not data["outputs"] and not data["asked"]:
        out.append("No project file and no logged answer exists yet, so nothing could have used a note: the 0 is real, not a gap in the report.")
    if sums["undated"]:
        out.append(f"{sums['undated']} note(s) have no readable date: they are in neither idle nor stale.")
    return "\n".join(out)


def idle_for(rows: list[dict], project: str, top: int) -> list[dict]:
    mine = [r for r in rows if r["project"] == project and r["state"] in ("stale", "idle", "undated")]
    return sorted(mine, key=lambda r: (-(r["age"] if r["age"] is not None else -1), r["note"]))[:top]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("mode", nargs="?", choices=["report", "idle"], default="report")
    ap.add_argument("--vault", default=str(ROOT / "vault"))
    ap.add_argument("--days", type=int, default=90)
    ap.add_argument("--today", help="YYYY-MM-DD, for a reproducible report (default: the system date)")
    ap.add_argument("--project")
    ap.add_argument("--top", type=int, default=3)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    vault = Path(a.vault)
    today = parse_day(a.today) if a.today else date.today()
    if today is None or a.days < 1 or a.top < 1 or (a.mode == "idle" and not a.project):
        ap.error("--today must be YYYY-MM-DD, --days and --top at least 1, and idle needs --project")
    if not vault.is_dir():
        print(f"NOT_VERIFIED: the vault '{vault}' does not exist, so no usage was measured.")
        return 3
    data = scan(vault, today, a.days)
    if not data["rows"]:
        print("NOT_VERIFIED: there is no note under notes/, so usage was not measured (0 notes is not 0% idle).")
        return 3
    if a.mode == "idle":
        picks = idle_for(data["rows"], a.project, a.top)
        if not picks:
            print(f"No idle note for project '{a.project}'.")
        for r in picks:
            age = f"{r['age']} days" if r["age"] is not None else "undated"
            print(f"[[{r['note'].removesuffix('.md')}|{r['title']}]]  ({age}, {r['state']})")
        return 0
    if a.json:
        print(json.dumps({"summary": summarize(data["rows"]), "outputs": data["outputs"], "asked": data["asked"],
                          "bad_log_lines": data["bad_log_lines"]}, ensure_ascii=False, indent=2))
    else:
        print(render(data, a.days, today))
    return 0


if __name__ == "__main__":
    sys.exit(main())
