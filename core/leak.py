#!/usr/bin/env python3
"""leak.py: fails text that carries personal data before it goes to a public repo.

Catches the PATTERN, not the context: /Users/<name> path, e-mail, BR phone, formatted CPF and
every term of the private blocklist. Stdlib only.

    leak.py [PATH ...]     scans files/folders (default: .)
    leak.py --staged       scans what is in the git stage (used by the hook)

The blocklist lives OUTSIDE the repo (one term per line, case-insensitive):
    ~/.config/cogiforge/blocklist.txt    (change it with LEAK_BLOCKLIST=/other/path)
If blocklist.txt is missing, the old name negra.txt is still read, with a WARNING (the file was renamed);
the old env var VAZAMENTO_NEGRA is also accepted, with a WARNING.
Without the list, only the generic patterns run and the output says `NOT_VERIFIED`: the private
part was not checked, and that never becomes "OK". `--require-list` turns this into rc=3.

The output carries file:line:type and NEVER the data found (the CI log is public).
Files named `blocklist.txt` or `negra.txt` are always ignored. `.leakignore` (one path per line,
relative to where it runs) exempts fixtures planted on purpose; `--no-ignore` turns it off.
A `.claude/settings.local.json` in the git index, in any folder of the repo and in both modes, is always
a finding (`settings-local-tracked`), even if `.leakignore` lists it: it holds commands approved with
"don't ask again". Ignore it with `**/.claude/settings.local.json` (without `**/` only the root is covered).

rc: 0 clean · 1 found a leak · 2 usage/error or unreadable file · 3 private list required and missing
"""
import argparse
import os
import re
import shlex
import subprocess
import sys
import unicodedata
from pathlib import Path

CONFIG_DIR = Path.home() / ".config" / "cogiforge"
BLOCKLIST_DEFAULT = CONFIG_DIR / "blocklist.txt"
LEGACY_BLOCKLIST_DEFAULT = CONFIG_DIR / "negra.txt"
BLOCKLIST_NAME = "blocklist.txt"
LEGACY_BLOCKLIST_NAME = "negra.txt"
BLOCKLIST_NAMES = (BLOCKLIST_NAME, LEGACY_BLOCKLIST_NAME)
IGNORE_FILE = ".leakignore"
# Claude Code's "don't ask again" writes approved commands (sometimes with a password inside) here
SETTINGS_LOCAL = ".claude/settings.local.json"
# with `**/` the line also covers subfolders; `.claude/settings.local.json` alone only covers the root
SETTINGS_LOCAL_IGNORE = "**/" + SETTINGS_LOCAL
SKIP_DIRS = {".git", "__pycache__", ".pytest_cache"}  # only what is never content: venv/node_modules ARE scanned

PATH_RE = re.compile(r"(?:/|\\)Users(?:/|\\)[A-Za-z0-9._-]+", re.IGNORECASE)  # includes the Windows style
# example.com/org/net (RFC 2606) only counts WHOLE: any suffix after example.com is already a real domain
EMAIL_RE = re.compile(
    r"(?<![\w.+-])([\w.+-]+)@(?!example\.(?:com|org|net)(?![\w-]|\.\w))"
    r"[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}\b")
SCP_USERS = {"git", "ssh", "hg"}  # `git@host:org/repo` is an scp address, not an e-mail
PHONE_RE = re.compile(
    r"(?<![\d(])(?:\+55\s?\(?\d{2}\)?\s?9?\d{4}-?\d{4}|\(\d{2}\)\s?9?\d{4}-?\d{4}|\d{2}\s9?\d{4}[-\s]\d{4})(?!\d)")
CPF_RE = re.compile(r"(?<![\d.])\d{3}\.\d{3}\.\d{3}-\d{2}(?!\d)")


def normalize(text):
    """NFKC (full-width becomes ASCII) without the invisible characters (zero-width, soft hyphen, BOM)."""
    return "".join(c for c in unicodedata.normalize("NFKC", text) if unicodedata.category(c) != "Cf")


def chk_path(line):
    return ["path"] if PATH_RE.search(line) else []


def chk_email(line):
    for m in EMAIL_RE.finditer(line):
        if m.group(1) in SCP_USERS and line[m.end():m.end() + 1] == ":":
            continue
        return ["email"]
    return []


def chk_phone(line):
    return ["phone"] if PHONE_RE.search(line) else []


def chk_cpf(line):
    return ["cpf"] if CPF_RE.search(line) else []


def chk_list(line, terms):
    lowered = line.casefold()
    return ["blocklist"] if any(t in lowered for t in terms) else []


