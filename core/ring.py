#!/usr/bin/env python3
"""ring.py: a note with no link at all (inbound or outbound) is an orphan. Stdlib only.

    ring.py [--vault vault]                lists the orphans (rc 0)
    ring.py --gate                         rc 1 if there is an orphan; this is what the hook runs
    ring.py --gate --stage                 only fails orphans that are IN THIS commit; the others become a WARNING
    ring.py --json                         {"total", "orphans", "exempt"}
    ring.py --selftest                     proves it fails when it should (orphan -> rc 1, cure -> rc 0)

Edge = wikilink `[[x]]` or link `[t](x.md)` that RESOLVES to another .md note. A dead link, a link
to itself, a link inside code and a link to an image do not count.
`inbox/` and `tasks/` are exempt from failing: quick capture cannot be blocked, because
whoever is blocked at capture uninstalls, and `tasks/` is where the TaskNotes plugin writes tasks created in the
interface, without asking for a link. Notes in those folders still count as the end of an edge.
rc: 0 ok · 1 fails · 2 could not verify (vault does not exist, git unavailable)
"""
import argparse
import collections
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unicodedata
from pathlib import Path
from urllib.parse import unquote

from gate import Index, mask, wikilinks

DEPOSITS = ("inbox", "tasks")  # quick capture and the TaskNotes plugin: blocking here makes people uninstall
MDLINK = re.compile(r"(?<!!)\[[^\]\n]*\]\(([^)\s]+?\.md)(?:#[^)]*)?\)")


def nfc(s):
    return unicodedata.normalize("NFC", s)


def is_deposit(rel):
    return any(rel == d or rel.startswith(d + "/") for d in DEPOSITS)


def analyze(vault):
    """([.md notes], degree of each). Degree = inbound + outbound edges."""
    idx = Index(vault, areas={})
    notes = sorted(r for r in idx.paths.values() if r.endswith(".md"))
    degree = collections.Counter()
    for rel in notes:
        text = mask(Path(vault, rel).read_bytes().decode("utf-8", errors="replace"))
        targets = [a for a, _ in wikilinks(text)] + [unquote(m) for m in MDLINK.findall(text)]
        for a in targets:
            r = idx.find(a, rel)
            if r and r != rel and r.endswith(".md"):
                degree[rel] += 1
                degree[r] += 1
    return notes, degree


def chk_orphans(notes, degree):
    return [r for r in notes if degree[r] == 0 and not is_deposit(r)]


def chk_in_commit(orphans, in_commit):
    return [r for r in orphans if nfc(r) in in_commit]


def staged(vault):
    """.md files this commit creates or changes, relative to the vault. `-z`: git quotes accented paths."""
    r = subprocess.run(["git", "-C", str(vault), "diff", "--cached", "--name-only", "--diff-filter=ACMR",
                        "-z", "--relative"], capture_output=True, check=True)
    return {nfc(c) for c in r.stdout.decode("utf-8").split("\0") if c.endswith(".md")}


TEACH = """
How to fix: open the note and connect it to a note that EXISTS with a [[wikilink]] in the middle of the text
(where the connection is real; a block of links in the footer is not the way), or point to it from an
existing note.
A link to a file that does not exist does not count. Just a quick capture? Drop it in inbox/ (or create the task in tasks/): they are exempt.
Deliberate bypass: git commit --no-verify
"""


def gate(vault, stage_only=False):
    if not Path(vault).is_dir():
        print(f"NOT_VERIFIED: the vault '{vault}' does not exist; the gate judged nothing.")
        return 2
    notes, degree = analyze(vault)
    orphans = chk_orphans(notes, degree)
    outside = []
    if stage_only:
        try:
            blocking = chk_in_commit(orphans, staged(vault))
        except (subprocess.CalledProcessError, FileNotFoundError, UnicodeDecodeError):
            print("NOT_VERIFIED: could not read the git stage (git missing, or the vault is not in a repo).")
            return 2
        outside = [o for o in orphans if o not in blocking]
        orphans = blocking
    if outside:
        print(f"WARNING — {len(outside)} orphan(s) OUTSIDE this commit (does not block):")
        print("".join(f"   {o}\n" for o in outside))
    if orphans:
        print(f"FAILS — {len(orphans)} note(s) with no inbound or outbound link:")
        print("".join(f"   {o}\n" for o in orphans) + TEACH)
        return 1
    print(f"OK — no orphans{' in this commit' if stage_only else ''} ({len(notes)} note(s) seen).")
    return 0


def selftest():
    failed = []

    def check(name, cond):
        print(f"  {'ok  ' if cond else 'FAILED'}  {name}")
        if not cond:
            failed.append(name)

    tmp = Path(tempfile.mkdtemp(prefix="ring-selftest-"))
    try:
        def write(rel, txt):
            (tmp / rel).parent.mkdir(parents=True, exist_ok=True)
            (tmp / rel).write_text(txt, encoding="utf-8")

        def rc(**kw):
            import io, contextlib
            with contextlib.redirect_stdout(io.StringIO()):
                return gate(tmp, **kw)
        write("a.md", "goes to [[b]]\n")
        write("b.md", "goes back to [[a]]\n")
        check("vault without orphans passes (rc 0)", rc() == 0)
        write("loose.md", "no link here\n")
        check("plant an orphan: gate fails (rc 1)", rc() == 1)
        write("loose.md", "now linked to [[a]]\n")
        check("cure the orphan: gate passes (rc 0)", rc() == 0)
        write("inbox/capture.md", "loose idea\n")
        check("orphan in inbox/ is exempt (rc 0)", rc() == 0)
        write("dead.md", "only points to [[does-not-exist]]\n")
        check("dead link is not an edge: orphan (rc 1)", rc() == 1)
        os.remove(tmp / "dead.md")
        if shutil.which("git"):
            subprocess.run(["git", "init", "-q"], cwd=tmp, check=True)
            write("new.md", "orphan in the commit\n")
            write("old.md", "orphan outside the commit\n")
            subprocess.run(["git", "add", "new.md"], cwd=tmp, check=True)
            check("--stage fails the orphan that is in the commit (rc 1)", rc(stage_only=True) == 1)
            subprocess.run(["git", "reset", "-q"], cwd=tmp, check=True)
            subprocess.run(["git", "add", "a.md"], cwd=tmp, check=True)
            check("--stage lets an orphan outside the commit pass (rc 0)", rc(stage_only=True) == 0)
        else:
            print("  NOT_VERIFIED  git missing: --stage was not tested")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print("\nSELFTEST FAILED: " + "; ".join(failed) if failed else "\nSELFTEST OK — the ring fails when it should")
    return 1 if failed else 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--vault", default="vault")
    ap.add_argument("--gate", action="store_true")
    ap.add_argument("--stage", action="store_true", help="with --gate: only fail what is in the git stage")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args(argv)
    if args.selftest:
        return selftest()
    if args.gate:
        return gate(args.vault, stage_only=args.stage)
    if not Path(args.vault).is_dir():
        print(f"ERROR: vault does not exist: {args.vault}", file=sys.stderr)
        return 2
    notes, degree = analyze(args.vault)
    orphans = chk_orphans(notes, degree)
    exempt = [r for r in notes if degree[r] == 0 and is_deposit(r)]
    if args.json:
        print(json.dumps({"total": len(notes), "orphans": orphans, "exempt": exempt}, ensure_ascii=False))
    else:
        for o in orphans:
            print(f"ORPHAN {o}")
        print(f"{len(orphans)} orphan(s) of {len(notes)} note(s); {len(exempt)} exempt (inbox/ and tasks/)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
