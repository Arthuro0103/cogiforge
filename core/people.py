#!/usr/bin/env python3
"""people.py: team mode. Keeps one person from editing another person's folder. Stdlib only.

    people.py [--vault vault] [--staged]   judges what is in the git stage (used by the hook)
    people.py --selftest                   proves it blocks when it should (and that nothing-checked is not OK)

Team mode exists only when `<vault>/roles.txt` exists. One line per person, `#` starts a comment:

    handle  admin|member  email

The e-mail is matched, case-insensitively, against `git config user.email` of whoever commits.
WITHOUT `roles.txt` this script is silent and returns 0: solo mode is unchanged.

The rules (an admin passes everything):
  author     the commit's e-mail has no line in roles.txt: blocked, ask an admin to add you
  person     a member touches `people/<other>/`: blocked (own folder, `people/<you>/`, is free)
  admin      a member touches `roles.txt` or `areas.txt`: blocked
  project    a member CREATES `projects/<new>/instructions.md`: blocked (editing an existing one is fine)

Honest limit: git has no permission per folder. This is a convention enforced by a local hook, which
`git commit --no-verify` skips. Real enforcement is the host: CODEOWNERS plus branch protection.

The output is `file: reason` and NEVER the content of a file. A `roles.txt` that exists but holds no valid
line, or cannot be read, is `NOT_VERIFIED` (rc 3), never OK: a check that touched nothing proves nothing.

rc: 0 clean (or solo mode) · 1 blocked · 2 usage/error (git unavailable, bad line in roles.txt) ·
    3 team mode could not be verified (roles.txt unreadable or empty)
"""
import argparse
import re
import subprocess
import sys
import tempfile
import shutil
from pathlib import Path

ROLES = ("admin", "member")
ADMIN_ONLY = ("roles.txt", "areas.txt")
PERSON_DIR = re.compile(r"^people/([^/]+)/")
NEW_PROJECT = re.compile(r"^projects/[^/]+/instructions\.md$")


class RolesError(Exception):
    """roles.txt has a line that cannot be understood (rc 2)."""


def parse_roles(text):
    """{email (casefolded): (handle, role)}. A bad line raises RolesError, it is never guessed."""
    out = {}
    for n, line in enumerate(text.splitlines(), 1):
        line = line.split("#", 1)[0].strip()
        if not line:
            continue
        parts = line.split()
        if len(parts) != 3 or parts[1] not in ROLES or "@" not in parts[2]:
            raise RolesError(f"roles.txt:{n}: expected `handle admin|member email`")
        out[parts[2].casefold()] = (parts[0], parts[1])
    return out


def chk_author(me, rel_changes):
    """The commit's author has no line in roles.txt. `me` is None when unknown."""
    if me is None:
        return ["(author): your git e-mail is not in roles.txt; ask an admin to add a line for you"]
    return []


def chk_other_person(me, rel_changes):
    """A member touches the folder of another person (including `_template`)."""
    if me is None or me[1] == "admin":
        return []
    out = []
    for _, rel in rel_changes:
        m = PERSON_DIR.match(rel)
        if m and m.group(1) != me[0]:
            out.append(f"{rel}: folder of '{m.group(1)}'; yours is people/{me[0]}/")
    return out


def chk_admin_files(me, rel_changes):
    """A member touches roles.txt or areas.txt."""
    if me is None or me[1] == "admin":
        return []
    return [f"{rel}: only an admin changes this file" for _, rel in rel_changes if rel in ADMIN_ONLY]


def chk_new_project(me, rel_changes):
    """A member creates a project root (status A); editing an existing one is allowed."""
    if me is None or me[1] == "admin":
        return []
    return [f"{rel}: only an admin creates a project" for st, rel in rel_changes
            if st == "A" and NEW_PROJECT.match(rel)]


CHECKS = (chk_author, chk_other_person, chk_admin_files, chk_new_project)


def judge(roles, email, changes, vault="vault"):
    """[findings]. `changes` = [(status, path relative to the repo root)]; only paths under `vault/` count."""
    prefix = vault.rstrip("/") + "/"
    rel_changes = [(st, p[len(prefix):]) for st, p in changes if p.startswith(prefix)]
    me = roles.get((email or "").casefold())
    found = []
    for check in CHECKS:
        found.extend(check(me, rel_changes))
    return found


def staged_changes():
    r = subprocess.run(["git", "diff", "--cached", "--name-status", "--no-renames", "--diff-filter=ACMRD", "-z"],
                       capture_output=True, check=True)
    parts = [c for c in r.stdout.decode("utf-8").split("\0") if c]
    return [(parts[i], parts[i + 1]) for i in range(0, len(parts) - 1, 2)]


