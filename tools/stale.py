#!/usr/bin/env python3
"""stale.py: which memory lines (and notes) have gone stale, and why. Stdlib only.

    python3 tools/stale.py [--vault vault] [--root .] [--threshold 3] [--gate] [--json] [--today YYYY-MM-DD]

Why it exists: a memory line that states a fact about a file or a state ages. The file it cites disappears or
changes folder, or changes so much that the sentence no longer holds, and the next session obeys an old line.
Research of Nov 2026 on agent memory measured it: a "superseded" memory that stays loaded keeps being obeyed, so
marking it obsolete is not enough, it has to leave what loads. This tool measures; it does not decide or fix.
The field names (stale_after, superseded_by) come from the Open Knowledge Format (OKF); the dead-path / moved
/ aged signals follow the memory audit of the author's private vault (commits since a date, cited paths).

For every entry of every memory file (the same list core/memory.py judges: `vault/memory/*.md` and, in team
mode, `vault/people/<handle>/memory/*.md`; `archive/` is out), the paths cited in the phrase or in `where`
(inside `backticks` or `[[wikilinks]]`, relative to `vault/`; a `:line` suffix and a `|alias` are dropped):
  dead-path   the path does not exist and no file with the same name exists in the vault
  moved       it does not exist, but a file with the same name exists in another folder (the new path is shown)
  aged        the file exists and had `>= --threshold` commits AFTER the entry date (a folder does not count)
  expired     the entry has `stale_after:` in the past (relative to --today, default today); a note in
              `vault/notes/` with `stale_after:` in its frontmatter already past counts too
  superseded  the entry has `superseded_by:` and is still in a loaded file (it should be in the archive:
              `python3 tools/cool.py` moves it first)
Output: a count per signal and one line per finding (`file:line signal detail`).
rc: 0 report (it measures, it does not decide) · 1 `--gate` and at least one finding · 3 NOT_VERIFIED (a file
that cannot be read; no git means the `aged` signal is NOT_VERIFIED while the others still run) · 2 usage.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "core"))
import gate  # noqa: E402
import memory  # noqa: E402

SIGNALS = ("dead-path", "moved", "aged", "expired", "superseded")
TICKS = re.compile(r"`([^`\n]+)`")
WIKI = re.compile(r"\[\[([^\[\]\n]+)\]\]")
EXT = re.compile(r"\.[A-Za-z0-9]{1,8}$")


def cited_paths(text: str) -> list[str]:
    """Paths cited in `backticks` (only if they look like a file: an extension, no space) or in [[wikilinks]]."""
    out = []
    for raw in TICKS.findall(text):
        p = raw.strip()
        if " " in p or "://" in p:
            continue
        p = re.sub(r":\d+(?:-\d+)?$", "", p)
        if EXT.search(p) and not p.startswith(("/", "-")):
            out.append(p)
    for raw in WIKI.findall(text):
        p = gate.link_target(raw).split("#", 1)[0].strip()
        p = re.sub(r":\d+(?:-\d+)?$", "", p)
        if p and "://" not in p:
            out.append(p)
    return list(dict.fromkeys(out))


def vault_index(vault: Path) -> dict[str, list[str]]:
    """file name (lower case) -> relative paths, for every file of the vault."""
    names: dict[str, list[str]] = {}
    for dirpath, dirs, files in os.walk(vault):
        dirs[:] = sorted(d for d in dirs if d not in gate.IGNORE_DIRS)
        for fn in sorted(files):
            rel = (Path(dirpath) / fn).relative_to(vault).as_posix()
            names.setdefault(fn.lower(), []).append(rel)
    return names


def resolve(path: str, vault: Path, names: dict) -> tuple[str, str | None]:
    """('ok', None) | ('moved', new path) | ('dead', None)."""
    cands = [path] if EXT.search(path) else [path, path + ".md"]
    for c in cands:
        if (vault / c).exists():
            return "ok", None
    for c in cands:
        found = names.get(Path(c).name.lower(), [])
        if found:
            return "moved", found[0]
    return "dead", None


def git_ok(vault: Path) -> bool:
    try:
        r = subprocess.run(["git", "-C", str(vault), "rev-parse", "--is-inside-work-tree"], capture_output=True, text=True)
    except OSError:
        return False
    return r.returncode == 0 and r.stdout.strip() == "true"


def commits_after(vault: Path, rel: str, day: date) -> int | None:
    """Commits that touched `rel` after the end of `day`; None when git cannot say."""
    # midnight spelled out: git reads a bare date as that day at the CURRENT time of day, so the count
    # would change with the hour the tool runs
    since = f"{(day + timedelta(days=1)).isoformat()} 00:00:00"
    try:
        r = subprocess.run(["git", "-C", str(vault), "log", f"--since={since}", "--format=%H", "--", rel],
                           capture_output=True, text=True)
    except OSError:
        return None
    if r.returncode != 0:
        return None
    return len([l for l in r.stdout.splitlines() if l.strip()])


def shown(p: Path, root: Path) -> str:
    return p.relative_to(root).as_posix() if p.is_relative_to(root) else p.name


def scan(vault: Path, root: Path, threshold: int, today: date) -> dict:
    findings, not_verified = [], []
    names = vault_index(vault)
    has_git = git_ok(vault)
    if not has_git:
        not_verified.append("NOT_VERIFIED: no git repository here, so the `aged` signal was not measured")
    cache: dict = {}
    for f in memory.memory_files(vault):
        rel = shown(f, root)
        try:
            lines = f.read_bytes().decode("utf-8").split("\n")
        except (OSError, UnicodeDecodeError) as e:
            not_verified.append(f"NOT_VERIFIED: {rel} could not be read ({type(e).__name__})")
            continue
        start = next((i for i, l in enumerate(lines) if l.startswith(memory.MARKER)), None)
        if start is None:
            continue
        for i in range(start + 1, len(lines)):
            m = memory.ENTRY.match(lines[i])
            if not m:
                continue
            at = f"{rel}:{i + 1}"
            fields = dict(memory.FIELD.findall(m.group(4)))
            entry_day = memory.valid_date(m.group(1))
            for p in cited_paths(m.group(2) + "\n" + m.group(3)):
                state, new = resolve(p, vault, names)
                if state == "dead":
                    findings.append((at, "dead-path", f"`{p}` does not exist in the vault"))
                elif state == "moved":
                    findings.append((at, "moved", f"`{p}` is now `{new}`"))
                elif has_git and entry_day and (vault / p).is_file():
                    key = (p, entry_day)
                    if key not in cache:
                        cache[key] = commits_after(vault, p, entry_day)
                    n = cache[key]
                    if n is None:
                        not_verified.append(f"NOT_VERIFIED: {at} git could not count the commits of `{p}`")
                    elif n >= threshold:
                        findings.append((at, "aged", f"`{p}` had {n} commits after {m.group(1)} (threshold {threshold})"))
            end = memory.valid_date(fields.get("stale_after", ""))
            if end and end < today:
                findings.append((at, "expired", f"stale_after {end.isoformat()} is before {today.isoformat()}"))
            if fields.get("superseded_by"):
                findings.append((at, "superseded", f"superseded_by {fields['superseded_by']} but the entry is still in a loaded file"))
    notes = vault / "notes"
    for n in sorted(notes.rglob("*.md")) if notes.is_dir() else []:
        try:
            text = n.read_bytes().decode("utf-8")
        except (OSError, UnicodeDecodeError) as e:
            not_verified.append(f"NOT_VERIFIED: {shown(n, root)} could not be read ({type(e).__name__})")
            continue
        block, _ = gate.split_frontmatter(text.split("\n"))
        if not block:
            continue
        fm, _ = gate.parse_fm(block)
        end = memory.valid_date(str(fm.get("stale_after") or ""))
        if end and end < today:
            findings.append((shown(n, root), "expired", f"stale_after {end.isoformat()} is before {today.isoformat()}"))
    return {"findings": findings, "not_verified": not_verified}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--vault", default="vault")
    ap.add_argument("--root", default=".")
    ap.add_argument("--threshold", type=int, default=3, help="commits after the entry date that make a cited file `aged`")
    ap.add_argument("--gate", action="store_true", help="rc 1 if there is any finding")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--today", help="YYYY-MM-DD (default: today)")
    a = ap.parse_args(argv)
    vault, root = Path(a.vault).resolve(), Path(a.root).resolve()
    if not vault.is_dir():
        print(f"ERROR: the vault '{vault}' does not exist.", file=sys.stderr)
        return 2
    if a.threshold < 1:
        ap.error("--threshold must be at least 1")
    try:
        today = date.fromisoformat(a.today) if a.today else date.today()
    except ValueError:
        ap.error("--today must be YYYY-MM-DD")
    res = scan(vault, root, a.threshold, today)
    found, nv = res["findings"], res["not_verified"]
    counts = {s: sum(1 for f in found if f[1] == s) for s in SIGNALS}
    if a.json:
        print(json.dumps({"counts": counts, "findings": [dict(at=x, signal=s, detail=d) for x, s, d in found],
                          "not_verified": nv}, ensure_ascii=False, indent=2))
    else:
        print("  ".join(f"{s}={counts[s]}" for s in SIGNALS))
        for at, s, d in found:
            print(f"{at} {s} {d}")
        for n in nv:
            print(n)
        print(f"{len(found)} finding(s), {len(nv)} not verified")
    if a.gate and found:
        return 1
    return 3 if nv else 0


if __name__ == "__main__":
    sys.exit(main())
