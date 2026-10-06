#!/usr/bin/env python3
"""hub.py: the root of each project points to ALL the .md files of the project.

In vault/projects/<name>/instructions.md there is a GENERATED block between two markers. The script
rewrites only that block, with a full-path wikilink from vault/
(`[[projects/<name>/file|file]]`) for each .md of the project. A full path is the only form
Obsidian resolves without ambiguity. A hand-written list does not keep up with the project; the generated one does.

Usage:
    python3 tools/hub.py              # rewrites the block in each project root
    python3 tools/hub.py --check      # rc=1 if the disk differs from the generated block (does not write)
    python3 tools/hub.py --dry-run    # prints each project's block, does not write
    python3 tools/hub.py --selftest
    python3 tools/hub.py --vault DIR  # another vault (tests)

Admission rule: if vault/projects/_index.md exists, every project must appear in it.
A project folder without instructions.md is reported, never invented.
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

OPEN, CLOSE = "<!-- hub:start -->", "<!-- hub:end -->"
VAULT = Path(__file__).resolve().parent.parent / "vault"


def list_files(folder: Path) -> list[Path]:
    return sorted(p for p in folder.rglob("*.md") if p != folder / "instructions.md")


def generate(folder: Path, vault: Path) -> str:
    files = list_files(folder)
    lines = [OPEN]
    lines += [_link(p, vault) for p in files]
    if not files:
        lines.append("_(no other file yet)_")
    return "\n".join(lines + [CLOSE])


def _link(p: Path, vault: Path) -> str:
    rel = p.relative_to(vault).with_suffix("").as_posix()
    if any(c in p.stem for c in "|#") or "]]" in p.stem:
        return f"- `{rel}` (title with a character that breaks a wikilink)"
    return f"- [[{rel}|{p.stem}]]"


def current_block(text: str) -> str | None:
    i, j = text.find(OPEN), text.find(CLOSE)
    return text[i:j + len(CLOSE)] if 0 <= i < j else None


def process(folder: Path, vault: Path, check: bool, dry: bool) -> str:
    root = folder / "instructions.md"
    if not root.is_file():
        return "NO ROOT"
    new, text = generate(folder, vault), root.read_text(encoding="utf-8")
    current = current_block(text)
    if current is None and not list_files(folder):
        return "OK"  # no block and no extra files: nothing to register, nothing to touch
    if dry:
        print(f"# {folder.name}\n{new}\n")
        return "dry"
    if current == new:
        return "OK"
    if check:
        return "NO BLOCK" if current is None else "STALE"
    final = text.replace(current, new) if current else text.rstrip() + "\n\n" + new + "\n"
    root.write_text(final, encoding="utf-8")
    return "written"


def missing_from_index(vault: Path, projects: list[Path]) -> list[str]:
    index = vault / "projects" / "_index.md"
    if not index.is_file():
        return []
    text = index.read_text(encoding="utf-8")
    return [p.name for p in projects if p.name not in text]


def run(vault: Path, check: bool, dry: bool) -> int:
    base = vault / "projects"
    projects = sorted(p for p in base.iterdir() if p.is_dir()) if base.is_dir() else []
    bad = 0
    for p in projects:
        st = process(p, vault, check, dry)
        print(f"{st:10} {p.name}")
        bad += st in ("STALE", "NO BLOCK", "NO ROOT")
    for name in missing_from_index(vault, projects):
        print(f"NOT IN INDEX {name}  (every project goes in projects/_index.md)")
        bad += 1
    return 1 if check and bad else 0


def selftest() -> int:
    with tempfile.TemporaryDirectory() as td:
        v = Path(td)
        p = v / "projects" / "x"
        p.mkdir(parents=True)
        (p / "instructions.md").write_text("# x\n")
        empty = run(v, check=True, dry=False)
        (p / "a.md").write_text("a")
        stale = run(v, check=True, dry=False)
        run(v, check=False, dry=False)
        after = run(v, check=True, dry=False)
    ok = (empty, stale, after) == (0, 1, 0)
    print("selftest:", "OK" if ok else f"FAILED {(empty, stale, after)}")
    return 0 if ok else 1


def main(argv: list[str]) -> int:
    if "-h" in argv or "--help" in argv:
        print(__doc__)
        return 0
    known = {"--check", "--dry-run", "--selftest", "--vault"}
    pos = [a for i, a in enumerate(argv) if a not in known and not (i and argv[i - 1] == "--vault")]
    if pos:
        print(f"unknown flag: {pos[0]} (nothing was written)", file=sys.stderr)
        return 2
    if "--selftest" in argv:
        return selftest()
    vault = Path(argv[argv.index("--vault") + 1]) if "--vault" in argv else VAULT
    return run(vault, "--check" in argv, "--dry-run" in argv)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
