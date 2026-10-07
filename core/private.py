#!/usr/bin/env python3
"""private.py: folders Claude Code is told not to READ. Stdlib only.

    private.py --apply [--vault vault] [--settings .claude/settings.json]   write the deny rules
    private.py --check [--vault vault] [--settings .claude/settings.json]   rc 1 if a derived rule is missing
    private.py --selftest                                                   proves the parser and the merge

`vault/private.txt` holds one path or glob per line, relative to `vault/` (`#` starts a comment). Each line
becomes one Claude Code permission rule in `permissions.deny`:  `Read(/vault/<line>)`.

Claude Code docs (https://code.claude.com/docs/en/permissions, "Read and Edit", read 2026-10-07):
  - the rule format is `Read(<path>)` and it goes in `permissions.deny` of `.claude/settings.json`;
  - the path uses gitignore syntax; a leading `/` anchors at the primary working directory for rules in
    project settings (so `/vault/x` is `<repo root>/vault/x` when Claude runs at the repo root);
  - `*` matches inside one path segment, `**` across directories;
  - deny rules apply to the built-in file tools and, best effort, to Grep/Glob and to file commands that
    Claude Code recognizes in Bash (cat, head, tail, sed, tee). They do NOT stop a script that opens files
    itself, `grep -r` run from the folder, other agents, or anyone who clones the repo. Only the OS-level
    sandbox does that. See docs/PRIVATE.md.
[VERIFY 2026-10-07] the docs were read on that date; Claude Code versions differ (some rule behaviors say
"requires v2.1.2xx"), so test a rule in your own version: ask Claude to read a file the rule covers.

The merge is conservative: rules already in the file stay, a rule is never duplicated, and a settings file
that is not valid JSON (or has an unexpected shape) is an ERROR (rc 2) and is never overwritten.

rc: 0 ok (or no private.txt: nothing to do) · 1 --check found a missing rule · 2 usage/error
"""
import argparse
import json
import re
import sys
import tempfile
from pathlib import Path

PREFIX = "/vault/"          # anchors at the project root in .claude/settings.json (see docstring)
DRIVE = re.compile(r"^[A-Za-z]:")


class PrivateError(Exception):
    """Something that cannot be understood or merged safely (rc 2)."""


def parse(text):
    """[glob, ...] in file order, without duplicates. A bad line raises PrivateError, it is never guessed."""
    out = []
    for n, raw in enumerate(text.splitlines(), 1):
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        if line.startswith(("/", "~", "!")) or DRIVE.match(line) or "\\" in line:
            raise PrivateError(f"private.txt:{n}: use a path relative to vault/ with `/` separators "
                               f"(no leading `/`, `~` or `!`, no drive letter, no backslash)")
        if ".." in line.split("/"):
            raise PrivateError(f"private.txt:{n}: `..` is not allowed: the path must stay inside vault/")
        if line not in out:
            out.append(line)
    return out


def rules(globs):
    return [f"Read({PREFIX}{g})" for g in globs]


def load_settings(path):
    """The settings dict; {} if the file does not exist. Malformed content raises PrivateError."""
    path = Path(path)
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, ValueError) as e:
        raise PrivateError(f"{path}: cannot be read as JSON ({e.__class__.__name__}); fix it by hand, nothing was written")
    if not isinstance(data, dict):
        raise PrivateError(f"{path}: the top level is not a JSON object; nothing was written")
    perms = data.get("permissions", {})
    if not isinstance(perms, dict) or not isinstance(perms.get("deny", []), list):
        raise PrivateError(f"{path}: `permissions` / `permissions.deny` have an unexpected shape; nothing was written")
    return data


def merge(data, wanted):
    """(data, added): `wanted` rules appended to permissions.deny when missing; nothing else is touched."""
    deny = data.setdefault("permissions", {}).setdefault("deny", [])
    added = [r for r in wanted if r not in deny]
    deny.extend(added)
    return data, added


def write_atomic(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False, suffix=".tmp") as f:
        f.write(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
        tmp = Path(f.name)
    tmp.replace(path)


def wanted_rules(vault):
    private = Path(vault) / "private.txt"
    if not private.exists():
        return None
    try:
        return rules(parse(private.read_text(encoding="utf-8")))
    except (OSError, UnicodeDecodeError) as e:
        raise PrivateError(f"{private}: cannot be read ({e.__class__.__name__})")


def apply(vault, settings):
    wanted = wanted_rules(vault)
    if wanted is None:
        print(f"no {vault}/private.txt: nothing to do.")
        return 0
    data = load_settings(settings)
    data, added = merge(data, wanted)
    if added:
        write_atomic(settings, data)
    print(f"OK: {len(wanted)} read-deny rule(s) from private.txt, {len(added)} added to {settings}.")
    return 0


def check(vault, settings):
    wanted = wanted_rules(vault)
    if wanted is None:
        print("NOT_VERIFIED: no private.txt, so no rule was derived.")
        return 0
    deny = load_settings(settings).get("permissions", {}).get("deny", [])
    missing = [r for r in wanted if r not in deny]
    for r in missing:
        print(f"missing: {r}")
    if missing:
        print("Run: python3 core/private.py --apply")
    return 1 if missing else 0


def selftest():
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        assert parse("# c\n\npeople/*/private/**  # x\npeople/*/private/**\nnotes/a.md\n") == ["people/*/private/**", "notes/a.md"]
        for bad in ("/abs", "~/x", "!x", "C:x", "a\\b", "../x", "a/../b"):
            try:
                parse(bad)
            except PrivateError:
                continue
            raise AssertionError(f"accepted {bad!r}")
        (d / "private.txt").write_text("people/*/private/**\n", encoding="utf-8")
        s = d / ".claude" / "settings.json"
        assert apply(d, s) == 0 and apply(d, s) == 0
        assert json.loads(s.read_text())["permissions"]["deny"] == ["Read(/vault/people/*/private/**)"]
        s.write_text("{not json", encoding="utf-8")
        try:
            apply(d, s)
        except PrivateError:
            assert s.read_text() == "{not json"
        else:
            raise AssertionError("malformed settings were accepted")
    print("selftest OK")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description="derive Claude Code read-deny rules from vault/private.txt")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--vault", default="vault")
    ap.add_argument("--settings", default=".claude/settings.json")
    a = ap.parse_args(argv)
    try:
        if a.selftest:
            return selftest()
        if a.apply:
            return apply(a.vault, a.settings)
        if a.check:
            return check(a.vault, a.settings)
    except PrivateError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2
    ap.print_usage(sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
