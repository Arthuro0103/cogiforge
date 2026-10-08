#!/usr/bin/env python3
"""new_project.py: creates a project in the vault the way the example project does, and proves it fits.

Usage:
    python3 tools/new_project.py <name> --target "<one sentence>" [--type TYPE] [--status active|paused|closed]
                                 [--what "<short text for the index>"] [--vault DIR] [--dry-run]

What it does, in this order:
  1. validates EVERYTHING (name, target, status, the index table, a folder that already exists);
  2. writes vault/projects/<name>/instructions.md from the example's structure;
  3. appends one row to vault/projects/_index.md, right after the last row of the table;
  4. runs tools/hub.py (write, then --check), core/gate.py and core/ring.py --gate on that vault.

The --target is the user's own sentence, copied unchanged. Nothing else is written about the user:
only the name, the target, the type and the status (rule 2 of the repo).
--dry-run prints what would be created and writes nothing.

rc: 0 ok · 1 invalid input or a check failed · 2 wrong usage
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NAME_RE = re.compile(r"[a-z0-9]+(-[a-z0-9]+)*")
MAX_NAME = 40
STATUSES = ("active", "paused", "closed")
EXAMPLE_TARGET = "describe in one sentence what exists in the world when this project succeeds"

BODY = """
# {title}

This file is the project's **root**: the point where everything that comes out of it connects.

## Quick facts

| | |
|---|---|
| where the work lives | folder, repo or link |
| deadline | date, or "no deadline" |
| next step | one concrete action |

## Why this matters

Write in your own words why this project exists. This is where Claude understands what to
prioritize. Do not write what you think you should feel; write what you feel.

## Your decisions

One line per decision, with the date and the reason in your words. E.g. `2026-10-03: start with the small version, because I want to test it in a week.`

## Open

What has not been decided or discovered yet. When it closes, move it to the decisions.

