#!/usr/bin/env python3
"""conflicts.py: finds the files a sync tool leaves behind when two copies collide. Stdlib only.

    conflicts.py [PATH ...]    scans files/folders (default: vault)
    conflicts.py --staged      looks only at what is in the git stage (used by the hook)
    conflicts.py --json        machine-readable output: a list of {"file", "reason"}
    conflicts.py --selftest    proves it finds each pattern, and that it stays quiet on a normal note

What it flags (the reason is the second field of every output line):
  conflicted-copy     `name (conflicted copy ...)`          Dropbox, and others that copy its wording
  case-conflict       `name (Case Conflict)`                Dropbox, when two names differ only by case
  syncthing-conflict  `name.sync-conflict-<date>-<id>.md`   Syncthing
  icloud-placeholder  `.name.md.icloud`                     iCloud file that was never downloaded
  numbered-duplicate  `name (1).md` or `name 2.md`          iCloud and others, ONLY when `name.md` exists
                                                            in the same folder

The numbered case needs the sibling on purpose: a real note called `Chapter 2.md` with no `Chapter.md`
is not a conflict, and a detector that cries wolf on legitimate names gets switched off.

The output is `file:reason` and NEVER the content of a file.

rc: 0 clean · 1 found a conflict file · 2 usage/error (path missing, git unavailable) ·
    3 could not read (a folder or the git stage): not reading wins over reporting clean, never "clean"
"""
import argparse
import contextlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

SKIP_DIRS = {".git", "__pycache__", ".pytest_cache"}
COPY_RE = re.compile(r"\([^()]*conflicted copy[^()]*\)", re.IGNORECASE)
CASE_RE = re.compile(r"\(case conflict[^()]*\)", re.IGNORECASE)
SYNCTHING_RE = re.compile(r"\.sync-conflict-\d{8}-\d{6}", re.IGNORECASE)
PAREN_RE = re.compile(r"^(?P<base>.+) \(\d+\)$")
SPACE_RE = re.compile(r"^(?P<base>.+) \d+$")


def split_name(name):
    dot = name.rfind(".")
    if dot <= 0:
        return name, ""
    return name[:dot], name[dot:]


def reason_of(path, exists):
    """The reason `path` looks like a sync leftover, or None. `exists(p)` says whether a sibling exists."""
    p = Path(path)
    name = p.name
    if name.endswith(".icloud"):
        return "icloud-placeholder"
    if SYNCTHING_RE.search(name):
        return "syncthing-conflict"
    if COPY_RE.search(name):
        return "conflicted-copy"
    if CASE_RE.search(name):
        return "case-conflict"
    stem, ext = split_name(name)
    for rx in (PAREN_RE, SPACE_RE):
        m = rx.match(stem)
        if m and exists(str(p.with_name(m.group("base") + ext))):
            return "numbered-duplicate"
    return None


def scan_disk(paths):
    """Returns (findings, unreadable). findings: list of (file, reason)."""
    found, unreadable = [], []
    disk = os.path.exists
    for root in paths:
        if os.path.isfile(root):
            r = reason_of(root, disk)
            if r:
                found.append((os.path.normpath(root), r))
            continue
        for dirpath, dirs, files in os.walk(root, onerror=lambda e: unreadable.append(str(e.filename))):
            dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS)
            for f in sorted(files):
                full = os.path.join(dirpath, f)
                r = reason_of(full, disk)
                if r:
                    found.append((os.path.normpath(full), r))
    return found, unreadable


def git_list(*args):
    r = subprocess.run(["git", *args, "-z"], capture_output=True, check=True)
    return [c for c in r.stdout.decode("utf-8", "replace").split("\0") if c]


def scan_staged():
    """Only what this commit adds or changes; a sibling counts if it is in the index or on disk."""
    names = git_list("diff", "--cached", "--name-only", "--diff-filter=ACMR")
    indexed = {os.path.normpath(n) for n in git_list("ls-files")}

    def exists(p):
        return os.path.normpath(p) in indexed or os.path.exists(p)

    return [(os.path.normpath(n), r) for n in names for r in [reason_of(n, exists)] if r]


def selftest():
    tmp = Path(tempfile.mkdtemp(prefix="conflicts-selftest-"))
    try:
        v = tmp / "vault"
        v.mkdir()
        for n in ("note.md", "Chapter 2.md", "Plan (3).md", "ok (conflicted copy).txt", "a.md", "a (1).md",
                  "b.md", "b 2.md", "c (conflicted copy 2026-01-01).md", "d (Case Conflict).md",
                  "e.sync-conflict-20260101-120000-ABCDEFG.md", ".f.md.icloud"):
            (v / n).write_text("x", encoding="utf-8")
        got = {Path(f).name: r for f, r in scan_disk([str(v)])[0]}
        want = {
            "a (1).md": "numbered-duplicate", "b 2.md": "numbered-duplicate",
            "c (conflicted copy 2026-01-01).md": "conflicted-copy", "d (Case Conflict).md": "case-conflict",
            "e.sync-conflict-20260101-120000-ABCDEFG.md": "syncthing-conflict",
            ".f.md.icloud": "icloud-placeholder", "ok (conflicted copy).txt": "conflicted-copy",
        }
        ok = True
        if got != want:
            print(f"FAIL: expected {sorted(want)}, got {sorted(got)}")
            ok = False
        for legit in ("note.md", "Chapter 2.md", "Plan (3).md"):
            if legit in got:
                print(f"FAIL: false positive on {legit}")
                ok = False
        clean = tmp / "clean"
        clean.mkdir()
        (clean / "n.md").write_text("x", encoding="utf-8")
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            rcs = (main([str(clean)]), main([str(v)]), main([str(tmp / "missing")]))
        if rcs[:2] != (0, 1):
            print("FAIL: rc (clean must be 0, conflicts must be 1)")
            ok = False
        if rcs[2] != 2:
            print("FAIL: a missing path must be rc 2")
            ok = False
        print("selftest OK" if ok else "selftest FAILED")
        return 0 if ok else 1
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("paths", nargs="*")
    ap.add_argument("--staged", action="store_true")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args(argv)
    if args.selftest:
        return selftest()
    unreadable = []
    if args.staged:
        try:
            found = scan_staged()
        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            print(f"ERROR: could not list the git stage ({e})", file=sys.stderr)
            return 2
    else:
        paths = args.paths or ["vault"]
        missing = [p for p in paths if not os.path.exists(p)]
        if missing:
            print(f"ERROR: path does not exist, nothing was scanned: {', '.join(missing)}", file=sys.stderr)
            return 2
        found, unreadable = scan_disk(paths)
    if args.json:
        print(json.dumps([{"file": f, "reason": r} for f, r in found] +
                         [{"file": u, "reason": "unreadable"} for u in unreadable]))
    else:
        for f, r in found:
            print(f"{f}:{r}")
        print(f"{len(found)} conflict file(s)")
        for u in unreadable:
            print(f"{u}:unreadable")
        if unreadable:
            print(f"NOT_VERIFIED: {len(unreadable)} folder(s) not read; the result above does not cover them.")
    if unreadable:
        return 3
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main())
