#!/usr/bin/env python3
"""target.py: a new note says what it is FOR. Stdlib only.

    target.py [--vault vault] --staged

"The target comes first" (vault/CLAUDE.md): an item is only processed when a file that already existed
changed, so a new note under `notes/` declares `target:` in its frontmatter: a path that exists, or `none`
(a legitimate answer: the idea stays, with a date, and nobody is told it is used). Whether that path exists
is the job of gate.py (`dead-target`); this check only asks that the field is there.

It judges only the notes that THIS commit ADDS. An old note, an edited note, `inbox/` and `tasks/` are never
asked. By default it only warns (rc 0): quick capture must never be blocked. `target: block` in
vault/gate.txt turns the same report into a blocked commit; `target: warn` is the default.
rc: 0 ok or warned · 1 blocked (mode block) · 2 gate.txt unreadable or malformed · 3 NOT_VERIFIED (git could not say what is staged)
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import gate  # noqa: E402

MODES = ("warn", "block")


def target_mode(vault: Path) -> str:
    """`warn` (default) or `block`, from the `target:` line of vault/gate.txt. Other lines belong to ring.py."""
    f = vault / "gate.txt"
    if not f.exists():
        return "warn"
    try:
        lines = f.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError) as e:
        raise ValueError(f"vault/gate.txt exists but cannot be read ({type(e).__name__})")
    mode = "warn"
    for n, raw in enumerate(lines, 1):
        key, sep, value = raw.split("#", 1)[0].strip().partition(":")
        if key.strip() == "target" and sep:
            mode = value.strip()
            if mode not in MODES:
                raise ValueError(f"vault/gate.txt line {n}: unknown target value '{mode}' (use warn or block)")
    return mode


def added(vault: Path) -> list[str]:
    """Notes under notes/ that this commit creates, relative to the vault."""
    r = subprocess.run(["git", "-C", str(vault), "diff", "--cached", "--name-only", "--diff-filter=A", "-z", "--relative"],
                       capture_output=True, check=True)
    names = (unicodedata.normalize("NFC", c) for c in r.stdout.decode("utf-8").split("\0"))
    return sorted(c for c in names if c.endswith(".md") and c.startswith("notes/"))


def real_path(vault: Path, rel: str, exists=os.path.exists, entries=lambda d: os.listdir(d)) -> Path:
    """`rel` is NFC (that is how it is reported), but on Linux the file keeps the spelling git gave it, often NFD.
    macOS looks names up without caring; Linux does not, so walk the path and match each part by its NFC form."""
    p = vault / rel
    if exists(p):
        return p
    cur = vault
    for part in Path(rel).parts:
        nxt = cur / part
        if not exists(nxt):
            try:
                found = [e for e in entries(cur) if unicodedata.normalize("NFC", e) == part]
            except OSError:
                found = []
            if found:
                nxt = cur / found[0]
        cur = nxt
    return cur


def declared(vault: Path, rel: str) -> bool:
    text = real_path(vault, rel).read_bytes().decode("utf-8", errors="replace")
    block, _ = gate.split_frontmatter(text.split("\n"))
    value = gate.parse_fm(block)[0].get("target") if block is not None else None
    return bool(str(value).strip()) if value is not None else False


TEACH = """
How to fix: add `target:` to the frontmatter of each note: the path of the file that already existed and
that this note changes, or `target: none` if it changes nothing yet (that is allowed; it only says so out loud).
A note whose target is `none` stays a trace, not a result.
"""


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--vault", default="vault")
    ap.add_argument("--staged", action="store_true", required=True)
    a = ap.parse_args(argv)
    vault = Path(a.vault)
    if not vault.is_dir():
        print(f"NOT_VERIFIED: the vault '{vault}' does not exist; the target check judged nothing.")
        return 3
    try:
        mode = target_mode(vault)
    except ValueError as e:
        print(f"ERROR: {e}. The target check judged nothing, so the commit is blocked until it is fixed.")
        return 2
    try:
        new = added(vault)
    except (subprocess.CalledProcessError, FileNotFoundError, UnicodeDecodeError):
        print("NOT_VERIFIED: could not read the git stage (git missing, or the vault is not in a repo).")
        return 3
    missing = [rel for rel in new if not declared(vault, rel)]
    if not missing:
        print(f"OK — {len(new)} new note(s) in this commit, all with a target.")
        return 0
    word = "FAILS" if mode == "block" else "WARNING"
    print(f"{word} — {len(missing)} new note(s) without `target:` (vault/gate.txt: target: {mode}"
          f"{', does not block' if mode == 'warn' else ''}):")
    print("".join(f"   {m}\n" for m in missing) + TEACH)
    return 1 if mode == "block" else 0


if __name__ == "__main__":
    sys.exit(main())