def git_email():
    r = subprocess.run(["git", "config", "user.email"], capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 else ""


def run(vault, changes, email, prefix="vault"):
    """rc for a vault dir, a list of changes (paths under `prefix`) and an author e-mail."""
    roles_file = Path(vault) / "roles.txt"
    if not roles_file.exists():
        return 0  # solo mode: silent
    try:
        roles = parse_roles(roles_file.read_text(encoding="utf-8"))
    except OSError as e:
        print(f"NOT_VERIFIED: roles.txt could not be read ({e.__class__.__name__}); nothing was judged.")
        return 3
    except RolesError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2
    if not roles:
        print("NOT_VERIFIED: roles.txt has no line, so nobody could be judged; add the first admin.")
        return 3
    found = judge(roles, email, changes, vault=prefix)
    for f in found:
        print(f)
    if found:
        print(f"{len(found)} finding(s) in the stage. Real enforcement is CODEOWNERS plus branch protection.")
        return 1
    print(f"OK: {len(changes)} change(s) checked in team mode.")
    return 0


def selftest():
    failed = []

    def check(name, cond):
        print(f"  {'ok  ' if cond else 'FAILED'}  {name}")
        if not cond:
            failed.append(name)

    roles = parse_roles("# team\nana admin ana@example.com\nbia member bia@example.com\n")
    mod = lambda p: [("M", f"vault/{p}")]
    add = lambda p: [("A", f"vault/{p}")]

    def blocked(email, changes):
        return bool(judge(roles, email, changes))

    check("member in their own folder passes", not blocked("bia@example.com", mod("people/bia/memory/profile.md")))
    check("member in another folder is blocked", blocked("bia@example.com", mod("people/ana/memory/profile.md")))
    check("member deleting in another folder is blocked", blocked("bia@example.com", [("D", "vault/people/ana/x.md")]))
    check("member on roles.txt is blocked", blocked("bia@example.com", mod("roles.txt")))
    check("member on areas.txt is blocked", blocked("bia@example.com", mod("areas.txt")))
    check("member creating a project is blocked", blocked("bia@example.com", add("projects/new/instructions.md")))
    check("member editing a project passes", not blocked("bia@example.com", mod("projects/old/instructions.md")))
    check("member note in notes/ passes", not blocked("bia@example.com", add("notes/learning/x.md")))
    check("admin in another folder passes", not blocked("ana@example.com", mod("people/bia/memory/profile.md")))
    check("admin on roles.txt passes", not blocked("ana@example.com", mod("roles.txt")))
    check("unknown author is blocked", blocked("eve@example.com", add("notes/learning/x.md")))
    check("no author e-mail is blocked", blocked("", add("notes/learning/x.md")))
    check("e-mail match ignores case", not blocked("bia@example.com".upper(), add("notes/learning/x.md")))

    tmp = Path(tempfile.mkdtemp(prefix="people-selftest-"))
    try:
        import contextlib
        import io

        def rc(changes, email):
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                return run(tmp, changes, email, prefix="vault")
        check("solo mode (no roles.txt) is silent rc 0", rc(mod("people/ana/x.md"), "") == 0)
        (tmp / "roles.txt").write_text("# nobody yet\n", encoding="utf-8")
        check("empty roles.txt is NOT_VERIFIED rc 3, never OK", rc(mod("notes/x.md"), "a@example.com") == 3)
        (tmp / "roles.txt").write_text("ana admin\n", encoding="utf-8")
        check("bad line in roles.txt is rc 2", rc(mod("notes/x.md"), "a@example.com") == 2)
        (tmp / "roles.txt").write_text("ana admin ana@example.com\nbia member bia@example.com\n", encoding="utf-8")
        check("team mode blocks a member in another folder (rc 1)", rc(mod("people/ana/x.md"), "bia@example.com") == 1)
        check("team mode passes a member note (rc 0)", rc(add("notes/learning/x.md"), "bia@example.com") == 0)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print("\nSELFTEST FAILED: " + "; ".join(failed) if failed else "\nSELFTEST OK: people blocks when it should")
    return 1 if failed else 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--vault", default="vault")
    ap.add_argument("--staged", action="store_true", help="judge the git stage (default and only source)")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args(argv)
    if args.selftest:
        return selftest()
    if not (Path(args.vault) / "roles.txt").exists():
        return 0
    try:
        changes = staged_changes()
    except (subprocess.CalledProcessError, FileNotFoundError, UnicodeDecodeError):
        print("ERROR: could not read the git stage; nothing was judged.", file=sys.stderr)
        return 2
    return run(args.vault, changes, git_email(), prefix=args.vault)


if __name__ == "__main__":
    sys.exit(main())