def resolve_blocklist():
    """(path, [warnings]). Order: LEAK_BLOCKLIST, the old VAZAMENTO_NEGRA (WARNING), blocklist.txt,
    and, if that one is missing, the old negra.txt (WARNING: the file was renamed)."""
    if os.environ.get("LEAK_BLOCKLIST"):
        return Path(os.environ["LEAK_BLOCKLIST"]), []
    if os.environ.get("VAZAMENTO_NEGRA"):
        return Path(os.environ["VAZAMENTO_NEGRA"]), [
            "WARNING: env VAZAMENTO_NEGRA is the old name; use LEAK_BLOCKLIST."]
    if not BLOCKLIST_DEFAULT.is_file() and LEGACY_BLOCKLIST_DEFAULT.is_file():
        return LEGACY_BLOCKLIST_DEFAULT, [
            f"WARNING: the private list was renamed: rename {LEGACY_BLOCKLIST_DEFAULT} to {BLOCKLIST_DEFAULT}. "
            f"Reading the old name for now."]
    return BLOCKLIST_DEFAULT, []


def read_blocklist(path):
    """Lowercase terms, or None if the list does not exist or has no term."""
    try:
        text = Path(path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    terms = [normalize(t).strip().casefold() for t in text.splitlines()
             if t.strip() and not t.lstrip().startswith("#")]
    return terms or None  # an empty list checked nothing: it is absence, not "clean"


def findings_of_text(text, terms):
    """[(line, type)] — one per type per line."""
    out = []
    for n, line in enumerate(normalize(text).splitlines(), 1):
        kinds = (chk_path(line) + chk_email(line) + chk_phone(line)
                 + chk_cpf(line) + chk_list(line, terms))
        out.extend((n, t) for t in kinds)
    return out


def read_ignored(use):
    if not use or not Path(IGNORE_FILE).is_file():
        return set()
    lines = Path(IGNORE_FILE).read_text(encoding="utf-8").splitlines()
    return {os.path.normpath(l.strip()) for l in lines if l.strip() and not l.startswith("#")}


def files_of(paths):
    for c in paths:
        p = Path(c)
        if p.is_file():
            if p.name not in SKIP_DIRS:  # a worktree's `.git` is a FILE holding the machine's path
                yield p
            continue
        for root, dirs, names in os.walk(p):
            dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS)
            for name in sorted(n for n in names if n not in SKIP_DIRS):
                yield Path(root) / name


def decode(data):
    """Text of a file, or None if it is binary. Never drops a file for bad encoding:
    a file with an invalid byte can still carry the e-mail on the next line."""
    if data[:2] in (b"\xff\xfe", b"\xfe\xff"):
        return data.decode("utf-16", errors="replace")
    if b"\x00" in data[:8000]:
        return None
    return data.decode("utf-8", errors="replace")


def tracked():
    """Files versioned in git here (empty if not a git repo, or if git is not installed)."""
    try:
        r = subprocess.run(["git", "ls-files", "-z"], capture_output=True)
    except FileNotFoundError:
        return set()
    if r.returncode != 0:
        return set()
    return {os.path.normpath(c) for c in r.stdout.decode("utf-8", "replace").split("\0") if c}


def staged():
    r = subprocess.run(["git", "diff", "--cached", "--name-only", "--diff-filter=ACMR", "-z"],
                       capture_output=True, check=True)
    return [c for c in r.stdout.decode("utf-8").split("\0") if c]


def staged_text(path):
    r = subprocess.run(["git", "show", f":{path}"], capture_output=True)
    if r.returncode != 0:
        raise OSError(f"git show :{path} failed")
    return decode(r.stdout)


def is_settings_local(name):
    # case-insensitive: macOS and Windows write `.Claude/Settings.Local.json` to the same file
    n = unicodedata.normalize("NFC", str(name).replace(os.sep, "/")).lower()
    return n == SETTINGS_LOCAL or n.endswith("/" + SETTINGS_LOCAL)


def tracked_settings_local(roots=None, why=None):
    """Every settings.local.json in the git INDEX of the scanned path(s), as (name, key) pairs:
    `name` is the path from the repo top (for the report), `key` the absolute path (to count a
    file once, whatever found it).

    Read from git itself, not from the disk walk: a file deleted from disk but still in the
    index is still committed, a committed file that did not change is not in the staged diff,
    and the disk (NFD on macOS) and git (NFC) spell accented folders differently. Git runs in
    the repo of each scanned path (default: the current folder), never in the folder we stand in.

    Returns None when it could not look (git missing, unreadable index, no repo at all) and
    appends the reason to `why`: not looking never becomes "clean"."""
    found, seen_tops = [], set()
    for root in (roots or ["."]):
        d = root if os.path.isdir(root) else (os.path.dirname(root) or ".")
        try:
            top = subprocess.run(["git", "-C", d, "rev-parse", "--show-toplevel"], capture_output=True)
        except FileNotFoundError:
            if why is not None:
                why.append("git is not installed")
            return None
        if top.returncode != 0:
            if why is not None:
                if b"not a git repository" in top.stderr:
                    why.append(f"{shown(root)} is not inside a git repo")
                else:
                    why.append("git rev-parse failed")
            return None
        raw = top.stdout[:-1] if top.stdout.endswith(b"\n") else top.stdout  # bytes: no decode round trip
        if raw in seen_tops:
            continue
        seen_tops.add(raw)
        arg = raw if os.name != "nt" else raw.decode("utf-8", "replace")
        try:
            r = subprocess.run(["git", "-C", arg, "ls-files", "-z"], capture_output=True)
        except FileNotFoundError:
            if why is not None:
                why.append("git is not installed")
            return None
        if r.returncode != 0:
            if why is not None:
                why.append("git ls-files failed")
            return None
        base = os.fsdecode(raw)
        for c in r.stdout.decode("utf-8", "replace").split("\0"):
            if c and is_settings_local(c):
                found.append((c, os.path.normpath(os.path.join(base, c))))
    return found