<!-- hub:start -->
_(no other file yet)_
<!-- hub:end -->
"""


def check_name(name: str, projects: Path) -> str | None:
    if not name:
        return "the name is empty. Use a few words, lowercase, joined by hyphens (example: my-first-app)."
    if "/" in name or ".." in name or "\\" in name:
        return f"the name {name!r} has a path character ('/', '\\' or '..'). Use only lowercase letters, numbers and hyphens."
    if any(c.isspace() for c in name):
        return f"the name {name!r} has a space. Replace spaces with hyphens (example: my-first-app)."
    if name != name.lower():
        return f"the name {name!r} has an uppercase letter. Use lowercase only: {name.lower()!r}."
    if len(name) > MAX_NAME:
        return f"the name has {len(name)} characters; the limit is {MAX_NAME}. Shorten it."
    if not NAME_RE.fullmatch(name):
        return (f"the name {name!r} is not valid. Use lowercase letters, numbers and single hyphens, "
                f"not at the start or the end (example: my-first-app).")
    if (projects / name).exists():
        return f"projects/{name}/ already exists. Pick another name; this tool never touches an existing project."
    return None


def check_text(label: str, value: str) -> str | None:
    if "\n" in value or "\r" in value:
        return f"{label} has a line break. Write it as one line."
    if "|" in value and label != "--target":
        return f"{label} has a '|', which breaks the index table. Remove it."
    return None


def yaml_value(value: str) -> str:
    """Plain when safe (like the example); quoted when YAML would read it differently. Text is unchanged."""
    if re.search(r": |\s#|^[\-?:,\[\]{}#&*!|>'\"%@`]|:$", value) or value != value.strip():
        return json.dumps(value, ensure_ascii=False)
    return value


def find_table_end(lines: list[str]) -> int | None:
    """Index (in lines) of the last row of the projects table, or None if there is no table."""
    head = next((i for i, l in enumerate(lines) if re.match(r"\|\s*project\s*\|", l)), None)
    if head is None or head + 1 >= len(lines) or not re.match(r"\|[\s\-:|]+\|\s*$", lines[head + 1]):
        return None
    last = head + 1
    for i in range(head + 2, len(lines)):
        if lines[i].startswith("|"):
            last = i
        else:
            break
    return last


def build(args, vault: Path):
    """Validates everything; returns (errors, plan). Writes nothing."""
    projects = vault / "projects"
    index = projects / "_index.md"
    errors: list[str] = []
    if (e := check_name(args.name, projects)):
        errors.append(e)
    target = args.target
    if not target.strip():
        errors.append("--target is empty. It must be the user's own sentence: what exists in the world when the project succeeds.")
    elif target.strip().casefold() == EXAMPLE_TARGET:
        errors.append("--target is the example's placeholder text. It must be the user's own sentence.")
    elif (e := check_text("--target", target)):
        errors.append(e)
    if args.status not in STATUSES:
        errors.append(f"--status {args.status!r} is not valid. Use one of: {', '.join(STATUSES)}.")
    if not args.type.strip():
        errors.append("--type is empty. Use a word such as software, school, work, personal, writing.")
    elif (e := check_text("--type", args.type)):
        errors.append(e)
    what = args.what if args.what is not None else target
    if not what.strip():
        errors.append("--what is empty.")
    elif (e := check_text("--what", what)):
        errors.append(e)
    lines, row_at = [], None
    if not index.is_file():
        errors.append(f"{index} does not exist, so the project could not be registered. Nothing was created. "
                      f"Restore projects/_index.md (a table with the header '| project | status | type | what it is |').")
    else:
        lines = index.read_text(encoding="utf-8").split("\n")
        row_at = find_table_end(lines)
        if row_at is None:
            errors.append("projects/_index.md has no projects table (header '| project | status | type | what it is |'). "
                          "Nothing was created. Restore the table first.")
        elif f"[[projects/{args.name}/instructions" in "\n".join(lines):
            errors.append(f"projects/_index.md already lists {args.name!r}. Pick another name or remove that row first.")
    if errors:
        return errors, None
    title = args.name
    file_text = (f"---\ntype: {args.type.strip()}\nstatus: {args.status}\n"
                 f"declared_target: {yaml_value(target)}\n---\n" + BODY.format(title=title))
    row = f"| [[projects/{args.name}/instructions\\|{args.name}]] | {args.status} | {args.type.strip()} | {what.strip()} |"
    return [], dict(dir=projects / args.name, file=projects / args.name / "instructions.md",
                    text=file_text, index=index, lines=lines, row_at=row_at, row=row)


def run_check(label: str, cmd: list[str]) -> bool:
    r = subprocess.run(cmd, capture_output=True, text=True, cwd=ROOT)
    out = (r.stdout + r.stderr).strip()
    print(f"[{label}] rc={r.returncode}")
    if r.returncode != 0:
        print(out)
    return r.returncode == 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("name")
    ap.add_argument("--target", required=True)
    ap.add_argument("--type", default="software")
    ap.add_argument("--status", default="active")
    ap.add_argument("--what")
    ap.add_argument("--vault", default=str(ROOT / "vault"))
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)
    vault = Path(args.vault).resolve()
    errors, plan = build(args, vault)
    if errors:
        for e in errors:
            print(f"ERROR: {e}", file=sys.stderr)
        print("Nothing was written.", file=sys.stderr)
        return 1
    if args.dry_run:
        print(f"DRY RUN (nothing written). Would create:\n--- {plan['file'].relative_to(vault)}\n{plan['text']}"
              f"--- append to projects/_index.md after the last table row:\n{plan['row']}")
        return 0
    plan["dir"].mkdir(parents=True)
    plan["file"].write_text(plan["text"], encoding="utf-8")
    lines = plan["lines"]
    lines.insert(plan["row_at"] + 1, plan["row"])
    plan["index"].write_text("\n".join(lines), encoding="utf-8")
    print(f"created projects/{args.name}/instructions.md and added the row to projects/_index.md")
    py = sys.executable
    v = str(vault)
    ok = run_check("hub", [py, "tools/hub.py", "--vault", v])
    ok = run_check("hub --check", [py, "tools/hub.py", "--vault", v, "--check"]) and ok
    ok = run_check("gate", [py, "core/gate.py", "--vault", v]) and ok
    ok = run_check("ring", [py, "core/ring.py", "--vault", v, "--gate"]) and ok
    if not ok:
        print(f"CHECK FAILED: the project was created but a check above did not pass. "
              f"Fix what it names (the files are in projects/{args.name}/) and run it again.", file=sys.stderr)
        return 1
    print("OK: hub, gate and ring pass.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
