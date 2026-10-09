#!/usr/bin/env python3
"""voice_check.py: checks a text against the voice rules of a person and of a project.

    python3 tools/voice_check.py <text.md> [--person PATH] [--project NAME] [--vault DIR] [--selftest]

Rules come from one or two voice.md files:
    person   --person PATH, default <vault>/memory/voice.md
    project  <vault>/projects/<NAME>/brand/voice.md  (only when --project is given)

Format of a voice.md: frontmatter (`type: voice`, `scope: person|project`, optional `inherits:`) and the
sections `## Phrases`, `## Never say`, `## Avoid`, `## Pairs`. Only `Never say` and `Avoid` become rules.
Empty list items, HTML comments and `<placeholder>` items are ignored. `inherits:` is read but not followed:
pass both files explicitly.

Matching is case-insensitive and NFKC-normalized. A one-word term matches whole words only; a term with a
space matches as a substring. Fenced code blocks and the frontmatter of the text are skipped.

The output carries file:line:[kind] term and NEVER the line itself.

rc: 0 clean · 1 found something · 2 unreadable file / usage error · 3 NOT_VERIFIED (no effective rule,
or nothing in the text was checkable): absence of a check is never "OK".
"""
import argparse
import contextlib
import io
import re
import sys
import tempfile
import unicodedata
import shutil
from pathlib import Path

KINDS = {"never say": "never", "avoid": "avoid"}
COMMENT_RE = re.compile(r"<!--.*?-->", re.S)
PLACEHOLDER_RE = re.compile(r"^<[^<>]*>$")
FENCE_RE = re.compile(r"^\s*(```|~~~)")


def normalize(text):
    """NFKC, case-folded, whitespace collapsed to single spaces."""
    return " ".join(unicodedata.normalize("NFKC", text).casefold().split())


def strip_frontmatter(lines):
    """Lines of the body, with frontmatter lines replaced by empty ones (line numbers stay true)."""
    if lines and lines[0].strip() == "---":
        for i in range(1, len(lines)):
            if lines[i].strip() == "---":
                return [""] * (i + 1) + lines[i + 1:]
    return lines


def parse_rules(text):
    """[(kind, term)] from the `Never say` and `Avoid` sections of a voice.md."""
    text = COMMENT_RE.sub("", text)
    section, rules = None, []
    for line in strip_frontmatter(text.splitlines()):
        m = re.match(r"^##\s+(.*?)\s*$", line)
        if m:
            section = KINDS.get(m.group(1).casefold())
            continue
        if section is None:
            continue
        m = re.match(r"^\s*[-*]\s+(.*?)\s*$", line)
        if not m:
            continue
        item = m.group(1).strip()
        if len(item) >= 2 and item[0] == item[-1] and item[0] in "\"'":
            item = item[1:-1].strip()
        if not item or PLACEHOLDER_RE.match(item):
            continue
        rules.append((section, normalize(item)))
    return rules


def checkable_lines(text):
    """[(line_number, normalized_line)] outside the frontmatter and fenced code blocks."""
    out, fence = [], None
    for n, line in enumerate(strip_frontmatter(text.splitlines()), 1):
        m = FENCE_RE.match(line)
        if m:
            if fence is None:
                fence = m.group(1)
            elif m.group(1) == fence:
                fence = None
            continue
        if fence is None and line.strip():
            out.append((n, normalize(line)))
    return out


def term_matches(term, line):
    if " " in term:
        return term in line
    return re.search(r"(?<!\w)" + re.escape(term) + r"(?!\w)", line) is not None


def find(text, rules):
    """[(line, kind, term)]: one per rule per line."""
    out = []
    for n, line in checkable_lines(text):
        for kind, term in rules:
            if term_matches(term, line):
                out.append((n, kind, term))
    return out


def read(path):
    return Path(path).read_text(encoding="utf-8")


def rule_files(args):
    """[(label, path, explicit)] in the order person, project."""
    vault = Path(args.vault)
    files = [("person", Path(args.person) if args.person else vault / "memory" / "voice.md", bool(args.person))]
    if args.project:
        files.append(("project", vault / "projects" / args.project / "brand" / "voice.md", True))
    return files