def shown(name):
    """Path as printed: always with `/`, so the report reads the same on every OS."""
    return str(name).replace(os.sep, "/")


def main(argv=None):
    # the report carries non-ASCII text; the Windows console/pipe default (cp1252) would make it
    # invalid UTF-8 for the shell tools that read it back (grep calls such a file "binary")
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("paths", nargs="*")
    ap.add_argument("--staged", action="store_true")
    ap.add_argument("--require-list", action="store_true")
    ap.add_argument("--no-ignore", action="store_true")
    args = ap.parse_args(argv)

    blocklist_path, warnings = resolve_blocklist()
    for w in warnings:
        print(w)
    terms = read_blocklist(blocklist_path)
    ignored = read_ignored(not args.no_ignore)

    sources, unreadable = [], []  # sources: (name, text)
    try:
        if args.staged:
            for c in staged():
                try:
                    sources.append((c, staged_text(c)))
                except OSError:
                    unreadable.append(c)
        else:
            missing = [c for c in args.paths if not os.path.exists(c)]
            if missing:
                print(f"ERROR: path does not exist, nothing was scanned: {', '.join(missing)}", file=sys.stderr)
                return 2
            for p in files_of(args.paths or ["."]):
                try:
                    sources.append((os.path.normpath(p), decode(p.read_bytes())))
                except OSError:
                    unreadable.append(os.path.normpath(p))
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        print(f"ERROR: could not list the git stage ({e})", file=sys.stderr)
        return 2

    total, exempted = 0, []
    flagged = set()  # absolute paths with a finding: a file counts once, whoever found it
    scanned = {os.path.abspath(n) for n, _ in sources}
    # repo-wide and read from the git index, in both modes: .leakignore never exempts it
    why = []
    index_hits = tracked_settings_local(None if args.staged else args.paths, why)
    if index_hits is None:
        print(f"NOT_VERIFIED: could not read the git index ({why[0]}), so a tracked "
              f"settings.local.json may be missed")
        index_failed = bool(why) and not why[0].endswith("is not inside a git repo")
    else:
        index_failed = False
    for name, key in index_hits or []:
        # a public repo with this file leaks whatever the user approved with "don't ask again"
        print(f"{name}:0: settings-local-tracked")
        print("  Claude Code stores approved commands (sometimes with secrets) in this file; it must stay "
              f"local. Fix: git rm --cached {shlex.quote(':/' + name)} and add "
              f"`{SETTINGS_LOCAL_IGNORE}` to .gitignore.")
        total += 1
        flagged.add(key)
        scanned.add(key)

    versioned = set() if args.staged else tracked()
    for name, text in sources:
        key = os.path.abspath(name)
        if Path(name).name in BLOCKLIST_NAMES and (args.staged or os.path.normpath(name) in versioned):
            # the private list can never be in a commit; only the local copy, outside git, is ignored
            print(f"{shown(name)}:0: {'blocklist-staged' if args.staged else 'blocklist-in-repo'}")
            total += 1
            flagged.add(key)
            continue
        if text is None or Path(name).name in BLOCKLIST_NAMES:
            continue
        if os.path.normpath(name) in ignored:
            exempted.append(name)
            continue
        found = findings_of_text(text, terms or [])
        for n, kind in found:
            print(f"{shown(name)}:{n}: {kind}")
        total += len(found)
        if found:
            flagged.add(key)
    with_findings = len(flagged)

    for name in exempted:
        print(f"exempt ({IGNORE_FILE}): {shown(name)}")
    print(f"{total} finding(s) in {with_findings} file(s), of {len(scanned)} scanned")
    for name in unreadable:
        print(f"{shown(name)}: unreadable")
    if unreadable:
        print(f"NOT_VERIFIED: {len(unreadable)} file(s) not read; the result above does not cover them.")
    if terms is None:
        print("NOT_VERIFIED: private blocklist missing — only the generic patterns ran. "
              f"Create {BLOCKLIST_DEFAULT} (one term per line) to check the private part.")
        if args.require_list:
            return 3
    else:
        print(f"private list: {len(terms)} term(s) checked")
    return 1 if total else (2 if (unreadable or index_failed) else 0)


if __name__ == "__main__":
    sys.exit(main())
