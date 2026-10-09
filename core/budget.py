#!/usr/bin/env python3
"""budget.py: how many bytes a session loads before any work happens, and a ceiling on it. Stdlib only.

    budget.py [--vault vault] [--root DIR] [--json]       the report; rc 1 if a ceiling is crossed
    budget.py --staged                                    the hook: rc 1 only if THIS commit makes a loaded file bigger and a ceiling is crossed

Two numbers, in bytes (a token is about 4 bytes of English):
  every session   CLAUDE.md, vault/CLAUDE.md, the three memory files (profile, patterns, decisions) and the
                  `description:` of every skill. Paid in every session. Ceiling: ALWAYS_MAX.
  open a project  the above, plus what `cf-open-session <name>` reads: the project root, the 3 newest diary
                  entries and up to 5 open tasks. The WORST project counts. Ceiling: OPEN_MAX.
Why a ceiling: a context that is cut short is cut in silence. A session once answered "I do not know" to
3 of 3 questions whose hook had been cut off the end of an oversized index. A rule here only has to say
"this is too big" out loud, before the commit, while the fix is still one file.
rc: 0 within the ceilings · 1 over · 2 usage · 3 NOT_VERIFIED (none of the loaded files could be read)
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

ALWAYS_MAX = 32_000   # about 8k tokens. The empty skeleton already loads 24.5 KB (11.6 KB of it is skill descriptions), so 32 KB leaves ~7 KB for what you say
OPEN_MAX = 48_000     # the always-loaded part plus one project's reading (root, 3 diary entries, 5 tasks)
DIARY_READ, TASKS_READ = 3, 5
MEMORY = ("profile", "patterns", "decisions")
DESCRIPTION = re.compile(r"^description:\s*(.+)$", re.M)
TASK_OPEN = re.compile(r"^status:\s*(open|in-progress)\s*$", re.M)
PROJECT_LINK = re.compile(r"projects/([^/|\]\"']+)/instructions")


def size(path: Path) -> int | None:
    try:
        return path.stat().st_size if path.is_file() else None
    except OSError:
        return None


def skill_descriptions(root: Path) -> int:
    total = 0
    for f in sorted((root / ".claude" / "skills").glob("*/SKILL.md")):
        try:
            head = f.read_text(encoding="utf-8", errors="replace")[:4000]
        except OSError:
            continue
        m = DESCRIPTION.search(head)
        total += len((m.group(1) if m else "").encode("utf-8"))
    return total


def loaded_files(vault: Path, root: Path) -> list[Path]:
    return [root / "CLAUDE.md", vault / "CLAUDE.md"] + [vault / "memory" / f"{m}.md" for m in MEMORY]


def skill_files(root: Path) -> list[Path]:
    return sorted((root / ".claude" / "skills").glob("*/SKILL.md"))


def open_tasks(vault: Path) -> dict[str, list[Path]]:
    by: dict[str, list[Path]] = {}
    for f in sorted((vault / "tasks").glob("*.md")) if (vault / "tasks").is_dir() else []:
        try:
            text = f.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if TASK_OPEN.search(text):
            for name in set(PROJECT_LINK.findall(text)):
                by.setdefault(name, []).append(f)
    return by


def measure(vault: Path, root: Path) -> dict:
    files = {str(p.relative_to(root)) if p.is_relative_to(root) else p.name: size(p) for p in loaded_files(vault, root)}
    skills = skill_descriptions(root)
    always = sum(v or 0 for v in files.values()) + skills
    diary = sorted((vault / "memory" / "diary").glob("*.md"), reverse=True)[:DIARY_READ] if (vault / "memory" / "diary").is_dir() else []
    diary_bytes = sum(size(f) or 0 for f in diary)
    tasks = open_tasks(vault)
    projects = {}
    for d in sorted((vault / "projects").iterdir()) if (vault / "projects").is_dir() else []:
        rootfile = d / "instructions.md"
        if rootfile.is_file():
            t = sum(size(f) or 0 for f in tasks.get(d.name, [])[:TASKS_READ])
            projects[d.name] = {"root": size(rootfile) or 0, "tasks": t}
    worst = max(projects, key=lambda p: projects[p]["root"] + projects[p]["tasks"], default=None)
    open_cost = always + diary_bytes + (projects[worst]["root"] + projects[worst]["tasks"] if worst else 0)
    return {"files": files, "skill_descriptions": skills, "always": always, "diary": diary_bytes, "worst_project": worst,
            "worst": projects.get(worst), "open": open_cost, "projects": len(projects),
            "verified": any(v is not None for v in files.values()) or skills > 0}


def verdict(m: dict) -> list[str]:
    over = []
    if m["always"] > ALWAYS_MAX:
        over.append(f"every session loads {m['always']:,} bytes, ceiling {ALWAYS_MAX:,}")
    if m["open"] > OPEN_MAX:
        over.append(f"opening '{m['worst_project']}' loads {m['open']:,} bytes, ceiling {OPEN_MAX:,}")
    return over


TEACH = """
How to fix: shrink the biggest loaded file. For a memory file, `python3 tools/cool.py memory/<file>.md --keep 40`
shows what would move to vault/memory/archive/ (add --apply to do it, with the user's yes): the older dated lines
move word for word and one link stays behind. A project root that grew should keep its detail in project
files; a skill description is the skill author's to shorten.
Deliberate bypass: git commit --no-verify
"""


def report(m: dict) -> str:
    out = ["Context loaded before any work (bytes):"]
    for name, n in m["files"].items():
        out.append(f"  {name:<32}{'missing' if n is None else f'{n:,}':>10}")
    out.append(f"  {'skill descriptions':<32}{m['skill_descriptions']:>10,}")
    out.append(f"  {'EVERY SESSION':<32}{m['always']:>10,}   (ceiling {ALWAYS_MAX:,}, {100 * m['always'] / ALWAYS_MAX:.0f}%)")
    if m["worst_project"]:
        w = m["worst"]
        out.append(f"  worst project '{m['worst_project']}': root {w['root']:,} + {TASKS_READ} open tasks {w['tasks']:,} "
                   f"+ {DIARY_READ} diary entries {m['diary']:,}")
    out.append(f"  {'OPEN A PROJECT':<32}{m['open']:>10,}   (ceiling {OPEN_MAX:,}, {100 * m['open'] / OPEN_MAX:.0f}%, {m['projects']} project(s))")
    return "\n".join(out)


def sizes_at(rev: str, rels: list[str], cwd: Path) -> dict[str, int | None]:
    """Size of each path in the index (rev ':') or in HEAD, None where it does not exist there."""
    out = {}
    for rel in rels:
        r = subprocess.run(["git", "cat-file", "-s", f"{rev}{rel}"], cwd=cwd, capture_output=True, text=True)
        out[rel] = int(r.stdout) if r.returncode == 0 and r.stdout.strip().isdigit() else None
    return out


def grew(vault: Path, root: Path) -> bool | None:
    """True if a loaded file is bigger in the index than in HEAD. None if git could not tell."""
    try:
        top = Path(subprocess.run(["git", "rev-parse", "--show-toplevel"], cwd=root, capture_output=True, text=True,
                                  check=True).stdout.strip())
        rels = [p.resolve().relative_to(top.resolve()).as_posix() for p in loaded_files(vault, root) + skill_files(root)]
    except (subprocess.CalledProcessError, OSError, ValueError):
        return None
    now, before = sizes_at(":", rels, top), sizes_at("HEAD:", rels, top)
    return any((now[r] or 0) > (before[r] or 0) for r in rels)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--vault", default="vault")
    ap.add_argument("--root", help="the repo root that holds CLAUDE.md and .claude/ (default: the vault's parent folder)")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--staged", action="store_true")
    a = ap.parse_args(argv)
    vault = Path(a.vault).resolve()
    root = Path(a.root).resolve() if a.root else vault.parent
    if not vault.is_dir():
        print(f"NOT_VERIFIED: the vault '{vault}' does not exist, so no context was measured.")
        return 3
    m = measure(vault, root)
    if not m["verified"]:
        print("NOT_VERIFIED: none of the files a session loads could be read, so nothing was measured.")
        return 3
    over = verdict(m)
    if a.staged:
        g = grew(vault, root)
        if g is None:
            print("NOT_VERIFIED: could not compare the staged files with HEAD (git missing, or the vault is not in a repo).")
            return 3
        if not g or not over:
            return 0
    if a.json:
        print(json.dumps({**m, "over": over}, ensure_ascii=False, indent=2))
    else:
        print(report(m))
        for line in over:
            print(f"OVER: {line}")
        if over:
            print(TEACH)
    return 1 if over else 0


if __name__ == "__main__":
    sys.exit(main())