def run(args):
    try:
        text = read(args.text)
    except (OSError, UnicodeDecodeError) as e:
        print(f"ERROR: cannot read {args.text}: {type(e).__name__}", file=sys.stderr)
        return 2
    rules, used = [], []
    for label, path, explicit in rule_files(args):
        if not path.is_file():
            if explicit:
                print(f"ERROR: {label} voice file not found: {path}", file=sys.stderr)
                return 2
            print(f"note: no {label} voice file at {path}")
            continue
        try:
            found = parse_rules(read(path))
        except (OSError, UnicodeDecodeError) as e:
            print(f"ERROR: cannot read {path}: {type(e).__name__}", file=sys.stderr)
            return 2
        print(f"{label}: {len(found)} rule(s) from {path}")
        rules.extend(found)
        used.append(label)
    if not rules:
        print("NOT_VERIFIED: no effective rule found (no `Never say` or `Avoid` item): nothing was checked.")
        return 3
    if not checkable_lines(text):
        print(f"NOT_VERIFIED: {args.text} has no checkable line (empty, frontmatter or code only).")
        return 3
    hits = find(text, rules)
    for n, kind, term in hits:
        print(f"{args.text}:{n}: [{kind}] {term}")
    counts = f"{sum(1 for k, _ in rules if k == 'never')} never, {sum(1 for k, _ in rules if k == 'avoid')} avoid"
    if hits:
        print(f"{len(hits)} finding(s) in {args.text}; rules checked: {counts}")
        return 1
    print(f"OK: 0 findings in {args.text}; rules checked: {counts}")
    return 0


def selftest():
    failed = []

    def check(name, cond):
        print(f"  {'ok  ' if cond else 'FAILED'}  {name}")
        if not cond:
            failed.append(name)

    voice = ("---\ntype: voice\nscope: person\n---\n## Phrases\n- 2026-01-01 | \"hello\"\n"
             "## Never say\n- Synergy\n- <term>\n-\n<!-- - hidden -->\n- game changer\n"
             "## Avoid\n- art\n## Pairs\n- say: \"a\" | not: \"b\"\n")
    rules = parse_rules(voice)
    check("parses never and avoid only", rules == [("never", "synergy"), ("never", "game changer"), ("avoid", "art")])
    check("placeholder, empty item and comment are ignored", ("never", "<term>") not in rules and ("never", "hidden") not in rules)
    check("case-insensitive whole word", find("We love SYNERGY.\n", rules) == [(1, "never", "synergy")])
    check("word inside another word does not count", find("let us start\n", rules) == [])
    check("expression matches as substring", find("a real game  changer here\n", rules) == [(1, "never", "game changer")])
    check("term in a fenced code block does not count", find("```\nsynergy\n```\nclean\n", rules) == [])
    check("term in the text frontmatter does not count", find("---\ntitle: synergy\n---\nclean\n", rules) == [])
    check("line numbers are true after frontmatter", find("---\na: b\n---\nsynergy\n", rules) == [(4, "never", "synergy")])
    check("NFKC: full-width letters match", find("ｓｙｎｅｒｇｙ\n", rules) == [(1, "never", "synergy")])

    tmp = Path(tempfile.mkdtemp(prefix="voice-check-selftest-"))
    try:
        def rc(text, voice_text, extra=()):
            (tmp / "t.md").write_text(text, encoding="utf-8")
            if voice_text is not None:
                (tmp / "v.md").write_text(voice_text, encoding="utf-8")
            argv = [str(tmp / "t.md"), "--vault", str(tmp / "none"), *extra]
            if voice_text is not None:
                argv += ["--person", str(tmp / "v.md")]
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                return main(argv)
        check("clean text is rc 0", rc("hello there\n", voice) == 0)
        check("finding is rc 1", rc("big synergy\n", voice) == 1)
        check("no rule at all is rc 3, never OK", rc("hello\n", "## Never say\n- <term>\n## Avoid\n-\n") == 3)
        check("no voice file at all is rc 3", rc("hello\n", None) == 3)
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            missing = main([str(tmp / "absent.md"), "--vault", str(tmp)])
        check("missing text file is rc 2", missing == 2)
        check("code-only text is rc 3", rc("```\nsynergy\n```\n", voice) == 3)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print("\nSELFTEST FAILED: " + "; ".join(failed) if failed else "\nSELFTEST OK: voice_check")
    return 1 if failed else 0


def main(argv=None):
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("text", nargs="?")
    ap.add_argument("--person")
    ap.add_argument("--project")
    ap.add_argument("--vault", default="vault")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args(argv)
    if args.selftest:
        return selftest()
    if not args.text:
        ap.error("a text file is required")
    return run(args)


if __name__ == "__main__":
    sys.exit(main())
